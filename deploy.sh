#!/bin/bash
set -e

# Корень проекта (на VPS обычно /opt/hackathon)
PROJECT_ROOT="${DEPLOY_ROOT:-/opt/hackathon}"
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

# Переход в корень проекта
cd "$PROJECT_ROOT" || { echo "Ошибка: директория $PROJECT_ROOT не найдена"; exit 1; }

# Создание директорий для логов и данных (первый запуск / после чистой клонизации)
mkdir -p "$PROJECT_ROOT/logs" \
         "$PROJECT_ROOT/data/postgres" "$PROJECT_ROOT/data/rabbitmq" \
         "$PROJECT_ROOT/data/pgadmin" "$PROJECT_ROOT/data/caddy" \
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
    [ -f "$PROJECT_ROOT/check-health.sh" ] && bash "$PROJECT_ROOT/check-health.sh" | tee -a "$LOG_FILE" || true
    echo "----------------------------------------" >> "$LOG_FILE"
    exit 0
fi

log "📝 Изменены файлы: $(echo "$CHANGED" | tr '\n' ' ')"

# === СЛУЧАЙ 1: Изменения в инфраструктуре (.env или docker-compose.yml) ===
if echo "$CHANGED" | grep -qE "^(docker-compose\.yml|\.env)$"; then
    log "⚠️ Изменена инфраструктура — требуется полный перезапуск!"
    log "🛑 Останавливаем все сервисы..."
    docker compose --profile all down 2>&1 | tee -a "$LOG_FILE"
    
    log "🔄 Запускаем с новой конфигурацией..."
    docker compose --profile all up -d --build 2>&1 | tee -a "$LOG_FILE"
    
    log "✅ Полный перезапуск завершён"
    docker compose ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
    [ -f "$PROJECT_ROOT/check-health.sh" ] && bash "$PROJECT_ROOT/check-health.sh" | tee -a "$LOG_FILE" || true
    echo "----------------------------------------" >> "$LOG_FILE"
    exit 0
fi

# === СЛУЧАЙ 2: Caddyfile → reload Caddy ===
if echo "$CHANGED" | grep -q "^Caddyfile$"; then
    log "🔄 Перезагрузка Caddy..."
    if ! docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tee -a "$LOG_FILE"; then
        log "⚠️ Reload не удался — перезапуск"
        docker compose restart caddy 2>&1 | tee -a "$LOG_FILE"
    fi
fi

# === СЛУЧАЙ 3: Микросервисы → пересборка всего стека ===
REBUILD_NEEDED=false

SERVICES_MAP=(
    "services/frontend:frontend"
    "services/java-backend:java"
    "services/go-backend:go"
    "services/ml-service:ml"
)

for mapping in "${SERVICES_MAP[@]}"; do
    dir="${mapping%%:*}"
    profile="${mapping##*:}"

    if echo "$CHANGED" | grep -q "^${dir}/"; then
        log "📝 Изменения обнаружены в ${profile}"
        REBUILD_NEEDED=true
    fi
done

# Если были изменения в микросервисах - пересобираем весь стек
if [ "$REBUILD_NEEDED" = true ]; then
    log "🔄 Пересборка всех сервисов..."
    docker compose --profile all up -d --build 2>&1 | tee -a "$LOG_FILE"
fi

log "✅ Деплой завершён"
docker compose ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
if [ -f "$PROJECT_ROOT/check-health.sh" ]; then
    bash "$PROJECT_ROOT/check-health.sh" | tee -a "$LOG_FILE" || true
else
    log "⚠️ check-health.sh не найден — пропуск проверки здоровья"
fi
echo "----------------------------------------" >> "$LOG_FILE"
