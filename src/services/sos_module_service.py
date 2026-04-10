import random
from typing import List, Optional

from src.exceptions import TechniqueNotFoundError
from src.models import Technique
from src.repositories.technique_repo import TechniqueRepository


class SOSModuleService:
    def __init__(self, technique_repo: TechniqueRepository):
        self._technique_repo = technique_repo
        self.craving_messages = [
            "Тяга пройдет через 5-10 минут! Держитесь! 💪",
            "Вы сильнее, чем вам кажется! Эта тяга скоро ослабнет 🌟",
            "Каждая победа над тягой делает вас сильнее! 🏆",
            "Помните: одна тяга не отменяет весь ваш прогресс! 📈",
            "Вы уже прошли такой путь! Не сдавайтесь сейчас! 🚀"
        ]

    async def get_technique_by_id(self, technique_id: str) -> Optional[Technique]:
        """Находит технику по ID через репозиторий"""
        technique = await self._technique_repo.get_by_id(technique_id)
        if not technique:
            raise TechniqueNotFoundError(f"Техника {technique_id} не найдена")
        return technique

    async def get_sos_techniques(self, count: int = 4) -> list[Technique]:
        """Возвращает случайные техники для борьбы с тягой"""
        return await self._technique_repo.get_random(count)

    def get_craving_message(self) -> str:
        """Возвращает случайное мотивационное сообщение"""
        return random.choice(self.craving_messages)

    @staticmethod
    def get_craving_analysis_questions() -> List[str]:
        """Вопросы для анализа триггеров тяги"""
        return [
            "Что спровоцировало тягу? (ситуация, эмоции, место)",
            "Какие мысли были у вас в момент тяги?",
            "Что вы почувствовали физически?",
            "Какой способ помог справиться с тягой?"
        ]
