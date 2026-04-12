import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.services.registration_orchestrator import RegistrationOrchestrator, QuestionData
from src.services.participant_service import ParticipantService
from src.exceptions import ValidationError

logger = logging.getLogger(__name__)


class RegistrationHandlers:
    """Обработчики регистрации"""

    def __init__(
            self,
            orchestrator: RegistrationOrchestrator,
            participant_service: ParticipantService
    ):
        self._orchestrator = orchestrator
        self._participant_service = participant_service

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id
        logger.info(f"Команда /start от пользователя {telegram_id}")

        if await self._participant_service.exists(telegram_id):
            participant = await self._participant_service.get_by_telegram_id(telegram_id)
            logger.info(f"Пользователь {telegram_id} уже зарегистрирован (код: {participant.participant_code})")
            await update.message.reply_text(
                f"✅ Вы уже зарегистрированы!\n"
                f"Код: `{participant.participant_code}`\n"
                f"Группа: {participant.group_name}",
                parse_mode='Markdown'
            )
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ ДА, СОГЛАСЕН", callback_data="consent_yes")],
            [InlineKeyboardButton("❌ НЕТ, ОТКАЗЫВАЮСЬ", callback_data="consent_no")]
        ])
        await update.message.reply_text(
            "🎯 **ДОБРО ПОЖАЛОВАТЬ В ИССЛЕДОВАНИЕ TELEGRAM-MI!**\n\n"
            "Это исследование помощи в отказе от курения после перенесенного инфаркта миокарда.\n\n"
            "**УСЛОВИЯ УЧАСТИЯ:**\n"
            "• Исследование длится 6 месяцев\n"
            "• Ваши данные полностью анонимны\n"
            "• Вы можете выйти из исследования в любой момент\n\n"
            "Вы согласны участвовать в исследовании?",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_consent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "consent_yes":
            logger.info(f"Пользователь {query.from_user.id} дал согласие на участие")
            self._orchestrator.start_registration(query.from_user.id)
            await query.edit_message_text(
                "Отлично! Давайте начнем регистрацию.\n\n"
                "📝 **Введите ваш возраст:**\n"
                "(число от 18 до 120 лет)",
                parse_mode='Markdown'
            )
        else:
            logger.info(f"Пользователь {query.from_user.id} отказался от участия")
            await query.edit_message_text(
                "Спасибо за ваше время! ❤️\nЕсли передумаете - просто напишите /start"
            )

    async def handle_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id
        user_input = update.message.text

        try:
            age = int(user_input)
        except ValueError:
            logger.warning(f"Некорректный ввод возраста от {telegram_id}: '{user_input}'")
            await update.message.reply_text("⚠️ Пожалуйста, введите число (например: 35):")
            return

        try:
            self._orchestrator.set_age(telegram_id, age)
            logger.info(f"Установлен возраст для {telegram_id}: {age} лет")
        except ValidationError as e:
            logger.warning(f"Ошибка валидации возраста от {telegram_id}: {e}")
            await update.message.reply_text(str(e))
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👨 Мужской", callback_data="gender_male")],
            [InlineKeyboardButton("👩 Женский", callback_data="gender_female")]
        ])
        await update.message.reply_text(
            "👤 **Выберите ваш пол:**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        try:
            self._orchestrator.set_gender(query.from_user.id, query.data)
            logger.info(f"Установлен пол для {query.from_user.id}: {query.data}")
        except ValidationError as e:
            logger.warning(f"Ошибка валидации пола от {query.from_user.id}: {e}")
            await query.edit_message_text(str(e))
            return

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ НАЧАТЬ ОПРОС", callback_data="start_fagerstrom")
        ]])
        await query.edit_message_text(
            "📋 **Теперь заполним опросник никотиновой зависимости (Фагерстрём)**\n\n"
            "Это поможет нам лучше понять ваши привычки курения.\n"
            "Опросник состоит из 6 вопросов.\n\n"
            "Готовы начать?",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def start_fagerstrom(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запускает опросник Фагерстрёма"""
        query = update.callback_query
        await query.answer()

        logger.info(f"Пользователь {query.from_user.id} начал опросник Фагерстрёма")

        self._orchestrator.start_questionnaire(query.from_user.id, 'fagerstrom')
        await self._send_current_question(query)

    async def start_prochaska(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Запускает опросник Прохаски"""
        query = update.callback_query
        await query.answer()

        logger.info(f"Пользователь {query.from_user.id} начал опросник Прохаски")

        self._orchestrator.start_questionnaire(query.from_user.id, 'prochaska')
        await self._send_current_question(query)

    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id

        try:
            self._orchestrator.go_to_previous_question(telegram_id)
        except ValidationError as e:
            logger.warning(f"Ошибка при возврате к вопросу от {telegram_id}: {e}")
            await query.answer(str(e), show_alert=True)
            return

        await self._send_current_question(query)

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        telegram_id = query.from_user.id

        parts = query.data.split('_')
        q_type = parts[1]
        q_idx = int(parts[2])
        ans_idx = int(parts[3])

        self._orchestrator.save_answer(telegram_id, q_type, q_idx, ans_idx)

        if self._orchestrator.is_questionnaire_completed(telegram_id, q_type):
            if q_type == 'fagerstrom':
                result = self._orchestrator.complete_fagerstrom(telegram_id)
                logger.info(
                    f"Пользователь {telegram_id} завершил Фагерстрём с результатом: {result.score}/10 ({result.level})")
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("➡️ ПРОДОЛЖИТЬ", callback_data="start_prochaska")
                ]])
                await query.edit_message_text(
                    f"📊 **Результаты теста Фагерстрёма:**\n\n"
                    f"• **Общий балл:** {result.score}/10\n"
                    f"• **Уровень зависимости:** {result.level}\n\n"
                    "Теперь заполним опросник мотивации...",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                self._orchestrator.complete_prochaska(telegram_id)
                participant = await self._orchestrator.finalize_registration(telegram_id)
                logger.info(
                    f"Регистрация пользователя {telegram_id} завершена. Код: {participant.participant_code}, Группа: {participant.group_name}")
                await query.edit_message_text(
                    f"✅ **РЕГИСТРАЦИЯ ЗАВЕРШЕНА!**\n\n"
                    f"🆔 **Ваш код участника:** `{participant.participant_code}`\n"
                    f"👥 **Ваша группа:** {participant.group_name}\n\n"
                    f"💙 **Спасибо за участие в исследовании!**\n"
                    f"Исследование начнется после выписки из стационара.",
                    parse_mode='Markdown'
                )
        else:
            await self._send_current_question(query)

    async def _send_current_question(self, query):
        """Отправляет текущий вопрос"""
        q = self._orchestrator.get_current_question(query.from_user.id)
        keyboard = self._build_question_keyboard(q)
        await query.edit_message_text(
            f"📝 **Вопрос {q.number} из {q.total}**\n\n{q.text}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    @staticmethod
    def _build_question_keyboard(q: QuestionData) -> InlineKeyboardMarkup:
        """Строит клавиатуру для вопроса"""
        keyboard = []
        for i, option in enumerate(q.options):
            callback = f"answer_{q.callback_prefix}_{q.number - 1}_{i}"
            keyboard.append([InlineKeyboardButton(option, callback_data=callback)])

        if q.can_go_back:
            keyboard.append([
                InlineKeyboardButton("◀️ Назад", callback_data=f"back_{q.callback_prefix}")
            ])

        return InlineKeyboardMarkup(keyboard)

    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id

        if self._orchestrator.is_registration_active(telegram_id):
            step = self._orchestrator.get_current_step(telegram_id)
            if step and step.value == 'age':
                await self.handle_age(update, context)
                return

        await update.message.reply_text(
            "Используйте /start для начала регистрации или кнопки меню для навигации."
        )
