#!/bin/bash
set -e

LOG_FILE="/opt/hackathon/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

cd /opt/hackathon
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
    log "ℹ️ Нет изменений"
    exit 0
fi

log "📝 Изменены файлы: $(echo "$CHANGED" | tr '\n' ' ')"

# === СЛУЧАЙ 2: Caddyfile → reload Caddy ===
if echo "$CHANGED" | grep -q "^Caddyfile$"; then
    log "🔄 Перезагрузка Caddy..."
    if ! docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tee -a "$LOG_FILE"; then
        log "⚠️ Reload не удался — перезапуск"
        docker compose restart caddy 2>&1 | tee -a "$LOG_FILE"
    fi
fi

# === СЛУЧАЙ 3: Микросервисы → пересборка по отдельности ===
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
        log "🔄 Пересборка ${profile}..."
        docker compose --profile "$profile" up -d --build 2>&1 | tee -a "$LOG_FILE"
    fi
done

log "✅ Деплой завершён"
docker compose ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
