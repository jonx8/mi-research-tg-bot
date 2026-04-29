import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from scripts.seed_techniques import seed_techniques
from src.config import Config
from src.database import Database
from src.handlers.daily_log_handlers import DailyLogHandlers
from src.handlers.final_survey_handlers import FinalSurveyHandlers
from src.handlers.follow_up_survey_handlers import FollowUpSurveyHandlers
from src.handlers.global_error_handler import global_error_handler
from src.handlers.registration_handlers import RegistrationHandlers
from src.handlers.sos_module_handlers import SOSModuleHandlers
from src.handlers.weekly_check_in_handlers import WeeklyCheckInHandlers
from src.logging_config import setup_logging
from src.repositories.baseline_repo import BaselineQuestionnaireRepository
from src.repositories.craving_analysis_repo import CravingAnalysisRepository
from src.repositories.daily_log_repo import DailyLogRepository
from src.repositories.final_repo import FinalSurveyRepository
from src.repositories.follow_up_repo import FollowUpRepository
from src.repositories.morning_tips_repo import MorningTipRepository
from src.repositories.participant_repo import ParticipantRepository
from src.repositories.sos_usage_repo import SOSUsageRepository
from src.repositories.technique_repo import TechniqueRepository
from src.repositories.weekly_check_in_repo import WeeklyCheckInRepository
from src.schedulers.scheduler import SchedulerService
from src.services.baseline_questionnaire_service import BaselineQuestionnaireService
from src.services.craving_analysis_orchestrator import CravingAnalysisOrchestrator
from src.services.craving_analysis_service import CravingAnalysisService
from src.services.daily_log_sender import DailyLogSender
from src.services.daily_log_service import DailyLogService
from src.services.final_service import FinalSurveyService
from src.services.follow_up_service import FollowUpService
from src.services.google_sheets_exporter import GoogleSheetsExporter
from src.services.participant_service import ParticipantService
from src.services.registration_orchestrator import RegistrationOrchestrator
from src.services.session_manager import SessionManager
from src.services.sos_usage_service import SOSUsageService
from src.services.techniques_service import TechniqueService
from src.services.weekly_check_in_service import WeeklyCheckInService
from src.utils.batch_sender import BatchSender

config = Config()
setup_logging(config)

logger = logging.getLogger(__name__)

database = Database(config.DATABASE_URL)

batch_sender = BatchSender()

participant_repo = ParticipantRepository(database)
baseline_repo = BaselineQuestionnaireRepository(database)
follow_up_repo = FollowUpRepository(database)
weekly_checkin_repo = WeeklyCheckInRepository(database)
daily_log_repo = DailyLogRepository(database)
final_survey_repo = FinalSurveyRepository(database)
morning_tip_repo = MorningTipRepository(database)
technique_repo = TechniqueRepository(database)
sos_usage_repo = SOSUsageRepository(database)
craving_analysis_repo = CravingAnalysisRepository(database)

participant_service = ParticipantService(participant_repo)
baseline_service = BaselineQuestionnaireService(baseline_repo)
follow_up_service = FollowUpService(follow_up_repo)
weekly_checkin_service = WeeklyCheckInService(weekly_checkin_repo)
final_survey_service = FinalSurveyService(final_survey_repo)
technique_service = TechniqueService(technique_repo)
daily_log_service = DailyLogService(daily_log_repo)
sos_usage_service = SOSUsageService(sos_usage_repo)
craving_analysis_service = CravingAnalysisService(craving_analysis_repo)

session_manager = SessionManager()
registration_orchestrator = RegistrationOrchestrator(
    session_manager,
    participant_service,
    baseline_service,
    follow_up_service,
    weekly_checkin_service,
    final_survey_service,
    config
)
craving_analysis_orchestrator = CravingAnalysisOrchestrator(
    session_manager,
    craving_analysis_service,
    participant_service
)

registration_handlers = RegistrationHandlers(registration_orchestrator, participant_service)
sos_module_handlers = SOSModuleHandlers(
    technique_service,
    participant_service,
    craving_analysis_orchestrator,
    sos_usage_service
)
follow_up_handlers = FollowUpSurveyHandlers(follow_up_service)
weekly_checkin_handlers = WeeklyCheckInHandlers(weekly_checkin_service)
final_survey_handlers = FinalSurveyHandlers(final_survey_service)
daily_log_handlers = DailyLogHandlers(daily_log_service)


