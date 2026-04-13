from src.database import Database
from src.models import BaselineQuestionnaire


class BaselineQuestionnaireRepository:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, questionnaire: BaselineQuestionnaire) -> BaselineQuestionnaire:
        async with self._db.get_db_session() as session:
            session.add(questionnaire)
            await session.flush()
            return questionnaire