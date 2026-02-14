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

# === СЛУЧАЙ 1: Изменения в инфраструктуре (.env или docker-compose.yml) ===
if echo "$CHANGED" | grep -qE "^(docker-compose\.yml|\.env)$"; then
    log "⚠️ Изменена инфраструктура — требуется полный перезапуск!"
    log "🛑 Останавливаем все сервисы..."
    docker compose --profile all down 2>&1 | tee -a "$LOG_FILE"
    
    log "🔄 Запускаем с новой конфигурацией..."
    docker compose --profile all up -d --build 2>&1 | tee -a "$LOG_FILE"
    
    log "✅ Полный перезапуск завершён"
    docker compose ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
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
echo "----------------------------------------" >> "$LOG_FILE"
