#!/bin/bash
set -e

# Корень проекта (на VPS обычно /opt/hackathon)
PROJECT_ROOT="${DEPLOY_ROOT:-/opt/hackathon}"
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# Добавление сервиса в список без дублей
add_service() {
    local svc="$1"
    for s in "${CHANGED_SERVICES[@]}"; do
        [ "$s" = "$svc" ] && return
    done
    CHANGED_SERVICES+=("$svc")
}

# Ожидание healthy-статуса всех контейнеров (макс 90 сек)
wait_for_healthy() {
    log "⏳ Ожидание готовности сервисов..."
    local max_wait=90
    local elapsed=0
    local interval=5

    while [ "$elapsed" -lt "$max_wait" ]; do
        # Считаем контейнеры в статусе (health: starting)
        STARTING=$(docker compose --profile all ps 2>/dev/null | grep -c "(health: starting)" || true)
        if [ "$STARTING" -eq 0 ]; then
            log "✅ Все сервисы готовы (${elapsed}s)"
            return 0
        fi
        log "⏳ Ещё запускаются: $STARTING сервисов... (${elapsed}/${max_wait}s)"
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    log "⚠️ Таймаут ожидания (${max_wait}s). Некоторые сервисы могут быть не готовы."
    return 0
}

# Сборка с автоматическим восстановлением при битом кэше BuildKit
build_with_recovery() {
    local build_cmd="$1"
    BUILD_LOG=$(mktemp)

    if ! eval "$build_cmd" 2>&1 | tee -a "$LOG_FILE" "$BUILD_LOG"; then
        if grep -q "snapshot.*does not exist\|failed to stat active key" "$BUILD_LOG"; then
            log "⚠️ BuildKit cache повреждён — очистка и повторная сборка..."
            docker builder prune -a -f 2>&1 | tee -a "$LOG_FILE"
            eval "$build_cmd" 2>&1 | tee -a "$LOG_FILE"
        else
            log "❌ Ошибка сборки"
            rm -f "$BUILD_LOG"
            return 1
        fi
    fi
    rm -f "$BUILD_LOG"
    return 0
}

# === НАЧАЛО ===
cd "$PROJECT_ROOT" || { echo "Ошибка: директория $PROJECT_ROOT не найдена"; exit 1; }

# Создание директорий (первый запуск)
mkdir -p "$PROJECT_ROOT/logs/caddy" \
         "$PROJECT_ROOT/data/postgres" \
         "$PROJECT_ROOT/backups/postgres"

# Проверка .env
[ ! -f "$PROJECT_ROOT/.env" ] && { log "❌ Файл .env не найден!"; exit 1; }

# Проверка Docker
command -v docker &>/dev/null || { log "❌ Docker не установлен"; exit 1; }
docker compose version &>/dev/null || { log "❌ Docker Compose не доступен"; exit 1; }

log "🚀 Деплой запущен"

# Анализ изменений (код уже обновлён через workflow или вручную)
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
if [[ -z "$CHANGED" ]]; then
    log "ℹ️ Нет изменений — проверка здоровья"
    docker compose --profile all ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | tee -a "$LOG_FILE" || true
    [ -f "$PROJECT_ROOT/scripts/check-health.sh" ] && bash "$PROJECT_ROOT/scripts/check-health.sh" | tee -a "$LOG_FILE" || true
    exit 0
fi

log "📝 Изменены файлы: $(echo "$CHANGED" | tr '\n' ' ')"

# Маппинг директорий → сервисов compose
SERVICES_MAP=(
    "services/frontend:frontend"
    "services/ai-agent-service:java-backend"
    "services/go-backend:go-backend"
    "services/ml-service:ml-service"
    "services/caddy:caddy"
)

# Если изменился docker-compose.yml, .env или скрипты — полная пересборка
if echo "$CHANGED" | grep -qE '^(docker-compose\.yml|\.env)$'; then
    log "📝 Изменения в конфигурации — полная пересборка"
    build_with_recovery "docker compose --profile all up -d --build"
    log "✅ Деплой завершён (полная пересборка)"
else
    # Точечная пересборка изменённых сервисов
    CHANGED_SERVICES=()
    for mapping in "${SERVICES_MAP[@]}"; do
        dir="${mapping%%:*}"
        service="${mapping##*:}"
        if echo "$CHANGED" | grep -q "^${dir}/"; then
            log "📝 Изменения в сервисе: ${service}"
            add_service "$service"
        fi
    done

    if [ "${#CHANGED_SERVICES[@]}" -gt 0 ]; then
        log "🔄 Пересборка: ${CHANGED_SERVICES[*]}"
        build_with_recovery "docker compose up -d --build ${CHANGED_SERVICES[*]}"
    fi
    log "✅ Деплой завершён"
fi

# Ожидание готовности сервисов
wait_for_healthy

# Статус контейнеров
docker compose --profile all ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"

# Health check
if [ -f "$PROJECT_ROOT/scripts/check-health.sh" ]; then
    bash "$PROJECT_ROOT/scripts/check-health.sh" | tee -a "$LOG_FILE" || true
fi

echo "----------------------------------------" >> "$LOG_FILE"
