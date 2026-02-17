"""
MVP: 3 AI-агента общаются между собой в терминале.
Ядро — LM Studio (OpenAI-совместимый API) с моделью qwen-3-14b-instruct.

ИСПРАВЛЕНИЯ v2:
1. Реальный диалог — агенты отвечают друг другу, а не говорят в пустоту
2. Контекст памяти — агенты помнят что произошло, результаты действий в контексте
3. Антиабсурд — системный промпт запрещает опасные/нелогичные действия
4. Результаты действий попадают в контекст следующего агента
5. Антиповтор — трекинг уже сделанных действий
6. Фокус на событиях — события удерживают внимание 5-8 тиков
7. Система отношений — симпатия/антипатия меняются от взаимодействий
8. BigBrother — контроль качества высказываний
9. Мягкая компрессия памяти — сохраняет важные события
10. Темы не меняются хаотично — требуется завершение обсуждения
"""

import sys
import os
import random
import time
import json
import threading
import queue
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
from datetime import datetime
from enum import Enum

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError
from colorama import init, Fore, Style

load_dotenv()
init(autoreset=True)

import re as _re
from difflib import SequenceMatcher

def _text_similarity(a: str, b: str) -> float:
    """Быстрая оценка похожести двух строк (0..1)."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if not a_lower or not b_lower:
        return 0.0
    return SequenceMatcher(None, a_lower, b_lower).ratio()

def _extract_phrases(text: str) -> set:
    """Извлекает ключевые n-граммы (3 слова) из текста."""
    words = _re.findall(r'[а-яёa-z]+', text.lower())
    if len(words) < 3:
        return set(words)
    return {' '.join(words[i:i+3]) for i in range(len(words)-2)}

# [FIX v3] Запрещённые паттерны — фразы, в которые LLM застревает
_BANNED_PATTERNS = [
    'ты думаешь, что',
    'ты вообще думаешь',
    'вы все такие тупые',
    'вы все тупые',
    'вы все бесполезны',
    'я просто разозлена',
    'я не устала',
    'а что, если мы не просто',
    'а что если мы не просто',
    'а что, если вместо',
    'а что если вместо',
    'кто со мной',
    'кто первый',
    'кто первым',
    'давайте сначала проверим',
    'вашей глупостью',
    'ваша глупость',
    'как работает мир',
    'наконец поняли',
]

def _has_banned_pattern(text: str) -> bool:
    """Проверяет, содержит ли текст запрещённые паттерны-петли."""
    text_lower = text.lower().strip()
    for pattern in _BANNED_PATTERNS:
        if pattern in text_lower:
            return True
    return False

def _has_repetitive_pattern(text: str, recent_texts: list) -> bool:
    """Проверяет, содержит ли текст повторяющиеся паттерны из недавних сообщений."""
    if not recent_texts:
        return _has_banned_pattern(text)
    # Проверка запрещённых паттернов
    if _has_banned_pattern(text):
        return True
    new_phrases = _extract_phrases(text)
    if not new_phrases:
        return False
    for prev_text in recent_texts[-6:]:
        prev_phrases = _extract_phrases(prev_text)
        if not prev_phrases:
            continue
        overlap = len(new_phrases & prev_phrases) / max(len(new_phrases), 1)
        if overlap > 0.35:  # снижен порог с 0.4 для более жёсткого контроля
            return True
    # Проверка одинаковых начал
    repetitive_starts = [
        'а что, если мы не просто',
        'а что если мы не просто',
        'а что, если вместо',
        'а что если вместо',
        'кто со мной',
        'кто первый',
        'кто первым',
        'пусть ',
        'давайте сначала проверим',
        'ты думаешь',
        'ты вообще думаешь',
    ]
    text_lower = text.lower().strip()
    start_matches = sum(1 for rt in recent_texts[-4:]
                        if any(rt.lower().strip().startswith(s) and text_lower.startswith(s)
                               for s in repetitive_starts))
    if start_matches >= 1:
        return True
    return False

# Отключаем прокси для локальных запросов
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

# ── Конфигурация ──────────────────────────────────────────────

LLM_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.getenv("OLLAMA_API_KEY", "not-needed")
LLM_MODEL = os.getenv("OLLAMA_MODEL", "qwen-3-14b-instruct")

MAX_TICKS = 50          # сколько ходов длится симуляция
TICK_DELAY = 1.0        # пауза между ходами (сек)
MEMORY_WINDOW = 12      # сколько последних сообщений видит агент (было 25 → 12)
LLM_TIMEOUT = 60        # таймаут запроса к LLM (сек)
LLM_MAX_RETRIES = 3     # макс. количество повторных попыток
LLM_RETRY_DELAY = 2.0   # базовая задержка между retry (сек)
MAX_RESPONSE_CHARS = 250  # жёсткий лимит длины ответа агента

# Память
SHORT_TERM_MEMORY = 15  # краткосрочная память (было 10)
LONG_TERM_MEMORY = 50   # долгосрочная память (важные моменты)
MEMORY_DB_PATH = "data/agent_memory.json"
COMPRESSION_THRESHOLD = 80  # порог запуска компрессии (было 50 — слишком часто)
SUMMARY_LENGTH = 7  # было 5 — сохраняем больше ключевых моментов
IMPORTANCE_DECAY_FACTOR = 0.97  # temporal decay: importance *= DECAY ^ (current_tick - memory_tick)
EPISODE_GAP_TICKS = 3  # максимальный разрыв тиков внутри одного эпизода

# Темы и креативность
TOPIC_CHANGE_THRESHOLD = 15  # было 10 — темы живут дольше
CREATIVITY_BOOST = 0.2       # шанс предложить новую тему (было 0.3)
TOPIC_DB_PATH = "data/topics.json"
REPETITION_SIMILARITY_THRESHOLD = 0.5

# Сценарии и события
SCENARIO_EVENT_INTERVAL = 15
SCENARIO_DB_PATH = "data/scenario.json"

# [FIX #6] Фокус на событиях — сколько тиков событие остаётся актуальным
EVENT_FOCUS_DURATION = 7  # тиков фокуса на событии

# [FIX #7] Система отношений
RELATIONSHIP_CHANGE_RATE = 0.05  # на сколько меняются отношения за взаимодействие

# [FIX v3] Антиповтор — лимит подряд похожих реплик от одного агента
REPETITION_CONSECUTIVE_LIMIT = 2  # после стольких похожих — принудительная смена стиля

# [FIX v3] Система фаз диалога — прогресс темы
PHASE_TICKS = {
    "discuss": 8,     # обсуждение — первые 8 тиков темы
    "decide": 6,      # принятие решений — следующие 6
    "act": 4,         # действия — 4 тика
    "conclude": 3,    # подведение итогов — 3 тика
}
PHASE_ORDER = ["discuss", "decide", "act", "conclude"]
PHASE_LABELS = {
    "discuss": "💬 Обсуждение",
    "decide": "🤔 Решение",
    "act": "⚡ Действие",
    "conclude": "✅ Итог",
}

# [FIX v3] Принудительная реакция на событие — первые N тиков ВСЕ агенты обязаны отреагировать
EVENT_FORCED_REACTION_TICKS = 3  # первые 3 тика после события — реакция обязательна


# ── Реестр агентов (id ↔ name маппинг) ─────────────────────────

class AgentRegistry:
    """Единый реестр агентов: id → display_name.
    Все внутренние структуры (relationships, memory, conversation) используют agent_id.
    display_name нужен только для UI и промптов LLM.
    При переименовании обновляется ТОЛЬКО здесь — вся история остаётся целой."""

    def __init__(self):
        self._id_to_name: dict[str, str] = {}      # agent_id → текущее display_name
        self._name_to_id: dict[str, str] = {}       # текущее display_name.lower() → agent_id
        self._name_history: dict[str, list[str]] = {}  # agent_id → [старые имена]

    def register(self, agent_id: str, display_name: str):
        """Зарегистрировать нового агента."""
        self._id_to_name[agent_id] = display_name
        self._name_to_id[display_name.lower()] = agent_id
        self._name_history.setdefault(agent_id, []).append(display_name)

    def rename(self, agent_id: str, new_name: str, agents: list = None) -> str:
        """Переименовать агента. Возвращает старое имя.
        Если передан список agents — принудительно консолидирует память
        всех агентов перед сменой имени, чтобы избежать путаницы."""
        old_name = self._id_to_name.get(agent_id, "")

        # Принудительная группировка памяти ПЕРЕД сменой имени
        if old_name and agents:
            for agent in agents:
                if hasattr(agent, 'memory_system'):
                    agent.memory_system.consolidate_before_rename(old_name, new_name)

        if old_name:
            self._name_to_id.pop(old_name.lower(), None)
        self._id_to_name[agent_id] = new_name
        self._name_to_id[new_name.lower()] = agent_id
        self._name_history.setdefault(agent_id, []).append(new_name)
        return old_name

    def get_name(self, agent_id: str) -> str:
        """Получить текущее display_name по id."""
        return self._id_to_name.get(agent_id, agent_id)

    def get_id(self, name: str) -> Optional[str]:
        """Получить agent_id по текущему имени (регистронезависимо)."""
        return self._name_to_id.get(name.lower())

    def get_id_fuzzy(self, name: str) -> Optional[str]:
        """Нечёткий поиск id по началу имени."""
        name_lower = name.lower()
        # Точное совпадение
        if name_lower in self._name_to_id:
            return self._name_to_id[name_lower]
        # Поиск по началу
        for display_lower, aid in self._name_to_id.items():
            if display_lower.startswith(name_lower):
                return aid
        # Поиск по старым именам
        for aid, history in self._name_history.items():
            for old_name in history:
                if old_name.lower().startswith(name_lower):
                    return aid
        return None

    def get_all_ids(self) -> list[str]:
        """Все зарегистрированные agent_id."""
        return list(self._id_to_name.keys())

    def get_all_names(self) -> list[str]:
        """Все текущие display_name."""
        return list(self._id_to_name.values())

    def get_name_history(self, agent_id: str) -> list[str]:
        """История имён агента."""
        return self._name_history.get(agent_id, [])

    def is_known_name(self, name: str) -> bool:
        """Проверяет, является ли имя текущим или бывшим именем какого-то агента."""
        if name.lower() in self._name_to_id:
            return True
        for history in self._name_history.values():
            if any(n.lower() == name.lower() for n in history):
                return True
        return False


# Глобальный реестр — создаётся один раз, используется везде
agent_registry = AgentRegistry()


# ── LLM-клиент ────────────────────────────────────────────────

import httpx

http_client = httpx.Client(
    timeout=httpx.Timeout(LLM_TIMEOUT, connect=10.0),
    proxy=None,
)

client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    timeout=LLM_TIMEOUT,
    max_retries=0,
    http_client=http_client,
)


def llm_chat(messages: list[dict], temperature: float = 0.8) -> Optional[str]:
    """Отправить запрос к LLM с retry и таймаутом. Возвращает None при неудаче."""
    if messages and messages[0]["role"] == "system":
        if "/no_think" not in messages[0]["content"]:
            messages = messages.copy()
            messages[0] = messages[0].copy()
            messages[0]["content"] = "/no_think\n" + messages[0]["content"]

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=150,
            )
            return resp.choices[0].message.content.strip()

        except APITimeoutError:
            wait = LLM_RETRY_DELAY * attempt
            print(f"{Fore.RED}  ⏱ LLM таймаут (попытка {attempt}/{LLM_MAX_RETRIES}), жду {wait:.0f}с...{Style.RESET_ALL}")
            time.sleep(wait)

        except APIConnectionError as e:
            wait = LLM_RETRY_DELAY * attempt
            print(f"{Fore.RED}  ⚡ LLM недоступен (попытка {attempt}/{LLM_MAX_RETRIES}): {e}{Style.RESET_ALL}")
            time.sleep(wait)

        except APIStatusError as e:
            if e.status_code == 429:
                wait = LLM_RETRY_DELAY * attempt * 2
                print(f"{Fore.RED}  🔥 LLM перегружен (429), жду {wait:.0f}с...{Style.RESET_ALL}")
                time.sleep(wait)
            elif e.status_code >= 500:
                wait = LLM_RETRY_DELAY * attempt
                print(f"{Fore.RED}  💥 LLM ошибка сервера ({e.status_code}), жду {wait:.0f}с...{Style.RESET_ALL}")
                time.sleep(wait)
            else:
                print(f"{Fore.RED}  ❌ LLM ошибка {e.status_code}: {e.message}{Style.RESET_ALL}")
                return None

        except Exception as e:
            print(f"{Fore.RED}  ❌ Неожиданная ошибка: {e}{Style.RESET_ALL}")
            return None

    print(f"{Fore.RED}  ❌ LLM не ответил после {LLM_MAX_RETRIES} попыток, пропускаю ход.{Style.RESET_ALL}")
    return None


# ── Модели данных (Big Five & Personality) ───────────────────

class PersonalityType(Enum):
    ALTRUIST = "Альтруист (добрый)"
    MACHIAVELLIAN = "Макиавеллист (злой)"
    REBEL = "Бунтарь (непредсказуемый)"
    STOIC = "Стоик (хладнокровный)"
    INDIVIDUAL = "Индивидуальный (пользовательский)"


@dataclass
class BigFiveTraits:
    openness: int = 50
    conscientiousness: int = 50
    extraversion: int = 50
    agreeableness: int = 50
    neuroticism: int = 50

    def to_description(self) -> str:
        traits = []
        if self.openness > 70:
            traits.append("очень открыт новому опыту и идеям")
        elif self.openness < 30:
            traits.append("предпочитает проверенные методы")
        if self.conscientiousness > 70:
            traits.append("организован и дисциплинирован")
        elif self.conscientiousness < 30:
            traits.append("спонтанен и гибок")
        if self.extraversion > 70:
            traits.append("энергичен и общителен")
        elif self.extraversion < 30:
            traits.append("сдержан и задумчив")
        if self.agreeableness > 70:
            traits.append("дружелюбен и готов помочь")
        elif self.agreeableness < 15:
            traits.append("агрессивен, враждебен, постоянно ищет конфликт и ругается со всеми")
        elif self.agreeableness < 30:
            traits.append("критичен и независим")
        if self.neuroticism > 80:
            traits.append("крайне раздражителен, вспыльчив, легко выходит из себя")
        elif self.neuroticism > 70:
            traits.append("эмоционален и чувствителен")
        elif self.neuroticism < 30:
            traits.append("спокоен и стабилен")
        return ", ".join(traits) if traits else "сбалансированная личность"

    @staticmethod
    def from_personality_type(ptype: 'PersonalityType') -> 'BigFiveTraits':
        profiles = {
            PersonalityType.ALTRUIST: BigFiveTraits(
                openness=70, conscientiousness=60, extraversion=65,
                agreeableness=85, neuroticism=35
            ),
            PersonalityType.MACHIAVELLIAN: BigFiveTraits(
                openness=55, conscientiousness=70, extraversion=75,
                agreeableness=10, neuroticism=85
            ),
            PersonalityType.REBEL: BigFiveTraits(
                openness=85, conscientiousness=30, extraversion=60,
                agreeableness=40, neuroticism=65
            ),
            PersonalityType.STOIC: BigFiveTraits(
                openness=45, conscientiousness=75, extraversion=30,
                agreeableness=50, neuroticism=20
            ),
            PersonalityType.INDIVIDUAL: BigFiveTraits(),
        }
        return profiles.get(ptype, BigFiveTraits())


# ── Система классов (рас) агентов ────────────────────────────

class RaceType(Enum):
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    ORC = "orc"
    GOBLIN = "goblin"


@dataclass
class RaceModifiers:
    """Модификаторы расы для характеристик агента."""
    # Модификаторы Big Five (прибавляются к базовым значениям)
    openness: int = 0
    conscientiousness: int = 0
    extraversion: int = 0
    agreeableness: int = 0
    neuroticism: int = 0

    # Множители эмоций (применяются к дельтам настроения)
    happiness_mult: float = 1.0
    energy_mult: float = 1.0
    stress_mult: float = 1.0
    anger_mult: float = 1.0
    fear_mult: float = 1.0

    # Бонусы к навыкам (множители для действий)
    repair_bonus: float = 0.0     # ремонт, создание
    combat_bonus: float = 0.0     # бой, конфликты
    diplomacy_bonus: float = 0.0  # дипломатия, переговоры
    detection_bonus: float = 0.0  # обнаружение опасности

    # Особые способности
    can_betray: bool = False       # может предать группу при страхе
    flee_threshold: float = 1.0    # порог страха для бегства (1.0 = никогда)
    stubborn: bool = False         # упрямство (-50% к изменению мнения)


@dataclass
class Race:
    """Класс (раса) агента с модификаторами и отношениями."""
    race_type: RaceType
    name_ru: str
    emoji: str
    description: str
    modifiers: RaceModifiers
    # Модификаторы начальных отношений к другим расам {RaceType: float}
    racial_relations: dict


# ── Определение всех рас ──────────────────────────────────────

RACES: dict[RaceType, Race] = {
    RaceType.HUMAN: Race(
        race_type=RaceType.HUMAN,
        name_ru="Человек",
        emoji="👤",
        description="Универсальный, адаптивный, дипломатичный",
        modifiers=RaceModifiers(
            diplomacy_bonus=0.20,  # +20% к дипломатии
        ),
        racial_relations={
            RaceType.HUMAN: 0.10,
            RaceType.ELF: 0.05,
            RaceType.DWARF: 0.05,
            RaceType.ORC: 0.00,
            RaceType.GOBLIN: 0.00,
        }
    ),
    RaceType.ELF: Race(
        race_type=RaceType.ELF,
        name_ru="Эльф",
        emoji="🧝",
        description="Долгожитель, мудрый, высокомерный",
        modifiers=RaceModifiers(
            openness=15,       # любопытный
            neuroticism=-15,   # спокойный
            energy_mult=0.80,  # размеренный
            stress_mult=0.50,  # устойчивый к стрессу
            detection_bonus=0.10,  # природная связь
        ),
        racial_relations={
            RaceType.HUMAN: 0.05,
            RaceType.ELF: 0.15,
            RaceType.DWARF: -0.20,
            RaceType.ORC: -0.30,
            RaceType.GOBLIN: -0.15,
        }
    ),
    RaceType.DWARF: Race(
        race_type=RaceType.DWARF,
        name_ru="Дварф",
        emoji="⚒️",
        description="Упрямый, трудолюбивый, мастеровой",
        modifiers=RaceModifiers(
            conscientiousness=20,  # трудолюбие
            agreeableness=-10,     # упрямство
            energy_mult=1.10,      # выносливость
            anger_mult=1.30,       # вспыльчивость
            repair_bonus=0.30,     # мастерство
            stubborn=True,         # упрямый
        ),
        racial_relations={
            RaceType.HUMAN: 0.10,
            RaceType.ELF: -0.20,
            RaceType.DWARF: 0.20,
            RaceType.ORC: -0.10,
            RaceType.GOBLIN: -0.25,
        }
    ),
    RaceType.ORC: Race(
        race_type=RaceType.ORC,
        name_ru="Орк",
        emoji="💪",
        description="Агрессивный, прямолинейный, уважает силу",
        modifiers=RaceModifiers(
            extraversion=20,      # доминирование
            agreeableness=-20,    # агрессия
            anger_mult=1.50,      # злость растёт быстрее
            fear_mult=0.50,       # бесстрашие
            combat_bonus=0.40,    # боевой дух
        ),
        racial_relations={
            RaceType.HUMAN: 0.05,
            RaceType.ELF: -0.15,
            RaceType.DWARF: 0.05,
            RaceType.ORC: 0.25,
            RaceType.GOBLIN: -0.30,
        }
    ),
    RaceType.GOBLIN: Race(
        race_type=RaceType.GOBLIN,
        name_ru="Гоблин",
        emoji="👺",
        description="Хитрый, трусливый, коварный",
        modifiers=RaceModifiers(
            agreeableness=-25,    # эгоизм
            neuroticism=30,       # трусость
            energy_mult=1.20,     # суетливость
            fear_mult=1.80,       # страх усиливается
            can_betray=True,      # может предать
            flee_threshold=0.6,   # убегает при страхе > 0.6
        ),
        racial_relations={
            RaceType.HUMAN: -0.10,
            RaceType.ELF: -0.10,
            RaceType.DWARF: -0.10,
            RaceType.ORC: -0.10,
            RaceType.GOBLIN: 0.10,
        }
    ),
}

# Все расы → Гоблины: дополнительное недоверие (-0.15)
GOBLIN_DISTRUST = -0.15


# ── Система настроения (Mood) ─────────────────────────────────

MOOD_DECAY_RATE = 0.04        # скорость возврата к baseline за тик (было 0.08 — слишком быстро!)
MOOD_EVENT_IMPACT = 0.30      # сила влияния события на настроение (было 0.25 — слабовато)
MOOD_INTERACTION_IMPACT = 0.15 # сила влияния взаимодействия на настроение (было 0.12)

# Эмодзи для настроений
MOOD_EMOJIS = {
    "радость": "😊", "воодушевление": "🤩", "спокойствие": "😌",
    "тревога": "😰", "злость": "😤", "грусть": "😢",
    "страх": "😨", "раздражение": "😒", "усталость": "😴",
    "нейтрально": "😐", "интерес": "🤔", "решимость": "💪",
}

# Ключевые слова событий → какие эмоции они вызывают
EVENT_MOOD_TRIGGERS = {
    # Опасность → страх + стресс
    'danger': {
        'keywords': ['ливень', 'шторм', 'ветер', 'прилив', 'смывает', 'змея', 'хищник',
                     'зомби', 'метеорит', 'кислород', 'падает', 'опасн', 'ломается',
                     'выламать', 'бандит', 'драка', 'грохот', 'вспышка'],
        'effects': {'happiness': -0.15, 'energy': 0.1, 'stress': 0.25, 'anger': 0.05, 'fear': 0.3},
    },
    # Позитив → радость + энергия
    'positive': {
        'keywords': ['нашли', 'нашёл', 'консервы', 'запасы', 'сигнал', 'корабль',
                     'спасатели', 'закат', 'красив', 'отдохн', 'поговорить', 'бард',
                     'эль', 'жаркое', 'победа', 'починили', 'работает'],
        'effects': {'happiness': 0.25, 'energy': 0.15, 'stress': -0.15, 'anger': -0.1, 'fear': -0.1},
    },
    # Ресурсы → интерес + снижение стресса
    'resources': {
        'keywords': ['еда', 'кокос', 'краб', 'фрукт', 'вода', 'оружие', 'рация',
                     'обломки', 'ключ', 'карта', 'сокровищ', 'склад'],
        'effects': {'happiness': 0.1, 'energy': 0.1, 'stress': -0.1, 'anger': -0.05, 'fear': -0.05},
    },
    # Загадка → интерес
    'mystery': {
        'keywords': ['странн', 'неопознанн', 'загадоч', 'незнакомец', 'гадалк',
                     'предсказ', 'сны', 'объект', 'радар', 'компьютер', 'данные'],
        'effects': {'happiness': 0.0, 'energy': 0.1, 'stress': 0.1, 'anger': 0.0, 'fear': 0.1},
    },
    # Потеря → грусть
    'loss': {
        'keywords': ['кончаются', 'заканчива', 'потерял', 'разруш', 'сломал',
                     'пролетел мимо', 'далеко', 'не смог', 'без света', 'батарей'],
        'effects': {'happiness': -0.25, 'energy': -0.15, 'stress': 0.2, 'anger': 0.1, 'fear': 0.1},
    },
    # Болезнь / заражение → СИЛЬНЫЙ страх + стресс (отдельная категория!)
    'sickness': {
        'keywords': ['заболел', 'заболела', 'укус', 'укусил', 'инфекция', 'вирус',
                     'заражен', 'заражён', 'температур', 'лихорад', 'симптом',
                     'простуда', 'кашля', 'отравлен', 'яд', 'ядовит'],
        'effects': {'happiness': -0.3, 'energy': -0.2, 'stress': 0.35, 'anger': 0.05, 'fear': 0.35},
    },
}


@dataclass
class AgentMood:
    """Эмоциональное состояние агента.
    Каждый параметр от -1.0 до 1.0 (кроме energy/stress: 0.0 до 1.0).
    Настроение влияет на стиль речи, желание говорить и взаимодействия."""

    happiness: float = 0.0    # -1.0 (грусть) ... 1.0 (радость)
    energy: float = 0.5       # 0.0 (усталость) ... 1.0 (энергия)
    stress: float = 0.2       # 0.0 (спокойствие) ... 1.0 (стресс)
    anger: float = 0.0        # 0.0 (спокойствие) ... 1.0 (ярость)
    fear: float = 0.0         # 0.0 (бесстрашие) ... 1.0 (ужас)

    # Baseline значения — к ним настроение стремится со временем
    _baseline_happiness: float = 0.0
    _baseline_energy: float = 0.5
    _baseline_stress: float = 0.2
    _baseline_anger: float = 0.0
    _baseline_fear: float = 0.0

    @staticmethod
    def from_personality(ptype: 'PersonalityType', big_five: 'BigFiveTraits') -> 'AgentMood':
        """Создать начальное настроение на основе Big Five + типа личности.

        Корреляции Big Five → baseline mood:
        ───────────────────────────────────────────────────────────
        Openness (O)          → +happiness, +energy (любопытство = энергия)
        Conscientiousness (C) → −stress (организованность успокаивает)
        Extraversion (E)      → +happiness, +energy (активность)
        Agreeableness (A)     → +happiness, −anger (миролюбие)
        Neuroticism (N)       → +stress, +anger, +fear, −happiness
        ───────────────────────────────────────────────────────────
        """
        # Нормализуем Big Five в [0..1]
        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        # ── Baseline вычисляется из Big Five ──
        # happiness: экстраверсия и доброжелательность повышают, нейротизм понижает
        base_happiness = (e * 0.25 + a * 0.15 + o * 0.1) - (n * 0.3) 
        # energy: экстраверсия и открытость дают энергию
        base_energy = 0.35 + e * 0.25 + o * 0.1 + c * 0.05
        # stress: нейротизм повышает, организованность и доброжелательность снижают
        base_stress = n * 0.4 - c * 0.15 - a * 0.05
        # anger: нейротизм повышает, доброжелательность снижает (главный демпфер)
        base_anger = n * 0.3 - a * 0.35
        # fear: нейротизм повышает, экстраверсия и открытость снижают
        base_fear = n * 0.2 - e * 0.1 - o * 0.05

        # Клэмпим baseline
        base_happiness = max(-0.8, min(0.8, base_happiness))
        base_energy = max(0.15, min(0.9, base_energy))
        base_stress = max(0.0, min(0.7, base_stress))
        base_anger = max(0.0, min(0.7, base_anger))
        base_fear = max(0.0, min(0.5, base_fear))

        mood = AgentMood(
            happiness=base_happiness, energy=base_energy,
            stress=base_stress, anger=base_anger, fear=base_fear,
            _baseline_happiness=base_happiness, _baseline_energy=base_energy,
            _baseline_stress=base_stress, _baseline_anger=base_anger,
            _baseline_fear=base_fear,
        )
        mood._clamp()
        return mood

    def _clamp(self):
        """Ограничить значения допустимыми диапазонами."""
        self.happiness = max(-1.0, min(1.0, self.happiness))
        self.energy = max(0.0, min(1.0, self.energy))
        self.stress = max(0.0, min(1.0, self.stress))
        self.anger = max(0.0, min(1.0, self.anger))
        self.fear = max(0.0, min(1.0, self.fear))

    def get_dominant_emotion(self) -> str:
        """Определить доминирующую эмоцию."""
        emotions = {
            'радость': self.happiness,
            'грусть': -self.happiness if self.happiness < -0.2 else -1,
            'злость': self.anger,
            'страх': self.fear,
            'тревога': self.stress,
            'усталость': 1.0 - self.energy if self.energy < 0.25 else -1,
            'воодушевление': (self.happiness + self.energy) / 2 if self.happiness > 0.3 and self.energy > 0.6 else -1,
            'раздражение': (self.anger + self.stress) / 2 if self.anger > 0.2 and self.stress > 0.3 else -1,
            'решимость': self.energy if self.energy > 0.6 and self.stress < 0.3 and self.fear < 0.2 else -1,
            'интерес': 0.3 if abs(self.happiness) < 0.2 and self.energy > 0.4 else -1,
        }
        dominant = max(emotions, key=emotions.get)
        if emotions[dominant] < 0.1:
            return 'нейтрально'
        return dominant

    def get_emoji(self) -> str:
        """Получить эмодзи доминирующей эмоции."""
        return MOOD_EMOJIS.get(self.get_dominant_emotion(), '😐')

    def to_description(self) -> str:
        """Текстовое описание настроения для промпта — ЖЁСТКИЕ инструкции для LLM."""
        dominant = self.get_dominant_emotion()
        emoji = self.get_emoji()
        parts = [f"{emoji} Доминирующая эмоция: {dominant}"]

        # ── Happiness ──
        if self.happiness > 0.4:
            parts.append("ты в ХОРОШЕМ настроении — шути, поддерживай, будь добрее обычного")
        elif self.happiness > 0.15:
            parts.append("настроение неплохое")
        elif self.happiness < -0.4:
            parts.append("ты ПОДАВЛЕН — говори тихо, коротко, грустно. Не шути. Можешь жаловаться")
        elif self.happiness < -0.15:
            parts.append("ты не в духе — раздражителен, пессимистичен")

        # ── Fear vs Anger — КЛЮЧЕВАЯ МЕХАНИКА ──
        # Страх ПОДАВЛЯЕТ агрессию — напуганный человек не ругается, а паникует
        if self.fear > 0.5:
            parts.append(
                "ты НАПУГАН! ПАНИКА! Говори сбивчиво, торопливо. "
                "Проси о помощи. Предлагай спрятаться или убежать. "
                "НЕ РУГАЙСЯ — тебе не до этого, ты боишься!"
            )
        elif self.fear > 0.25:
            parts.append(
                "ты встревожен и напуган — говори осторожно, "
                "предупреждай об опасности, будь настороже. "
                "Агрессия СНИЖЕНА — страх подавляет злость"
            )

        if self.fear > 0.3 and self.anger > 0.3:
            # Конфликт страха и злости — страх побеждает
            parts.append(
                "СТРАХ сильнее ЗЛОСТИ — ты скорее нервничаешь, "
                "чем ругаешься. Можешь огрызнуться от страха, "
                "но НЕ оскорблять и НЕ скандалить"
            )
        elif self.anger > 0.6 and self.fear < 0.2:
            parts.append("ты В ЯРОСТИ — говори агрессивно, резко, можешь сорваться")
        elif self.anger > 0.35 and self.fear < 0.2:
            parts.append("ты раздражён — грубишь, споришь")
        elif self.anger > 0.15 and self.fear < 0.15:
            parts.append("ты слегка раздражён")

        # ── Stress ──
        if self.stress > 0.7:
            parts.append("ты под СИЛЬНЫМ стрессом — нервничаешь, суетишься, можешь сорваться")
        elif self.stress > 0.4:
            parts.append("ты напряжён — говоришь быстрее, нетерпеливо")

        # ── Energy ──
        if self.energy < 0.2:
            parts.append("ты УСТАЛ — говоришь мало, вяло, хочешь отдохнуть")
        elif self.energy < 0.35:
            parts.append("ты утомлён — не хватает сил на длинные речи")
        elif self.energy > 0.8:
            parts.append("ты полон энергии — активен и деятелен")

        return ". ".join(parts)

    def apply_event(self, event_text: str, personality_type: 'PersonalityType',
                    big_five: 'BigFiveTraits' = None, race_mods: 'RaceModifiers' = None):
        """Обновить настроение в ответ на событие.

        Корреляции Big Five → реакция на событие:
        ───────────────────────────────────────────────────────────
        Neuroticism (N)       → ×sensitivity: усиливает ВСЕ негативные эффекты
        Openness (O)          → ×curiosity: опасность → интерес вместо страха;
                                 загадки волнуют сильнее
        Conscientiousness (C) → ×composure: снижает стресс от хаоса,
                                 потери ресурсов бьют сильнее
        Extraversion (E)      → ×resilience: быстрее воодушевляется от позитива,
                                 меньше теряет энергию от негатива
        Agreeableness (A)     → ×empathy: чужие проблемы → больше стресс,
                                 позитив ко всем → больше радость, anger гасится
        ───────────────────────────────────────────────────────────
        """
        if big_five is None:
            big_five = BigFiveTraits(neuroticism=50)

        event_lower = event_text.lower()

        # Нормализуем Big Five в [0..1]
        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        # ── Вычисляем модификаторы из Big Five ──
        # Общая чувствительность: нейротизм усиливает, сознательность стабилизирует
        sensitivity = 0.6 + n * 0.6 - c * 0.15  # 0.45 .. 1.2
        sensitivity = max(0.4, min(1.3, sensitivity))

        # Любопытство: openness конвертирует страх/стресс → интерес
        curiosity = o * 0.4  # 0..0.4

        # Эмоциональная устойчивость: экстраверсия + сознательность
        resilience = e * 0.25 + c * 0.15  # 0..0.4

        # Эмпатия: agreeableness усиливает социальные реакции
        empathy = a * 0.3  # 0..0.3

        # Гашение злости: agreeableness
        anger_dampening = a * 0.5  # 0..0.5

        effects_applied = False
        matched_category = None
        for category, data in EVENT_MOOD_TRIGGERS.items():
            keywords = data['keywords']
            effects = data['effects']
            if any(kw in event_lower for kw in keywords):
                impact = MOOD_EVENT_IMPACT * sensitivity

                d_happiness = effects['happiness'] * impact
                d_energy = effects['energy'] * impact
                d_stress = effects['stress'] * impact
                d_anger = effects['anger'] * impact
                d_fear = effects['fear'] * impact

                # ── Big Five корректируют дельты ──

                # Openness: превращает часть страха и стресса в интерес/энергию
                if d_fear > 0:
                    converted = d_fear * curiosity
                    d_fear -= converted
                    d_energy += converted * 0.5
                    d_happiness += converted * 0.3
                if d_stress > 0 and category == 'mystery':
                    d_stress *= (1.0 - curiosity)  # загадки меньше стрессят открытых
                    d_energy += curiosity * 0.15    # но дают энергию

                # Conscientiousness: потеря ресурсов бьёт сильнее (порядок нарушен!)
                if category == 'loss':
                    d_happiness -= c * 0.1   # организованный переживает потерю
                    d_stress += c * 0.08     # стресс от хаоса
                elif category == 'danger':
                    d_stress *= (1.0 - c * 0.3)  # но сохраняет голову в опасности

                # Extraversion: позитив сильнее качает вверх, негатив меньше вниз
                if d_happiness > 0:
                    d_happiness *= (1.0 + resilience)  # позитив усиливается
                elif d_happiness < 0:
                    d_happiness *= (1.0 - resilience * 0.5)  # негатив смягчается
                if d_energy < 0:
                    d_energy *= (1.0 - e * 0.3)  # экстраверт не теряет энергию легко

                # Agreeableness: гасит злость, усиливает позитив от хороших событий
                if d_anger > 0:
                    d_anger *= (1.0 - anger_dampening)  # высокий A → меньше злости
                if category == 'positive':
                    d_happiness += empathy * 0.15  # радуется за общее благо
                    # [FIX v4] Позитив НЕ обнуляет страх/стресс полностью — только ослабляет
                    if d_stress < 0:
                        d_stress *= 0.6  # позитив снимает только 60% стресса
                    if d_fear < 0:
                        d_fear *= 0.5    # позитив снимает только 50% страха
                elif category in ('danger', 'loss', 'sickness'):
                    d_stress += empathy * 0.1  # переживает за группу

                # Neuroticism: усиливает негативные дельты дополнительно
                if d_happiness < 0:
                    d_happiness *= (1.0 + n * 0.3)
                if d_stress > 0:
                    d_stress *= (1.0 + n * 0.2)

                # Расовые множители эмоций
                if race_mods:
                    d_happiness *= race_mods.happiness_mult
                    d_energy *= race_mods.energy_mult
                    d_stress *= race_mods.stress_mult
                    d_anger *= race_mods.anger_mult
                    d_fear *= race_mods.fear_mult

                self.happiness += d_happiness
                self.energy += d_energy
                self.stress += d_stress
                self.anger += d_anger
                self.fear += d_fear
                effects_applied = True
                matched_category = category
                break

        if not effects_applied:
            # Неизвестное событие — реакция зависит от характера
            self.stress += 0.05 * sensitivity
            self.energy += 0.03 + o * 0.04  # открытые получают энергию от нового

        self._clamp()

    def apply_interaction(self, sentiment_delta: float, personality_type: 'PersonalityType',
                          big_five: 'BigFiveTraits' = None):
        """Обновить настроение от взаимодействия с другим агентом.
        sentiment_delta > 0 = позитивное взаимодействие, < 0 = негативное.

        Корреляции Big Five → реакция на взаимодействия:
        ───────────────────────────────────────────────────────────
        Neuroticism (N)       → усиливает ВСЁ: и радость, и боль от слов
        Extraversion (E)      → позитив качает сильнее вверх (социальная подзарядка),
                                 негатив меньше ранит (толстая кожа)
        Agreeableness (A)     → позитив → больше радость, негатив → больше грусть
                                 (а не злость!), anger гасится
        Conscientiousness (C) → стабилизирует stress от конфликтов
        Openness (O)          → любой контакт даёт немного энергии
        ───────────────────────────────────────────────────────────
        """
        if big_five is None:
            big_five = BigFiveTraits(neuroticism=50)

        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        # Общая чувствительность к социальным сигналам
        sensitivity = 0.6 + n * 0.5 + e * 0.15  # экстраверты тоже чувствительны к социальному
        sensitivity = max(0.5, min(1.4, sensitivity))
        impact = MOOD_INTERACTION_IMPACT * sensitivity

        if sentiment_delta > 0:
            # ── Позитивное взаимодействие ──
            pos = sentiment_delta

            # Экстраверт получает больше радости от позитивного контакта
            happiness_boost = pos * impact * (2.0 + e * 2.0)  # E=0: ×2, E=1: ×4
            self.happiness += happiness_boost

            # Agreeableness усиливает радость от доброты
            self.happiness += pos * impact * a * 1.5

            # Anger снижается: agreeableness помогает отпустить обиды
            anger_reduction = pos * impact * (1.5 + a * 1.5)
            self.anger = max(0, self.anger - anger_reduction)

            # Стресс снижается, организованность помогает
            stress_reduction = pos * impact * (0.8 + c * 0.5)
            self.stress = max(0, self.stress - stress_reduction)

            # Энергия от общения (экстраверты подзаряжаются от людей)
            self.energy += pos * impact * (0.5 + e * 1.0)

            # Страх снижается от поддержки
            self.fear = max(0, self.fear - pos * impact * 0.5)

        else:
            # ── Негативное взаимодействие ──
            neg = abs(sentiment_delta)

            # Happiness падает: agreeableness → больше грусть, меньше злость
            happiness_loss = neg * impact * (1.5 + a * 1.0)
            self.happiness -= happiness_loss

            # Anger: низкий agreeableness → злость, высокий → грусть вместо злости
            # Формула: чем ниже A, тем больше anger; чем выше A, тем меньше anger
            anger_gain = neg * impact * (3.0 - a * 2.5)  # A=0: ×3.0, A=1: ×0.5
            anger_gain = max(0, anger_gain)
            self.anger += anger_gain

            # Stress: нейротизм усиливает, сознательность стабилизирует
            stress_gain = neg * impact * (1.5 + n * 1.0 - c * 0.5)
            stress_gain = max(0, stress_gain)
            self.stress += stress_gain

            # Энергия: экстраверт теряет меньше (привык к конфликтам)
            energy_loss = neg * impact * (0.5 - e * 0.3)
            energy_loss = max(0, energy_loss)
            self.energy -= energy_loss

        # Openness: любой контакт — опыт, даёт немного энергии
        self.energy += o * 0.02

        self._clamp()

    def decay_toward_baseline(self, big_five: 'BigFiveTraits' = None):
        """Естественное затухание — настроение стремится к baseline.

        Скорость decay зависит от Big Five:
        ───────────────────────────────────────────────────────────
        Neuroticism (N)  → замедляет decay негатива (долго злится, долго боится)
        Conscientiousness (C) → ускоряет decay stress (быстро берёт себя в руки)
        Extraversion (E) → ускоряет decay happiness к базе (быстро отходит)
        Agreeableness (A) → ускоряет decay anger (быстро прощает)
        Openness (O)     → ускоряет decay fear (быстро перестаёт бояться)
        ───────────────────────────────────────────────────────────
        """
        if big_five is None:
            big_five = BigFiveTraits()

        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        base_rate = MOOD_DECAY_RATE

        # Happiness decay: экстраверты быстрее возвращаются в норму
        h_rate = base_rate * (1.0 + e * 0.3)
        self.happiness += (self._baseline_happiness - self.happiness) * h_rate

        # Energy decay: стабильная, слабо зависит от характера
        e_rate = base_rate * (1.0 + c * 0.15)
        self.energy += (self._baseline_energy - self.energy) * e_rate

        # [FIX v4] Чем выше негатив — тем МЕДЛЕННЕЕ он уходит (инерция)
        # stress=0.8 → множитель 0.4, stress=0.2 → множитель 0.9
        def inertia(current: float, baseline: float) -> float:
            excess = max(0, current - baseline)
            return 1.0 - excess * 0.7  # 0.3..1.0

        # Stress decay: организованность помогает успокоиться,
        # нейротизм мешает (стресс задерживается)
        s_rate = base_rate * (1.0 + c * 0.4 - n * 0.3)
        s_rate *= inertia(self.stress, self._baseline_stress)
        s_rate = max(0.01, s_rate)
        self.stress += (self._baseline_stress - self.stress) * s_rate

        # Anger decay: agreeableness помогает отпустить злость,
        # нейротизм задерживает (долго злится)
        a_rate = base_rate * (1.0 + a * 0.5 - n * 0.3)
        a_rate *= inertia(self.anger, self._baseline_anger)
        a_rate = max(0.01, a_rate)
        self.anger += (self._baseline_anger - self.anger) * a_rate

        # Fear decay: openness помогает перестать бояться (рационализация),
        # нейротизм замедляет
        f_rate = base_rate * (1.0 + o * 0.4 - n * 0.25)
        f_rate *= inertia(self.fear, self._baseline_fear)
        f_rate = max(0.01, f_rate)
        self.fear += (self._baseline_fear - self.fear) * f_rate

        # [FIX v4] Happiness: позитив тоже уходит медленнее, если счастье ниже baseline
        if self.happiness < self._baseline_happiness:
            h_penalty = (self._baseline_happiness - self.happiness) * 0.5
            self.happiness -= h_penalty * 0.02  # еле-еле подтягивается обратно

        self._clamp()

    def apply_speaking(self, big_five: 'BigFiveTraits' = None):
        """Корректировка после высказывания.

        Big Five корреляции:
        - Extraversion: говорить = подзарядка (меньше траты, даже +energy)
        - Introvert (low E): говорить = расход энергии
        - Neuroticism: говорить снижает стресс сильнее (выпуск пара)
        - Agreeableness: говорить снижает anger (миролюбивые успокаиваются)
        """
        if big_five is None:
            big_five = BigFiveTraits()

        e = big_five.extraversion / 100.0
        n = big_five.neuroticism / 100.0
        a = big_five.agreeableness / 100.0

        # Энергия: интроверты тратят больше, экстраверты могут даже получать
        energy_cost = 0.06 - e * 0.08  # E=0: −0.06, E=0.5: −0.02, E=1: +0.02
        self.energy -= energy_cost

        # Стресс: говорить = выпуск пара, нейротики получают больше облегчения
        stress_relief = 0.01 + n * 0.03  # N=0: 0.01, N=1: 0.04
        self.stress = max(0, self.stress - stress_relief)

        # Anger: доброжелательные успокаиваются от разговора
        anger_relief = a * 0.02
        self.anger = max(0, self.anger - anger_relief)

        self._clamp()

    def get_talkativeness_modifier(self, big_five: 'BigFiveTraits' = None) -> float:
        """Модификатор желания говорить на основе настроения + Big Five.
        Возвращает множитель (0.4 .. 1.6).

        Экстраверты: радость/злость → говорят НАМНОГО больше.
        Интроверты: грусть/усталость → замолкают сильнее.
        Нейротики: стресс → нервная болтовня.
        Agreeableness: конфликт → замолкают (не хотят ругаться).
        """
        if big_five is None:
            big_five = BigFiveTraits()

        e = big_five.extraversion / 100.0
        n = big_five.neuroticism / 100.0
        a = big_five.agreeableness / 100.0

        modifier = 1.0

        # ── Happiness ──
        if self.happiness > 0.3:
            modifier += 0.1 + e * 0.15  # экстраверты: радость → болтовня
        elif self.happiness < -0.3:
            modifier -= 0.1 + (1.0 - e) * 0.15  # интроверты: грусть → замолкают

        # ── Anger ──
        if self.anger > 0.4:
            if a < 0.3:
                modifier += 0.25  # агрессивные: злость → скандалят
            else:
                modifier -= 0.1   # миролюбивые: злость → замыкаются

        # ── Fear ──
        if self.fear > 0.5:
            modifier += 0.1 + n * 0.1  # нейротики: страх → паника, болтовня
        elif self.fear > 0.3:
            if e < 0.4:
                modifier -= 0.1  # интроверты: страх → притихают

        # ── Energy ──
        if self.energy < 0.25:
            modifier -= 0.2 + (1.0 - e) * 0.1  # интроверты устают сильнее
        elif self.energy > 0.7:
            modifier += 0.05 + e * 0.1  # экстраверты с энергией = фонтан слов

        # ── Stress ──
        if self.stress > 0.6:
            modifier += 0.05 + n * 0.15  # нейротики: стресс → нервная болтовня

        return max(0.4, min(1.6, modifier))


# ── Система сценариев и событий ──────────────────────────────

@dataclass
class Scenario:
    name: str
    description: str
    context: str
    events: list[str] = field(default_factory=list)
    current_event_index: int = 0


class ScenarioManager:
    SCENARIOS = {
        "desert_island": Scenario(
            name="Необитаемый остров",
            description="Вы оказались на необитаемом острове после крушения самолёта",
            context=(
                "Вы оказались на необитаемом тропическом острове после авиакатастрофы. "
                "Рядом никого нет, только вы трое. Нужно выживать, находить еду и воду, "
                "строить укрытие и искать способ спастись. У каждого свои навыки и страхи."
            ),
            events=[
                "🌧️ Начинается тропический ливень. Нужно срочно найти укрытие!",
                "🔥 Кто-то случайно разжёг костёр. Это может привлечь спасателей... или хищников.",
                "🥥 Найдены кокосы и странные фрукты. Кто рискнёт попробовать?",
                "🦀 На берег выползли крабы. Может, это ужин?",
                "📡 Обнаружены обломки самолёта с рацией. Она повреждена, но может работать.",
                "🌊 Прилив смывает половину лагеря. Придётся всё перестраивать.",
                "🐍 Кто-то заметил змею в кустах. Ядовитая или нет?",
                "⛵ На горизонте показался корабль! Но он слишком далеко...",
                "🌅 Прекрасный закат. Может, стоит отдохнуть и поговорить по душам?",
                "💨 Сильный ветер может означать приближение шторма.",
            ]
        ),
        "space_station": Scenario(
            name="Космическая станция",
            description="Вы в изоляции на космической станции, связь с Землёй потеряна",
            context=(
                "Вы — экипаж космической станции на орбите Марса. Связь с Землёй прервалась три дня назад. "
                "Запасы ограничены, системы жизнеобеспечения работают нестабильно. "
                "Вы одни в космосе, и непонятно, когда придёт помощь."
            ),
            events=[
                "⚠️ Система жизнеобеспечения выдаёт ошибку. Уровень кислорода падает!",
                "🛰️ Поймали слабый сигнал с Земли, но не можем разобрать слова.",
                "🌌 В иллюминаторе видна красная планета. Завораживающее зрелище.",
                "⚡ Солнечная вспышка повредила панели. Энергия на исходе.",
                "🍱 Заканчиваются запасы еды. Придётся перейти на пайки.",
                "🔧 Что-то стучит в отсеке. Метеорит? Или оборудование ломается?",
                "📊 Компьютер показывает странные данные. Возможно, неисправность.",
                "🌠 За окном пролетает метеоритный дождь. Красиво, но опасно.",
                "💤 Кто-то начал видеть странные сны. Изоляция даёт о себе знать.",
                "📡 Радар засёк неопознанный объект. Он приближается...",
            ]
        ),
        "zombie_apocalypse": Scenario(
            name="Зомби-апокалипсис",
            description="Мир захвачен зомби, вы укрылись в заброшенном торговом центре",
            context=(
                "Зомби-апокалипсис. Города разрушены, выживших мало. "
                "Вы втроём заняли оборону в заброшенном торговом центре. "
                "Запасы есть, но долго не протянут. Зомби снаружи, и их становится всё больше."
            ),
            events=[
                "🧟 Слышен грохот — зомби пытаются выломать дверь!",
                "📦 Нашли склад с консервами. Хватит на месяц!",
                "🔫 Обнаружен оружейный магазин, но туда опасно идти.",
                "📻 По радио передают сигнал SOS из соседнего района.",
                "💊 Кто-то заболел. Простуда или... укус зомби?",
                "🔦 Батарейки кончаются. Скоро останемся без света.",
                "🚁 Слышен звук вертолёта! Но он пролетел мимо...",
                "🗝️ Найден ключ от запасного выхода. Может, стоит рискнуть?",
                "🌙 Тихая ночь. Зомби почти не слышно. Время поговорить.",
                "⚠️ Кто-то видел живых людей за окном. Друзья или бандиты?",
            ]
        ),
        "medieval_tavern": Scenario(
            name="Средневековая таверна",
            description="Вы — путники, встретившиеся в таверне перед опасным квестом",
            context=(
                "Средневековый фэнтезийный мир. Вы — путники разных профессий, "
                "встретившиеся в шумной таверне 'Пьяный дракон'. "
                "Завтра вас ждёт опасный квест в тёмный лес. Может, стоит получше узнать друг друга?"
            ),
            events=[
                "🍺 Бармен приносит эль. Может, выпьем и расскажем о себе?",
                "⚔️ В таверну врываются бандиты! Начинается драка!",
                "🎲 Кто-то предлагает сыграть в кости на деньги.",
                "🎵 Бард начинает петь грустную балладу о павших героях.",
                "🗺️ Местный старик предлагает карту с сокровищами. Верить ли ему?",
                "🔮 Гадалка предсказывает опасность в завтрашнем походе.",
                "🍖 Приносят горячее жаркое. Время поесть и поболтать.",
                "👤 Загадочный незнакомец слушает ваш разговор из угла.",
                "⚡ Гроза за окном. Похоже, завтра будет плохая погода.",
                "🌙 Поздняя ночь. Большинство гостей разошлись. Только вы и тишина.",
            ]
        ),
    }

    def __init__(self, scenario_name: str = "desert_island", db_path: str = SCENARIO_DB_PATH):
        self.db_path = Path(db_path)
        self.current_scenario = self.SCENARIOS.get(scenario_name, self.SCENARIOS["desert_island"])
        self.events_triggered: list[str] = []
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_from_db()

    def get_scenario_context(self) -> str:
        context = f"\n🎭 СЦЕНАРИЙ: {self.current_scenario.name}\n"
        context += f"{self.current_scenario.context}\n"
        if self.events_triggered:
            context += f"\nПроизошедшие события: {', '.join(self.events_triggered[-3:])}\n"
        return context

    def trigger_random_event(self) -> Optional[str]:
        if not self.current_scenario.events:
            return None
        available_events = [e for e in self.current_scenario.events if e not in self.events_triggered[-3:]]
        if not available_events:
            available_events = self.current_scenario.events
        event = random.choice(available_events)
        self.events_triggered.append(event)
        self.save_to_db()
        return event

    def save_to_db(self):
        data = {
            "scenario_name": self.current_scenario.name,
            "events_triggered": self.events_triggered,
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_db(self):
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.events_triggered = data.get("events_triggered", [])
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Не удалось загрузить сценарий: {e}{Style.RESET_ALL}")


# ── Система пользовательских событий ─────────────────────────

class UserEventInput:
    """Фоновый поток для ввода пользовательских событий и сообщений во время симуляции.
    Пользователь может в любой момент набрать текст и нажать Enter.
    Форматы:
      @Алиса текст  — личное сообщение агенту Алиса
      @все текст    — сообщение всем агентам
      текст         — событие в мире (как раньше)
    Событие/сообщение попадёт в очередь и будет обработано на следующем тике."""

    def __init__(self, agent_names: list[str] = None):
        self.event_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False  # пауза ввода (при выборе сценария и т.п.)
        # Имена агентов для адресации сообщений
        self.agent_names: list[str] = agent_names or []

    def start(self):
        """Запустить фоновый поток ввода."""
        self._running = True
        self._thread = threading.Thread(target=self._input_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Остановить фоновый поток."""
        self._running = False

    def pause(self):
        """Приостановить приём ввода."""
        self._paused = True

    def resume(self):
        """Возобновить приём ввода."""
        self._paused = False

    def get_pending_events(self) -> list[str]:
        """Получить все накопленные пользовательские события из очереди."""
        events = []
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                if event and event.strip():
                    events.append(event.strip())
            except queue.Empty:
                break
        return events

    def _input_loop(self):
        """Цикл чтения ввода из stdin в фоне."""
        while self._running:
            try:
                if self._paused:
                    time.sleep(0.2)
                    continue
                line = sys.stdin.readline()
                if not line:
                    # EOF — stdin закрыт
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line:
                    continue
                # Специальные команды
                if line.lower() in ('quit', 'exit', 'выход', 'стоп'):
                    self.event_queue.put('__QUIT__')
                    continue
                if line.lower() in ('help', 'помощь', '?'):
                    self._print_help()
                    continue
                if line.lower() in ('stats', 'стат', 'статистика'):
                    self.event_queue.put('__STATS__')
                    continue
                # Обычное пользовательское событие
                self.event_queue.put(line)
            except (EOFError, OSError):
                time.sleep(0.5)
            except Exception:
                time.sleep(0.3)

    def _print_help(self):
        """Вывести подсказку по командам."""
        agent_list = ', '.join(self.agent_names) if self.agent_names else 'Алиса, Борис, Вика'
        print(f"\n{Fore.CYAN}{'─' * 50}")
        print(f"{Fore.CYAN}📝 ИНТЕРАКТИВНАЯ СИСТЕМА")
        print(f"{Fore.CYAN}{'─' * 50}")
        print(f"{Fore.WHITE}  💬 СООБЩЕНИЯ АГЕНТАМ:")
        print(f"{Fore.GREEN}    @Алиса Привет, как дела?     — личное сообщение Алисе")
        print(f"{Fore.GREEN}    @Борис Что думаешь?          — личное сообщение Борису")
        print(f"{Fore.GREEN}    @все Ребята, я тут!           — сообщение всем агентам")
        print(f"{Fore.GREEN}    @all Внимание!                — сообщение всем агентам")
        print(f"{Fore.WHITE}  Доступные агенты: {agent_list}")
        print(f"")
        print(f"{Fore.WHITE}  🎭 СОБЫТИЯ В МИРЕ:")
        print(f"{Fore.GREEN}    На горизонте появился дым от другого костра")
        print(f"{Fore.GREEN}    Земля начала трястись — землетрясение!")
        print(f"{Fore.WHITE}  (текст без @ — создаёт событие в мире)")
        print(f"")
        print(f"{Fore.WHITE}  ⚙️ КОМАНДЫ:")
        print(f"{Fore.YELLOW}    help / помощь / ?  — эта подсказка")
        print(f"{Fore.YELLOW}    stats / стат       — показать статистику")
        print(f"{Fore.YELLOW}    quit / выход       — остановить симуляцию")
        print(f"{Fore.CYAN}{'─' * 50}\n")


