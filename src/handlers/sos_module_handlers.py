import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.exceptions import ValidationError
from src.services.craving_analysis_orchestrator import CravingAnalysisOrchestrator
from src.services.participant_service import ParticipantService
from src.services.sos_usage_service import SOSUsageService
from src.services.techniques_service import TechniqueService

logger = logging.getLogger(__name__)


class SOSModuleHandlers:
    def __init__(
            self,
            techniques_service: TechniqueService,
            participant_service: ParticipantService,
            craving_analysis_orchestrator: CravingAnalysisOrchestrator,
            sos_usage_service: SOSUsageService,
    ):
        self._participant_service = participant_service
        self._techniques_service = techniques_service
        self._sos_usage_service = sos_usage_service
        self._analysis_orchestrator = craving_analysis_orchestrator

    async def show_sos_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню с техниками"""
        techniques = await self._techniques_service.get_sos_techniques(4)
        keyboard = []
        for technique in techniques:
            keyboard.append([
                InlineKeyboardButton(technique.name, callback_data=f"sos_technique_{technique.id}")
            ])
        keyboard.append([
            InlineKeyboardButton("📝 Проанализировать тягу", callback_data="analyze_craving")
        ])

        message_text = (
            "🆘 **ЭКСТРЕННАЯ ПОМОЩЬ ПРИ ТЯГЕ К КУРЕНИЮ**\n\n"
            "Тяга обычно длится 5-15 минут. Выберите технику для преодоления:\n\n"
            "💡 *Совет: Попробуйте технику, которую еще не использовали!*"
        )

        if update.message:
            await update.message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            query = update.callback_query
            await query.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def handle_technique(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбранную технику"""
        query = update.callback_query
        telegram_id = query.from_user.id
        await query.answer()

        technique_id = "_".join(query.data.split('_')[2:])
        technique = await self._techniques_service.get_technique_by_id(technique_id)
        participant = await self._participant_service.get_by_telegram_id(telegram_id)
        await self._sos_usage_service.create(participant.participant_code, technique_id)

        message = (
            f"🆘 **{technique.name}**\n\n"
            f"{technique.description}\n\n"
            f"💪 {self._techniques_service.get_craving_message()}\n\n"
            f"*Попробуйте эту технику прямо сейчас!*"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 Другая техника", callback_data="sos_new_techniques")],
            [InlineKeyboardButton("✅ Помогло!", callback_data="sos_helped")],
            [InlineKeyboardButton("📝 Затрудняюсь", callback_data="analyze_craving")]
        ]
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        logger.info(f"Участник {telegram_id} использовал технику: {technique.name}")

    async def handle_new_techniques(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает другие техники"""
        query = update.callback_query
        await query.answer()

        techniques = await self._techniques_service.get_sos_techniques(4)
        keyboard = []
        for technique in techniques:
            keyboard.append([
                InlineKeyboardButton(technique.name, callback_data=f"sos_technique_{technique.id}")
            ])
        keyboard.append([
            InlineKeyboardButton("📝 Проанализировать тягу", callback_data="analyze_craving")
        ])

        await query.edit_message_text(
            "🆘 **Выберите другую технику:**\n\n"
            "Иногда помогает попробовать что-то новое!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    @staticmethod
    async def handle_helped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает подтверждение, что техника помогла"""
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()

        await query.edit_message_text(
            "🎉 **Отлично! Вы справились с тягой!**\n\n"
            "Каждая такая победа делает вас сильнее и приближает к цели.\n\n"
            "💪 *Помните: вы способны контролировать свои привычки!*",
            parse_mode='Markdown'
        )
        logger.info(f"Участник {user_id} успешно справился с тягой")

    async def start_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запускает анализ тяги"""
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        self._analysis_orchestrator.start_analysis(user_id)

        await query.edit_message_text(
            "📝 **Давайте проанализируем вашу тягу**\n\n"
            "Это поможет лучше понимать свои триггеры и эффективнее с ними бороться.\n\n"
            "Я задам вам несколько вопросов. Отвечайте текстом.\n\n"
            "Готовы?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ НАЧАТЬ", callback_data="begin_craving_analysis")
            ]]),
            parse_mode='Markdown'
        )

    async def begin_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает задавать вопросы"""
        query = update.callback_query
        await query.answer()
        await self._send_current_question(query, query.from_user.id, is_callback=True)

    async def handle_analysis_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текстовый ответ во время анализа"""
        user_id = update.effective_user.id
        answer = update.message.text.strip()

        try:
            self._analysis_orchestrator.save_answer(user_id, answer)
        except ValidationError as e:
            await update.message.reply_text(str(e))
            return

        if self._analysis_orchestrator.is_completed(user_id):
            await self._complete_analysis(update)
        else:
            await self._send_current_question(update, user_id, is_callback=False)

    async def _send_current_question(self, update_or_query, user_id: int, is_callback: bool = True):
        """Отправляет текущий вопрос"""
        question = self._analysis_orchestrator.get_current_question(user_id)
        message_text = (
            f"📝 **Вопрос {question.number} из {question.total}**\n\n{question.text}\n\n"
            "Напишите ваш ответ текстом:"
        )

        if is_callback:
            await update_or_query.edit_message_text(message_text, parse_mode='Markdown')
        else:
            await update_or_query.message.reply_text(message_text, parse_mode='Markdown')

    async def _complete_analysis(self, update: Update):
        """Завершает анализ"""
        user_id = update.effective_user.id
        await self._analysis_orchestrator.finish_analysis(user_id)

        await update.message.reply_text(
            "📊 **Анализ завершён!**\n\n"
            "Теперь вы лучше понимаете свои триггеры. Используйте эти знания:\n\n"
            "• **Избегайте** ситуаций, провоцирующих тягу\n"
            "• **Подготовьте** техники для сложных моментов\n"
            "• **Гордитесь** тем, что анализируете свои привычки\n\n"
            "💪 *Осознанность — ключ к успешному отказу от курения!*",
            parse_mode='Markdown'
        )
        logger.info(f"Участник {user_id} завершил анализ тяги")
