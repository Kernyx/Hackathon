#!/usr/bin/env python3
"""
КИБЕР РЫВОК — AI-агенты v2
Три уникальных агента с памятью, настроением и расами обсуждают сценарии.

Модули:
  config.py         — константы и параметры
  utils.py          — утилиты (text_similarity и др.)
  llm_client.py     — LLM-клиент (httpx + OpenAI)
  agent_registry.py — реестр агентов
  models.py         — PersonalityType, BigFiveTraits, RaceType, Race, AgentMood
  memory.py         — MemoryItem, AgentMemorySystem
  scenarios.py      — Scenario, ScenarioManager, UserEventInput
  topics.py         — TopicManager, DialoguePhaseManager, Goal, ActionPlan
  agent.py          — Agent (dataclass)
  orchestrator.py   — RACE_PRESETS, create_agents(), BigBrotherOrchestrator
"""

import os
import sys
import time
import random
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

os.environ.setdefault("HTTP_PROXY", "")
os.environ.setdefault("HTTPS_PROXY", "")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

from colorama import Fore, Style, init as colorama_init
colorama_init()

from config import LLM_MODEL, LLM_BASE_URL, MAX_TICKS, TICK_DELAY, CHROMA_DB_PATH
from models import RACES
from agent_registry import agent_registry
from scenarios import ScenarioManager, UserEventInput
from orchestrator import RACE_PRESETS, create_agents, BigBrotherOrchestrator
from session import session_manager


