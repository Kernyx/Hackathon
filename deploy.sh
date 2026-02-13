#!/bin/bash
set -e

echo "🔄 Обновление кода из GitHub..."
cd /opt/hackathon
git pull origin main

echo "📦 Перезапуск инфраструктуры..."
docker compose down
docker compose up -d --build

echo "✅ Статус сервисов:"
docker compose ps
