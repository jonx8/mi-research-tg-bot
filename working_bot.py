import csv
import hashlib
import random
import secrets
import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import Config
from questionnaires import get_fagerstrom_questions, calculate_fagerstrom_score, get_prochaska_questions, \
    calculate_prochaska_score

config = Config()

# ==================== SQLite ====================
DB_NAME = 'participants.db'

def init_db():
    """Создаёт таблицу participants, если её нет"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            participant_code TEXT PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            group_name TEXT,
            registration_date TEXT,
            age INTEGER,
            gender TEXT,
            fagerstrom_score INTEGER,
            fagerstrom_level TEXT,
            prochaska_score INTEGER,
            prochaska_level TEXT,
            fagerstrom_1 INTEGER,
            fagerstrom_2 INTEGER,
            fagerstrom_3 INTEGER,
            fagerstrom_4 INTEGER,
            fagerstrom_5 INTEGER,
            fagerstrom_6 INTEGER,
            prochaska_1 INTEGER,
            prochaska_2 INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def save_participant(user_data):
    """Сохраняет или обновляет данные участника в БД"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT OR REPLACE INTO participants (
                participant_code, telegram_id, group_name, registration_date,
                age, gender, fagerstrom_score, fagerstrom_level,
                prochaska_score, prochaska_level,
                fagerstrom_1, fagerstrom_2, fagerstrom_3, fagerstrom_4, fagerstrom_5, fagerstrom_6,
                prochaska_1, prochaska_2
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data['participant_code'],
            user_data['user_id'],
            user_data['group'],
            user_data['registration_date'],
            user_data['age'],
            user_data['gender'],
            user_data['fagerstrom_score'],
            user_data['fagerstrom_level'],
            user_data['prochaska_score'],
            user_data['prochaska_level'],
            user_data.get('fagerstrom_1', 0),
            user_data.get('fagerstrom_2', 0),
            user_data.get('fagerstrom_3', 0),
            user_data.get('fagerstrom_4', 0),
            user_data.get('fagerstrom_5', 0),
            user_data.get('fagerstrom_6', 0),
            user_data.get('prochaska_1', 0),
            user_data.get('prochaska_2', 0)
        ))
        conn.commit()
        print(f"✅ Данные сохранены в БД: {user_data['participant_code']}, группа {user_data['group']}")
    except Exception as e:
        print(f"❌ Ошибка сохранения в БД: {e}")
    finally:
        conn.close()