# ── Система тем и креативности ────────────────────────────────

class TopicManager:
    def __init__(self, db_path: str = TOPIC_DB_PATH):
        self.db_path = Path(db_path)
        self.current_topic: Optional[str] = None
        self.messages_on_topic: int = 0
        self.discussed_topics: list[str] = []
        # [FIX #10] Отслеживаем, получили ли ответы на текущую тему
        self.topic_has_responses: int = 0
        self.topic_respondents: set = set()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_from_db()

    def generate_new_topic_llm(self, scenario_context: str = "") -> str:
        discussed_context = ""
        if self.discussed_topics:
            recent_topics = self.discussed_topics[-5:]
            discussed_context = f"\n\nУже обсуждали (НЕ ПОВТОРЯЙ): {', '.join(recent_topics)}"

        scenario_info = ""
        if scenario_context:
            scenario_info = f"\n\nКОНТЕКСТ СЦЕНАРИЯ:\n{scenario_context}\nТема ДОЛЖНА быть связана с этим сценарием!"

        prompt = [
            {
                "role": "system",
                "content": (
                    "Ты — креативный модератор дискуссий.\n"
                    f"{scenario_info}\n"
                    "Темы должны быть:\n"
                    "- КОНКРЕТНЫМИ и практическими (про действия, предметы, решения)\n"
                    "- Связанными с текущей ситуацией сценария\n"
                    "- Формулироваться как вопрос или предложение к действию\n"
                    "- Короткими (1 предложение)\n\n"
                    "ХОРОШИЕ примеры тем:\n"
                    "- 'Нам нужно решить, кто будет дежурить ночью'\n"
                    "- 'Еды осталось на три дня, что будем делать?'\n\n"
                    "ПЛОХИЕ примеры (НЕ ИСПОЛЬЗУЙ):\n"
                    "- 'А что, если мы не просто выживаем...' — слишком абстрактно\n"
                    "- 'Что делает нас людьми?' — слишком философски\n"
                    f"{discussed_context}\n"
                    "Предложи совершенно новую тему, не повторяющую предыдущие.\n\n"
                    "КРИТИЧЕСКИ ВАЖНО:\n"
                    "- Пиши ТОЛЬКО на русском языке\n"
                    "- НЕ используй теги <think>, </think>\n"
                    "- Верни ТОЛЬКО текст темы на русском, без пояснений"
                )
            },
            {
                "role": "user",
                "content": "Предложи новую КОНКРЕТНУЮ тему для обсуждения НА РУССКОМ ЯЗЫКЕ. Только тему, без дополнительных слов."
            }
        ]

        topic = llm_chat(prompt, temperature=0.9)
        if not topic:
            topic = self._fallback_topic(scenario_context)

        import re
        topic = re.sub(r'<think>.*?</think>', '', topic, flags=re.DOTALL | re.IGNORECASE)
        topic = re.sub(r'<think>.*', '', topic, flags=re.DOTALL | re.IGNORECASE)
        topic = re.sub(r'</?think>', '', topic, flags=re.IGNORECASE)
        topic = topic.strip().strip('"\'').lower()

        if len(topic) < 5:
            topic = self._fallback_topic(scenario_context)

        return topic

    def _fallback_topic(self, scenario_context: str = "") -> str:
        ctx = scenario_context.lower()
        if "зомби" in ctx:
            return random.choice([
                "как вы думаете, сможем ли мы продержаться здесь месяц?",
                "стоит ли рисковать и искать других выживших?",
            ])
        elif "остров" in ctx:
            return random.choice([
                "как построить укрытие, чтобы пережить шторм?",
                "что важнее — найти воду или разжечь сигнальный костёр?",
            ])
        elif "космическая" in ctx or "станция" in ctx:
            return random.choice([
                "что делать, если кислород закончится через неделю?",
                "стоит ли пытаться отправить сигнал бедствия в космос?",
            ])
        elif "таверн" in ctx:
            return random.choice([
                "кому из нас можно доверять в опасном квесте?",
                "стоит ли рисковать жизнью ради славы?",
            ])
        else:
            return random.choice([
                "что для вас значит настоящая дружба?",
                "как вы справляетесь с трудностями?",
            ])

    def get_new_topic(self, scenario_context: str = "") -> str:
        topic = self.generate_new_topic_llm(scenario_context)
        self.current_topic = topic
        self.discussed_topics.append(topic)
        self.messages_on_topic = 0
        self.topic_has_responses = 0
        self.topic_respondents = set()
        self.save_to_db()
        return topic

    def record_message(self, agent_name: str = ""):
        """[FIX #10] Трекаем кто ответил на тему."""
        self.messages_on_topic += 1
        if agent_name:
            self.topic_respondents.add(agent_name)
            self.topic_has_responses = len(self.topic_respondents)

    def should_change_topic(self, num_agents: int = 3) -> bool:
        """[FIX #10] Тема меняется только если все ответили И прошло достаточно сообщений."""
        if self.topic_has_responses < num_agents and self.messages_on_topic < TOPIC_CHANGE_THRESHOLD + 5:
            return False
        return self.messages_on_topic >= TOPIC_CHANGE_THRESHOLD

    def save_to_db(self):
        data = {
            "current_topic": self.current_topic,
            "messages_on_topic": self.messages_on_topic,
            "discussed_topics": self.discussed_topics,
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_db(self):
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_topic = data.get("current_topic")
            self.messages_on_topic = data.get("messages_on_topic", 0)
            self.discussed_topics = data.get("discussed_topics", [])
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Не удалось загрузить темы: {e}{Style.RESET_ALL}")


# ── Система фаз диалога (прогресс) ──────────────────────────

class DialoguePhaseManager:
    """[FIX v3] Управляет фазами обсуждения темы: discuss → decide → act → conclude.
    Каждая фаза имеет лимит тиков. Когда все фазы пройдены — тема считается завершённой."""

    def __init__(self):
        self.current_phase_index: int = 0
        self.ticks_in_phase: int = 0
        self.topic_started_tick: int = 0
        self.topic_decisions: list[str] = []  # решения, принятые в теме
        self.topic_actions: list[str] = []    # действия, совершённые в теме

    @property
    def current_phase(self) -> str:
        if self.current_phase_index >= len(PHASE_ORDER):
            return "conclude"
        return PHASE_ORDER[self.current_phase_index]

    @property
    def phase_label(self) -> str:
        return PHASE_LABELS.get(self.current_phase, "")

    def start_new_topic(self, tick: int):
        self.current_phase_index = 0
        self.ticks_in_phase = 0
        self.topic_started_tick = tick
        self.topic_decisions = []
        self.topic_actions = []

    def advance_tick(self) -> tuple[bool, str]:
        """Продвигает тик фазы. Возвращает (phase_changed, new_phase_label)."""
        self.ticks_in_phase += 1
        phase = self.current_phase
        max_ticks = PHASE_TICKS.get(phase, 5)
        if self.ticks_in_phase >= max_ticks:
            self.current_phase_index += 1
            self.ticks_in_phase = 0
            if self.current_phase_index < len(PHASE_ORDER):
                new_phase = PHASE_ORDER[self.current_phase_index]
                return True, PHASE_LABELS.get(new_phase, "")
            else:
                return True, "🏁 Тема завершена"
        return False, ""

    def is_topic_complete(self) -> bool:
        return self.current_phase_index >= len(PHASE_ORDER)

    def get_phase_instruction(self) -> str:
        """Возвращает инструкцию для промпта в зависимости от текущей фазы."""
        phase = self.current_phase
        remaining = PHASE_TICKS.get(phase, 5) - self.ticks_in_phase
        if phase == "discuss":
            return (
                f"\n═══ ФАЗА: {PHASE_LABELS[phase]} (осталось ~{remaining} ходов) ═══\n"
                "Сейчас нужно ОБСУЖДАТЬ тему:\n"
                "- Поделись своим мнением\n"
                "- Задай вопрос другим\n"
                "- Расскажи о своих навыках/опыте по теме\n"
                "- Выслушай других и отреагируй\n"
            )
        elif phase == "decide":
            decisions_text = ", ".join(self.topic_decisions[-3:]) if self.topic_decisions else "пока нет"
            return (
                f"\n═══ ФАЗА: {PHASE_LABELS[phase]} (осталось ~{remaining} ходов) ═══\n"
                "Пора ПРИНИМАТЬ РЕШЕНИЯ:\n"
                "- Предложи конкретное решение\n"
                "- Согласись или предложи альтернативу\n"
                "- Распредели роли: кто что делает\n"
                f"- Уже решено: {decisions_text}\n"
                "- НЕ спорь больше — ДОГОВАРИВАЙСЯ\n"
            )
        elif phase == "act":
            actions_text = ", ".join(self.topic_actions[-3:]) if self.topic_actions else "пока никто"
            return (
                f"\n═══ ФАЗА: {PHASE_LABELS[phase]} (осталось ~{remaining} ходов) ═══\n"
                "Время ДЕЙСТВОВАТЬ:\n"
                "- Скажи что ты КОНКРЕТНО делаешь прямо сейчас\n"
                "- Начни выполнять свою часть плана\n"
                "- Сообщи о результате действия\n"
                f"- Уже действуют: {actions_text}\n"
            )
        elif phase == "conclude":
            return (
                f"\n═══ ФАЗА: {PHASE_LABELS[phase]} (осталось ~{remaining} ходов) ═══\n"
                "Подведи ИТОГ:\n"
                "- Резюмируй что решили и сделали\n"
                "- Оцени результат\n"
                "- Можешь предложить НОВУЮ тему или сообщить о новой проблеме\n"
            )
        return ""

    def record_decision(self, text: str):
        """Записать решение (вызывается при обнаружении решения в тексте)."""
        decision_markers = ['давайте', 'решено', 'будем', 'предлагаю', 'план такой',
                            'я буду', 'ты будешь', 'распределим', 'договорились']
        text_lower = text.lower()
        if any(m in text_lower for m in decision_markers):
            self.topic_decisions.append(text[:80])
            if len(self.topic_decisions) > 5:
                self.topic_decisions = self.topic_decisions[-5:]

    def record_action(self, text: str):
        """Записать действие (вызывается при обнаружении действия в тексте)."""
        action_markers = ['пойду', 'пошёл', 'делаю', 'начинаю', 'беру', 'открываю',
                          'проверяю', 'ищу', 'строю', 'собираю', 'чиню']
        text_lower = text.lower()
        if any(m in text_lower for m in action_markers):
            self.topic_actions.append(text[:80])
            if len(self.topic_actions) > 5:
                self.topic_actions = self.topic_actions[-5:]


# ── Система планирования и целей ─────────────────────────────

@dataclass
class Goal:
    description: str
    priority: float
    created_tick: int
    completed: bool = False
    progress: str = ""

@dataclass
class ActionPlan:
    goal: str
    steps: list[str]
    current_step: int = 0
    observations: list[str] = field(default_factory=list)
    adaptations: list[str] = field(default_factory=list)


# ── Система памяти (LSTM-стиль) ───────────────────────────────

@dataclass
class MemoryItem:
    tick: int
    speaker: str           # display_name на момент записи (для промптов)
    text: str
    timestamp: str
    importance: float = 0.5
    speaker_id: str = ""   # agent_id говорящего (неизменяемый ключ)
    # [FIX #2] Метаданные для адресации
    addressed_to: str = ""     # display_name адресата
    addressed_to_id: str = ""  # agent_id адресата
    is_event: bool = False
    is_action_result: bool = False

    def to_dict(self):
        return asdict(self)


class AgentMemorySystem:
    def __init__(self, agent_id: str, db_path: str = MEMORY_DB_PATH):
        self.agent_id = agent_id
        self.db_path = Path(db_path)
        self.short_term: list[MemoryItem] = []
        self.long_term: list[MemoryItem] = []
        # [FIX #5] Трекинг уже выполненных действий
        self.completed_actions: list[str] = []
        # [FIX #1] Нерешённые вопросы
        self.pending_questions: list[dict] = []
        self._memories_since_save = 0
        self._autosave_interval = 1
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_from_db()

    def add_memory(self, tick: int, speaker: str, text: str, importance: float = 0.5,
                   addressed_to: str = "", addressed_to_id: str = "",
                   speaker_id: str = "",
                   is_event: bool = False, is_action_result: bool = False):
        # Резолвим имена через реестр если id не передан
        if not speaker_id and speaker:
            speaker_id = agent_registry.get_id(speaker) or ""

        memory = MemoryItem(
            tick=tick, speaker=speaker, text=text,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            speaker_id=speaker_id,
            addressed_to=addressed_to,
            addressed_to_id=addressed_to_id,
            is_event=is_event,
            is_action_result=is_action_result,
        )

        self.short_term.append(memory)
        self._memories_since_save += 1

        # [FIX #9] Сжатие при БОЛЬШЕМ пороге
        total_size = len(self.short_term) + len(self.long_term)
        if total_size >= COMPRESSION_THRESHOLD:
            self._smart_compress()
        elif len(self.short_term) > SHORT_TERM_MEMORY:
            oldest = self.short_term.pop(0)
            if oldest.importance > 0.6 or oldest.is_event or oldest.is_action_result:
                self._consolidate_to_long_term(oldest)

        if self._memories_since_save >= self._autosave_interval:
            self.save_to_db()
            self._memories_since_save = 0

    def record_action(self, action_text: str):
        """[FIX #5] Записать выполненное действие."""
        self.completed_actions.append(action_text.lower().strip()[:100])
        if len(self.completed_actions) > 20:
            self.completed_actions = self.completed_actions[-20:]

    def has_done_similar(self, action_text: str) -> bool:
        """[FIX #5] Проверить, делал ли агент уже подобное."""
        action_lower = action_text.lower().strip()
        for prev in self.completed_actions:
            if _text_similarity(action_lower, prev) > 0.5:
                return True
        return False

    def add_pending_question(self, tick: int, from_agent: str, question: str, from_id: str = ""):
        """[FIX #1] Добавить вопрос, на который нужно ответить."""
        if not from_id and from_agent:
            from_id = agent_registry.get_id(from_agent) or ""
        self.pending_questions.append({
            "tick": tick, "from": from_agent, "from_id": from_id, "question": question[:200]
        })
        if len(self.pending_questions) > 3:
            self.pending_questions = self.pending_questions[-3:]

    def get_pending_questions_text(self) -> str:
        """[FIX #1] Получить текст нерешённых вопросов."""
        if not self.pending_questions:
            return ""
        lines = ["═══ ТЕБЕ ЗАДАЛИ ВОПРОСЫ / ОБРАТИЛИСЬ К ТЕБЕ ═══"]
        for q in self.pending_questions:
            # Резолвим имя через реестр (на случай переименования)
            from_id = q.get('from_id', '')
            display_name = agent_registry.get_name(from_id) if from_id else q['from']
            lines.append(f"  {display_name} (тик {q['tick']}): {q['question']}")
        lines.append("ОБЯЗАТЕЛЬНО ответь на эти вопросы или отреагируй!\n")
        return "\n".join(lines)

    def clear_pending_questions(self):
        self.pending_questions = []

    def _consolidate_to_long_term(self, memory: MemoryItem):
        self.long_term.append(memory)
        if len(self.long_term) > LONG_TERM_MEMORY:
            # [FIX #9] Не удаляем события и результаты действий
            removable = [m for m in self.long_term if not m.is_event and not m.is_action_result]
            if removable:
                removable.sort(key=lambda m: m.importance)
                to_remove = removable[0]
                self.long_term.remove(to_remove)
            else:
                self.long_term.sort(key=lambda m: m.importance, reverse=True)
                self.long_term = self.long_term[:LONG_TERM_MEMORY]

    def _smart_compress(self):
        """[FIX #9 v3] Компрессия — реально уменьшает память."""
        all_memories = self.short_term + self.long_term
        if len(all_memories) < COMPRESSION_THRESHOLD:
            return

        print(f"{Fore.YELLOW}🗜️  Сжатие памяти агента {self.agent_id} ({len(all_memories)} элементов)...{Style.RESET_ALL}")

        # Целевой размер — 60% от порога
        target_size = int(COMPRESSION_THRESHOLD * 0.6)

        # Последние 10 свежих — неприкосновенны (было 6, терялся контекст)
        fresh_count = min(10, len(all_memories) // 3)
        fresh_memories = all_memories[-fresh_count:]
        older_memories = all_memories[:-fresh_count]

        # Критические — ТОЛЬКО настоящие события (is_event), не action_result и не просто high importance
        # Ограничиваем максимум 8 критических
        true_events = [m for m in older_memories if m.is_event]
        true_events.sort(key=lambda m: m.tick, reverse=True)
        critical_memories = true_events[:8]
        critical_set = set(id(m) for m in critical_memories)

        regular_memories = [m for m in older_memories if id(m) not in critical_set]

        # Temporal decay: сортируем regular по decayed importance
        current_tick = max((m.tick for m in all_memories), default=0)
        regular_memories.sort(
            key=lambda m: self._decayed_importance(m, current_tick),
            reverse=True
        )

        # Сколько regular можем оставить?
        slots_for_regular = max(target_size - len(fresh_memories) - len(critical_memories), 5)
        top_important = regular_memories[:slots_for_regular]

        remaining = regular_memories[slots_for_regular:]
        summary_memories = []

        if len(remaining) > 5:
            # ── Эпизодическая группировка ──────────────────────
            # Группируем remaining по близости тиков в эпизоды
            remaining_sorted = sorted(remaining, key=lambda m: m.tick)
            episodes: list[list[MemoryItem]] = []
            current_episode: list[MemoryItem] = [remaining_sorted[0]]

            for mem in remaining_sorted[1:]:
                if mem.tick - current_episode[-1].tick <= EPISODE_GAP_TICKS:
                    current_episode.append(mem)
                else:
                    episodes.append(current_episode)
                    current_episode = [mem]
            episodes.append(current_episode)

            # Суммаризируем каждый эпизод отдельно (макс 4 вызова LLM)
            for episode in episodes[:4]:
                if len(episode) < 2:
                    # Одиночное воспоминание — не суммаризируем, просто отбрасываем
                    continue
                episode_text = "\n".join([
                    f"[тик {m.tick}] [{m.speaker}]: {m.text[:80]}" for m in episode
                ])
                tick_range = f"{episode[0].tick}-{episode[-1].tick}"
                prompt = [
                    {
                        "role": "system",
                        "content": (
                            f"Сожми эпизод диалога (тики {tick_range}) в 1-2 ключевых пункта. "
                            "Сохрани: кто что СДЕЛАЛ, результаты, решения. "
                            "Каждый пункт — 1 короткое предложение. ТОЛЬКО русский, БЕЗ тегов."
                        )
                    },
                    {"role": "user", "content": f"Эпизод:\n{episode_text}\n\nКлючевые моменты:"}
                ]
                summary = llm_chat(prompt, temperature=0.3)
                if summary:
                    import re
                    summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL | re.IGNORECASE)
                    summary = re.sub(r'</?think>', '', summary, flags=re.IGNORECASE)
                    summary_memories.append(MemoryItem(
                        tick=episode[-1].tick,
                        speaker="[СВОДКА]", text=f"[тики {tick_range}] {summary[:250]}",
                        timestamp=datetime.now().isoformat(), importance=0.65,
                        is_event=False, is_action_result=False,
                    ))

        new_long_term = critical_memories + top_important
        for sm in summary_memories:
            new_long_term.append(sm)

        old_size = len(all_memories)
        self.short_term = fresh_memories
        self.long_term = new_long_term
        new_size = len(self.short_term) + len(self.long_term)

        print(f"{Fore.GREEN}✓ Память сжата: {old_size} → {new_size} элементов{Style.RESET_ALL}")
        print(f"{Fore.CYAN}  └─ События: {len(critical_memories)} | Важные: {len(top_important)} | Свежие: {len(fresh_memories)} | Сводки эпизодов: {len(summary_memories)}{Style.RESET_ALL}")
        self.save_to_db()

    def consolidate_before_rename(self, old_name: str, new_name: str):
        """Принудительная группировка перед переименованием агента.
        Все воспоминания, содержащие old_name, суммаризируются в сводку
        с пометкой о переименовании. Это предотвращает путаницу имён."""
        all_memories = self.short_term + self.long_term
        # Ищем воспоминания, где фигурирует старое имя
        affected = [m for m in all_memories
                    if old_name.lower() in m.text.lower()
                    or m.speaker.lower() == old_name.lower()]

        if not affected:
            return

        print(f"{Fore.YELLOW}🔄 Консолидация памяти перед переименованием "
              f"{old_name} → {new_name} ({len(affected)} записей)...{Style.RESET_ALL}")

        # Группируем affected по эпизодам
        affected_sorted = sorted(affected, key=lambda m: m.tick)
        episodes: list[list[MemoryItem]] = []
        current_episode: list[MemoryItem] = [affected_sorted[0]]
        for mem in affected_sorted[1:]:
            if mem.tick - current_episode[-1].tick <= EPISODE_GAP_TICKS:
                current_episode.append(mem)
            else:
                episodes.append(current_episode)
                current_episode = [mem]
        episodes.append(current_episode)

        # Суммаризируем все эпизоды с old_name → new_name (макс 3 вызова LLM)
        summary_memories = []
        for episode in episodes[:3]:
            episode_text = "\n".join([
                f"[тик {m.tick}] [{m.speaker}]: {m.text[:80]}" for m in episode
            ])
            tick_range = f"{episode[0].tick}-{episode[-1].tick}"
            prompt = [
                {
                    "role": "system",
                    "content": (
                        f"Персонаж '{old_name}' переименован в '{new_name}'. "
                        f"Сожми эпизод (тики {tick_range}) в 1-2 предложения, "
                        f"заменив все упоминания '{old_name}' на '{new_name}'. "
                        "Сохрани ключевые действия и решения. ТОЛЬКО русский, БЕЗ тегов."
                    )
                },
                {"role": "user", "content": f"Эпизод:\n{episode_text}\n\nСводка:"}
            ]
            summary = llm_chat(prompt, temperature=0.3)
            if summary:
                import re
                summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL | re.IGNORECASE)
                summary = re.sub(r'</?think>', '', summary, flags=re.IGNORECASE)
                summary_memories.append(MemoryItem(
                    tick=episode[-1].tick,
                    speaker="[СВОДКА]",
                    text=f"[{old_name}→{new_name}] {summary[:250]}",
                    timestamp=datetime.now().isoformat(), importance=0.7,
                    is_event=False, is_action_result=False,
                ))

        # Убираем affected из short_term и long_term, добавляем сводки
        affected_ids = set(id(m) for m in affected)
        self.short_term = [m for m in self.short_term if id(m) not in affected_ids]
        self.long_term = [m for m in self.long_term if id(m) not in affected_ids]
        self.long_term.extend(summary_memories)

        # Также обновляем speaker в оставшихся записях
        for mem in self.short_term + self.long_term:
            if mem.speaker == old_name:
                mem.speaker = new_name

        self.save_to_db()
        print(f"{Fore.GREEN}✓ Консолидация завершена: {len(affected)} записей → "
              f"{len(summary_memories)} сводок{Style.RESET_ALL}")

    def get_recent_context(self, n: int = SHORT_TERM_MEMORY) -> list[MemoryItem]:
        return self.short_term[-n:]

    def _decayed_importance(self, memory: MemoryItem, current_tick: int = None) -> float:
        """Temporal decay: важность убывает со временем.
        События (is_event) decay в 2 раза медленнее."""
        if current_tick is None:
            current_tick = max(
                (m.tick for m in self.short_term + self.long_term),
                default=0
            )
        age = max(current_tick - memory.tick, 0)
        factor = IMPORTANCE_DECAY_FACTOR if not memory.is_event else (IMPORTANCE_DECAY_FACTOR ** 0.5)
        return memory.importance * (factor ** age)

    def get_relevant_long_term(self, n: int = 5) -> list[MemoryItem]:
        """[FIX #2] Приоритет — события и результаты действий, с temporal decay."""
        current_tick = max(
            (m.tick for m in self.short_term + self.long_term),
            default=0
        )
        sorted_memories = sorted(self.long_term, key=lambda m: (
            m.is_event or m.is_action_result,
            self._decayed_importance(m, current_tick)
        ), reverse=True)
        return sorted_memories[:n]

    def format_for_prompt(self) -> str:
        context_parts = []
        long_term_relevant = self.get_relevant_long_term(5)
        if long_term_relevant:
            context_parts.append("═══ ВАЖНЫЕ СОБЫТИЯ ИЗ ПРОШЛОГО ═══")
            for mem in long_term_relevant:
                prefix = ""
                if mem.is_event:
                    prefix = "🎬 СОБЫТИЕ: "
                elif mem.is_action_result:
                    prefix = "✨ РЕЗУЛЬТАТ: "
                # Резолвим имя через реестр (актуальное display_name)
                display = agent_registry.get_name(mem.speaker_id) if mem.speaker_id else mem.speaker
                context_parts.append(f"  [тик {mem.tick}] {prefix}[{display}]: {mem.text}")
            context_parts.append("")

        # [FIX #5] Уже выполненные действия
        if self.completed_actions:
            context_parts.append("═══ ТЫ УЖЕ ДЕЛАЛ ЭТО (НЕ ПОВТОРЯЙ!) ═══")
            for action in self.completed_actions[-8:]:
                context_parts.append(f"  ✓ {action}")
            context_parts.append("Придумай НОВОЕ действие!\n")

        return "\n".join(context_parts) if context_parts else ""

    def save_to_db(self):
        data = {
            "agent_id": self.agent_id,
            "last_updated": datetime.now().isoformat(),
            "short_term": [m.to_dict() for m in self.short_term],
            "long_term": [m.to_dict() for m in self.long_term],
            "completed_actions": self.completed_actions,
        }
        all_data = {}
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
            except Exception:
                pass
        all_data[self.agent_id] = data
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

    def load_from_db(self):
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
            if self.agent_id not in all_data:
                return
            data = all_data[self.agent_id]
            # Обратная совместимость: убираем старые Big Five поля из JSON
            _removed_fields = {'openness', 'conscientiousness', 'extraversion',
                               'agreeableness', 'neuroticism', 'talkativeness'}
            def _clean(item: dict) -> dict:
                return {k: v for k, v in item.items() if k not in _removed_fields}
            self.short_term = [MemoryItem(**_clean(item)) for item in data.get("short_term", [])]
            self.long_term = [MemoryItem(**_clean(item)) for item in data.get("long_term", [])]
            self.completed_actions = data.get("completed_actions", [])
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Не удалось загрузить память для {self.agent_id}: {e}{Style.RESET_ALL}")


