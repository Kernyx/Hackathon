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
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
else
    # Значения по умолчанию для проверки, если .env нет
    export DB_USER="${DB_USER:-hackuser}"
    export DB_NAME="${DB_NAME:-hackdb}"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  HACKATHON INFRASTRUCTURE HEALTH CHECK${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Date: $(date)"
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
echo -e "${BLUE} Docker Engine${NC}"
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
echo -e "${BLUE} Containers Status${NC}"
SERVICES=("hackathon-caddy" "hackathon-db" "hackathon-queue" "hackathon-auth" "hackathon-java" "hackathon-go" "hackathon-frontend" "hackathon-ml" "hackathon-redis")

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
        STATUS_TEXT=$(echo "$INFO" | cut -d'|' -f2)
        STATE=$(echo "$INFO" | cut -d'|' -f3)

        # Проверка состояния (running vs exited)
        if [ "$STATE" == "running" ]; then
             # Проверка Healthcheck (если есть)
             if echo "$STATUS_TEXT" | grep -qi "healthy)" && ! echo "$STATUS_TEXT" | grep -qi "unhealthy"; then
                 print_status "OK" "$service: Running & Healthy"
             elif echo "$STATUS_TEXT" | grep -qi "unhealthy"; then
                 print_status "FAIL" "$service: Running but UNHEALTHY"
             elif echo "$STATUS_TEXT" | grep -qi "starting"; then
                 print_status "WARN" "$service: Still starting up..."
             else
                 # Может быть контейнер без healthcheck, или healthcheck ещё не запустился
                 # Проверяем есть ли у него healthcheck вообще
                 HAS_HC=$(docker inspect "$service" --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
                 if [ "$HAS_HC" == "starting" ]; then
                     print_status "WARN" "$service: Healthcheck starting..."
                 elif [ "$HAS_HC" == "none" ] || [ -z "$HAS_HC" ]; then
                     print_status "OK" "$service: Running (no healthcheck)"
                 else
                     print_status "OK" "$service: Running ($HAS_HC)"
                 fi
             fi
        else
             EXIT_CODE=$(docker inspect "$service" --format='{{.State.ExitCode}}' 2>/dev/null)
             print_status "FAIL" "$service: Stopped (Exit Code: $EXIT_CODE)"
        fi
    fi
done
echo ""

# === 3. SERVICE ENDPOINTS (inside containers) ===
echo -e "${BLUE} Service Endpoints (docker exec)${NC}"

check_service() {
    local name="$1"
    local container="$2"
    local cmd="$3"

    if ! docker ps --filter "name=^/${container}$" --format '{{.Names}}' | grep -q "$container"; then
        print_status "WARN" "$name: container not running, skipped"
        return
    fi

    if docker exec "$container" sh -c "$cmd" > /dev/null 2>&1; then
        print_status "OK" "$name: responding"
    else
        print_status "FAIL" "$name: not responding"
    fi
}

check_service "Frontend /health" "hackathon-frontend" \
    "curl -sf http://localhost:8082/health"

check_service "Auth /actuator/health" "hackathon-auth" \
    "wget -qO- http://localhost:8080/actuator/health"

check_service "Java /actuator/health" "hackathon-java" \
    "wget -qO- http://localhost:8080/actuator/health"

check_service "Go /health" "hackathon-go" \
    "wget -qO- http://localhost:8083/health"

check_service "ML /health" "hackathon-ml" \
    "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8084/health')\""

check_service "Redis PING" "hackathon-redis" \
    "redis-cli ping"
echo ""

# === 3.1 CONTAINER CONNECTIVITY (межсервисная связность) ===
echo -e "${BLUE}🔗 Container Connectivity (Go↔ML, Caddy↔ML)${NC}"
if docker ps --filter "name=^/hackathon-go$" --format '{{.Names}}' | grep -q "hackathon-go"; then
    if docker exec hackathon-go wget -qO- --timeout=5 http://ml-service:8084/health > /dev/null 2>&1; then
        print_status "OK" "Go → ML (ml-service:8084/health)"
    else
        print_status "FAIL" "Go → ML: cannot reach ml-service:8084"
    fi
else
    print_status "WARN" "Go → ML: hackathon-go not running, skipped"
fi
if docker ps --filter "name=^/hackathon-ml$" --format '{{.Names}}' | grep -q "hackathon-ml"; then
    if docker exec hackathon-ml python -c "import urllib.request; urllib.request.urlopen('http://go-backend:8083/health', timeout=5)" > /dev/null 2>&1; then
        print_status "OK" "ML → Go (go-backend:8083/health)"
    else
        print_status "FAIL" "ML → Go: cannot reach go-backend:8083"
    fi
    HAS_HOST_GW=$(docker inspect hackathon-ml --format '{{range .HostConfig.ExtraHosts}}{{.}}{{end}}' 2>/dev/null | grep -o 'host.docker.internal' || true)
    if [ -z "$HAS_HOST_GW" ]; then
        print_status "WARN" "ML → Ollama: контейнер без extra_hosts (host.docker.internal). Пересоздайте: docker compose --profile all up -d --force-recreate ml-service"
    elif docker exec hackathon-ml python -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=5)" > /dev/null 2>&1; then
        print_status "OK" "ML → Ollama (host.docker.internal:1234)"
    else
        print_status "WARN" "ML → Ollama: host.docker.internal:1234 unreachable (туннель поднят? ssh -R 0.0.0.0:1234:...)"
    fi
else
    print_status "WARN" "ML connectivity: hackathon-ml not running, skipped"
fi
echo ""

# === 4. PUBLIC DOMAIN & SSL ===
echo -e "${BLUE} Public Domain & SSL${NC}"
DOMAIN="besthackaton.duckdns.org"
API_DOMAIN="api.besthackaton.duckdns.org"

check_url() {
    local name="$1"
    local url="$2"
    local expected_code="$3"

    HTTP_CODE=$(curl -s -L -k -o /dev/null -w "%{http_code}" --max-time 5 "$url")
    if [[ "$HTTP_CODE" == "$expected_code" || "$HTTP_CODE" == "200" || "$HTTP_CODE" == "401" ]]; then
        print_status "OK" "$name -> $HTTP_CODE"
    elif [ "$HTTP_CODE" == "000" ]; then
        print_status "FAIL" "$name -> Connection Refused / Timeout"
    else
        print_status "FAIL" "$name -> $HTTP_CODE (Expected: $expected_code)"
    fi
}

# Проверка срока действия сертификата
EXPIRY_DATE=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)

