# Структура AI-агента и механика общительности
## Система "Большой брат" (BigBrother Orchestrator)

---

## 🎭 Полная структура агента

### 1. Входные данные от API (Frontend → Backend)

```json
{
  "username": "Алекс",
  "photo": "iVBORw0KGgoAAAANSUhEUgAA...",  // base64 encoded image
  "isMale": true,
  "age": 25,
  "interests": "Ездить по ночам на питбайке, слушать рок-музыку, программировать",
  "personalityType": "REBEL",  // ALTRUIST | MACHIAVELLIAN | REBEL | STOIC | INDIVIDUAL
  "additionalInformation": "Любит яблоки, не любит рано вставать, мечтает о мотоцикле Harley-Davidson"
}
```

---

### 2. Внутреннее представление агента (в ML-сервисе)

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import time
import uuid

class PersonalityType(Enum):
    """Типы личности агента"""
    ALTRUIST = "Альтруист"           # Добрый, помогающий
    MACHIAVELLIAN = "Макиавеллист"   # Хитрый, манипулятор
    REBEL = "Бунтарь"                # Непредсказуемый, бунтующий
    STOIC = "Стоик"                  # Хладнокровный, сдержанный
    INDIVIDUAL = "Индивидуальный"    # Кастомный


@dataclass
class AgentTraits:
    """Черты характера по модели Big Five"""
    openness: float           # 0.0 - 1.0: Открытость новому
    conscientiousness: float  # 0.0 - 1.0: Организованность
    extraversion: float       # 0.0 - 1.0: Экстраверсия/общительность
    agreeableness: float      # 0.0 - 1.0: Доброжелательность
    neuroticism: float        # 0.0 - 1.0: Эмоциональная нестабильность


@dataclass
class AgentMood:
    """Эмоциональное состояние агента"""
    happiness: float      # -1.0 to 1.0
    energy: float         # 0.0 to 1.0
    stress: float         # 0.0 to 1.0
    dominant_emotion: str # "happy", "sad", "angry", "excited", "neutral", etc.


@dataclass
class TalkativenessState:
    """
    Состояние общительности агента.
    
    Это КЛЮЧЕВОЙ параметр для системы "Большой брат".
    Определяет вероятность того, что агент захочет заговорить.
    """
    
    # Текущее желание говорить (0.0 - 1.0)
    current_desire: float = 0.5
    
    # Базовая общительность (зависит от extraversion)
    base_talkativeness: float = 0.5
    
    # Скорость восстановления (как быстро растёт желание говорить)
    recovery_rate: float = 0.1
    
    # Скорость истощения (как сильно падает после разговора)
    depletion_rate: float = 0.3
    
    # Минимальное значение (даже самый молчаливый может заговорить)
    min_desire: float = 0.05
    
    # Максимальное значение
    max_desire: float = 1.0
    
    # Тики с момента последнего высказывания
    ticks_since_last_speech: int = 0
    
    # Счётчик высказываний за последние N тиков
    recent_speech_count: int = 0


