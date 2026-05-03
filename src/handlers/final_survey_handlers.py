import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.services.final_service import FinalSurveyService
from src.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


class FinalSurveyHandlers:
    def __init__(self, final_survey_service: FinalSurveyService, session_manager: SessionManager) -> None:
        self._final_survey_service = final_survey_service
        self._session_manager = session_manager

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

        ppa30 = (answer == 'yes')
        await self._session_manager.create_or_update_final_survey_session(
            telegram_id=update.effective_user.id,
            survey_id=survey_id,
            ppa_30d=ppa30
        )

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

        session = await self._session_manager.get_final_survey_session_by_id(survey_id)
        if not session:
            await query.edit_message_text("Ошибка сессии. Попробуйте снова.")
            return

        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            await query.edit_message_text("Опрос уже завершён.")
            return

        ppa7 = (answer == 'yes')
        await self._session_manager.update_final_survey_session(
            survey_id=survey_id,
            ppa_7d=ppa7
        )

        if ppa7:
            await query.edit_message_text(
                "📝 Сколько сигарет в день в среднем выкуриваете сейчас? (введите число)"
            )
            return
        await self._ask_quit_attempt(query, survey_id)

    async def handle_final_cigs_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 3a: ввод количества сигарет (если курит)."""
        user_input = update.message.text.strip()

        session = await self._session_manager.get_final_survey_session_by_telegram_id(update.effective_user.id)
        if not session:
            await update.message.reply_text("Ошибка сессии. Попробуйте снова.")
            return

        try:
            cigs = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Введите целое число.")
            return

        if not (0 <= cigs <= 100):
            await update.message.reply_text("⚠️ Введите число от 0 до 100.")
            return

        await self._session_manager.update_final_survey_session(
            session.survey_id,
            cigs_per_day=cigs
        )
        await self._ask_quit_attempt(update, session.survey_id)

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

        session = await self._session_manager.get_final_survey_session_by_id(survey_id)
        if not session:
            await query.edit_message_text("Ошибка сессии.")
            return

        quit_attempt = (answer == 'yes')
        await self._session_manager.update_final_survey_session(
            survey_id=survey_id,
            quit_attempt_made=quit_attempt
        )

        if quit_attempt:
            await query.edit_message_text(
                "Через сколько дней после начала исследования произошёл первый срыв? (введите число дней)"
            )
            return

        await self._complete_final_survey(query, context, survey_id)

    async def handle_final_days_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Шаг 5: ввод дней до первого срыва."""
        user_input = update.message.text.strip()

        session = await self._session_manager.get_final_survey_session_by_telegram_id(update.effective_user.id)
        if not session:
            await update.message.reply_text("Ошибка сессии.")
            return

        try:
            days = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Введите целое число дней.")
            return

        if days < 0:
            await update.message.reply_text("⚠️ Количество дней не может быть отрицательным.")
            return

        await self._session_manager.update_final_survey_session(
            survey_id=session.survey_id,
            days_to_first_lapse=days
        )
        await self._complete_final_survey(update, context, session.survey_id)

    async def _complete_final_survey(self, destination, context: ContextTypes.DEFAULT_TYPE,
                                     survey_id: int):
        """Завершает финальный опрос и сохраняет все данные."""
        session = await self._session_manager.get_final_survey_session_by_id(survey_id)
        survey = await self._final_survey_service.get_by_id(survey_id)
        if not survey or survey.completed_at:
            if hasattr(destination, 'edit_message_text'):
                await destination.edit_message_text("Опрос уже завершён.")
            else:
                await destination.message.reply_text("Опрос уже завершён.")
            return

        await self._final_survey_service.complete(
            survey=survey,
            ppa_30d=session.ppa_30d,
            ppa_7d=session.ppa_7d,
            cigs_per_day=session.cigs_per_day,
            quit_attempt_made=session.quit_attempt_made,
            days_to_first_lapse=session.days_to_first_lapse
        )

        await self._session_manager.delete_final_survey_session(session.survey_id)

        text = "✅ Спасибо! Финальный опрос завершён. Спасибо за участие в исследовании!\n" \
               f"📋 **Заполните форму обратной связи:**\n" \
               f"https://forms.yandex.ru/u/69ea4864068ff035aa33ec68"

        if hasattr(destination, 'edit_message_text'):
            await destination.edit_message_text(text, parse_mode='Markdown')
        else:
            await destination.message.reply_text(text, parse_mode='Markdown')
        logger.info(f"Final survey {survey.id} завершён")
