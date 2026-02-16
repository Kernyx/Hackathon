#!/bin/bash
set -e

# Корень проекта (на VPS обычно /opt/hackathon)
PROJECT_ROOT="${DEPLOY_ROOT:-/opt/hackathon}"
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

# Добавление сервиса в список без дублей
add_service() {
    local svc="$1"
    for s in "${CHANGED_SERVICES[@]}"; do
        if [ "$s" = "$svc" ]; then
            return
        fi
    done
    CHANGED_SERVICES+=("$svc")
}

# Переход в корень проекта
cd "$PROJECT_ROOT" || { echo "Ошибка: директория $PROJECT_ROOT не найдена"; exit 1; }

# Создание директорий для логов, данных и бэкапов (первый запуск)
mkdir -p "$PROJECT_ROOT/logs/caddy" \
         "$PROJECT_ROOT/data/postgres" \
         "$PROJECT_ROOT/backups/postgres"

# Проверка наличия .env
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    log "❌ Файл .env не найден! Скопируй .env_example в .env и заполни переменные."
    exit 1
fi

# Проверка Docker
if ! command -v docker &>/dev/null; then
    log "❌ Docker не установлен или не в PATH."
    exit 1
fi
if ! docker compose version &>/dev/null; then
    log "❌ Docker Compose не доступен (нужен docker compose или docker-compose)."
    exit 1
fi

log "🚀 Деплой запущен"

# Проверка незакоммиченных изменений
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    log "⚠️ НЕЗАКОММИЧЕННЫЕ ИЗМЕНЕНИЯ! Деплой отменён."
    exit 1
fi

# Обновление кода
log "🔄 Обновление кода..."
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"

# Анализ изменений
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
if [[ -z "$CHANGED" ]]; then
    log "ℹ️ Нет изменений в коммите — проверка здоровья и выход"
    docker compose ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | tee -a "$LOG_FILE" || true
    [ -f "$PROJECT_ROOT/scripts/check-health.sh" ] && bash "$PROJECT_ROOT/scripts/check-health.sh" | tee -a "$LOG_FILE" || true
    echo "----------------------------------------" >> "$LOG_FILE"
    exit 0
fi

log "📝 Изменены файлы: $(echo "$CHANGED" | tr '\n' ' ')"

# === СЛУЧАЙ 3: Микросервисы / отдельные сервисы → точечная пересборка ===
CHANGED_SERVICES=()

# dir:service_name
SERVICES_MAP=(
    "services/frontend:frontend"
    "services/ai-agent-service:java-backend"
    "services/go-backend:go-backend"
    "services/ml-service:ml-service"
    "services/caddy:caddy"
)

for mapping in "${SERVICES_MAP[@]}"; do
    dir="${mapping%%:*}"
    service="${mapping##*:}"

    if echo "$CHANGED" | grep -q "^${dir}/"; then
        log "📝 Изменения обнаружены в сервисе ${service}"
        add_service "$service"
    fi
done

# Если были изменения в сервисах - пересобираем только их
if [ "${#CHANGED_SERVICES[@]}" -gt 0 ]; then
    log "🔄 Пересборка сервисов: ${CHANGED_SERVICES[*]}"
    BUILD_LOG=$(mktemp)
    if ! docker compose up -d --build "${CHANGED_SERVICES[@]}" 2>&1 | tee -a "$LOG_FILE" "$BUILD_LOG"; then
        if grep -q "snapshot.*does not exist\|failed to stat active key" "$BUILD_LOG"; then
            log "⚠️ BuildKit cache повреждён — очистка и повторная сборка..."
            docker builder prune -a -f 2>&1 | tee -a "$LOG_FILE"
            docker compose up -d --build "${CHANGED_SERVICES[@]}" 2>&1 | tee -a "$LOG_FILE"
        else
            log "❌ Ошибка сборки сервисов: ${CHANGED_SERVICES[*]}"
        fi
    fi
    rm -f "$BUILD_LOG"
fi

log "✅ Деплой завершён"
docker compose ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
if [ -f "$PROJECT_ROOT/scripts/check-health.sh" ]; then
    bash "$PROJECT_ROOT/scripts/check-health.sh" | tee -a "$LOG_FILE" || true
else
    log "⚠️ scripts/check-health.sh не найден — пропуск проверки здоровья"
fi
echo "----------------------------------------" >> "$LOG_FILE"
