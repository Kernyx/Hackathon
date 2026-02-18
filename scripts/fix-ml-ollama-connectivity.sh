#!/bin/bash
# Диагностика и подсказка: почему контейнер ML не достучивается до host.docker.internal:1234 (Ollama/LM Studio).
# Запускать на VPS от пользователя, имеющего доступ к docker и (для проверки) curl.

set -e
echo "=== Проверка доступа к порту 1234 (LM Studio / Ollama) ==="
echo ""

# 1. С хоста — localhost
echo "1. Хост, localhost:1234"
if curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null 2>&1; then
    echo "   OK — туннель отвечает на 127.0.0.1:1234"
else
    echo "   FAIL — нет ответа. Поднимите туннель: ssh -N -R 0.0.0.0:1234:192.168.88.56:1234 hackathon@VPS"
    exit 1
fi

# 2. Узнать, на какой IP контейнер стучится и из какой подсети (source)
GATEWAY_IP=$(docker exec hackathon-ml getent hosts host.docker.internal 2>/dev/null | awk '{print $1}' || true)
CONTAINER_NET=$(docker inspect hackathon-ml --format '{{range $k, $v := .NetworkSettings.Networks}}{{$v.IPAddress}} {{$v.Gateway}} {{end}}' 2>/dev/null | awk '{print $1; exit}')
# Подсеть контейнера: 172.19.0.5 → 172.19.0.0/16 (источник пакетов — именно она важна для INPUT)
CONTAINER_SUBNET=$(echo "$CONTAINER_NET" | sed -n 's/^\([0-9]*\.[0-9]*\.[0-9]*\)\.[0-9]*$/\1.0\/16/p')
if [ -z "$GATEWAY_IP" ]; then
    echo "2. host.docker.internal в контейнере не резолвится (нет extra_hosts?)"
    GATEWAY_IP="172.17.0.1"
else
    echo "2. Контейнер стучится на host.docker.internal = $GATEWAY_IP, сам контейнер в подсети $CONTAINER_SUBNET"
fi
if curl -s -m 3 http://${GATEWAY_IP}:1234/v1/models >/dev/null 2>&1; then
    echo "   OK — туннель слушает на $GATEWAY_IP:1234"
else
    echo "   FAIL — с хоста $GATEWAY_IP:1234 не отвечает. Туннель: ssh -R 0.0.0.0:1234:..."
    exit 1
fi

# 3. Из контейнера
echo "3. Контейнер hackathon-ml → host.docker.internal:1234"
if docker exec hackathon-ml python -c "import urllib.request; urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=5)" >/dev/null 2>&1; then
    echo "   OK — контейнер достучался до LM Studio"
    exit 0
fi

echo "   FAIL — таймаут из контейнера. UFW/iptables режет INPUT: пакеты идут с подсети контейнера (source), не шлюза."
echo ""
echo "Пакеты из контейнера имеют source = $CONTAINER_SUBNET (hackathon-net). Разрешите порт 1234 с этой подсети (нужен root):"
echo "  sudo iptables -I INPUT -p tcp -s $CONTAINER_SUBNET --dport 1234 -j ACCEPT"
if [ -n "$CONTAINER_SUBNET" ] && [ "$CONTAINER_SUBNET" != "172.17.0.0/16" ]; then
    echo "  # если уже добавляли 172.17.0.0/16 — нужна именно подсеть контейнера (часто 172.19.0.0/16)"
fi
echo "  sudo netfilter-persistent save   # или: iptables-save | sudo tee /etc/iptables/rules.v4"
echo ""
exit 1
