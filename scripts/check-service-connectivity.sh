#!/bin/bash
# Проверка межсервисного взаимодействия в Hackathon инфраструктуре

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔗 ПРОВЕРКА МЕЖСЕРВИСНОГО ВЗАИМОДЕЙСТВИЯ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

ERRORS=0

check_connectivity() {
    local from="$1"
    local to="$2"
    local url="$3"
    local desc="$4"
    
    if ! docker ps --filter "name=^/${from}$" --format '{{.Names}}' | grep -q "$from"; then
        echo -e "[${YELLOW}SKIP${NC}] $from → $to: контейнер $from не запущен"
        return
    fi
    
    if docker exec "$from" sh -c "wget -qO- --timeout=5 '$url' >/dev/null 2>&1 || python -c \"import urllib.request; urllib.request.urlopen('$url', timeout=5)\" >/dev/null 2>&1" 2>/dev/null; then
        echo -e "[${GREEN}OK${NC}] $from → $to ($desc)"
    else
        echo -e "[${RED}FAIL${NC}] $from → $to ($desc)"
        ((ERRORS++))
    fi
}

# === ML SERVICE ===
echo -e "${BLUE}📡 ML Service (hackathon-ml)${NC}"

# ML → Go (audit)
check_connectivity "hackathon-ml" "go-backend" \
    "http://go-backend:8083/health" \
    "audit service"

# ML → Ollama (host)
echo -n "  ML → Ollama (host.docker.internal:1234): "
if docker exec hackathon-ml python -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=5)" >/dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] LLM доступен"
else
    echo -e "[${RED}FAIL${NC}] LLM недоступен (туннель поднят? iptables?)"
    ((ERRORS++))
fi

echo ""

# === GO BACKEND ===
echo -e "${BLUE}📡 Go Backend (hackathon-go)${NC}"

# Go → ML
check_connectivity "hackathon-go" "ml-service" \
    "http://ml-service:8084/health" \
    "ML service"

# Go → Redis
echo -n "  Go → Redis: "
if docker exec hackathon-go sh -c "redis-cli -h redis -p 6379 ping" >/dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] Redis доступен"
else
    echo -e "[${RED}FAIL${NC}] Redis недоступен"
    ((ERRORS++))
fi

# Go → Postgres (проверка порта)
echo -n "  Go → Postgres: "
if docker exec hackathon-go sh -c "nc -z postgres 5432" >/dev/null 2>&1 || docker exec hackathon-go sh -c "timeout 2 bash -c '</dev/tcp/postgres/5432'" >/dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] Postgres порт доступен"
else
    echo -e "[${RED}FAIL${NC}] Postgres порт недоступен"
    ((ERRORS++))
fi

echo ""

# === CADDY ===
echo -e "${BLUE}📡 Caddy (hackathon-caddy)${NC}"

# Caddy → ML
check_connectivity "hackathon-caddy" "ml-service" \
    "http://ml-service:8084/health" \
    "ML service (reverse proxy)"

# Caddy → Go
check_connectivity "hackathon-caddy" "go-backend" \
    "http://go-backend:8083/health" \
    "Go backend"

# Caddy → Auth
check_connectivity "hackathon-caddy" "auth-service" \
    "http://auth-service:8080/actuator/health" \
    "Auth service"

# Caddy → Java
check_connectivity "hackathon-caddy" "java-backend" \
    "http://java-backend:8080/actuator/health" \
    "Java backend"

# Caddy → Frontend
check_connectivity "hackathon-caddy" "frontend" \
    "http://frontend:8082/health" \
    "Frontend"

echo ""

# === JAVA BACKEND ===
echo -e "${BLUE}📡 Java Backend (hackathon-java)${NC}"

# Java → Postgres (проверка порта)
echo -n "  Java → Postgres: "
if docker exec hackathon-java sh -c "nc -z postgres 5432" >/dev/null 2>&1 || docker exec hackathon-java sh -c "timeout 2 bash -c '</dev/tcp/postgres/5432'" >/dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] Postgres порт доступен"
else
    echo -e "[${RED}FAIL${NC}] Postgres порт недоступен"
    ((ERRORS++))
fi

# Java → RabbitMQ (проверка порта)
echo -n "  Java → RabbitMQ: "
if docker exec hackathon-java sh -c "nc -z rabbitmq 5672" >/dev/null 2>&1 || docker exec hackathon-java sh -c "timeout 2 bash -c '</dev/tcp/rabbitmq/5672'" >/dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] RabbitMQ порт доступен"
else
    echo -e "[${RED}FAIL${NC}] RabbitMQ порт недоступен"
    ((ERRORS++))
fi

echo ""

# === AUTH SERVICE ===
echo -e "${BLUE}📡 Auth Service (hackathon-auth)${NC}"

# Auth → Postgres (проверка порта)
echo -n "  Auth → Postgres: "
if docker exec hackathon-auth sh -c "nc -z postgres 5432" >/dev/null 2>&1 || docker exec hackathon-auth sh -c "timeout 2 bash -c '</dev/tcp/postgres/5432'" >/dev/null 2>&1; then
    echo -e "[${GREEN}OK${NC}] Postgres порт доступен"
else
    echo -e "[${RED}FAIL${NC}] Postgres порт недоступен"
    ((ERRORS++))
fi

echo ""

# === SUMMARY ===
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ${NC}"
    exit 0
else
    echo -e "${RED}❌ НАЙДЕНО ОШИБОК: $ERRORS${NC}"
    exit 1
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
