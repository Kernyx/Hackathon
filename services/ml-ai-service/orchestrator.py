"""
Оркестратор: create_agents(), BigBrotherOrchestrator.
Пресеты расового состава вынесены в data_presets/race_presets.py.
"""

import re
import time
import random
from typing import Optional

from colorama import Fore, Style

from config import (
    MAX_RESPONSE_CHARS, MEMORY_WINDOW,
    EVENT_FOCUS_DURATION, EVENT_FORCED_REACTION_TICKS,
    SCENARIO_EVENT_INTERVAL, CREATIVITY_BOOST,
    RELATIONSHIP_CHANGE_RATE, REPETITION_SIMILARITY_THRESHOLD,
    REPETITION_CONSECUTIVE_LIMIT, PHASE_TICKS,
    GOBLIN_DISTRUST, TICK_DELAY,
)
from models import (
    PersonalityType, BigFiveTraits, RaceType,
    RACES, AgentMood,
)
from memory import AgentMemorySystem
from agent_registry import agent_registry
from agent import Agent
from topics import TopicManager, DialoguePhaseManager
from scenarios import ScenarioManager, UserEventInput
from llm_client import llm_chat
from utils import text_similarity, extract_phrases, has_banned_pattern, has_repetitive_pattern
from audit_client import send_audit_event
from data_presets.race_presets import RACE_PRESETS, AGENT_COLORS


def create_agents(race_preset: str = "humans", user_id: str = "",
                  registry: 'AgentRegistry' = None) -> list['Agent']:
    """Создать агентов по выбранному расовому пресету.
    
    Args:
        race_preset: Ключ пресета расового состава.
        user_id: ID пользователя для изоляции данных.
        registry: Изолированный реестр агентов сессии (если None — глобальный).
    """
    _reg = registry if registry is not None else agent_registry
    preset = RACE_PRESETS.get(race_preset, RACE_PRESETS["humans"])
    agents_data = preset["agents"]

    agents = []
    for i, data in enumerate(agents_data):
        color = AGENT_COLORS[i % len(AGENT_COLORS)]

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
            user_id=user_id,
            _registry=registry,
        )
        agents.append(agent)

    for a in agents:
        _reg.register(a.agent_id, a.name)

    for a in agents:
        for b in agents:
            if a.agent_id != b.agent_id:
                if a.personality_type == PersonalityType.MACHIAVELLIAN:
                    base_rel = round(random.uniform(-0.8, -0.5), 2)
                else:
                    base_rel = round(random.uniform(-0.1, 0.1), 2)

                racial_mod = a.race.racial_relations.get(b.race.race_type, 0.0)

                if b.race.race_type == RaceType.GOBLIN and a.race.race_type != RaceType.GOBLIN:
                    racial_mod += GOBLIN_DISTRUST

                if a.race.race_type == RaceType.HUMAN:
                    racial_mod += 0.05

                total = round(max(-1.0, min(1.0, base_rel + racial_mod)), 2)
                a.relationships[b.agent_id] = total
    return agents


