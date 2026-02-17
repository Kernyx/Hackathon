"""
Конфигурация проекта: все константы и параметры.

Данные (пресеты, сценарии, словари эмоций) вынесены в data_presets/.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
LLM_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.getenv("OLLAMA_API_KEY", "not-needed")
LLM_MODEL = os.getenv("OLLAMA_MODEL", "qwen-3-14b-instruct")
LLM_TIMEOUT = 60
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAY = 2.0

# --- Audit ---
AUDIT_API_URL = os.getenv("AUDIT_API_URL", "http://localhost:8000/events")

# --- Симуляция ---
MAX_TICKS = 150
TICK_DELAY = 0.5
MEMORY_WINDOW = 12
MAX_RESPONSE_CHARS = 250
MAX_CONTEXT_TOKENS = 3200

# --- Память ---
SHORT_TERM_MEMORY = 15
LONG_TERM_MEMORY = 50
COMPRESSION_THRESHOLD = 80
SUMMARY_LENGTH = 7
IMPORTANCE_DECAY_FACTOR = 0.97
EPISODE_GAP_TICKS = 3

# --- ChromaDB ---
CHROMA_DB_PATH = "data/chroma_db"

# --- Векторная память ---
VECTOR_MEMORY_TOP_K = 3

# --- Темы ---
TOPIC_CHANGE_THRESHOLD = 15
CREATIVITY_BOOST = 0.2
REPETITION_SIMILARITY_THRESHOLD = 0.5

# --- Сценарий ---
SCENARIO_EVENT_INTERVAL = 15

# --- События ---
EVENT_FOCUS_DURATION = 7
EVENT_FORCED_REACTION_TICKS = 3

# --- Отношения ---
RELATIONSHIP_CHANGE_RATE = 0.05
GOBLIN_DISTRUST = -0.15

# --- Повторы ---
REPETITION_CONSECUTIVE_LIMIT = 2

# --- Фазы диалога ---
PHASE_TICKS = {"discuss": 8, "decide": 6, "act": 4, "conclude": 3}
PHASE_ORDER = ["discuss", "decide", "act", "conclude"]
PHASE_LABELS = {"discuss": "Обсуждение", "decide": "Решение", "act": "Действие", "conclude": "Итог"}

# --- Настроение ---
MOOD_DECAY_RATE = 0.04
MOOD_EVENT_IMPACT = 0.30
MOOD_INTERACTION_IMPACT = 0.15

# --- Реэкспорт данных из data_presets (для обратной совместимости) ---
from data_presets.mood_data import MOOD_EMOJIS, EVENT_MOOD_TRIGGERS
