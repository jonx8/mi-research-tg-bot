from typing import Optional, List

from sqlalchemy import select

from src.database import Database
from src.models import Participant
from src.utils.encryption import get_encryption_service


class ParticipantRepository:
    def __init__(self, db: Database):
        self._db = db

    async def save(self, participant: Participant) -> Participant:
        async with self._db.get_db_session() as session:
            session.add(participant)
            await session.flush()
            return participant

    async def get_by_id(self, participant_code: str) -> Optional[Participant]:
        async with self._db.get_db_session() as session:
            return await session.get_one(Participant, ident=participant_code)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[Participant]:
        """Получает участника по telegram_id (автоматически шифрует для поиска)"""
        encryption_service = get_encryption_service()
        encrypted_id = encryption_service.encrypt(telegram_id)

        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(Participant).where(Participant.telegram_id_encrypted == encrypted_id)
            )
            return result.scalar_one_or_none()

    async def get_group_by_telegram_id(self, telegram_id: int) -> Optional[str]:
        """Получает группу участника по telegram_id"""
        encryption_service = get_encryption_service()
        encrypted_id = encryption_service.encrypt(telegram_id)

        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(Participant.group_name).where(Participant.telegram_id_encrypted == encrypted_id)
            )
            return result.scalar_one_or_none()

    async def exists(self, telegram_id: int) -> bool:
        """Проверяет существование участника по telegram_id"""
        encryption_service = get_encryption_service()
        encrypted_id = encryption_service.encrypt(telegram_id)

        async with self._db.get_db_session() as session:
            result = await session.execute(
                select(Participant.telegram_id_encrypted).where(Participant.telegram_id_encrypted == encrypted_id)
            )
            return result.scalar_one_or_none() is not None

    async def get_all_by_group(self, group_name: str) -> List[Participant]:
        async with self._db.get_db_session() as session:
            result = await session.execute(select(Participant).where(Participant.group_name == group_name))
            return result.scalars().all()
