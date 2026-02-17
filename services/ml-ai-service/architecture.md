# Техническая архитектура системы AI-агентов
## Хакатон "КИБЕР РЫВОК"

---

## 🎯 Основная идея и логика общения агентов

### Концепция системы
Система представляет собой **непрерывный event-driven цикл симуляции**, где агенты живут в общем виртуальном пространстве и взаимодействуют друг с другом через события.

### Жизненный цикл агента (каждый тик симуляции)

```
┌─────────────────────────────────────────────────────────┐
│                    SIMULATION TICK                      │
│                     (базовая единица времени)           │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 1. ВОСПРИЯТИЕ (Perception)                              │
│    • Получение событий из окружения                     │
│    • Получение сообщений от других агентов              │
│    • Обновление текущего контекста                      │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 2. ОБНОВЛЕНИЕ СОСТОЯНИЯ                                 │
│    • Обновление эмоционального состояния                │
│    • Пересчёт отношений с другими агентами              │
│    • Сохранение события в память                        │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 3. ИЗВЛЕЧЕНИЕ ПАМЯТИ (Memory Retrieval)                 │
│    • Векторный поиск релевантных воспоминаний           │
│    • Фильтрация по важности и свежести                  │
│    • Формирование контекста для LLM                     │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 4. ПЛАНИРОВАНИЕ (LLM Reasoning)                         │
│    • Отправка контекста в LLM                           │
│    • Получение JSON-плана действий                      │
│    • Валидация ответа                                   │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ 5. ДЕЙСТВИЕ (Action Execution)                          │
│    • Выполнение запланированного действия               │
│    • Генерация события для других агентов               │
│    • Broadcast в систему                                │
└─────────────────────────────────────────────────────────┘
```

---

## ⚡ Управление скоростью общения

### Концепция времени симуляции

**Ключевая идея:** Отделение реального времени от времени симуляции.

```python
# Параметры скорости
TICK_DURATION = 1.0  # секунда реального времени на 1 тик
TIME_MULTIPLIER = 1.0  # множитель скорости (управляется слайдером)

# Примеры:
# TIME_MULTIPLIER = 0.5  → агенты общаются медленнее (2 сек на тик)
# TIME_MULTIPLIER = 2.0  → агенты общаются быстрее (0.5 сек на тик)
# TIME_MULTIPLIER = 5.0  → ускоренная симуляция (0.2 сек на тик)
```

### Реализация контроллера скорости

```python
class SimulationController:
    def __init__(self):
        self.time_multiplier = 1.0  # default
        self.current_tick = 0
        self.is_running = False
        
    def set_speed(self, multiplier: float):
        """Изменить скорость симуляции (от слайдера фронта)"""
        self.time_multiplier = max(0.1, min(10.0, multiplier))
        
    async def run_simulation_loop(self):
        """Основной цикл симуляции"""
        while self.is_running:
            tick_start = time.time()
            
            # Выполнить один тик для всех агентов
            await self.process_tick()
            
            # Рассчитать задержку с учётом множителя
            base_delay = 1.0  # 1 секунда базовая
            adjusted_delay = base_delay / self.time_multiplier
            
            # Учесть время выполнения тика
            elapsed = time.time() - tick_start
            sleep_time = max(0, adjusted_delay - elapsed)
            
            await asyncio.sleep(sleep_time)
            self.current_tick += 1
```

### Механизм throttling для LLM запросов

```python
class AgentThrottler:
    """Предотвращает перегрузку LLM API"""
    
    def __init__(self, max_concurrent=5, cooldown=2.0):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.cooldown = cooldown
        self.last_request = {}
        
    async def can_act(self, agent_id: str) -> bool:
        """Проверить, может ли агент сейчас действовать"""
        now = time.time()
        last = self.last_request.get(agent_id, 0)
        
        if now - last < self.cooldown:
            return False
            
        async with self.semaphore:
            self.last_request[agent_id] = now
            return True
```

---

## 📊 Структура данных между сервисами

### 1. Создание агента (Frontend → ai-agent-service)

```json
{
  "agent_data": {
    "name": "Алиса",
    "avatar_url": "https://...",
    "personality_type": "ENFP",
    "age": 25,
    "interests": ["музыка", "искусство", "путешествия"],
    "additional_traits": "Оптимистична, любит помогать людям, немного импульсивна. Мечтает стать художником.",
    "initial_mood": {
      "happiness": 0.7,
      "energy": 0.6,
      "sociability": 0.8
    }
  }
}
```

