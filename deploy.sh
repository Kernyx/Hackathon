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
    log "💡 Закоммитьте изменения или используйте 'git stash'"
    exit 1
fi

# Обновление кода
log "🔄 Обновление кода..."
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"

# Анализ изменений (последний коммит)
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
log "📝 Изменено: ${CHANGED:-<ничего>}"

if [[ -z "$CHANGED" ]]; then
    log "ℹ️  Нет изменений для перезапуска"
    exit 0
fi

# Флаги
RESTART_INFRA=false
RESTART_CADDY=false
RESTART_SERVICES=()

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    case "$file" in
        docker-compose.yml) RESTART_INFRA=true ;;
        Caddyfile) RESTART_CADDY=true ;;
        services/*)
            svc=$(echo "$file" | cut -d'/' -f2)
            [[ ! " ${RESTART_SERVICES[*]} " =~ " ${svc} " ]] && RESTART_SERVICES+=("$svc")
            ;;
    esac
done < <(echo "$CHANGED")

# Инфраструктура
if [[ "$RESTART_INFRA" == true ]]; then
    log "🔄 Перезапуск инфраструктуры..."
    docker compose down 2>&1 | tee -a "$LOG_FILE" || true
    docker compose up -d --build 2>&1 | tee -a "$LOG_FILE"
    log "✅ Инфраструктура перезапущена"
    exit 0
fi

# Caddy
if [[ "$RESTART_CADDY" == true ]]; then
    log "🔄 Перезагрузка Caddy..."
    if ! docker exec hackathon-caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tee -a "$LOG_FILE"; then
        log "⚠️  Reload не удался — пересоздаём контейнер"
        docker compose up -d --force-recreate --no-deps caddy 2>&1 | tee -a "$LOG_FILE"
    fi
fi

# Микросервисы
for svc in "${RESTART_SERVICES[@]}"; do
    dir="services/$svc"
    if [[ -f "$dir/docker-compose.yml" ]]; then
        log "🔄 Перезапуск $svc..."
        if cd "$dir" && docker compose down 2>&1 | tee -a "$LOG_FILE" && \
           docker compose up -d --build 2>&1 | tee -a "$LOG_FILE"; then
            log "✅ $svc успешно перезапущен"
        else
            log "❌ ОШИБКА при перезапуске $svc"
            exit 1
        fi
        cd /opt/hackathon
    fi
done

log "✅ Деплой завершён"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tee -a "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