@dataclass
class Agent:
    """Полная структура AI-агента"""
    
    # === ИДЕНТИФИКАЦИЯ ===
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = "Unnamed"
    
    # === ВНЕШНОСТЬ ===
    photo_base64: Optional[str] = None
    is_male: bool = True
    age: int = 25
    
    # === ЛИЧНОСТЬ ===
    personality_type: PersonalityType = PersonalityType.INDIVIDUAL
    traits: AgentTraits = field(default_factory=lambda: AgentTraits(
        openness=0.5,
        conscientiousness=0.5,
        extraversion=0.5,
        agreeableness=0.5,
        neuroticism=0.5
    ))
    interests: str = ""
    additional_information: str = ""
    
    # === ЭМОЦИОНАЛЬНОЕ СОСТОЯНИЕ ===
    mood: AgentMood = field(default_factory=lambda: AgentMood(
        happiness=0.0,
        energy=0.7,
        stress=0.3,
        dominant_emotion="neutral"
    ))
    
    # === ОБЩИТЕЛЬНОСТЬ (НОВАЯ МЕХАНИКА) ===
    talkativeness: TalkativenessState = field(default_factory=TalkativenessState)
    
    # === СОЦИАЛЬНЫЕ СВЯЗИ ===
    relationships: Dict[str, float] = field(default_factory=dict)  # {agent_id: value}
    
    # === ПАМЯТЬ ===
    memory_collection_id: str = ""  # ID коллекции в ChromaDB
    
    # === МЕТАДАННЫЕ ===
    created_at: float = field(default_factory=time.time)
    last_action_time: float = field(default_factory=time.time)
    is_active: bool = True
    
    def __post_init__(self):
        """Инициализация после создания"""
        # Установить параметры общительности на основе extraversion
        self._initialize_talkativeness()
        
        # Установить начальные traits на основе типа личности
        if self.personality_type != PersonalityType.INDIVIDUAL:
            self._apply_personality_preset()
    
    def _initialize_talkativeness(self):
        """Инициализировать параметры общительности на основе extraversion"""
        ext = self.traits.extraversion
        
        # Базовая общительность = extraversion
        self.talkativeness.base_talkativeness = ext
        
        # Экстраверты быстрее восстанавливают желание говорить
        self.talkativeness.recovery_rate = 0.05 + (ext * 0.15)  # 0.05 - 0.20
        
        # Экстраверты медленнее истощаются
        self.talkativeness.depletion_rate = 0.4 - (ext * 0.2)  # 0.2 - 0.4
        
        # Стартовое желание = базовая общительность
        self.talkativeness.current_desire = self.talkativeness.base_talkativeness
    
    def _apply_personality_preset(self):
        """Применить пресет характеристик на основе типа личности"""
        presets = {
            PersonalityType.ALTRUIST: AgentTraits(
                openness=0.7,
                conscientiousness=0.8,
                extraversion=0.7,
                agreeableness=0.9,
                neuroticism=0.3
            ),
            PersonalityType.MACHIAVELLIAN: AgentTraits(
                openness=0.8,
                conscientiousness=0.5,
                extraversion=0.6,
                agreeableness=0.2,
                neuroticism=0.4
            ),
            PersonalityType.REBEL: AgentTraits(
                openness=0.9,
                conscientiousness=0.3,
                extraversion=0.8,
                agreeableness=0.4,
                neuroticism=0.6
            ),
            PersonalityType.STOIC: AgentTraits(
                openness=0.4,
                conscientiousness=0.9,
                extraversion=0.3,
                agreeableness=0.6,
                neuroticism=0.2
            )
        }
        
        if self.personality_type in presets:
            self.traits = presets[self.personality_type]
            # Пересчитать параметры общительности
            self._initialize_talkativeness()
