import hashlib
import secrets

from telegram import ReplyKeyboardMarkup, KeyboardButton

from src.exceptions import UserNotFoundError

from src.models import Participant
from src.repositories.participant_repo import ParticipantRepository


class ParticipantService:
    def __init__(self, repo: ParticipantRepository):
        self._repo = repo

    @staticmethod
    def generate_participant_code(telegram_id: int) -> str:
        hash_input = f"{telegram_id}{secrets.token_hex(8)}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:10]

    async def get_by_telegram_id(self, telegram_id: int) -> Participant:
        participant = await self._repo.get_by_telegram_id(telegram_id)
        if not participant:
            raise UserNotFoundError(telegram_id)
        return participant

    async def get_main_keyboard(self, telegram_id: int):
        if not await self.exists(telegram_id):
            return ReplyKeyboardMarkup([[]], resize_keyboard=True)

        user_group = await self.get_group(telegram_id)

        if user_group == 'B':
            return ReplyKeyboardMarkup([
                [KeyboardButton("🆘 SOS - Экстренная помощь")],
                [KeyboardButton("ℹ️ Помощь")]
            ], resize_keyboard=True)
        else:
            return ReplyKeyboardMarkup([[KeyboardButton("ℹ️ Помощь")]], resize_keyboard=True)

    async def get_group(self, telegram_id: int) -> str:
        group = await self._repo.get_group_by_telegram_id(telegram_id)
        if not group:
            raise UserNotFoundError(telegram_id)
        return group

    async def exists(self, telegram_id: int) -> bool:
        return await self._repo.exists(telegram_id)

    async def save(self, participant: Participant) -> Participant:
        return await self._repo.save(participant)