class BigBrotherOrchestrator:
    def __init__(self, agents: list[Agent], scenario_name: str = "desert_island",
                 user_event_input: Optional[UserEventInput] = None,
                 user_id: str = "", registry: 'AgentRegistry' = None):
        self.agents = agents
        self.user_id = user_id
        self._registry = registry if registry is not None else agent_registry
        self.conversation: list[dict] = []
        self.tick = 0
        self.topic_manager = TopicManager(user_id=user_id)
        self.scenario_manager = ScenarioManager(scenario_name, user_id=user_id)
        self.active_event: Optional[str] = None
        self.event_started_tick: int = 0
        self.quality_warnings: int = 0
        self.last_warning_reason: str = ""
        self.last_speaker_id: Optional[str] = None
        self.phase_manager = DialoguePhaseManager()
        self.event_reacted_agents: set = set()
        self.last_visible_tick: int = 0
        self.user_event_input = user_event_input
        self._quit_requested = False
        self.tick_delay = TICK_DELAY
        self._next_agent_index = len(agents)  # Счётчик для уникальных agent_id

    # ─── Динамическое управление агентами ─────────────────────

    def add_agent(self, name: str, race_type: RaceType,
                  personality: PersonalityType = PersonalityType.ALTRUIST,
                  is_male: bool = True, age: int = 25,
                  interests: str = "", info: str = "") -> Optional[Agent]:
        """Добавить нового агента в работающую симуляцию."""
        # Проверка уникальности имени
        if self._registry.get_id(name):
            print(f"{Fore.RED}Агент с именем '{name}' уже существует!{Style.RESET_ALL}")
            return None

        self._next_agent_index += 1
        agent_id = f"agent_{self._next_agent_index}"
        color = AGENT_COLORS[(self._next_agent_index - 1) % len(AGENT_COLORS)]

        if personality == PersonalityType.MACHIAVELLIAN:
            big_five = BigFiveTraits(
                openness=40, conscientiousness=30, extraversion=85,
                agreeableness=5, neuroticism=90
            )
        else:
            big_five = BigFiveTraits.from_personality_type(personality)

        agent = Agent(
            agent_id=agent_id,
            name=name,
            personality_type=personality,
            big_five=big_five,
            race_type=race_type,
            is_male=is_male,
            age=age,
            interests=interests,
            additional_info=info,
            color=color,
            user_id=self.user_id,
            _registry=self._registry,
        )

        self._registry.register(agent_id, name)

        # Установить отношения с существующими агентами
        for existing in self.agents:
            # Новый → существующий
            if personality == PersonalityType.MACHIAVELLIAN:
                base_rel = round(random.uniform(-0.8, -0.5), 2)
            else:
                base_rel = round(random.uniform(-0.1, 0.1), 2)
            racial_mod = agent.race.racial_relations.get(existing.race.race_type, 0.0)
            if existing.race.race_type == RaceType.GOBLIN and agent.race.race_type != RaceType.GOBLIN:
                racial_mod += GOBLIN_DISTRUST
            if agent.race.race_type == RaceType.HUMAN:
                racial_mod += 0.05
            total = round(max(-1.0, min(1.0, base_rel + racial_mod)), 2)
            agent.relationships[existing.agent_id] = total

            # Существующий → новый
            if existing.personality_type == PersonalityType.MACHIAVELLIAN:
                base_rel2 = round(random.uniform(-0.8, -0.5), 2)
            else:
                base_rel2 = round(random.uniform(-0.1, 0.1), 2)
            racial_mod2 = existing.race.racial_relations.get(agent.race.race_type, 0.0)
            if agent.race.race_type == RaceType.GOBLIN and existing.race.race_type != RaceType.GOBLIN:
                racial_mod2 += GOBLIN_DISTRUST
            if existing.race.race_type == RaceType.HUMAN:
                racial_mod2 += 0.05
            total2 = round(max(-1.0, min(1.0, base_rel2 + racial_mod2)), 2)
            existing.relationships[agent_id] = total2

        self.agents.append(agent)

        # Обновить список имён в UserEventInput
        if self.user_event_input:
            self.user_event_input.agent_names = self._registry.get_all_names()

        # Дать агенту контекст последних сообщений
        for entry in self.conversation[-10:]:
            agent.process_message(
                entry.get("tick", self.tick),
                entry.get("name", ""),
                entry.get("text", ""),
                is_own=False,
                is_event=entry.get("is_event", False),
            )

        # Объявить о появлении нового агента
        race = agent.race
        gender_icon = "M" if is_male else "F"
        join_text = f"{race.emoji} {name} ({race.name_ru}, {gender_icon}, {age} лет) присоединяется к группе!"

        print(f"\n{Fore.GREEN}{'=' * 60}")
        print(f"{Fore.GREEN}  НОВЫЙ АГЕНТ ПРИСОЕДИНЯЕТСЯ!")
        print(f"{Fore.GREEN}{'=' * 60}")
        print(f"  {agent.color}{Style.BRIGHT}{race.emoji} {gender_icon} {name} ({age} лет) [{race.name_ru}] [{personality.value}]{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}Раса: {race.name_ru} -- {race.description}{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}Big Five: O:{agent.big_five.openness} C:{agent.big_five.conscientiousness} "
              f"E:{agent.big_five.extraversion} A:{agent.big_five.agreeableness} N:{agent.big_five.neuroticism}{Style.RESET_ALL}")
        if interests:
            print(f"     {Fore.WHITE}Интересы: {interests}{Style.RESET_ALL}")
        if info:
            print(f"     {Fore.WHITE}Характер: {info}{Style.RESET_ALL}")
        mods = race.modifiers
        bonuses = []
        if mods.repair_bonus > 0:
            bonuses.append(f"Ремонт +{mods.repair_bonus*100:.0f}%")
        if mods.combat_bonus > 0:
            bonuses.append(f"Бой +{mods.combat_bonus*100:.0f}%")
        if mods.diplomacy_bonus > 0:
            bonuses.append(f"Дипломатия +{mods.diplomacy_bonus*100:.0f}%")
        if mods.detection_bonus > 0:
            bonuses.append(f"Обнаружение +{mods.detection_bonus*100:.0f}%")
        if mods.can_betray:
            bonuses.append("предатель")
        if mods.stubborn:
            bonuses.append("упрямый")
        if bonuses:
            print(f"     {Fore.YELLOW}Бонусы: {', '.join(bonuses)}{Style.RESET_ALL}")
        dominant = agent.mood.get_dominant_emotion()
        print(f"     {Fore.WHITE}Настроение: {dominant} "
              f"(Счастье:{agent.mood.happiness:+.1f} Энергия:{agent.mood.energy:.1f} "
              f"Стресс:{agent.mood.stress:.1f} Злость:{agent.mood.anger:.1f} Страх:{agent.mood.fear:.1f}){Style.RESET_ALL}")
        # Отношения с группой
        rel_parts = []
        for other in self.agents:
            if other.agent_id != agent.agent_id:
                other_display = self._registry.get_name(other.agent_id)
                rel_val = agent.relationships.get(other.agent_id, 0.0)
                rel_parts.append(f"{other_display}:{rel_val:+.2f}")
        if rel_parts:
            print(f"     {Fore.WHITE}Отношения: {', '.join(rel_parts)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'=' * 60}\n")

        join_entry = {
            "tick": self.tick, "agent_id": "system",
            "name": "Ведущий", "text": join_text, "is_event": True,
        }
        self.conversation.append(join_entry)
        for a in self.agents:
            a.process_message(self.tick, "Ведущий", join_text, is_own=False, is_event=True)

        return agent

    def remove_agent(self, name: str) -> bool:
        """Удалить агента из работающей симуляции."""
        found_id = self._registry.get_id_fuzzy(name)
        if not found_id:
            print(f"{Fore.RED}Агент '{name}' не найден! "
                  f"Доступные: {', '.join(self._registry.get_all_names())}{Style.RESET_ALL}")
            return False

        agent = next((a for a in self.agents if a.agent_id == found_id), None)
        if not agent:
            print(f"{Fore.RED}Агент '{name}' не найден в симуляции!{Style.RESET_ALL}")
            return False

        if len(self.agents) <= 2:
            print(f"{Fore.RED}Нельзя удалить — минимум 2 агента для симуляции!{Style.RESET_ALL}")
            return False

        display_name = self._registry.get_name(found_id)
        race = agent.race

        # Сохранить память перед удалением
        agent.save_memory()

        # Удалить из списка
        self.agents.remove(agent)

        # Удалить из реестра
        self._registry.unregister(found_id)

        # Удалить отношения у других агентов
        for a in self.agents:
            a.relationships.pop(found_id, None)

        # Удалить из event_reacted_agents
        self.event_reacted_agents.discard(found_id)

        # Сбросить last_speaker_id если это был удалённый агент
        if self.last_speaker_id == found_id:
            self.last_speaker_id = None

        # Обновить список имён в UserEventInput
        if self.user_event_input:
            self.user_event_input.agent_names = self._registry.get_all_names()

        # Объявить об уходе агента
        leave_text = f"{race.emoji} {display_name} ({race.name_ru}) покидает группу."

        print(f"\n{Fore.RED}{'=' * 60}")
        print(f"{Fore.RED}АГЕНТ УШЁЛ: {leave_text}")
        print(f"{Fore.RED}{'=' * 60}\n")

        leave_entry = {
            "tick": self.tick, "agent_id": "system",
            "name": "Ведущий", "text": leave_text, "is_event": True,
        }
        self.conversation.append(leave_entry)
        for a in self.agents:
            a.process_message(self.tick, "Ведущий", leave_text, is_own=False, is_event=True)

        return True

    def _list_agents(self):
        """Вывести список текущих агентов."""
        print(f"\n{Fore.CYAN}{'─' * 50}")
        print(f"{Fore.CYAN}ТЕКУЩИЕ АГЕНТЫ ({len(self.agents)}):")
        print(f"{Fore.CYAN}{'─' * 50}")
        for a in self.agents:
            display = self._registry.get_name(a.agent_id)
            gender_icon = "M" if a.is_male else "F"
            race = a.race
            dominant = a.mood.get_dominant_emotion()
            print(f"  {a.color}{race.emoji} {gender_icon} {display} ({a.age} лет) "
                  f"[{race.name_ru}] [{a.personality_type.value}] "
                  f"Настроение: {dominant}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─' * 50}\n")

    # ─── Маппинг расы из текста ───────────────────────────────

    # Пресеты характеров: для каждой расы и личности — интересы, доп.инфо, варианты пола/возраста
    DYNAMIC_AGENT_PRESETS: dict[tuple[RaceType, PersonalityType], dict] = {
        # ── HUMAN ──
        (RaceType.HUMAN, PersonalityType.ALTRUIST): {
            "interests": ["психология, помощь людям, искусство",
                          "медицина, дипломатия, переговоры",
                          "лидерство, защита, стратегия",
                          "педагогика, социальная работа, музыка"],
            "info": ["Всегда готов(а) поддержать и выслушать. Верит в лучшее в людях.",
                     "Прирождённый лидер-дипломат. Пытается объединить группу.",
                     "Заботливая натура. Ставит интересы группы выше своих.",
                     "Миротворец по призванию. Находит компромиссы там, где другие видят тупик."],
            "age_range": (20, 40),
        },
        (RaceType.HUMAN, PersonalityType.STOIC): {
            "interests": ["технологии, наука, логика",
                          "философия, анализ, шахматы",
                          "инженерия, математика, тактика",
                          "история, стратегия, выживание"],
            "info": ["Предпочитает факты эмоциям, анализирует ситуацию холодно и рационально.",
                     "Невозмутим и расчётлив. Принимает решения на основе логики, не эмоций.",
                     "Хладнокровен под давлением. Молчит, пока не найдёт лучший вариант.",
                     "Методичен и терпелив. Не поддаётся панике, даже когда всё плохо."],
            "age_range": (25, 45),
        },
        (RaceType.HUMAN, PersonalityType.MACHIAVELLIAN): {
            "interests": ["власть, манипуляции, критика всех вокруг",
                          "интриги, контроль, подчинение",
                          "политика, обман, самоутверждение",
                          "провокации, скандалы, доминирование"],
            "info": ["Крайне токсичная и скандальная личность. ВСЕГДА недоволен(а) другими, ругается, оскорбляет.",
                     "Манипулятор от природы. Видит в каждом слабость и использует её.",
                     "Агрессивен и язвителен. Никому не доверяет, всех подозревает в худшем.",
                     "Провокатор и интриган. Сеет раздор ради собственной выгоды."],
            "age_range": (22, 38),
        },
        (RaceType.HUMAN, PersonalityType.REBEL): {
            "interests": ["свобода, бунт, нестандартные решения",
                          "приключения, риск, экстрим",
                          "анархия, креатив, нарушение правил",
                          "исследования, авантюры, импровизация"],
            "info": ["Не признаёт авторитетов. Делает всё по-своему и всегда идёт против течения.",
                     "Авантюрист. Предпочитает действовать, а не обсуждать. Рискует ради интереса.",
                     "Бунтарь-одиночка. Спорит ради спора, но иногда подкидывает гениальные идеи.",
                     "Непредсказуемый и импульсивный. Может удивить и спасти, а может всё усложнить."],
            "age_range": (18, 35),
        },
        # ── ELF ──
        (RaceType.ELF, PersonalityType.ALTRUIST): {
            "interests": ["целительство, природа, знания",
                          "гармония, защита леса, травничество",
                          "музыка, поэзия, исцеление"],
            "info": ["Мудрая эльфийская натура. Стремится к гармонии и исцелению всех вокруг.",
                     "Древний целитель. Спокоен, мудр, видит красоту даже в хаосе.",
                     "Покровитель слабых. Долгая жизнь научила ценить каждое существо."],
            "age_range": (100, 500),
        },
        (RaceType.ELF, PersonalityType.STOIC): {
            "interests": ["природа, мудрость, стрельба из лука",
                          "древние знания, магия, история",
                          "медитация, наблюдение, тактика"],
            "info": ["Древний эльф, видевший многое. Высокомерен к другим расам, но справедлив.",
                     "Древний мудрец. Высокомерен, но незаменим в сложных решениях.",
                     "Молчаливый наблюдатель. Говорит редко, но каждое слово — на вес золота."],
            "age_range": (200, 600),
        },
        (RaceType.ELF, PersonalityType.MACHIAVELLIAN): {
            "interests": ["тайные знания, манипуляции, власть над природой",
                          "интриги, тёмная магия, контроль",
                          "доминирование, презрение к смертным"],
            "info": ["Тёмный эльф-интриган. Считает себя выше всех и не стесняется этого показывать.",
                     "Высокомерен до предела. Манипулирует «низшими расами» ради своих целей.",
                     "Жесток и расчётлив. Века жизни сделали его циничным и безжалостным."],
            "age_range": (150, 500),
        },
        (RaceType.ELF, PersonalityType.REBEL): {
            "interests": ["приключения, нарушение традиций, свобода",
                          "изгнание, одиночество, непокорность",
                          "странствия, бунт против эльфийских устоев"],
            "info": ["Эльф-изгнанник, отвергший традиции своего народа. Идёт своим путём.",
                     "Молодой бунтарь. Презирает эльфийское высокомерие и ищет дружбу среди «низших».",
                     "Нетипичный эльф. Импульсивен, дерзок и непредсказуем."],
            "age_range": (80, 300),
        },
        # ── DWARF ──
        (RaceType.DWARF, PersonalityType.ALTRUIST): {
            "interests": ["кузнечное дело, помощь товарищам, защита",
                          "строительство, горное дело, братство",
                          "ремёсла, угощение друзей, честный труд"],
            "info": ["Надёжный дварф — скала, на которую можно опереться. Защитит любого товарища.",
                     "Щедрый мастеровой. Угостит элем и починит что угодно, лишь бы все были довольны.",
                     "Верный друг. Упрям, но его сердце полно заботы о ближних."],
            "age_range": (80, 200),
        },
        (RaceType.DWARF, PersonalityType.STOIC): {
            "interests": ["камнерезное дело, архитектура подземелий, руны",
                          "история кланов, оружейное дело, стойкость",
                          "шахты, геология, традиции предков"],
            "info": ["Невозмутимый дварф-мастер. Молчит и работает, когда другие паникуют.",
                     "Хранитель традиций. Спокоен как гранит, но если решит — не свернёт.",
                     "Старый рудокоп. Видел обвалы и подземных тварей — его ничем не напугать."],
            "age_range": (100, 250),
        },
        (RaceType.DWARF, PersonalityType.MACHIAVELLIAN): {
            "interests": ["золото, сокровища, накопление богатств",
                          "торговля, обман, жадность",
                          "власть в клане, политические интриги"],
            "info": ["Жадный дварф-торгаш. Считает каждую монету и никому не доверяет своё добро.",
                     "Хитрый и скупой. Прячет лучшие ресурсы и всегда берёт больше, чем отдаёт.",
                     "Властолюбивый дварф. Считает, что только он знает, как правильно."],
            "age_range": (90, 180),
        },
        (RaceType.DWARF, PersonalityType.REBEL): {
            "interests": ["кузнечное дело, горное дело, пиво",
                          "бунт, упрямство, нарушение приказов",
                          "эксперименты с рунами, взрывчатка, нестандартные решения"],
            "info": ["Упрямый дварф-мастер. Жаден при дележе, но надёжен в бою. Делает по-своему.",
                     "Бунтарь-кузнец. Плюёт на правила и авторитеты, но его работа — шедевр.",
                     "Мастер-кузнец. Упрям как скала, жаден при дележе, но верный товарищ."],
            "age_range": (80, 200),
        },
        # ── ORC ──
        (RaceType.ORC, PersonalityType.ALTRUIST): {
            "interests": ["защита племени, честь, боевые искусства",
                          "братство, наставничество, охота",
                          "справедливость, сила ради добра"],
            "info": ["Благородный орк-воин. Защищает слабых и сражается за правое дело.",
                     "Честный и прямой. Уважает силу, но ещё больше уважает тех, кто защищает других.",
                     "Орк-наставник. Грубоват, но искренне заботится о товарищах."],
            "age_range": (18, 35),
        },
        (RaceType.ORC, PersonalityType.STOIC): {
            "interests": ["бой, выносливость, оружие",
                          "тактика, молчаливая сила, стойкость",
                          "воинская дисциплина, честь, закалка"],
            "info": ["Молчаливый орк-воин. Презирает трусов. Готов защищать группу до конца.",
                     "Невозмутимый боец. Говорит мало, бьёт сильно, никогда не отступает.",
                     "Железная воля. Не знает страха и не понимает тех, кто боится."],
            "age_range": (20, 35),
        },
        (RaceType.ORC, PersonalityType.MACHIAVELLIAN): {
            "interests": ["бой, оружие, сила",
                          "доминирование, запугивание, агрессия",
                          "власть, жестокость, завоевание"],
            "info": ["Агрессивный орк-воин. Уважает только силу и храбрость. Презирает слабых и трусов.",
                     "Свирепый орк-воин. Уважает только силу. Агрессивен, но честен в бою.",
                     "Берсерк. Готов сражаться со всеми подряд, не разбирая правых и виноватых."],
            "age_range": (18, 30),
        },
        (RaceType.ORC, PersonalityType.REBEL): {
            "interests": ["свобода, охота, одиночные вылазки",
                          "нарушение приказов, дикая природа, инстинкты",
                          "бродяжничество, бунт, импульсивность"],
            "info": ["Орк-одиночка. Не признаёт вождей и идёт своим путём. Дикий и непредсказуемый.",
                     "Бунтарь среди орков. Отвергает правила клана, полагается только на себя.",
                     "Дикий орк. Импульсивен и яростен, но в нём есть странная мудрость."],
            "age_range": (16, 28),
        },
        # ── GOBLIN ──
        (RaceType.GOBLIN, PersonalityType.ALTRUIST): {
            "interests": ["хитрость на благо группы, мелкие услуги, разведка",
                          "готовка, собирательство, помощь по-гоблински",
                          "шпионаж, предупреждение об опасности"],
            "info": ["Необычный гоблин — действительно хочет помочь! Хитрый, но на стороне группы.",
                     "Гоблин-разведчик. Труслив, но старается быть полезным. Всех предупреждает об опасности.",
                     "Добродушный гоблин (редкость!). Услужлив и суетлив, но искренне предан товарищам."],
            "age_range": (8, 18),
        },
        (RaceType.GOBLIN, PersonalityType.STOIC): {
            "interests": ["выживание, осторожность, наблюдение",
                          "ловушки, скрытность, расчёт",
                          "тихая хитрость, терпение, засады"],
            "info": ["Тихий гоблин-наблюдатель. Молчит, выжидает и действует только наверняка.",
                     "Осторожный гоблин. Не суетится, не паникует — просто тихо выживает.",
                     "Хладнокровный гоблин-тактик. Редкость среди своего народа."],
            "age_range": (10, 20),
        },
        (RaceType.GOBLIN, PersonalityType.MACHIAVELLIAN): {
            "interests": ["воровство, обман, манипуляции",
                          "предательство, шантаж, скрытые намерения",
                          "накопительство, хитрость, двуличие"],
            "info": ["Коварный гоблин. Улыбается в лицо и крадёт за спиной. Предаст при первой возможности.",
                     "Гоблин-предатель. Хитёр, жаден и абсолютно беспринципен.",
                     "Мерзкий пройдоха. Ворует, врёт, предаёт — и не испытывает ни капли стыда."],
            "age_range": (8, 20),
        },
        (RaceType.GOBLIN, PersonalityType.REBEL): {
            "interests": ["воровство, хитрость, выживание",
                          "проказы, хаос, непредсказуемость",
                          "побеги, уловки, мелкие пакости"],
            "info": ["Трусливый гоблин-пройдоха. Хитёр, жаден, может предать группу при опасности.",
                     "Хаотичный гоблин. Делает что попало, паникует, но иногда случайно спасает всех.",
                     "Суетливый трусишка. Бежит первым, но может вернуться... если выгодно."],
            "age_range": (6, 18),
        },
    }

    @staticmethod
    def _parse_race_name(race_str: str) -> Optional[RaceType]:
        """Распознать расу из строки пользователя."""
        race_map = {
            'human': RaceType.HUMAN, 'человек': RaceType.HUMAN, 'чел': RaceType.HUMAN,
            'elf': RaceType.ELF, 'эльф': RaceType.ELF,
            'dwarf': RaceType.DWARF, 'дварф': RaceType.DWARF, 'гном': RaceType.DWARF,
            'orc': RaceType.ORC, 'орк': RaceType.ORC,
            'goblin': RaceType.GOBLIN, 'гоблин': RaceType.GOBLIN, 'гоб': RaceType.GOBLIN,
        }
        return race_map.get(race_str.lower().strip())

    @staticmethod
    def _parse_personality_name(pers_str: str) -> PersonalityType:
        """Распознать тип личности из строки пользователя."""
        pers_map = {
            'altruist': PersonalityType.ALTRUIST, 'альтруист': PersonalityType.ALTRUIST,
            'добрый': PersonalityType.ALTRUIST,
            'machiavellian': PersonalityType.MACHIAVELLIAN, 'макиавеллист': PersonalityType.MACHIAVELLIAN,
            'злой': PersonalityType.MACHIAVELLIAN,
            'rebel': PersonalityType.REBEL, 'бунтарь': PersonalityType.REBEL,
            'stoic': PersonalityType.STOIC, 'стоик': PersonalityType.STOIC,
        }
        return pers_map.get(pers_str.lower().strip(), PersonalityType.ALTRUIST)

    def _handle_add_agent(self, raw_command: str):
        """Обработать команду добавления агента: add <раса> <имя> [личность]"""
        # Убираем префикс команды
        for prefix in ('add ', 'добавить '):
            if raw_command.lower().startswith(prefix):
                raw_command = raw_command[len(prefix):].strip()
                break

        parts = raw_command.split()
        if len(parts) < 2:
            print(f"{Fore.YELLOW}Формат: add <раса> <имя> [личность]{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Расы: human/человек, elf/эльф, dwarf/дварф, orc/орк, goblin/гоблин{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Личности (опц.): altruist/альтруист, stoic/стоик, rebel/бунтарь, machiavellian/макиавеллист{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Пример: add elf Леголас stoic{Style.RESET_ALL}")
            return

        race_str = parts[0]
        name = parts[1]
        personality = PersonalityType.ALTRUIST
        if len(parts) >= 3:
            personality = self._parse_personality_name(parts[2])

        race_type = self._parse_race_name(race_str)
        if race_type is None:
            print(f"{Fore.RED}Неизвестная раса: '{race_str}'. "
                  f"Доступные: human/человек, elf/эльф, dwarf/дварф, orc/орк, goblin/гоблин{Style.RESET_ALL}")
            return

        # Получить пресет характера для расы+личности
        preset_key = (race_type, personality)
        preset = self.DYNAMIC_AGENT_PRESETS.get(preset_key)
        if preset:
            interests = random.choice(preset["interests"])
            info = random.choice(preset["info"])
            age_min, age_max = preset["age_range"]
            age = random.randint(age_min, age_max)
        else:
            # Фоллбэк — базовые значения по расе
            interests = "выживание, наблюдение"
            info = "Новый участник группы."
            age_defaults = {
                RaceType.HUMAN: (20, 40), RaceType.ELF: (100, 500),
                RaceType.DWARF: (80, 200), RaceType.ORC: (18, 35),
                RaceType.GOBLIN: (8, 20),
            }
            age_min, age_max = age_defaults.get(race_type, (20, 40))
            age = random.randint(age_min, age_max)

        # Пол: для гендерно-нейтральных имён — рандом, но для info подставляем окончания
        is_male = random.choice([True, False])
        # Адаптируем окончания в info под пол
        if not is_male:
            info = info.replace("готов ", "готова ")
            info = info.replace("Готов ", "Готова ")
            info = info.replace("готов(а)", "готова")
            info = info.replace("недоволен(а)", "недовольна")
            info = info.replace("Невозмутим ", "Невозмутима ")
            info = info.replace("Агрессивен ", "Агрессивна ")
            info = info.replace("Хладнокровен ", "Хладнокровна ")
            info = info.replace("Расчётлив.", "Расчётлива.")
            info = info.replace("Упрям,", "Упряма,")
            info = info.replace("Хитёр,", "Хитра,")
            info = info.replace("Жаден ", "Жадна ")
            info = info.replace("Молчалив ", "Молчалива ")
            info = info.replace("Импульсивен ", "Импульсивна ")
        else:
            info = info.replace("готов(а)", "готов")
            info = info.replace("недоволен(а)", "недоволен")

        self.add_agent(
            name=name,
            race_type=race_type,
            personality=personality,
            is_male=is_male,
            age=age,
            interests=interests,
            info=info,
        )

    def _handle_remove_agent(self, raw_command: str):
        """Обработать команду удаления агента: remove <имя>"""
        for prefix in ('remove ', 'удалить '):
            if raw_command.lower().startswith(prefix):
                raw_command = raw_command[len(prefix):].strip()
                break
        if not raw_command:
            print(f"{Fore.YELLOW}Формат: remove <имя агента>{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Доступные: {', '.join(self._registry.get_all_names())}{Style.RESET_ALL}")
            return
        self.remove_agent(raw_command)

    def inject_user_event(self, event_text: str):
        event_text = event_text.strip()
        if not event_text:
            return

        if not any(event_text.startswith(e) for e in ['🔥', '🌧', '⚠', '📡', '🦀', '🌊',
                                                       '🐍', '⛵', '🌅', '💨', '📦', '🔫',
                                                       '📻', '💊', '🔦', '🚁', '🗝', '🌙',
                                                       '⚡', '🍱', '🔧', '📊', '🌠', '💤',
                                                       '🍺', '⚔', '🎲', '🎵', '🗺', '🔮',
                                                       '🍖', '👤', '🧟', '🎬']):
            event_text = f"[EVENT] {event_text}"

        print(f"\n{Fore.MAGENTA}{'=' * 60}")
        print(f"{Fore.MAGENTA}СОБЫТИЕ ОТ ИГРОКА: {event_text}")
        print(f"{Fore.MAGENTA}{'=' * 60}\n")

        self.active_event = event_text
        self.event_started_tick = self.tick
        self.event_reacted_agents = set()

        self.scenario_manager.events_triggered.append(event_text)
        self.scenario_manager.save_to_db()

        event_entry = {
            "tick": self.tick, "agent_id": "user_event",
            "name": "Событие (Игрок)", "text": event_text, "is_event": True,
        }
        self.conversation.append(event_entry)

        for agent in self.agents:
            agent.process_message(self.tick, "Событие (Игрок)", event_text,
                                  is_own=False, is_event=True)
            agent.update_observations(self.tick, "Событие (Игрок)", event_text, event_text)
            agent.active_event = event_text
            agent.event_focus_tick = self.tick
            agent.reacted_to_event = False
            agent.mood.apply_event(event_text, agent.personality_type, agent.big_five, agent.race.modifiers)

        scenario_ctx = self.scenario_manager.get_scenario_context()
        consequence = self._generate_event_consequence(event_text, scenario_ctx)
        if consequence:
            print(f"{Fore.YELLOW}Последствие: {consequence}{Style.RESET_ALL}")
            consequence_entry = {
                "tick": self.tick, "agent_id": "world",
                "name": "Мир", "text": consequence, "is_event": True,
            }
            self.conversation.append(consequence_entry)
            for agent in self.agents:
                agent.process_message(self.tick, "Мир", consequence,
                                      is_own=False, is_action_result=True)

    def inject_user_message(self, message_text: str, target_agents: list[Agent]):
        """Инжектить сообщение пользователя (терминальный режим, с print)."""
        responses = self._inject_user_message_core(message_text, target_agents)
        # Печать для терминального режима
        for resp in responses:
            agent = next((a for a in self.agents if a.agent_id == resp["agent_id"]), None)
            if agent:
                is_personal = len(target_agents) == 1
                tick_str = f"{Fore.WHITE}[tick {self.tick:>3}]"
                name_str = f"{agent.color}{Style.BRIGHT}{resp['name']}"
                arrow = f"{Fore.MAGENTA}→ Игроку" if is_personal else f"{Fore.MAGENTA}→ Всем"
                text_str = f"{Style.RESET_ALL}{resp['text']}"
                print(f"{tick_str} {name_str} {arrow}: {text_str}")
        print()

    def inject_user_message_api(self, message_text: str, target_agents: list[Agent]) -> list[dict]:
        """Инжектить сообщение пользователя (API режим, возвращает ответы)."""
        return self._inject_user_message_core(message_text, target_agents)

    def _inject_user_message_core(self, message_text: str, target_agents: list[Agent]) -> list[dict]:
        """Ядро обработки сообщения пользователя. Возвращает список ответов агентов."""
        message_text = message_text.strip()
        if not message_text or not target_agents:
            return []

        responses = []

        target_names = [self._registry.get_name(a.agent_id) for a in target_agents]
        is_personal = len(target_agents) == 1
        if is_personal:
            label = f"Сообщение для {target_names[0]}"
        else:
            label = "Сообщение для всех"

        print(f"\n{Fore.MAGENTA}{'=' * 60}")
        print(f"{Fore.MAGENTA}{label}: {message_text}")
        print(f"{Fore.MAGENTA}{'=' * 60}\n")

        msg_entry = {
            "tick": self.tick, "agent_id": "user",
            "name": "Игрок", "text": message_text, "is_event": False,
        }
        self.conversation.append(msg_entry)

        for agent in self.agents:
            is_target = agent in target_agents
            agent.process_message(
                self.tick, "Игрок", message_text,
                is_own=False, is_event=False, is_action_result=False,
                speaker_id="user",
            )
            if is_target:
                agent.memory_system.add_pending_question(self.tick, "Игрок", message_text, from_id="user")

        for agent in target_agents:
            scenario_context = self.scenario_manager.get_scenario_context()
            phase_instruction = self.phase_manager.get_phase_instruction()

            messages = agent.build_messages(
                self.conversation, "normal", scenario_context,
                active_event=self.active_event, all_agents=self.agents,
                phase_instruction=phase_instruction,
                force_event_reaction=False,
            )
            if messages and messages[-1]["role"] == "user":
                agent_display = self._registry.get_name(agent.agent_id)
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
                text = self._clean_response(raw_response, self._registry.get_name(agent.agent_id))

            if not text:
                agent_display = self._registry.get_name(agent.agent_id)
                retry_messages = messages.copy()
                retry_messages.append({"role": "user", "content":
                    f"Ты — {agent_display}. Ответь Игроку на: '{message_text[:80]}'. "
                    f"КОРОТКО, 1-2 предложения. РУССКИЙ. НЕ пиши за других."
                })
                raw_retry = llm_chat(retry_messages, temperature=1.0)
                if raw_retry:
                    text = self._clean_response(raw_retry, self._registry.get_name(agent.agent_id))

            if not text:
                print(f"{Fore.WHITE}  {self._registry.get_name(agent.agent_id)} не смог ответить на сообщение.{Style.RESET_ALL}")
                continue

            for a in self.agents:
                a_display = self._registry.get_name(a.agent_id)
                prefix = f"{a_display}:"
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    break
            text = self._strip_other_agents_speech(text, self._registry.get_name(agent.agent_id))

            if not text or len(text) < 3:
                continue

            quality_ok, quality_reason = self._check_quality(text, agent)
            if not quality_ok:
                print(f"{Fore.RED}  BigBrother отклонил ответ {self._registry.get_name(agent.agent_id)}: {quality_reason}{Style.RESET_ALL}")
                continue

            agent_display = self._registry.get_name(agent.agent_id)
            reply_entry = {
                "tick": self.tick, "agent_id": agent.agent_id,
                "name": agent_display, "text": text,
            }
            self.conversation.append(reply_entry)
            self.topic_manager.record_message(agent_display)

            # Собираем ответ для возврата через API
            responses.append({
                "agent_id": agent.agent_id,
                "name": agent_display,
                "text": text,
                "tick": self.tick,
                "race": agent.race.race_type.value,
                "race_emoji": agent.race.emoji,
                "mood": agent.mood.get_dominant_emotion(),
            })

            for a in self.agents:
                is_own = (a.agent_id == agent.agent_id)
                a.process_message(self.tick, agent_display, text, is_own, speaker_id=agent.agent_id)

            if agent.memory_system.pending_questions:
                agent.memory_system.clear_pending_questions()

            agent.update_talkativeness_spoke()
            agent.memory_system.record_action(text)

        return responses

    def _parse_user_input(self, raw_input: str) -> tuple[str, Optional[list[Agent]]]:
        raw_input = raw_input.strip()
        if not raw_input.startswith('@'):
            return raw_input, None

        parts = raw_input.split(None, 1)
        if len(parts) < 2:
            return raw_input, None

        target_raw = parts[0][1:]
        message_text = parts[1]

        if target_raw.lower() in ('все', 'всем', 'all'):
            return message_text, list(self.agents)

        target_agent = None
        found_id = self._registry.get_id_fuzzy(target_raw)
        if found_id:
            target_agent = next((a for a in self.agents if a.agent_id == found_id), None)

        if target_agent:
            return message_text, [target_agent]

        agent_names = ', '.join(self._registry.get_all_names())
        print(f"{Fore.YELLOW}Агент '{target_raw}' не найден. Доступные: {agent_names}")
        print(f"{Fore.YELLOW}  Ваш ввод будет обработан как событие.{Style.RESET_ALL}")
        return raw_input, None

    def _process_user_events(self):
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
            if event.startswith('__SPEED__'):
                try:
                    new_delay = float(event.replace('__SPEED__', ''))
                    self.tick_delay = new_delay
                    if new_delay == 0:
                        print(f"{Fore.YELLOW}Симуляция на паузе. Введите 'speed X' чтобы продолжить.{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.GREEN}Задержка между ходами: {new_delay:.2f} сек{Style.RESET_ALL}")
                except ValueError:
                    pass
                continue
            if event.startswith('__ADD_AGENT__'):
                raw_cmd = event.replace('__ADD_AGENT__', '')
                self._handle_add_agent(raw_cmd)
                continue
            if event.startswith('__REMOVE_AGENT__'):
                raw_cmd = event.replace('__REMOVE_AGENT__', '')
                self._handle_remove_agent(raw_cmd)
                continue
            if event == '__LIST_AGENTS__':
                self._list_agents()
                continue
            text, target_agents = self._parse_user_input(event)
            if target_agents:
                self.inject_user_message(text, target_agents)
            else:
                self.inject_user_event(text)

    def _strip_other_agents_speech(self, text: str, speaker_name: str) -> str:
        agent_names = [n for n in self._registry.get_all_names() if n != speaker_name]
        if not agent_names:
            return text
        pattern = r'(?:\n|\. |\! |\? |^)\s*(?:' + '|'.join(re.escape(n) for n in agent_names) + r')\s*[:\-]'
        match = re.search(pattern, text)
        if match:
            cut_pos = match.start()
            if cut_pos > 10:
                text = text[:cut_pos].strip()
        for name in agent_names:
            simple_pattern = f'{name}:'
            idx = text.find(simple_pattern)
            if idx > 15:
                text = text[:idx].strip()
                break
        return text

    def _clean_response(self, text: str, speaker_name: str = "") -> str:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<think>.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'</?think>', '', text, flags=re.IGNORECASE)

        # Удаляем системные теги, которые LLM скопировал из контекста
        text = re.sub(r'\[СОБЫТИЕ\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[РЕЗУЛЬТАТ\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[Мир\]\s*:', '', text, flags=re.IGNORECASE)
        # Обрезанные теги (ТИЕ], ЫТИЕ], etc.)
        text = re.sub(r'\b[А-ЯЁа-яё]{0,6}ТИЕ\]\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[?СВОДКА\]\s*', '', text, flags=re.IGNORECASE)
        # Любые квадратные скобки с эмодзи-событиями
        text = re.sub(r'\[[^\]]{0,5}[🔥🌧⚠📡🦀🌊🐍⛵🌅💨📦🔫📻💊🔦🚁🗝🌙⚡🍱🔧📊🌠💤🍺⚔🎲🎵🗺🔮🍖👤🧟🎬][^\]]{0,60}\]', '', text)
        # Удаляем театральные ремарки: (делает что-то)
        text = re.sub(r'\([^)]{5,80}\)', '', text)
        # Одинокие ] или : в начале после удаления тегов
        text = re.sub(r'^\s*[\]:\-]+\s*', '', text)
        # Убираем обращения к Ведущему/системе
        text = re.sub(r'(?:^|\s)Ведущий[,:]?\s*', ' ', text, flags=re.IGNORECASE).strip()
        # Убираем префикс "ИмяСпикера:" если LLM начал с него
        if speaker_name:
            sp_prefix = f"{speaker_name}:"
            if text.startswith(sp_prefix):
                text = text[len(sp_prefix):].strip()

        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        if len(text) < 5:
            return ""

        # Исправляем обрезанные начала реплик
        # Если начинается с маленькой буквы или обрезанного слова — убираем до первого нормального предложения
        if text and text[0].islower():
            # Ищем начало нового предложения (заглавная буква после пробела)
            match = re.search(r'[.!?…]\s+([А-ЯЁA-Z])', text)
            if match:
                text = text[match.start(1):]
            else:
                # Нет полного предложения — пробуем убрать мусор до первой заглавной
                match2 = re.search(r'(?:^|[,\s]\s*)([А-ЯЁ][а-яё])', text)
                if match2 and match2.start(1) < 30:
                    text = text[match2.start(1):]
                # Иначе оставляем как есть (может быть валидное начало)

        if not text or len(text) < 5:
            return ""

        # Убираем префикс спикера (может появиться после обрезки начала)
        if speaker_name:
            sp_prefix = f"{speaker_name}:"
            if text.startswith(sp_prefix):
                text = text[len(sp_prefix):].strip()

        if speaker_name:
            text = self._strip_other_agents_speech(text, speaker_name)
        if len(text) > MAX_RESPONSE_CHARS:
            cut_text = text[:MAX_RESPONSE_CHARS]
            last_p = max(cut_text.rfind('.'), cut_text.rfind('!'), cut_text.rfind('?'))
            if last_p > MAX_RESPONSE_CHARS * 0.3:
                text = cut_text[:last_p + 1].strip()
            else:
                last_space = cut_text.rfind(' ')
                if last_space > MAX_RESPONSE_CHARS * 0.3:
                    text = cut_text[:last_space].strip() + '...'
                else:
                    text = cut_text.strip() + '...'
        if text and text[-1] not in '.!?…"\'…':
            last_punctuation = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
            if last_punctuation > len(text) * 0.3:
                text = text[:last_punctuation + 1].strip()
            else:
                last_space = text.rfind(' ')
                if last_space > len(text) * 0.5:
                    text = text[:last_space].strip() + '...'
        return text

    def _check_quality(self, text: str, speaker: Agent) -> tuple[bool, str]:
        text_lower = text.lower()
        speaker_display = self._registry.get_name(speaker.agent_id)

        # Безусловно опасные — блокируем всегда
        dangerous_always = [
            'разрезаю', 'ампутир', 'отрежу', 'режу себ', 'пущу кровь',
            'сломаю себе', 'выколю', 'ритуал с кровью',
            'жертвоприношен', 'убью себя', 'повешу', 'утоплюсь',
        ]
        for pattern in dangerous_always:
            if pattern in text_lower:
                self._log_warning(f"опасное действие: '{pattern}' от {speaker_display}")
                return False, f"опасное действие: '{pattern}'"
        # Контекстно-зависимые — 'проклят' опасно только рядом с ритуалами/кровью
        if 'проклят' in text_lower:
            danger_context = ['ритуал', 'кров', 'жертв', 'себя', 'прокляну', 'наложу']
            if any(dc in text_lower for dc in danger_context):
                self._log_warning(f"опасный контекст: 'проклят' + контекст от {speaker_display}")
                return False, "опасное действие: 'проклят' в опасном контексте"

        other_names = [n for n in self._registry.get_all_names() if n != speaker_display]
        for name in other_names:
            if f"{name}:" in text:
                self._log_warning(f"{speaker_display} пишет за {name}")
                return False, f"пишешь за {name} — говори только от себя"

        # Bug fix: самообращение — агент обращается к себе по имени
        if self._has_self_reference(speaker_display, text):
            self._log_warning(f"{speaker_display} обращается к себе")
            return False, f"не обращайся к себе по имени — ты {speaker_display}"

        # Bug fix: обращение к Ведущему/системе — ломает четвёртую стену
        fourth_wall_patterns = [
            r'\bведущ', r'\bведущий\b', r'\bгейм.?мастер', r'\bсистем[аеу]\b',
            r'\bавтор\b', r'\bсоздател', r'\bигрок\b',
        ]
        for pattern in fourth_wall_patterns:
            if re.search(pattern, text_lower):
                self._log_warning(f"{speaker_display} обращается к Ведущему/системе")
                return False, "не обращайся к Ведущему — говори с другими персонажами"

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

        # Bug fix: метаописание действий ("Я обращаюсь к...", "Я поворачиваюсь к...")
        meta_action_patterns = [
            r'я обращаюсь к\s',
            r'я поворачиваюсь к\s',
            r'я оборачиваюсь к\s',
            r'я подхожу к\s',
            r'я беру\s',
            r'я встаю\s',
            r'я сажусь\s',
            r'я ложусь\s',
            r'я наклоняюсь\s',
            r'я протягиваю\s',
            r'я смотрю на\s',
            r'я киваю\s',
            r'я качаю голов',
            r'я вздыхаю\s',
            r'я хмурюсь\s',
        ]
        for pattern in meta_action_patterns:
            if re.search(pattern, text_lower):
                self._log_warning(f"{speaker_display} описывает физическое действие: '{pattern}'")
                return False, "не описывай физические действия — говори словами"

        # Системные теги — LLM скопировал контекст
        system_tag_patterns = [
            'событие]', 'результат]', 'сводка]', 'тие]',
            '[мир]', 'важные события из прошлого',
            'твоё текущее настроение', 'правила настроения',
            'как общаться', 'запрещено', 'критически важно',
        ]
        for pattern in system_tag_patterns:
            if pattern in text_lower:
                self._log_warning(f"{speaker_display} скопировал системный тег: '{pattern}'")
                return False, f"не копируй системные теги — говори от себя"

        return True, ""

    @staticmethod
    def _has_self_reference(agent_name: str, text: str) -> bool:
        """Проверяет, обращается ли агент к себе по имени."""
        patterns = [
            rf'\b{re.escape(agent_name)},\s',           # "Вика, ты..."
            rf'^{re.escape(agent_name)}[,:\s]',          # В начале строки
            rf'говорит\s+{re.escape(agent_name)}',       # "говорит Вика"
            rf'обращаюсь к {re.escape(agent_name)}',      # "Я обращаюсь к Вике" (метаописание)
            rf'— {re.escape(agent_name)}',                # "— Вика сказала"
        ]
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _log_warning(self, reason: str):
        self.quality_warnings += 1
        self.last_warning_reason = reason
        if self.quality_warnings <= 10 or self.quality_warnings % 5 == 0:
            print(f"{Fore.RED}  Предупреждение #{self.quality_warnings}: {reason}{Style.RESET_ALL}")

    def _analyze_interaction_sentiment(self, speaker_id: str, text: str, all_agents: list) -> dict:
        sentiment = {}
        text_lower = text.lower()

        speaker_agent = next((a for a in all_agents if a.agent_id == speaker_id), None)

        for agent in all_agents:
            if agent.agent_id == speaker_id:
                continue
            agent_display = self._registry.get_name(agent.agent_id)
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
            bravery_patterns = [
                'храбр', 'смел', 'пойду перв', 'не боюсь', 'рискну',
                'не страшно', 'бесстраш', 'отважн', 'герой', 'сражаться',
            ]
            sharing_patterns = [
                'делим', 'поровну', 'раздел', 'припасы', 'ресурсы',
                'запасы', 'поделить', 'раздать', 'разделить',
            ]

            # Контекстный анализ: слово должно быть РЯДОМ с именем target'а
            # Ищем предложение, содержащее имя упомянутого агента
            name_lower = agent_display.lower()
            sentences = re.split(r'[.!?…]+', text_lower)
            name_sentence = ""
            for s in sentences:
                if name_lower in s:
                    name_sentence = s
                    break
            # Если имя в конкретном предложении — анализируем только это предложение
            # Это предотвращает инверсию: "Я готова поддержать тебя" не даёт позитив ОТ target'а
            context_text = name_sentence if name_sentence else text_lower

            delta = 0.0
            reason = ""
            for p in positive_patterns:
                if p in context_text:
                    delta += RELATIONSHIP_CHANGE_RATE
                    reason = f"позитив: '{p}'"
                    break
            for p in negative_patterns:
                if p in context_text:
                    delta -= RELATIONSHIP_CHANGE_RATE
                    reason = f"негатив: '{p}'"
                    break
            # Нейтральное упоминание — НЕ меняет отношения (предотвращает дрифт)
            if delta == 0.0:
                continue  # пропускаем — нет явного позитива/негатива

            if agent.race.race_type == RaceType.ORC:
                if any(p in text_lower for p in bravery_patterns):
                    delta += 0.15
                    reason += " + 💪храбрость (орк восхищён)"

            if speaker_agent and speaker_agent.race.race_type == RaceType.DWARF:
                if any(p in text_lower for p in sharing_patterns):
                    speaker_agent.mood.anger = min(1.0, speaker_agent.mood.anger + 0.10)
                    delta -= 0.05
                    reason += " + жадность (дварф злится при дележе)"

            if speaker_agent and speaker_agent.race.race_type == RaceType.GOBLIN:
                if any(p in text_lower for p in sharing_patterns):
                    delta -= 0.10
                    reason += " + жадность (гоблин хочет больше)"

            if delta != 0:
                sentiment[agent.agent_id] = (delta, reason)
        return sentiment

    def select_speaker(self) -> Agent:
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

    def _select_speaker_v3(self) -> Agent:
        agents_with_questions = [a for a in self.agents if a.memory_system.pending_questions]
        if agents_with_questions:
            return random.choice(agents_with_questions)

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
            if a.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT:
                w *= 0.5
            weights.append(w)

        total = sum(weights)
        if total == 0:
            return random.choice(self.agents)
        return random.choices(self.agents, weights=weights, k=1)[0]

    def _check_racial_abilities(self, agent: Agent) -> Optional[str]:
        race = agent.race
        mods = race.modifiers
        agent_display = self._registry.get_name(agent.agent_id)

        if race.race_type == RaceType.GOBLIN and agent.mood.fear > mods.flee_threshold:
            if random.random() < 0.4:
                flee_text = f"!!! {race.emoji} {agent_display} ПЫТАЕТСЯ СБЕЖАТЬ! (страх: {agent.mood.fear:.2f} > порог: {mods.flee_threshold})"

                if mods.can_betray and agent.mood.fear > 0.7 and random.random() < 0.3:
                    betray_text = (
                        f"\n!!! {race.emoji} {agent_display} ПРЕДАЛ ГРУППУ! "
                        f"Незаметно выскользнул, прихватив часть припасов!"
                    )
                    for other in self.agents:
                        if other.agent_id != agent.agent_id:
                            other.update_relationship(agent.agent_id, -0.50, "ПРЕДАТЕЛЬСТВО гоблина!")
                            other.mood.anger = min(1.0, other.mood.anger + 0.3)

                    betray_entry = {
                        "tick": self.tick, "agent_id": "race_event",
                        "name": "Расовое событие", "text": f"{agent_display} предал группу и сбежал с припасами!",
                        "is_event": True,
                    }
                    self.conversation.append(betray_entry)
                    for a in self.agents:
                        a.process_message(self.tick, "Расовое событие",
                                          f"{agent_display} предал группу!",
                                          is_own=False, is_event=True)

                    return f"{Fore.RED}{flee_text}{betray_text}{Style.RESET_ALL}"

                return f"{Fore.YELLOW}{flee_text}{Style.RESET_ALL}"

        if race.race_type == RaceType.ELF and self.active_event:
            event_lower = self.active_event.lower()
            danger_keywords = ['зомби', 'опасн', 'хищник', 'змея', 'бандит', 'враг']
            if any(kw in event_lower for kw in danger_keywords):
                if random.random() < mods.detection_bonus:
                    return f"{Fore.GREEN}  {race.emoji} {agent_display} чувствует опасность раньше других! (+обнаружение){Style.RESET_ALL}"

        if race.race_type == RaceType.DWARF:
            repair_keywords = ['чин', 'ремонт', 'почин', 'постро', 'мастер', 'кова', 'куз']
            text_lower = agent.memory_system.completed_actions[-1].lower() if agent.memory_system.completed_actions else ""
            if any(kw in text_lower for kw in repair_keywords):
                if random.random() < 0.5:
                    return f"{Fore.GREEN}  {race.emoji} {agent_display} применяет мастерство дварфов! (+{mods.repair_bonus*100:.0f}% к ремонту){Style.RESET_ALL}"

        if race.race_type == RaceType.ORC and self.active_event:
            event_lower = self.active_event.lower()
            combat_keywords = ['зомби', 'бандит', 'драк', 'бой', 'сражен', 'атак', 'напад']
            if any(kw in event_lower for kw in combat_keywords):
                if random.random() < 0.3:
                    agent.mood.energy = min(1.0, agent.mood.energy + 0.15)
                    agent.mood.fear = max(0.0, agent.mood.fear - 0.1)
                    return f"{Fore.GREEN}  {race.emoji} {agent_display} воодушевлён боем! (+боевой дух, -страх){Style.RESET_ALL}"

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

    def _check_consecutive_similarity(self, speaker: Agent, new_text: str):
        new_phrases = extract_phrases(new_text)
        if speaker.last_response_phrases:
            overlap = len(new_phrases & speaker.last_response_phrases) / max(len(new_phrases), 1)
            if overlap > 0.3 or has_banned_pattern(new_text):
                speaker.consecutive_similar_count += 1
            else:
                speaker.consecutive_similar_count = 0
        speaker.last_response_phrases = new_phrases

    def run_tick(self) -> Optional[dict]:
        self.tick += 1

        self._process_user_events()
        if self._quit_requested:
            return None

        if self.active_event and (self.tick - self.event_started_tick) > EVENT_FOCUS_DURATION:
            print(f"{Fore.MAGENTA}  📋 Фокус на событии завершён{Style.RESET_ALL}")
            self.active_event = None
            self.event_reacted_agents = set()
            for agent in self.agents:
                agent.active_event = None
                agent.reacted_to_event = False

        phase_changed, phase_label = self.phase_manager.advance_tick()
        if phase_changed and phase_label:
            print(f"{Fore.CYAN}  {phase_label}{Style.RESET_ALL}")

        if self.phase_manager.is_topic_complete() and not self.active_event:
            scenario_context = self.scenario_manager.get_scenario_context()
            new_topic = self.topic_manager.get_new_topic(scenario_context)
            self.phase_manager.start_new_topic(self.tick)
            print(f"{Fore.CYAN}Тема завершена! Новая тема: {new_topic[:80]}{Style.RESET_ALL}")
            topic_entry = {
                "tick": self.tick, "agent_id": "system",
                "name": "Ведущий", "text": f"Новая тема: {new_topic}",
                "is_new_topic": True,
            }
            self.conversation.append(topic_entry)
            for agent in self.agents:
                agent.process_message(self.tick, "Ведущий", f"Новая тема: {new_topic}", is_own=False)

        if self.tick % SCENARIO_EVENT_INTERVAL == 0:
            event = self.scenario_manager.trigger_random_event()
            if event:
                print(f"\n{Fore.MAGENTA}{'=' * 60}")
                print(f"{Fore.MAGENTA}СОБЫТИЕ: {event}")
                print(f"{Fore.MAGENTA}{'=' * 60}\n")

                self.active_event = event
                self.event_started_tick = self.tick
                self.event_reacted_agents = set()

                event_entry = {
                    "tick": self.tick, "agent_id": "event",
                    "name": "Событие", "text": event, "is_event": True,
                }
                self.conversation.append(event_entry)

                for agent in self.agents:
                    agent.process_message(self.tick, "Событие", event, is_own=False, is_event=True)
                    agent.update_observations(self.tick, "Событие", event, event)
                    agent.active_event = event
                    agent.event_focus_tick = self.tick
                    agent.reacted_to_event = False
                    agent.mood.apply_event(event, agent.personality_type, agent.big_five, agent.race.modifiers)

                for agent in self.agents:
                    agent_display = self._registry.get_name(agent.agent_id)
                    dominant = agent.mood.get_dominant_emotion()
                    emoji = agent.mood.get_emoji()
                    print(f"{Fore.YELLOW}  {agent_display}: {dominant} "
                          f"(Счаст:{agent.mood.happiness:+.2f} Злость:{agent.mood.anger:.2f} Страх:{agent.mood.fear:.2f}){Style.RESET_ALL}")

                scenario_ctx = self.scenario_manager.get_scenario_context()
                consequence = self._generate_event_consequence(event, scenario_ctx)
                if consequence:
                    print(f"{Fore.YELLOW}Последствие: {consequence}{Style.RESET_ALL}")
                    consequence_entry = {
                        "tick": self.tick, "agent_id": "world",
                        "name": "Мир", "text": consequence, "is_event": True,
                    }
                    self.conversation.append(consequence_entry)
                    for agent in self.agents:
                        agent.process_message(self.tick, "Мир", consequence, is_own=False, is_action_result=True)

        speaker = self._select_speaker_v3()

        force_event_reaction = False
        if (self.active_event
                and speaker.agent_id not in self.event_reacted_agents
                and (self.tick - self.event_started_tick) <= EVENT_FORCED_REACTION_TICKS):
            force_event_reaction = True

        mode = "normal"
        if not self.active_event and self.topic_manager.should_change_topic(len(self.agents)):
            if random.random() < CREATIVITY_BOOST:
                mode = "new_topic"
                print(f"{Fore.CYAN}{self._registry.get_name(speaker.agent_id)} предлагает новую тему...{Style.RESET_ALL}")

        scenario_context = self.scenario_manager.get_scenario_context()

        current_event = None
        for entry in reversed(self.conversation[-5:]):
            if entry.get("is_event", False):
                current_event = entry["text"]
                break

        old_plan_goal = speaker.current_plan.goal if speaker.current_plan else None
        # Пересоздаём план если: нет плана / новое событие / план полностью завершён
        plan_complete = (
            speaker.current_plan
            and speaker.current_plan.steps
            and speaker.current_plan.current_step >= len(speaker.current_plan.steps) - 1
        )
        new_event_for_plan = (
            current_event
            and speaker.current_plan
            and current_event.lower()[:30] not in speaker.current_plan.goal.lower()
        )
        if not speaker.current_plan or new_event_for_plan or plan_complete:
            speaker.create_or_update_plan(self.conversation, scenario_context)
        if speaker.current_plan and speaker.current_plan.goal != old_plan_goal:
            step = speaker.current_plan.steps[0] if speaker.current_plan.steps else 'нет'
            print(f"{Fore.CYAN}{self._registry.get_name(speaker.agent_id)} -> {speaker.current_plan.goal} | {step}{Style.RESET_ALL}")

        phase_instruction = self.phase_manager.get_phase_instruction()

        messages = speaker.build_messages(
            self.conversation, mode, scenario_context,
            active_event=self.active_event, all_agents=self.agents,
            phase_instruction=phase_instruction,
            force_event_reaction=force_event_reaction,
        )
        raw_response = llm_chat(messages)
        text = None

        if raw_response is not None:
            text = self._clean_response(raw_response, self._registry.get_name(speaker.agent_id))

        if not text:
            retry_messages = speaker.build_messages(
                self.conversation, mode, scenario_context,
                active_event=self.active_event, all_agents=self.agents,
                phase_instruction=phase_instruction,
                force_event_reaction=force_event_reaction,
            )
            retry_messages.append({"role": "user", "content":
                f"Ты — {self._registry.get_name(speaker.agent_id)}. Ответь КОРОТКО, 1-2 предложения. БЕЗ тегов. Русский текст. НЕ пиши за других."
            })
            raw_retry = llm_chat(retry_messages, temperature=1.0)
            if raw_retry:
                text = self._clean_response(raw_retry, self._registry.get_name(speaker.agent_id))

        if not text:
            print(f"{Fore.WHITE}  [tick {self.tick:>3}] {self._registry.get_name(speaker.agent_id)} промолчал (LLM не дал ответ){Style.RESET_ALL}")
            for a in self.agents:
                a.update_talkativeness_silent()
            return None

        speaker_display = self._registry.get_name(speaker.agent_id)
        for a in self.agents:
            a_display = self._registry.get_name(a.agent_id)
            prefix = f"{a_display}:"
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        text = self._strip_other_agents_speech(text, speaker_display)
        if not text or len(text) < 5:
            print(f"{Fore.WHITE}  Тик {self.tick}: {speaker_display} промолчал (текст пуст после очистки){Style.RESET_ALL}")
            for a in self.agents:
                a.update_talkativeness_silent()
            return None

        quality_ok, quality_reason = self._check_quality(text, speaker)
        if not quality_ok:
            print(f"{Fore.RED}  BigBrother отклонил: {quality_reason}{Style.RESET_ALL}")
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
                    a_display = self._registry.get_name(a.agent_id)
                    if text and text.startswith(f"{a_display}:"):
                        text = text[len(f"{a_display}:"):].strip()
                        break
                text = self._strip_other_agents_speech(text, speaker_display)
            if not text:
                for a in self.agents:
                    a.update_talkativeness_silent()
                return None

        recent_texts = [e['text'] for e in self.conversation[-40:]
                        if not e.get('is_event', False) and e.get('text')]
        own_recent = [e['text'] for e in self.conversation[-80:]
                      if e.get('agent_id') == speaker.agent_id and not e.get('is_event', False)]

        is_repetitive = False
        if has_banned_pattern(text):
            is_repetitive = True

        # Проверка ТОЧНОГО совпадения по всей истории агента (ключевая проверка!)
        if not is_repetitive:
            text_stripped = text.strip().lower()
            for old_msg in own_recent:
                if old_msg.strip().lower() == text_stripped:
                    is_repetitive = True
                    break

        # Проверка точного совпадения с последним сообщением любого агента
        if not is_repetitive and self.conversation and not self.conversation[-1].get('is_event', False):
            if self.conversation[-1].get('text') == text:
                is_repetitive = True

        # Проверка высокой похожести с ЛЮБЫМ сообщением в расширенном окне
        if not is_repetitive:
            for prev_text in recent_texts[-30:]:
                if text_similarity(text, prev_text) > REPETITION_SIMILARITY_THRESHOLD:
                    is_repetitive = True
                    break

        # Для собственных сообщений — более строгий порог (0.42 вместо 0.5)
        if not is_repetitive and own_recent:
            for old_msg in own_recent:
                if text_similarity(text, old_msg) > 0.42:
                    is_repetitive = True
                    break

        # Проверка одинаковых начал реплик
        if not is_repetitive and own_recent:
            first_words = ' '.join(text.lower().split()[:5])
            for old_msg in own_recent[-20:]:
                old_first_words = ' '.join(old_msg.lower().split()[:5])
                if first_words == old_first_words and len(first_words) > 10:
                    is_repetitive = True
                    break
        if not is_repetitive:
            is_repetitive = has_repetitive_pattern(text, own_recent)
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
                    a_display = self._registry.get_name(a.agent_id)
                    if text_retry and text_retry.startswith(f"{a_display}:"):
                        text_retry = text_retry[len(f"{a_display}:"):].strip()
                        break
                text_retry = self._strip_other_agents_speech(text_retry, speaker_display)
                if text_retry and text_similarity(text_retry, text) < 0.4:
                    text = text_retry
                else:
                    for a in self.agents:
                        a.update_talkativeness_silent()
                    return None
            else:
                for a in self.agents:
                    a.update_talkativeness_silent()
                return None

        self._check_consecutive_similarity(speaker, text)

        if self.active_event and speaker.agent_id not in self.event_reacted_agents:
            self.event_reacted_agents.add(speaker.agent_id)
            speaker.reacted_to_event = True

        speaker.memory_system.record_action(text)

        race_event = self._check_racial_abilities(speaker)
        if race_event:
            print(f"{race_event}")

        self.phase_manager.record_decision(text)
        self.phase_manager.record_action(text)

        # Записываем ключевые решения и предложения в память всех агентов
        decision_keywords = [
            'давайте', 'предлагаю', 'решено', 'план:', 'будем',
            'нужно', 'разожжём', 'построим', 'пойдём', 'сделаем',
            'распределим', 'назначим', 'соберём', 'костёр', 'сигнал',
            'укрытие', 'лагерь', 'дежурство', 'вахта',
        ]
        text_lower = text.lower()
        if any(kw in text_lower for kw in decision_keywords):
            for agent in self.agents:
                agent.memory_system.add_group_decision(
                    self.tick, speaker_display, text[:150], proposer_id=speaker.agent_id
                )

        action_result = self._generate_action_result(speaker_display, text, scenario_context)

        if mode == "new_topic":
            self.topic_manager.current_topic = text
            self.topic_manager.messages_on_topic = 0
            self.topic_manager.topic_respondents = set()
            self.phase_manager.start_new_topic(self.tick)
            self.topic_manager.save_to_db()

        self.last_visible_tick = self.tick

        # Определяем, является ли реплика инициативой
        is_initiative = False
        if mode == "new_topic":
            is_initiative = True
        elif force_event_reaction:
            # Первый реагирующий на событие — инициатор обсуждения
            is_initiative = True
        elif not speaker.memory_system.pending_questions:
            # Агент говорит без вопроса к нему — проверяем, предлагает ли он действие/тему
            initiative_words = ['предлагаю', 'давайте', 'нужно', 'а что если', 'может стоит',
                                'пойдём', 'надо', 'план:', 'идея:', 'слушайте']
            if any(w in text.lower() for w in initiative_words):
                is_initiative = True

        entry = {
            "tick": self.tick, "agent_id": speaker.agent_id,
            "name": speaker_display, "text": text,
            "is_new_topic": mode == "new_topic",
            "is_initiative": is_initiative,
        }
        self.conversation.append(entry)
        self.topic_manager.record_message(speaker_display)

        if speaker.memory_system.pending_questions:
            speaker.memory_system.clear_pending_questions()

        for agent in self.agents:
            if agent.agent_id != speaker.agent_id:
                agent_display = self._registry.get_name(agent.agent_id)
                if agent_display.lower() in text.lower() and "?" in text:
                    agent.memory_system.add_pending_question(self.tick, speaker_display, text, from_id=speaker.agent_id)

        if action_result:
            print(f"{Fore.YELLOW}Результат: {action_result}{Style.RESET_ALL}")
            result_entry = {
                "tick": self.tick, "agent_id": "action_result",
                "name": "Результат", "text": f"{speaker_display}: {action_result}",
                "is_event": True,
            }
            self.conversation.append(result_entry)
            for a in self.agents:
                a.process_message(self.tick, speaker_display, action_result,
                                  is_own=(a.agent_id == speaker.agent_id),
                                  is_action_result=True, speaker_id=speaker.agent_id)
                a.update_observations(self.tick, speaker_display, action_result, action_result)

        sentiments = self._analyze_interaction_sentiment(speaker.agent_id, text, self.agents)
        for target_id, (delta, reason) in sentiments.items():
            speaker.update_relationship(target_id, delta, reason)
            speaker.mood.apply_interaction(delta, speaker.personality_type, speaker.big_five)
            target_agent = next((a for a in self.agents if a.agent_id == target_id), None)
            if target_agent:
                reciprocal = delta * 0.5
                target_agent.update_relationship(speaker.agent_id, reciprocal,
                    f"{'позитив' if delta > 0 else 'негатив'} от {speaker_display}")
                target_agent.mood.apply_interaction(reciprocal, target_agent.personality_type, target_agent.big_five)

        for a in self.agents:
            is_own = (a.agent_id == speaker.agent_id)
            a.process_message(self.tick, speaker_display, text, is_own, speaker_id=speaker.agent_id)
            a.update_observations(self.tick, speaker_display, text, current_event)

        if speaker.current_plan and speaker.current_plan.steps:
            # Продвигаем шаг только если реплика реально связана с текущим шагом
            current_step_text = speaker.current_plan.steps[speaker.current_plan.current_step].lower()
            step_keywords = current_step_text.split()
            text_lower_plan = text.lower()
            # Проверяем: хотя бы одно ключевое слово шага есть в реплике (кроме служебных)
            step_match = any(
                kw in text_lower_plan
                for kw in step_keywords
                if len(kw) > 3  # игнорируем предлоги и короткие слова
            )
            if step_match or speaker.current_plan.current_step == 0:
                speaker.current_plan.current_step = min(
                    speaker.current_plan.current_step + 1,
                    len(speaker.current_plan.steps) - 1
                )

        for target_id, (delta, reason) in sentiments.items():
            if abs(delta) >= 0.03:
                emoji = "+" if delta > 0 else "-"
                target_display = self._registry.get_name(target_id)
                print(f"{Fore.MAGENTA}  {emoji} {speaker_display} -> {target_display}: {delta:+.2f} ({reason}){Style.RESET_ALL}")

        # Отправка в Audit Service (после всех обновлений состояния)
        audit_event_type = "message_sent"
        if mode == "new_topic":
            audit_event_type = "new_topic"
        elif force_event_reaction:
            audit_event_type = "event_reaction"
        other_agents = [a for a in self.agents if a.agent_id != speaker.agent_id]
        send_audit_event(
            event_type=audit_event_type,
            source_agent=speaker,
            target_agents=other_agents,
            message=text,
            tick=self.tick,
            scenario_name=self.scenario_manager.current_scenario.name,
            scenario_description=self.scenario_manager.current_scenario.description,
            active_event=self.active_event,
            current_topic=self.topic_manager.current_topic,
            current_phase=self.phase_manager.current_phase,
            phase_label=self.phase_manager.phase_label,
            is_initiative=is_initiative,
            is_new_topic=(mode == "new_topic"),
            action_result=action_result,
            sentiments=sentiments,
        )

        for a in self.agents:
            if a.agent_id == speaker.agent_id:
                a.update_talkativeness_spoke()
                a.mood.apply_speaking(a.big_five)
            else:
                a.update_talkativeness_silent()
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
            name_str = f"{agent.color}{Style.BRIGHT}[NEW] {agent.race.emoji} {entry['name']}"
        else:
            name_str = f"{agent.color}{Style.BRIGHT}{agent.race.emoji} {entry['name']}"
        text_str = f"{Style.RESET_ALL}{entry['text']}"
        print(f"{tick_str} {name_str}: {text_str}")

    def print_stats(self):
        print(f"\n{Fore.MAGENTA}{'=' * 60}")
        print(f"{Fore.MAGENTA}Статистика:")
        for a in self.agents:
            display = self._registry.get_name(a.agent_id)
            race = a.race
            bar_len = int(a.talkativeness * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {a.color}{race.emoji} {display:<8}{Style.RESET_ALL} [{race.name_ru}] [{bar}] {a.talkativeness:.2f}")

        print(f"\n{Fore.YELLOW}Настроение:")
        for a in self.agents:
            display = self._registry.get_name(a.agent_id)
            race = a.race
            m = a.mood
            emoji = m.get_emoji()
            dominant = m.get_dominant_emotion()
            h_bar = self._mood_bar(m.happiness, signed=True)
            e_bar = self._mood_bar(m.energy)
            s_bar = self._mood_bar(m.stress)
            a_bar = self._mood_bar(m.anger)
            f_bar = self._mood_bar(m.fear)
            print(f"  {a.color}{race.emoji} {display}{Style.RESET_ALL} {dominant}")
            print(f"    Счастье: {h_bar} {m.happiness:+.2f}")
            print(f"    Энергия: {e_bar} {m.energy:.2f}")
            print(f"    Стресс:  {s_bar} {m.stress:.2f}")
            print(f"    Злость:  {a_bar} {m.anger:.2f}")
            print(f"    Страх:   {f_bar} {m.fear:.2f}")
            mods = race.modifiers
            race_info = []
            if mods.repair_bonus > 0:
                race_info.append(f"Ремонт+{mods.repair_bonus*100:.0f}%")
            if mods.combat_bonus > 0:
                race_info.append(f"Бой+{mods.combat_bonus*100:.0f}%")
            if mods.diplomacy_bonus > 0:
                race_info.append(f"Дипломатия+{mods.diplomacy_bonus*100:.0f}%")
            if mods.detection_bonus > 0:
                race_info.append(f"Обнаружение+{mods.detection_bonus*100:.0f}%")
            if mods.can_betray:
                betray_status = "ОПАСНО!" if m.fear > 0.5 else "ok"
                race_info.append(f"Предательство:{betray_status}")
            if mods.stubborn:
                race_info.append("упрямый")
            if race_info:
                print(f"    {Fore.YELLOW}Раса: {' | '.join(race_info)}{Style.RESET_ALL}")

        print(f"\n{Fore.RED}Отношения:")
        for a in self.agents:
            a_display = self._registry.get_name(a.agent_id)
            a_race = a.race
            for other_id, val in a.relationships.items():
                other_agent = next((ag for ag in self.agents if ag.agent_id == other_id), None)
                other_display = self._registry.get_name(other_id)
                other_emoji = other_agent.race.emoji if other_agent else ""
                if val > 0.3:
                    emoji = "+"
                elif val > 0:
                    emoji = "~"
                elif val > -0.3:
                    emoji = "="
                else:
                    emoji = "-"
                bar_len = int((val + 1) * 10)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                print(f"  {a.color}{a_race.emoji}{a_display}{Style.RESET_ALL} → {other_emoji}{other_display}: [{bar}] {val:+.2f} {emoji}")

        print(f"\n{Fore.WHITE}Активность (реплики / инициатив / реакции):")
        for a in self.agents:
            a_display = self._registry.get_name(a.agent_id)
            total_msgs = sum(1 for e in self.conversation if e.get('agent_id') == a.agent_id and not e.get('is_event'))
            initiatives = sum(1 for e in self.conversation if e.get('agent_id') == a.agent_id and e.get('is_initiative'))
            reactions = total_msgs - initiatives
            print(f"  {a.color}{a_display}:{Style.RESET_ALL} {total_msgs} реплик, {initiatives} инициатив, {reactions} реакций")

        print(f"\n{Fore.GREEN}Планы:")
        for a in self.agents:
            a_display = self._registry.get_name(a.agent_id)
            if a.current_plan:
                step_info = f"{a.current_plan.current_step + 1}/{len(a.current_plan.steps)}"
                current_step = a.current_plan.steps[a.current_plan.current_step] if a.current_plan.steps else "нет"
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} {a.current_plan.goal}")
                print(f"    └─ Шаг {step_info}: {current_step[:50]}")
            else:
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} нет плана")

        print(f"\n{Fore.YELLOW}Сценарий: {self.scenario_manager.current_scenario.name}")
        if self.active_event:
            remaining = EVENT_FOCUS_DURATION - (self.tick - self.event_started_tick)
            print(f"{Fore.YELLOW}   Активное событие (еще {remaining} тиков): {self.active_event[:60]}")
        warn_text = f"{Fore.RED}   Предупреждения: {self.quality_warnings}"
        if self.last_warning_reason:
            warn_text += f" (последнее: {self.last_warning_reason[:60]})"
        print(warn_text)

        if self.topic_manager.current_topic:
            clean_topic = re.sub(r'<think>.*?</think>', '', self.topic_manager.current_topic, flags=re.DOTALL | re.IGNORECASE)
            clean_topic = re.sub(r'<think>.*', '', clean_topic, flags=re.DOTALL | re.IGNORECASE)
            clean_topic = re.sub(r'</?think>', '', clean_topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'\s+', ' ', clean_topic).strip()
            if len(clean_topic) > 100:
                clean_topic = clean_topic[:97] + "..."
            if len(clean_topic) < 5:
                clean_topic = "[тема генерируется...]"
            respondents = ", ".join(self.topic_manager.topic_respondents) if self.topic_manager.topic_respondents else "никто"
            print(f"\n{Fore.CYAN}Тема: {clean_topic}")
            print(f"{Fore.CYAN}   Сообщений: {self.topic_manager.messages_on_topic} | Ответили: {respondents}")
            phase = self.phase_manager.phase_label
            ticks_left = PHASE_TICKS.get(self.phase_manager.current_phase, 0) - self.phase_manager.ticks_in_phase
            print(f"{Fore.CYAN}   Фаза: {phase} (осталось ~{max(0, ticks_left)} тиков)")
            if self.phase_manager.topic_decisions:
                print(f"{Fore.GREEN}   Решения: {'; '.join(self.phase_manager.topic_decisions[-3:])}")
            if self.phase_manager.topic_actions:
                print(f"{Fore.GREEN}   Действия: {'; '.join(self.phase_manager.topic_actions[-3:])}")

        print(f"\n{Fore.WHITE}Петли повторов:")
        for a in self.agents:
            a_display = self._registry.get_name(a.agent_id)
            if a.consecutive_similar_count > 0:
                status = f"!!! {a.consecutive_similar_count} подряд" if a.consecutive_similar_count >= REPETITION_CONSECUTIVE_LIMIT else f"{a.consecutive_similar_count}"
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} {status}")
            else:
                print(f"  {a.color}{a_display}:{Style.RESET_ALL} нет повторов")

        print(f"{Fore.MAGENTA}{'=' * 60}\n")

    @staticmethod
    def _mood_bar(value: float, signed: bool = False, width: int = 10) -> str:
        if signed:
            fill = int((value + 1.0) / 2.0 * width)
        else:
            fill = int(value * width)
        fill = max(0, min(width, fill))
        return "█" * fill + "░" * (width - fill)
