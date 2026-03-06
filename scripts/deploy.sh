#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════
# Hackathon Deploy Script v2
# Вызывается из GitHub Actions (deploy.yml)
# или вручную: bash scripts/deploy.sh [service1 service2 ...]
# ══════════════════════════════════════════════

PROJECT_ROOT="${DEPLOY_ROOT:-/opt/hackathon}"
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"
COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-2}"
BUILD_TIMEOUT="${BUILD_TIMEOUT:-300}"  # 5 минут на сборку одного сервиса

# ─── Logging ────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# ─── Cleanup on exit ────────────────────────
cleanup() {
    local exit_code=$?
    [ -f "${ROLLBACK_FILE:-}" ] && rm -f "$ROLLBACK_FILE"
    [ -f "${BUILD_LOG:-}" ] && rm -f "$BUILD_LOG"
    if [ "$exit_code" -ne 0 ]; then
        log "❌ Deploy script exited with code $exit_code"
    fi
}
trap cleanup EXIT

# ─── Directories ────────────────────────────
cd "$PROJECT_ROOT" || { echo "Ошибка: $PROJECT_ROOT не найдена"; exit 1; }
mkdir -p "$PROJECT_ROOT/logs/caddy" \
         "$PROJECT_ROOT/data/postgres" \
         "$PROJECT_ROOT/backups/postgres"

# ─── Pre-flight checks ─────────────────────
[ ! -f "$PROJECT_ROOT/.env" ] && { log "❌ .env не найден!"; exit 1; }
command -v docker &>/dev/null || { log "❌ Docker не установлен"; exit 1; }
docker compose version &>/dev/null || { log "❌ Docker Compose не доступен"; exit 1; }

# Disk space check
AVAIL_MB=$(df -m "$PROJECT_ROOT" | awk 'NR==2{print $4}')
if [ "$AVAIL_MB" -lt 500 ]; then
    log "❌ ABORT: ${AVAIL_MB}MB свободно, нужно минимум 500MB"
    log "Попробуйте: docker system prune -af --volumes"
    exit 1
fi
log "💾 Свободно: ${AVAIL_MB}MB"

log "🚀 Деплой запущен"

# ─── Service mapping ───────────────────────
declare -A SMAP=(
    ["services/vite-project"]="frontend"
    ["services/auth-service"]="auth-service"
    ["services/ai-agent-service"]="java-backend"
    ["services/go-backend"]="go-backend"
    ["services/ml-ai-service"]="ml-service"
    ["services/caddy"]="caddy"
)

# ─── Determine changed services ───────────
CHANGED_SERVICES=()