```

---

## 🎮 Механика общительности (Talkativeness System)

### Концепция

**Идея:** Каждый агент имеет "желание говорить" (talkativeness desire), которое:
- **Растёт**, когда агент молчит (накапливается желание высказаться)
- **Падает**, когда агент говорит (истощается от разговора)
- **Определяет вероятность** того, что именно этот агент заговорит

### Формулы расчёта

```python
class TalkativenessManager:
    """Управление системой общительности"""
    
    @staticmethod
    def update_after_silence(agent: Agent) -> float:
        """
        Обновить желание говорить когда агент молчал.
        
        Формула:
        current_desire = min(
            current_desire + (recovery_rate * extraversion_bonus),
            max_desire
        )
        """
        t = agent.talkativeness
        
        # Бонус от экстраверсии (1.0 - 2.0)
        extraversion_bonus = 1.0 + agent.traits.extraversion
        
        # Увеличить желание говорить
        increment = t.recovery_rate * extraversion_bonus
        t.current_desire = min(
            t.current_desire + increment,
            t.max_desire
        )
        
        # Увеличить счётчик молчания
        t.ticks_since_last_speech += 1
        
        return t.current_desire
    
    @staticmethod
    def update_after_speech(agent: Agent) -> float:
        """
        Обновить желание говорить после того как агент высказался.
        
        Формула:
        current_desire = max(
            current_desire - (depletion_rate * introversion_penalty),
            min_desire
        )
        """
        t = agent.talkativeness
        
        # Штраф для интровертов (1.0 - 2.0)
        introversion_penalty = 2.0 - agent.traits.extraversion
        
        # Уменьшить желание говорить
        decrement = t.depletion_rate * introversion_penalty
        t.current_desire = max(
            t.current_desire - decrement,
            t.min_desire
        )
        
        # Сбросить счётчик молчания
        t.ticks_since_last_speech = 0
        t.recent_speech_count += 1
        
        return t.current_desire
    
    @staticmethod
    def calculate_speak_probability(agent: Agent, context: Dict) -> float:
        """
        Рассчитать вероятность того, что агент захочет заговорить.
        
        Учитывает:
        - Текущее желание говорить
        - Настроение агента
        - Контекст разговора
        - Отношения с другими агентами в разговоре
        
        Returns:
            float: Вероятность от 0.0 до 1.0
        """
        t = agent.talkativeness
        
        # Базовая вероятность = текущее желание
        base_prob = t.current_desire
        
        # Модификатор настроения
        mood_modifier = 1.0
        if agent.mood.dominant_emotion == "happy":
            mood_modifier = 1.2
        elif agent.mood.dominant_emotion == "excited":
            mood_modifier = 1.3
        elif agent.mood.dominant_emotion == "sad":
            mood_modifier = 0.7
        elif agent.mood.dominant_emotion == "angry":
            mood_modifier = 1.4  # Злость может заставить говорить
        
        # Модификатор энергии
        energy_modifier = 0.5 + (agent.mood.energy * 0.5)  # 0.5 - 1.0
        
        # Модификатор социального контекста
        social_modifier = 1.0
        if "mentioned_agent_ids" in context:
            # Если агента упомянули, он более вероятно ответит
            if agent.agent_id in context["mentioned_agent_ids"]:
                social_modifier = 1.5
        
        if "active_speaker_id" in context:
            # Отношение к говорящему влияет на желание ответить
            speaker_id = context["active_speaker_id"]
            relationship = agent.relationships.get(speaker_id, 0.0)
            
            # Положительные отношения -> выше вероятность ответа
            # Отрицательные отношения -> может захотеть поспорить
            if relationship > 0.5:
                social_modifier *= 1.3
            elif relationship < -0.3:
                social_modifier *= 1.2  # Хочет поспорить
        
        # Итоговая вероятность
        probability = base_prob * mood_modifier * energy_modifier * social_modifier
        
        # Ограничить диапазон
        probability = max(t.min_desire, min(1.0, probability))
        
        return probability
    
    @staticmethod
    def apply_fatigue(agent: Agent):
        """
        Применить усталость если агент говорил слишком много.
        
        Снижает recovery_rate и увеличивает depletion_rate.
        """
        t = agent.talkativeness
        
        # Если агент говорил более 3 раз за последние 10 тиков
        if t.recent_speech_count > 3:
            t.recovery_rate *= 0.8  # Восстанавливается медленнее
            t.depletion_rate *= 1.2  # Истощается быстрее
    
    @staticmethod
    def reset_fatigue(agent: Agent):
        """Сбросить усталость (вызывается периодически)"""
        agent.talkativeness.recent_speech_count = 0
        agent._initialize_talkativeness()  # Восстановить базовые значения
```

---

## 🧠 Класс "Большой брат" (BigBrother Orchestrator)

### Концепция

**BigBrother** — это центральный оркестратор, который:
1. Управляет всеми агентами в симуляции
2. Решает, кто из агентов должен говорить в данный момент
3. Обновляет состояние общительности всех агентов
4. Контролирует flow разговора
5. Предотвращает монополизацию разговора

```python
import random
import asyncio
from typing import List, Optional, Dict, Any
from collections import deque