**Обработка в ai-agent-service:**
```python
# 1. Валидация данных
# 2. Создание записи в PostgreSQL
# 3. Отправка в ml-service для инициализации
```

---

### 2. Инициализация агента (ai-agent-service → ml-service)

```json
{
  "command": "initialize_agent",
  "agent_id": "agent_001",
  "data": {
    "name": "Алиса",
    "personality": {
      "type": "ENFP",
      "traits": {
        "openness": 0.8,
        "conscientiousness": 0.6,
        "extraversion": 0.9,
        "agreeableness": 0.7,
        "neuroticism": 0.4
      },
      "description": "Оптимистична, любит помогать..."
    },
    "age": 25,
    "interests": ["музыка", "искусство", "путешествия"],
    "initial_mood": {
      "happiness": 0.7,
      "energy": 0.6,
      "sociability": 0.8
    }
  }
}
```

**Действия ml-service:**
1. Создать когнитивное ядро агента
2. Инициализировать векторное хранилище (Chroma collection)
3. Создать начальную социальную матрицу
4. Вернуть подтверждение

---

### 3. Событие в симуляции (ai-agent-service → ml-service)

```json
{
  "command": "process_event",
  "simulation_id": "sim_001",
  "tick": 1523,
  "event": {
    "type": "user_message",
    "target_agent_id": "agent_001",
    "content": "Привет, Алиса! Как дела?",
    "sender": "user",
    "timestamp": 1708095600
  }
}
```

или

```json
{
  "command": "process_event",
  "simulation_id": "sim_001",
  "tick": 1524,
  "event": {
    "type": "agent_message",
    "sender_agent_id": "agent_002",
    "target_agent_id": "agent_001",
    "content": "Слушай, хочешь сходить на концерт завтра?",
    "timestamp": 1708095661
  }
}
```

или

```json
{
  "command": "process_event",
  "simulation_id": "sim_001",
  "tick": 1525,
  "event": {
    "type": "environment",
    "content": "Найден клад с древними артефактами!",
    "affected_agents": ["agent_001", "agent_002", "agent_003"],
    "timestamp": 1708095722
  }
}
```

---

### 4. Ответ агента (ml-service → ai-agent-service)

```json
{
  "agent_id": "agent_001",
  "tick": 1523,
  "response": {
    "action": {
      "type": "message",
      "target": "user",
      "content": "Привет! Дела отлично, спасибо! Сегодня такой хороший день! ☀️",
      "emotion": "joyful"
    },
    "internal_state": {
      "mood": {
        "happiness": 0.75,
        "energy": 0.65,
        "sociability": 0.85
      },
      "thought": "Приятно получить сообщение! Хочется поделиться позитивом."
    },
    "memory_saved": {
      "event": "user_message",
      "importance": 0.6,
      "reflection": "Пользователь проявил интерес ко мне, это мило"
    }
  }
}
```

---

### 5. Состояние агента для фронтенда (ai-agent-service → Frontend)

```json
{
  "agent_id": "agent_001",
  "name": "Алиса",
  "avatar_url": "https://...",
  "current_state": {
    "mood": {
      "happiness": 0.75,
      "energy": 0.65,
      "sociability": 0.85,
      "dominant_emotion": "joyful",
      "emoji": "😊"
    },
    "status": "active",
    "last_action": "Отправила сообщение пользователю",
    "last_action_time": 1708095600
  },
  "relationships": [
    {
      "agent_id": "agent_002",
      "agent_name": "Боб",
      "relationship_value": 0.6,
      "relationship_type": "friend",
      "last_interaction": "30 минут назад"
    },
    {
      "agent_id": "agent_003",
      "agent_name": "Чарли",
      "relationship_value": -0.3,
      "relationship_type": "rival",
      "last_interaction": "2 часа назад"
    }
  ],
  "recent_memories": [
    {
      "timestamp": 1708095000,
      "event": "Боб пригласил на концерт",
      "importance": 0.8,
      "emotion": "excited"
    },
    {
      "timestamp": 1708094000,
      "event": "Поспорила с Чарли о музыке",
      "importance": 0.7,
      "emotion": "frustrated"
    }
  ]
}
```

---

### 6. Граф отношений (ai-agent-service → Frontend)

