"""
Пресеты расового состава групп и палитра цветов агентов.
"""

from colorama import Fore

from models.personality import PersonalityType
from models.races import RaceType


AGENT_COLORS = [Fore.CYAN, Fore.YELLOW, Fore.GREEN, Fore.RED, Fore.MAGENTA]


RACE_PRESETS = {
    "humans": {
        "name": "Люди (классика)",
        "agents": [
            {
                "name": "Алиса",
                "race": RaceType.HUMAN,
                "personality": PersonalityType.ALTRUIST,
                "is_male": False,
                "age": 25,
                "interests": "психология, помощь людям, искусство",
                "info": "Всегда готова поддержать и выслушать.",
            },
            {
                "name": "Борис",
                "race": RaceType.HUMAN,
                "personality": PersonalityType.STOIC,
                "is_male": True,
                "age": 35,
                "interests": "технологии, наука, логика",
                "info": "Предпочитает факты эмоциям, анализирует ситуацию.",
            },
            {
                "name": "Вика",
                "race": RaceType.HUMAN,
                "personality": PersonalityType.MACHIAVELLIAN,
                "is_male": False,
                "age": 28,
                "interests": "власть, манипуляции, критика всех вокруг",
                "info": (
                    "Вика — крайне токсичная и скандальная личность. "
                    "Она ВСЕГДА недовольна другими, ругается, оскорбляет. "
                    "Никогда ни с кем не соглашается."
                ),
            },
        ],
    },

    "fantasy_party": {
        "name": "Фэнтези-группа (Эльф + Дварф + Орк)",
        "agents": [
            {
                "name": "Леголас",
                "race": RaceType.ELF,
                "personality": PersonalityType.STOIC,
                "is_male": True,
                "age": 300,
                "interests": "природа, мудрость, стрельба из лука",
                "info": "Древний эльф, видевший многое. Высокомерен к другим расам, но справедлив.",
            },
            {
                "name": "Гимли",
                "race": RaceType.DWARF,
                "personality": PersonalityType.REBEL,
                "is_male": True,
                "age": 140,
                "interests": "кузнечное дело, горное дело, пиво",
                "info": "Упрямый дварф-мастер. Жаден при дележе, но надёжен в бою. Ненавидит эльфов.",
            },
            {
                "name": "Урук",
                "race": RaceType.ORC,
                "personality": PersonalityType.MACHIAVELLIAN,
                "is_male": True,
                "age": 30,
                "interests": "бой, оружие, сила",
                "info": "Агрессивный орк-воин. Уважает только силу и храбрость. Презирает слабых и трусов.",
            },
        ],
    },

    "mixed_survival": {
        "name": "Смешанная группа (Человек + Эльф + Гоблин)",
        "agents": [
            {
                "name": "Арагорн",
                "race": RaceType.HUMAN,
                "personality": PersonalityType.ALTRUIST,
                "is_male": True,
                "age": 35,
                "interests": "лидерство, стратегия, дипломатия",
                "info": "Прирождённый лидер-дипломат. Пытается объединить группу и помирить всех.",
            },
            {
                "name": "Арвен",
                "race": RaceType.ELF,
                "personality": PersonalityType.STOIC,
                "is_male": False,
                "age": 250,
                "interests": "целительство, природа, знания",
                "info": "Мудрая эльфийка-целительница. Спокойна, но презирает грубость.",
            },
            {
                "name": "Фик",
                "race": RaceType.GOBLIN,
                "personality": PersonalityType.REBEL,
                "is_male": True,
                "age": 15,
                "interests": "воровство, хитрость, выживание",
                "info": "Трусливый гоблин-пройдоха. Хитёр, жаден, может предать группу при опасности.",
            },
        ],
    },

    "classic_party": {
        "name": "Классическая партия (4 расы)",
        "agents": [
            {
                "name": "Анна",
                "race": RaceType.HUMAN,
                "personality": PersonalityType.ALTRUIST,
                "is_male": False,
                "age": 28,
                "interests": "дипломатия, медицина, переговоры",
                "info": "Дипломат и посредник. Пытается найти общий язык со всеми.",
            },
            {
                "name": "Таурил",
                "race": RaceType.ELF,
                "personality": PersonalityType.STOIC,
                "is_male": True,
                "age": 400,
                "interests": "древние знания, магия, природа",
                "info": "Древний мудрец. Высокомерен, но незаменим в сложных решениях.",
            },
            {
                "name": "Торин",
                "race": RaceType.DWARF,
                "personality": PersonalityType.REBEL,
                "is_male": True,
                "age": 160,
                "interests": "кузнечное дело, шахты, сокровища",
                "info": "Мастер-кузнец. Упрям как скала, жаден при дележе, но верный товарищ.",
            },
            {
                "name": "Грок",
                "race": RaceType.ORC,
                "personality": PersonalityType.MACHIAVELLIAN,
                "is_male": True,
                "age": 25,
                "interests": "бой, оружие, охота",
                "info": "Свирепый орк-воин. Уважает только силу. Агрессивен, но честен в бою.",
            },
        ],
    },

    "goblin_betrayal": {
        "name": "Гоблин-предатель (сценарий предательства)",
        "agents": [
            {
                "name": "Джон",
                "race": RaceType.HUMAN,
                "personality": PersonalityType.ALTRUIST,
                "is_male": True,
                "age": 30,
                "interests": "лидерство, защита, стратегия",
                "info": "Лидер группы. Верит в каждого, даже в гоблина.",
            },
            {
                "name": "Грок",
                "race": RaceType.ORC,
                "personality": PersonalityType.STOIC,
                "is_male": True,
                "age": 28,
                "interests": "бой, выносливость, оружие",
                "info": "Молчаливый орк-воин. Презирает трусов. Готов защищать группу.",
            },
            {
                "name": "Фик",
                "race": RaceType.GOBLIN,
                "personality": PersonalityType.REBEL,
                "is_male": True,
                "age": 12,
                "interests": "хитрость, воровство, побег",
                "info": "Трусливый гоблин. Слабое звено группы. Может предать при первой опасности, украв припасы.",
            },
        ],
    },
}
