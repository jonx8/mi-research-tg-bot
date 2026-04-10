from typing import Optional

from sqlalchemy import select

from src.database import get_db_session
from src.models import Participant


class ParticipantRepository:
    def __init__(self, session_factory=get_db_session):
        self._session_factory = session_factory

    async def save(self, participant: Participant) -> Participant:
        async with self._session_factory() as session:
            saved = await session.merge(participant)
            return saved

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Participant]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Participant).where(Participant.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def get_group_by_telegram_id(self, telegram_id: int) -> Optional[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Participant.group_name).where(Participant.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    async def exists(self, telegram_id: int) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Participant.telegram_id).where(Participant.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none() is not None
