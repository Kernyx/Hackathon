#!/bin/bash
set -e

LOG_FILE="/opt/hackathon/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

cd /opt/hackathon
log "🚀 Деплой запущен"

# Проверяем, нет ли незакоммиченных изменений
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    log "⚠️  Найдены незакоммиченные изменения в рабочей директории"
    log "💡 Закоммитьте изменения или используйте 'git stash' перед деплоем"
    exit 1
fi

# Безопасное обновление кода
log "🔄 Обновление кода из GitHub..."
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"

# Анализ изменений (последний коммит)
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
log "📝 Изменено: ${CHANGED:-<ничего>}"

# Если изменений нет — выходим
if [[ -z "$CHANGED" ]]; then
    log "ℹ️  Нет изменений, требующих перезапуска"
    exit 0
fi

# Флаги для перезапуска
RESTART_INFRA=false
RESTART_CADDY=false
RESTART_SERVICES=()

# Анализируем изменения
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    
    case "$file" in
        docker-compose.yml)
            RESTART_INFRA=true
            ;;
        Caddyfile)
            RESTART_CADDY=true
            ;;
        services/*)
            # Извлекаем имя сервиса
            SERVICE_NAME=$(echo "$file" | cut -d'/' -f2)
            if [[ ! " ${RESTART_SERVICES[@]} " =~ " ${SERVICE_NAME} " ]]; then
                RESTART_SERVICES+=("$SERVICE_NAME")
            fi
            ;;
    esac
done < <(echo "$CHANGED")

# Перезапуск инфраструктуры
if [[ "$RESTART_INFRA" == true ]]; then
    log "🔄 Перезапуск инфраструктуры..."
    docker compose down 2>&1 | tee -a "$LOG_FILE"
    docker compose up -d --build 2>&1 | tee -a "$LOG_FILE"
    log "✅ Инфраструктура перезапущена"
    exit 0  # Если перезапустили инфраструктуру — всё перезапустилось
fi

# Перезапуск Caddy
if [[ "$RESTART_CADDY" == true ]]; then
    log "🔄 Обновление конфига Caddy (zero-downtime)..."
    if ! docker exec hackathon-caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tee -a "$LOG_FILE"; then
        log "⚠️  Reload не удался — пересоздаём контейнер..."
        docker compose up -d --force-recreate --no-deps caddy 2>&1 | tee -a "$LOG_FILE"
    fi
fi

# Перезапуск микросервисов
for svc in "${RESTART_SERVICES[@]}"; do
    SVC_DIR="services/$svc"
    if [[ -f "$SVC_DIR/docker-compose.yml" ]]; then
        log "🔄 Перезапуск сервиса: $svc..."
        if (cd "$SVC_DIR" && docker compose down && docker compose up -d --build 2>&1) | tee -a "$LOG_FILE"; then
            log "✅ $svc успешно перезапущен"
        else
            log "❌ Ошибка при перезапуске $svc (продолжаем деплой других сервисов)"
        fi
    fi
done

log "✅ Деплой завершён"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | tee -a "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
