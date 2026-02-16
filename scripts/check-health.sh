#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Корень проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"

# Загрузка переменных окружения
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
else
    # Значения по умолчанию для проверки, если .env нет
    export DB_USER="${DB_USER:-hackuser}"
    export DB_NAME="${DB_NAME:-hackdb}"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🏥  HACKATHON INFRASTRUCTURE HEALTH CHECK${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "📅 Date: $(date)"
echo ""

# Счётчик ошибок
ERRORS=0
WARNINGS=0

# Функция для вывода статуса
print_status() {
    local status="$1"
    local message="$2"
    if [ "$status" == "OK" ]; then
        echo -e "[${GREEN}OK${NC}] $message"
    elif [ "$status" == "WARN" ]; then
        echo -e "[${YELLOW}WARN${NC}] $message"
        ((WARNINGS++))
    else
        echo -e "[${RED}FAIL${NC}] $message"
        ((ERRORS++))
    fi
}

# === 1. DOCKER & COMPOSE ===
echo -e "${BLUE}🐳 Docker Engine${NC}"
if docker info > /dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] Docker daemon is running"
else
    echo -e "[${RED}FAIL${NC}] Docker daemon is NOT running or accessible"
    exit 1
fi

if docker compose version > /dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] Docker Compose is installed"
else
    echo -e "[${RED}FAIL${NC}] Docker Compose not found"
    exit 1
fi
echo ""

# === 2. CONTAINER STATUS & HEALTH ===
echo -e "${BLUE}📦 Containers Status${NC}"
SERVICES=("hackathon-caddy" "hackathon-db" "hackathon-queue" "hackathon-java" "hackathon-go" "hackathon-frontend" "hackathon-ml" "hackathon-redis")

# Формат вывода docker ps: Name, Status, Health, State
FORMAT="{{.Names}}|{{.Status}}|{{.State}}"

for service in "${SERVICES[@]}"; do
    # Получаем инфо о контейнере
    INFO=$(docker ps -a --filter "name=^/${service}$" --format "$FORMAT")
    
    if [ -z "$INFO" ]; then
        # Если сервис не найден (может быть отключен профилем)
        # Проверяем, должен ли он быть (из docker-compose ps)
        IS_EXPECTED=$(docker compose ps -q "$service" 2>/dev/null)
        if [ -n "$IS_EXPECTED" ]; then
             print_status "FAIL" "$service: Not found (but expected)"
        else
             # Сервис не в текущем профиле - пропускаем
             continue
        fi
    else
        NAME=$(echo "$INFO" | cut -d'|' -f1)
        STATUS_TEXT=$(echo "$INFO" | cut -d'|' -f2)
        STATE=$(echo "$INFO" | cut -d'|' -f3)

        # Проверка состояния (running vs exited)
        if [ "$STATE" == "running" ]; then
             # Проверка Healthcheck (если есть)
             if echo "$STATUS_TEXT" | grep -q "(healthy)"; then
                 print_status "OK" "$service: Running & Healthy"
             elif echo "$STATUS_TEXT" | grep -q "(unhealthy)"; then
                 print_status "FAIL" "$service: Running but UNHEALTHY"
             elif echo "$STATUS_TEXT" | grep -q "(starting)"; then
                 print_status "WARN" "$service: Starting..."
             else
                 print_status "OK" "$service: Running (no healthcheck)"
             fi
        else
             EXIT_CODE=$(docker inspect "$service" --format='{{.State.ExitCode}}' 2>/dev/null)
             print_status "FAIL" "$service: Stopped (Exit Code: $EXIT_CODE)"
        fi
    fi
done
echo ""

# === 3. ENDPOINTS REACHABILITY (INTERNAL) ===
echo -e "${BLUE}🔌 Internal Connectivity (via curl)${NC}"

