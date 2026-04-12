import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.exceptions import ValidationError, SessionNotFoundError, InvalidStepError, UserNotFoundError, \
    TechniqueNotFoundError, CravingSessionNotFoundError

logger = logging.getLogger(__name__)


async def _notify_user(update: Update, text: str) -> None:
    if not update:
        return

    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(text)
        except Exception:
            await update.callback_query.answer(text, show_alert=True)


async def global_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик всех необработанных исключений"""
    error = context.error

    logger.error(f"Global error handler caught: {type(error).__name__}: {error}", exc_info=error)

    if isinstance(error, ValidationError):
        await _notify_user(update, str(error))

    elif isinstance(error, SessionNotFoundError):
        await _notify_user(
            update,
            "⏰ Ваша сессия истекла. Пожалуйста, начните заново с команды /start"
        )

    elif isinstance(error, InvalidStepError):
        if update and update.callback_query:
            await update.callback_query.answer("Это действие уже недоступно")

    elif isinstance(error, UserNotFoundError):
        await _notify_user(
            update,
            "👤 Пользователь не найден. Используйте /start для регистрации."
        )

    elif isinstance(error, TechniqueNotFoundError):
        logger.warning(f"Техника не найдена: {error.technique_id}")
        await _notify_user(
            update,
            "🆘 Техника временно недоступна. Попробуйте выбрать другую."
        )

    elif isinstance(error, CravingSessionNotFoundError):
        await _notify_user(
            update,
            "📝 Сессия анализа тяги не найдена. Начните заново через /sos"
        )

    else:
        logger.exception("Unexpected error")
        await _notify_user(
            update,
            "❌ Произошла техническая ошибка. Мы уже работаем над её исправлением. "
            "Пожалуйста, попробуйте позже"
        )