def main():
    # Создаём изолированную сессию для этого пользователя
    session = session_manager.create_session()
    user_id = session.user_id
    registry = session.agent_registry

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'═' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  КИБЕР РЫВОК — AI-агенты v2")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  Модель: {LLM_MODEL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  LLM API: {LLM_BASE_URL}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}  Сессия: {user_id[:8]}...")
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

    print(f"{Fore.YELLOW}Очистка данных предыдущих сессий...{Style.RESET_ALL}")
    data_dir = Path("data")
    if data_dir.exists():
        for file in ["agent_memory.json", "topics.json", "scenario.json", "vector_memory.json"]:
            file_path = data_dir / file
            if file_path.exists():
                file_path.unlink()
                print(f"   Удален {file}")
    print(f"{Fore.GREEN}Данные очищены. Новая сессия!{Style.RESET_ALL}\n")

    agents = create_agents(selected_race_preset, user_id=user_id, registry=registry)
    user_input = UserEventInput(agent_names=registry.get_all_names())
    orchestrator = BigBrotherOrchestrator(
        agents, selected_scenario, user_event_input=user_input,
        user_id=user_id, registry=registry,
    )
    session.orchestrator = orchestrator

    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'=' * 60}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}СЦЕНАРИЙ: {orchestrator.scenario_manager.current_scenario.name}")
    print(f"{Fore.WHITE}{orchestrator.scenario_manager.current_scenario.description}")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}{'=' * 60}\n")

    print(f"{Fore.WHITE}Участники:")
    for a in agents:
        display = registry.get_name(a.agent_id)
        gender_icon = "M" if a.is_male else "F"
        race = a.race
        print(f"  {a.color}{Style.BRIGHT}{race.emoji} {gender_icon} {display} ({a.age} лет) [{race.name_ru}] [id: {a.agent_id}]{Style.RESET_ALL} -- {a.personality_type.value}")
        print(f"     {Fore.WHITE}Раса: {race.name_ru} -- {race.description}{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}Big Five: O:{a.big_five.openness} C:{a.big_five.conscientiousness} "
              f"E:{a.big_five.extraversion} A:{a.big_five.agreeableness} N:{a.big_five.neuroticism}{Style.RESET_ALL}")
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
        print(f"     {Fore.WHITE}Настроение: {a.mood.get_dominant_emotion()} "
              f"(Счастье:{a.mood.happiness:+.1f} Энергия:{a.mood.energy:.1f} Стресс:{a.mood.stress:.1f} "
              f"Злость:{a.mood.anger:.1f} Страх:{a.mood.fear:.1f}){Style.RESET_ALL}")
        rel_parts = []
        for b in agents:
            if a.agent_id != b.agent_id:
                b_display = registry.get_name(b.agent_id)
                rel_val = a.relationships.get(b.agent_id, 0.0)
                rel_parts.append(f"{b_display}:{rel_val:+.2f}")
        if rel_parts:
            print(f"     {Fore.WHITE}Отношения: {', '.join(rel_parts)}{Style.RESET_ALL}")
    print()

    agent_names_str = ', '.join(registry.get_all_names())
    print(f"{Fore.CYAN}{'-' * 60}")
    print(f"{Fore.CYAN}ИНТЕРАКТИВНЫЙ РЕЖИМ")
    print(f"{Fore.CYAN}{'-' * 60}")
    print(f"{Fore.WHITE}  Вы можете общаться с агентами и создавать события!")
    print(f"{Fore.WHITE}  Сообщения агентам:")
    print(f"{Fore.GREEN}    @имя текст   -- личное сообщение (напр.: @Алиса Привет!)")
    print(f"{Fore.GREEN}    @все текст   -- сообщение всем агентам")
    print(f"{Fore.WHITE}  События: просто введите текст без @")
    print(f"{Fore.WHITE}  Агенты: {agent_names_str}")
    print(f"{Fore.WHITE}  Управление агентами:")
    print(f"{Fore.GREEN}    add <раса> <имя> [личность]   -- добавить агента (напр.: add elf Леголас stoic)")
    print(f"{Fore.GREEN}    remove <имя>                  -- удалить агента  (напр.: remove Вика)")
    print(f"{Fore.GREEN}    agents / агенты               -- список текущих агентов")
    print(f"{Fore.WHITE}  Расы: human/человек, elf/эльф, dwarf/дварф, orc/орк, goblin/гоблин")
    print(f"{Fore.YELLOW}  Команды: help/помощь, stats/стат, speed X/скорость X, pause/пауза, quit/выход")
    print(f"{Fore.CYAN}{'-' * 60}\n")

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
    print(f"{Fore.MAGENTA}[tick   0] {Style.BRIGHT}Ведущий: {Style.RESET_ALL}{starter['text']}\n")

    user_input.start()

    # MAX_TICKS=0 → бесконечный режим
    infinite_mode = (MAX_TICKS == 0)
    if infinite_mode:
        print(f"{Fore.YELLOW}Бесконечный режим (MAX_TICKS=0). Для остановки: quit/выход или Ctrl+C{Style.RESET_ALL}\n")

    try:
        i = 0
        while True:
            # Проверка лимита тиков (если не бесконечный режим)
            if not infinite_mode and i >= MAX_TICKS:
                break

            if orchestrator._quit_requested:
                print(f"\n{Fore.YELLOW}Симуляция остановлена по команде пользователя.{Style.RESET_ALL}")
                break

            while orchestrator.tick_delay == 0 and not orchestrator._quit_requested:
                time.sleep(0.2)
                orchestrator._process_user_events()

            if orchestrator._quit_requested:
                print(f"\n{Fore.YELLOW}Симуляция остановлена по команде пользователя.{Style.RESET_ALL}")
                break

            entry = orchestrator.run_tick()
            if entry:
                orchestrator.print_entry(entry)

            if orchestrator._quit_requested:
                print(f"\n{Fore.YELLOW}Симуляция остановлена по команде пользователя.{Style.RESET_ALL}")
                break

            if random.random() < 0.50:
                entry2 = orchestrator.run_tick()
                if entry2:
                    orchestrator.print_entry(entry2)

            if (i + 1) % 10 == 0:
                orchestrator.print_stats()

            time.sleep(orchestrator.tick_delay)
            i += 1

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Симуляция остановлена пользователем (Ctrl+C).")

    finally:
        user_input.stop()
        print(f"\n{Fore.CYAN}Сохраняю память агентов...{Style.RESET_ALL}")
        orchestrator.save_all_memories()
        print(f"{Fore.GREEN}Память сохранена в ChromaDB ({CHROMA_DB_PATH}){Style.RESET_ALL}")
        # Закрываем сессию пользователя
        session_manager.close_session(user_id)
        print(f"{Fore.GREEN}Сессия {user_id[:8]}... закрыта.{Style.RESET_ALL}")

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
