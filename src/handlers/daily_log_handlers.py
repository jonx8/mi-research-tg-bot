import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.services.daily_log_service import DailyLogService

logger = logging.getLogger(__name__)


class DailyLogHandlers:
    def __init__(self, daily_log_service: DailyLogService):
        self._daily_service = daily_log_service

    async def handle_evening_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data  # "daily_{log_id}_{yes/difficult/craving}"

        parts = data.split('_')
        log_id = int(parts[1])
        response = parts[2]

        await self._daily_service.save_evening_response(log_id, response)

        await query.edit_message_text(
            "✅ Спасибо за ответ! Желаем спокойного вечера и хорошего отдыха."
        )
        logger.info(f"Вечерний опрос {log_id}: ответ '{response}'")
