from typing import Optional, List

from sqlalchemy import select

from src.database import Database
from src.models import WeeklyCheckIn


class WeeklyCheckInRepository:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, checkin: WeeklyCheckIn) -> WeeklyCheckIn:
        async with self._db.get_db_session() as session:
            session.add(checkin)
            await session.flush()
            return checkin

    async def save_batch(self, checkins: List[WeeklyCheckIn]) -> List[WeeklyCheckIn]:
        async with self._db.get_db_session() as session:
            session.add_all(checkins)
            await session.flush()
            return checkins

    async def update(self, checkin: WeeklyCheckIn) -> WeeklyCheckIn:
        async with self._db.get_db_session() as session:
            await session.merge(checkin)
            return checkin

    async def get_pending(self, participant_code: str) -> Optional[WeeklyCheckIn]:
        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(WeeklyCheckIn)
                .where(WeeklyCheckIn.participant_code == participant_code)
                .where(WeeklyCheckIn.completed_at.is_(None))
                .order_by(WeeklyCheckIn.scheduled_date)
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_latest_completed_week(self, participant_code: str) -> int:
        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(WeeklyCheckIn.week_number)
                .where(WeeklyCheckIn.participant_code == participant_code)
                .where(WeeklyCheckIn.completed_at.isnot(None))
                .order_by(WeeklyCheckIn.week_number.desc())
                .limit(1)
            )
            week = result.scalar_one_or_none()
            return week or 0
