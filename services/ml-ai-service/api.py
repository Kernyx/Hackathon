"""
FastAPI сервер для ML AI Service.

Эндпоинты:
  POST /api/v1/ml/users/{userId}/messages      — отправить сообщение от пользователя в обсуждение
  GET  /api/v1/ml/users/{userId}/conversation   — получить историю сообщений (polling)
  GET  /api/v1/ml/users/{userId}/session        — получить статус сессии
  POST /api/v1/ml/users/{userId}/session        — создать/инициализировать сессию
  GET  /health                                  — healthcheck

Фоновая симуляция:
  При создании сессии запускается фоновый поток, в котором агенты общаются
  между собой автономно (run_tick). Пользователь может в любой момент отправить
  сообщение через POST /messages, и агенты ответят ему.
"""

import os
import sys
import time
import random
import threading
import traceback
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Настройка кодировки
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault("HTTP_PROXY", "")
os.environ.setdefault("HTTPS_PROXY", "")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

from config import LLM_MODEL, LLM_BASE_URL, CHROMA_DB_PATH
from models import RACES
from scenarios import ScenarioManager
from orchestrator import RACE_PRESETS, create_agents, BigBrotherOrchestrator
from session import session_manager
from topics import TopicManager, DialoguePhaseManager


# ─── Pydantic-схемы ──────────────────────────────────────────

class MessageRequest(BaseModel):
    """Запрос на отправку сообщения от пользователя."""
    message: str = Field(..., min_length=1, max_length=2000, description="Текст сообщения")
    target_agent: Optional[str] = Field(
        None,
        description="Имя агента для личного сообщения. None / не указано = сообщение всем"
    )


class AgentResponse(BaseModel):
    """Ответ одного агента."""
    agent_id: str
    name: str
    text: str
    tick: int
    race: str
    race_emoji: str
    mood: str


class MessageResponse(BaseModel):
    """Ответ на сообщение пользователя."""
    user_message: str
    target: str  # "all" или имя агента
    responses: list[AgentResponse]
    tick: int
    session_id: str


class SessionCreateRequest(BaseModel):
    """Запрос на создание сессии."""
    scenario: str = Field("desert_island", description="Ключ сценария")
    race_preset: str = Field("humans", description="Ключ расового пресета")


class SessionInfo(BaseModel):
    """Информация о сессии."""
    user_id: str
    is_active: bool
    scenario: str
    agents: list[dict]
    tick: int
    available_scenarios: list[str]
    available_race_presets: list[str]


class HealthResponse(BaseModel):
    status: str = "ok"
    model: str
    llm_url: str


class ConversationEntry(BaseModel):
    """Одно сообщение в истории."""
    tick: int
    agent_id: str
    name: str
    text: str
    is_event: bool = False
    is_new_topic: bool = False


class ConversationResponse(BaseModel):
    """История сообщений."""
    user_id: str
    entries: list[ConversationEntry]
    total: int
    last_tick: int
    simulation_running: bool


class SessionSettingsRequest(BaseModel):
    """Запрос на изменение настроек сессии."""
    speed_seconds: float = Field(
        ...,
        ge=0.5,
        le=60.0,
        description="Задержка между сообщениями агентов в секундах (0.5–60)",
        examples=[1.0, 5.0, 15.0],
    )


class SessionSettingsResponse(BaseModel):
    """Подтверждение обновления настроек."""
    user_id: str
    speed_seconds: float
    message: str


# ─── Фоновая симуляция ────────────────────────────────────────

# {user_id: threading.Thread}
_simulation_threads: dict[str, threading.Thread] = {}
_simulation_stop_flags: dict[str, threading.Event] = {}
_simulation_locks: dict[str, threading.Lock] = {}


def _get_session_lock(user_id: str) -> threading.Lock:
    """Получить или создать lock для сессии (для синхронизации tick/message)."""
    if user_id not in _simulation_locks:
        _simulation_locks[user_id] = threading.Lock()
    return _simulation_locks[user_id]