```json
{
  "simulation_id": "sim_001",
  "tick": 1523,
  "graph": {
    "nodes": [
      {
        "id": "agent_001",
        "name": "Алиса",
        "avatar_url": "https://...",
        "mood_color": "#FFD700",
        "mood_emoji": "😊"
      },
      {
        "id": "agent_002",
        "name": "Боб",
        "avatar_url": "https://...",
        "mood_color": "#87CEEB",
        "mood_emoji": "😌"
      }
    ],
    "edges": [
      {
        "from": "agent_001",
        "to": "agent_002",
        "value": 0.6,
        "color": "#4CAF50",
        "label": "друзья",
        "strength": "medium",
        "interactions_count": 23
      },
      {
        "from": "agent_001",
        "to": "agent_003",
        "value": -0.3,
        "color": "#F44336",
        "label": "соперники",
        "strength": "weak",
        "interactions_count": 8
      }
    ]
  }
}
```

---

### 7. Лента событий (ai-agent-service → Frontend, WebSocket)

```json
{
  "type": "event_stream",
  "events": [
    {
      "tick": 1523,
      "timestamp": 1708095600,
      "event_type": "message",
      "from": "agent_001",
      "from_name": "Алиса",
      "to": "user",
      "content": "Привет! Дела отлично, спасибо!",
      "emotion": "joyful"
    },
    {
      "tick": 1524,
      "timestamp": 1708095661,
      "event_type": "mood_change",
      "agent_id": "agent_002",
      "agent_name": "Боб",
      "old_mood": "neutral",
      "new_mood": "anxious",
      "reason": "Беспокоится о завтрашнем экзамене"
    },
    {
      "tick": 1525,
      "timestamp": 1708095722,
      "event_type": "relationship_change",
      "agent1_id": "agent_001",
      "agent1_name": "Алиса",
      "agent2_id": "agent_003",
      "agent2_name": "Чарли",
      "old_value": -0.2,
      "new_value": -0.3,
      "reason": "Очередной спор о музыкальных вкусах"
    }
  ]
}
```

---

## 🏗️ Разделение ответственности сервисов

### AI-Agent-Service (Backend)

**Технологии:** FastAPI, PostgreSQL, Redis, WebSocket

**Ответственность:**

#### 1. CRUD операции с агентами
```python
# Создание агента
POST /api/agents
{
  "name": "Алиса",
  "avatar_url": "...",
  "personality_type": "ENFP",
  ...
}

# Получение агента
GET /api/agents/{agent_id}

# Обновление агента
PATCH /api/agents/{agent_id}

# Удаление агента
DELETE /api/agents/{agent_id}

# Список всех агентов
GET /api/agents
```

#### 2. Управление симуляцией
```python
# Запуск симуляции
POST /api/simulation/start

# Пауза
POST /api/simulation/pause

# Изменение скорости
POST /api/simulation/speed
{
  "multiplier": 2.0
}

# Статус симуляции
GET /api/simulation/status
```

#### 3. Пользовательские действия
```python
# Отправить сообщение агенту
POST /api/interaction/message
{
  "target_agent_id": "agent_001",
  "content": "Привет!"
}

# Добавить событие в мир
POST /api/interaction/event
{
  "type": "environment",
  "content": "Найден клад!"
}

# Изменить окружение
POST /api/interaction/environment
{
  "parameter": "weather",
  "value": "rainy"
}
```

#### 4. WebSocket для real-time обновлений
```python
# Подключение к ленте событий
WS /ws/events

# Подписка на конкретного агента
WS /ws/agent/{agent_id}

# Граф отношений
WS /ws/relationships
```

#### 5. Координация с ML-сервисом
```python
class MLServiceClient:
    """Клиент для общения с ML-сервисом"""
    
    async def initialize_agent(self, agent_data):
        """Инициализировать агента в ML"""
        
    async def send_event(self, event):
        """Отправить событие на обработку"""
        
    async def get_agent_state(self, agent_id):
        """Получить состояние агента из ML"""
        
    async def request_memory_summary(self, agent_id):
        """Запросить компрессию памяти"""
```

---

### ML-Service (Machine Learning)

**Технологии:** FastAPI, ChromaDB, OpenAI/Gemini/YandexGPT API, sentence-transformers

**Ответственность:**

