"""
Настроение агента: AgentMood.
"""

from dataclasses import dataclass

from config import (
    MOOD_DECAY_RATE, MOOD_EVENT_IMPACT, MOOD_INTERACTION_IMPACT,
    MOOD_EMOJIS, EVENT_MOOD_TRIGGERS,
)
from models.personality import PersonalityType, BigFiveTraits
from models.races import RaceModifiers


@dataclass
class AgentMood:
    """Эмоциональное состояние агента."""

    happiness: float = 0.0
    energy: float = 0.5
    stress: float = 0.2
    anger: float = 0.0
    fear: float = 0.0

    _baseline_happiness: float = 0.0
    _baseline_energy: float = 0.5
    _baseline_stress: float = 0.2
    _baseline_anger: float = 0.0
    _baseline_fear: float = 0.0
    _accumulated_trauma: float = 0.0

    @staticmethod
    def from_personality(ptype: 'PersonalityType', big_five: 'BigFiveTraits') -> 'AgentMood':
        """Создать начальное настроение на основе Big Five + типа личности."""
        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        base_happiness = (e * 0.25 + a * 0.15 + o * 0.1) - (n * 0.3)
        base_energy = 0.35 + e * 0.25 + o * 0.1 + c * 0.05
        base_stress = n * 0.4 - c * 0.15 - a * 0.05
        base_anger = n * 0.3 - a * 0.35
        base_fear = n * 0.2 - e * 0.1 - o * 0.05

        base_happiness = max(-0.8, min(0.8, base_happiness))
        base_energy = max(0.15, min(0.9, base_energy))
        base_stress = max(0.0, min(0.7, base_stress))
        base_anger = max(0.0, min(0.7, base_anger))
        base_fear = max(0.0, min(0.5, base_fear))

        mood = AgentMood(
            happiness=base_happiness, energy=base_energy,
            stress=base_stress, anger=base_anger, fear=base_fear,
            _baseline_happiness=base_happiness, _baseline_energy=base_energy,
            _baseline_stress=base_stress, _baseline_anger=base_anger,
            _baseline_fear=base_fear,
        )
        mood._clamp()
        return mood

    def _clamp(self):
        """Ограничить значения допустимыми диапазонами."""
        self.happiness = max(-1.0, min(1.0, self.happiness))
        self.energy = max(0.0, min(1.0, self.energy))
        self.stress = max(0.0, min(1.0, self.stress))
        self.anger = max(0.0, min(1.0, self.anger))
        self.fear = max(0.0, min(1.0, self.fear))

    def get_dominant_emotion(self) -> str:
        """Определить доминирующую эмоцию."""
        emotions = {
            'радость': self.happiness,
            'грусть': -self.happiness if self.happiness < -0.2 else -1,
            'злость': self.anger,
            'страх': self.fear,
            'тревога': self.stress,
            'усталость': 1.0 - self.energy if self.energy < 0.25 else -1,
            'воодушевление': (self.happiness + self.energy) / 2 if self.happiness > 0.3 and self.energy > 0.6 else -1,
            'раздражение': (self.anger + self.stress) / 2 if self.anger > 0.2 and self.stress > 0.3 else -1,
            'решимость': self.energy if self.energy > 0.6 and self.stress < 0.3 and self.fear < 0.2 else -1,
            'интерес': 0.3 if abs(self.happiness) < 0.2 and self.energy > 0.4 else -1,
        }
        dominant = max(emotions, key=emotions.get)
        if emotions[dominant] < 0.1:
            return 'нейтрально'
        return dominant

    def get_emoji(self) -> str:
        """Получить метку доминирующей эмоции."""
        return MOOD_EMOJIS.get(self.get_dominant_emotion(), '[--]')

    def to_description(self) -> str:
        """Текстовое описание настроения для промпта."""
        dominant = self.get_dominant_emotion()
        emoji = self.get_emoji()
        parts = [f"{emoji} Доминирующая эмоция: {dominant}"]

        if self.happiness > 0.4:
            parts.append("ты в ХОРОШЕМ настроении — шути, поддерживай, будь добрее обычного")
        elif self.happiness > 0.15:
            parts.append("настроение неплохое")
        elif self.happiness < -0.4:
            parts.append("ты ПОДАВЛЕН — говори тихо, коротко, грустно. Не шути. Можешь жаловаться")
        elif self.happiness < -0.15:
            parts.append("ты не в духе — раздражителен, пессимистичен")

        if self.fear > 0.5:
            parts.append(
                "ты НАПУГАН! ПАНИКА! Говори сбивчиво, торопливо. "
                "Проси о помощи. Предлагай спрятаться или убежать. "
                "НЕ РУГАЙСЯ — тебе не до этого, ты боишься!"
            )
        elif self.fear > 0.25:
            parts.append(
                "ты встревожен и напуган — говори осторожно, "
                "предупреждай об опасности, будь настороже. "
                "Агрессия СНИЖЕНА — страх подавляет злость"
            )

        if self.fear > 0.3 and self.anger > 0.3:
            parts.append(
                "СТРАХ сильнее ЗЛОСТИ — ты скорее нервничаешь, "
                "чем ругаешься. Можешь огрызнуться от страха, "
                "но НЕ оскорблять и НЕ скандалить"
            )
        elif self.anger > 0.6 and self.fear < 0.2:
            parts.append("ты В ЯРОСТИ — говори агрессивно, резко, можешь сорваться")
        elif self.anger > 0.35 and self.fear < 0.2:
            parts.append("ты раздражён — грубишь, споришь")
        elif self.anger > 0.15 and self.fear < 0.15:
            parts.append("ты слегка раздражён")

        if self.stress > 0.7:
            parts.append("ты под СИЛЬНЫМ стрессом — нервничаешь, суетишься, можешь сорваться")
        elif self.stress > 0.4:
            parts.append("ты напряжён — говоришь быстрее, нетерпеливо")

        if self.energy < 0.2:
            parts.append("ты УСТАЛ — говоришь мало, вяло, хочешь отдохнуть")
        elif self.energy < 0.35:
            parts.append("ты утомлён — не хватает сил на длинные речи")
        elif self.energy > 0.8:
            parts.append("ты полон энергии — активен и деятелен")

        return ". ".join(parts)

    def apply_event(self, event_text: str, personality_type: 'PersonalityType',
                    big_five: 'BigFiveTraits' = None, race_mods: 'RaceModifiers' = None):
        """Обновить настроение в ответ на событие."""
        if big_five is None:
            big_five = BigFiveTraits(neuroticism=50)

        event_lower = event_text.lower()

        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        sensitivity = 0.6 + n * 0.6 - c * 0.15
        sensitivity = max(0.4, min(1.3, sensitivity))
        curiosity = o * 0.4
        resilience = e * 0.25 + c * 0.15
        empathy = a * 0.3
        anger_dampening = a * 0.5

        effects_applied = False
        for category, data in EVENT_MOOD_TRIGGERS.items():
            keywords = data['keywords']
            effects = data['effects']
            if any(kw in event_lower for kw in keywords):
                impact = MOOD_EVENT_IMPACT * sensitivity

                d_happiness = effects['happiness'] * impact
                d_energy = effects['energy'] * impact
                d_stress = effects['stress'] * impact
                d_anger = effects['anger'] * impact
                d_fear = effects['fear'] * impact

                if d_fear > 0:
                    converted = d_fear * curiosity
                    d_fear -= converted
                    d_energy += converted * 0.5
                    d_happiness += converted * 0.3
                if d_stress > 0 and category == 'mystery':
                    d_stress *= (1.0 - curiosity)
                    d_energy += curiosity * 0.15

                if category == 'loss':
                    d_happiness -= c * 0.1
                    d_stress += c * 0.08
                elif category == 'danger':
                    d_stress *= (1.0 - c * 0.3)

                if d_happiness > 0:
                    d_happiness *= (1.0 + resilience)
                elif d_happiness < 0:
                    d_happiness *= (1.0 - resilience * 0.5)
                if d_energy < 0:
                    d_energy *= (1.0 - e * 0.3)

                if d_anger > 0:
                    d_anger *= (1.0 - anger_dampening)
                if category == 'positive':
                    d_happiness += empathy * 0.15
                    if d_stress < 0:
                        d_stress *= 0.6
                    if d_fear < 0:
                        d_fear *= 0.5
                elif category in ('danger', 'loss', 'sickness'):
                    d_stress += empathy * 0.1

                if d_happiness < 0:
                    d_happiness *= (1.0 + n * 0.3)
                if d_stress > 0:
                    d_stress *= (1.0 + n * 0.2)

                if race_mods:
                    d_happiness *= race_mods.happiness_mult
                    d_energy *= race_mods.energy_mult
                    d_stress *= race_mods.stress_mult
                    d_anger *= race_mods.anger_mult
                    d_fear *= race_mods.fear_mult

                self.happiness += d_happiness
                self.energy += d_energy
                self.stress += d_stress
                self.anger += d_anger
                self.fear += d_fear
                effects_applied = True

                if category in ('danger', 'sickness'):
                    min_fear = 0.10
                    min_stress = 0.12
                    if self.fear < min_fear:
                        self.fear = min_fear
                    if self.stress < min_stress:
                        self.stress = min_stress
                    if self.happiness > 0.15:
                        self.happiness = max(0.0, self.happiness - 0.10)

                break

        if not effects_applied:
            self.stress += 0.05 * sensitivity
            self.energy += 0.03 + o * 0.04
        else:
            if any(cat in ('danger', 'loss', 'sickness') for cat, data in EVENT_MOOD_TRIGGERS.items()
                   if any(kw in event_lower for kw in data['keywords'])):
                trauma_gain = 0.08 * sensitivity
                self._accumulated_trauma = min(1.0, self._accumulated_trauma + trauma_gain)
                self._baseline_stress = min(0.7, self._baseline_stress + 0.03 * sensitivity)
                self._baseline_fear = min(0.5, self._baseline_fear + 0.02 * sensitivity)
                self._baseline_happiness = max(-0.8, self._baseline_happiness - 0.02 * sensitivity)

        self._clamp()

    def apply_interaction(self, sentiment_delta: float, personality_type: 'PersonalityType',
                          big_five: 'BigFiveTraits' = None):
        """Обновить настроение от взаимодействия с другим агентом."""
        if big_five is None:
            big_five = BigFiveTraits(neuroticism=50)

        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        sensitivity = 0.6 + n * 0.5 + e * 0.15
        sensitivity = max(0.5, min(1.4, sensitivity))
        impact = MOOD_INTERACTION_IMPACT * sensitivity

        if sentiment_delta > 0:
            pos = sentiment_delta
            happiness_boost = pos * impact * (2.0 + e * 2.0)
            self.happiness += happiness_boost
            self.happiness += pos * impact * a * 1.5
            anger_reduction = pos * impact * (1.5 + a * 1.5)
            self.anger = max(0, self.anger - anger_reduction)
            stress_reduction = pos * impact * (0.8 + c * 0.5)
            self.stress = max(0, self.stress - stress_reduction)
            self.energy += pos * impact * (0.5 + e * 1.0)
            self.fear = max(0, self.fear - pos * impact * 0.5)
        else:
            neg = abs(sentiment_delta)
            happiness_loss = neg * impact * (1.5 + a * 1.0)
            self.happiness -= happiness_loss
            anger_gain = neg * impact * (3.0 - a * 2.5)
            anger_gain = max(0, anger_gain)
            self.anger += anger_gain
            stress_gain = neg * impact * (1.5 + n * 1.0 - c * 0.5)
            stress_gain = max(0, stress_gain)
            self.stress += stress_gain
            energy_loss = neg * impact * (0.5 - e * 0.3)
            energy_loss = max(0, energy_loss)
            self.energy -= energy_loss

        self.energy += o * 0.02
        self._clamp()

    def decay_toward_baseline(self, big_five: 'BigFiveTraits' = None):
        """Естественное затухание — настроение стремится к baseline."""
        if big_five is None:
            big_five = BigFiveTraits()

        o = big_five.openness / 100.0
        c = big_five.conscientiousness / 100.0
        e = big_five.extraversion / 100.0
        a = big_five.agreeableness / 100.0
        n = big_five.neuroticism / 100.0

        base_rate = MOOD_DECAY_RATE

        h_rate = base_rate * (1.0 + e * 0.3)
        self.happiness += (self._baseline_happiness - self.happiness) * h_rate

        e_rate = base_rate * (1.0 + c * 0.15)
        self.energy += (self._baseline_energy - self.energy) * e_rate

        def inertia(current: float, baseline: float) -> float:
            excess = max(0, current - baseline)
            return 1.0 - excess * 0.7

        trauma_slowdown = 1.0 - self._accumulated_trauma * 0.6
        trauma_slowdown = max(0.2, trauma_slowdown)

        s_rate = base_rate * (1.0 + c * 0.4 - n * 0.3) * trauma_slowdown
        s_rate *= inertia(self.stress, self._baseline_stress)
        s_rate = max(0.005, s_rate)
        self.stress += (self._baseline_stress - self.stress) * s_rate

        a_rate = base_rate * (1.0 + a * 0.5 - n * 0.3)
        a_rate *= inertia(self.anger, self._baseline_anger)
        a_rate = max(0.01, a_rate)
        self.anger += (self._baseline_anger - self.anger) * a_rate

        f_rate = base_rate * (1.0 + o * 0.4 - n * 0.25) * trauma_slowdown
        f_rate *= inertia(self.fear, self._baseline_fear)
        f_rate = max(0.005, f_rate)
        self.fear += (self._baseline_fear - self.fear) * f_rate

        self._accumulated_trauma = max(0.0, self._accumulated_trauma - 0.01 * c)

        if self.happiness < self._baseline_happiness:
            h_penalty = (self._baseline_happiness - self.happiness) * 0.5
            self.happiness -= h_penalty * 0.02

        self._clamp()

    def apply_speaking(self, big_five: 'BigFiveTraits' = None):
        """Корректировка после высказывания."""
        if big_five is None:
            big_five = BigFiveTraits()

        e = big_five.extraversion / 100.0
        n = big_five.neuroticism / 100.0
        a = big_five.agreeableness / 100.0

        energy_cost = 0.06 - e * 0.08
        self.energy -= energy_cost

        stress_relief = 0.01 + n * 0.03
        self.stress = max(0, self.stress - stress_relief)

        anger_relief = a * 0.02
        self.anger = max(0, self.anger - anger_relief)

        self._clamp()

    def get_talkativeness_modifier(self, big_five: 'BigFiveTraits' = None) -> float:
        """Модификатор желания говорить на основе настроения + Big Five."""
        if big_five is None:
            big_five = BigFiveTraits()

        e = big_five.extraversion / 100.0
        n = big_five.neuroticism / 100.0
        a = big_five.agreeableness / 100.0

        modifier = 1.0

        if self.happiness > 0.3:
            modifier += 0.1 + e * 0.15
        elif self.happiness < -0.3:
            modifier -= 0.1 + (1.0 - e) * 0.15

        if self.anger > 0.4:
            if a < 0.3:
                modifier += 0.25
            else:
                modifier -= 0.1

        if self.fear > 0.5:
            modifier += 0.1 + n * 0.1
        elif self.fear > 0.3:
            if e < 0.4:
                modifier -= 0.1

        if self.energy < 0.25:
            modifier -= 0.2 + (1.0 - e) * 0.1
        elif self.energy > 0.7:
            modifier += 0.05 + e * 0.1

        if self.stress > 0.6:
            modifier += 0.05 + n * 0.15

        return max(0.4, min(1.6, modifier))
