"""
Реестр агентов: единый id → display_name маппинг.
Все внутренние структуры используют agent_id, display_name — только для UI и промптов.
"""

import threading
from typing import Optional


class AgentRegistry:
    """Единый реестр агентов: id → display_name. Потокобезопасный."""

    def __init__(self):
        self._id_to_name: dict[str, str] = {}
        self._name_to_id: dict[str, str] = {}
        self._name_history: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def register(self, agent_id: str, display_name: str):
        """Зарегистрировать нового агента."""
        with self._lock:
            self._id_to_name[agent_id] = display_name
            self._name_to_id[display_name.lower()] = agent_id
            self._name_history.setdefault(agent_id, []).append(display_name)

    def unregister(self, agent_id: str) -> str:
        """Удалить агента из реестра. Возвращает его имя."""
        with self._lock:
            name = self._id_to_name.pop(agent_id, "")
            if name:
                self._name_to_id.pop(name.lower(), None)
            return name

    def rename(self, agent_id: str, new_name: str, agents: list = None) -> str:
        """Переименовать агента. Возвращает старое имя."""
        with self._lock:
            old_name = self._id_to_name.get(agent_id, "")

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
        with self._lock:
            return self._id_to_name.get(agent_id, agent_id)

    def get_id(self, name: str) -> Optional[str]:
        """Получить agent_id по текущему имени (регистронезависимо)."""
        with self._lock:
            return self._name_to_id.get(name.lower())

    def get_id_fuzzy(self, name: str) -> Optional[str]:
        """Нечёткий поиск id по началу имени."""
        with self._lock:
            name_lower = name.lower()
            if name_lower in self._name_to_id:
                return self._name_to_id[name_lower]
            for display_lower, aid in self._name_to_id.items():
                if display_lower.startswith(name_lower):
                    return aid
            for aid, history in self._name_history.items():
                for old_name in history:
                    if old_name.lower().startswith(name_lower):
                        return aid
            return None

    def get_all_ids(self) -> list[str]:
        """Все зарегистрированные agent_id."""
        with self._lock:
            return list(self._id_to_name.keys())

    def get_all_names(self) -> list[str]:
        """Все текущие display_name."""
        with self._lock:
            return list(self._id_to_name.values())

    def get_name_history(self, agent_id: str) -> list[str]:
        """История имён агента."""
        with self._lock:
            return list(self._name_history.get(agent_id, []))

    def is_known_name(self, name: str) -> bool:
        """Проверяет, является ли имя текущим или бывшим именем какого-то агента."""
        with self._lock:
            if name.lower() in self._name_to_id:
                return True
            for history in self._name_history.values():
                if any(n.lower() == name.lower() for n in history):
                    return True
            return False


# Глобальный реестр — создаётся один раз, используется везде
agent_registry = AgentRegistry()