def _simulation_loop(user_id: str):
    """
    Фоновый цикл симуляции — агенты общаются между собой.

    Работает в отдельном потоке для каждой сессии.
    Когда приходит сообщение от пользователя (POST /messages),
    lock не даёт одновременно выполнять tick и user message.
    """
    from config import TICK_DELAY

    stop_flag = _simulation_stop_flags.get(user_id)
    if not stop_flag:
        return

    session = session_manager.get_session(user_id)
    if not session or not session.orchestrator:
        return

    orchestrator = session.orchestrator
    lock = _get_session_lock(user_id)

    print(f"[Simulation] Фоновая симуляция запущена для {user_id[:8]}...")

    while not stop_flag.is_set():
        try:
            with lock:
                if orchestrator._quit_requested:
                    break

                entry = orchestrator.run_tick()
                if entry:
                    orchestrator.print_entry(entry)

                # Иногда второй тик подряд (как в терминальном режиме)
                if random.random() < 0.50:
                    entry2 = orchestrator.run_tick()
                    if entry2:
                        orchestrator.print_entry(entry2)

            # Задержка между тиками
            delay = orchestrator.tick_delay if orchestrator.tick_delay > 0 else TICK_DELAY
            # Проверяем stop_flag каждые 0.5 сек, чтобы быстро остановиться
            waited = 0.0
            while waited < delay and not stop_flag.is_set():
                time.sleep(min(0.5, delay - waited))
                waited += 0.5

        except Exception as e:
            print(f"[Simulation] Ошибка в симуляции {user_id[:8]}: {e}")
            traceback.print_exc()
            time.sleep(2.0)

    print(f"[Simulation] Фоновая симуляция остановлена для {user_id[:8]}...")


def _start_simulation(user_id: str):
    """Запустить фоновую симуляцию для сессии."""
    if user_id in _simulation_threads and _simulation_threads[user_id].is_alive():
        return  # Уже запущена

    stop_flag = threading.Event()
    _simulation_stop_flags[user_id] = stop_flag

    thread = threading.Thread(
        target=_simulation_loop,
        args=(user_id,),
        daemon=True,
        name=f"sim-{user_id[:8]}",
    )
    _simulation_threads[user_id] = thread
    thread.start()


def _stop_simulation(user_id: str):
    """Остановить фоновую симуляцию."""
    stop_flag = _simulation_stop_flags.pop(user_id, None)
    if stop_flag:
        stop_flag.set()
    thread = _simulation_threads.pop(user_id, None)
    if thread and thread.is_alive():
        thread.join(timeout=5.0)
    _simulation_locks.pop(user_id, None)


# ─── Инициализация сессии ─────────────────────────────────────

def _init_session(user_id: str, scenario: str = "desert_island",
                  race_preset: str = "humans"):
    """Инициализировать сессию: создать агентов, оркестратор, начать обсуждение."""
    session = session_manager.get_or_create_session(user_id)

    if session.orchestrator is not None:
        return session

    registry = session.agent_registry

    # Очистка данных предыдущих сессий
    data_dir = Path("data")
    if data_dir.exists():
        for file in ["agent_memory.json", "topics.json", "scenario.json", "vector_memory.json"]:
            file_path = data_dir / file
            if file_path.exists():
                file_path.unlink()

    agents = create_agents(race_preset, user_id=user_id, registry=registry)
    orchestrator = BigBrotherOrchestrator(
        agents, scenario, user_id=user_id, registry=registry,
    )
    session.orchestrator = orchestrator

    # Стартовая тема
    scenario_context = orchestrator.scenario_manager.get_scenario_context()
    start_topic = orchestrator.topic_manager.get_new_topic(scenario_context)
    orchestrator.phase_manager.start_new_topic(0)

    starter = {
        "tick": 0, "agent_id": "system",
        "name": "Ведущий",
        "text": f"Привет всем! Давайте обсудим: {start_topic}",
        "is_new_topic": True,
    }
    orchestrator.conversation.append(starter)
    for agent in agents:
        agent.process_message(0, "Ведущий", starter["text"], is_own=False)

    # Запускаем фоновую симуляцию — агенты общаются между собой
    _start_simulation(user_id)

    return session


def _get_session_with_orchestrator(user_id: str):
    """Получить сессию с инициализированным оркестратором или выбросить 404."""
    session = session_manager.get_session(user_id)
    if session is None or session.orchestrator is None:
        raise HTTPException(
            status_code=404,
            detail=f"Сессия для пользователя '{user_id}' не найдена. "
                   f"Сначала создайте сессию: POST /api/v1/ml/users/{user_id}/session"
        )
    return session


