import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.services.session_manager import SessionManager
from src.services.weekly_check_in_service import WeeklyCheckInService

logger = logging.getLogger(__name__)


class WeeklyCheckInHandlers:
    def __init__(self, weekly_check_in_service: WeeklyCheckInService, session_manager: SessionManager):
        self._weekly_service = weekly_check_in_service
        self._session_manager = session_manager

    async def handle_weekly_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 1: выбор статуса курения за неделю."""
        query = update.callback_query
        await query.answer()
        data = query.data
        telegram_id = update.effective_user.id

        parts = data.split('_')
        checkin_id = int(parts[1])
        status = parts[3]

        checkin = await self._weekly_service.get_by_id(checkin_id)
        if not checkin or checkin.completed_at:
            logger.warning(f"Чек-ин завершен или не найден: {checkin_id}")
            await query.edit_message_text("Этот чек‑ин уже завершён или не найден.")
            return

        await self._session_manager.create_or_update_weekly_checkin_session(
            telegram_id=telegram_id,
            checkin_id=checkin_id,
            status=status
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(str(i), callback_data=f"weekly_{checkin_id}_craving_{i}") for i in range(1, 6)],
            [InlineKeyboardButton(str(i), callback_data=f"weekly_{checkin_id}_craving_{i}") for i in range(6, 11)],
        ])

        await query.edit_message_text(
            "📊 Оцените уровень тяги к курению за прошедшую неделю по шкале от 1 до 10:\n"
            "(1 — совсем не было, 10 — очень сильная тяга)",
            reply_markup=keyboard
        )

    async def handle_weekly_craving_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 2: выбор уровня тяги (1-10) через инлайн-кнопки."""
        query = update.callback_query
        await query.answer()
        data = query.data

        parts = data.split('_')
        checkin_id = int(parts[1])
        craving = int(parts[3])

        session = await self._session_manager.get_weekly_checkin_session(checkin_id)
        if not session:
            await query.edit_message_text("Сессия не найдена. Начните заново.")
            return

        checkin = await self._weekly_service.get_by_id(checkin_id)
        if not checkin or checkin.completed_at:
            await query.edit_message_text("Чек‑ин уже завершён.")
            await self._session_manager.delete_weekly_checkin_session(checkin_id)
            return

        await self._session_manager.update_weekly_checkin_session(
            checkin_id=checkin_id,
            craving=craving
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("😊 Хорошее", callback_data=f"weekly_{checkin_id}_mood_good")],
            [InlineKeyboardButton("😐 Среднее", callback_data=f"weekly_{checkin_id}_mood_average")],
            [InlineKeyboardButton("😞 Плохое", callback_data=f"weekly_{checkin_id}_mood_bad")],
        ])

        await query.edit_message_text(
            "😌 Как бы вы оценили своё общее самочувствие за неделю?",
            reply_markup=keyboard
        )

    async def handle_weekly_mood(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 3: выбор настроения."""
        query = update.callback_query
        await query.answer()
        data = query.data

        parts = data.split('_')
        checkin_id = int(parts[1])
        mood = parts[3]

        session = await self._session_manager.get_weekly_checkin_session(checkin_id)
        if not session:
            await query.edit_message_text("Сессия не найдена. Начните заново.")
            return

        checkin = await self._weekly_service.get_by_id(checkin_id)
        if not checkin or checkin.completed_at:
            await query.edit_message_text("Чек‑ин уже завершён.")
            await self._session_manager.delete_weekly_checkin_session(checkin_id)
            return

        await self._session_manager.update_weekly_checkin_session(
            checkin_id=checkin_id,
            mood=mood
        )

        status_map = {'not': 'не курил', 'some': 'эпизодически', 'regular': 'регулярно'}
        mood_map = {'good': 'хорошее', 'average': 'среднее', 'bad': 'плохое'}

        smoking_status = status_map.get(session.status)
        craving = session.craving
        mood_value = mood_map.get(mood)

        await self._weekly_service.complete(checkin, smoking_status, craving, mood_value)
        await self._session_manager.delete_weekly_checkin_session(checkin_id)

        await query.edit_message_text("✅ Спасибо! Ваш еженедельный отчёт записан.")
        logger.info(f"Weekly check‑in {checkin_id} завершён")