def get_user_group(telegram_id: int) -> str:
    """Возвращает группу участника по telegram_id"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT group_name FROM participants WHERE telegram_id = ?', (telegram_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# ==================== Вспомогательные функции ====================
def generate_participant_code(telegram_id: int) -> str:
    """Генерация уникального обезличенного ID"""
    hash_input = f"{telegram_id}{secrets.token_hex(8)}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:10]

# ==================== Клавиатура ====================
def get_main_keyboard(user_id: int):
    """Возвращает основную клавиатуру в зависимости от группы пользователя"""
    user_group = get_user_group(user_id)
    if user_group == 'B':
        return ReplyKeyboardMarkup([
            [KeyboardButton("🆘 SOS - Экстренная помощь")],
            [KeyboardButton("📊 Статус курения"), KeyboardButton("ℹ️ Помощь")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            [KeyboardButton("📊 Статус курения"), KeyboardButton("ℹ️ Помощь")]
        ], resize_keyboard=True)

# ==================== SOS модуль (без изменений) ====================
class SOSModule:
    def __init__(self):
        self.sos_techniques = [
            {'name': '🧘 Дыхательное упражнение 4-7-8', 'description': '• Вдох через нос на 4 счета\n• Задержка дыхания на 7 счетов\n• Выдох через рот на 8 счетов\n• Повторить 3-4 раза', 'type': 'breathing'},
            {'name': '🚶 Отвлечься прогулкой', 'description': '• Выйти на 5-минутную прогулку\n• Сменить обстановку\n• Сделать 10 глубоких вдохов на свежем воздухе', 'type': 'physical'},
            {'name': '💧 Выпить стакан воды', 'description': '• Медленно выпить стакан холодной воды\n• Сосредоточиться на ощущениях\n• Это помогает "обмануть" привычку', 'type': 'distraction'},
            {'name': '🎯 Напомнить о причинах бросить', 'description': '• Вспомните почему вы начали бросать\n• Подумайте о преимуществах жизни без курения\n• Представьте себя здоровым некурящим человеком', 'type': 'motivational'},
            {'name': '🏃 Физическая активность', 'description': '• Сделать 10 приседаний\n• Отжаться от стены 10 раз\n• Любая короткая физическая активность', 'type': 'physical'},
            {'name': '🍎 Перекусить полезным', 'description': '• Съесть яблоко или морковку\n• Пожевать жевательную резинку\n• Выпить мятный чай', 'type': 'distraction'},
            {'name': '📱 Отвлечься на телефон', 'description': '• Сыграть в короткую игру\n• Почитать интересную статью\n• Посмотреть смешное видео', 'type': 'distraction'},
            {'name': '🎵 Послушать музыку', 'description': '• Включить любимую песню\n• Сосредоточиться на тексте и мелодии\n• Потанцевать 2-3 минуты', 'type': 'distraction'}
        ]
        self.craving_messages = [
            "Тяга пройдет через 5-10 минут! Держитесь! 💪",
            "Вы сильнее, чем вам кажется! Эта тяга скоро ослабнет 🌟",
            "Каждая победа над тягой делает вас сильнее! 🏆",
            "Помните: одна тяга не отменяет весь ваш прогресс! 📈",
            "Вы уже прошли такой путь! Не сдавайтесь сейчас! 🚀"
        ]

    def get_sos_techniques(self, count=4):
        return random.sample(self.sos_techniques, min(count, len(self.sos_techniques)))

    def get_craving_message(self):
        return random.choice(self.craving_messages)

    def get_craving_analysis_questions(self):
        return [
            "Что спровоцировало тягу? (ситуация, эмоции, место)",
            "Какие мысли были у вас в момент тяги?",
            "Что вы почувствовали физически?",
            "Какой способ помог справиться с тягой?"
        ]

sos_module = SOSModule()
user_data_store = {}

# ==================== Обработчики ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Проверяем, зарегистрирован ли пользователь
    user_group = get_user_group(user_id)
    if user_group:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('SELECT participant_code FROM participants WHERE telegram_id = ?', (user_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            keyboard = get_main_keyboard(user_id)
            await update.message.reply_text(
                f"ℹ️ Вы уже зарегистрированы в исследовании!\n\n"
                f"Ваш код участника: `{row[0]}`\n"
                f"Группа: {user_group}\n\n"
                "Исследование начнется после выписки из стационара.",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            return

    consent_text = """
🎯 **ДОБРО ПОЖАЛОВАТЬ В ИССЛЕДОВАНИЕ TELEGRAM-MI!**

Это исследование помощи в отказе от курения после перенесенного инфаркта миокарда.

**УСЛОВИЯ УЧАСТИЯ:**
• Исследование длится 6 месяцев
• Ваши данные полностью анонимны
• Вы можете выйти из исследования в любой момент
• Вам будет назначен один из двух типов поддержки

