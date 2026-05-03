
import logging
from datetime import datetime
from typing import Dict

from telegram import Bot
from telegram.error import TelegramError

from src.models import Participant
from src.repositories.intervention_content_repo import InterventionContentRepository
from src.repositories.participant_repo import ParticipantRepository

logger = logging.getLogger(__name__)


class InterventionContentSender:
    """Сервис для рассылки образовательного и мотивационного контента группе Б."""

    def __init__(
            self,
            bot: Bot,
            content_repo: InterventionContentRepository,
            participant_repo: ParticipantRepository,
    ):
        self._bot = bot
        self._content_repo = content_repo
        self._participant_repo = participant_repo

    async def _get_participant_weeks(self) -> Dict[str, tuple[int, Participant]]:
        """
        Получить словарь {participant_code: (week_number, participant)} для всех участников группы Б.
        Делает один запрос в БД для получения всех участников.
        """
        participants = await self._participant_repo.get_all_by_group('B')
        if not participants:
            return {}

        result = {}
        for participant in participants:
            registration_date = participant.registration_date.date()
            days_since_registration = (datetime.now().date() - registration_date).days
            week_number = max(1, (days_since_registration // 7) + 1)
            week_number = min(week_number, 24)
            result[participant.participant_code] = (week_number, participant)

        return result

    async def send_educational_message(self) -> None:
        """Отправить еженедельное образовательное сообщение всем участникам группы Б."""
        participant_weeks = await self._get_participant_weeks()

        if not participant_weeks:
            logger.info("Нет участников группы Б для образовательной рассылки")
            return

        weeks_map = {code: week for code, (week, _) in participant_weeks.items()}


        content_with_ids = await self._content_repo.get_educational_content_with_ids(weeks_map)

        for participant_code, (content_id, content) in content_with_ids.items():
            _, participant = participant_weeks[participant_code]
            week_number = weeks_map[participant_code]

            already_sent = await self._content_repo.get_already_sent_content_ids(
                participant_code, [content_id]
            )

            if content_id in already_sent:
                continue

            try:
                await self._bot.send_message(
                    chat_id=participant.telegram_id,
                    text=f"📚 **Образовательная информация **(неделя {week_number})\n\n{content}",
                    parse_mode='Markdown'
                )

                await self._content_repo.log_content_sent(participant_code, content_id)

                logger.info(f"Образовательное сообщение отправлено участнику {participant.telegram_id} (неделя {week_number})")
            except TelegramError as e:
                logger.error(f"Ошибка отправки образовательного сообщения участнику {participant.telegram_id}: {e}")

    async def send_motivational_message(self) -> None:
        """Отправить мотивационную историю (раз в 2 недели) всем участникам группы Б."""
        participant_weeks = await self._get_participant_weeks()

        if not participant_weeks:
            logger.info("Нет участников группы Б для мотивационной рассылки")
            return

        weeks_map = {
            code: week for code, (week, _) in participant_weeks.items()
            if week % 2 == 0
        }

        if not weeks_map:
            logger.info("Сейчас нечетная неделя, пропускаем мотивационную рассылку")
            return

        content_with_ids = await self._content_repo.get_motivational_content_with_ids(weeks_map)

        for participant_code, (content_id, content) in content_with_ids.items():
            _, participant = participant_weeks[participant_code]
            week_number = weeks_map[participant_code]

            already_sent = await self._content_repo.get_already_sent_content_ids(
                participant_code, [content_id]
            )

            if content_id in already_sent:
                logger.info(f"Контент {content_id} уже был отправлен участнику {participant_code}, пропускаем")
                continue

            try:
                await self._bot.send_message(
                    chat_id=participant.telegram_id,
                    text=f"💪 **Мотивационная история **(неделя {week_number})\n\n{content}",
                    parse_mode='Markdown'
                )

                await self._content_repo.log_content_sent(participant_code, content_id)

                logger.info(f"Мотивационное сообщение отправлено участнику {participant.telegram_id} (неделя {week_number})")
            except TelegramError as e:
                logger.error(f"Ошибка отправки мотивационного сообщения участнику {participant.telegram_id}: {e}")