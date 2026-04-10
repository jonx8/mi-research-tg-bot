import random
from typing import Optional

from sqlalchemy import select
from src.database import get_db_session

from src.models import Technique


class TechniqueRepository:
    def __init__(self, session_factory=get_db_session):
        self._session_factory = session_factory

    async def get_all(self) -> list[Technique]:
        async with self._session_factory() as session:
            result = await session.execute(select(Technique))
            return result.scalars().all()

    async def get_random(self, count: int = 4) -> list[Technique]:
        async with self._session_factory() as session:
            result = await session.execute(select(Technique.id))
            all_ids = result.scalars().all()

            if len(all_ids) <= count:
                result = await session.execute(select(Technique))
                return result.scalars().all()

            random_ids = random.sample(all_ids, count)

            result = await session.execute(
                select(Technique)
                .where(Technique.id.in_(random_ids))
            )
            return result.scalars().all()

    async def get_by_id(self, technique_id: str) -> Optional[Technique]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Technique).where(Technique.id == technique_id)
            )
            return result.scalar_one_or_none()