class BigBrotherOrchestrator:
    """
    Центральный оркестратор симуляции агентов.
    
    Управляет:
    - Очерёдностью разговоров
    - Обновлением общительности
    - Выбором следующего говорящего
    - Балансировкой участия
    """
    
    def __init__(self, agents: List[Agent]):
        self.agents = {agent.agent_id: agent for agent in agents}
        self.talkativeness_manager = TalkativenessManager()
        
        # История разговоров
        self.conversation_history = deque(maxlen=100)
        
        # Текущий контекст
        self.current_context = {
            "active_speaker_id": None,
            "mentioned_agent_ids": set(),
            "topic": None,
            "tick": 0
        }
        
        # Статистика
        self.stats = {agent_id: {"speak_count": 0} for agent_id in self.agents}
    
    def update_tick(self):
        """Обновить тик симуляции"""
        self.current_context["tick"] += 1
        
        # Периодически сбрасывать усталость (каждые 50 тиков)
        if self.current_context["tick"] % 50 == 0:
            for agent in self.agents.values():
                self.talkativeness_manager.reset_fatigue(agent)
    
    def select_next_speaker(self, 
                           exclude_ids: Optional[List[str]] = None) -> Optional[str]:
        """
        Выбрать следующего говорящего на основе вероятностей.
        
        Args:
            exclude_ids: Агенты, которые не могут говорить (например, только что говорили)
        
        Returns:
            agent_id следующего говорящего или None если никто не хочет говорить
        """
        exclude_ids = exclude_ids or []
        
        # Получить кандидатов
        candidates = [
            agent for agent_id, agent in self.agents.items()
            if agent_id not in exclude_ids and agent.is_active
        ]
        
        if not candidates:
            return None
        
        # Рассчитать вероятности для каждого кандидата
        probabilities = []
        for agent in candidates:
            prob = self.talkativeness_manager.calculate_speak_probability(
                agent, self.current_context
            )
            probabilities.append((agent.agent_id, prob))
        
        # Нормализовать вероятности
        total_prob = sum(p for _, p in probabilities)
        if total_prob == 0:
            # Никто не хочет говорить - принудительно выбрать случайного
            return random.choice(candidates).agent_id
        
        normalized_probs = [(aid, p/total_prob) for aid, p in probabilities]
        
        # Взвешенный случайный выбор
        agent_ids, probs = zip(*normalized_probs)
        selected_id = random.choices(agent_ids, weights=probs, k=1)[0]
        
        return selected_id
    
    def update_talkativeness_after_speech(self, speaker_id: str):
        """
        Обновить общительность всех агентов после того как кто-то высказался.
        
        - У говорящего: уменьшить желание
        - У остальных: увеличить желание
        """
        for agent_id, agent in self.agents.items():
            if agent_id == speaker_id:
                # Говорящий истощается
                self.talkativeness_manager.update_after_speech(agent)
                self.stats[agent_id]["speak_count"] += 1
            else:
                # Остальные набираются желания говорить
                self.talkativeness_manager.update_after_silence(agent)
        
        # Применить усталость если нужно
        speaker = self.agents[speaker_id]
        self.talkativeness_manager.apply_fatigue(speaker)
    
    def update_context(self, event: Dict[str, Any]):
        """
        Обновить контекст разговора на основе события.
        
        Парсит упоминания агентов, темы разговора и т.д.
        """
        if event.get("type") == "agent_message":
            self.current_context["active_speaker_id"] = event["sender_agent_id"]
            
            # Поиск упоминаний агентов в сообщении
            content = event.get("content", "")
            mentioned_ids = self._extract_mentioned_agents(content)
            self.current_context["mentioned_agent_ids"] = mentioned_ids
    
    def _extract_mentioned_agents(self, text: str) -> set:
        """
        Извлечь ID агентов, упомянутых в тексте.
        
        Ищет имена агентов или прямые обращения.
        """
        mentioned = set()
        text_lower = text.lower()
        
        for agent_id, agent in self.agents.items():
            if agent.username.lower() in text_lower:
                mentioned.add(agent_id)
        
        return mentioned
    
    def prevent_monopolization(self, speaker_id: str) -> bool:
        """
        Проверить, не монополизирует ли агент разговор.
        
        Returns:
            True если агент может говорить, False если нужно дать слово другим
        """
        # Проверить последние N событий
        recent_speakers = [
            event["sender_agent_id"]
            for event in list(self.conversation_history)[-5:]
            if event.get("type") == "agent_message"
        ]
        
        # Если агент говорил > 60% последних сообщений
        if recent_speakers.count(speaker_id) / max(len(recent_speakers), 1) > 0.6:
            return False
        
        return True
    
    async def orchestrate_conversation_round(self) -> Optional[Dict]:
        """
        Провести один раунд разговора.
        
        Returns:
            Событие с ответом выбранного агента или None
        """
        # Обновить тик
        self.update_tick()
        
        # Выбрать следующего говорящего
        speaker_id = self.select_next_speaker()
        
        if not speaker_id:
            return None
        
        # Проверить монополизацию
        if not self.prevent_monopolization(speaker_id):
            # Выбрать другого говорящего
            speaker_id = self.select_next_speaker(exclude_ids=[speaker_id])
            if not speaker_id:
                return None
        
        speaker = self.agents[speaker_id]
        
        # Здесь происходит генерация ответа через LLM
        # (это будет делать ML-сервис)
        
        # Обновить общительность после высказывания
        self.update_talkativeness_after_speech(speaker_id)
        
        # Создать событие
        event = {
            "type": "agent_message",
            "sender_agent_id": speaker_id,
            "sender_username": speaker.username,
            "tick": self.current_context["tick"],
            "talkativeness_after": speaker.talkativeness.current_desire,
            "timestamp": time.time()
        }
        
        # Добавить в историю
        self.conversation_history.append(event)
        
        return event
    
    def get_talkativeness_status(self) -> Dict:
        """
        Получить текущий статус общительности всех агентов.
        
        Полезно для дашборда.
        """
        return {
            agent_id: {
                "username": agent.username,
                "current_desire": agent.talkativeness.current_desire,
                "base_talkativeness": agent.talkativeness.base_talkativeness,
                "extraversion": agent.talkativeness.extraversion,
                "ticks_since_speech": agent.talkativeness.ticks_since_last_speech,
                "speak_count": self.stats[agent_id]["speak_count"]
            }
            for agent_id, agent in self.agents.items()
        }
    
    def balance_participation(self):
        """
        Балансировка участия агентов.
        
        Если кто-то вообще не говорил, искусственно повысить его желание.
        """
        speak_counts = [self.stats[aid]["speak_count"] for aid in self.agents]
        avg_count = sum(speak_counts) / len(speak_counts)
        
        for agent_id, agent in self.agents.items():
            count = self.stats[agent_id]["speak_count"]
            
            # Если говорил меньше половины среднего
            if count < avg_count * 0.5:
                # Увеличить желание говорить
                agent.talkativeness.current_desire = min(
                    agent.talkativeness.current_desire + 0.2,
                    agent.talkativeness.max_desire
                )
