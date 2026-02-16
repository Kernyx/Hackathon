#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Корень проекта (как в deploy.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    echo "⚠️ Файл .env не найден — используются значения по умолчанию для проверки БД"
    export DB_USER="${DB_USER:-hackuser}"
    export DB_NAME="${DB_NAME:-hackdb}"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏥 Проверка здоровья инфраструктуры хакатона"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Функция проверки
check() {
    if eval "$2" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1"
        return 1
    fi
}

# Счётчик ошибок
ERRORS=0

# === ПРОВЕРКА DOCKER ===
echo "🐳 Docker:"
check "Docker запущен" "docker info" || ((ERRORS++))
echo ""

# === ПРОВЕРКА КОНТЕЙНЕРОВ ===
echo "📦 Контейнеры:"
for container in hackathon-db hackathon-queue hackathon-pgadmin hackathon-caddy; do
    check "$container запущен" "docker ps --filter name=$container --format '{{.Names}}' | grep -q $container" || ((ERRORS++))
done
echo ""

# === ПРОВЕРКА ЗДОРОВЬЯ СЕРВИСОВ ===
echo "💚 Здоровье сервисов:"
check "PostgreSQL здоров" "docker exec hackathon-db pg_isready -U $DB_USER -d $DB_NAME" || ((ERRORS++))
check "RabbitMQ здоров" "docker exec hackathon-queue rabbitmq-diagnostics check_running" || ((ERRORS++))
echo ""

# === ПРОВЕРКА ПОРТОВ ===
echo "🔌 Порты (VPN):"
check "PostgreSQL (10.66.66.1:5432)" "timeout 2 bash -c '</dev/tcp/10.66.66.1/5432' 2>/dev/null" || ((ERRORS++))
check "RabbitMQ AMQP (10.66.66.1:5672)" "timeout 2 bash -c '</dev/tcp/10.66.66.1/5672' 2>/dev/null" || ((ERRORS++))
check "RabbitMQ Management (10.66.66.1:15672)" "timeout 2 bash -c '</dev/tcp/10.66.66.1/15672' 2>/dev/null" || ((ERRORS++))
check "pgAdmin (10.66.66.1:5050)" "timeout 2 bash -c '</dev/tcp/10.66.66.1/5050' 2>/dev/null" || ((ERRORS++))
echo ""

# === ПРОВЕРКА ПУБЛИЧНЫХ ДОМЕНОВ ===
echo "🌐 Публичные домены:"
check "besthackaton.duckdns.org (HTTPS)" "curl -s -o /dev/null -w '%{http_code}' https://besthackaton.duckdns.org | grep -q '^[23]'" || echo -e "${YELLOW}⚠️${NC} Фронтенд не запущен (это нормально если профиль не активен)"
echo ""

# === ПРОВЕРКА БЭКАПОВ ===
echo "💾 Бэкапы:"
LATEST_BACKUP=$(ls -t "$PROJECT_ROOT/backups/postgres"/db_*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_AGE_HOURS=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))
    if [ "$BACKUP_AGE_HOURS" -lt 24 ]; then
        echo -e "${GREEN}✅${NC} Последний бэкап: $BACKUP_AGE_HOURS часов назад"
    else
        echo -e "${YELLOW}⚠️${NC} Последний бэкап: $BACKUP_AGE_HOURS часов назад (старше суток!)"
        ((ERRORS++))
    fi
    
    # Проверка целостности
    if gunzip -t "$LATEST_BACKUP" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} Целостность бэкапа в порядке"
    else
        echo -e "${RED}❌${NC} Бэкап повреждён!"
        ((ERRORS++))
    fi
else
    echo -e "${RED}❌${NC} Бэкапов не найдено!"
    ((ERRORS++))
fi
echo ""

# === ПРОВЕРКА ДИСКОВОГО ПРОСТРАНСТВА ===
echo "💿 Дисковое пространство:"
DISK_USAGE=$(df -h "$PROJECT_ROOT" | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✅${NC} Использовано: $DISK_USAGE%"
else
    echo -e "${YELLOW}⚠️${NC} Использовано: $DISK_USAGE% (больше 80%!)"
fi
echo ""

# === ПРОВЕРКА ЛОГОВ ===
echo "📋 Последние ошибки в логах:"
ERROR_COUNT=$(cd "$PROJECT_ROOT" && docker compose logs --tail=100 2>/dev/null | grep -i "error\|failed\|fatal" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅${NC} Ошибок в последних 100 строках логов не найдено"
else
    echo -e "${YELLOW}⚠️${NC} Найдено $ERROR_COUNT ошибок в последних 100 строках логов"
    echo "    Подробнее: docker compose logs --tail=100 | grep -i error"
fi
echo ""

# === ИТОГИ ===
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ ВСЁ РАБОТАЕТ ОТЛИЧНО!${NC}"
else
    echo -e "${RED}⚠️ НАЙДЕНО ПРОБЛЕМ: $ERRORS${NC}"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Возвращаем код ошибки если есть проблемы
exit $ERRORS
