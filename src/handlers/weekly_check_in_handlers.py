import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.services.weekly_check_in_service import WeeklyCheckInService

logger = logging.getLogger(__name__)


class WeeklyCheckInHandlers:
    def __init__(self, weekly_check_in_service: WeeklyCheckInService):
        self._weekly_service = weekly_check_in_service

    async def handle_weekly_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 1: выбор статуса курения за неделю."""
        query = update.callback_query
        await query.answer()
        data = query.data  # "weekly_{id}_status_{not/some/regular}"
        telegram_id = update.effective_user.id

        parts = data.split('_')
        checkin_id = int(parts[1])
        status = parts[3]  # 'not', 'some', 'regular'

        checkin = await self._weekly_service.get_by_id(checkin_id)
        if not checkin or checkin.completed_at:
            logger.warning(f"чек-ин завершен или не найден от {telegram_id}: {data}")
            await query.edit_message_text("Этот чек‑ин уже завершён или не найден.")
            return

        context.user_data['pending_weekly_id'] = checkin_id
        context.user_data['weekly_status'] = status

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
        data = query.data  # "weekly_{id}_craving_{1-10}"

        parts = data.split('_')
        checkin_id = int(parts[1])
        craving = int(parts[3])

        stored_id = context.user_data.get('pending_weekly_id')
        if stored_id != checkin_id:
            await query.edit_message_text("Несоответствие опроса. Начните заново.")
            return

        checkin = await self._weekly_service.get_by_id(checkin_id)
        if not checkin or checkin.completed_at:
            await query.edit_message_text("Чек‑ин уже завершён.")
            context.user_data.pop('pending_weekly_id', None)
            return

        context.user_data['weekly_craving'] = craving

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
        data = query.data  # "weekly_{id}_mood_{good/average/bad}"

        parts = data.split('_')
        checkin_id = int(parts[1])
        mood = parts[3]  # 'good', 'average', 'bad'

        stored_id = context.user_data.get('pending_weekly_id')
        if stored_id != checkin_id:
            await query.edit_message_text("Несоответствие опроса. Начните заново.")
            return

        checkin = await self._weekly_service.get_by_id(checkin_id)
        if not checkin or checkin.completed_at:
            await query.edit_message_text("Чек‑ин уже завершён.")
            context.user_data.pop('pending_weekly_id', None)
            return

        context.user_data['weekly_mood'] = mood

        status_map = {'not': 'не курил', 'some': 'эпизодически', 'regular': 'регулярно'}
        mood_map = {'good': 'хорошее', 'average': 'среднее', 'bad': 'плохое'}

        smoking_status = status_map.get(context.user_data['weekly_status'])
        craving = context.user_data['weekly_craving']
        mood_value = mood_map.get(mood)

        await self._weekly_service.complete(checkin, smoking_status, craving, mood_value)

        for key in ('pending_weekly_id', 'weekly_status', 'weekly_craving', 'weekly_mood'):
            context.user_data.pop(key, None)

        await query.edit_message_text("✅ Спасибо! Ваш еженедельный отчёт записан.")
        logger.info(f"Weekly check‑in {checkin_id} завершён")