```

---

## 🔄 Интеграция с симуляцией

### Основной цикл симуляции с BigBrother

```python
class SimulationEngine:
    """Основной движок симуляции"""
    
    def __init__(self):
        self.big_brother = None
        self.ml_service_client = MLServiceClient()
        self.is_running = False
        self.time_multiplier = 1.0
    
    async def initialize(self, agents: List[Agent]):
        """Инициализировать симуляцию с агентами"""
        self.big_brother = BigBrotherOrchestrator(agents)
        
        # Инициализировать каждого агента в ML-сервисе
        for agent in agents:
            await self.ml_service_client.initialize_agent(agent)
    
    async def run_simulation_loop(self):
        """Основной цикл симуляции"""
        self.is_running = True
        
        while self.is_running:
            tick_start = time.time()
            
            # ===== ШАГ 1: ВЫБРАТЬ ГОВОРЯЩЕГО =====
            event = await self.big_brother.orchestrate_conversation_round()
            
            if event:
                speaker_id = event["sender_agent_id"]
                speaker = self.big_brother.agents[speaker_id]
                
                # ===== ШАГ 2: ПОЛУЧИТЬ ОТВЕТ ОТ ML-СЕРВИСА =====
                response = await self.ml_service_client.generate_response(
                    agent_id=speaker_id,
                    context=self.big_brother.current_context,
                    conversation_history=list(self.big_brother.conversation_history)
                )
                
                # Добавить контент в событие
                event["content"] = response["content"]
                event["emotion"] = response["emotion"]
                
                # ===== ШАГ 3: ОБНОВИТЬ КОНТЕКСТ =====
                self.big_brother.update_context(event)
                
                # ===== ШАГ 4: BROADCAST СОБЫТИЕ =====
                await self.broadcast_event(event)
                
                # ===== ШАГ 5: ОБРАБОТАТЬ СОБЫТИЕ У ДРУГИХ АГЕНТОВ =====
                for agent_id, agent in self.big_brother.agents.items():
                    if agent_id != speaker_id:
                        # Другие агенты воспринимают сообщение
                        await self.ml_service_client.process_event(
                            agent_id=agent_id,
                            event=event
                        )
            
            # ===== ШАГ 6: ПЕРИОДИЧЕСКАЯ БАЛАНСИРОВКА =====
            if self.big_brother.current_context["tick"] % 20 == 0:
                self.big_brother.balance_participation()
            
            # Рассчитать задержку с учётом множителя скорости
            elapsed = time.time() - tick_start
            base_delay = 2.0  # 2 секунды между сообщениями
            adjusted_delay = base_delay / self.time_multiplier
            sleep_time = max(0, adjusted_delay - elapsed)
            
            await asyncio.sleep(sleep_time)
    
    async def broadcast_event(self, event: Dict):
        """Отправить событие всем подключённым клиентам через WebSocket"""
        # Это будет делать ai-agent-service
        pass
    
    def set_speed(self, multiplier: float):
        """Изменить скорость симуляции"""
        self.time_multiplier = max(0.1, min(10.0, multiplier))
