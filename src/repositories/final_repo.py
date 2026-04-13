from datetime import datetime
from typing import Optional

from sqlalchemy import select

from src.database import Database
from src.models import FinalSurvey


class FinalSurveyRepository:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, survey: FinalSurvey) -> FinalSurvey:
        async with self._db.get_db_session() as session:
            session.add(survey)
            await session.flush()
            return survey

    async def update(self, survey: FinalSurvey) -> FinalSurvey:
        async with self._db.get_db_session() as session:
            await session.merge(survey)
            return survey

    async def get_pending(self, participant_code: str) -> Optional[FinalSurvey]:
        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(FinalSurvey)
                .where(FinalSurvey.participant_code == participant_code)
                .where(FinalSurvey.completed_at.is_(None))
                .where(FinalSurvey.scheduled_date <= datetime.now())
            )
            return result.scalar_one_or_none()