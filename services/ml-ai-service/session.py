"""
Система управления пользовательскими сессиями.

Каждый пользователь получает уникальный user_id (UUID).
Все данные (агенты, память, сценарии, ChromaDB) изолированы по user_id.
Пользователь НЕ может взаимодействовать с агентами чужой сессии.
"""

import uuid
import threading
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from agent_registry import AgentRegistry


@dataclass
class UserSession:
    """Сессия одного пользователя — изолированный мир."""
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_registry: AgentRegistry = field(default_factory=AgentRegistry)
    orchestrator: Optional[object] = None  # BigBrotherOrchestrator (ленивая инициализация)
    is_active: bool = True

    def __post_init__(self):
        # Валидация user_id — только буквы, цифры, дефисы, подчёркивания
        if not self.user_id or not all(c.isalnum() or c in '-_' for c in self.user_id):
            raise ValueError(f"Невалидный user_id: '{self.user_id}'. "
                             f"Допустимы буквы, цифры, дефисы, подчёркивания.")


class SessionManager:
    """
    Менеджер сессий — хранит все активные сессии.

    Гарантии изоляции:
    - Каждая сессия имеет свой AgentRegistry (нет глобального singleton)
    - Каждая сессия имеет свой Orchestrator с изолированными агентами
    - Данные в ChromaDB разделены по user_id (префикс в коллекциях)
    - Пользователь не может отправить сообщение в чужую сессию
    """

    def __init__(self):
        self._sessions: dict[str, UserSession] = {}
        self._lock = threading.Lock()

    def create_session(self, user_id: Optional[str] = None) -> UserSession:
        """
        Создать новую сессию.

        Args:
            user_id: Пользовательский ID. Если None — генерируется UUID.

        Returns:
            UserSession — новая изолированная сессия.

        Raises:
            ValueError: Если user_id уже занят.
        """
        if user_id is None:
            user_id = str(uuid.uuid4())

        with self._lock:
            if user_id in self._sessions:
                raise ValueError(f"Сессия с user_id='{user_id}' уже существует. "
                                 f"Используйте get_session() для получения.")

            session = UserSession(user_id=user_id)
            self._sessions[user_id] = session
            return session

    def get_session(self, user_id: str) -> Optional[UserSession]:
        """Получить сессию по user_id. Возвращает None если не найдена."""
        with self._lock:
            return self._sessions.get(user_id)

    def get_or_create_session(self, user_id: str) -> UserSession:
        """Получить существующую сессию или создать новую."""
        with self._lock:
            if user_id in self._sessions:
                return self._sessions[user_id]
            session = UserSession(user_id=user_id)
            self._sessions[user_id] = session
            return session

    def close_session(self, user_id: str) -> bool:
        """
        Закрыть сессию. Сохраняет память агентов перед закрытием.

        Returns:
            True если сессия была найдена и закрыта.
        """
        with self._lock:
            session = self._sessions.pop(user_id, None)
            if session is None:
                return False
            session.is_active = False
            if session.orchestrator and hasattr(session.orchestrator, 'save_all_memories'):
                try:
                    session.orchestrator.save_all_memories()
                except Exception:
                    pass
            return True

    def validate_access(self, user_id: str, target_agent_id: str) -> bool:
        """
        Проверить, имеет ли пользователь доступ к агенту.

        Пользователь может взаимодействовать ТОЛЬКО с агентами своей сессии.

        Args:
            user_id: ID пользователя.
            target_agent_id: ID агента, к которому обращаются.

        Returns:
            True если агент принадлежит сессии пользователя.
        """
        session = self.get_session(user_id)
        if session is None:
            return False
        # Агент должен быть в реестре этой сессии
        return target_agent_id in session.agent_registry.get_all_ids()

    def list_sessions(self) -> list[dict]:
        """Список активных сессий (для мониторинга)."""
        with self._lock:
            result = []
            for uid, session in self._sessions.items():
                result.append({
                    "user_id": uid,
                    "created_at": session.created_at,
                    "is_active": session.is_active,
                    "agents_count": len(session.agent_registry.get_all_ids()),
                    "agent_names": session.agent_registry.get_all_names(),
                })
            return result

    @property
    def active_count(self) -> int:
        """Количество активных сессий."""
        with self._lock:
            return sum(1 for s in self._sessions.values() if s.is_active)


# Глобальный менеджер сессий (singleton)
session_manager = SessionManager()