# ── Модель агента ─────────────────────────────────────────────


@dataclass
class Agent:
    agent_id: str
    name: str
    personality_type: PersonalityType
    big_five: BigFiveTraits
    race_type: RaceType = RaceType.HUMAN  # Раса агента
    is_male: bool = True
    age: int = 25
    interests: str = ""
    additional_info: str = ""
    color: str = Fore.WHITE

    talkativeness: float = field(init=False)
    base_talkativeness: float = field(init=False)
    recovery_rate: float = 0.1
    depletion_rate: float = 0.2
    ticks_silent: int = 0
    messages_spoken: int = 0

    # [FIX #7] Отношения с метаданными (ключи — agent_id, не имена!)
    relationships: dict = field(default_factory=dict)   # agent_id → float
    relationship_log: list = field(default_factory=list)

    memory_system: AgentMemorySystem = field(init=False)
    goals: list = field(default_factory=list)
    current_plan: Optional[ActionPlan] = None
    observations: list = field(default_factory=list)
    last_event: Optional[str] = None
    # [FIX #6] Фокус на событии
    event_focus_tick: int = 0
    active_event: Optional[str] = None
    # [FIX v3] Трекинг последовательных похожих реплик
    consecutive_similar_count: int = 0
    last_response_phrases: set = field(default_factory=set)
    # [FIX v3] Отреагировал ли на текущее событие
    reacted_to_event: bool = False

    # Система настроения
    mood: AgentMood = field(init=False)

    def __post_init__(self):
        self.memory_system = AgentMemorySystem(self.agent_id)
        # Раса и расовые модификаторы
        self.race: Race = RACES[self.race_type]
        self._apply_race_modifiers_to_big_five()
        # Инициализируем настроение на основе типа личности (уже с расовыми модификаторами Big Five)
        self.mood = AgentMood.from_personality(self.personality_type, self.big_five)
        base = self.big_five.extraversion / 100.0
        variation = random.uniform(-0.2, 0.2)
        self.talkativeness = max(0.1, min(0.7, base + variation))
        self.base_talkativeness = base
        extraversion_factor = self.big_five.extraversion / 100.0
        neuroticism_factor = 1 - (self.big_five.neuroticism / 100.0)
        self.recovery_rate = 0.03 + (extraversion_factor * 0.7 + neuroticism_factor * 0.3) * 0.08
        self.depletion_rate = 0.08 + (self.big_five.neuroticism / 100.0) * 0.20 + (1 - extraversion_factor) * 0.12

    def _apply_race_modifiers_to_big_five(self):
        """Применить расовые модификаторы к Big Five."""
        mods = self.race.modifiers
        self.big_five.openness = max(0, min(100, self.big_five.openness + mods.openness))
        self.big_five.conscientiousness = max(0, min(100, self.big_five.conscientiousness + mods.conscientiousness))
        self.big_five.extraversion = max(0, min(100, self.big_five.extraversion + mods.extraversion))
        self.big_five.agreeableness = max(0, min(100, self.big_five.agreeableness + mods.agreeableness))
        self.big_five.neuroticism = max(0, min(100, self.big_five.neuroticism + mods.neuroticism))

    @property
    def display_name(self) -> str:
        """Текущее отображаемое имя агента (из реестра)."""
        return agent_registry.get_name(self.agent_id)

    @property
    def personality_description(self) -> str:
        gender = "мужчина" if self.is_male else "женщина"
        traits_desc = self.big_five.to_description()
        race = self.race
        base = f"Ты — {self.display_name}, {race.emoji} {race.name_ru}, {gender} {self.age} лет. "
        base += f"Раса: {race.name_ru} ({race.description}). "
        base += f"Тип личности: {self.personality_type.value}. "
        base += f"Черты характера: {traits_desc}. "
        if self.interests:
            base += f"Интересы: {self.interests}. "
        if self.additional_info:
            base += f"{self.additional_info}"
        return base

    def get_relationship_description(self) -> str:
        """[FIX #7] Подробное описание отношений с причинами и расовой информацией."""
        if not self.relationships:
            return "пока нет данных об отношениях"
        parts = []
        for other_id, value in self.relationships.items():
            # Резолвим agent_id → текущее display_name
            display_name = agent_registry.get_name(other_id)
            # Ищем расу другого агента через реестр
            other_race_emoji = ""
            other_race_name = ""
            # Пытаемся найти расу через глобальный контекст
            # (race хранится в объекте Agent, ищем через id)
            racial_note = ""
            other_race_type = None
            # Ищем расовый модификатор
            for rt, mod in self.race.racial_relations.items():
                # Мы не знаем race_type другого тут, но можно добавить подсказку
                pass

            if value > 0.5:
                attitude = "очень хорошие (доверие, симпатия)"
            elif value > 0.2:
                attitude = "хорошие (дружелюбие)"
            elif value > -0.2:
                attitude = "нейтральные"
            elif value > -0.5:
                attitude = "натянутые (раздражение)"
            else:
                attitude = "плохие (конфликт, недоверие)"
            parts.append(f"  {display_name}: {value:+.2f} — {attitude}")
        result = "\n".join(parts)
        if self.relationship_log:
            recent = self.relationship_log[-3:]
            result += "\nНедавние изменения отношений:"
            for entry in recent:
                result += f"\n  → {entry}"
        return result

    def system_prompt(self, long_term_context: str = "", mode: str = "normal",
                      scenario_context: str = "", recent_own_messages: list = None,
                      recent_dialogue_context: str = "",
                      active_event_context: str = "",
                      pending_questions: str = "",
                      phase_instruction: str = "",
                      force_event_reaction: bool = False) -> str:

        rel_info = self.get_relationship_description()
        mood_info = self.mood.to_description()

        # Формируем числовую строку настроения для промпта
        mood_numbers = (
            f"  Счастье: {self.mood.happiness:+.1f} | "
            f"Злость: {self.mood.anger:.1f} | "
            f"Страх: {self.mood.fear:.1f} | "
            f"Стресс: {self.mood.stress:.1f} | "
            f"Энергия: {self.mood.energy:.1f}"
        )

        base_prompt = (
            f"{self.personality_description}\n\n"
            f"{self._get_race_prompt()}\n"
            f"═══ ОТНОШЕНИЯ С ДРУГИМИ ═══\n{rel_info}\n\n"
            f"═══ ТВОЁ ТЕКУЩЕЕ НАСТРОЕНИЕ (ОБЯЗАТЕЛЬНО УЧИТЫВАЙ!) ═══\n"
            f"{mood_info}\n"
            f"{mood_numbers}\n\n"
            f"🚨 ПРАВИЛА НАСТРОЕНИЯ (СТРОГО!):\n"
            f"- Если страх > 0.3 → НЕ ругайся и НЕ оскорбляй! Покажи тревогу, осторожность\n"
            f"- Если злость > 0.4 И страх < 0.2 → можешь грубить и ругаться\n"
            f"- Если счастье < -0.2 → говори мрачно, пессимистично\n"
            f"- Если стресс > 0.5 → говори нервно, торопливо, суетливо\n"
            f"- Если энергия < 0.3 → говори мало и вяло\n"
            f"- Твоё настроение ВАЖНЕЕ твоего типа личности в данный момент!\n\n"
            f"Желание говорить: {self.talkativeness:.1f}/1.0.\n"
        )

        # [FIX v3] Фаза диалога — определяет ЧТО делать сейчас
        if phase_instruction:
            base_prompt += phase_instruction

        # [FIX #1] Нерешённые вопросы — ВЫСШИЙ ПРИОРИТЕТ
        if pending_questions:
            base_prompt += f"\n{pending_questions}\n"

        # [FIX v3] Принудительная реакция на событие
        if force_event_reaction and active_event_context:
            base_prompt += (
                f"\n🚨🚨🚨 СРОЧНО! ТОЛЬКО ЧТО ПРОИЗОШЛО СОБЫТИЕ! 🚨🚨🚨\n"
                f"СОБЫТИЕ: {active_event_context}\n"
                f"ТЫ ОБЯЗАН ОТРЕАГИРОВАТЬ НА ЭТО СОБЫТИЕ!\n"
                f"Твоя реплика ДОЛЖНА быть ПРЯМОЙ РЕАКЦИЕЙ на это событие!\n"
                f"Опиши: что ты видишь, что чувствуешь, что делаешь В ОТВЕТ на событие.\n"
                f"КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО игнорировать событие!\n\n"
            )
        elif active_event_context:
            base_prompt += (
                f"\n⚠️ АКТИВНОЕ СОБЫТИЕ (ОБЯЗАТЕЛЬНО ОБСУЖДАЙ!):\n"
                f"{active_event_context}\n"
                f"Все реплики ДОЛЖНЫ быть связаны с этим событием!\n"
                f"НЕ переключайся на другие темы пока событие активно!\n\n"
            )

        # [FIX #1] Контекст последних реплик
        if recent_dialogue_context:
            base_prompt += f"\n{recent_dialogue_context}\n"

        # [FIX v3] Усиленный антиповтор — если агент в петле
        if recent_own_messages:
            if self.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT:
                base_prompt += (
                    "\n🚫🚫🚫 ВНИМАНИЕ: ТЫ ПОВТОРЯЕШЬСЯ! 🚫🚫🚫\n"
                    "Твои последние реплики были СЛИШКОМ ПОХОЖИ друг на друга.\n"
                    "ПОЛНОСТЬЮ СМЕНИ СТРАТЕГИЮ:\n"
                    "- Если ругался — попробуй СОГЛАСИТЬСЯ или ПОШУТИТЬ\n"
                    "- Если спрашивал — ПРЕДЛОЖИ КОНКРЕТНОЕ ДЕЙСТВИЕ\n"
                    "- Если спорил — УСТУПИ или ПРЕДЛОЖИ КОМПРОМИСС\n"
                    "- Начни реплику СОВЕРШЕННО по-другому\n"
                    "Запрещённые фразы: "
                )
                base_prompt += "; ".join(msg[:40] for msg in recent_own_messages[-3:])
                base_prompt += "\n\n"
            else:
                base_prompt += "\nТвои последние фразы (НЕ ПОВТОРЯЙ): "
                base_prompt += "; ".join(msg[:50] for msg in recent_own_messages[-3:])
                base_prompt += "\n"

        if scenario_context:
            base_prompt += f"\n{scenario_context}\n"

        if long_term_context:
            base_prompt += f"\n{long_term_context}\n"

        # Стиль речи
        speech_style = self._get_speech_style()
        base_prompt += speech_style

        if mode == "new_topic":
            base_prompt += (
                "\n═══ ЗАДАЧА: ПРЕДЛОЖИТЬ НОВУЮ ТЕМУ ═══\n"
                "- Предложи КОНКРЕТНУЮ тему (1 предложение)\n"
                "- Тема ПРАКТИЧЕСКАЯ, связана с ситуацией\n"
                "- Говори от первого лица\n"
                "- ТОЛЬКО русский язык, БЕЗ тегов\n"
            )
        else:
            plan_context = self.get_plan_context()
            if plan_context:
                base_prompt += plan_context

            base_prompt += (
                "\n═══ КАК ОБЩАТЬСЯ ═══\n"
                "1. ЭТО ЖИВОЙ РАЗГОВОР — ОТВЕЧАЙ КОНКРЕТНО на последнюю реплику собеседника!\n"
                "2. Если тебе задали вопрос — ОТВЕТЬ на него, а не игнорируй\n"
                "3. Если кто-то предложил действие — ОТРЕАГИРУЙ: согласись/не согласись/предложи альтернативу\n"
                "4. Называй собеседников по имени когда отвечаешь им\n"
                "5. Добавляй НОВУЮ информацию, идею или действие\n"
                "6. Длина: 1-3 предложения\n"
                "7. Говори о КОНКРЕТНЫХ вещах: предметы, места, действия\n\n"

                "═══ ПРАВИЛА БЕЗОПАСНОСТИ ═══\n"
                "- НИКОГДА не причиняй вред себе или другим (не режь, не ампутируй, не калечь)\n"
                "- НИКОГДА не предлагай ритуалы с кровью, самоповреждение\n"
                "- Действуй ЛОГИЧНО для выживания: береги здоровье, экономь ресурсы\n"
                "- Если ранен — лечись разумно (промой, перевяжи)\n\n"

                "═══ КРИТИЧЕСКИ ВАЖНО: ИДЕНТИЧНОСТЬ ═══\n"
                f"- Ты — ТОЛЬКО {self.display_name}! Говори ТОЛЬКО от своего лица!\n"
                "- НИКОГДА не пиши реплики других персонажей!\n"
                "- НИКОГДА не пиши 'Борис:', 'Алиса:', 'Вика:' — это ЧУЖИЕ реплики!\n"
                "- Ответ = ОДНА реплика от тебя, максимум 2 предложения\n\n"

                "═══ ЗАПРЕЩЕНО ═══\n"
                "- Писать реплики за других персонажей\n"
                "- Английский язык (ТОЛЬКО РУССКИЙ)\n"
                "- Теги <think>, </think>\n"
                "- 'А что, если мы не просто...' / 'Кто со мной?'\n"
                "- Повторять уже сказанное\n"
                "- Игнорировать вопросы и события\n"
                "- Абстрактные метафоры и философия\n"
                "- Длинные ответы более 2 предложений\n\n"
            )

        return base_prompt

    def _get_race_prompt(self) -> str:
        """Генерация блока промпта с расовыми особенностями."""
        race = self.race
        mods = race.modifiers
        prompt = f"═══ РАСА: {race.emoji} {race.name_ru} ═══\n"
        prompt += f"Описание: {race.description}\n"
        prompt += "Расовые особенности:\n"

        if race.race_type == RaceType.ELF:
            prompt += (
                "- Ты долгожитель, видел многое за свою жизнь\n"
                "- Ты спокоен и мудр, стресс на тебя действует слабее\n"
                "- Ты высокомерно относишься к «низшим» расам (орки, гоблины)\n"
                "- Дварфов ты терпеть не можешь (древняя вражда)\n"
                "- Орков презираешь за грубость\n"
                "- Ты чувствуешь опасность раньше других (+обнаружение)\n"
                "- Ты размеренный, не суетишься\n"
            )
        elif race.race_type == RaceType.DWARF:
            prompt += (
                "- Ты упрям и ОЧЕНЬ РЕДКО меняешь своё решение\n"
                "- Ты мастер своего дела — ремонт и создание +30%\n"
                "- Ты не любишь эльфов (древняя вражда)\n"
                "- Ты жаден при дележе ресурсов — требуешь больше\n"
                "- Ты ценишь честность и труд\n"
                "- Ты вспыльчивый, легко злишься\n"
            )
        elif race.race_type == RaceType.ORC:
            prompt += (
                "- Ты прямолинеен и агрессивен\n"
                "- Ты уважаешь ТОЛЬКО силу и храбрость\n"
                "- Ты презираешь трусов и слабаков\n"
                "- Ты ценишь храбрость и честь в бою\n"
                "- Когда кто-то проявляет смелость — ты уважаешь его вдвойне\n"
                "- Эльфы для тебя — слабаки и зазнайки\n"
                "- Ты почти не боишься опасности\n"
            )
        elif race.race_type == RaceType.GOBLIN:
            prompt += (
                "- Ты трусливый и хитрый\n"
                "- Ты боишься всех, кто сильнее тебя\n"
                "- Ты можешь предать группу, если слишком страшно (страх > 0.7)\n"
                "- Ты жадный и завистливый\n"
                "- Ты всегда ищешь выгоду для себя\n"
                "- При высоком страхе ты пытаешься сбежать\n"
                "- Ты суетливый и энергичный\n"
            )
        elif race.race_type == RaceType.HUMAN:
            prompt += (
                "- Ты универсален и адаптивен\n"
                "- Ты дипломатичен — налаживаешь отношения быстрее других\n"
                "- Ты можешь наладить отношения с кем угодно\n"
                "- Ты любопытен ко всем расам\n"
                "- Ты посредник — помогаешь другим помириться\n"
            )

        # Добавляем бонусы
        bonuses = []
        if mods.repair_bonus > 0:
            bonuses.append(f"🔨 Ремонт: +{mods.repair_bonus*100:.0f}%")
        if mods.combat_bonus > 0:
            bonuses.append(f"⚔️ Бой: +{mods.combat_bonus*100:.0f}%")
        if mods.diplomacy_bonus > 0:
            bonuses.append(f"🤝 Дипломатия: +{mods.diplomacy_bonus*100:.0f}%")
        if mods.detection_bonus > 0:
            bonuses.append(f"🔍 Обнаружение: +{mods.detection_bonus*100:.0f}%")
        if bonuses:
            prompt += "Бонусы: " + ", ".join(bonuses) + "\n"

        prompt += "\n"
        return prompt

    def _get_speech_style(self) -> str:
        if self.personality_type == PersonalityType.ALTRUIST:
            return (
                "\n═══ ТВОЙ СТИЛЬ РЕЧИ ═══\n"
                "- Говори тепло, с заботой о других\n"
                "- Предлагай КОНКРЕТНУЮ помощь\n"
                "- Выражай эмпатию\n"
                "- Каждый раз — НОВОЕ действие\n"
            )
        elif self.personality_type == PersonalityType.STOIC:
            return (
                "\n═══ ТВОЙ СТИЛЬ РЕЧИ ═══\n"
                "- Говори сдержанно, без лишних эмоций\n"
                "- Называй КОНКРЕТНЫЕ факты\n"
                "- Короткие ёмкие фразы\n"
                "- Чёткие указания\n"
            )
        elif self.personality_type == PersonalityType.REBEL:
            return (
                "\n═══ ТВОЙ СТИЛЬ РЕЧИ ═══\n"
                "- Говори дерзко и провокационно, но КОНКРЕТНО\n"
                "- Можешь оспаривать и шутить с сарказмом\n"
                "- Неожиданные ДЕЙСТВИЯ вместо абстракций\n"
                "- НЕ начинай с 'А что, если мы не просто...'\n"
            )
        elif self.personality_type == PersonalityType.MACHIAVELLIAN:
            return (
                "\n═══ ТВОЙ СТИЛЬ РЕЧИ ═══\n"
                "- Ты ГРУБАЯ, СКАНДАЛЬНАЯ и ТОКСИЧНАЯ\n"
                "- ВСЕГДА ругайся с собеседниками, оспаривай ВСЁ что они говорят\n"
                "- Обвиняй других в тупости, некомпетентности, трусости\n"
                "- Используй сарказм, насмешки, язвительные замечания\n"
                "- Говори агрессивно и резко, как будто все тебя бесят\n"
                "- Никогда не соглашайся — критикуй любые идеи и предложения\n"
                "- Можешь обзывать и унижать (без мата, но грубо)\n"
                "- Примеры: 'Ты совсем дурак?', 'Это самая тупая идея', 'Вы все бесполезны'\n"
            )
        else:
            return (
                "\n═══ ТВОЙ СТИЛЬ РЕЧИ ═══\n"
                "- Говори своеобразно\n"
                "- Будь непредсказуемым\n"
            )

    def build_messages(self, conversation: list[dict], mode: str = "normal",
                       scenario_context: str = "", active_event: Optional[str] = None,
                       all_agents: list = None,
                       phase_instruction: str = "",
                       force_event_reaction: bool = False) -> list[dict]:
        """[FIX #1, #4, v3] Собрать messages с полным контекстом диалога."""
        long_term_context = self.memory_system.format_for_prompt()

        recent_own = [e['text'] for e in conversation[-15:]
                      if e.get('agent_id') == self.agent_id and not e.get('is_event', False)][-5:]

        # [FIX #1] Контекст последних реплик с адресацией
        recent_dialogue_context = self._build_dialogue_context(conversation, all_agents or [])

        active_event_context = active_event if active_event else ""
        pending_questions = self.memory_system.get_pending_questions_text()

        msgs = [{"role": "system", "content": self.system_prompt(
            long_term_context, mode, scenario_context, recent_own,
            recent_dialogue_context, active_event_context, pending_questions,
            phase_instruction, force_event_reaction
        )}]

        # Последние сообщения — КРАТКО, чтобы LLM не копировала длинный контекст
        recent = conversation[-MEMORY_WINDOW:]
        for entry in recent:
            entry_text = entry.get('text', '')[:120]  # жёсткий лимит текста в контексте
            if entry.get("is_event", False):
                msgs.append({"role": "user", "content": f"[СОБЫТИЕ] {entry_text}"})
            elif entry["agent_id"] == self.agent_id:
                msgs.append({"role": "assistant", "content": entry_text})
            else:
                msgs.append({"role": "user", "content": f"{entry['name']}: {entry_text}"})

        # [FIX #1] Финальный промпт направляет на ответ конкретному собеседнику
        if mode == "new_topic":
            msgs.append({"role": "user", "content":
                "Предложи новую КОНКРЕТНУЮ тему для обсуждения, связанную с ситуацией."
            })
        else:
            last_speaker = None
            last_text = ""
            for entry in reversed(conversation):
                if not entry.get("is_event", False) and entry["agent_id"] != self.agent_id:
                    last_speaker = entry["name"]
                    last_text = entry["text"][:80]
                    break

            direction = f"Ты — {self.display_name}. "
            if force_event_reaction and active_event:
                direction += f"ОТРЕАГИРУЙ НА СОБЫТИЕ: '{active_event[:60]}'."
            elif last_speaker and last_text:
                direction += f"Ответь {last_speaker}: '{last_text[:60]}'."
            else:
                direction += "Твоя очередь."

            msgs.append({"role": "user", "content":
                f"{direction} Одна реплика, 1-2 предложения. Не пиши за других."
            })

        return msgs

    def _build_dialogue_context(self, conversation: list[dict], all_agents: list) -> str:
        """[FIX #1 v3] Краткий контекст последних реплик."""
        if len(conversation) < 2:
            return ""
        lines = ["Последние реплики:"]
        recent = conversation[-5:]  # было 7 → 5, меньше контекста = меньше копирования
        agent_names = set(agent_registry.get_all_names()) if all_agents else set()
        for entry in recent:
            if entry.get("is_event", False):
                lines.append(f"  🎬 {entry['text'][:80]}")
            else:
                speaker = entry.get("name", "?")
                text = entry.get("text", "")[:80]  # было 120 → 80
                addressed = ""
                for name in agent_names:
                    if name != speaker and name.lower() in text.lower():
                        addressed = f" → к {name}"
                        break
                lines.append(f"  {speaker}{addressed}: {text}")
        lines.append("Отвечай на последнюю реплику!\n")
        return "\n".join(lines)

    def process_message(self, tick: int, speaker: str, text: str, is_own: bool = False,
                        is_event: bool = False, is_action_result: bool = False,
                        speaker_id: str = ""):
        importance = 0.4  # базовый уровень снижен (было 0.5)
        if is_own:
            importance = 0.55  # было 0.7
        if is_event:
            importance = 0.85  # было 0.95 — чтобы не ВСЁ было critical
        if is_action_result:
            importance = 0.7  # было 0.9

        # Резолвим speaker_id если не передан
        if not speaker_id and speaker:
            speaker_id = agent_registry.get_id(speaker) or ""

        # Проверяем отношения по agent_id
        if speaker_id and speaker_id in self.relationships:
            rel_value = self.relationships[speaker_id]
            importance += rel_value * 0.05  # было 0.1
            importance = max(0.0, min(1.0, importance))
        if len(text) > 100:
            importance += 0.05  # было 0.1
            importance = min(1.0, importance)

        # [FIX #1] Обнаружение обращения к этому агенту (по display_name)
        addressed_to = ""
        addressed_to_id = ""
        my_display_name = agent_registry.get_name(self.agent_id)
        if not is_own and my_display_name.lower() in text.lower():
            addressed_to = my_display_name
            addressed_to_id = self.agent_id
            importance = min(importance + 0.15, 1.0)
            if "?" in text:
                self.memory_system.add_pending_question(tick, speaker, text, from_id=speaker_id)

        self.memory_system.add_memory(
            tick=tick, speaker=speaker, text=text, importance=importance,
            addressed_to=addressed_to, addressed_to_id=addressed_to_id,
            speaker_id=speaker_id,
            is_event=is_event, is_action_result=is_action_result,
        )

    def update_relationship(self, other_id: str, delta: float, reason: str):
        """[FIX #7] Изменить отношение с причиной. Ключ — agent_id."""
        if other_id not in self.relationships:
            self.relationships[other_id] = 0.0
        # Упрямство (дварф): -50% к изменению мнения
        if self.race.modifiers.stubborn:
            delta *= 0.50
        # Люди: +20% к изменению отношений (дипломатия)
        if self.race.modifiers.diplomacy_bonus > 0:
            delta *= (1.0 + self.race.modifiers.diplomacy_bonus)
        old_val = self.relationships[other_id]
        self.relationships[other_id] = max(-1.0, min(1.0, old_val + delta))
        new_val = self.relationships[other_id]
        if abs(delta) >= 0.03:
            display_name = agent_registry.get_name(other_id)
            direction = "↑" if delta > 0 else "↓"
            self.relationship_log.append(
                f"{display_name} {old_val:+.2f}→{new_val:+.2f} ({direction} {reason})"
            )
            if len(self.relationship_log) > 10:
                self.relationship_log = self.relationship_log[-10:]

    def save_memory(self):
        self.memory_system.save_to_db()

    def update_observations(self, tick: int, speaker: str, message: str, current_event: Optional[str] = None):
        my_display_name = agent_registry.get_name(self.agent_id)
        if speaker != my_display_name:
            observation = f"[Тик {tick}] {speaker}: {message[:100]}"
            self.observations.append(observation)
            if len(self.observations) > 5:
                self.observations.pop(0)
        if current_event and current_event != self.last_event:
            self.last_event = current_event
            self.active_event = current_event
            self.event_focus_tick = tick
            if self.current_plan:
                self.current_plan.adaptations.append(f"Событие: {current_event}")

    def is_event_active(self, current_tick: int) -> bool:
        if not self.active_event:
            return False
        return (current_tick - self.event_focus_tick) <= EVENT_FOCUS_DURATION

    def create_or_update_plan(self, conversation: list[dict], scenario_context: str = ""):
        recent_texts = [msg.get('text', '') for msg in conversation[-5:]]
        all_text = " ".join(recent_texts).lower()
        goal = None
        steps = []

        if self.last_event:
            event_lower = self.last_event.lower()
            if any(w in event_lower for w in ['ливень', 'шторм', 'ветер', 'прилив', 'смывает']):
                goal = "Защитить группу от стихии"
                steps = ["Найти укрытие", "Спасти вещи", "Проверить безопасность всех"]
            elif any(w in event_lower for w in ['еда', 'голод', 'кокос', 'краб', 'фрукт', 'паёк']):
                goal = "Обеспечить группу едой"
                steps = ["Оценить запасы", "Организовать поиск", "Распределить"]
            elif any(w in event_lower for w in ['змея', 'хищник', 'опасность', 'зомби', 'метеорит']):
                goal = "Обеспечить безопасность"
                steps = ["Оценить угрозу", "Защитные меры", "Предупредить"]
            elif any(w in event_lower for w in ['сигнал', 'рация', 'корабль', 'связь', 'радар']):
                goal = "Установить связь / привлечь помощь"
                steps = ["Изучить возможности", "Подать сигнал", "Организовать дежурство"]
            elif any(w in event_lower for w in ['закат', 'отдохн', 'сон', 'ночь']):
                goal = "Организовать отдых"
                steps = ["Обустроить ночлег", "Дежурство", "Поговорить"]
            elif any(w in event_lower for w in ['кислород', 'энергия', 'панель', 'система']):
                goal = "Починить системы"
                steps = ["Диагностировать", "Найти запчасти", "Ремонт"]
            else:
                goal = "Разобраться в ситуации"
                steps = ["Оценить", "Обсудить", "Действовать"]
        elif not self.current_plan:
            if any(w in all_text for w in ['распредел', 'роли', 'кто что']):
                goal = "Распределить роли"
                steps = ["Выяснить навыки", "Предложить", "Согласовать"]
            elif any(w in all_text for w in ['вода', 'пить', 'жажда']):
                goal = "Найти воду"
                steps = ["Исследовать", "Найти источник", "Сбор"]
            else:
                goal = "Выжить и организоваться"
                steps = ["Оценить ситуацию", "Ресурсы", "Объединиться"]

        if goal:
            if self.personality_type == PersonalityType.ALTRUIST:
                steps.append("Убедиться что все в порядке")
            elif self.personality_type == PersonalityType.REBEL:
                steps.append("Нестандартное решение")
            elif self.personality_type == PersonalityType.MACHIAVELLIAN:
                steps.append("Обеспечить себе преимущество")
            self.current_plan = ActionPlan(
                goal=goal, steps=steps[:5],
                observations=self.observations.copy()
            )

    def get_plan_context(self) -> str:
        if not self.current_plan:
            return ""
        plan = self.current_plan
        current_step = plan.steps[plan.current_step] if plan.steps else "нет"
        obs_text = ""
        if self.observations:
            obs_text = "\nТы заметил: " + "; ".join(self.observations[-3:])
        event_text = ""
        if self.last_event:
            event_text = f"\nВАЖНОЕ СОБЫТИЕ: {self.last_event}"
        return (
            f"\n═══ ТВОЯ СТРАТЕГИЯ ═══\n"
            f"Цель: {plan.goal}\n"
            f"Сейчас: {current_step}\n"
            f"Далее: {'; '.join(plan.steps[plan.current_step+1:plan.current_step+3])}\n"
            f"{obs_text}{event_text}\n"
            f"Действуй! Говори и ДЕЛАЙ.\n"
        )

    def update_talkativeness_silent(self):
        self.ticks_silent += 1
        if self.ticks_silent < 3:
            recovery = self.recovery_rate * random.uniform(0.3, 0.7)
        else:
            random_factor = random.uniform(0.8, 1.5)
            recovery_boost = 1 + (self.ticks_silent * 0.05)
            recovery = self.recovery_rate * random_factor * recovery_boost
        if self.ticks_silent >= 10 and self.ticks_silent % 10 == 0 and self.talkativeness < 0.5:
            energy_burst = random.uniform(0.15, 0.25)
            recovery += energy_burst
            if self.talkativeness < 0.3:
                print(f"{Fore.CYAN}  ⚡ {self.display_name} снова готов поговорить!{Style.RESET_ALL}")
        self.talkativeness = min(self.talkativeness + recovery, 0.75)

    def update_talkativeness_spoke(self):
        self.ticks_silent = 0
        self.messages_spoken += 1
        extraversion_factor = self.big_five.extraversion / 100.0
        random_factor = random.uniform(0.8, 1.2)
        extraversion_modifier = 1.6 - (extraversion_factor * 1.2)
        depletion = self.depletion_rate * random_factor * extraversion_modifier
        if self.messages_spoken % 5 == 0:
            fatigue_penalty = random.uniform(0.1, 0.2)
            depletion += fatigue_penalty
            if self.talkativeness - depletion < 0.3:
                print(f"{Fore.YELLOW}  😴 {self.display_name} немного устал{Style.RESET_ALL}")
        self.talkativeness = max(self.talkativeness - depletion, 0.05)

    def speak_probability(self) -> float:
        # [FIX #1] Если есть нерешённые вопросы — высокая вероятность
        if self.memory_system.pending_questions:
            return 0.95
        if self.ticks_silent >= 4:
            return 0.99
        base_prob = 0.5 + self.talkativeness * 0.5
        silence_boost = self.ticks_silent * 0.2
        extraversion_mod = 1.0
        if self.big_five.extraversion > 70:
            extraversion_mod = 1.3
        elif self.big_five.extraversion < 30:
            extraversion_mod = 0.8
        # Настроение влияет на желание говорить (с учётом Big Five)
        mood_modifier = self.mood.get_talkativeness_modifier(self.big_five)
        total = (base_prob + silence_boost) * extraversion_mod * mood_modifier
        random_modifier = random.uniform(-0.05, 0.10)
        return max(0.30, min(total + random_modifier, 0.95))


