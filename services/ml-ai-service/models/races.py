"""
Расы: RaceType, RaceModifiers, Race, RACES.
"""

from dataclasses import dataclass
from enum import Enum


class RaceType(Enum):
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    ORC = "orc"
    GOBLIN = "goblin"


@dataclass
class RaceModifiers:
    """Модификаторы расы для характеристик агента."""
    openness: int = 0
    conscientiousness: int = 0
    extraversion: int = 0
    agreeableness: int = 0
    neuroticism: int = 0

    happiness_mult: float = 1.0
    energy_mult: float = 1.0
    stress_mult: float = 1.0
    anger_mult: float = 1.0
    fear_mult: float = 1.0

    repair_bonus: float = 0.0
    combat_bonus: float = 0.0
    diplomacy_bonus: float = 0.0
    detection_bonus: float = 0.0

    can_betray: bool = False
    flee_threshold: float = 1.0
    stubborn: bool = False


@dataclass
class Race:
    """Класс (раса) агента с модификаторами и отношениями."""
    race_type: RaceType
    name_ru: str
    emoji: str
    description: str
    modifiers: RaceModifiers
    racial_relations: dict


RACES: dict[RaceType, Race] = {
    RaceType.HUMAN: Race(
        race_type=RaceType.HUMAN,
        name_ru="Человек",
        emoji="[Чел]",
        description="Универсальный, адаптивный, дипломатичный",
        modifiers=RaceModifiers(diplomacy_bonus=0.20),
        racial_relations={
            RaceType.HUMAN: 0.10, RaceType.ELF: 0.05, RaceType.DWARF: 0.05,
            RaceType.ORC: 0.00, RaceType.GOBLIN: 0.00,
        }
    ),
    RaceType.ELF: Race(
        race_type=RaceType.ELF,
        name_ru="Эльф",
        emoji="[Эльф]",
        description="Долгожитель, мудрый, высокомерный",
        modifiers=RaceModifiers(
            openness=15, neuroticism=-15, energy_mult=0.80,
            stress_mult=0.50, detection_bonus=0.10,
        ),
        racial_relations={
            RaceType.HUMAN: 0.05, RaceType.ELF: 0.15, RaceType.DWARF: -0.20,
            RaceType.ORC: -0.30, RaceType.GOBLIN: -0.15,
        }
    ),
    RaceType.DWARF: Race(
        race_type=RaceType.DWARF,
        name_ru="Дварф",
        emoji="[Двр]",
        description="Упрямый, трудолюбивый, мастеровой",
        modifiers=RaceModifiers(
            conscientiousness=20, agreeableness=-10, energy_mult=1.10,
            anger_mult=1.30, repair_bonus=0.30, stubborn=True,
        ),
        racial_relations={
            RaceType.HUMAN: 0.10, RaceType.ELF: -0.20, RaceType.DWARF: 0.20,
            RaceType.ORC: -0.10, RaceType.GOBLIN: -0.25,
        }
    ),
    RaceType.ORC: Race(
        race_type=RaceType.ORC,
        name_ru="Орк",
        emoji="[Орк]",
        description="Агрессивный, прямолинейный, уважает силу",
        modifiers=RaceModifiers(
            extraversion=20, agreeableness=-20, anger_mult=1.50,
            fear_mult=0.50, combat_bonus=0.40,
        ),
        racial_relations={
            RaceType.HUMAN: 0.05, RaceType.ELF: -0.15, RaceType.DWARF: 0.05,
            RaceType.ORC: 0.25, RaceType.GOBLIN: -0.30,
        }
    ),
    RaceType.GOBLIN: Race(
        race_type=RaceType.GOBLIN,
        name_ru="Гоблин",
        emoji="[Гоб]",
        description="Хитрый, трусливый, коварный",
        modifiers=RaceModifiers(
            agreeableness=-25, neuroticism=30, energy_mult=1.20,
            fear_mult=1.80, can_betray=True, flee_threshold=0.6,
        ),
        racial_relations={
            RaceType.HUMAN: -0.10, RaceType.ELF: -0.10, RaceType.DWARF: -0.10,
            RaceType.ORC: -0.10, RaceType.GOBLIN: 0.10,
        }
    ),
}