# ─── FastAPI App ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[ML-AI-Service] Запуск API сервера...")
    print(f"[ML-AI-Service] Модель: {LLM_MODEL}")
    print(f"[ML-AI-Service] LLM API: {LLM_BASE_URL}")
    yield
    # Shutdown: останавливаем симуляции и сохраняем сессии
    print(f"[ML-AI-Service] Остановка сервера, сохранение сессий...")
    for session_info in session_manager.list_sessions():
        uid = session_info["user_id"]
        _stop_simulation(uid)
        session_manager.close_session(uid)
    print(f"[ML-AI-Service] Все сессии сохранены.")


app = FastAPI(
    title="ML AI Service",
    description="Сервис AI-агентов с памятью, настроением и расами",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Эндпоинты ───────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    """Healthcheck."""
    return HealthResponse(status="ok", model=LLM_MODEL, llm_url=LLM_BASE_URL)


@app.post("/api/v1/ml/users/{user_id}/session", response_model=SessionInfo)
async def create_session(user_id: str, request: SessionCreateRequest = None):
    """
    Создать или переинициализировать сессию для пользователя.
    
    Создаёт агентов, выбирает сценарий, запускает обсуждение.
    """
    if request is None:
        request = SessionCreateRequest()

    # Валидация сценария
    if request.scenario not in ScenarioManager.SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный сценарий: '{request.scenario}'. "
                   f"Доступные: {list(ScenarioManager.SCENARIOS.keys())}"
        )

    # Валидация расового пресета
    if request.race_preset not in RACE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный расовый пресет: '{request.race_preset}'. "
                   f"Доступные: {list(RACE_PRESETS.keys())}"
        )

    try:
        session = _init_session(user_id, request.scenario, request.race_preset)
        orchestrator = session.orchestrator

        agents_info = []
        for a in orchestrator.agents:
            race = a.race
            agents_info.append({
                "agent_id": a.agent_id,
                "name": session.agent_registry.get_name(a.agent_id),
                "race": race.race_type.value,
                "race_emoji": race.emoji,
                "race_name": race.name_ru,
                "personality": a.personality_type.value,
                "mood": a.mood.get_dominant_emotion(),
                "is_male": a.is_male,
                "age": a.age,
            })

        return SessionInfo(
            user_id=user_id,
            is_active=session.is_active,
            scenario=orchestrator.scenario_manager.current_scenario.name,
            agents=agents_info,
            tick=orchestrator.tick,
            available_scenarios=list(ScenarioManager.SCENARIOS.keys()),
            available_race_presets=list(RACE_PRESETS.keys()),
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ошибка создания сессии: {str(e)}")


@app.get("/api/v1/ml/users/{user_id}/session", response_model=SessionInfo)
async def get_session(user_id: str):
    """Получить информацию о сессии пользователя."""
    session = _get_session_with_orchestrator(user_id)
    orchestrator = session.orchestrator

    agents_info = []
    for a in orchestrator.agents:
        race = a.race
        agents_info.append({
            "agent_id": a.agent_id,
            "name": session.agent_registry.get_name(a.agent_id),
            "race": race.race_type.value,
            "race_emoji": race.emoji,
            "race_name": race.name_ru,
            "personality": a.personality_type.value,
            "mood": a.mood.get_dominant_emotion(),
            "is_male": a.is_male,
            "age": a.age,
        })

    return SessionInfo(
        user_id=user_id,
        is_active=session.is_active,
        scenario=orchestrator.scenario_manager.current_scenario.name,
        agents=agents_info,
        tick=orchestrator.tick,
        available_scenarios=list(ScenarioManager.SCENARIOS.keys()),
        available_race_presets=list(RACE_PRESETS.keys()),
    )


@app.patch("/api/v1/ml/users/{user_id}/session/settings", response_model=SessionSettingsResponse)
async def update_session_settings(user_id: str, request: SessionSettingsRequest):
    """
    Изменить настройки сессии.

    Позволяет фронтенду управлять скоростью общения агентов —
    задержкой (в секундах) между их сообщениями.
    """
    session = _get_session_with_orchestrator(user_id)
    orchestrator = session.orchestrator

    old_delay = orchestrator.tick_delay
    orchestrator.tick_delay = request.speed_seconds

    return SessionSettingsResponse(
        user_id=user_id,
        speed_seconds=request.speed_seconds,
        message=f"Скорость обновлена: {request.speed_seconds} сек между сообщениями "
                f"(было {old_delay} сек)",
    )


@app.post("/api/v1/ml/users/{user_id}/messages", response_model=MessageResponse)
async def send_message(user_id: str, request: MessageRequest):
    """
    Отправить сообщение от пользователя в обсуждение.
    
    Frontend отправляет сообщение → ML-сервис добавляет его в обсуждение →
    агенты генерируют ответы → ответы возвращаются.
    
    Если target_agent указан — личное сообщение конкретному агенту.
    Если target_agent не указан (None) — сообщение всем агентам.
    """
    session = _get_session_with_orchestrator(user_id)
    orchestrator = session.orchestrator

    # Определяем целевых агентов
    if request.target_agent:
        # Личное сообщение конкретному агенту
        found_id = session.agent_registry.get_id_fuzzy(request.target_agent)
        if not found_id:
            available = session.agent_registry.get_all_names()
            raise HTTPException(
                status_code=404,
                detail=f"Агент '{request.target_agent}' не найден. "
                       f"Доступные агенты: {available}"
            )
        target_agent = next(
            (a for a in orchestrator.agents if a.agent_id == found_id), None
        )
        if not target_agent:
            raise HTTPException(status_code=404, detail=f"Агент не найден в симуляции")
        target_agents = [target_agent]
        target_label = session.agent_registry.get_name(found_id)
    else:
        # Сообщение всем агентам
        target_agents = list(orchestrator.agents)
        target_label = "all"

    try:
        # Lock — чтобы фоновая симуляция не делала tick одновременно
        lock = _get_session_lock(user_id)
        with lock:
            responses_raw = orchestrator.inject_user_message_api(
                request.message, target_agents
            )

        responses = [
            AgentResponse(
                agent_id=r["agent_id"],
                name=r["name"],
                text=r["text"],
                tick=r["tick"],
                race=r["race"],
                race_emoji=r["race_emoji"],
                mood=r["mood"],
            )
            for r in responses_raw
        ]

        return MessageResponse(
            user_message=request.message,
            target=target_label,
            responses=responses,
            tick=orchestrator.tick,
            session_id=user_id,
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки сообщения: {str(e)}"
        )


@app.get("/api/v1/ml/users/{user_id}/conversation", response_model=ConversationResponse)
async def get_conversation(
    user_id: str,
    after_tick: int = Query(-1, description="Вернуть сообщения после этого тика (для polling)"),
    limit: int = Query(50, ge=1, le=200, description="Максимум сообщений"),
):
    """
    Получить историю сообщений.

    Фронтенд вызывает этот эндпоинт по таймеру (polling), чтобы подтягивать
    новые сообщения, которые агенты сгенерировали в фоне.

    Пример polling:
      1. GET /conversation?after_tick=-1&limit=50   → получить последние 50
      2. Запомнить last_tick из ответа
      3. GET /conversation?after_tick=42&limit=50    → только новые после тика 42
    """
    session = _get_session_with_orchestrator(user_id)
    orchestrator = session.orchestrator

    all_entries = orchestrator.conversation

    # Фильтруем по after_tick
    if after_tick >= 0:
        filtered = [e for e in all_entries if e.get("tick", 0) > after_tick]
    else:
        filtered = list(all_entries)

    # Берём последние limit
    filtered = filtered[-limit:]

    entries = [
        ConversationEntry(
            tick=e.get("tick", 0),
            agent_id=e.get("agent_id", ""),
            name=e.get("name", ""),
            text=e.get("text", ""),
            is_event=e.get("is_event", False),
            is_new_topic=e.get("is_new_topic", False),
        )
        for e in filtered
    ]

    last_tick = all_entries[-1].get("tick", 0) if all_entries else 0
    sim_running = user_id in _simulation_threads and _simulation_threads[user_id].is_alive()

    return ConversationResponse(
        user_id=user_id,
        entries=entries,
        total=len(all_entries),
        last_tick=last_tick,
        simulation_running=sim_running,
    )
