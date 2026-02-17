"""
Темы и фазы диалога: TopicManager, DialoguePhaseManager, Goal, ActionPlan.
"""

import re
import random
from dataclasses import dataclass, field
from typing import Optional

from colorama import Fore, Style

from config import (
    TOPIC_CHANGE_THRESHOLD,
    PHASE_TICKS, PHASE_ORDER, PHASE_LABELS,
)
from llm_client import llm_chat
import chroma_storage


class TopicManager:
    def __init__(self, user_id: str = ""):
        self.current_topic: Optional[str] = None
        self.messages_on_topic: int = 0
        self.discussed_topics: list[str] = []
        self.topic_has_responses: int = 0
        self.topic_respondents: set = set()
        self.user_id = user_id
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
        self.messages_on_topic += 1
        if agent_name:
            self.topic_respondents.add(agent_name)
            self.topic_has_responses = len(self.topic_respondents)

    def should_change_topic(self, num_agents: int = 3) -> bool:
        if self.topic_has_responses < num_agents and self.messages_on_topic < TOPIC_CHANGE_THRESHOLD + 5:
            return False
        return self.messages_on_topic >= TOPIC_CHANGE_THRESHOLD

    def save_to_db(self):
        chroma_storage.save_topic_state(
            current_topic=self.current_topic,
            messages_on_topic=self.messages_on_topic,
            discussed_topics=self.discussed_topics,
            user_id=self.user_id,
        )

    def load_from_db(self):
        try:
            data = chroma_storage.load_topic_state(user_id=self.user_id)
            self.current_topic = data.get("current_topic")
            self.messages_on_topic = data.get("messages_on_topic", 0)
            self.discussed_topics = data.get("discussed_topics", [])
        except Exception as e:
            print(f"{Fore.YELLOW}Не удалось загрузить темы: {e}{Style.RESET_ALL}")


class DialoguePhaseManager:
    """Управляет фазами обсуждения темы: discuss → decide → act → conclude."""

    def __init__(self):
        self.current_phase_index: int = 0
        self.ticks_in_phase: int = 0
        self.topic_started_tick: int = 0
        self.topic_decisions: list[str] = []
        self.topic_actions: list[str] = []

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
                return True, "Тема завершена"
        return False, ""

    def is_topic_complete(self) -> bool:
        return self.current_phase_index >= len(PHASE_ORDER)

    def get_phase_instruction(self) -> str:
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
        decision_markers = ['давайте', 'решено', 'будем', 'предлагаю', 'план такой',
                            'я буду', 'ты будешь', 'распределим', 'договорились']
        text_lower = text.lower()
        if any(m in text_lower for m in decision_markers):
            self.topic_decisions.append(text[:80])
            if len(self.topic_decisions) > 5:
                self.topic_decisions = self.topic_decisions[-5:]

    def record_action(self, text: str):
        action_markers = ['пойду', 'пошёл', 'делаю', 'начинаю', 'беру', 'открываю',
                          'проверяю', 'ищу', 'строю', 'собираю', 'чиню']
        text_lower = text.lower()
        if any(m in text_lower for m in action_markers):
            self.topic_actions.append(text[:80])
            if len(self.topic_actions) > 5:
                self.topic_actions = self.topic_actions[-5:]


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
