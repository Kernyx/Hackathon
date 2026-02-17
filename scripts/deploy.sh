#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
#  deploy.sh — Умный деплой с блокировкой, трекингом коммитов
#              и точечной пересборкой изменённых сервисов
#
#  Переменные окружения:
#    DEPLOY_ROOT    — корень проекта (default: /opt/hackathon)
#    FORCE_DEPLOY   — 1 = полная пересборка всех сервисов
# ──────────────────────────────────────────────────────────────

PROJECT_ROOT="${DEPLOY_ROOT:-/opt/hackathon}"
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"
LOCK_FILE="/tmp/hackathon-deploy.lock"
LAST_DEPLOY_FILE="$PROJECT_ROOT/.last_deploy_commit"
FORCE_DEPLOY="${FORCE_DEPLOY:-0}"
DEPLOY_START=$(date +%s)

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# ── Блокировка (с ожиданием до 5 мин) ──
# Если другой деплой запущен — ЖДЁМ, не выходим.
# Так два пуша подряд не конфликтуют: второй ждёт первый.
acquire_lock() {
    exec 9>"$LOCK_FILE"
    if ! flock --timeout 300 9; then
        log "❌ Не удалось получить блокировку за 5 минут"
        exit 1
    fi
    log "🔒 Блокировка получена (PID $$)"
}

# Добавление сервиса в список без дублей
add_service() {
    local svc="$1"
    for s in "${CHANGED_SERVICES[@]}"; do
        [ "$s" = "$svc" ] && return
    done
    CHANGED_SERVICES+=("$svc")
}

# Ожидание healthy-статуса (макс 120 сек)
wait_for_healthy() {
    log "⏳ Ожидание готовности сервисов..."
    local max_wait=120
    local elapsed=0
    local interval=5

    while [ "$elapsed" -lt "$max_wait" ]; do
        STARTING=$(docker compose --profile all ps 2>/dev/null | grep -c "(health: starting)" || true)
        if [ "$STARTING" -eq 0 ]; then
            log "✅ Все сервисы готовы (${elapsed}s)"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    log "⚠️ Таймаут ожидания (${max_wait}s). Некоторые сервисы могут быть не готовы."
    return 1
}

# Сборка с автоматическим восстановлением при битом кэше BuildKit
build_with_recovery() {
    local BUILD_LOG
    BUILD_LOG=$(mktemp)
    local -a cmd=("$@")

    if ! "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE" "$BUILD_LOG"; then
        if grep -q "snapshot.*does not exist\|failed to stat active key" "$BUILD_LOG"; then
            log "⚠️ BuildKit cache повреждён — очистка и повторная сборка..."
            docker builder prune -a -f 2>&1 | tee -a "$LOG_FILE"
            "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"
        else
            log "❌ Ошибка сборки"
            rm -f "$BUILD_LOG"
            return 1
        fi
    fi
    rm -f "$BUILD_LOG"
    return 0
}

# ═══════════════════════════════════════════════
#  НАЧАЛО
# ═══════════════════════════════════════════════
cd "$PROJECT_ROOT" || { echo "Ошибка: директория $PROJECT_ROOT не найдена"; exit 1; }
acquire_lock

mkdir -p "$PROJECT_ROOT/logs/caddy" \
         "$PROJECT_ROOT/data/postgres" \
         "$PROJECT_ROOT/backups/postgres"

[ ! -f "$PROJECT_ROOT/.env" ] && { log "❌ Файл .env не найден!"; exit 1; }

command -v docker &>/dev/null || { log "❌ Docker не установлен"; exit 1; }
docker compose version &>/dev/null || { log "❌ Docker Compose не доступен"; exit 1; }
docker compose config -q 2>/dev/null || { log "❌ Ошибка в docker-compose.yml"; exit 1; }

log "🚀 Деплой запущен"

# ── Определение изменений ──
# Сравниваем с последним УСПЕШНО задеплоенным коммитом,
# а не HEAD~1: так ни один коммит не пропускается,
# даже если пушили пачкой или деплой был отменён.
CURRENT_COMMIT=$(git rev-parse HEAD)
CHANGED=""
FULL_REBUILD=false

if [[ "$FORCE_DEPLOY" == "1" ]]; then
    log "🔄 Принудительная пересборка (FORCE_DEPLOY=1)"
    FULL_REBUILD=true
elif [ -f "$LAST_DEPLOY_FILE" ]; then
    LAST_COMMIT=$(cat "$LAST_DEPLOY_FILE")
    if [ "$LAST_COMMIT" = "$CURRENT_COMMIT" ]; then
        log "ℹ️ Код не менялся с последнего деплоя ($CURRENT_COMMIT)"
        docker compose --profile all ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | tee -a "$LOG_FILE" || true
        log "✅ Деплой не требуется"
        exit 0
    elif git rev-parse --verify "$LAST_COMMIT" >/dev/null 2>&1; then
        CHANGED=$(git diff --name-only "$LAST_COMMIT" "$CURRENT_COMMIT" 2>/dev/null || true)
        log "📊 Коммиты: ${LAST_COMMIT:0:8} → ${CURRENT_COMMIT:0:8}"
    else
        log "⚠️ Предыдущий коммит не найден — полная пересборка"
        FULL_REBUILD=true
    fi
else
    log "ℹ️ Первый деплой — полная пересборка"
    FULL_REBUILD=true
fi

# ── Маппинг директорий → сервисов compose ──
SERVICES_MAP=(
    "services/vite-project:frontend"
    "services/auth-service:auth-service"
    "services/ai-agent-service:java-backend"
    "services/go-backend:go-backend"
    "services/ml-service:ml-service"
    "services/caddy:caddy"
)

if [[ "$FULL_REBUILD" == "true" ]]; then
    log "🔄 Полная пересборка всех сервисов"
    build_with_recovery docker compose --profile all up -d --build --remove-orphans
elif echo "$CHANGED" | grep -qE '^(docker-compose\.yml|\.env)$'; then
    log "📝 Изменения в docker-compose.yml/.env — полный reconcile"
    build_with_recovery docker compose --profile all up -d --build --remove-orphans
else
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
        build_with_recovery docker compose up -d --build "${CHANGED_SERVICES[@]}"
    else
        log "ℹ️ Изменённые файлы не относятся к сервисам — пересборка не нужна"
    fi
fi

# Ожидание готовности
wait_for_healthy || true

# ── Сохраняем коммит после успешного деплоя ──
echo "$CURRENT_COMMIT" > "$LAST_DEPLOY_FILE"
log "📌 Задеплоен коммит: ${CURRENT_COMMIT:0:8}"

# ── Статус ──
docker compose --profile all ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"

# ── Очистка висящих образов (чтобы диск не забивался) ──
DANGLING=$(docker images -f "dangling=true" -q 2>/dev/null | wc -l)
if [ "$DANGLING" -gt 0 ]; then
    docker image prune -f >/dev/null 2>&1 || true
    log "🧹 Очищено $DANGLING висящих образов"
fi

# ── Время деплоя ──
DEPLOY_END=$(date +%s)
DURATION=$((DEPLOY_END - DEPLOY_START))
log "⏱️ Деплой завершён за ${DURATION}s"

echo "────────────────────────────────────────" >> "$LOG_FILE"
