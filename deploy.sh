#!/bin/bash
set -e

LOG_FILE="/opt/hackathon/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

cd /opt/hackathon
log "🚀 Деплой запущен"

# Проверка незакоммиченных изменений
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    log "⚠️  НЕЗАКОММИЧЕННЫЕ ИЗМЕНЕНИЯ! Деплой отменён."
    exit 1
fi

# Обновление кода
log "🔄 Обновление кода..."
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"

# Анализ изменений (последний коммит)
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
if [[ -z "$CHANGED" ]]; then
    log "ℹ️  Нет изменений для перезапуска"
    exit 0
fi

log "📝 Изменены файлы: $(echo "$CHANGED" | tr '\n' ' ')"

# Флаги
RESTART_ALL=false
RESTART_CADDY=false
RESTART_SERVICES=false

# Анализ изменений
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    
    case "$file" in
        docker-compose.yml)
            RESTART_ALL=true
            ;;
        Caddyfile)
            RESTART_CADDY=true
            ;;
        services/*)
            RESTART_SERVICES=true
            ;;
    esac
done < <(echo "$CHANGED")

# Команда с профилями
DC="docker compose --profile infra --profile proxy --profile apps"

# Случай 1: Изменения в сервисах → пересборка приложений
if [[ "$RESTART_SERVICES" == true ]]; then
    log "🔄 Пересборка микросервисов..."
    $DC up -d --build frontend java-backend go-backend ml-service 2>&1 | tee -a "$LOG_FILE"
fi

# Случай 2: Изменения в Caddyfile → graceful reload
if [[ "$RESTART_CADDY" == true ]]; then
    log "🔄 Перезагрузка Caddy..."
    if ! docker compose --profile proxy exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tee -a "$LOG_FILE"; then
        log "⚠️  Reload не удался — перезапуск контейнера"
        docker compose --profile proxy restart caddy 2>&1 | tee -a "$LOG_FILE"
    fi
fi

log "✅ Деплой завершён"
$DC ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