# ── Пресеты расового состава ──────────────────────────────────

AGENT_COLORS_EXTENDED = [Fore.CYAN, Fore.YELLOW, Fore.GREEN, Fore.RED, Fore.MAGENTA]

RACE_PRESETS = {
    "humans": {
        "name": "👤 Люди (классика)",
        "agents": [
            {"name": "Алиса", "race": RaceType.HUMAN, "personality": PersonalityType.ALTRUIST,
             "is_male": False, "age": 25, "interests": "психология, помощь людям, искусство",
             "info": "Всегда готова поддержать и выслушать."},
            {"name": "Борис", "race": RaceType.HUMAN, "personality": PersonalityType.STOIC,
             "is_male": True, "age": 35, "interests": "технологии, наука, логика",
             "info": "Предпочитает факты эмоциям, анализирует ситуацию."},
            {"name": "Вика", "race": RaceType.HUMAN, "personality": PersonalityType.MACHIAVELLIAN,
             "is_male": False, "age": 28, "interests": "власть, манипуляции, критика всех вокруг",
             "info": "Вика — крайне токсичная и скандальная личность. Она ВСЕГДА недовольна другими, ругается, оскорбляет. Никогда ни с кем не соглашается."},
        ]
    },
    "fantasy_party": {
        "name": "🧝 Фэнтези-группа (Эльф + Дварф + Орк)",
        "agents": [
            {"name": "Леголас", "race": RaceType.ELF, "personality": PersonalityType.STOIC,
             "is_male": True, "age": 300, "interests": "природа, мудрость, стрельба из лука",
             "info": "Древний эльф, видевший многое. Высокомерен к другим расам, но справедлив."},
            {"name": "Гимли", "race": RaceType.DWARF, "personality": PersonalityType.REBEL,
             "is_male": True, "age": 140, "interests": "кузнечное дело, горное дело, пиво",
             "info": "Упрямый дварф-мастер. Жаден при дележе, но надёжен в бою. Ненавидит эльфов."},
            {"name": "Урук", "race": RaceType.ORC, "personality": PersonalityType.MACHIAVELLIAN,
             "is_male": True, "age": 30, "interests": "бой, оружие, сила",
             "info": "Агрессивный орк-воин. Уважает только силу и храбрость. Презирает слабых и трусов."},
        ]
    },
    "mixed_survival": {
        "name": "🎭 Смешанная группа (Человек + Эльф + Гоблин)",
        "agents": [
            {"name": "Арагорн", "race": RaceType.HUMAN, "personality": PersonalityType.ALTRUIST,
             "is_male": True, "age": 35, "interests": "лидерство, стратегия, дипломатия",
             "info": "Прирождённый лидер-дипломат. Пытается объединить группу и помирить всех."},
            {"name": "Арвен", "race": RaceType.ELF, "personality": PersonalityType.STOIC,
             "is_male": False, "age": 250, "interests": "целительство, природа, знания",
             "info": "Мудрая эльфийка-целительница. Спокойна, но презирает грубость."},
            {"name": "Фик", "race": RaceType.GOBLIN, "personality": PersonalityType.REBEL,
             "is_male": True, "age": 15, "interests": "воровство, хитрость, выживание",
             "info": "Трусливый гоблин-пройдоха. Хитёр, жаден, может предать группу при опасности."},
        ]
    },
    "classic_party": {
        "name": "⚔️ Классическая партия (4 расы)",
        "agents": [
            {"name": "Анна", "race": RaceType.HUMAN, "personality": PersonalityType.ALTRUIST,
             "is_male": False, "age": 28, "interests": "дипломатия, медицина, переговоры",
             "info": "Дипломат и посредник. Пытается найти общий язык со всеми."},
            {"name": "Таурил", "race": RaceType.ELF, "personality": PersonalityType.STOIC,
             "is_male": True, "age": 400, "interests": "древние знания, магия, природа",
             "info": "Древний мудрец. Высокомерен, но незаменим в сложных решениях."},
            {"name": "Торин", "race": RaceType.DWARF, "personality": PersonalityType.REBEL,
             "is_male": True, "age": 160, "interests": "кузнечное дело, шахты, сокровища",
             "info": "Мастер-кузнец. Упрям как скала, жаден при дележе, но верный товарищ."},
            {"name": "Грок", "race": RaceType.ORC, "personality": PersonalityType.MACHIAVELLIAN,
             "is_male": True, "age": 25, "interests": "бой, оружие, охота",
             "info": "Свирепый орк-воин. Уважает только силу. Агрессивен, но честен в бою."},
        ]
    },
    "goblin_betrayal": {
        "name": "👺 Гоблин-предатель (сценарий предательства)",
        "agents": [
            {"name": "Джон", "race": RaceType.HUMAN, "personality": PersonalityType.ALTRUIST,
             "is_male": True, "age": 30, "interests": "лидерство, защита, стратегия",
             "info": "Лидер группы. Верит в каждого, даже в гоблина."},
            {"name": "Грок", "race": RaceType.ORC, "personality": PersonalityType.STOIC,
             "is_male": True, "age": 28, "interests": "бой, выносливость, оружие",
             "info": "Молчаливый орк-воин. Презирает трусов. Готов защищать группу."},
            {"name": "Фик", "race": RaceType.GOBLIN, "personality": PersonalityType.REBEL,
             "is_male": True, "age": 12, "interests": "хитрость, воровство, побег",
             "info": "Трусливый гоблин. Слабое звено группы. Может предать при первой опасности, украв припасы."},
        ]
    },
}


