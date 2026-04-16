import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.services.follow_up_service import FollowUpService

logger = logging.getLogger(__name__)


class FollowUpSurveyHandlers:
    def __init__(self, follow_up_service: FollowUpService):
        self._follow_up_service = follow_up_service

    async def handle_follow_up_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ответ на первый вопрос follow‑up (курили за 7 дней)."""
        query = update.callback_query
        await query.answer()
        data = query.data  # формат: "followup_{id}_ppa_{yes/no}"

        parts = data.split('_')
        if len(parts) != 4:
            await query.edit_message_text("Некорректный формат данных.")
            return

        follow_up_id = int(parts[1])
        answer = parts[3]

        follow_up = await self._follow_up_service.get_by_id(int(follow_up_id))
        if not follow_up:
            await query.edit_message_text("Опрос не найден.")
            return
        if follow_up.completed_at:
            await query.edit_message_text("Вы уже ответили на этот опрос.")
            return

        if answer == 'yes':
            follow_up.ppa_7d = True
            await self._follow_up_service.update(follow_up)
            context.user_data['pending_follow_up_id'] = follow_up_id
            await query.edit_message_text(
                "📝 Сколько сигарет в день в среднем выкуриваете сейчас?\n"
                "(введите целое число от 0 до 100)"
            )
            return

        await self._follow_up_service.complete(follow_up, ppa_7d=False, cigs_per_day=None)
        await query.edit_message_text("✅ Спасибо! Ваш ответ записан.")
        logger.info(f"Follow‑up {follow_up_id} завершён: не курил")

    async def handle_follow_up_cigs_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ввод количества сигарет после утвердительного ответа."""
        user_input = update.message.text.strip()

        follow_up_id = context.user_data.get('pending_follow_up_id')
        if not follow_up_id:
            await update.message.reply_text("Нет активного опроса. Возможно, он уже завершён.")
            return

        follow_up = await self._follow_up_service.get_by_id(follow_up_id)
        if not follow_up or follow_up.completed_at:
            await update.message.reply_text("Опрос уже завершён или не существует.")
            context.user_data.pop('pending_follow_up_id', None)
            return

        try:
            cigs = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Пожалуйста, введите целое число.")
            return

        if not (0 <= cigs <= 100):
            await update.message.reply_text("⚠️ Введите число от 0 до 100.")
            return

        await self._follow_up_service.complete(follow_up, ppa_7d=True, cigs_per_day=cigs)
        context.user_data.pop('pending_follow_up_id', None)
        await update.message.reply_text("✅ Спасибо! Ваш ответ записан.")
        logger.info(f"Follow‑up {follow_up_id} завершён: курит {cigs} сигарет/день")
