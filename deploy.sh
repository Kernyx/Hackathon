#!/bin/bash
set -e

LOG_FILE="/opt/hackathon/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"; }

cd /opt/hackathon
log "🚀 Деплой запущен"

# Проверка незакоммиченных изменений
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
  log "⚠️  Обнаружены незакоммиченные изменения — деплой отменён"
  exit 1
fi

# Безопасное обновление
git pull --ff-only origin main 2>&1 | tee -a "$LOG_FILE"

# Анализ последнего коммита
CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
log "📝 Изменено: ${CHANGED:-<ничего>}"

# Перезапуск сервисов (только если есть изменения)
if [[ -n "$CHANGED" ]]; then
  # Caddy
  if echo "$CHANGED" | grep -q "^Caddyfile$"; then
    log "🔄 Перезагрузка Caddy..."
    docker exec hackathon-caddy caddy reload --config /etc/caddy/Caddyfile 2>&1 | tee -a "$LOG_FILE" || \
    docker compose up -d --force-recreate --no-deps caddy 2>&1 | tee -a "$LOG_FILE"
  fi

  # Инфраструктура
  if echo "$CHANGED" | grep -q "^docker-compose\.yml$"; then
    log "🔄 Перезапуск инфраструктуры..."
    docker compose up -d --build 2>&1 | tee -a "$LOG_FILE"
  fi

  # Микросервисы
  SERVICES=("java-backend" "go-backend" "ml-service" "frontend")
  for svc in "${SERVICES[@]}"; do
    if echo "$CHANGED" | grep -q "^services/$svc/" && [ -f "services/$svc/docker-compose.yml" ]; then
      log "🔄 Перезапуск $svc..."
      (cd "services/$svc" && docker compose up -d --build 2>&1) | tee -a "$LOG_FILE" || true
    fi
  done
fi

log "✅ Деплой завершён"
docker ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
