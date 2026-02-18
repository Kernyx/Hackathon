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

# 2. Узнать, на какой IP контейнер стучится (host.docker.internal = шлюз его сети)
GATEWAY_IP=$(docker exec hackathon-ml getent hosts host.docker.internal 2>/dev/null | awk '{print $1}' || true)
if [ -z "$GATEWAY_IP" ]; then
    echo "2. host.docker.internal в контейнере не резолвится (нет extra_hosts?)"
    GATEWAY_IP="172.17.0.1"
else
    echo "2. Контейнер стучится на host.docker.internal = $GATEWAY_IP"
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

# Подсеть шлюза (172.17.0.1 → 172.17.0.0/16, 172.18.0.1 → 172.18.0.0/16)
SUBNET=$(echo "$GATEWAY_IP" | sed -n 's/^\([0-9]*\.[0-9]*\.[0-9]*\)\.[0-9]*$/\1.0\/16/p')
echo "   FAIL — таймаут из контейнера. Фаервол режет INPUT с подсети контейнера."
echo ""
echo "Контейнер в пользовательской сети (hackathon-net), шлюз = $GATEWAY_IP (не 172.17.0.1)."
echo "Разрешите порт 1234 с подсети $SUBNET (нужен root):"
echo "  sudo iptables -I INPUT -p tcp -s $SUBNET --dport 1234 -j ACCEPT"
echo "  sudo netfilter-persistent save   # или iptables-save в rules"
echo ""
echo "Подробнее: docs/ML-LMSTUDIO-TUNNEL.md"
exit 1
