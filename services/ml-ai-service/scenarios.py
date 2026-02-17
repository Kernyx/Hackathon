"""
Сценарии и события: Scenario, ScenarioManager, UserEventInput.
Данные сценариев вынесены в data_presets/scenarios_data.py.
"""

import sys
import time
import queue
import random
import threading
from dataclasses import dataclass, field
from typing import Optional

from colorama import Fore, Style

from config import SCENARIO_EVENT_INTERVAL
from data_presets.scenarios_data import SCENARIOS_DATA
import chroma_storage


@dataclass
class Scenario:
    name: str
    description: str
    context: str
    events: list[str] = field(default_factory=list)
    current_event_index: int = 0


class ScenarioManager:
    SCENARIOS = {
        key: Scenario(
            name=data["name"],
            description=data["description"],
            context=data["context"],
            events=data["events"],
        )
        for key, data in SCENARIOS_DATA.items()
    }

    def __init__(self, scenario_name: str = "desert_island", user_id: str = ""):
        self.current_scenario = self.SCENARIOS.get(scenario_name, self.SCENARIOS["desert_island"])
        self.events_triggered: list[str] = []
        self.user_id = user_id
        self.load_from_db()

    def get_scenario_context(self) -> str:
        context = f"\nСЦЕНАРИЙ: {self.current_scenario.name}\n"
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
        chroma_storage.save_scenario_state(
            scenario_name=self.current_scenario.name,
            events_triggered=self.events_triggered,
            user_id=self.user_id,
        )

    def load_from_db(self):
        try:
            data = chroma_storage.load_scenario_state(user_id=self.user_id)
            self.events_triggered = data.get("events_triggered", [])
        except Exception as e:
            print(f"{Fore.YELLOW}Не удалось загрузить сценарий: {e}{Style.RESET_ALL}")


class UserEventInput:
    """Фоновый поток для ввода пользовательских событий и сообщений."""

    def __init__(self, agent_names: list[str] = None):
        self.event_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self.agent_names: list[str] = agent_names or []

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._input_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def get_pending_events(self) -> list[str]:
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
        while self._running:
            try:
                if self._paused:
                    time.sleep(0.2)
                    continue
                line = sys.stdin.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line = line.strip()
                if not line:
                    continue
                if line.lower() in ('quit', 'exit', 'выход', 'стоп'):
                    self.event_queue.put('__QUIT__')
                    continue
                if line.lower() in ('help', 'помощь', '?'):
                    self._print_help()
                    continue
                if line.lower() in ('stats', 'стат', 'статистика'):
                    self.event_queue.put('__STATS__')
                    continue
                # Команда изменения скорости: speed X / скорость X
                lower = line.lower().strip()
                if lower.startswith('speed ') or lower.startswith('скорость '):
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        try:
                            val = float(parts[1].replace(',', '.'))
                            if val < 0:
                                print(f"{Fore.RED}Задержка не может быть отрицательной.{Style.RESET_ALL}")
                            else:
                                self.event_queue.put(f'__SPEED__{val}')
                        except ValueError:
                            print(f"{Fore.RED}Неверное значение. Используйте: speed 0.5{Style.RESET_ALL}")
                    continue
                if lower in ('pause', 'пауза'):
                    self.event_queue.put('__SPEED__0')
                    continue
                # Команда добавления агента: add <раса> <имя> / добавить <раса> <имя>
                if lower.startswith('add ') or lower.startswith('добавить '):
                    self.event_queue.put(f'__ADD_AGENT__{line}')
                    continue
                # Команда удаления агента: remove <имя> / удалить <имя>
                if lower.startswith('remove ') or lower.startswith('удалить '):
                    self.event_queue.put(f'__REMOVE_AGENT__{line}')
                    continue
                # Команда списка агентов
                if lower in ('agents', 'агенты', 'список'):
                    self.event_queue.put('__LIST_AGENTS__')
                    continue
                self.event_queue.put(line)
            except (EOFError, OSError):
                time.sleep(0.5)
            except Exception:
                time.sleep(0.3)

    def _print_help(self):
        agent_list = ', '.join(self.agent_names) if self.agent_names else 'Алиса, Борис, Вика'
        print(f"\n{Fore.CYAN}{'-' * 50}")
        print(f"{Fore.CYAN}ИНТЕРАКТИВНАЯ СИСТЕМА")
        print(f"{Fore.CYAN}{'-' * 50}")
        print(f"{Fore.WHITE}  СООБЩЕНИЯ АГЕНТАМ:")
        print(f"{Fore.GREEN}    @Алиса Привет, как дела?     — личное сообщение Алисе")
        print(f"{Fore.GREEN}    @Борис Что думаешь?          — личное сообщение Борису")
        print(f"{Fore.GREEN}    @все Ребята, я тут!           — сообщение всем агентам")
        print(f"{Fore.GREEN}    @all Внимание!                — сообщение всем агентам")
        print(f"{Fore.WHITE}  Доступные агенты: {agent_list}")
        print(f"")
        print(f"{Fore.WHITE}  СОБЫТИЯ В МИРЕ:")
        print(f"{Fore.GREEN}    На горизонте появился дым от другого костра")
        print(f"{Fore.GREEN}    Земля начала трястись — землетрясение!")
        print(f"{Fore.WHITE}  (текст без @ — создаёт событие в мире)")
        print(f"")
        print(f"{Fore.WHITE}  УПРАВЛЕНИЕ АГЕНТАМИ:")
        print(f"{Fore.GREEN}    add <раса> <имя>        — добавить нового агента")
        print(f"{Fore.GREEN}    добавить <раса> <имя>   — добавить нового агента")
        print(f"{Fore.GREEN}    remove <имя>            — удалить агента из симуляции")
        print(f"{Fore.GREEN}    удалить <имя>           — удалить агента из симуляции")
        print(f"{Fore.GREEN}    agents / агенты         — список текущих агентов")
        print(f"{Fore.WHITE}  Доступные расы: human/человек, elf/эльф, dwarf/дварф, orc/орк, goblin/гоблин")
        print(f"{Fore.WHITE}  Пример: add elf Леголас   или   добавить орк Грук")
        print(f"")
        print(f"{Fore.WHITE}  КОМАНДЫ:")
        print(f"{Fore.YELLOW}    help / помощь / ?       — эта подсказка")
        print(f"{Fore.YELLOW}    stats / стат            — показать статистику")
        print(f"{Fore.YELLOW}    speed X / скорость X    — задержка между ходами (сек), напр.: speed 0.2")
        print(f"{Fore.YELLOW}    pause / пауза           — поставить на паузу (speed 0)")
        print(f"{Fore.YELLOW}    quit / выход            — остановить симуляцию")
        print(f"{Fore.CYAN}{'-' * 50}\n")