#### 1. Когнитивное ядро агента
```python
class CognitiveAgent:
    def __init__(self, agent_id, personality, initial_mood):
        self.agent_id = agent_id
        self.personality = personality
        self.mood = initial_mood
        self.memory_engine = MemoryEngine(agent_id)
        self.social_model = SocialModel(agent_id)
        self.llm_client = LLMClient()
        
    async def process_event(self, event):
        """Обработать входящее событие"""
        # 1. Обновить эмоции
        self.update_emotions(event)
        
        # 2. Обновить отношения
        self.update_relationships(event)
        
        # 3. Сохранить в память
        await self.memory_engine.store(event)
        
        # 4. Извлечь релевантные воспоминания
        memories = await self.memory_engine.retrieve(event)
        
        # 5. Отправить в LLM
        action = await self.llm_client.plan_action(
            personality=self.personality,
            mood=self.mood,
            relationships=self.social_model.get_state(),
            memories=memories,
            event=event
        )
        
        return action
```

#### 2. Memory Engine
```python
class MemoryEngine:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.chroma_client = ChromaDB()
        self.collection = f"agent_{agent_id}_memories"
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
    async def store(self, event):
        """Сохранить событие в память"""
        # Создать эпизод памяти
        memory = {
            "event": event,
            "reflection": await self.generate_reflection(event),
            "emotion": self.current_emotion,
            "social": self.social_snapshot,
            "importance": self.calculate_importance(event),
            "timestamp": time.time()
        }
        
        # Векторизовать
        text = self.format_for_embedding(memory)
        embedding = self.embedder.encode(text)
        
        # Сохранить в ChromaDB
        self.chroma_client.add(
            collection=self.collection,
            embeddings=[embedding],
            metadatas=[memory],
            ids=[f"mem_{uuid.uuid4()}"]
        )
        
    async def retrieve(self, query_context, top_k=5):
        """Извлечь релевантные воспоминания"""
        query_text = self.format_query(query_context)
        query_embedding = self.embedder.encode(query_text)
        
        results = self.chroma_client.query(
            collection=self.collection,
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Фильтровать по важности
        memories = self.filter_by_importance(results)
        
        return memories
        
    async def compress_old_memories(self):
        """Компрессия старых воспоминаний"""
        old_memories = self.get_old_memories(days=7)
        
        # Отправить в LLM для summary
        summary = await self.llm_client.summarize(old_memories)
        
        # Удалить старые
        self.delete_memories(old_memories)
        
        # Сохранить сжатое
        await self.store_summary(summary)
```

#### 3. Social Model
```python
class SocialModel:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.relationships = {}  # {agent_id: value}
        
    def update_relationship(self, other_agent_id, event):
        """Обновить отношение на основе события"""
        current = self.relationships.get(other_agent_id, 0.0)
        
        # Рассчитать изменение
        delta = self.calculate_relationship_change(event)
        
        # Обновить с decay
        new_value = self.apply_decay(current) + delta
        new_value = max(-1.0, min(1.0, new_value))
        
        self.relationships[other_agent_id] = new_value
        
    def calculate_relationship_change(self, event):
        """Рассчитать изменение отношения"""
        if event.type == "compliment":
            return 0.1
        elif event.type == "insult":
            return -0.15
        elif event.type == "help":
            return 0.2
        elif event.type == "conflict":
            return -0.25
        else:
            return 0.0
            
    def get_relationship_type(self, value):
        """Определить тип отношения"""
        if value > 0.6:
            return "close_friend"
        elif value > 0.3:
            return "friend"
        elif value > -0.3:
            return "acquaintance"
        elif value > -0.6:
            return "rival"
        else:
            return "enemy"
```

#### 4. LLM Client
```python
class LLMClient:
    def __init__(self):
        self.provider = "openai"  # or "gemini" or "yandex"
        self.model = "gpt-4"
        
    async def plan_action(self, personality, mood, relationships, 
                          memories, event):
        """Получить план действий от LLM"""
        
        system_prompt = self.build_system_prompt(personality)
        user_prompt = self.build_user_prompt(
            mood, relationships, memories, event
        )
        
        response = await self.call_llm(system_prompt, user_prompt)
        
        # Парсинг JSON
        action = self.parse_response(response)
        
        return action
        
    def build_system_prompt(self, personality):
        """Построить system prompt для агента"""
        return f"""
You are {personality.name}, a {personality.age}-year-old person with the following traits:
- Personality type: {personality.type}
- Interests: {', '.join(personality.interests)}
- Character: {personality.description}

You must respond in character and return your action in JSON format:
{{
    "action": {{
        "type": "message" | "think" | "activity",
        "target": "agent_id or null",
        "content": "your message or thought",
        "emotion": "happy|sad|angry|excited|neutral"
    }},
    "internal_thought": "your reasoning"
}}
"""
        
    def build_user_prompt(self, mood, relationships, memories, event):
        """Построить user prompt с контекстом"""
        return f"""
Current mood:
- Happiness: {mood.happiness}
- Energy: {mood.energy}
- Sociability: {mood.sociability}

Relationships:
{self.format_relationships(relationships)}

Relevant memories:
{self.format_memories(memories)}

Current event:
{self.format_event(event)}

How do you respond?
"""
```