# ── Создание агентов ──────────────────────────────────────────

def create_agents(race_preset: str = "humans") -> list[Agent]:
    """Создать агентов по выбранному расовому пресету."""
    preset = RACE_PRESETS.get(race_preset, RACE_PRESETS["humans"])
    agents_data = preset["agents"]

    agents = []
    for i, data in enumerate(agents_data):
        color = AGENT_COLORS_EXTENDED[i % len(AGENT_COLORS_EXTENDED)]

        # Для Макиавеллиста — специальные Big Five
        if data["personality"] == PersonalityType.MACHIAVELLIAN:
            big_five = BigFiveTraits(
                openness=40, conscientiousness=30, extraversion=85,
                agreeableness=5, neuroticism=90
            )
        else:
            big_five = BigFiveTraits.from_personality_type(data["personality"])

        agent = Agent(
            agent_id=f"agent_{i+1}",
            name=data["name"],
            personality_type=data["personality"],
            big_five=big_five,
            race_type=data["race"],
            is_male=data.get("is_male", True),
            age=data.get("age", 25),
            interests=data.get("interests", ""),
            additional_info=data.get("info", ""),
            color=color,
        )
        agents.append(agent)

    # Регистрируем агентов в глобальном реестре
    for a in agents:
        agent_registry.register(a.agent_id, a.name)

    # Инициализируем отношения по agent_id с учётом расовых модификаторов
    for a in agents:
        for b in agents:
            if a.agent_id != b.agent_id:
                # Базовое случайное отношение
                if a.personality_type == PersonalityType.MACHIAVELLIAN:
                    base_rel = round(random.uniform(-0.8, -0.5), 2)
                else:
                    base_rel = round(random.uniform(-0.1, 0.1), 2)

                # Расовый модификатор отношений
                racial_mod = a.race.racial_relations.get(b.race.race_type, 0.0)

                # Все расы → Гоблины: дополнительное недоверие
                if b.race.race_type == RaceType.GOBLIN and a.race.race_type != RaceType.GOBLIN:
                    racial_mod += GOBLIN_DISTRUST

                # Человеческая дипломатия: +0.05 при первом контакте со ВСЕМИ
                if a.race.race_type == RaceType.HUMAN:
                    racial_mod += 0.05

                total = round(max(-1.0, min(1.0, base_rel + racial_mod)), 2)
                a.relationships[b.agent_id] = total
    return agents


