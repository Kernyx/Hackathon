"""
Типы личности и Big Five: PersonalityType, BigFiveTraits.
"""

from dataclasses import dataclass
from enum import Enum


class PersonalityType(Enum):
    ALTRUIST = "Альтруист (добрый)"
    MACHIAVELLIAN = "Макиавеллист (злой)"
    REBEL = "Бунтарь (непредсказуемый)"
    STOIC = "Стоик (хладнокровный)"
    INDIVIDUAL = "Индивидуальный (пользовательский)"


@dataclass
class BigFiveTraits:
    openness: int = 50
    conscientiousness: int = 50
    extraversion: int = 50
    agreeableness: int = 50
    neuroticism: int = 50

    def to_description(self) -> str:
        traits = []
        if self.openness > 70:
            traits.append("очень открыт новому опыту и идеям")
        elif self.openness < 30:
            traits.append("предпочитает проверенные методы")
        if self.conscientiousness > 70:
            traits.append("организован и дисциплинирован")
        elif self.conscientiousness < 30:
            traits.append("спонтанен и гибок")
        if self.extraversion > 70:
            traits.append("энергичен и общителен")
        elif self.extraversion < 30:
            traits.append("сдержан и задумчив")
        if self.agreeableness > 70:
            traits.append("дружелюбен и готов помочь")
        elif self.agreeableness < 15:
            traits.append("агрессивен, враждебен, постоянно ищет конфликт и ругается со всеми")
        elif self.agreeableness < 30:
            traits.append("критичен и независим")
        if self.neuroticism > 80:
            traits.append("крайне раздражителен, вспыльчив, легко выходит из себя")
        elif self.neuroticism > 70:
            traits.append("эмоционален и чувствителен")
        elif self.neuroticism < 30:
            traits.append("спокоен и стабилен")
        return ", ".join(traits) if traits else "сбалансированная личность"

    @staticmethod
    def from_personality_type(ptype: 'PersonalityType') -> 'BigFiveTraits':
        profiles = {
            PersonalityType.ALTRUIST: BigFiveTraits(
                openness=70, conscientiousness=60, extraversion=65,
                agreeableness=85, neuroticism=35
            ),
            PersonalityType.MACHIAVELLIAN: BigFiveTraits(
                openness=55, conscientiousness=70, extraversion=75,
                agreeableness=10, neuroticism=85
            ),
            PersonalityType.REBEL: BigFiveTraits(
                openness=85, conscientiousness=30, extraversion=60,
                agreeableness=40, neuroticism=65
            ),
            PersonalityType.STOIC: BigFiveTraits(
                openness=45, conscientiousness=75, extraversion=30,
                agreeableness=50, neuroticism=20
            ),
            PersonalityType.INDIVIDUAL: BigFiveTraits(),
        }
        return profiles.get(ptype, BigFiveTraits())
