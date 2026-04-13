from datetime import datetime
from typing import Optional, List

from sqlalchemy import select

from src.database import Database
from src.models import FollowUp


class FollowUpRepository:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, follow_up: FollowUp) -> FollowUp:
        async with self._db.get_db_session() as session:
            session.add(follow_up)
            await session.flush()
            return follow_up

    async def save_batch(self, follow_ups: List[FollowUp]) -> List[FollowUp]:
        async with self._db.get_db_session() as session:
            session.add_all(follow_ups)
            await session.flush()
            return follow_ups

    async def update(self, follow_up: FollowUp) -> FollowUp:
        async with self._db.get_db_session() as session:
            await session.merge(follow_up)
            return follow_up

    async def get_pending(self, participant_code: str) -> Optional[FollowUp]:
        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(FollowUp)
                .where(FollowUp.participant_code == participant_code)
                .where(FollowUp.completed_at.is_(None))
                .where(FollowUp.scheduled_date <= datetime.now())
                .order_by(FollowUp.scheduled_date)
                .limit(1)
            )
            return result.scalar_one_or_none()