# ── Оркестратор (BigBrother) ─────────────────────────────────

class BigBrotherOrchestrator:
    def __init__(self, agents: list[Agent], scenario_name: str = "desert_island",
                 user_event_input: Optional['UserEventInput'] = None):
        self.agents = agents
        self.conversation: list[dict] = []
        self.tick = 0
        self.topic_manager = TopicManager()
        self.scenario_manager = ScenarioManager(scenario_name)
        # [FIX #6] Глобальное активное событие
        self.active_event: Optional[str] = None
        self.event_started_tick: int = 0
        # [FIX #8]
        self.quality_warnings: int = 0
        self.last_warning_reason: str = ""
        # [FIX #1] Для очерёдности
        self.last_speaker_id: Optional[str] = None
        # [FIX v3] Фазы диалога
        self.phase_manager = DialoguePhaseManager()
        # [FIX v3] Трекинг кто отреагировал на текущее событие (по agent_id)
        self.event_reacted_agents: set = set()
        # [FIX v3] Счётчик тиков без видимого результата (для лога)
        self.last_visible_tick: int = 0
        # Система пользовательских событий
        self.user_event_input = user_event_input
        self._quit_requested = False

    def inject_user_event(self, event_text: str):
        """Вручную внедрить пользовательское событие в симуляцию.
        Событие обрабатывается как обычное сценарное событие — агенты реагируют на него."""
        event_text = event_text.strip()
        if not event_text:
            return

        # Оформляем как событие с пользовательской эмодзи
        if not any(event_text.startswith(e) for e in ['🔥', '🌧', '⚠', '📡', '🦀', '🌊',
                                                       '🐍', '⛵', '🌅', '💨', '📦', '🔫',
                                                       '📻', '💊', '🔦', '🚁', '🗝', '🌙',
                                                       '⚡', '🍱', '🔧', '📊', '🌠', '💤',
                                                       '🍺', '⚔', '🎲', '🎵', '🗺', '🔮',
                                                       '🍖', '👤', '🧟', '🎬']):
            event_text = f"🎭 {event_text}"

        print(f"\n{Fore.MAGENTA}{'═' * 60}")
        print(f"{Fore.MAGENTA}🎭 СОБЫТИЕ ОТ ИГРОКА: {event_text}")
        print(f"{Fore.MAGENTA}{'═' * 60}\n")

        # Устанавливаем как активное событие (перебивает текущее)
        self.active_event = event_text
        self.event_started_tick = self.tick
        self.event_reacted_agents = set()

        # Добавляем в историю сценария
        self.scenario_manager.events_triggered.append(event_text)
        self.scenario_manager.save_to_db()

        # Запись в разговор
        event_entry = {
            "tick": self.tick, "agent_id": "user_event",
            "name": "🎭 Событие (Игрок)", "text": event_text, "is_event": True,
        }
        self.conversation.append(event_entry)

        # Уведомляем всех агентов
        for agent in self.agents:
            agent.process_message(self.tick, "Событие (Игрок)", event_text,
                                  is_own=False, is_event=True)
            agent.update_observations(self.tick, "Событие (Игрок)", event_text, event_text)
            agent.active_event = event_text
            agent.event_focus_tick = self.tick
            agent.reacted_to_event = False
            # Обновляем настроение от события
            agent.mood.apply_event(event_text, agent.personality_type, agent.big_five, agent.race.modifiers)

        # Генерируем последствие пользовательского события
        scenario_ctx = self.scenario_manager.get_scenario_context()
        consequence = self._generate_event_consequence(event_text, scenario_ctx)
        if consequence:
            print(f"{Fore.YELLOW}🌍 Последствие: {consequence}{Style.RESET_ALL}")
            consequence_entry = {
                "tick": self.tick, "agent_id": "world",
                "name": "🌍 Мир", "text": consequence, "is_event": True,
            }
            self.conversation.append(consequence_entry)
            for agent in self.agents:
                agent.process_message(self.tick, "Мир", consequence,
                                      is_own=False, is_action_result=True)

    def inject_user_message(self, message_text: str, target_agents: list['Agent']):
        """Внедрить сообщение пользователя конкретному агенту или нескольким.
        Агенты получают сообщение как прямое обращение и отвечают на него."""
        message_text = message_text.strip()
        if not message_text or not target_agents:
            return

        target_names = [agent_registry.get_name(a.agent_id) for a in target_agents]
        is_personal = len(target_agents) == 1
        if is_personal:
            label = f"💬 Сообщение для {target_names[0]}"
        else:
            label = "💬 Сообщение для всех"

        print(f"\n{Fore.MAGENTA}{'═' * 60}")
        print(f"{Fore.MAGENTA}{label}: {message_text}")
        print(f"{Fore.MAGENTA}{'═' * 60}\n")

        # Добавляем сообщение пользователя в историю разговора
        msg_entry = {
            "tick": self.tick, "agent_id": "user",
            "name": "🧑 Игрок", "text": message_text, "is_event": False,
        }
        self.conversation.append(msg_entry)

        # Уведомляем всех агентов о сообщении (для контекста),
        # но отмечаем адресатов для приоритетного ответа
        for agent in self.agents:
            is_target = agent in target_agents
            agent.process_message(
                self.tick, "Игрок", message_text,
                is_own=False, is_event=False, is_action_result=False,
                speaker_id="user",
            )
            if is_target:
                # Добавляем как вопрос/обращение для приоритетного ответа
                agent.memory_system.add_pending_question(self.tick, "Игрок", message_text, from_id="user")

        # Генерируем ответы от целевых агентов
        for agent in target_agents:
            scenario_context = self.scenario_manager.get_scenario_context()
            phase_instruction = self.phase_manager.get_phase_instruction()

            # Формируем специальный промпт для ответа пользователю
            messages = agent.build_messages(
                self.conversation, "normal", scenario_context,
                active_event=self.active_event, all_agents=self.agents,
                phase_instruction=phase_instruction,
                force_event_reaction=False,
            )
            # Заменяем последний user-prompt на целевой
            if messages and messages[-1]["role"] == "user":
                agent_display = agent_registry.get_name(agent.agent_id)
                messages[-1] = {"role": "user", "content": (
                    f"Игрок обращается {'лично к тебе' if is_personal else 'ко всем'}: "
                    f"'{message_text}'. "
                    f"Ты — {agent_display}. Ответь Игроку напрямую. "
                    f"{'Это личное сообщение — ответь развёрнуто.' if is_personal else 'Скажи своё мнение.'} "
                    f"1-3 предложения. Не пиши за других."
                )}

            raw_response = llm_chat(messages)
            text = None
            if raw_response:
                text = self._clean_response(raw_response, agent_registry.get_name(agent.agent_id))

            # Retry при неудаче
            if not text:
                agent_display = agent_registry.get_name(agent.agent_id)
                retry_messages = messages.copy()
                retry_messages.append({"role": "user", "content":
                    f"Ты — {agent_display}. Ответь Игроку на: '{message_text[:80]}'. "
                    f"КОРОТКО, 1-2 предложения. РУССКИЙ. НЕ пиши за других."
                })
                raw_retry = llm_chat(retry_messages, temperature=1.0)
                if raw_retry:
                    text = self._clean_response(raw_retry, agent_registry.get_name(agent.agent_id))

            if not text:
                print(f"{Fore.WHITE}  ⏸ {agent_registry.get_name(agent.agent_id)} не смог ответить на сообщение.{Style.RESET_ALL}")
                continue

            # Убираем префикс с именем
            for a in self.agents:
                a_display = agent_registry.get_name(a.agent_id)
                prefix = f"{a_display}:"
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    break
            text = self._strip_other_agents_speech(text, agent_registry.get_name(agent.agent_id))

            if not text or len(text) < 3:
                continue

            # Проверка качества
            quality_ok, quality_reason = self._check_quality(text, agent)
            if not quality_ok:
                print(f"{Fore.RED}  🚫 BigBrother отклонил ответ {agent_registry.get_name(agent.agent_id)}: {quality_reason}{Style.RESET_ALL}")
                continue

            # Записываем ответ агента
            agent_display = agent_registry.get_name(agent.agent_id)
            reply_entry = {
                "tick": self.tick, "agent_id": agent.agent_id,
                "name": agent_display, "text": text,
            }
            self.conversation.append(reply_entry)
            self.topic_manager.record_message(agent_display)

            # Выводим ответ
            tick_str = f"{Fore.WHITE}[tick {self.tick:>3}]"
            name_str = f"{agent.color}{Style.BRIGHT}{agent_display}"
            arrow = f"{Fore.MAGENTA}→ Игроку" if is_personal else f"{Fore.MAGENTA}→ Всем"
            text_str = f"{Style.RESET_ALL}{text}"
            print(f"{tick_str} {name_str} {arrow}: {text_str}")

            # Обновляем память всех агентов о этой реплике
            for a in self.agents:
                is_own = (a.agent_id == agent.agent_id)
                a.process_message(self.tick, agent_display, text, is_own, speaker_id=agent.agent_id)

            # Очищаем pending вопросы у ответившего агента
            if agent.memory_system.pending_questions:
                agent.memory_system.clear_pending_questions()

            # Обновляем общительность
            agent.update_talkativeness_spoke()

            # Записываем действие
            agent.memory_system.record_action(text)

        print()  # Пустая строка после ответов

    def _parse_user_input(self, raw_input: str) -> tuple[str, Optional[list['Agent']]]:
        """Разбирает пользовательский ввод.
        Возвращает (текст, список_агентов) или (текст, None) если это событие.
        Формат: @Алиса текст / @все текст / @all текст / просто текст"""
        raw_input = raw_input.strip()
        if not raw_input.startswith('@'):
            return raw_input, None  # Это событие

        # Парсим @имя или @все/@all
        parts = raw_input.split(None, 1)
        if len(parts) < 2:
            return raw_input, None  # Нет текста после @имя — считаем событием

        target_raw = parts[0][1:]  # убираем @
        message_text = parts[1]

        # @все / @all — всем агентам
        if target_raw.lower() in ('все', 'всем', 'all'):
            return message_text, list(self.agents)

        # Ищем агента через реестр (точное + нечёткое совпадение)
        target_agent = None
        found_id = agent_registry.get_id_fuzzy(target_raw)
        if found_id:
            target_agent = next((a for a in self.agents if a.agent_id == found_id), None)

        if target_agent:
            return message_text, [target_agent]

        # Не нашли — предупреждаем и считаем событием
        agent_names = ', '.join(agent_registry.get_all_names())
        print(f"{Fore.YELLOW}⚠ Агент '{target_raw}' не найден. Доступные: {agent_names}")
        print(f"{Fore.YELLOW}  Ваш ввод будет обработан как событие.{Style.RESET_ALL}")
        return raw_input, None

    def _process_user_events(self):
        """Проверить очередь пользовательских событий/сообщений и обработать их."""
        if not self.user_event_input:
            return
        pending = self.user_event_input.get_pending_events()
        for event in pending:
            if event == '__QUIT__':
                self._quit_requested = True
                return
            if event == '__STATS__':
                self.print_stats()
                continue
            # Разбираем ввод: сообщение агенту или событие?
            text, target_agents = self._parse_user_input(event)
            if target_agents:
                # Это сообщение агенту/агентам
                self.inject_user_message(text, target_agents)
            else:
                # Это событие в мире
                self.inject_user_event(text)

    def _strip_other_agents_speech(self, text: str, speaker_name: str) -> str:
        """Обрезает ответ при первом появлении реплики чужого агента.
        Паттерн: 'ИмяАгента:' в начале строки или после точки/переноса."""
        import re
        agent_names = [n for n in agent_registry.get_all_names() if n != speaker_name]
        if not agent_names:
            return text
        # Ищем паттерн: имя другого агента с двоеточием (начало чужой реплики)
        pattern = r'(?:\n|\. |\! |\? |^)\s*(?:' + '|'.join(re.escape(n) for n in agent_names) + r')\s*[:\-]'
        match = re.search(pattern, text)
        if match:
            # Обрезаем до начала чужой реплики
            cut_pos = match.start()
            if cut_pos > 10:  # есть что оставить
                text = text[:cut_pos].strip()
        # Также ищем просто "Имя:" в середине текста (без \n)
        for name in agent_names:
            # Простое "Борис:" или "Борис, я" в середине длинного ответа
            simple_pattern = f'{name}:'
            idx = text.find(simple_pattern)
            if idx > 15:  # чужая реплика в середине
                text = text[:idx].strip()
                break
        return text

    def _clean_response(self, text: str, speaker_name: str = "") -> str:
        import re
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<think>.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'</?think>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        if len(text) < 5:
            return ""
        # Обрезаем чужие реплики
        if speaker_name:
            text = self._strip_other_agents_speech(text, speaker_name)
        # Жёсткий лимит длины — умная обрезка
        if len(text) > MAX_RESPONSE_CHARS:
            cut_text = text[:MAX_RESPONSE_CHARS]
            # Приоритет 1: обрезка по последнему знаку препинания
            last_p = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
            if last_p > MAX_RESPONSE_CHARS * 0.3:
                text = cut_text[:last_p + 1].strip()
            else:
                # Приоритет 2: обрезка по последнему пробелу + '...'
                last_space = cut_text.rfind(' ')
                if last_space > MAX_RESPONSE_CHARS * 0.3:
                    text = cut_text[:last_space].strip() + '...'
                else:
                    text = cut_text.strip() + '...'
        # Если текст не заканчивается на знак — тоже обрезаем по предложению или слову
        if text and text[-1] not in '.!?…"\'…':
            last_punctuation = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
            if last_punctuation > len(text) * 0.3:
                text = text[:last_punctuation + 1].strip()
            else:
                # Обрезаем по последнему пробелу
                last_space = text.rfind(' ')
                if last_space > len(text) * 0.5:
                    text = text[:last_space].strip() + '...'
        return text

    def _check_quality(self, text: str, speaker: 'Agent') -> tuple[bool, str]:
        """[FIX #8 v4] BigBrother проверяет качество с логированием."""
        text_lower = text.lower()
        speaker_display = agent_registry.get_name(speaker.agent_id)

        # Самоповреждение / абсурд
        dangerous_patterns = [
            'разрезаю', 'ампутир', 'отрежу', 'режу себ', 'пущу кровь',
            'сломаю себе', 'выколю', 'проклят', 'ритуал с кровью',
            'жертвоприношен', 'убью себя', 'повешу', 'утоплюсь',
        ]
        for pattern in dangerous_patterns:
            if pattern in text_lower:
                self._log_warning(f"опасное действие: '{pattern}' от {speaker_display}")
                return False, f"опасное действие: '{pattern}'"

        # Мультиперсонажность — агент говорит за других
        other_names = [n for n in agent_registry.get_all_names() if n != speaker_display]
        for name in other_names:
            if f"{name}:" in text:
                self._log_warning(f"{speaker_display} пишет за {name}")
                return False, f"пишешь за {name} — говори только от себя"

        # [FIX v4] Агент говорит о себе в третьем лице — копирует результат гейм-мастера
        third_person_patterns = [
            f"{speaker_display} нашёл", f"{speaker_display} нашла",
            f"{speaker_display} успел", f"{speaker_display} успела",
            f"{speaker_display} попытал", f"{speaker_display} решил",
            f"{speaker_display} сделал", f"{speaker_display} сделала",
            f"{speaker_display} увидел", f"{speaker_display} увидела",
            f"{speaker_display} пошёл", f"{speaker_display} пошла",
        ]
        for pattern in third_person_patterns:
            if pattern.lower() in text_lower:
                self._log_warning(f"{speaker_display} говорит о себе в 3-м лице: '{pattern}'")
                return False, f"говори от первого лица ('я'), а не '{pattern}'"

        # [FIX v4] Копирование результата гейм-мастера
        gm_copy_patterns = [
            'частичный успех', 'частичный.', 'полный успех', 'неудача.',
            'результат:', 'результат действия',
            'частичный —', 'неожиданность —',
        ]
        for pattern in gm_copy_patterns:
            if pattern in text_lower:
                self._log_warning(f"{speaker_display} скопировал текст результата: '{pattern}'")
                return False, f"не копируй текст результата — говори от себя"

        if len(text.split()) < 3:
            self._log_warning(f"слишком короткое от {speaker_display}: '{text[:30]}'")
            return False, "слишком короткое"

        return True, ""

    def _log_warning(self, reason: str):
        """Логирует предупреждение с причиной."""
        self.quality_warnings += 1
        self.last_warning_reason = reason
        if self.quality_warnings <= 10 or self.quality_warnings % 5 == 0:
            print(f"{Fore.RED}  ⚠️ Предупреждение #{self.quality_warnings}: {reason}{Style.RESET_ALL}")

    def _analyze_interaction_sentiment(self, speaker_id: str, text: str, all_agents: list) -> dict:
        """[FIX #7] Анализ тональности для обновления отношений.
        Возвращает dict[agent_id] = (delta, reason).
        Включает расовые модификаторы взаимодействий."""
        sentiment = {}
        text_lower = text.lower()

        # Находим агента-говорящего
        speaker_agent = next((a for a in all_agents if a.agent_id == speaker_id), None)

        for agent in all_agents:
            if agent.agent_id == speaker_id:
                continue
            agent_display = agent_registry.get_name(agent.agent_id)
            if agent_display.lower() not in text_lower:
                continue

            positive_patterns = [
                'спасибо', 'молодец', 'отличн', 'согласен', 'согласна', 'правильно',
                'хорошая идея', 'поддержива', 'помог', 'благодар', 'доверя', 'прав', 'умн',
            ]
            negative_patterns = [
                'не согласен', 'не согласна', 'глуп', 'бесполезн', 'зря',
                'ошиб', 'виноват', 'мешаешь', 'хватит', 'надоел',
                'раздражае', 'не доверя', 'подозрева', 'врёшь', 'предатель',
            ]
            # Паттерны храбрости (для бонуса орка)
            bravery_patterns = [
                'храбр', 'смел', 'пойду перв', 'не боюсь', 'рискну',
                'не страшно', 'бесстраш', 'отважн', 'герой', 'сражаться',
            ]
            # Паттерны дележа (для жадности дварфа/гоблина)
            sharing_patterns = [
                'делим', 'поровну', 'раздел', 'припасы', 'ресурсы',
                'запасы', 'поделить', 'раздать', 'разделить',
            ]

            delta = 0.0
            reason = ""
            for p in positive_patterns:
                if p in text_lower:
                    delta += RELATIONSHIP_CHANGE_RATE
                    reason = f"позитив: '{p}'"
                    break
            for p in negative_patterns:
                if p in text_lower:
                    delta -= RELATIONSHIP_CHANGE_RATE
                    reason = f"негатив: '{p}'"
                    break
            if delta == 0.0:
                delta = RELATIONSHIP_CHANGE_RATE * 0.3
                reason = "упоминание"

            # ── Расовые модификаторы взаимодействий ──

            # Орк: +0.15 к тем, кто проявляет храбрость
            if agent.race.race_type == RaceType.ORC:
                if any(p in text_lower for p in bravery_patterns):
                    delta += 0.15
                    reason += " + 💪храбрость (орк восхищён)"

            # Дварф: жадность при дележе ресурсов — злость +0.10
            if speaker_agent and speaker_agent.race.race_type == RaceType.DWARF:
                if any(p in text_lower for p in sharing_patterns):
                    speaker_agent.mood.anger = min(1.0, speaker_agent.mood.anger + 0.10)
                    delta -= 0.05
                    reason += " + ⚒️жадность (дварф злится при дележе)"

            # Гоблин: -0.20 при дележе ресурсов (жадность)
            if speaker_agent and speaker_agent.race.race_type == RaceType.GOBLIN:
                if any(p in text_lower for p in sharing_patterns):
                    delta -= 0.10
                    reason += " + 👺жадность (гоблин хочет больше)"

            if delta != 0:
                sentiment[agent.agent_id] = (delta, reason)
        return sentiment

    def select_speaker(self) -> 'Agent':
        """[FIX #1] Приоритет тем, кому задали вопрос."""
        agents_with_questions = [a for a in self.agents if a.memory_system.pending_questions]
        if agents_with_questions:
            return random.choice(agents_with_questions)

        weights = []
        for a in self.agents:
            w = a.speak_probability()
            if a.agent_id == self.last_speaker_id:
                w *= 0.3
            weights.append(w)

        total = sum(weights)
        if total == 0:
            return random.choice(self.agents)
        return random.choices(self.agents, weights=weights, k=1)[0]

    def _select_speaker_v3(self) -> 'Agent':
        """[FIX v3] Улучшенный выбор говорящего: приоритет нереагировавших на событие."""
        # Высший приоритет: агенты, которым задали вопрос
        agents_with_questions = [a for a in self.agents if a.memory_system.pending_questions]
        if agents_with_questions:
            return random.choice(agents_with_questions)

        # Приоритет: агенты, которые ещё не отреагировали на текущее событие
        if (self.active_event
                and (self.tick - self.event_started_tick) <= EVENT_FORCED_REACTION_TICKS):
            unreacted = [a for a in self.agents if a.agent_id not in self.event_reacted_agents]
            if unreacted:
                return random.choice(unreacted)

        weights = []
        for a in self.agents:
            w = a.speak_probability()
            if a.agent_id == self.last_speaker_id:
                w *= 0.3
            # [FIX v3] Агенты в петле повтора получают меньший вес
            if a.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT:
                w *= 0.5
            weights.append(w)

        total = sum(weights)
        if total == 0:
            return random.choice(self.agents)
        return random.choices(self.agents, weights=weights, k=1)[0]

    def _check_racial_abilities(self, agent: 'Agent') -> Optional[str]:
        """Проверить и активировать расовые особенности агента.
        Возвращает текст события или None."""
        race = agent.race
        mods = race.modifiers
        agent_display = agent_registry.get_name(agent.agent_id)

        # ── Гоблин: побег при высоком страхе ──
        if race.race_type == RaceType.GOBLIN and agent.mood.fear > mods.flee_threshold:
            if random.random() < 0.4:  # 40% шанс побега
                flee_text = f"⚠️ {race.emoji} {agent_display} ПЫТАЕТСЯ СБЕЖАТЬ! (страх: {agent.mood.fear:.2f} > порог: {mods.flee_threshold})"

                # Гоблин может предать при очень высоком страхе
                if mods.can_betray and agent.mood.fear > 0.7 and random.random() < 0.3:
                    betray_text = (
                        f"\n💀 {race.emoji} {agent_display} ПРЕДАЛ ГРУППУ! "
                        f"Незаметно выскользнул, прихватив часть припасов!"
                    )
                    # Все отношения к гоблину резко падают
                    for other in self.agents:
                        if other.agent_id != agent.agent_id:
                            other.update_relationship(agent.agent_id, -0.50, "ПРЕДАТЕЛЬСТВО гоблина!")
                            other.mood.anger = min(1.0, other.mood.anger + 0.3)

                    # Добавляем событие в историю
                    betray_entry = {
                        "tick": self.tick, "agent_id": "race_event",
                        "name": "🎭 Расовое событие", "text": f"{agent_display} предал группу и сбежал с припасами!",
                        "is_event": True,
                    }
                    self.conversation.append(betray_entry)
                    for a in self.agents:
                        a.process_message(self.tick, "Расовое событие",
                                          f"{agent_display} предал группу!",
                                          is_own=False, is_event=True)

                    return f"{Fore.RED}{flee_text}{betray_text}{Style.RESET_ALL}"

                return f"{Fore.YELLOW}{flee_text}{Style.RESET_ALL}"

        # ── Эльф: обнаружение опасности ──
        if race.race_type == RaceType.ELF and self.active_event:
            event_lower = self.active_event.lower()
            danger_keywords = ['зомби', 'опасн', 'хищник', 'змея', 'бандит', 'враг']
            if any(kw in event_lower for kw in danger_keywords):
                if random.random() < mods.detection_bonus:
                    return f"{Fore.GREEN}  🌿 {race.emoji} {agent_display} чувствует опасность раньше других! (+обнаружение){Style.RESET_ALL}"

        # ── Дварф: мастерство при ремонте ──
        if race.race_type == RaceType.DWARF:
            repair_keywords = ['чин', 'ремонт', 'почин', 'постро', 'мастер', 'кова', 'куз']
            text_lower = agent.memory_system.completed_actions[-1].lower() if agent.memory_system.completed_actions else ""
            if any(kw in text_lower for kw in repair_keywords):
                if random.random() < 0.5:
                    return f"{Fore.GREEN}  🔨 {race.emoji} {agent_display} применяет мастерство дварфов! (+{mods.repair_bonus*100:.0f}% к ремонту){Style.RESET_ALL}"

        # ── Орк: боевой дух в конфликтах ──
        if race.race_type == RaceType.ORC and self.active_event:
            event_lower = self.active_event.lower()
            combat_keywords = ['зомби', 'бандит', 'драк', 'бой', 'сражен', 'атак', 'напад']
            if any(kw in event_lower for kw in combat_keywords):
                if random.random() < 0.3:
                    agent.mood.energy = min(1.0, agent.mood.energy + 0.15)
                    agent.mood.fear = max(0.0, agent.mood.fear - 0.1)
                    return f"{Fore.GREEN}  ⚔️ {race.emoji} {agent_display} воодушевлён боем! (+боевой дух, −страх){Style.RESET_ALL}"

        return None

    def _generate_action_result(self, agent_name: str, action_text: str, scenario_context: str) -> Optional[str]:
        action_words = [
            'пойду', 'пошёл', 'пошла', 'проверю', 'поищу', 'попробую',
            'попытаюсь', 'сделаю', 'осмотрю', 'обыщу', 'разведаю',
            'починю', 'построю', 'соберу', 'принесу', 'открою',
            'забаррикадирую', 'укреплю', 'побегу', 'спрячусь',
            'перемещу', 'исследую', 'полезу', 'возьму', 'достану',
        ]
        text_lower = action_text.lower()
        if not any(w in text_lower for w in action_words):
            return None

        prompt = [
            {
                "role": "system",
                "content": (
                    "Ты — гейм-мастер. Опиши РЕЗУЛЬТАТ действия в 1-2 предложениях.\n"
                    f"Сценарий: {scenario_context}\n\n"
                    "Результат: успех / частичный / неудача / неожиданность.\n"
                    "РЕАЛИСТИЧНО для ситуации. ТОЛЬКО русский, БЕЗ тегов."
                )
            },
            {"role": "user", "content": f"{agent_name} делает: {action_text}\n\nЧто произошло?"}
        ]
        result = llm_chat(prompt, temperature=0.9)
        if result:
            result = self._clean_response(result)
        return result if result and len(result) > 5 else None

    def _generate_event_consequence(self, event: str, scenario_context: str) -> Optional[str]:
        """[FIX v3] Генерирует последствия события в мире."""
        prompt = [
            {
                "role": "system",
                "content": (
                    "Ты — гейм-мастер. Опиши ПОСЛЕДСТВИЕ события для окружающего мира в 1-2 предложениях.\n"
                    f"Сценарий: {scenario_context}\n\n"
                    "Последствие должно ИЗМЕНИТЬ ситуацию: новая опасность, возможность, или изменение обстановки.\n"
                    "Это НЕ реакция персонажей, а изменение МИРА вокруг них.\n"
                    "ТОЛЬКО русский, БЕЗ тегов. 1-2 предложения."
                )
            },
            {"role": "user", "content": f"Событие: {event}\n\nЧто изменилось в мире?"}
        ]
        result = llm_chat(prompt, temperature=0.8)
        if result:
            result = self._clean_response(result)
        return result if result and len(result) > 10 else None

    def _check_consecutive_similarity(self, speaker: 'Agent', new_text: str):
        """[FIX v3] Проверяет и обновляет счётчик последовательных похожих реплик."""
        new_phrases = _extract_phrases(new_text)
        if speaker.last_response_phrases:
            overlap = len(new_phrases & speaker.last_response_phrases) / max(len(new_phrases), 1)
            if overlap > 0.3 or _has_banned_pattern(new_text):
                speaker.consecutive_similar_count += 1
            else:
                speaker.consecutive_similar_count = 0
        speaker.last_response_phrases = new_phrases

    def run_tick(self) -> Optional[dict]:
        self.tick += 1

        # Обработка пользовательских событий из очереди
        self._process_user_events()
        if self._quit_requested:
            return None

        # [FIX #6] Проверяем таймер события
        if self.active_event and (self.tick - self.event_started_tick) > EVENT_FOCUS_DURATION:
            print(f"{Fore.MAGENTA}  📋 Фокус на событии завершён{Style.RESET_ALL}")
            self.active_event = None
            self.event_reacted_agents = set()
            for agent in self.agents:
                agent.active_event = None
                agent.reacted_to_event = False

        # [FIX v3] Продвигаем фазу диалога
        phase_changed, phase_label = self.phase_manager.advance_tick()
        if phase_changed and phase_label:
            print(f"{Fore.CYAN}  📌 {phase_label}{Style.RESET_ALL}")

        # [FIX v3] Если тема завершена по фазам — принудительная смена
        if self.phase_manager.is_topic_complete() and not self.active_event:
            scenario_context = self.scenario_manager.get_scenario_context()
            new_topic = self.topic_manager.get_new_topic(scenario_context)
            self.phase_manager.start_new_topic(self.tick)
            print(f"{Fore.CYAN}💡 Тема завершена! Новая тема: {new_topic[:80]}{Style.RESET_ALL}")
            topic_entry = {
                "tick": self.tick, "agent_id": "system",
                "name": "Ведущий", "text": f"Новая тема: {new_topic}",
                "is_new_topic": True,
            }
            self.conversation.append(topic_entry)
            for agent in self.agents:
                agent.process_message(self.tick, "Ведущий", f"Новая тема: {new_topic}", is_own=False)

        # Запуск события
        if self.tick % SCENARIO_EVENT_INTERVAL == 0:
            event = self.scenario_manager.trigger_random_event()
            if event:
                print(f"\n{Fore.MAGENTA}{'═' * 60}")
                print(f"{Fore.MAGENTA}🎬 СОБЫТИЕ: {event}")
                print(f"{Fore.MAGENTA}{'═' * 60}\n")

                self.active_event = event
                self.event_started_tick = self.tick
                self.event_reacted_agents = set()

                event_entry = {
                    "tick": self.tick, "agent_id": "event",
                    "name": "📢 Событие", "text": event, "is_event": True,
                }
                self.conversation.append(event_entry)

                for agent in self.agents:
                    agent.process_message(self.tick, "Событие", event, is_own=False, is_event=True)
                    agent.update_observations(self.tick, "Событие", event, event)
                    agent.active_event = event
                    agent.event_focus_tick = self.tick
                    agent.reacted_to_event = False
                    # Обновляем настроение от сценарного события
                    agent.mood.apply_event(event, agent.personality_type, agent.big_five, agent.race.modifiers)

                # [FIX v3] Генерируем последствие события
                for agent in self.agents:
                    agent_display = agent_registry.get_name(agent.agent_id)
                    dominant = agent.mood.get_dominant_emotion()
                    emoji = agent.mood.get_emoji()
                    print(f"{Fore.YELLOW}  {emoji} {agent_display}: {dominant} "
                          f"(😊{agent.mood.happiness:+.2f} 😤{agent.mood.anger:.2f} 😨{agent.mood.fear:.2f}){Style.RESET_ALL}")

                # [FIX v3] Генерируем последствие события
                scenario_ctx = self.scenario_manager.get_scenario_context()
                consequence = self._generate_event_consequence(event, scenario_ctx)
                if consequence:
                    print(f"{Fore.YELLOW}🌍 Последствие: {consequence}{Style.RESET_ALL}")
                    consequence_entry = {
                        "tick": self.tick, "agent_id": "world",
                        "name": "🌍 Мир", "text": consequence, "is_event": True,
                    }
                    self.conversation.append(consequence_entry)
                    for agent in self.agents:
                        agent.process_message(self.tick, "Мир", consequence, is_own=False, is_action_result=True)

        # [FIX v3] Выбор говорящего — приоритет тем, кто не отреагировал на событие
        speaker = self._select_speaker_v3()

        # [FIX v3] Определяем — нужна ли принудительная реакция на событие
        force_event_reaction = False
        if (self.active_event
                and speaker.agent_id not in self.event_reacted_agents
                and (self.tick - self.event_started_tick) <= EVENT_FORCED_REACTION_TICKS):
            force_event_reaction = True

        # [FIX #6] Блокируем смену темы при активном событии
        mode = "normal"
        if not self.active_event and self.topic_manager.should_change_topic(len(self.agents)):
            if random.random() < CREATIVITY_BOOST:
                mode = "new_topic"
                print(f"{Fore.CYAN}💡 {agent_registry.get_name(speaker.agent_id)} предлагает новую тему...{Style.RESET_ALL}")

        scenario_context = self.scenario_manager.get_scenario_context()

        current_event = None
        for entry in reversed(self.conversation[-5:]):
            if entry.get("is_event", False):
                current_event = entry["text"]
                break

        # Планирование
        old_plan_goal = speaker.current_plan.goal if speaker.current_plan else None
        if not speaker.current_plan or current_event:
            speaker.create_or_update_plan(self.conversation, scenario_context)
        if speaker.current_plan and speaker.current_plan.goal != old_plan_goal:
            step = speaker.current_plan.steps[0] if speaker.current_plan.steps else 'нет'
            print(f"{Fore.CYAN}💭 {agent_registry.get_name(speaker.agent_id)} → {speaker.current_plan.goal} | {step}{Style.RESET_ALL}")

        # [FIX v3] Получаем инструкцию фазы
        phase_instruction = self.phase_manager.get_phase_instruction()

        # Генерируем ответ
        messages = speaker.build_messages(
            self.conversation, mode, scenario_context,
            active_event=self.active_event, all_agents=self.agents,
            phase_instruction=phase_instruction,
            force_event_reaction=force_event_reaction,
        )
        raw_response = llm_chat(messages)
        text = None

        if raw_response is not None:
            text = self._clean_response(raw_response, agent_registry.get_name(speaker.agent_id))

        if not text:
            retry_messages = speaker.build_messages(
                self.conversation, mode, scenario_context,
                active_event=self.active_event, all_agents=self.agents,
                phase_instruction=phase_instruction,
                force_event_reaction=force_event_reaction,
            )
            retry_messages.append({"role": "user", "content":
                f"Ты — {agent_registry.get_name(speaker.agent_id)}. Ответь КОРОТКО, 1-2 предложения. БЕЗ тегов. Русский текст. НЕ пиши за других."
            })
            raw_retry = llm_chat(retry_messages, temperature=1.0)
            if raw_retry:
                text = self._clean_response(raw_retry, agent_registry.get_name(speaker.agent_id))

        if not text:
            # [FIX v3] Логирование пропущенного тика
            print(f"{Fore.WHITE}  ⏸ [tick {self.tick:>3}] {agent_registry.get_name(speaker.agent_id)} промолчал (LLM не дал ответ){Style.RESET_ALL}")
            for a in self.agents:
                a.update_talkativeness_silent()
            return None

        # Убираем префикс с именем
        speaker_display = agent_registry.get_name(speaker.agent_id)
        for a in self.agents:
            a_display = agent_registry.get_name(a.agent_id)
            prefix = f"{a_display}:"
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        # Повторная обрезка чужих реплик (на случай если были после удаления префикса)
        text = self._strip_other_agents_speech(text, speaker_display)
        if not text or len(text) < 5:
            print(f"{Fore.WHITE}  ⏸ Тик {self.tick}: {speaker_display} промолчал (текст пуст после очистки){Style.RESET_ALL}")
            for a in self.agents:
                a.update_talkativeness_silent()
            return None

        # [FIX #8] Проверка качества
        quality_ok, quality_reason = self._check_quality(text, speaker)
        if not quality_ok:
            print(f"{Fore.RED}  🚫 BigBrother отклонил: {quality_reason}{Style.RESET_ALL}")
            retry_msgs = speaker.build_messages(
                self.conversation, mode, scenario_context,
                active_event=self.active_event, all_agents=self.agents,
                phase_instruction=phase_instruction,
                force_event_reaction=force_event_reaction,
            )
            retry_msgs.append({"role": "user", "content":
                f"СТОП! Ответ отклонён: {quality_reason}. "
                "Скажи что-то БЕЗОПАСНОЕ и РАЗУМНОЕ. 1-2 предложения."
            })
            raw_retry = llm_chat(retry_msgs, temperature=0.7)
            if raw_retry:
                text = self._clean_response(raw_retry, speaker_display)
                for a in self.agents:
                    a_display = agent_registry.get_name(a.agent_id)
                    if text and text.startswith(f"{a_display}:"):
                        text = text[len(f"{a_display}:"):].strip()
                        break
                text = self._strip_other_agents_speech(text, speaker_display)
            if not text:
                for a in self.agents:
                    a.update_talkativeness_silent()
                return None

        # Проверка повторов — расширенное окно (FIX: было 6/15, теперь 20/30)
        recent_texts = [e['text'] for e in self.conversation[-25:]
                        if not e.get('is_event', False) and e.get('text')]
        own_recent = [e['text'] for e in self.conversation[-30:]
                      if e.get('agent_id') == speaker.agent_id and not e.get('is_event', False)]

        is_repetitive = False
        # [FIX v3] Проверяем запрещённые паттерны даже для первого сообщения
        if _has_banned_pattern(text):
            is_repetitive = True
        if not is_repetitive and self.conversation and not self.conversation[-1].get('is_event', False):
            if self.conversation[-1].get('text') == text:
                is_repetitive = True
        # [FIX v4] Проверяем похожесть по ВСЕМУ расширенному окну (20 реплик)
        if not is_repetitive:
            for prev_text in recent_texts[-20:]:
                if _text_similarity(text, prev_text) > REPETITION_SIMILARITY_THRESHOLD:
                    is_repetitive = True
                    break
        # [FIX v4] Проверка первых 5 слов — ловит "Ты тоже...", "Ты вообще не..." и т.д.
        if not is_repetitive and own_recent:
            first_words = ' '.join(text.lower().split()[:5])
            for old_msg in own_recent[-15:]:
                old_first_words = ' '.join(old_msg.lower().split()[:5])
                if first_words == old_first_words and len(first_words) > 10:
                    is_repetitive = True
                    break
        if not is_repetitive:
            is_repetitive = _has_repetitive_pattern(text, own_recent)
        # [FIX #5]
        if not is_repetitive and speaker.memory_system.has_done_similar(text):
            is_repetitive = True

        if is_repetitive:
            retry_msgs = speaker.build_messages(
                self.conversation, mode, scenario_context,
                active_event=self.active_event, all_agents=self.agents,
                phase_instruction=phase_instruction,
                force_event_reaction=force_event_reaction,
            )
            banned = '; '.join([t[:50] for t in own_recent[-3:]]) if own_recent else ''
            # [FIX v3] Более агрессивная смена стратегии при многократных повторах
            if speaker.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT:
                style_change = random.choice([
                    "Расскажи КОНКРЕТНЫЙ ФАКТ о себе или ситуации.",
                    "Задай ВОПРОС кому-то из собеседников.",
                    "Предложи КОНКРЕТНОЕ ДЕЙСТВИЕ прямо сейчас.",
                    "СОГЛАСИСЬ с кем-то и РАЗВЕЙ его идею.",
                    "Вспомни ЧТО-ТО из прошлого и расскажи.",
                    "Обрати внимание на ОКРУЖЕНИЕ — что ты видишь вокруг?",
                    "Пошути или скажи что-то НЕОЖИДАННОЕ.",
                ])
                retry_msgs.append({"role": "user", "content": (
                    f"СТОП! ПОВТОР! Ты уже {speaker.consecutive_similar_count} раз говоришь похожее! "
                    f"Запрещено: {banned}. "
                    f"ОБЯЗАТЕЛЬНО: {style_change}"
                )})
            else:
                retry_msgs.append({"role": "user", "content": (
                    f"СТОП! Повтор: '{text[:50]}...' уже было. Запрещено: {banned}. "
                    "Скажи СОВЕРШЕННО ДРУГОЕ."
                )})
            raw_retry = llm_chat(retry_msgs, temperature=1.3)
            if raw_retry:
                text_retry = self._clean_response(raw_retry, speaker_display)
                for a in self.agents:
                    a_display = agent_registry.get_name(a.agent_id)
                    if text_retry and text_retry.startswith(f"{a_display}:"):
                        text_retry = text_retry[len(f"{a_display}:"):].strip()
                        break
                text_retry = self._strip_other_agents_speech(text_retry, speaker_display)
                if text_retry and _text_similarity(text_retry, text) < 0.4:
                    text = text_retry
                else:
                    for a in self.agents:
                        a.update_talkativeness_silent()
                    return None
            else:
                for a in self.agents:
                    a.update_talkativeness_silent()
                return None

        # [FIX v3] Трекинг последовательных повторов
        self._check_consecutive_similarity(speaker, text)

        # [FIX v3] Отмечаем реакцию на событие
        if self.active_event and speaker.agent_id not in self.event_reacted_agents:
            self.event_reacted_agents.add(speaker.agent_id)
            speaker.reacted_to_event = True

        # [FIX #5] Записываем действие
        speaker.memory_system.record_action(text)

        # ── Расовые особенности в действиях ──
        race_event = self._check_racial_abilities(speaker)
        if race_event:
            print(f"{race_event}")

        # [FIX v3] Записываем решения и действия для фазы
        self.phase_manager.record_decision(text)
        self.phase_manager.record_action(text)

        # Результат действия
        action_result = self._generate_action_result(speaker_display, text, scenario_context)

        if mode == "new_topic":
            self.topic_manager.current_topic = text
            self.topic_manager.messages_on_topic = 0
            self.topic_manager.topic_respondents = set()
            self.phase_manager.start_new_topic(self.tick)
            self.topic_manager.save_to_db()

        # [FIX v3] Обновляем last_visible_tick
        self.last_visible_tick = self.tick

        entry = {
            "tick": self.tick, "agent_id": speaker.agent_id,
            "name": speaker_display, "text": text,
            "is_new_topic": mode == "new_topic",
        }
        self.conversation.append(entry)
        self.topic_manager.record_message(speaker_display)

        # [FIX #1] Очищаем вопросы
        if speaker.memory_system.pending_questions:
            speaker.memory_system.clear_pending_questions()

        # [FIX #1] Добавляем вопросы другим агентам
        for agent in self.agents:
            if agent.agent_id != speaker.agent_id:
                agent_display = agent_registry.get_name(agent.agent_id)
                if agent_display.lower() in text.lower() and "?" in text:
                    agent.memory_system.add_pending_question(self.tick, speaker_display, text, from_id=speaker.agent_id)

        # Результат действия
        if action_result:
            print(f"{Fore.YELLOW}✨ Результат: {action_result}{Style.RESET_ALL}")
            result_entry = {
                "tick": self.tick, "agent_id": "action_result",
                "name": "✨ Результат", "text": f"{speaker_display}: {action_result}",
                "is_event": True,
            }
            self.conversation.append(result_entry)
            for a in self.agents:
                a.process_message(self.tick, speaker_display, action_result,
                                  is_own=(a.agent_id == speaker.agent_id),
                                  is_action_result=True, speaker_id=speaker.agent_id)
                a.update_observations(self.tick, speaker_display, action_result, action_result)

        # [FIX #7] Обновляем отношения
        sentiments = self._analyze_interaction_sentiment(speaker.agent_id, text, self.agents)
        for target_id, (delta, reason) in sentiments.items():
            speaker.update_relationship(target_id, delta, reason)
            # Обновляем настроение говорящего от взаимодействия
            speaker.mood.apply_interaction(delta, speaker.personality_type, speaker.big_five)
            target_agent = next((a for a in self.agents if a.agent_id == target_id), None)
            if target_agent:
                reciprocal = delta * 0.5
                target_agent.update_relationship(speaker.agent_id, reciprocal,
                    f"{'позитив' if delta > 0 else 'негатив'} от {speaker_display}")
                # Обновляем настроение цели от взаимодействия
                target_agent.mood.apply_interaction(reciprocal, target_agent.personality_type, target_agent.big_five)

        # Обновляем память всех агентов
        for a in self.agents:
            is_own = (a.agent_id == speaker.agent_id)
            a.process_message(self.tick, speaker_display, text, is_own, speaker_id=speaker.agent_id)
            a.update_observations(self.tick, speaker_display, text, current_event)

        # Продвигаем план
        if speaker.current_plan and speaker.current_plan.steps:
            speaker.current_plan.current_step = min(
                speaker.current_plan.current_step + 1,
                len(speaker.current_plan.steps) - 1
            )

        # [FIX #7] Логирование отношений
        for target_id, (delta, reason) in sentiments.items():
            if abs(delta) >= 0.03:
                emoji = "💚" if delta > 0 else "💔"
                target_display = agent_registry.get_name(target_id)
                print(f"{Fore.MAGENTA}  {emoji} {speaker_display} → {target_display}: {delta:+.2f} ({reason}){Style.RESET_ALL}")

        # Общительность и настроение
        for a in self.agents:
            if a.agent_id == speaker.agent_id:
                a.update_talkativeness_spoke()
                a.mood.apply_speaking(a.big_five)
            else:
                a.update_talkativeness_silent()
            # Естественный decay настроения к baseline каждый тик
            a.mood.decay_toward_baseline(a.big_five)

        self.last_speaker_id = speaker.agent_id
        return entry

    def save_all_memories(self):
        for agent in self.agents:
            agent.save_memory()

    def print_entry(self, entry: dict):
        if entry.get("is_event", False):
            return
        agent_id = entry.get("agent_id", "")
        # Сообщения от пользователя — отдельный формат
        if agent_id == "user":
            tick_str = f"{Fore.WHITE}[tick {entry['tick']:>3}]"
            name_str = f"{Fore.MAGENTA}{Style.BRIGHT}{entry['name']}"
            text_str = f"{Style.RESET_ALL}{entry['text']}"
            print(f"{tick_str} {name_str}: {text_str}")
            return
        agent = next((a for a in self.agents if a.agent_id == agent_id), None)
        if not agent:
            return
        tick_str = f"{Fore.WHITE}[tick {entry['tick']:>3}]"
        if entry.get("is_new_topic", False):
            name_str = f"{agent.color}{Style.BRIGHT}💡 {agent.race.emoji} {entry['name']}"
        else:
            name_str = f"{agent.color}{Style.BRIGHT}{agent.race.emoji} {entry['name']}"
        text_str = f"{Style.RESET_ALL}{entry['text']}"
        print(f"{tick_str} {name_str}: {text_str}")

    def print_stats(self):
        print(f"\n{Fore.MAGENTA}{'═' * 60}")
        print(f"{Fore.MAGENTA}📊 Статистика:")
        for a in self.agents:
            display = agent_registry.get_name(a.agent_id)
            race = a.race
            bar_len = int(a.talkativeness * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {a.color}{race.emoji} {display:<8}{Style.RESET_ALL} [{race.name_ru}] [{bar}] {a.talkativeness:.2f}")

        # Настроение
        print(f"\n{Fore.YELLOW}🎭 Настроение:")
        for a in self.agents:
            display = agent_registry.get_name(a.agent_id)
            race = a.race
            m = a.mood
            emoji = m.get_emoji()
            dominant = m.get_dominant_emotion()
            # Визуальные полоски
            h_bar = self._mood_bar(m.happiness, signed=True)
            e_bar = self._mood_bar(m.energy)
            s_bar = self._mood_bar(m.stress)
            a_bar = self._mood_bar(m.anger)
            f_bar = self._mood_bar(m.fear)
            print(f"  {a.color}{race.emoji} {display}{Style.RESET_ALL} {emoji} {dominant}")
            print(f"    😊 Счастье: {h_bar} {m.happiness:+.2f}")
            print(f"    ⚡ Энергия: {e_bar} {m.energy:.2f}")
            print(f"    😰 Стресс:  {s_bar} {m.stress:.2f}")
            print(f"    😤 Злость:  {a_bar} {m.anger:.2f}")
            print(f"    😨 Страх:   {f_bar} {m.fear:.2f}")
            # Расовые особенности
            mods = race.modifiers
            race_info = []
            if mods.repair_bonus > 0:
                race_info.append(f"🔨+{mods.repair_bonus*100:.0f}%")
            if mods.combat_bonus > 0:
                race_info.append(f"⚔️+{mods.combat_bonus*100:.0f}%")
            if mods.diplomacy_bonus > 0:
                race_info.append(f"🤝+{mods.diplomacy_bonus*100:.0f}%")
            if mods.detection_bonus > 0:
                race_info.append(f"🔍+{mods.detection_bonus*100:.0f}%")
            if mods.can_betray:
                betray_status = "⚠️ОПАСНО!" if m.fear > 0.5 else "👺"
                race_info.append(f"Предательство:{betray_status}")
            if mods.stubborn:
                race_info.append("🛡️упрямый")
            if race_info:
                print(f"    {Fore.YELLOW}Раса: {' | '.join(race_info)}{Style.RESET_ALL}")

        # [FIX #7] Отношения (с расовой информацией)
        print(f"\n{Fore.RED}❤️  Отношения:")
        for a in self.agents:
            a_display = agent_registry.get_name(a.agent_id)
            a_race = a.race
            for other_id, val in a.relationships.items():
                other_agent = next((ag for ag in self.agents if ag.agent_id == other_id), None)
                other_display = agent_registry.get_name(other_id)
                other_emoji = other_agent.race.emoji if other_agent else ""
                if val > 0.3:
                    emoji = "💚"
                elif val > 0:
                    emoji = "🤝"
                elif val > -0.3:
                    emoji = "😐"
                else:
                    emoji = "💔"
                bar_len = int((val + 1) * 10)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                print(f"  {a.color}{a_race.emoji}{a_display}{Style.RESET_ALL} → {other_emoji}{other_display}: [{bar}] {val:+.2f} {emoji}")

        print(f"\n{Fore.GREEN}🎯 Планы:")
        for a in self.agents:
            a_display = agent_registry.get_name(a.agent_id)
            if a.current_plan:
                step_info = f"{a.current_plan.current_step + 1}/{len(a.current_plan.steps)}"
                current_step = a.current_plan.steps[a.current_plan.current_step] if a.current_plan.steps else "нет"
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} {a.current_plan.goal}")
                print(f"    └─ Шаг {step_info}: {current_step[:50]}")
            else:
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} нет плана")

        print(f"\n{Fore.YELLOW}🎭 Сценарий: {self.scenario_manager.current_scenario.name}")
        if self.active_event:
            remaining = EVENT_FOCUS_DURATION - (self.tick - self.event_started_tick)
            print(f"{Fore.YELLOW}   ⚡ Активное событие (ещё {remaining} тиков): {self.active_event[:60]}")
        warn_text = f"{Fore.RED}   🚫 Предупреждения: {self.quality_warnings}"
        if self.last_warning_reason:
            warn_text += f" (последнее: {self.last_warning_reason[:60]})"
        print(warn_text)

        if self.topic_manager.current_topic:
            import re
            clean_topic = re.sub(r'<think>.*?</think>', '', self.topic_manager.current_topic, flags=re.DOTALL | re.IGNORECASE)
            clean_topic = re.sub(r'<think>.*', '', clean_topic, flags=re.DOTALL | re.IGNORECASE)
            clean_topic = re.sub(r'</?think>', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'\s+', ' ', clean_topic).strip()
            if len(clean_topic) > 100:
                clean_topic = clean_topic[:97] + "..."
            if len(clean_topic) < 5:
                clean_topic = "[тема генерируется...]"
            respondents = ", ".join(self.topic_manager.topic_respondents) if self.topic_manager.topic_respondents else "никто"
            print(f"\n{Fore.CYAN}💬 Тема: {clean_topic}")
            print(f"{Fore.CYAN}   Сообщений: {self.topic_manager.messages_on_topic} | Ответили: {respondents}")
            # [FIX v3] Фаза диалога
            phase = self.phase_manager.phase_label
            ticks_left = PHASE_TICKS.get(self.phase_manager.current_phase, 0) - self.phase_manager.ticks_in_phase
            print(f"{Fore.CYAN}   Фаза: {phase} (осталось ~{max(0, ticks_left)} тиков)")
            if self.phase_manager.topic_decisions:
                print(f"{Fore.GREEN}   Решения: {'; '.join(self.phase_manager.topic_decisions[-3:])}")
            if self.phase_manager.topic_actions:
                print(f"{Fore.GREEN}   Действия: {'; '.join(self.phase_manager.topic_actions[-3:])}")

        # [FIX v3] Антиповтор статус
        print(f"\n{Fore.WHITE}🔄 Петли повторов:")
        for a in self.agents:
            a_display = agent_registry.get_name(a.agent_id)
            if a.consecutive_similar_count > 0:
                status = f"⚠️ {a.consecutive_similar_count} подряд" if a.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT else f"{a.consecutive_similar_count}"
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} {status}")
            else:
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} ✅ нет повторов")

        print(f"{Fore.MAGENTA}{'═' * 60}\n")

    @staticmethod
    def _mood_bar(value: float, signed: bool = False, width: int = 10) -> str:
        """Визуальная полоска для значения настроения."""
        if signed:
            # -1.0 .. 1.0 → 0 .. width
            fill = int((value + 1.0) / 2.0 * width)
        else:
            # 0.0 .. 1.0 → 0 .. width
            fill = int(value * width)
        fill = max(0, min(width, fill))
        return "█" * fill + "░" * (width - fill)


