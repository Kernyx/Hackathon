"""
Audit Service клиент: отправка событий (POST /events) в Audit Service.

Передаёт ПОЛНУЮ информацию о состоянии агентов и симуляции:
  - Полные данные source/target агентов (раса, Big Five, настроение, отношения, план)
  - Контекст симуляции (тик, сценарий, фаза, активное событие, тема)
  - Текст сообщения и метаданные
"""

import threading
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

import httpx
from colorama import Fore, Style

from config import AUDIT_API_URL

if TYPE_CHECKING:
    from agent import Agent


_audit_http_client = httpx.Client(
    timeout=httpx.Timeout(10.0, connect=5.0),
    proxy=None,
)


def _serialize_agent(agent: 'Agent') -> dict:
    """Сериализовать полное состояние агента для API."""
    _reg = agent._get_registry()

    mood = agent.mood
    race = agent.race
    mods = race.modifiers
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
        "personality_type": agent.personality_type.value,
        "race": {
            "type": agent.race_type.value,
            "name_ru": race.name_ru,
            "emoji": race.emoji,
            "description": race.description,
            "modifiers": {
                "repair_bonus": mods.repair_bonus,
                "combat_bonus": mods.combat_bonus,
                "diplomacy_bonus": mods.diplomacy_bonus,
                "detection_bonus": mods.detection_bonus,
                "can_betray": mods.can_betray,
                "stubborn": mods.stubborn,
            },
        },
        "big_five": {
            "openness": agent.big_five.openness,
            "conscientiousness": agent.big_five.conscientiousness,
            "extraversion": agent.big_five.extraversion,
            "agreeableness": agent.big_five.agreeableness,
            "neuroticism": agent.big_five.neuroticism,
        },
        "demographics": {
            "is_male": agent.is_male,
            "age": agent.age,
            "interests": agent.interests,
        },
        "mood": {
            "dominant_emotion": mood.get_dominant_emotion(),
            "emoji": mood.get_emoji(),
            "happiness": round(mood.happiness, 3),
            "energy": round(mood.energy, 3),
            "stress": round(mood.stress, 3),
            "anger": round(mood.anger, 3),
            "fear": round(mood.fear, 3),
        },
        "relationships": relationships,
        "activity": {
            "talkativeness": round(agent.talkativeness, 3),
            "ticks_silent": agent.ticks_silent,
            "messages_spoken": agent.messages_spoken,
            "consecutive_similar_count": agent.consecutive_similar_count,
        },
        "plan": {
            "goal": plan.goal if plan else None,
            "current_step": plan.current_step if plan else None,
            "steps": plan.steps if plan else [],
        } if plan else None,
        "active_event": agent.active_event,
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
        "user_id": source_agent.user_id,
        "source_agent": _serialize_agent(source_agent),
        "target_agents": [_serialize_agent(a) for a in target_agents],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "message": message,
            "mood": source_agent.mood.get_dominant_emotion(),
            "tick": tick,
            "is_initiative": is_initiative,
            "is_new_topic": is_new_topic,
            "action_result": action_result,
            "sentiments": sentiments_data,
        },
        "simulation_context": {
            "scenario": {
                "name": scenario_name,
                "description": scenario_description,
            },
            "active_event": active_event,
            "current_topic": current_topic,
            "phase": {
                "current": current_phase,
                "label": phase_label,
            },
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
        response = _audit_http_client.post(
            AUDIT_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
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

