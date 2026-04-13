import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.exceptions import ValidationError
from src.services.participant_service import ParticipantService
from src.services.registration_orchestrator import RegistrationOrchestrator, QuestionData
from src.services.session_manager import RegistrationStep

logger = logging.getLogger(__name__)


class RegistrationHandlers:
    """Обработчики регистрации"""

    def __init__(
            self,
            orchestrator: RegistrationOrchestrator,
            participant_service: ParticipantService,
    ):
        self._orchestrator = orchestrator
        self._participant_service = participant_service
        self._text_step_handlers = {
            RegistrationStep.AGE: self.handle_age,
            RegistrationStep.SMOKING_YEARS: self.handle_smoking_years,
            RegistrationStep.CIGS_PER_DAY: self.handle_cigs_per_day,
        }

    async def handle_text_for_step(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            step: RegistrationStep
    ) -> None:
        """Обрабатывает текстовый ввод для указанного шага регистрации.

        Если шаг регистрации предполагает текстовый ответ, то используется соответствующий обработчик.
        В ином случае отправляется сообщение о необходимости использовать кнопки
        """
        handler = self._text_step_handlers.get(step)

        if handler:
            await handler(update, context)  # type: ignore
            return

        await update.message.reply_text(
            "📝 Пожалуйста, используйте кнопки для ответа.",
            parse_mode='Markdown'
        )

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

        await query.edit_message_text(
            "🚬 **Расскажите о вашем опыте курения**\n\n"
            "📝 **Сколько лет вы курите?**\n"
            f"(введите целое число лет)",
            parse_mode='Markdown'
        )

    async def handle_smoking_years(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id
        user_input = update.message.text

        try:
            years = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Пожалуйста, введите число:")
            return

        try:
            self._orchestrator.set_smoking_years(telegram_id, years)
        except ValidationError as e:
            await update.message.reply_text(str(e))
            return

        await update.message.reply_text(
            "📝 **Сколько сигарет в среднем вы выкуриваете в день?**\n"
            "(введите целое число от 0 до 100)",
            parse_mode='Markdown'
        )

    async def handle_cigs_per_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        telegram_id = update.effective_user.id
        user_input = update.message.text

        try:
            cigs = int(user_input)
        except ValueError:
            await update.message.reply_text("⚠️ Пожалуйста, введите число:")
            return

        try:
            self._orchestrator.set_cigs_per_day(telegram_id, cigs)
        except ValidationError as e:
            await update.message.reply_text(str(e))
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data="quit_attempts_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="quit_attempts_no")]
        ])
        await update.message.reply_text(
            "📝 **Были ли у вас попытки бросить курить ранее?**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_quit_attempts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        has_attempts = query.data == "quit_attempts_yes"
        self._orchestrator.set_quit_attempts(query.from_user.id, has_attempts)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data="vape_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="vape_no")]
        ])
        await query.edit_message_text(
            "📝 **Используете ли вы электронные сигареты/вейп?**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_vape_usage(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        uses_vape = query.data == "vape_yes"
        self._orchestrator.set_uses_vape(query.from_user.id, uses_vape)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data="smoker_household_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="smoker_household_no")]
        ])
        await query.edit_message_text(
            "📝 **Курит ли кто-то ещё у вас дома/в семье?**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_smoker_household(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        has_smoker = query.data == "smoker_household_yes"
        self._orchestrator.set_smoker_in_household(query.from_user.id, has_smoker)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data="medical_help_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="medical_help_no")],
            [InlineKeyboardButton("🤔 Не помню", callback_data="medical_help_not_sure")]
        ])
        await query.edit_message_text(
            "📝 **Получали ли вы ранее лекарственную помощь или консультацию врача для отказа от курения?**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def handle_medical_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        mapping = {
            "medical_help_yes": "Да",
            "medical_help_no": "Нет",
            "medical_help_not_sure": "Не помню"
        }
        answer = mapping.get(query.data, "Не помню")
        self._orchestrator.set_prior_medical_help(query.from_user.id, answer)

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ НАЧАТЬ ОПРОС", callback_data="start_fagerstrom")
        ]])
        await query.edit_message_text(
            "📋 **Отлично! Теперь заполним опросник никотиновой зависимости (Фагерстрём)**\n\n"
            "Это поможет нам лучше понять ваши привычки курения.\n"
            "Опросник состоит из 6 вопросов.\n\n"
            "Готовы начать?",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def start_fagerstrom(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        logger.info(f"Пользователь {query.from_user.id} начал опросник Фагерстрёма")

        self._orchestrator.start_questionnaire(query.from_user.id, 'fagerstrom')
        await self._send_current_question(query)

    async def start_prochaska(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
                await self._handle_fagerstrom_completion(query, telegram_id)
            elif q_type == 'prochaska':
                await self._handle_prochaska_completion(query, telegram_id)
        else:
            await self._send_current_question(query)

    async def _handle_fagerstrom_completion(self, query, telegram_id: int) -> None:
        result = self._orchestrator.complete_fagerstrom(telegram_id)
        logger.info(
            f"Пользователь {telegram_id} завершил Фагерстрём: {result.score}/10 ({result.level})"
        )

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

    async def _handle_prochaska_completion(self, query, telegram_id: int) -> None:
        result = self._orchestrator.complete_prochaska(telegram_id)
        logger.info(
            f"Пользователь {telegram_id} завершил Прохаску: {result.score}/8 ({result.level})"
        )

        participant = await self._orchestrator.finalize_registration(telegram_id)

        logger.info(
            f"Регистрация пользователя {telegram_id} завершена. "
            f"Код: {participant.participant_code}, Группа: {participant.group_name}"
        )

        await query.edit_message_text(
            f"✅ **РЕГИСТРАЦИЯ ЗАВЕРШЕНА!**\n\n"
            f"🆔 **Ваш код участника:** `{participant.participant_code}`\n"
            f"👥 **Ваша группа:** {participant.group_name}\n\n"
            f"💙 **Спасибо за участие в исследовании!**\n"
            f"Исследование начнется после выписки из стационара.",
            parse_mode='Markdown'
        )

    async def _send_current_question(self, query):
        q = self._orchestrator.get_current_question(query.from_user.id)
        keyboard = self._build_question_keyboard(q)
        await query.edit_message_text(
            f"📝 **Вопрос {q.number} из {q.total}**\n\n{q.text}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    @staticmethod
    def _build_question_keyboard(q: QuestionData) -> InlineKeyboardMarkup:
        keyboard = []
        for i, option in enumerate(q.options):
            callback = f"answer_{q.callback_prefix}_{q.number - 1}_{i}"
            keyboard.append([InlineKeyboardButton(option, callback_data=callback)])

        if q.can_go_back:
            keyboard.append([
                InlineKeyboardButton("◀️ Назад", callback_data=f"back_{q.callback_prefix}")
            ])

        return InlineKeyboardMarkup(keyboard)
