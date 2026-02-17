#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
#  deploy.sh — Лёгкий деплой: поднимает сервисы БЕЗ пересборки.
#              Для пересборки образов используйте вручную:
#                docker compose up -d --build <service>
#
#  Переменные окружения:
#    DEPLOY_ROOT — корень проекта (default: /opt/hackathon)
# ──────────────────────────────────────────────────────────────

PROJECT_ROOT="${DEPLOY_ROOT:-/opt/hackathon}"
LOG_FILE="$PROJECT_ROOT/logs/deploy.log"
DEPLOY_START=$(date +%s)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

# ═══════════════════════════════════════════════
#  НАЧАЛО
# ═══════════════════════════════════════════════
cd "$PROJECT_ROOT" || { echo "Ошибка: директория $PROJECT_ROOT не найдена"; exit 1; }

mkdir -p "$PROJECT_ROOT/logs/caddy" \
         "$PROJECT_ROOT/data/postgres" \
         "$PROJECT_ROOT/backups/postgres"

[ ! -f "$PROJECT_ROOT/.env" ] && { log "❌ Файл .env не найден!"; exit 1; }
command -v docker &>/dev/null || { log "❌ Docker не установлен"; exit 1; }
docker compose version &>/dev/null || { log "❌ Docker Compose не доступен"; exit 1; }

log "🚀 Деплой запущен (коммит: $(git rev-parse --short HEAD 2>/dev/null || echo 'N/A'))"

# ── Поднимаем сервисы (без пересборки) ──
docker compose --profile all up -d --remove-orphans 2>&1 | tee -a "$LOG_FILE"

# ── Ожидание healthy-статуса (макс 90 сек) ──
log "⏳ Ожидание готовности сервисов..."
MAX_WAIT=90
ELAPSED=0

while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
    STARTING=$(docker compose --profile all ps 2>/dev/null | grep -c "(health: starting)" || true)
    if [ "$STARTING" -eq 0 ]; then
        log "✅ Все сервисы готовы (${ELAPSED}s)"
        break
    fi
    log "⏳ Ещё запускаются: $STARTING сервисов... (${ELAPSED}/${MAX_WAIT}s)"
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
    log "⚠️ Таймаут ожидания (${MAX_WAIT}s)"
fi

# ── Статус ──
docker compose --profile all ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"

# ── Время деплоя ──
DEPLOY_END=$(date +%s)
DURATION=$((DEPLOY_END - DEPLOY_START))
log "⏱️ Деплой завершён за ${DURATION}s"

echo "────────────────────────────────────────" >> "$LOG_FILE"
