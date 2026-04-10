from src.exceptions import UserNotFoundError

from src.models import Participant
from src.repositories.participant_repo import ParticipantRepository


class ParticipantService:
    def __init__(self, repo: ParticipantRepository):
        self._repo = repo

    async def get_by_telegram_id(self, telegram_id: int):
        participant = await self._repo.get_by_telegram_id(telegram_id)
        if not participant:
            raise UserNotFoundError(f"Пользователь {telegram_id} не найден")
        return participant

    async def get_group(self, telegram_id: int) -> str:
        group = await self._repo.get_group_by_telegram_id(telegram_id)
        if not group:
            raise UserNotFoundError(f"Пользователь {telegram_id} не найден")
        return group

    async def exists(self, telegram_id: int) -> bool:
        return await self._repo.exists(telegram_id)

    async def register(self, participant: Participant) -> Participant:
        return await self._repo.save(participant)