```

---

## 📊 API для работы с общительностью

### Эндпоинты для дашборда

```python
# ai-agent-service endpoints

@app.get("/api/v1/ai-agent/talkativeness/status")
async def get_talkativeness_status():
    """
    Получить статус общительности всех агентов.
    
    Response:
    {
        "tick": 1523,
        "agents": [
            {
                "agent_id": "...",
                "username": "Алекс",
                "current_desire": 0.75,
                "probability": 0.68,
                "extraversion": 0.8,
                "ticks_since_speech": 15,
                "speak_count": 23
            },
            ...
        ]
    }
    """
    status = simulation_engine.big_brother.get_talkativeness_status()
    
    # Добавить вероятности
    for agent_id, data in status.items():
        agent = simulation_engine.big_brother.agents[agent_id]
        prob = simulation_engine.big_brother.talkativeness_manager.calculate_speak_probability(
            agent,
            simulation_engine.big_brother.current_context
        )
        data["probability"] = prob
    
    return {
        "tick": simulation_engine.big_brother.current_context["tick"],
        "agents": list(status.values())
    }

@app.post("/api/v1/ai-agent/force-speak/{agent_id}")
async def force_agent_to_speak(agent_id: str):
    """
    Принудительно заставить агента говорить.
    
    Полезно для тестирования или если пользователь хочет услышать конкретного агента.
    """
    agent = simulation_engine.big_brother.agents.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    
    # Временно повысить желание говорить
    agent.talkativeness.current_desire = 1.0
    
    return {"status": "success", "message": f"{agent.username} will speak soon"}
```

---

## 🎨 Визуализация для фронтенда

### Данные для компонента "Talkativeness Meter"

```typescript
interface TalkativenessData {
  agentId: string;
  username: string;
  avatarUrl: string;
  
  // Основные параметры
  currentDesire: number;        // 0.0 - 1.0
  probability: number;          // 0.0 - 1.0
  
  // Визуальные индикаторы
  desirePercentage: number;     // 0 - 100 для progress bar
  probabilityPercentage: number; // 0 - 100
  
  // Статус
  status: "silent" | "ready" | "speaking";
  ticksSinceSpeech: number;
  speakCount: number;
  
  // Характеристики
  extraversion: number;         // 0.0 - 1.0
  personalityType: string;
}
```

### Пример UI компонента

```jsx
// React компонент для отображения общительности

