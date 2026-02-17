"""
Скрипт для локального тестирования ML AI Service API.
Запуск: python test_api.py

Тестирует:
  1. GET  /health
  2. POST /api/v1/ml/users/{userId}/session — создание сессии
  3. GET  /api/v1/ml/users/{userId}/session — получение сессии
  4. Ожидание фоновой симуляции (агенты общаются сами)
  5. GET  /api/v1/ml/users/{userId}/conversation — polling новых сообщений
  6. POST /api/v1/ml/users/{userId}/messages — сообщение всем
  7. POST /api/v1/ml/users/{userId}/messages — личное сообщение
  8. Повторный polling — видим и ответы агентов, и фоновые сообщения
"""

import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8083"
USER_ID = "test-user-123"


def request(method: str, path: str, body: dict = None) -> dict:
    """Простой HTTP-клиент без зависимостей."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return {"status": resp.status, "data": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return {"status": e.code, "data": json.loads(raw) if raw else {}}
    except urllib.error.URLError as e:
        return {"status": 0, "data": {"error": str(e.reason)}}


def print_result(label: str, result: dict):
    status = result["status"]
    icon = "✅" if 200 <= status < 300 else "❌"
    print(f"\n{icon} {label} — HTTP {status}")
    print(json.dumps(result["data"], indent=2, ensure_ascii=False))


def main():
    print("=" * 60)
    print("  ТЕСТ ML AI Service API")
    print(f"  Сервер: {BASE_URL}")
    print(f"  User ID: {USER_ID}")
    print("=" * 60)

    # 1. Health check
    print("\n--- 1. Health Check ---")
    r = request("GET", "/health")
    print_result("GET /health", r)
    if r["status"] != 200:
        print("\n❌ Сервер не отвечает! Убедитесь что он запущен: python main.py --api")
        sys.exit(1)

    # 2. Создание сессии (запускает фоновую симуляцию!)
    print("\n--- 2. Создание сессии ---")
    r = request("POST", f"/api/v1/ml/users/{USER_ID}/session", {
        "scenario": "desert_island",
        "race_preset": "humans"
    })
    print_result("POST /session", r)
    if r["status"] not in (200, 201):
        print("\n❌ Не удалось создать сессию!")
        sys.exit(1)

    agents = r["data"].get("agents", [])
    print(f"\n📋 Агенты в сессии: {len(agents)}")
    for a in agents:
        print(f"   {a.get('race_emoji', '')} {a['name']} ({a.get('race', '')}, {a.get('personality', '')})")

    # 3. Получение сессии
    print("\n--- 3. Получение информации о сессии ---")
    r = request("GET", f"/api/v1/ml/users/{USER_ID}/session")
    print_result("GET /session", r)

    # 4. Ждём фоновую симуляцию
    print("\n--- 4. Ждём 15 сек — агенты общаются в фоне ---")
    for i in range(15, 0, -1):
        print(f"   ⏳ {i} сек...", end="\r")
        time.sleep(1)
    print("   ✅ Готово!       ")

    # 5. Polling — получаем сообщения, которые агенты сгенерировали сами
    print("\n--- 5. Polling: GET /conversation ---")
    r = request("GET", f"/api/v1/ml/users/{USER_ID}/conversation?after_tick=-1&limit=50")
    print_result("GET /conversation", r)

    if r["status"] == 200:
        entries = r["data"].get("entries", [])
        sim_running = r["data"].get("simulation_running", False)
        last_tick = r["data"].get("last_tick", 0)
        print(f"\n💬 Сообщений в истории: {len(entries)}")
        print(f"🔄 Симуляция запущена: {sim_running}")
        print(f"📍 Последний тик: {last_tick}")
        for e in entries[-10:]:  # Последние 10
            emoji = "📢" if e.get("is_event") else "💬"
            print(f"   {emoji} [tick {e['tick']}] {e['name']}: {e['text'][:80]}")

    # 6. Сообщение всем агентам
    print("\n--- 6. Сообщение ВСЕМ агентам ---")
    print("⏳ Ожидание ответа от LLM...")
    r = request("POST", f"/api/v1/ml/users/{USER_ID}/messages", {
        "message": "Привет всем! Как вы тут оказались?",
        "target_agent": None
    })
    print_result("POST /messages (all)", r)

    if r["status"] == 200:
        responses = r["data"].get("responses", [])
        print(f"\n💬 Получено ответов: {len(responses)}")
        for resp in responses:
            print(f"   {resp.get('race_emoji', '')} {resp['name']}: {resp['text']}")

    # 7. Личное сообщение первому агенту
    if agents:
        target_name = agents[0]["name"]
        print(f"\n--- 7. Личное сообщение для {target_name} ---")
        print("⏳ Ожидание ответа от LLM...")
        r = request("POST", f"/api/v1/ml/users/{USER_ID}/messages", {
            "message": "Расскажи о себе, кто ты?",
            "target_agent": target_name
        })
        print_result(f"POST /messages (to {target_name})", r)

        if r["status"] == 200:
            responses = r["data"].get("responses", [])
            for resp in responses:
                print(f"   {resp.get('race_emoji', '')} {resp['name']}: {resp['text']}")

    # 8. Ещё раз polling — видим и фоновые, и ответы на наши сообщения
    print(f"\n--- 8. Повторный polling (after_tick={last_tick}) ---")
    r = request("GET", f"/api/v1/ml/users/{USER_ID}/conversation?after_tick={last_tick}&limit=50")
    if r["status"] == 200:
        entries = r["data"].get("entries", [])
        new_last_tick = r["data"].get("last_tick", 0)
        print(f"💬 Новых сообщений: {len(entries)} (тик {last_tick} → {new_last_tick})")
        for e in entries:
            emoji = "📢" if e.get("is_event") else "💬"
            print(f"   {emoji} [tick {e['tick']}] {e['name']}: {e['text'][:80]}")

    # 9. Тест ошибки — несуществующая сессия
    print("\n--- 9. Тест ошибки: несуществующий пользователь ---")
    r = request("POST", "/api/v1/ml/users/nonexistent-user/messages", {
        "message": "Привет!"
    })
    print_result("POST /messages (404 expected)", r)

    print("\n" + "=" * 60)
    print("  ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 60)


if __name__ == "__main__":
    main()
