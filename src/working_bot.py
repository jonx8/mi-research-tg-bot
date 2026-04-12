import logging

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from src.config import Config
from src.database import Database
from src.handlers.global_error_handler import global_error_handler
from src.handlers.registration_handlers import RegistrationHandlers
from src.handlers.sos_module_handlers import SOSModuleHandlers
from src.logging_config import setup_logging
from src.repositories.participant_repo import ParticipantRepository
from src.repositories.technique_repo import TechniqueRepository
from src.services.craving_analysis_orchestrator import CravingAnalysisOrchestrator
from src.services.participant_service import ParticipantService
from src.services.registration_orchestrator import RegistrationOrchestrator
from src.services.session_manager import SessionManager, RegistrationStep
from src.services.techniques_service import TechniqueService

config = Config()
setup_logging(config)

logger = logging.getLogger(__name__)

database = Database(config.DATABASE_URL)

participant_repo = ParticipantRepository(database)
technique_repo = TechniqueRepository(database)

participant_service = ParticipantService(participant_repo)
technique_service = TechniqueService(technique_repo)
session_manager = SessionManager()
registration_orchestrator = RegistrationOrchestrator(session_manager, participant_service)
craving_analysis_orchestrator = CravingAnalysisOrchestrator(session_manager)

registration_handlers = RegistrationHandlers(registration_orchestrator, participant_service)
sos_module_handlers = SOSModuleHandlers(technique_service, craving_analysis_orchestrator)


async def get_main_keyboard(telegram_id: int):
    if not await participant_service.exists(telegram_id):
        return ReplyKeyboardMarkup([[]], resize_keyboard=True)

    user_group = await participant_service.get_group(telegram_id)

    if user_group == 'B':
        return ReplyKeyboardMarkup([
            [KeyboardButton("🆘 SOS - Экстренная помощь")],
            [KeyboardButton("📊 Статус курения"), KeyboardButton("ℹ️ Помощь")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            [KeyboardButton("📊 Статус курения"), KeyboardButton("ℹ️ Помощь")]
        ], resize_keyboard=True)


async def sos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_group = await participant_service.get_group(user_id)
    if not user_group:
        await update.message.reply_text(
            "ℹ️ **Вы не зарегистрированы в исследовании**\n\n"
            "Для участия в исследовании зарегистрируйтесь с помощью команды /start",
            parse_mode='Markdown'
        )
        return
    if user_group == 'A':
        keyboard = await get_main_keyboard(user_id)

        await update.message.reply_text(
            "ℹ️ **Вам назначен базовый тип поддержки**\n\n"
            "Вы будете получать периодические опросы о вашем статусе курения.\n\n"
            "Спасибо за участие в исследовании!",
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        return
    await sos_module_handlers.show_sos_menu(update, context)


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not await participant_service.exists(user_id):
        await update.message.reply_text(
            "❌ Вы не зарегистрированы в исследовании.\n\n"
            "Нажмите /start для регистрации."
        )
        return

    user_group = await participant_service.get_group(user_id)

    if text == "🆘 SOS - Экстренная помощь":
        if user_group == 'B':
            await sos_module_handlers.show_sos_menu(update, context)
        else:
            keyboard = await get_main_keyboard(user_id)
            await update.message.reply_text(
                "ℹ️ **Вам назначен базовый тип поддержки**\n\n"
                "Вы будете получать периодические опросы о вашем статусе курения.\n\n"
                "Спасибо за участие в исследовании!",
                reply_markup=keyboard
            )
    elif text == "📊 Статус курения":
        keyboard = await get_main_keyboard(user_id)
        await update.message.reply_text(
            "📊 **Отслеживание статуса курения**\n\n"
            "Эта функция будет доступна после начала исследования.\n\n"
            "Вы будете получать регулярные опросы о вашем прогрессе.",
            reply_markup=keyboard
        )
    elif text == "ℹ️ Помощь":
        keyboard = await get_main_keyboard(user_id)
        await update.message.reply_text(
            "ℹ️ **Помощь**\n\n"
            "Этот бот создан для исследования TELEGRAM-MI по поддержке отказа от курения "
            "после перенесенного инфаркта миокарда.\n\n"
            "Доступные команды:\n"
            "• /start - начать регистрацию\n"
            "• /sos - экстренная помощь при тяге (только для группы B)\n\n"
            "Если у вас есть вопросы, обращайтесь к исследователям.",
            reply_markup=keyboard
        )


async def handle_all_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единая точка входа для всех текстовых сообщений."""
    telegram_id = update.effective_user.id

    if craving_analysis_orchestrator.is_analysis_active(telegram_id):
        await sos_module_handlers.handle_analysis_answer(update, context)
        return

    session = session_manager.get_registration_session(telegram_id)

    if session:
        if session.step == RegistrationStep.AGE:
            await registration_handlers.handle_age(update, context)
            return

        elif session.step == RegistrationStep.GENDER:
            await update.message.reply_text(
                "👤 Пожалуйста, выберите ваш пол, нажав на одну из кнопок выше.",
                parse_mode='Markdown'
            )
            return

        elif session.step in (RegistrationStep.FAGERSTROM, RegistrationStep.PROCHASKA):
            await update.message.reply_text(
                "📝 Пожалуйста, используйте кнопки для ответа на вопросы опросника.",
                parse_mode='Markdown'
            )
            return

    if await participant_service.exists(telegram_id):
        keyboard = await get_main_keyboard(telegram_id)
        await update.message.reply_text(
            "🤖 Используйте кнопки ниже для навигации:",
            reply_markup=keyboard
        )
        return

    await update.message.reply_text(
        "👋 Добро пожаловать!\n\n"
        "Для участия в исследовании нажмите /start",
        parse_mode='Markdown'
    )


async def post_init(application: Application):
    """Инициализация после запуска бота"""
    await database.init_db()
    logger.info("База данных инициализирована")


def main():
    logger.info("Запуск бота...")
    logger.info(f"Токен бота: {'установлен' if config.BOT_TOKEN else 'отсутствует'}")

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в файле .env")
        return

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # Глобальный обработчик ошибок
    app.add_error_handler(global_error_handler)

    # Регистрация
    app.add_handler(CommandHandler("start", registration_handlers.start))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_consent, pattern="^(consent_yes|consent_no)$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_gender, pattern="^(gender_male|gender_female)$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.start_fagerstrom, pattern="^start_fagerstrom$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.start_prochaska, pattern="^start_prochaska$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_back, pattern="^back_(fagerstrom|prochaska)$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_answer, pattern="^answer_"))

    # SOS-модуль
    app.add_handler(CommandHandler("sos", sos_command))
    app.add_handler(CallbackQueryHandler(sos_module_handlers.handle_technique, pattern="^sos_technique_"))
    app.add_handler(CallbackQueryHandler(sos_module_handlers.handle_new_techniques, pattern="^sos_new_techniques$"))
    app.add_handler(CallbackQueryHandler(sos_module_handlers.handle_helped, pattern="^sos_helped$"))
    app.add_handler(CallbackQueryHandler(sos_module_handlers.start_analysis, pattern="^analyze_craving$"))
    app.add_handler(CallbackQueryHandler(sos_module_handlers.begin_analysis, pattern="^begin_craving_analysis$"))

    # Главное меню
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex('^(🆘 SOS - Экстренная помощь|📊 Статус курения|ℹ️ Помощь)$'),
                       handle_main_menu))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_text_messages))

    logger.info("Бот запущен и готов к работе")
    logger.info("Для остановки нажмите Ctrl+C")

    app.run_polling()


if __name__ == '__main__':
    main()
