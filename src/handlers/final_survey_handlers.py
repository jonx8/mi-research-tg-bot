import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.services.final_service import FinalSurveyService

logger = logging.getLogger(__name__)


class FinalSurveyHandlers:
    def __init__(self, final_survey_service: FinalSurveyService) -> None:
        self._final_survey_service = final_survey_service

    async def handle_final_survey_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 1: ответ на 30‑дневную абстиненцию."""
        query = update.callback_query
        await query.answer()
        data = query.data  # "final_{id}_ppa30_{yes/no}"

        parts = data.split('_')
        survey_id = int(parts[1])
        answer = parts[3]  # 'yes' или 'no'

        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            await query.edit_message_text("Опрос уже завершён или не найден.")
            return

        context.user_data['final_survey_id'] = survey_id
        context.user_data['final_ppa30'] = (answer == 'yes')

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data=f"final_{survey_id}_ppa7_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data=f"final_{survey_id}_ppa7_no")]
        ])
        await query.edit_message_text(
            "Курили ли Вы хотя бы одну сигарету за последние 7 дней?",
            reply_markup=keyboard
        )

    async def handle_final_ppa7(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 2: ответ на 7‑дневную PPA."""
        query = update.callback_query
        await query.answer()
        data = query.data  # "final_{id}_ppa7_{yes/no}"

        parts = data.split('_')
        survey_id = int(parts[1])
        answer = parts[3]

        stored_id = context.user_data.get('final_survey_id')
        if stored_id != survey_id:
            await query.edit_message_text("Ошибка сессии. Попробуйте снова.")
            return

        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            await query.edit_message_text("Опрос уже завершён.")
            return

        ppa7 = (answer == 'yes')
        context.user_data['final_ppa7'] = ppa7

        if ppa7:
            await query.edit_message_text(
                "📝 Сколько сигарет в день в среднем выкуриваете сейчас? (введите число)"
            )
            context.user_data['final_step'] = 'cigs_per_day'
        else:
            await self._ask_quit_attempt(query, survey_id)

    async def handle_final_cigs_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 3a: ввод количества сигарет (если курит)."""
        user_input = update.message.text.strip()
        survey_id = context.user_data.get('final_survey_id')
        if not survey_id:
            await update.message.reply_text("Нет активного опроса.")
            return

        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            await update.message.reply_text("Опрос уже завершён.")
            return

        try:
            cigs = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Введите целое число.")
            return

        if not (0 <= cigs <= 100):
            await update.message.reply_text("⚠️ Введите число от 0 до 100.")
            return

        context.user_data['final_cigs'] = cigs
        await self._ask_quit_attempt(update, survey_id)

    async def _ask_quit_attempt(self, destination, survey_id: int):
        """Задаёт вопрос о попытках бросить."""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data=f"final_{survey_id}_quit_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data=f"final_{survey_id}_quit_no")]
        ])
        text = "Были ли у вас попытки бросить курить за последние 6 месяцев?"
        if hasattr(destination, 'edit_message_text'):
            await destination.edit_message_text(text, reply_markup=keyboard)
        else:
            await destination.message.reply_text(text, reply_markup=keyboard)

    async def handle_final_quit_attempt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 4: ответ о попытках бросить."""
        query = update.callback_query
        await query.answer()
        data = query.data  # "final_{id}_quit_{yes/no}"

        parts = data.split('_')
        survey_id = int(parts[1])
        answer = parts[3]

        stored_id = context.user_data.get('final_survey_id')
        if stored_id != survey_id:
            await query.edit_message_text("Ошибка сессии.")
            return

        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            await query.edit_message_text("Опрос уже завершён.")
            return

        quit_attempt = (answer == 'yes')
        context.user_data['final_quit_attempt'] = quit_attempt

        if quit_attempt:
            await query.edit_message_text(
                "Через сколько дней после начала исследования произошёл первый срыв? (введите число дней)"
            )
            context.user_data['final_step'] = 'days_to_lapse'
            return

        await self._complete_final_survey(query, context)

    async def handle_final_days_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 5: ввод дней до первого срыва."""
        user_input = update.message.text.strip()
        survey_id = context.user_data.get('final_survey_id')
        if not survey_id:
            await update.message.reply_text("Нет активного опроса.")
            return

        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            await update.message.reply_text("Опрос уже завершён.")
            return

        try:
            days = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Введите целое число дней.")
            return

        if days < 0:
            await update.message.reply_text("⚠️ Количество дней не может быть отрицательным.")
            return

        context.user_data['final_days_to_lapse'] = days
        await self._complete_final_survey(update, context)

    async def _complete_final_survey(self, destination, context: ContextTypes.DEFAULT_TYPE):
        """Завершает финальный опрос и сохраняет все данные."""
        survey_id = context.user_data.get('final_survey_id')
        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            if hasattr(destination, 'edit_message_text'):
                await destination.edit_message_text("Опрос уже завершён.")
            else:
                await destination.message.reply_text("Опрос уже завершён.")
            return

        ppa30 = context.user_data.get('final_ppa30', False)
        ppa7 = context.user_data.get('final_ppa7', False)
        cigs = context.user_data.get('final_cigs')
        quit_attempt = context.user_data.get('final_quit_attempt', False)
        days = context.user_data.get('final_days_to_lapse')

        await self._final_survey_service.complete(
            survey, ppa30, ppa7, cigs, quit_attempt, days
        )

        for key in list(context.user_data.keys()):
            if key.startswith('final_'):
                context.user_data.pop(key, None)

        text = "✅ Спасибо! Финальный опрос завершён. Спасибо за участие в исследовании!"
        if hasattr(destination, 'edit_message_text'):
            await destination.edit_message_text(text)
        else:
            await destination.message.reply_text(text)
        logger.info(f"Final survey {survey_id} завершён")
