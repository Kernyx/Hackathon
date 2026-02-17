"""
Audit Service клиент: отправка событий (POST /api/v1/audit/events) в Audit Service.

Формат payload по swagger-спецификации:
  - source_agent: { agent_id, name, mood, relationships, activity, plan }
  - target_agents: [{ agent_id, name }]
  - data: { message, tick, is_initiative, action_result, sentiments }
  - simulation_context: { scenario_name, current_topic, phase }

Авторизация: Bearer JWT (токен из env AUDIT_JWT_TOKEN).
"""

import threading
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

import httpx
from colorama import Fore, Style

from config import AUDIT_API_URL, AUDIT_JWT_TOKEN

if TYPE_CHECKING:
    from agent import Agent


_audit_http_client = httpx.Client(
    timeout=httpx.Timeout(10.0, connect=5.0),
    proxy=None,
)


def _serialize_source_agent(agent: 'Agent') -> dict:
    """
    Сериализовать состояние агента-инициатора для Audit API.
    Формат: agent_id, name, mood, relationships, activity, plan.
    """
    _reg = agent._get_registry()
    mood = agent.mood
    plan = agent.current_plan

    # Отношения: agent_id → { value, display_name }
    relationships = {}
    for other_id, value in agent.relationships.items():
        relationships[other_id] = {
            "value": round(value, 3),
            "display_name": _reg.get_name(other_id),
        }

    return {
        "agent_id": agent.agent_id,
        "name": _reg.get_name(agent.agent_id),
        "mood": {
            "dominant_emotion": mood.get_dominant_emotion(),
            "happiness": round(mood.happiness, 3),
            "energy": round(mood.energy, 3),
            "stress": round(mood.stress, 3),
            "anger": round(mood.anger, 3),
            "fear": round(mood.fear, 3),
        },
        "relationships": relationships,
        "activity": {
            "talkativeness": round(agent.talkativeness, 3),
            "messages_spoken": agent.messages_spoken,
        },
        "plan": {
            "goal": plan.goal if plan else None,
            "current_step": plan.current_step if plan else 0,
        } if plan else None,
    }


def _serialize_target_agent(agent: 'Agent') -> dict:
    """Сериализовать агента-получателя (только id и имя)."""
    _reg = agent._get_registry()
    return {
        "agent_id": agent.agent_id,
        "name": _reg.get_name(agent.agent_id),
    }


def send_audit_event(
    event_type: str,
    source_agent: 'Agent',
    target_agents: list['Agent'],
    message: str,
    tick: int,
    scenario_name: str = "",
    scenario_description: str = "",
    active_event: Optional[str] = None,
    current_topic: Optional[str] = None,
    current_phase: Optional[str] = None,
    phase_label: Optional[str] = None,
    is_initiative: bool = False,
    is_new_topic: bool = False,
    action_result: Optional[str] = None,
    sentiments: Optional[dict] = None,
) -> None:
    """
    Отправить полное событие в Audit Service (неблокирующе, в фоновом потоке).

    Args:
        event_type: "message_sent" | "new_topic" | "event_reaction"
        source_agent: Agent объект — инициатор
        target_agents: список Agent объектов — получатели
        message: текст сообщения
        tick: номер тика симуляции
        scenario_name: название текущего сценария
        scenario_description: описание сценария
        active_event: текст активного события (если есть)
        current_topic: текущая тема обсуждения
        current_phase: текущая фаза ("discuss", "decide", "act", "conclude")
        phase_label: человекочитаемая метка фазы
        is_initiative: агент инициировал тему/действие
        is_new_topic: это предложение новой темы
        action_result: результат действия (если был)
        sentiments: dict target_id → (delta, reason) — изменения отношений
    """
    # Сериализуем sentiments в JSON-совместимый формат
    sentiments_data = None
    if sentiments:
        sentiments_data = {}
        for target_id, (delta, reason) in sentiments.items():
            sentiments_data[target_id] = {
                "delta": round(delta, 3),
                "reason": reason,
            }

    payload = {
        "event_type": event_type,
        "source_agent": _serialize_source_agent(source_agent),
        "target_agents": [_serialize_target_agent(a) for a in target_agents],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data": {
            "message": message,
            "tick": tick,
            "is_initiative": is_initiative,
            "action_result": action_result,
            "sentiments": sentiments_data,
        },
        "simulation_context": {
            "scenario_name": scenario_name,
            "current_topic": current_topic,
            "phase": current_phase,
        },
    }

    thread = threading.Thread(
        target=_send_request,
        args=(payload,),
        daemon=True,
    )
    thread.start()


def _send_request(payload: dict) -> None:
    """Фактическая отправка POST-запроса (выполняется в фоновом потоке)."""
    try:
        headers = {"Content-Type": "application/json"}
        if AUDIT_JWT_TOKEN:
            headers["Authorization"] = f"Bearer {AUDIT_JWT_TOKEN}"

        response = _audit_http_client.post(
            AUDIT_API_URL,
            json=payload,
            headers=headers,
        )
        if response.status_code == 202:
            pass  # Успех — тихо
        elif response.status_code == 429:
            print(f"{Fore.YELLOW}  Audit: слишком много запросов (429){Style.RESET_ALL}")
        elif response.status_code == 400:
            print(f"{Fore.RED}  Audit: невалидный запрос (400): {response.text[:100]}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}  Audit: HTTP {response.status_code}{Style.RESET_ALL}")
    except httpx.ConnectError:
        pass  # Audit Service недоступен — не ломаем симуляцию
    except httpx.TimeoutException:
        pass  # Таймаут — не ломаем симуляцию
    except Exception as e:
        print(f"{Fore.RED}  Audit ошибка: {e}{Style.RESET_ALL}")

