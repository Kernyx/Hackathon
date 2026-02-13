#!/bin/bash
set -e

LOG_FILE="/opt/hackathon/logs/deploy.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TIMESTAMP] 🚀 Деплой запущен" | tee -a "$LOG_FILE"

cd /opt/hackathon
git pull origin main 2>&1 | tee -a "$LOG_FILE"

docker compose down 2>&1 | tee -a "$LOG_FILE"
docker compose up -d --build 2>&1 | tee -a "$LOG_FILE"

docker compose ps 2>&1 | tee -a "$LOG_FILE"
echo "[$TIMESTAMP] ✅ Деплой завершён" | tee -a "$LOG_FILE"
echo "----------------------------------------" | tee -a "$LOG_FILE"
