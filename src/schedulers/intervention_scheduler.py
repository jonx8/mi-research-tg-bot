import logging
from datetime import datetime

from src.services.intervention_content_sender import InterventionContentSender

logger = logging.getLogger(__name__)


class InterventionContentScheduler:
    """Планировщик для регулярной отправки образовательного и мотивационного контента."""

    def __init__(self, content_sender: InterventionContentSender):
        self._content_sender = content_sender

    async def process_weekly(self) -> None:
        """Еженедельная отправка образовательных и мотивационных сообщений."""

        weekday = datetime.now().weekday()
        current_hour = datetime.now().hour

        if weekday == 0 and current_hour >= 12:
            await self._content_sender.send_educational_message()

        if weekday == 2 and current_hour >= 14:
            await self._content_sender.send_motivational_message()

    async def run_all(self) -> None:
        """Запустить все задачи планировщика контента."""
        try:
            await self.process_weekly()
        except Exception as e:
            logger.error(f"Ошибка в планировщике контента: {e}", exc_info=True)
