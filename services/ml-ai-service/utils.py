"""
Утилиты: анализ текста, обнаружение повторов.
Запрещённые паттерны вынесены в data_presets/banned_patterns.py.
"""

import re
from difflib import SequenceMatcher

from data_presets.banned_patterns import BANNED_PATTERNS, REPETITIVE_STARTS


def estimate_tokens(text: str) -> int:
    """Грубая оценка количества токенов. Для русского: ~1.5 токена на слово, ~3.5 символа на токен."""
    if not text:
        return 0
    # Русский текст: примерно 1 токен на 3-4 символа
    return max(1, len(text) // 3)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Оценить общее количество токенов во всех сообщениях."""
    total = 0
    for msg in messages:
        # 4 токена на обёртку role/content
        total += 4 + estimate_tokens(msg.get("content", ""))
    total += 2  # служебные токены начала/конца
    return total


def text_similarity(a: str, b: str) -> float:
    """Быстрая оценка похожести двух строк (0..1)."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if not a_lower or not b_lower:
        return 0.0
    return SequenceMatcher(None, a_lower, b_lower).ratio()


def extract_phrases(text: str) -> set:
    """Извлекает ключевые n-граммы (3 слова) из текста."""
    words = re.findall(r'[а-яёa-z]+', text.lower())
    if len(words) < 3:
        return set(words)
    return {' '.join(words[i:i+3]) for i in range(len(words)-2)}


def has_banned_pattern(text: str) -> bool:
    """Проверяет, содержит ли текст запрещённые паттерны-петли."""
    text_lower = text.lower().strip()
    for pattern in BANNED_PATTERNS:
        if pattern in text_lower:
            return True
    return False


def has_repetitive_pattern(text: str, recent_texts: list) -> bool:
    """Проверяет, содержит ли текст повторяющиеся паттерны из недавних сообщений."""
    if not recent_texts:
        return has_banned_pattern(text)
    if has_banned_pattern(text):
        return True
    new_phrases = extract_phrases(text)
    if not new_phrases:
        return False
    for prev_text in recent_texts[-6:]:
        prev_phrases = extract_phrases(prev_text)
        if not prev_phrases:
            continue
        overlap = len(new_phrases & prev_phrases) / max(len(new_phrases), 1)
        if overlap > 0.35:
            return True
    text_lower = text.lower().strip()
    start_matches = sum(1 for rt in recent_texts[-4:]
                        if any(rt.lower().strip().startswith(s) and text_lower.startswith(s)
                               for s in REPETITIVE_STARTS))
    if start_matches >= 1:
        return True
    return False