async def sos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await participant_service.exists(user_id):
        await update.message.reply_text(
            "❌ Вы не зарегистрированы в исследовании.\n\n"
            "Нажмите /start для регистрации.",
            parse_mode='Markdown'
        )
        return

    user_group = await participant_service.get_group(user_id)
    if user_group == 'A':
        keyboard = await participant_service.get_main_keyboard(user_id)
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
            keyboard = await participant_service.get_main_keyboard(user_id)
            await update.message.reply_text(
                "ℹ️ **Вам назначен базовый тип поддержки**\n\n"
                "Вы будете получать периодические опросы о вашем статусе курения.\n\n"
                "Спасибо за участие в исследовании!",
                reply_markup=keyboard
            )
    elif text == "📊 Статус курения":
        keyboard = await participant_service.get_main_keyboard(user_id)
        await update.message.reply_text(
            "📊 **Отслеживание статуса курения**\n\n"
            "Эта функция будет доступна после начала исследования.\n\n"
            "Вы будете получать регулярные опросы о вашем прогрессе.",
            reply_markup=keyboard
        )
    elif text == "ℹ️ Помощь":
        keyboard = await participant_service.get_main_keyboard(user_id)
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
    if session and session.step:
        await registration_handlers.handle_text_for_step(update, context, session.step)
        return

    if 'pending_follow_up_id' in context.user_data:
        await follow_up_handlers.handle_follow_up_cigs_input(update, context)
        return

    if 'pending_weekly_id' in context.user_data and 'weekly_craving' not in context.user_data:
        await weekly_checkin_handlers.handle_weekly_craving_input(update, context)
        return

    if 'final_survey_id' in context.user_data:
        step = context.user_data.get('final_step')
        if step == 'cigs_per_day':
            await final_survey_handlers.handle_final_cigs_input(update, context)
            return
        elif step == 'days_to_lapse':
            await final_survey_handlers.handle_final_days_input(update, context)
            return

    if await participant_service.exists(telegram_id):
        keyboard = await participant_service.get_main_keyboard(telegram_id)
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
    await seed_techniques()
    logger.info("База данных инициализирована")


def main():
    logger.info("Запуск бота...")
    logger.info(f"Токен бота: {'установлен' if config.BOT_TOKEN else 'отсутствует'}")

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в файле .env")
        return

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Глобальный обработчик ошибок
    app.add_error_handler(global_error_handler)

    # Регистрация
    app.add_handler(CommandHandler("start", registration_handlers.start))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_consent, pattern="^(consent_yes|consent_no)$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_gender, pattern="^(gender_male|gender_female)$"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_quit_attempts, pattern="^quit_attempts_"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_vape_usage, pattern="^vape_"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_smoker_household, pattern="^smoker_household_"))
    app.add_handler(CallbackQueryHandler(registration_handlers.handle_medical_help, pattern="^medical_help_"))
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

    # Ежедневный опрос
    app.add_handler(CallbackQueryHandler(daily_log_handlers.handle_evening_response, pattern="^daily_"))

    # Промежуточные опросы
    app.add_handler(CallbackQueryHandler(follow_up_handlers.handle_follow_up_answer, pattern="^followup_"))

    # Еженедельные чек-ины
    app.add_handler(CallbackQueryHandler(weekly_checkin_handlers.handle_weekly_status, pattern="^weekly_.*_status_"))
    app.add_handler(CallbackQueryHandler(weekly_checkin_handlers.handle_weekly_mood, pattern="^weekly_.*_mood_"))

    # Финальный опрос
    app.add_handler(CallbackQueryHandler(final_survey_handlers.handle_final_survey_start, pattern="^final_.*_ppa30_"))
    app.add_handler(CallbackQueryHandler(final_survey_handlers.handle_final_ppa7, pattern="^final_.*_ppa7_"))
    app.add_handler(CallbackQueryHandler(final_survey_handlers.handle_final_quit_attempt, pattern="^final_.*_quit_"))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_text_messages))

    daily_log_sender = DailyLogSender(app.bot, daily_log_repo, participant_repo, morning_tip_repo, batch_sender)

    google_sheets_exporter = None
    if config.GOOGLE_SHEETS_SPREADSHEET_ID:
        try:
            google_sheets_exporter = GoogleSheetsExporter(
                credentials_path=config.GOOGLE_SHEETS_CREDENTIALS_PATH,
                spreadsheet_id=config.GOOGLE_SHEETS_SPREADSHEET_ID,
                database=database
            )
            logger.info("Google Sheets экспортер инициализирован")
        except Exception as e:
            logger.warning(f"Не удалось инициализировать Google Sheets экспортер: {e}")

    scheduler = SchedulerService(
        bot=app.bot,
        config=config,
        follow_up_repo=follow_up_repo,
        weekly_check_in_repo=weekly_checkin_repo,
        final_repo=final_survey_repo,
        daily_log_sender=daily_log_sender,
        google_sheets_exporter=google_sheets_exporter
    )

    scheduled_survey_check = lambda context: scheduler.process_all_pending()
    scheduled_daily_log_check = lambda context: scheduler.process_daily_logs()
    scheduled_google_sheets_export = lambda context: scheduler.export_to_google_sheets()

    job_queue = app.job_queue
    job_queue.run_repeating(scheduled_survey_check, interval=5, first=5)
    job_queue.run_repeating(scheduled_daily_log_check, interval=5, first=5)
    if google_sheets_exporter:
        job_queue.run_repeating(
            scheduled_google_sheets_export,
            interval=config.GOOGLE_SHEETS_EXPORT_INTERVAL,
            first=10
        )
        logger.info(
            f"Планировщик экспорта в Google Sheets запущен (интервал: {config.GOOGLE_SHEETS_EXPORT_INTERVAL} сек)")

    logger.info("Бот запущен и готов к работе")
    logger.info("Для остановки нажмите Ctrl+C")

    app.run_polling()


if __name__ == '__main__':
    main()
