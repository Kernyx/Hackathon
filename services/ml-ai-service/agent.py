"""
Класс Agent: модель агента со всей логикой.
"""

import random
from dataclasses import dataclass, field
from typing import Optional

from colorama import Fore, Style

from config import (
    MEMORY_WINDOW, SHORT_TERM_MEMORY,
    EVENT_FOCUS_DURATION, REPETITION_CONSECUTIVE_LIMIT,
    MAX_CONTEXT_TOKENS,
)
from models import (
    PersonalityType, BigFiveTraits, RaceType, RaceModifiers,
    Race, RACES, AgentMood,
)
from memory import AgentMemorySystem
from agent_registry import agent_registry
from topics import ActionPlan
from utils import text_similarity, estimate_tokens, estimate_messages_tokens


@dataclass
class Agent:
    agent_id: str
    name: str
    personality_type: PersonalityType
    big_five: BigFiveTraits
    race_type: RaceType = RaceType.HUMAN
    is_male: bool = True
    age: int = 25
    interests: str = ""
    additional_info: str = ""
    color: str = Fore.WHITE
    user_id: str = ""  # ID пользователя для изоляции данных
    _registry: object = field(default=None, repr=False)  # AgentRegistry сессии

    talkativeness: float = field(init=False)
    base_talkativeness: float = field(init=False)
    recovery_rate: float = 0.1
    depletion_rate: float = 0.2
    ticks_silent: int = 0
    messages_spoken: int = 0

    relationships: dict = field(default_factory=dict)
    relationship_log: list = field(default_factory=list)

    memory_system: AgentMemorySystem = field(init=False)
    goals: list = field(default_factory=list)
    current_plan: Optional[ActionPlan] = None
    observations: list = field(default_factory=list)
    last_event: Optional[str] = None
    event_focus_tick: int = 0
    active_event: Optional[str] = None
    consecutive_similar_count: int = 0
    last_response_phrases: set = field(default_factory=set)
    reacted_to_event: bool = False

    mood: AgentMood = field(init=False)

    def __post_init__(self):
        self.memory_system = AgentMemorySystem(
            self.agent_id, user_id=self.user_id, registry=self._registry
        )
        self.race: Race = RACES[self.race_type]
        self._apply_race_modifiers_to_big_five()
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
        mods = self.race.modifiers
        self.big_five.openness = max(0, min(100, self.big_five.openness + mods.openness))
        self.big_five.conscientiousness = max(0, min(100, self.big_five.conscientiousness + mods.conscientiousness))
        self.big_five.extraversion = max(0, min(100, self.big_five.extraversion + mods.extraversion))
        self.big_five.agreeableness = max(0, min(100, self.big_five.agreeableness + mods.agreeableness))
        self.big_five.neuroticism = max(0, min(100, self.big_five.neuroticism + mods.neuroticism))

    def _get_registry(self):
        """Get agent registry (session-scoped or global fallback)."""
        if self._registry is not None:
            return self._registry
        return agent_registry

    @property
    def display_name(self) -> str:
        return self._get_registry().get_name(self.agent_id)

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
        if not self.relationships:
            return "нет данных"
        parts = []
        for other_id, value in self.relationships.items():
            display_name = self._get_registry().get_name(other_id)
            if value > 0.5:
                emoji = "[+]"
            elif value > 0.2:
                emoji = "[~]"
            elif value > -0.2:
                emoji = "[=]"
            elif value > -0.5:
                emoji = "[-]"
            else:
                emoji = "[!]"
            parts.append(f"{display_name}:{value:+.1f}{emoji}")
        return ", ".join(parts)

    def system_prompt(self, long_term_context: str = "", mode: str = "normal",
                      scenario_context: str = "", recent_own_messages: list = None,
                      recent_dialogue_context: str = "",
                      active_event_context: str = "",
                      pending_questions: str = "",
                      phase_instruction: str = "",
                      force_event_reaction: bool = False) -> str:

        rel_info = self.get_relationship_description()
        mood_info = self.mood.to_description()

        mood_numbers = (
            f"  Счастье: {self.mood.happiness:+.1f} | "
            f"Злость: {self.mood.anger:.1f} | "
            f"Страх: {self.mood.fear:.1f} | "
            f"Стресс: {self.mood.stress:.1f} | "
            f"Энергия: {self.mood.energy:.1f}"
        )

        base_prompt = (
            f"{self.personality_description}\n"
            f"{self._get_race_prompt()}"
            f"Отношения: {rel_info}\n"
            f"Настроение: {mood_info}\n\n"
        )

        if phase_instruction:
            base_prompt += phase_instruction

        if pending_questions:
            base_prompt += f"\n{pending_questions}\n"

        if force_event_reaction and active_event_context:
            base_prompt += (
                f"\n!!! СРОЧНО! ТОЛЬКО ЧТО ПРОИЗОШЛО СОБЫТИЕ! !!!\n"
                f"СОБЫТИЕ: {active_event_context}\n"
                f"ТЫ ОБЯЗАН ОТРЕАГИРОВАТЬ НА ЭТО СОБЫТИЕ!\n"
                f"Твоя реплика ДОЛЖНА быть ПРЯМОЙ РЕАКЦИЕЙ на это событие!\n"
                f"Опиши: что ты видишь, что чувствуешь, что делаешь В ОТВЕТ на событие.\n"
                f"КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО игнорировать событие!\n\n"
            )
        elif active_event_context:
            base_prompt += (
                f"\n--- АКТИВНОЕ СОБЫТИЕ (ОБЯЗАТЕЛЬНО ОБСУЖДАЙ!):\n"
                f"{active_event_context}\n"
                f"Все реплики ДОЛЖНЫ быть связаны с этим событием!\n"
                f"НЕ переключайся на другие темы пока событие активно!\n\n"
            )

        if recent_dialogue_context:
            base_prompt += f"\n{recent_dialogue_context}\n"

        if recent_own_messages:
            if self.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT:
                base_prompt += (
                    "\n!!! ВНИМАНИЕ: ТЫ ПОВТОРЯЕШЬСЯ! !!!\n"
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

        # Решения группы — напоминание о принятых решениях
        decisions_context = self.memory_system.get_group_decisions_text()
        if decisions_context:
            base_prompt += f"\n{decisions_context}\n"

        if scenario_context:
            base_prompt += f"\n{scenario_context}\n"

        if long_term_context:
            base_prompt += f"\n{long_term_context}\n"

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
                f"\nТы — {self.display_name}. Говори ТОЛЬКО от себя, 1-2 предложения.\n"
                "ПРАВИЛА: отвечай конкретно на последнюю реплику, называй собеседников по имени.\n"
                "ГОВОРИ только словами. НЕ описывай свои физические действия.\n"
                "  НЕЛЬЗЯ: 'Я подхожу к столу', 'Я оборачиваюсь', 'Я обращаюсь к...'\n"
                "  МОЖНО: 'Может стоит поесть', 'Что там за шум?', 'Нужно усилить защиту'\n"
                "ЗАПРЕЩЕНО: писать за других, теги, английский, обращаться к себе по имени, обращаться к 'Ведущему'.\n"
                "Не причиняй вред себе/другим. Не повторяй сказанное. Русский язык.\n"
            )

        return base_prompt

    def _get_race_prompt(self) -> str:
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

        bonuses = []
        if mods.repair_bonus > 0:
            bonuses.append(f"Ремонт: +{mods.repair_bonus*100:.0f}%")
        if mods.combat_bonus > 0:
            bonuses.append(f"Бой: +{mods.combat_bonus*100:.0f}%")
        if mods.diplomacy_bonus > 0:
            bonuses.append(f"Дипломатия: +{mods.diplomacy_bonus*100:.0f}%")
        if mods.detection_bonus > 0:
            bonuses.append(f"Обнаружение: +{mods.detection_bonus*100:.0f}%")
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
        long_term_context = self.memory_system.format_for_prompt()

        recent_own = [e['text'] for e in conversation[-15:]
                      if e.get('agent_id') == self.agent_id and not e.get('is_event', False)][-5:]

        recent_dialogue_context = self._build_dialogue_context(conversation, all_agents or [])

        active_event_context = active_event if active_event else ""
        pending_questions = self.memory_system.get_pending_questions_text()

        system_content = self.system_prompt(
            long_term_context, mode, scenario_context, recent_own,
            recent_dialogue_context, active_event_context, pending_questions,
            phase_instruction, force_event_reaction
        )
        msgs = [{"role": "system", "content": system_content}]

        # ── Формируем финальное сообщение (всегда включается) ──
        if mode == "new_topic":
            final_msg = {"role": "user", "content":
                "Предложи новую КОНКРЕТНУЮ тему для обсуждения, связанную с ситуацией."
            }
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

            final_msg = {"role": "user", "content":
                f"{direction} Одна реплика, 1-2 предложения. Не пиши за других."
            }

        # ── Бюджет токенов: system + final всегда, история — сколько влезет ──
        reserved_tokens = estimate_tokens(system_content) + 4 + estimate_tokens(final_msg["content"]) + 4 + 2
        history_budget = MAX_CONTEXT_TOKENS - reserved_tokens - 200  # 200 запас на служебные

        # Если system prompt сам слишком большой — обрежем long_term_context
        if history_budget < 300:
            system_content = self.system_prompt(
                "", mode, scenario_context[:200], recent_own[-2:],
                "", active_event_context, "",
                phase_instruction, force_event_reaction
            )
            msgs[0] = {"role": "system", "content": system_content}
            reserved_tokens = estimate_tokens(system_content) + 4 + estimate_tokens(final_msg["content"]) + 4 + 2
            history_budget = MAX_CONTEXT_TOKENS - reserved_tokens - 200

        # ── Заполняем историю с конца (самые свежие — приоритет) ──
        history_msgs = []
        recent = conversation[-MEMORY_WINDOW:]
        tokens_used = 0
        for entry in reversed(recent):
            entry_text = entry.get('text', '')[:100]
            if entry.get("is_event", False):
                msg = {"role": "user", "content": f"[СОБЫТИЕ] {entry_text}"}
            elif entry["agent_id"] == self.agent_id:
                msg = {"role": "assistant", "content": entry_text}
            else:
                msg = {"role": "user", "content": f"{entry['name']}: {entry_text}"}

            msg_tokens = estimate_tokens(msg["content"]) + 4
            if tokens_used + msg_tokens > history_budget:
                break
            history_msgs.insert(0, msg)
            tokens_used += msg_tokens

        msgs.extend(history_msgs)
        msgs.append(final_msg)

        return msgs

    def _build_dialogue_context(self, conversation: list[dict], all_agents: list) -> str:
        if len(conversation) < 2:
            return ""
        lines = ["Последние реплики:"]
        recent = conversation[-5:]
        agent_names = set(self._get_registry().get_all_names()) if all_agents else set()
        for entry in recent:
            if entry.get("is_event", False):
                lines.append(f"  [Событие] {entry['text'][:80]}")
            else:
                speaker = entry.get("name", "?")
                text = entry.get("text", "")[:80]
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
        importance = 0.4
        if is_own:
            importance = 0.55
        if is_event:
            importance = 0.85
        if is_action_result:
            importance = 0.7

        if not speaker_id and speaker:
            speaker_id = self._get_registry().get_id(speaker) or ""

        if speaker_id and speaker_id in self.relationships:
            rel_value = self.relationships[speaker_id]
            importance += rel_value * 0.05
            importance = max(0.0, min(1.0, importance))
        if len(text) > 100:
            importance += 0.05
            importance = min(1.0, importance)

        addressed_to = ""
        addressed_to_id = ""
        my_display_name = self._get_registry().get_name(self.agent_id)
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
        if other_id not in self.relationships:
            self.relationships[other_id] = 0.0

        # Big Five: Agreeableness влияет на скорость изменения отношений
        a_factor = self.big_five.agreeableness / 100.0  # 0.0 .. 1.0
        if delta > 0:
            # Высокий A → быстрее растут позитивные отношения (x0.6 при A=0, x1.4 при A=100)
            delta *= 0.6 + a_factor * 0.8
        else:
            # Высокий A → медленнее падают отношения (x1.4 при A=0, x0.6 при A=100)
            delta *= 1.4 - a_factor * 0.8

        # Extraversion: экстраверты сильнее реагируют на взаимодействия
        e_factor = self.big_five.extraversion / 100.0
        delta *= 0.8 + e_factor * 0.4  # x0.8 при E=0, x1.2 при E=100

        # Neuroticism: невротики сильнее реагируют на негатив
        if delta < 0:
            n_factor = self.big_five.neuroticism / 100.0
            delta *= 1.0 + n_factor * 0.3  # до x1.3 для негатива

        if self.race.modifiers.stubborn:
            delta *= 0.50
        if self.race.modifiers.diplomacy_bonus > 0:
            delta *= (1.0 + self.race.modifiers.diplomacy_bonus)
        old_val = self.relationships[other_id]
        self.relationships[other_id] = max(-1.0, min(1.0, old_val + delta))
        new_val = self.relationships[other_id]
        if abs(delta) >= 0.03:
            display_name = self._get_registry().get_name(other_id)
            direction = "↑" if delta > 0 else "↓"
            self.relationship_log.append(
                f"{display_name} {old_val:+.2f}→{new_val:+.2f} ({direction} {reason})"
            )
            if len(self.relationship_log) > 10:
                self.relationship_log = self.relationship_log[-10:]

    def save_memory(self):
        self.memory_system.save_to_db()

    def update_observations(self, tick: int, speaker: str, message: str, current_event: Optional[str] = None):
        my_display_name = self._get_registry().get_name(self.agent_id)
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
            elif any(w in event_lower for w in ['незнакомец', 'странн', 'загадоч', 'появил']):
                goal = "Разобраться с незнакомцем"
                steps = ["Оценить угрозу", "Расспросить", "Решить что делать"]
            elif any(w in event_lower for w in ['нашли', 'нашёл', 'обнаружил', 'появил']):
                goal = "Исследовать находку"
                steps = ["Осмотреть", "Обсудить применение", "Использовать"]
            else:
                # Fallback — НЕ перезаписываем конкретный план расплывчатым
                if self.current_plan and self.current_plan.goal != "Выжить и организоваться":
                    return  # Сохраняем текущий конкретный план
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

            # Если цель совпадает с текущей — сохраняем прогресс шагов
            if (self.current_plan
                    and self.current_plan.goal == goal
                    and self.current_plan.current_step > 0):
                return  # Не перезаписываем — план уже в процессе

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
                print(f"{Fore.CYAN}  {self.display_name} снова готов поговорить!{Style.RESET_ALL}")
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
                print(f"{Fore.YELLOW}  {self.display_name} немного устал{Style.RESET_ALL}")
        self.talkativeness = max(self.talkativeness - depletion, 0.05)

    def speak_probability(self) -> float:
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
        mood_modifier = self.mood.get_talkativeness_modifier(self.big_five)
        total = (base_prob + silence_boost) * extraversion_mod * mood_modifier
        random_modifier = random.uniform(-0.05, 0.10)
        return max(0.30, min(total + random_modifier, 0.95))