function TalkativenessPanel({ agents }) {
  return (
    <div className="talkativeness-panel">
      <h3>Желание говорить</h3>
      
      {agents.map(agent => (
        <div key={agent.agentId} className="agent-row">
          <img src={agent.avatarUrl} alt={agent.username} />
          <span className="username">{agent.username}</span>
          
          {/* Progress bar показывающий текущее желание */}
          <div className="desire-bar">
            <div 
              className="fill"
              style={{ width: `${agent.desirePercentage}%` }}
            />
          </div>
          
          {/* Вероятность высказаться */}
          <div className="probability">
            {Math.round(agent.probabilityPercentage)}%
          </div>
          
          {/* Статус */}
          <div className={`status ${agent.status}`}>
            {agent.status === "speaking" && "🗣️"}
            {agent.status === "ready" && "✅"}
            {agent.status === "silent" && "💭"}
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## 🔧 Тонкая настройка параметров

### Конфигурация для разных сценариев

```python
# Для БЫСТРОГО разговора (агенты активно общаются)
FAST_CONVERSATION_CONFIG = {
    "recovery_rate_multiplier": 1.5,
    "depletion_rate_multiplier": 0.7,
    "min_desire": 0.1,
    "base_delay": 1.0  # 1 секунда между сообщениями
}

# Для МЕДЛЕННОГО размеренного разговора
SLOW_CONVERSATION_CONFIG = {
    "recovery_rate_multiplier": 0.8,
    "depletion_rate_multiplier": 1.3,
    "min_desire": 0.05,
    "base_delay": 4.0  # 4 секунды между сообщениями
}

# Для СБАЛАНСИРОВАННОГО разговора
BALANCED_CONFIG = {
    "recovery_rate_multiplier": 1.0,
    "depletion_rate_multiplier": 1.0,
    "min_desire": 0.05,
    "base_delay": 2.0
}
```

---

## 📈 Метрики для анализа

### Что отслеживать

```python
class SimulationMetrics:
    """Метрики симуляции для анализа и отладки"""
    
    def __init__(self):
        self.metrics = {
            "participation_balance": 0.0,  # 0.0 - 1.0 (1.0 = идеально сбалансировано)
            "average_desire": 0.0,
            "conversation_flow_score": 0.0,
            "monopolization_events": 0,
            "silent_agents": []
        }
    
    def calculate_participation_balance(self, 
                                       speak_counts: Dict[str, int]) -> float:
        """
        Рассчитать баланс участия.
        
        1.0 = все говорят одинаково
        0.0 = один агент монополизирует
        """
        if not speak_counts:
            return 0.0
        
        counts = list(speak_counts.values())
        avg = sum(counts) / len(counts)
        
        if avg == 0:
            return 0.0
        
        # Рассчитать стандартное отклонение
        variance = sum((c - avg) ** 2 for c in counts) / len(counts)
        std_dev = variance ** 0.5
        
        # Нормализовать (меньше отклонение = лучше баланс)
        balance = 1.0 - min(std_dev / (avg + 1), 1.0)
        
        return balance
```

---

## 🚀 Итоговая картина интеграции

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND                             │
│  • Дашборд с Talkativeness Meter                        │
│  • Граф отношений                                       │
│  • Лента событий                                        │
│  • Слайдер скорости                                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ WebSocket + REST API
                 ↓
┌─────────────────────────────────────────────────────────┐
│              AI-AGENT-SERVICE                           │
│  • REST API для CRUD                                    │
│  • WebSocket сервер                                     │
│  • PostgreSQL (хранение агентов и событий)              │
│  • SimulationEngine                                     │
│    └─→ BigBrotherOrchestrator ⭐                        │
│         ├─→ Выбор следующего говорящего                │
│         ├─→ Обновление общительности                   │
│         ├─→ Балансировка участия                       │
│         └─→ Контроль монополизации                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ HTTP API
                 ↓
┌─────────────────────────────────────────────────────────┐
│                ML-SERVICE                               │
│  • CognitiveAgent (когнитивное ядро)                    │
│  • MemoryEngine (ChromaDB)                              │
│  • SocialModel (отношения)                              │
│  • LLMClient (OpenAI/Gemini/Yandex)                     │
│  • TalkativenessManager ⭐                              │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ Чек-лист реализации

### День 1: Структура данных
- [ ] Создать `Agent` dataclass с полями
- [ ] Создать `TalkativenessState` dataclass
- [ ] Реализовать `_initialize_talkativeness()`
- [ ] Реализовать пресеты типов личности
- [ ] Создать API endpoint для создания агента

### День 2: Механика общительности
- [ ] Реализовать `TalkativenessManager`
- [ ] Реализовать `update_after_silence()`
- [ ] Реализовать `update_after_speech()`
- [ ] Реализовать `calculate_speak_probability()`
- [ ] Добавить систему усталости

### День 3: BigBrother Orchestrator
- [ ] Создать `BigBrotherOrchestrator` класс
- [ ] Реализовать `select_next_speaker()`
- [ ] Реализовать `update_talkativeness_after_speech()`
- [ ] Реализовать `prevent_monopolization()`
- [ ] Интегрировать с `SimulationEngine`
- [ ] Добавить API эндпоинты для дашборда

---

**Готово к старту! 🎮**