Вы согласны участвовать в исследовании?
    """
    keyboard = [
        [InlineKeyboardButton("✅ ДА, СОГЛАСЕН", callback_data="consent_yes")],
        [InlineKeyboardButton("❌ НЕТ, ОТКАЗЫВАЮСЬ", callback_data="consent_no")]
    ]
    await update.message.reply_text(consent_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "consent_yes":
        user_id = query.from_user.id
        user_data_store[user_id] = {
            'step': 'age',
            'fagerstrom_answers': {},
            'prochaska_answers': {},
            'current_questionnaire': None,
            'current_question_index': 0
        }
        await query.edit_message_text(
            "Отлично! Давайте начнем регистрацию.\n\n"
            "📝 **Введите ваш возраст:**\n"
            "(число от 18 до 120 лет)",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "Спасибо за ваше время! ❤️\n"
            "Если передумаете - просто напишите /start",
            parse_mode='Markdown'
        )

async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store or user_data_store[user_id].get('step') != 'age':
        await update.message.reply_text("Напишите /start чтобы начать регистрацию")
        return
    age_text = update.message.text
    try:
        age = int(age_text)
        if 18 <= age <= 120:
            user_data_store[user_id]['age'] = age
            user_data_store[user_id]['step'] = 'gender'
            keyboard = [
                [InlineKeyboardButton("👨 Мужской", callback_data="gender_male")],
                [InlineKeyboardButton("👩 Женский", callback_data="gender_female")]
            ]
            await update.message.reply_text(
                "👤 **Выберите ваш пол:**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("⚠️ Возраст должен быть от 18 до 120 лет. Попробуйте снова:")
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, введите число (например: 35):")

async def handle_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in user_data_store or user_data_store[user_id].get('step') != 'gender':
        await query.edit_message_text("Начните регистрацию заново с помощью /start")
        return
    gender = "Мужской" if query.data == "gender_male" else "Женский"
    user_data_store[user_id]['gender'] = gender
    user_data_store[user_id]['step'] = 'fagerstrom_start'
    await query.edit_message_text(
        "📋 **Теперь заполним опросник никотиновой зависимости (Фагерстрём)**\n\n"
        "Это поможет нам лучше понять ваши привычки курения.\n"
        "Опросник состоит из 6 вопросов.\n\n"
        "Готовы начать?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ НАЧАТЬ ОПРОС", callback_data="start_fagerstrom")
        ]]),
        parse_mode='Markdown'
    )

async def start_fagerstrom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    user_data_store[user_id]['current_questionnaire'] = 'fagerstrom'
    user_data_store[user_id]['current_question_index'] = 0
    user_data_store[user_id]['step'] = 'fagerstrom_questions'
    await send_next_question(update, context)

async def send_next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    current_data = user_data_store[user_id]
    questionnaire_type = current_data['current_questionnaire']
    question_index = current_data['current_question_index']

    if questionnaire_type == 'fagerstrom':
        questions = get_fagerstrom_questions()
    else:
        questions = get_prochaska_questions()

    if question_index < len(questions):
        question = questions[question_index]
        keyboard = []
        for i, option in enumerate(question['options']):
            callback_data = f"answer_{questionnaire_type}_{question_index}_{i}"
            keyboard.append([InlineKeyboardButton(option, callback_data=callback_data)])
        if question_index > 0:
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"back_{questionnaire_type}")])
        message_text = f"📝 **Вопрос {question['number']} из {len(questions)}**\n\n{question['question']}"
        await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        if questionnaire_type == 'fagerstrom':
            await complete_fagerstrom(update, context)
        else:
            await complete_prochaska(update, context)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    parts = query.data.split('_')
    questionnaire_type = parts[1]
    question_index = int(parts[2])
    answer_index = int(parts[3])
    current_data = user_data_store[user_id]
    questions = get_fagerstrom_questions() if questionnaire_type == 'fagerstrom' else get_prochaska_questions()
    question = questions[question_index]
    score = question['scores'][answer_index]
    current_data[f'{questionnaire_type}_answers'][question['field']] = score
    current_data['current_question_index'] += 1
    await send_next_question(update, context)

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    current_data = user_data_store[user_id]
    current_data['current_question_index'] = max(0, current_data['current_question_index'] - 1)
    await send_next_question(update, context)

async def complete_fagerstrom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    answers = user_data_store[user_id]['fagerstrom_answers']
    total_score, level = calculate_fagerstrom_score(answers)
    user_data_store[user_id]['fagerstrom_score'] = total_score
    user_data_store[user_id]['fagerstrom_level'] = level
    await query.edit_message_text(
        f"📊 **Результаты теста Фагерстрёма:**\n\n"
        f"• **Общий балл:** {total_score}/10\n"
        f"• **Уровень зависимости:** {level}\n\n"
        "Теперь заполним опросник мотивации...",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("➡️ ПРОДОЛЖИТЬ", callback_data="start_prochaska")
        ]]),
        parse_mode='Markdown'
    )

async def start_prochaska(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    user_data_store[user_id]['current_questionnaire'] = 'prochaska'
    user_data_store[user_id]['current_question_index'] = 0
    user_data_store[user_id]['step'] = 'prochaska_questions'
    await query.edit_message_text(
        "💭 **Опросник мотивации к отказу от курения (Прохаски)**\n\n"
        "Этот опросник поможет оценить вашу готовность к изменениям.\n"
        "Состоит из 2 вопросов.\n\n"
        "Начинаем?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ НАЧАТЬ ОПРОС", callback_data="send_prochaska_question")
        ]]),
        parse_mode='Markdown'
    )

async def complete_prochaska(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    answers = user_data_store[user_id]['prochaska_answers']
    total_score, level = calculate_prochaska_score(answers)
    user_data_store[user_id]['prochaska_score'] = total_score
    user_data_store[user_id]['prochaska_level'] = level
    await complete_registration(update, context)

async def complete_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    participant_code = generate_participant_code(user_id)
    group = 'A' if random.random() < 0.5 else 'B'
    user_data = {
        'participant_code': participant_code,
        'user_id': user_id,
        'group': group,
        'registration_date': datetime.now().isoformat(),
        'age': user_data_store[user_id]['age'],
        'gender': user_data_store[user_id]['gender'],
        'fagerstrom_score': user_data_store[user_id]['fagerstrom_score'],
        'fagerstrom_level': user_data_store[user_id]['fagerstrom_level'],
        'prochaska_score': user_data_store[user_id]['prochaska_score'],
        'prochaska_level': user_data_store[user_id]['prochaska_level'],
    }
    user_data.update(user_data_store[user_id]['fagerstrom_answers'])
    user_data.update(user_data_store[user_id]['prochaska_answers'])
    save_participant(user_data)
    keyboard = get_main_keyboard(user_id)
    final_message = (
        f"✅ **РЕГИСТРАЦИЯ ЗАВЕРШЕНА!**\n\n"
        f"🆔 **Ваш код участника:** `{participant_code}`\n\n"
        f"💙 **Спасибо за участие в исследовании!**\n"
        f"Исследование начнется после выписки из стационара."
    )
    await query.edit_message_text(final_message, parse_mode='Markdown')
    await context.bot.send_message(
        chat_id=user_id,
        text="Теперь вы можете использовать кнопки ниже для взаимодействия с ботом:",
        reply_markup=keyboard
    )
    if user_id in user_data_store:
        del user_data_store[user_id]
    print(f"🎉 Новый участник: {participant_code}, Группа: {group}")

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user_group = get_user_group(user_id)
    if text == "🆘 SOS - Экстренная помощь":
        if user_group == 'B':
            await show_sos_menu(update, context)
        else:
            await update.message.reply_text(
                "ℹ️ **Вам назначен базовый тип поддержки**\n\n"
                "Вы будете получать периодические опросы о вашем статусе курения.\n\n"
                "Спасибо за участие в исследовании!",
                reply_markup=get_main_keyboard(user_id)
            )
    elif text == "📊 Статус курения":
        await update.message.reply_text(
            "📊 **Отслеживание статуса курения**\n\n"
            "Эта функция будет доступна после начала исследования.\n\n"
            "Вы будете получать регулярные опросы о вашем прогрессе.",
            reply_markup=get_main_keyboard(user_id)
        )
    elif text == "ℹ️ Помощь":
        await update.message.reply_text(
            "ℹ️ **Помощь**\n\n"
            "Этот бот создан для исследования TELEGRAM-MI по поддержке отказа от курения "
            "после перенесенного инфаркта миокарда.\n\n"
            "Доступные команды:\n"
            "• /start - начать регистрацию\n"
            "• /sos - экстренная помощь при тяге (только для группы B)\n\n"
            "Если у вас есть вопросы, обращайтесь к исследователям.",
            reply_markup=get_main_keyboard(user_id)
        )

async def show_sos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    techniques = sos_module.get_sos_techniques(4)
    keyboard = []
    for technique in techniques:
        keyboard.append([InlineKeyboardButton(technique['name'], callback_data=f"sos_technique_{techniques.index(technique)}")])
    keyboard.append([InlineKeyboardButton("📝 Проанализировать тягу", callback_data="analyze_craving")])
    if update.message:
        await update.message.reply_text(
            "🆘 **ЭКСТРЕННАЯ ПОМОЩЬ ПРИ ТЯГЕ К КУРЕНИЮ**\n\n"
            "Тяга обычно длится 5-15 минут. Выберите технику для преодоления:\n\n"
            "💡 *Совет: Попробуйте технику, которую еще не использовали!*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        query = update.callback_query
        await query.edit_message_text(
            "🆘 **ЭКСТРЕННАЯ ПОМОЩЬ ПРИ ТЯГЕ К КУРЕНИЮ**\n\n"
            "Тяга обычно длится 5-15 минут. Выберите технику для преодоления:\n\n"
            "💡 *Совет: Попробуйте технику, которую еще не использовали!*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def sos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_group = get_user_group(user_id)
    if not user_group:
        await update.message.reply_text(
            "ℹ️ **Вы не зарегистрированы в исследовании**\n\n"
            "Для участия в исследовании зарегистрируйтесь с помощью команды /start",
            parse_mode='Markdown'
        )
        return
    if user_group == 'A':
        await update.message.reply_text(
            "ℹ️ **Вам назначен базовый тип поддержки**\n\n"
            "Вы будете получать периодические опросы о вашем статусе курения.\n\n"
            "Спасибо за участие в исследовании!",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )
        return
    await show_sos_menu(update, context)

async def handle_sos_technique(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    technique_index = int(query.data.split('_')[-1])
    techniques = sos_module.get_sos_techniques(4)
    if technique_index < len(techniques):
        technique = techniques[technique_index]
        message = (
            f"🆘 **{technique['name']}**\n\n"
            f"{technique['description']}\n\n"
            f"💪 {sos_module.get_craving_message()}\n\n"
            f"*Попробуйте эту технику прямо сейчас!*"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 Другая техника", callback_data="sos_new_techniques")],
            [InlineKeyboardButton("✅ Помогло!", callback_data="sos_helped")],
            [InlineKeyboardButton("📝 Затрудняюсь", callback_data="analyze_craving")]
        ]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        print(f"🆘 Участник {user_id} использовал технику: {technique['name']}")

async def handle_sos_new_techniques(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    techniques = sos_module.get_sos_techniques(4)
    keyboard = []
    for technique in techniques:
        keyboard.append([InlineKeyboardButton(technique['name'], callback_data=f"sos_technique_{techniques.index(technique)}")])
    keyboard.append([InlineKeyboardButton("📝 Проанализировать тягу", callback_data="analyze_craving")])
    await query.edit_message_text(
        "🆘 **Выберите другую технику:**\n\n"
        "Иногда помогает попробовать что-то новое!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_sos_helped(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    await query.edit_message_text(
        "🎉 **Отлично! Вы справились с тягой!**\n\n"
        "Каждая такая победа делает вас сильнее и приближает к цели.\n\n"
        "💪 *Помните: вы способны контролировать свои привычки!*",
        parse_mode='Markdown'
    )
    print(f"✅ Участник {user_id} успешно справился с тягой")

async def handle_analyze_craving(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    questions = sos_module.get_craving_analysis_questions()
    if user_id not in user_data_store:
        user_data_store[user_id] = {}
    user_data_store[user_id]['craving_analysis'] = {
        'step': 0,
        'questions': questions,
        'answers': []
    }
    await query.edit_message_text(
        "📝 **Давайте проанализируем вашу тягу**\n\n"
        "Это поможет лучше понимать свои триггеры и эффективнее с ними бороться.\n\n"
        f"**Вопрос 1 из {len(questions)}:**\n{questions[0]}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ Ответить", callback_data="start_craving_analysis")
        ]]),
        parse_mode='Markdown'
    )

async def start_craving_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in user_data_store or 'craving_analysis' not in user_data_store[user_id]:
        await query.edit_message_text("Начните анализ заново через команду /sos")
        return
    analysis_data = user_data_store[user_id]['craving_analysis']
    analysis_data['step'] = 0
    await query.edit_message_text(
        f"**Вопрос 1 из {len(analysis_data['questions'])}:**\n"
        f"{analysis_data['questions'][0]}\n\n"
        "Напишите ваш ответ:",
        parse_mode='Markdown'
    )

async def handle_craving_analysis_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data_store or 'craving_analysis' not in user_data_store[user_id]:
        await update.message.reply_text("Начните анализ заново через команду /sos")
        return
    analysis_data = user_data_store[user_id]['craving_analysis']
    current_step = analysis_data['step']
    analysis_data['answers'].append(update.message.text)
    if current_step + 1 < len(analysis_data['questions']):
        analysis_data['step'] += 1
        await update.message.reply_text(
            f"**Вопрос {current_step + 2} из {len(analysis_data['questions'])}:**\n"
            f"{analysis_data['questions'][current_step + 1]}\n\n"
            "Напишите ваш ответ:",
            parse_mode='Markdown'
        )
    else:
        await complete_craving_analysis(update, context)

async def complete_craving_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    analysis_data = user_data_store[user_id]['craving_analysis']
    # Сохраняем анализ в файл (можно позже перенести в БД)
    try:
        with open('craving_analysis.csv', 'a', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                headers = ['User ID', 'Timestamp']
                for i in range(len(analysis_data['questions'])):
                    headers.append(f'Q{i+1}')
                writer.writerow(headers)
            row_data = [user_id, datetime.now().isoformat()]
            row_data.extend(analysis_data['answers'])
            writer.writerow(row_data)
    except Exception as e:
        print(f"Ошибка при сохранении анализа тяги: {e}")
    await update.message.reply_text(
        "📊 **Анализ завершен!**\n\n"
        "Теперь вы лучше понимаете свои триггеры. Используйте эти знания:\n\n"
        "• **Избегайте** ситуаций, провоцирующих тягу\n"
        "• **Подготовьте** техники для сложных моментов\n"
        "• **Гордитесь** тем, что анализируете свои привычки\n\n"
        "💪 *Осознанность - ключ к успешному отказу от курения!*",
        parse_mode='Markdown'
    )
    if user_id in user_data_store and 'craving_analysis' in user_data_store[user_id]:
        del user_data_store[user_id]['craving_analysis']
    print(f"📝 Участник {user_id} завершил анализ тяги")

async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        current_step = user_data_store[user_id].get('step')
        if current_step == 'age':
            await update.message.reply_text("Пожалуйста, введите ваш возраст (число от 18 до 120):")
            return
    keyboard = get_main_keyboard(user_id)
    await update.message.reply_text(
        "🤖 **Бот исследования TELEGRAM-MI**\n\n"
        "Используйте кнопки ниже для навигации.\n\n"
        "Доступные команды:\n"
        "• /start - начать регистрацию\n"
        "• /sos - экстренная помощь при тяге",
        parse_mode='Markdown',
        reply_markup=keyboard
    )

# ==================== Main ====================
def main():
    print("🔄 Запускаю бота с обновленной клавиатурой...")
    print(f"📁 Токен бота: {'✅ Установлен' if config.BOT_TOKEN else '❌ Отсутствует'}")
    if not config.BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден в файле .env")
        return

    init_db()  # инициализация базы данных

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_consent, pattern="^(consent_yes|consent_no)$"))
    app.add_handler(CallbackQueryHandler(handle_gender, pattern="^(gender_male|gender_female)$"))
    app.add_handler(CallbackQueryHandler(start_fagerstrom, pattern="^start_fagerstrom$"))
    app.add_handler(CallbackQueryHandler(start_prochaska, pattern="^start_prochaska$"))
    app.add_handler(CallbackQueryHandler(handle_back, pattern="^back_(fagerstrom|prochaska)$"))
    app.add_handler(CallbackQueryHandler(send_next_question, pattern="^send_prochaska_question$"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^answer_"))
    app.add_handler(CommandHandler("sos", sos_command))
    app.add_handler(CallbackQueryHandler(handle_sos_technique, pattern="^sos_technique_"))
    app.add_handler(CallbackQueryHandler(handle_sos_new_techniques, pattern="^sos_new_techniques$"))
    app.add_handler(CallbackQueryHandler(handle_sos_helped, pattern="^sos_helped$"))
    app.add_handler(CallbackQueryHandler(handle_analyze_craving, pattern="^analyze_craving$"))
    app.add_handler(CallbackQueryHandler(start_craving_analysis, pattern="^start_craving_analysis$"))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex('^(🆘 SOS - Экстренная помощь|📊 Статус курения|ℹ️ Помощь)$'), handle_main_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_craving_analysis_answer))
    app.add_handler(MessageHandler(filters.ALL, handle_unknown_message))

    print("✅ Бот с обновленной клавиатурой запущен!")
    print("🆘 Кнопка SOS теперь доступна только для группы B")
    print("⏹️  Для остановки нажмите Ctrl+C")
    print("=" * 50)

    app.run_polling()

if __name__ == '__main__':
    main()