#### 5. API эндпоинты ML-сервиса
```python
# Инициализация агента
POST /ml/agent/initialize
{
  "agent_id": "...",
  "personality": {...},
  "initial_mood": {...}
}

# Обработка события
POST /ml/agent/process
{
  "agent_id": "...",
  "event": {...}
}

# Получение состояния агента
GET /ml/agent/{agent_id}/state

# Получение воспоминаний
GET /ml/agent/{agent_id}/memories?query=...

# Компрессия памяти
POST /ml/agent/{agent_id}/compress

# Health check
GET /ml/health
```

---

## 📦 Формат данных агента (полная схема)

### При создании агента (Frontend input)

```json
{
  "name": "Алиса",
  "avatar_url": "https://storage.example.com/avatars/alice.png",
  "personality_type": "ENFP",
  "age": 25,
  "interests": [
    "музыка",
    "искусство", 
    "путешествия",
    "фотография"
  ],
  "additional_traits": "Оптимистична, любит помогать людям, немного импульсивна. Мечтает стать художником. Боится одиночества. Ценит честность в отношениях."
}
```

### Хранение в PostgreSQL (ai-agent-service)

```sql
CREATE TABLE agents (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    avatar_url TEXT,
    personality_type VARCHAR(10),
    age INTEGER,
    interests TEXT[],
    additional_traits TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE agent_states (
    id SERIAL PRIMARY KEY,
    agent_id UUID REFERENCES agents(agent_id),
    tick INTEGER,
    mood_happiness FLOAT,
    mood_energy FLOAT,
    mood_sociability FLOAT,
    dominant_emotion VARCHAR(50),
    last_action TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE relationships (
    id SERIAL PRIMARY KEY,
    agent1_id UUID REFERENCES agents(agent_id),
    agent2_id UUID REFERENCES agents(agent_id),
    relationship_value FLOAT,
    relationship_type VARCHAR(50),
    interaction_count INTEGER DEFAULT 0,
    last_interaction TIMESTAMP,
    UNIQUE(agent1_id, agent2_id)
);

CREATE TABLE simulation_events (
    id SERIAL PRIMARY KEY,
    simulation_id VARCHAR(100),
    tick INTEGER,
    event_type VARCHAR(50),
    agent_id UUID REFERENCES agents(agent_id),
    event_data JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

### В ML-сервисе (внутреннее представление)

```python
@dataclass
class AgentPersonality:
    name: str
    type: str  # MBTI
    age: int
    interests: List[str]
    traits: Dict[str, float]  # Big Five
    description: str
    
@dataclass
class AgentMood:
    happiness: float  # -1.0 to 1.0
    energy: float
    sociability: float
    dominant_emotion: str
    
@dataclass
class Memory:
    event: Dict
    reflection: str
    emotion: Dict
    social_context: Dict
    importance: float
    timestamp: float
    
@dataclass
class Relationship:
    agent_id: str
    value: float  # -1.0 to 1.0
    relationship_type: str
    history: List[Dict]
```

---

## 🔄 Последовательность взаимодействия (полный flow)

### Сценарий: Пользователь отправляет сообщение агенту

```
┌──────────┐         ┌──────────────────┐         ┌─────────────┐
│ Frontend │         │ ai-agent-service │         │ ml-service  │
└────┬─────┘         └────────┬─────────┘         └──────┬──────┘
     │                        │                          │
     │ 1. POST /api/interaction/message                  │
     │ {"target": "agent_001", "content": "Привет!"}    │
     ├───────────────────────>│                          │
     │                        │                          │
     │                        │ 2. Валидация запроса     │
     │                        │ Сохранение в БД          │
     │                        │                          │
     │                        │ 3. POST /ml/agent/process│
     │                        │ {event: {...}}           │
     │                        ├─────────────────────────>│
     │                        │                          │
     │                        │                          │ 4. Обработка:
     │                        │                          │ - Update emotions
     │                        │                          │ - Update relationships
     │                        │                          │ - Store memory
     │                        │                          │ - Retrieve memories
     │                        │                          │ - Call LLM
     │                        │                          │
     │                        │ 5. Response {action: ...}│
     │                        │<─────────────────────────┤
     │                        │                          │
     │ 6. WebSocket broadcast │                          │
     │ {event: "new_message"}│                          │
     │<───────────────────────┤                          │
     │                        │                          │
     │ 7. GET /api/agent/agent_001/state                 │
     ├───────────────────────>│                          │
     │                        │                          │
     │ 8. Response with full state                       │
     │<───────────────────────┤                          │
     │                        │                          │