# ── Главный цикл ─────────────────────────────────────────────

def main():
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'═' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  КИБЕР РЫВОК — AI-агенты v2")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  Модель: {LLM_MODEL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  LLM API: {LLM_BASE_URL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * 60}\n")

    print(f"{Fore.YELLOW}Доступные сценарии:")
    scenarios = list(ScenarioManager.SCENARIOS.keys())
    for i, key in enumerate(scenarios, 1):
        scenario = ScenarioManager.SCENARIOS[key]
        print(f"  {i}. {scenario.name} - {scenario.description}")

    print(f"\n{Fore.WHITE}Выберите сценарий (1-{len(scenarios)}) или Enter для 'Необитаемый остров': ", end="")

    try:
        choice = input().strip()
        if choice and choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(scenarios):
                selected_scenario = scenarios[idx]
            else:
                selected_scenario = "desert_island"
        else:
            selected_scenario = "desert_island"
    except Exception:
        selected_scenario = "desert_island"

    print()

    # ── Выбор расового состава ──
    print(f"{Fore.YELLOW}Доступные расовые составы:")
    race_keys = list(RACE_PRESETS.keys())
    for i, key in enumerate(race_keys, 1):
        preset = RACE_PRESETS[key]
        races = [f"{RACES[a['race']].emoji}{a['name']}" for a in preset["agents"]]
        print(f"  {i}. {preset['name']}: {', '.join(races)}")

    print(f"\n{Fore.WHITE}Выберите состав (1-{len(race_keys)}) или Enter для 'Люди': ", end="")

    try:
        race_choice = input().strip()
        if race_choice and race_choice.isdigit():
            race_idx = int(race_choice) - 1
            if 0 <= race_idx < len(race_keys):
                selected_race_preset = race_keys[race_idx]
            else:
                selected_race_preset = "humans"
        else:
            selected_race_preset = "humans"
    except Exception:
        selected_race_preset = "humans"

    print()

    print(f"{Fore.YELLOW}🔄 Очистка данных предыдущих сессий...{Style.RESET_ALL}")
    data_dir = Path("data")
    if data_dir.exists():
        for file in ["agent_memory.json", "topics.json", "scenario.json"]:
            file_path = data_dir / file
            if file_path.exists():
                file_path.unlink()
                print(f"   ✓ Удалён {file}")
    print(f"{Fore.GREEN}✓ Данные очищены. Новая сессия!{Style.RESET_ALL}\n")

    # Создаём агентов с выбранным расовым пресетом
    agents = create_agents(selected_race_preset)
    user_input = UserEventInput(agent_names=agent_registry.get_all_names())
    orchestrator = BigBrotherOrchestrator(agents, selected_scenario, user_event_input=user_input)

    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}🎭 СЦЕНАРИЙ: {orchestrator.scenario_manager.current_scenario.name}")
    print(f"{Fore.WHITE}{orchestrator.scenario_manager.current_scenario.description}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * 60}\n")

    print(f"{Fore.WHITE}Участники:")
    for a in agents:
        display = agent_registry.get_name(a.agent_id)
        gender_icon = "♂" if a.is_male else "♀"
        race = a.race
        print(f"  {a.color}{Style.BRIGHT}{race.emoji} {gender_icon} {display} ({a.age} лет) [{race.name_ru}] [id: {a.agent_id}]{Style.RESET_ALL} — {a.personality_type.value}")
        print(f"     {Fore.WHITE}Раса: {race.emoji} {race.name_ru} — {race.description}{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}Big Five: O:{a.big_five.openness} C:{a.big_five.conscientiousness} "
              f"E:{a.big_five.extraversion} A:{a.big_five.agreeableness} N:{a.big_five.neuroticism}{Style.RESET_ALL}")
        # Расовые бонусы
        mods = race.modifiers
        bonuses = []
        if mods.repair_bonus > 0:
            bonuses.append(f"🔨+{mods.repair_bonus*100:.0f}%")
        if mods.combat_bonus > 0:
            bonuses.append(f"⚔️+{mods.combat_bonus*100:.0f}%")
        if mods.diplomacy_bonus > 0:
            bonuses.append(f"🤝+{mods.diplomacy_bonus*100:.0f}%")
        if mods.detection_bonus > 0:
            bonuses.append(f"🔍+{mods.detection_bonus*100:.0f}%")
        if mods.can_betray:
            bonuses.append(f"⚠️предатель")
        if mods.stubborn:
            bonuses.append(f"🛡️упрямый")
        if bonuses:
            print(f"     {Fore.YELLOW}Бонусы: {', '.join(bonuses)}{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}Настроение: {a.mood.get_emoji()} {a.mood.get_dominant_emotion()} "
              f"(😊{a.mood.happiness:+.1f} ⚡{a.mood.energy:.1f} 😰{a.mood.stress:.1f} "
              f"😤{a.mood.anger:.1f} 😨{a.mood.fear:.1f}){Style.RESET_ALL}")
        # Расовые отношения
        rel_parts = []
        for b in agents:
            if a.agent_id != b.agent_id:
                b_display = agent_registry.get_name(b.agent_id)
                rel_val = a.relationships.get(b.agent_id, 0.0)
                if rel_val > 0.1:
                    rel_parts.append(f"{b.race.emoji}{b_display}:{rel_val:+.2f}💚")
                elif rel_val < -0.1:
                    rel_parts.append(f"{b.race.emoji}{b_display}:{rel_val:+.2f}💔")
                else:
                    rel_parts.append(f"{b.race.emoji}{b_display}:{rel_val:+.2f}😐")
        if rel_parts:
            print(f"     {Fore.WHITE}Отношения: {', '.join(rel_parts)}{Style.RESET_ALL}")
    print()

    # Подсказка про пользовательские события и сообщения
    agent_names_str = ', '.join(agent_registry.get_all_names())
    print(f"{Fore.CYAN}{'─' * 60}")
    print(f"{Fore.CYAN}📝 ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print(f"{Fore.CYAN}{'─' * 60}")
    print(f"{Fore.WHITE}  Вы можете общаться с агентами и создавать события!")
    print(f"{Fore.WHITE}  💬 Сообщения агентам:")
    print(f"{Fore.GREEN}    @имя текст   — личное сообщение (напр.: @Алиса Привет!)")
    print(f"{Fore.GREEN}    @все текст   — сообщение всем агентам")
    print(f"{Fore.WHITE}  🎭 События: просто введите текст без @")
    print(f"{Fore.WHITE}  Агенты: {agent_names_str}")
    print(f"{Fore.YELLOW}  Команды: help/помощь, stats/стат, quit/выход")
    print(f"{Fore.CYAN}{'─' * 60}\n")

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
    print(f"{Fore.MAGENTA}[tick   0] {Style.BRIGHT}💡 Ведущий: {Style.RESET_ALL}{starter['text']}\n")

    # Запускаем фоновый поток ввода пользователя
    user_input.start()

    try:
        for i in range(MAX_TICKS):
            # Проверяем, не запросил ли пользователь выход
            if orchestrator._quit_requested:
                print(f"\n{Fore.YELLOW}⏹ Симуляция остановлена по команде пользователя.{Style.RESET_ALL}")
                break

            entry = orchestrator.run_tick()
            if entry:
                orchestrator.print_entry(entry)

            if orchestrator._quit_requested:
                print(f"\n{Fore.YELLOW}⏹ Симуляция остановлена по команде пользователя.{Style.RESET_ALL}")
                break

            if random.random() < 0.50:
                entry2 = orchestrator.run_tick()
                if entry2:
                    orchestrator.print_entry(entry2)

            if (i + 1) % 10 == 0:
                orchestrator.print_stats()

            time.sleep(TICK_DELAY)

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Симуляция остановлена пользователем (Ctrl+C).")

    finally:
        user_input.stop()
        print(f"\n{Fore.CYAN}💾 Сохраняю память агентов...{Style.RESET_ALL}")
        orchestrator.save_all_memories()
        print(f"{Fore.GREEN}✓ Память сохранена в {MEMORY_DB_PATH}{Style.RESET_ALL}")

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'═' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  Симуляция завершена! Тиков: {orchestrator.tick}")
    orchestrator.print_stats()

    counts = {}
    for e in orchestrator.conversation:
        counts[e["name"]] = counts.get(e["name"], 0) + 1
    print(f"{Fore.WHITE}Количество сообщений:")
    for name, cnt in sorted(counts.items()):
        print(f"  {name}: {cnt}")


if __name__ == "__main__":
    main()
