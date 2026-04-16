import random

from src.database import Database


class MorningTipRepository:
    def __init__(self, db: Database):
        self._db = db
        self.MORNING_TIPS = [
            "Начните день со стакана воды — это поможет снизить желание курить.",
            "Помните, почему вы решили бросить курить. Держите эту мысль в голове.",
            "Сделайте короткую прогулку утром — свежий воздух уменьшает тягу.",
            "Попробуйте дыхательное упражнение: вдох на 4 счёта, задержка на 7, выдох на 8.",
            "Не держите сигареты на виду — уберите их из поля зрения.",
        ]

    def get_random_tip(self) -> str:
        return random.choice(self.MORNING_TIPS)
