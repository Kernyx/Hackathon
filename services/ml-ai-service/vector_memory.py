"""
Векторная БД на основе TF-IDF + косинусное сходство.
Работает как ДОПОЛНИТЕЛЬНЫЙ слой поверх существующей AgentMemorySystem.
НЕ заменяет основную память — только обогащает контекст релевантными воспоминаниями.
Без внешних зависимостей (numpy, sklearn не нужны).
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, asdict
from typing import Optional

from config import VECTOR_MEMORY_TOP_K
import chroma_storage


_STOP_WORDS = frozenset({
    'и', 'в', 'на', 'с', 'по', 'для', 'не', 'что', 'это', 'как',
    'но', 'а', 'к', 'из', 'от', 'за', 'до', 'о', 'об', 'у', 'же',
    'бы', 'ли', 'то', 'ни', 'мы', 'вы', 'он', 'она', 'они', 'оно',
    'так', 'уже', 'ещё', 'еще', 'тоже', 'только', 'вот', 'если',
    'тут', 'там', 'потом', 'очень', 'всё', 'все', 'его', 'её', 'ее',
    'их', 'нас', 'вас', 'ты', 'я', 'мне', 'тебе', 'нам', 'вам',
    'им', 'ему', 'ей', 'себя', 'себе', 'при', 'будет', 'быть',
    'был', 'была', 'были', 'есть', 'может', 'нужно', 'надо',
    'давай', 'давайте', 'просто', 'этот', 'эта', 'эти', 'этих',
    'тебя', 'меня', 'свой', 'свою', 'своё', 'свои',
})


def _tokenize(text: str) -> list[str]:
    """Токенизация: слова >= 3 символов, без стоп-слов."""
    words = re.findall(r'[а-яёa-z]+', text.lower())
    return [w for w in words if len(w) >= 3 and w not in _STOP_WORDS]


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Косинусное сходство между двумя разреженными TF-IDF векторами."""
    if not vec_a or not vec_b:
        return 0.0
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class VectorDocument:
    """Один документ в векторной БД."""
    text: str
    tick: int
    importance: float
    is_event: bool
    speaker: str
    speaker_id: str