check_url() {
    local name="$1"
    local url="$2"
    local expected_code="$3"
    
    # -L follow redirects, -k ignore SSL verify for localhost/check
    HTTP_CODE=$(curl -s -L -k -o /dev/null -w "%{http_code}" --max-time 5 "$url")
    if [[ "$HTTP_CODE" == "$expected_code" || "$HTTP_CODE" == "200" || "$HTTP_CODE" == "401" ]]; then
        print_status "OK" "$name ($url) -> $HTTP_CODE"
    else
        if [ "$HTTP_CODE" == "000" ]; then
             print_status "FAIL" "$name ($url) -> Connection Refused / Timeout"
        else
             print_status "FAIL" "$name ($url) -> $HTTP_CODE (Expected: $expected_code)"
        fi
    fi
}

check_url "Frontend" "http://localhost:8082" "200"
check_url "Java Actuator" "http://localhost:8080/actuator/health" "200"
check_url "Go Audit Feed" "http://localhost:8083/api/v1/audit/feed" "200"
echo ""

# === 4. PUBLIC DOMAIN & SSL ===
echo -e "${BLUE}🌐 Public Domain & SSL${NC}"
DOMAIN="besthackaton.duckdns.org"
API_DOMAIN="api.besthackaton.duckdns.org"

# Проверка срока действия сертификата
EXPIRY_DATE=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

if [ -n "$EXPIRY_DATE" ]; then
    print_status "OK" "SSL Certificate for $DOMAIN is valid (Expires: $EXPIRY_DATE)"
    check_url "Public Frontend" "https://$DOMAIN" "200"
    check_url "Public API" "https://$API_DOMAIN/api/v1/audit/feed" "200"
else
    print_status "WARN" "SSL Certificate check failed (connection refused or no cert?)"
    # Try HTTP fallback check
    check_url "Public Frontend (HTTP)" "http://$DOMAIN" "301" # Caddy redirects http->https
fi
echo ""

# === 5. RESOURCES ===
echo -e "${BLUE}📊 Resource Usage (Top 5)${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -n 6
echo ""

# === 6. BACKUPS ===
echo -e "${BLUE}💾 Backups${NC}"
BACKUP_DIR="$PROJECT_ROOT/backups/postgres"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | head -1)

if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_TIME=$(stat -c %Y "$LATEST_BACKUP")
    CURRENT_TIME=$(date +%s)
    AGE_HOURS=$(( (CURRENT_TIME - BACKUP_TIME) / 3600 ))
    
    if [ "$AGE_HOURS" -lt 25 ]; then
        print_status "OK" "Latest backup: ${AGE_HOURS}h ago ($(basename "$LATEST_BACKUP"))"
    else
        print_status "WARN" "Latest backup is OLD: ${AGE_HOURS}h ago"
    fi
    
    # Check integrity
    if gunzip -t "$LATEST_BACKUP" 2>/dev/null; then
        print_status "OK" "Backup integrity verified"
    else
        print_status "FAIL" "Backup file is CORRUPTED!"
    fi
else
    print_status "FAIL" "No backups found in $BACKUP_DIR"
fi
echo ""

# === 7. RECENT ERRORS ===
echo -e "${BLUE}📋 Log Analysis (Last 50 lines)${NC}"
# Ищем "Error", "Exception", "Panic" но исключаем безобидные
LOG_ERRORS=$(cd "$PROJECT_ROOT" && docker compose logs --tail=50 2>&1 | grep -iE "error|exception|panic|fatal" | grep -v "npm notice" | grep -v "DeprecationWarning" | head -n 5)

if [ -z "$LOG_ERRORS" ]; then
    print_status "OK" "No obvious errors in recent logs"
else
    print_status "WARN" "Found suspicious log entries:"
    echo "$LOG_ERRORS" | sed 's/^/  /'
fi
echo ""

# === SUMMARY ===
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$ERRORS" -eq 0 ]; then
    if [ "$WARNINGS" -eq 0 ]; then
        echo -e "${GREEN}✅ SYSTEM HEALTHY - READY TO DEMO${NC}"
    else
        echo -e "${YELLOW}⚠️  SYSTEM RUNNING WITH $WARNINGS WARNINGS${NC}"
    fi
else
    echo -e "${RED}❌ SYSTEM HAS $ERRORS CRITICAL ISSUES${NC}"
    exit 1
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