if [ $# -gt 0 ]; then
    # Сервисы переданы как аргументы
    CHANGED_SERVICES=("$@")
    log "🔧 Сервисы из аргументов: ${CHANGED_SERVICES[*]}"
else
    # Auto-detect из git diff
    CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")

    if [ -z "$CHANGED" ]; then
        log "ℹ️ Нет изменений — только health check"
        [ -f "$PROJECT_ROOT/scripts/check-health.sh" ] && bash "$PROJECT_ROOT/scripts/check-health.sh" | tee -a "$LOG_FILE" || true
        exit 0
    fi

    log "Изменённые файлы: $(echo "$CHANGED" | tr '\n' ' ')"

    # docker-compose.yml или .env → ручной деплой
    if echo "$CHANGED" | grep -qE '^(docker-compose\.yml|\.env)$'; then
        log "⚠️ docker-compose.yml / .env изменены — требуется ручная проверка"
        log "Запустите: docker compose --profile all up -d"
        exit 0
    fi

    for dir in "${!SMAP[@]}"; do
        if echo "$CHANGED" | grep -q "^${dir}/"; then
            svc="${SMAP[$dir]}"
            log "📦 Изменения в: $svc"
            CHANGED_SERVICES+=("$svc")
        fi
    done
fi

if [ "${#CHANGED_SERVICES[@]}" -eq 0 ]; then
    log "ℹ️ Нет изменений в сервисах"
    exit 0
fi

# ─── Save rollback state ──────────────────
ROLLBACK_FILE=$(mktemp /tmp/rollback-XXXXXX.txt)
for svc in "${CHANGED_SERVICES[@]}"; do
    CONTAINER_ID=$(docker compose ps -q "$svc" 2>/dev/null || true)
    if [ -n "$CONTAINER_ID" ]; then
        IMAGE=$(docker inspect --format='{{.Image}}' "$CONTAINER_ID" 2>/dev/null || true)
        echo "${svc}|${IMAGE}" >> "$ROLLBACK_FILE"
    fi
done
log "📸 Состояние сохранено для rollback ($(wc -l < "$ROLLBACK_FILE") сервисов)"

# ─── Build & Deploy ───────────────────────
build_service() {
    local svc="$1"
    BUILD_LOG=$(mktemp /tmp/build-XXXXXX.log)

    log "🔨 Сборка: $svc"

    if ! timeout "$BUILD_TIMEOUT" docker compose up -d --build --no-deps "$svc" 2>&1 | tee -a "$LOG_FILE" "$BUILD_LOG"; then
        # BuildKit cache corruption → автоматическое восстановление
        if grep -q "snapshot.*does not exist\|failed to stat active key" "$BUILD_LOG" 2>/dev/null; then
            log "⚠️ BuildKit cache повреждён — очистка и повторная сборка..."
            docker builder prune -a -f 2>&1 | tee -a "$LOG_FILE"
            timeout "$BUILD_TIMEOUT" docker compose up -d --build --no-deps "$svc" 2>&1 | tee -a "$LOG_FILE"
        else
            log "❌ Ошибка сборки $svc"
            rm -f "$BUILD_LOG"
            return 1
        fi
    fi

    rm -f "$BUILD_LOG"
    return 0
}

DEPLOY_OK=true
FAILED_SVC=""

for svc in "${CHANGED_SERVICES[@]}"; do
    if ! build_service "$svc"; then
        DEPLOY_OK=false
        FAILED_SVC="$svc"
        break
    fi
done

# ─── Wait for healthy ─────────────────────
if [ "$DEPLOY_OK" = true ]; then
    log "⏳ Ожидание готовности сервисов..."
    MAX_WAIT=120
    ELAPSED=0
    INTERVAL=5

    while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
        STARTING=$(docker compose --profile all ps 2>/dev/null | grep -c "(health: starting)" || true)
        UNHEALTHY=$(docker compose --profile all ps 2>/dev/null | grep -c "unhealthy" || true)

        if [ "$STARTING" -eq 0 ] && [ "$UNHEALTHY" -eq 0 ]; then
            log "✅ Все сервисы готовы (${ELAPSED}s)"
            break
        fi

        if [ "$UNHEALTHY" -gt 0 ] && [ "$ELAPSED" -gt 60 ]; then
            log "❌ $UNHEALTHY сервисов unhealthy после ${ELAPSED}s"
            DEPLOY_OK=false
            break
        fi

        log "⏳ starting=$STARTING unhealthy=$UNHEALTHY (${ELAPSED}/${MAX_WAIT}s)"
        sleep "$INTERVAL"
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        UNHEALTHY=$(docker compose --profile all ps 2>/dev/null | grep -c "unhealthy" || true)
        if [ "$UNHEALTHY" -gt 0 ]; then
            log "❌ Таймаут: $UNHEALTHY unhealthy"
            DEPLOY_OK=false
        else
            log "⚠️ Таймаут, но все сервисы ОК"
        fi
    fi
fi

# ─── Rollback on failure ──────────────────
if [ "$DEPLOY_OK" = false ]; then
    log "🔄 ROLLBACK: откатываем ${CHANGED_SERVICES[*]}..."

    while IFS='|' read -r svc image; do
        if [ -n "$image" ]; then
            log "🔄 Откат $svc"
            docker compose up -d --no-build "$svc" 2>&1 | tee -a "$LOG_FILE" || true
        fi
    done < "$ROLLBACK_FILE"

    log "❌ ДЕПЛОЙ ПРОВАЛЕН (сбой: ${FAILED_SVC:-health check})"
    log "Последние логи проблемного сервиса:"
    [ -n "$FAILED_SVC" ] && docker compose logs --tail=20 "$FAILED_SVC" 2>&1 | tee -a "$LOG_FILE" || true

    exit 1
fi

# ─── Final status ─────────────────────────
log "✅ Деплой завершён: ${CHANGED_SERVICES[*]}"
docker compose --profile all ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"

# Health check
if [ -f "$PROJECT_ROOT/scripts/check-health.sh" ]; then
    bash "$PROJECT_ROOT/scripts/check-health.sh" | tee -a "$LOG_FILE" || true
fi

echo "────────────────────────────────" >> "$LOG_FILE"
