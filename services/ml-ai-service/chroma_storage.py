"""
Единый слой хранения данных на базе ChromaDB.

Коллекции:
  agent_memory   — short_term / long_term воспоминания агентов
  vector_memory  — документы для TF-IDF поиска
  scenario_state — состояние сценария (events_triggered)
  topic_state    — состояние тем (current_topic, discussed_topics)

Каждая запись хранит:
  document  — текстовое содержимое (для встроенного embedding)
  metadata  — все структурированные поля (tick, importance, is_event и т.д.)
  id        — уникальный ключ записи
"""

import json
import threading
from pathlib import Path
from typing import Optional

import chromadb

from config import CHROMA_DB_PATH


_client: Optional[chromadb.ClientAPI] = None
_client_lock = threading.Lock()


def get_client() -> chromadb.ClientAPI:
    """Ленивая инициализация ChromaDB клиента (persistent). Потокобезопасно."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # double-checked locking
                db_path = Path(CHROMA_DB_PATH)
                db_path.mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=str(db_path))
    return _client


def get_collection(name: str, user_id: str = "") -> chromadb.Collection:
    """Получить или создать коллекцию. Embedding отключён (поиск свой, TF-IDF).
    
    Args:
        name: Базовое имя коллекции.
        user_id: ID пользователя для изоляции данных. Если пусто — общая коллекция.
    """
    client = get_client()
    # Изоляция по user_id: каждый пользователь получает свой набор коллекций
    if user_id:
        # ChromaDB ограничивает длину имени коллекции (63 символа)
        # Используем последние 12 символов user_id как суффикс
        safe_uid = user_id.replace('-', '_')[:12]
        collection_name = f"{name}__{safe_uid}"
    else:
        collection_name = name
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def _meta_safe(value) -> str | int | float | bool:
    """ChromaDB metadata принимает только str/int/float/bool. Конвертируем остальное."""
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return ""
    return str(value)


# ---------------------------------------------------------------------------
#  Agent Memory (short_term + long_term)
# ---------------------------------------------------------------------------

def save_agent_memories(agent_id: str, short_term: list[dict], long_term: list[dict],
                        completed_actions: list[str], group_decisions: list[dict],
                        user_id: str = ""):
    """Полное сохранение памяти агента в ChromaDB."""
    col = get_collection("agent_memory", user_id=user_id)

    # Удаляем старые записи этого агента
    _delete_by_prefix(col, agent_id)

    ids = []
    documents = []
    metadatas = []

    for idx, mem in enumerate(short_term):
        doc_id = f"{agent_id}__st__{idx}"
        ids.append(doc_id)
        documents.append(mem.get("text", ""))
        metadatas.append({
            "agent_id": agent_id,
            "layer": "short_term",
            "tick": _meta_safe(mem.get("tick", 0)),
            "speaker": _meta_safe(mem.get("speaker", "")),
            "speaker_id": _meta_safe(mem.get("speaker_id", "")),
            "timestamp": _meta_safe(mem.get("timestamp", "")),
            "importance": float(mem.get("importance", 0.5)),
            "addressed_to": _meta_safe(mem.get("addressed_to", "")),
            "addressed_to_id": _meta_safe(mem.get("addressed_to_id", "")),
            "is_event": bool(mem.get("is_event", False)),
            "is_action_result": bool(mem.get("is_action_result", False)),
        })

    for idx, mem in enumerate(long_term):
        doc_id = f"{agent_id}__lt__{idx}"
        ids.append(doc_id)
        documents.append(mem.get("text", ""))
        metadatas.append({
            "agent_id": agent_id,
            "layer": "long_term",
            "tick": _meta_safe(mem.get("tick", 0)),
            "speaker": _meta_safe(mem.get("speaker", "")),
            "speaker_id": _meta_safe(mem.get("speaker_id", "")),
            "timestamp": _meta_safe(mem.get("timestamp", "")),
            "importance": float(mem.get("importance", 0.5)),
            "addressed_to": _meta_safe(mem.get("addressed_to", "")),
            "addressed_to_id": _meta_safe(mem.get("addressed_to_id", "")),
            "is_event": bool(mem.get("is_event", False)),
            "is_action_result": bool(mem.get("is_action_result", False)),
        })

    for idx, action in enumerate(completed_actions):
        doc_id = f"{agent_id}__act__{idx}"
        ids.append(doc_id)
        documents.append(action)
        metadatas.append({
            "agent_id": agent_id,
            "layer": "completed_actions",
            "tick": 0,
            "importance": 0.0,
            "is_event": False,
            "is_action_result": False,
            "speaker": "",
            "speaker_id": "",
            "timestamp": "",
            "addressed_to": "",
            "addressed_to_id": "",
        })

    for idx, decision in enumerate(group_decisions):
        doc_id = f"{agent_id}__gd__{idx}"
        ids.append(doc_id)
        documents.append(decision.get("decision", ""))
        metadatas.append({
            "agent_id": agent_id,
            "layer": "group_decisions",
            "tick": _meta_safe(decision.get("tick", 0)),
            "speaker": _meta_safe(decision.get("proposer", "")),
            "speaker_id": _meta_safe(decision.get("proposer_id", "")),
            "importance": 0.0,
            "is_event": False,
            "is_action_result": False,
            "timestamp": "",
            "addressed_to": "",
            "addressed_to_id": "",
        })

    if ids:
        _upsert_batched(col, ids, documents, metadatas)


def load_agent_memories(agent_id: str, user_id: str = "") -> dict:
    """Загрузить память агента из ChromaDB. Возвращает dict с ключами short_term/long_term/completed_actions/group_decisions."""
    col = get_collection("agent_memory", user_id=user_id)

    result = col.get(
        where={"agent_id": agent_id},
        include=["documents", "metadatas"],
    )

    short_term = []
    long_term = []
    completed_actions = []
    group_decisions = []

    if not result or not result["ids"]:
        return {
            "short_term": short_term,
            "long_term": long_term,
            "completed_actions": completed_actions,
            "group_decisions": group_decisions,
        }

    for doc, meta in zip(result["documents"], result["metadatas"]):
        layer = meta.get("layer", "")

        if layer == "short_term":
            short_term.append({
                "tick": meta.get("tick", 0),
                "speaker": meta.get("speaker", ""),
                "text": doc,
                "timestamp": meta.get("timestamp", ""),
                "importance": meta.get("importance", 0.5),
                "speaker_id": meta.get("speaker_id", ""),
                "addressed_to": meta.get("addressed_to", ""),
                "addressed_to_id": meta.get("addressed_to_id", ""),
                "is_event": meta.get("is_event", False),
                "is_action_result": meta.get("is_action_result", False),
            })
        elif layer == "long_term":
            long_term.append({
                "tick": meta.get("tick", 0),
                "speaker": meta.get("speaker", ""),
                "text": doc,
                "timestamp": meta.get("timestamp", ""),
                "importance": meta.get("importance", 0.5),
                "speaker_id": meta.get("speaker_id", ""),
                "addressed_to": meta.get("addressed_to", ""),
                "addressed_to_id": meta.get("addressed_to_id", ""),
                "is_event": meta.get("is_event", False),
                "is_action_result": meta.get("is_action_result", False),
            })
        elif layer == "completed_actions":
            completed_actions.append(doc)
        elif layer == "group_decisions":
            group_decisions.append({
                "tick": meta.get("tick", 0),
                "proposer": meta.get("speaker", ""),
                "proposer_id": meta.get("speaker_id", ""),
                "decision": doc,
            })

    # Сортируем по tick для правильного порядка
    short_term.sort(key=lambda m: m.get("tick", 0))
    long_term.sort(key=lambda m: m.get("tick", 0))

    return {
        "short_term": short_term,
        "long_term": long_term,
        "completed_actions": completed_actions,
        "group_decisions": group_decisions,
    }


# ---------------------------------------------------------------------------
#  Vector Memory (документы для TF-IDF поиска)
# ---------------------------------------------------------------------------

def save_vector_documents(agent_id: str, documents: list[dict], user_id: str = ""):
    """Сохранить документы векторной памяти агента."""
    col = get_collection("vector_memory", user_id=user_id)
    _delete_by_prefix(col, agent_id)

    if not documents:
        return

    ids = []
    docs = []
    metas = []

    for idx, vdoc in enumerate(documents):
        doc_id = f"{agent_id}__vd__{idx}"
        ids.append(doc_id)
        docs.append(vdoc.get("text", ""))
        metas.append({
            "agent_id": agent_id,
            "tick": _meta_safe(vdoc.get("tick", 0)),
            "importance": float(vdoc.get("importance", 0.5)),
            "is_event": bool(vdoc.get("is_event", False)),
            "speaker": _meta_safe(vdoc.get("speaker", "")),
            "speaker_id": _meta_safe(vdoc.get("speaker_id", "")),
        })

    _upsert_batched(col, ids, docs, metas)


def load_vector_documents(agent_id: str, user_id: str = "") -> list[dict]:
    """Загрузить документы векторной памяти агента."""
    col = get_collection("vector_memory", user_id=user_id)

    result = col.get(
        where={"agent_id": agent_id},
        include=["documents", "metadatas"],
    )

    documents = []
    if result and result["ids"]:
        for doc, meta in zip(result["documents"], result["metadatas"]):
            documents.append({
                "text": doc,
                "tick": meta.get("tick", 0),
                "importance": meta.get("importance", 0.5),
                "is_event": meta.get("is_event", False),
                "speaker": meta.get("speaker", ""),
                "speaker_id": meta.get("speaker_id", ""),
            })
        documents.sort(key=lambda d: d.get("tick", 0))

    return documents


# ---------------------------------------------------------------------------
#  Scenario State
# ---------------------------------------------------------------------------

def save_scenario_state(scenario_name: str, events_triggered: list[str], user_id: str = ""):
    """Сохранить состояние сценария."""
    col = get_collection("scenario_state", user_id=user_id)

    # Удаляем старое состояние
    try:
        existing = col.get(where={"kind": "scenario"}, include=[])
        if existing and existing["ids"]:
            col.delete(ids=existing["ids"])
    except Exception:
        pass

    col.upsert(
        ids=["scenario__current"],
        documents=[json.dumps(events_triggered, ensure_ascii=False)],
        metadatas=[{
            "kind": "scenario",
            "scenario_name": scenario_name,
        }],
    )


def load_scenario_state(user_id: str = "") -> dict:
    """Загрузить состояние сценария."""
    col = get_collection("scenario_state", user_id=user_id)
    try:
        result = col.get(
            ids=["scenario__current"],
            include=["documents", "metadatas"],
        )
        if result and result["ids"]:
            events = json.loads(result["documents"][0])
            return {"events_triggered": events}
    except Exception:
        pass
    return {"events_triggered": []}


# ---------------------------------------------------------------------------
#  Topic State
# ---------------------------------------------------------------------------

def save_topic_state(current_topic: Optional[str], messages_on_topic: int,
                     discussed_topics: list[str], user_id: str = ""):
    """Сохранить состояние тем."""
    col = get_collection("topic_state", user_id=user_id)

    try:
        existing = col.get(where={"kind": "topic"}, include=[])
        if existing and existing["ids"]:
            col.delete(ids=existing["ids"])
    except Exception:
        pass

    col.upsert(
        ids=["topic__current"],
        documents=[json.dumps({
            "current_topic": current_topic,
            "messages_on_topic": messages_on_topic,
            "discussed_topics": discussed_topics,
        }, ensure_ascii=False)],
        metadatas=[{"kind": "topic"}],
    )


def load_topic_state(user_id: str = "") -> dict:
    """Загрузить состояние тем."""
    col = get_collection("topic_state", user_id=user_id)
    try:
        result = col.get(
            ids=["topic__current"],
            include=["documents"],
        )
        if result and result["ids"]:
            return json.loads(result["documents"][0])
    except Exception:
        pass
    return {
        "current_topic": None,
        "messages_on_topic": 0,
        "discussed_topics": [],
    }


# ---------------------------------------------------------------------------
#  Утилиты
# ---------------------------------------------------------------------------

def _delete_by_prefix(col: chromadb.Collection, prefix: str):
    """Удалить все записи с id, начинающимся на prefix."""
    try:
        result = col.get(
            where={"agent_id": prefix},
            include=[],
        )
        if result and result["ids"]:
            col.delete(ids=result["ids"])
    except Exception:
        pass


def _upsert_batched(col: chromadb.Collection, ids: list, documents: list,
                    metadatas: list, batch_size: int = 500):
    """Upsert с разбивкой на батчи (ChromaDB ограничивает размер)."""
    for i in range(0, len(ids), batch_size):
        col.upsert(
            ids=ids[i:i + batch_size],
            documents=documents[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
        )


def reset_all(user_id: str = ""):
    """Полный сброс всех данных (для тестирования / нового запуска).
    
    Args:
        user_id: Если указан — сброс данных только этого пользователя.
                 Если пусто — сброс глобальных (legacy) данных.
    """
    client = get_client()
    base_names = ["agent_memory", "vector_memory", "scenario_state", "topic_state"]
    for name in base_names:
        if user_id:
            safe_uid = user_id.replace('-', '_')[:12]
            col_name = f"{name}__{safe_uid}"
        else:
            col_name = name
        try:
            client.delete_collection(col_name)
        except Exception:
            pass