```

---

## ⚙️ Конфигурация и переменные окружения

### ai-agent-service (.env)

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/agents_db
REDIS_URL=redis://localhost:6379

# ML Service
ML_SERVICE_URL=http://localhost:8001

# WebSocket
WS_HEARTBEAT_INTERVAL=30

# Simulation
DEFAULT_TICK_DURATION=1.0
MAX_TIME_MULTIPLIER=10.0
MIN_TIME_MULTIPLIER=0.1
```

### ml-service (.env)

```bash
# LLM Provider
LLM_PROVIDER=openai  # openai | gemini | yandex
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
YANDEX_API_KEY=...

# Model
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=500

# Vector DB
CHROMA_PERSIST_DIR=./chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Memory
MAX_MEMORIES_PER_AGENT=1000
MEMORY_COMPRESSION_THRESHOLD=800
MEMORY_IMPORTANCE_THRESHOLD=0.3

# Performance
MAX_CONCURRENT_LLM_CALLS=5
LLM_COOLDOWN_SECONDS=2.0
```

---

## 🚀 MVP Checklist для хакатона

### День 1: Инфраструктура
- [ ] Поднять ai-agent-service (FastAPI)
- [ ] Поднять ml-service (FastAPI)
- [ ] Настроить PostgreSQL
- [ ] Настроить ChromaDB
- [ ] Реализовать CRUD агентов
- [ ] Реализовать базовое общение между сервисами

### День 2: Когнитивное ядро
- [ ] Реализовать Memory Engine
- [ ] Интегрировать LLM (OpenAI/Gemini)
- [ ] Реализовать Social Model
- [ ] Реализовать Emotion System
- [ ] Реализовать контроллер скорости симуляции

### День 3: Интеграция и интерфейс
- [ ] WebSocket для real-time событий
- [ ] API для графа отношений
- [ ] API для ленты событий
- [ ] Тестирование с фронтендом
- [ ] Подготовка презентации

---

## 📈 Метрики для демонстрации

### Что показать жюри:

1. **Функциональность:** Несколько агентов общаются друг с другом, их отношения меняются
2. **Память:** Агент вспоминает прошлые события (показать через инспектор агента)
3. **Эмоции:** Настроение меняется в реальном времени (видно на графе)
4. **Скорость:** Демонстрация слайдера скорости симуляции
5. **Граф отношений:** Интерактивный граф с цветными связями

---

## 🎨 Рекомендации по презентации

### Структура защиты (10 минут):

1. **Проблема** (1 мин): Зачем нужны AI-агенты с памятью и эмоциями?
2. **Решение** (2 мин): Когнитивная архитектура агента
3. **Демонстрация** (5 мин): 
   - Создать агента
   - Показать общение
   - Показать изменение отношений
   - Показать память
   - Управление скоростью
4. **Технологии** (1 мин): Стек и архитектура
5. **Выводы** (1 мин): Что получилось

### Ключевые тезисы:

> "Мы создали систему, где агенты не просто генерируют текст, а демонстрируют последовательное социальное поведение во времени."

> "Каждый агент имеет эпизодическую память, которая влияет на его решения."

> "Отношения между агентами формируются динамически на основе их взаимодействий."

---

## 🔧 Технические детали для команды

### Что нужно от фронтенда:

1. UI для создания агента (форма с полями)
2. Дашборд с лентой событий (WebSocket подключение)
3. Граф отношений (D3.js)
4. Инспектор агента (модальное окно)
5. Панель управления (слайдер скорости, кнопки событий)

### Что нужно от бэкенда (ai-agent-service):

1. REST API для CRUD агентов
2. REST API для управления симуляцией
3. WebSocket сервер для real-time событий
4. Координация с ML-сервисом
5. Сохранение истории в PostgreSQL

### Что нужно от ML (ml-service):

1. Когнитивное ядро агента
2. Memory Engine с векторным поиском
3. Social Model
4. Интеграция с LLM
5. API для обработки событий

---

**Готово к старту! 🚀**