class VectorMemoryLayer:
    """
    Легковесная векторная БД для одного агента.
    
    Принцип работы:
    - Хранит документы (текст + метаданные)
    - Строит TF-IDF индекс по всем документам
    - При запросе находит top-K наиболее релевантных воспоминаний
    - НЕ влияет на основную систему памяти — только читается при формировании промпта
    
    Максимум документов: 200 (с автоочисткой старых/неважных).
    """

    MAX_DOCUMENTS = 200

    def __init__(self, agent_id: str, user_id: str = ""):
        self.agent_id = agent_id
        self.user_id = user_id
        self.documents: list[VectorDocument] = []
        self._idf_cache: dict[str, float] = {}
        self._tfidf_cache: list[dict[str, float]] = []
        self._dirty = False  # нужен ли пересчёт IDF
        self._load()

    def add_document(self, text: str, tick: int, importance: float = 0.5,
                     is_event: bool = False, speaker: str = "",
                     speaker_id: str = ""):
        """Добавить документ в векторную БД."""
        # Не добавляем слишком короткие тексты
        if not text or len(text.strip()) < 10:
            return

        doc = VectorDocument(
            text=text.strip()[:300],  # лимит длины документа
            tick=tick,
            importance=importance,
            is_event=is_event,
            speaker=speaker,
            speaker_id=speaker_id,
        )
        self.documents.append(doc)
        self._dirty = True

        # Автоочистка при переполнении
        if len(self.documents) > self.MAX_DOCUMENTS:
            self._prune()

    def search(self, query: str, top_k: int = VECTOR_MEMORY_TOP_K,
               exclude_ticks: set[int] = None) -> list[VectorDocument]:
        """
        Найти top_k документов, наиболее похожих на query.
        exclude_ticks — тики, которые уже видны в short-term (не дублируем).
        """
        if not self.documents or not query:
            return []

        if self._dirty:
            self._rebuild_index()

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_tf = Counter(query_tokens)
        max_freq = max(query_tf.values()) if query_tf else 1
        query_tfidf = {}
        for word, freq in query_tf.items():
            tf = 0.5 + 0.5 * (freq / max_freq)
            idf = self._idf_cache.get(word, 0.0)
            if idf > 0:
                query_tfidf[word] = tf * idf

        if not query_tfidf:
            return []

        exclude = exclude_ticks or set()
        scored: list[tuple[float, int, VectorDocument]] = []

        for i, doc in enumerate(self.documents):
            if doc.tick in exclude:
                continue
            if i >= len(self._tfidf_cache):
                continue
            sim = _cosine_similarity(query_tfidf, self._tfidf_cache[i])
            if sim > 0.05:  # минимальный порог релевантности
                # Бонус за важность и события
                boosted = sim * (0.7 + 0.3 * doc.importance)
                if doc.is_event:
                    boosted *= 1.3
                scored.append((boosted, i, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, _, doc in scored[:top_k]]

    def search_by_context(self, recent_messages: list[str],
                          current_event: str = "",
                          exclude_ticks: set[int] = None) -> list[VectorDocument]:
        """
        Поиск по контексту: строит запрос из последних сообщений + текущего события.
        Это основной метод для использования из format_for_prompt().
        """
        parts = []
        if current_event:
            parts.append(current_event)
        # Берём только 3 последних сообщения для запроса (не раздуваем)
        for msg in recent_messages[-3:]:
            parts.append(msg[:100])
        query = " ".join(parts)
        return self.search(query, exclude_ticks=exclude_ticks)

    def _rebuild_index(self):
        """Пересчёт TF-IDF индекса по всем документам."""
        n = len(self.documents)
        if n == 0:
            self._idf_cache = {}
            self._tfidf_cache = []
            self._dirty = False
            return

        # Подсчёт DF (document frequency)
        doc_tokens_list: list[list[str]] = []
        df: dict[str, int] = Counter()

        for doc in self.documents:
            tokens = _tokenize(doc.text)
            doc_tokens_list.append(tokens)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                df[t] += 1

        # IDF
        self._idf_cache = {}
        for word, count in df.items():
            self._idf_cache[word] = math.log((n + 1) / (count + 1)) + 1.0

        # TF-IDF для каждого документа
        self._tfidf_cache = []
        for tokens in doc_tokens_list:
            if not tokens:
                self._tfidf_cache.append({})
                continue
            tf_counts = Counter(tokens)
            max_freq = max(tf_counts.values())
            tfidf = {}
            for word, freq in tf_counts.items():
                tf = 0.5 + 0.5 * (freq / max_freq)
                idf = self._idf_cache.get(word, 0.0)
                tfidf[word] = tf * idf
            self._tfidf_cache.append(tfidf)

        self._dirty = False

    def _prune(self):
        """Удалить наименее важные документы при переполнении."""
        if len(self.documents) <= self.MAX_DOCUMENTS:
            return

        # Сохраняем все события и высоко-важные
        keep = []
        removable = []
        for doc in self.documents:
            if doc.is_event or doc.importance >= 0.8:
                keep.append(doc)
            else:
                removable.append(doc)

        # Из removable оставляем самые свежие и важные
        removable.sort(key=lambda d: (d.tick, d.importance), reverse=True)
        slots = self.MAX_DOCUMENTS - len(keep)
        keep.extend(removable[:max(slots, 0)])

        self.documents = keep
        self._dirty = True

    def save(self):
        """Сохранить документы в ChromaDB."""
        chroma_storage.save_vector_documents(
            agent_id=self.agent_id,
            documents=[asdict(d) for d in self.documents],
            user_id=self.user_id,
        )

    def _load(self):
        """Загрузить документы из ChromaDB."""
        try:
            docs_data = chroma_storage.load_vector_documents(self.agent_id, user_id=self.user_id)
            for doc_dict in docs_data:
                self.documents.append(VectorDocument(
                    text=doc_dict["text"],
                    tick=doc_dict["tick"],
                    importance=doc_dict.get("importance", 0.5),
                    is_event=doc_dict.get("is_event", False),
                    speaker=doc_dict.get("speaker", ""),
                    speaker_id=doc_dict.get("speaker_id", ""),
                ))
            if self.documents:
                self._dirty = True  # нужен пересчёт индекса
        except Exception:
            pass  # не критично — основная память работает независимо