if [ -n "$EXPIRY_DATE" ]; then
    EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - $(date +%s)) / 86400 ))
    if [ "$DAYS_LEFT" -gt 14 ]; then
        print_status "OK" "SSL $DOMAIN expires in ${DAYS_LEFT} days ($EXPIRY_DATE)"
    else
        print_status "WARN" "SSL $DOMAIN expires SOON: ${DAYS_LEFT} days ($EXPIRY_DATE)"
    fi
else
    print_status "WARN" "SSL Certificate check failed (connection refused?)"
fi

check_url "Public Frontend" "https://$DOMAIN" "200"
check_url "Public API /actuator/health" "https://$API_DOMAIN/actuator/health" "200"
check_url "Public API /audit/feed" "https://$API_DOMAIN/api/v1/audit/feed" "200"
ML_URL="https://$API_DOMAIN/api/v1/ml/users/test123/session"
ML_CODE=$(curl -s -L -k -o /dev/null -w "%{http_code}" --max-time 5 "$ML_URL")
if [ "$ML_CODE" = "200" ]; then
    print_status "OK" "Public API /api/v1/ml (Caddy→ML) -> 200"
elif [ "$ML_CODE" = "404" ]; then
    if docker exec hackathon-go wget -qO- --timeout=5 http://ml-service:8084/health >/dev/null 2>&1; then
        print_status "OK" "Public API /api/v1/ml: ML доступен из сети (с этого хоста публичный запрос 404 — hairpinning)"
    else
        print_status "WARN" "Public API /api/v1/ml -> 404 (при запуске с VPS возможно hairpinning; снаружи проверьте вручную)"
    fi
elif [ "$ML_CODE" = "000" ]; then
    print_status "FAIL" "Public API /api/v1/ml -> Connection Refused / Timeout"
else
    print_status "FAIL" "Public API /api/v1/ml -> $ML_CODE (Expected: 200)"
fi
echo ""

# === 5. RESOURCES ===
echo -e "${BLUE} Resource Usage${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo ""

# === 6. BACKUPS ===
echo -e "${BLUE} Backups${NC}"
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
echo -e "${BLUE} Log Analysis (Last 50 lines)${NC}"
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
        echo -e "${GREEN} SYSTEM HEALTHY - READY TO DEMO${NC}"
    else
        echo -e "${YELLOW} SYSTEM RUNNING WITH $WARNINGS WARNINGS${NC}"
    fi
else
    echo -e "${RED} SYSTEM HAS $ERRORS CRITICAL ISSUES${NC}"
    exit 1
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
