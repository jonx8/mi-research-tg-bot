import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация приложения"""

    # Telegram Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')

    # Database
    DB_NAME = os.getenv('DB_NAME', 'participants.db')
    DATABASE_URL = f'sqlite+aiosqlite:///{DB_NAME}'

    # Интервалы для тестирования (в минутах)
    FOLLOW_UP_INTERVALS = [5, 10]  # 1 месяц = 5 мин, 3 месяца = 10 мин
    WEEKLY_CHECKIN_INTERVAL = 2  # 1 неделя = 2 минуты
    FINAL_SURVEY_INTERVAL = 15  # 6 месяцев = 15 минут

    # Для продакшена (в днях)
    # FOLLOW_UP_INTERVALS = [30 * 24 * 60, 90 * 24 * 60]  # 30 и 90 дней в минутах
    # WEEKLY_CHECKIN_INTERVAL = 7 * 24 * 60               # 7 дней в минутах
    # FINAL_SURVEY_INTERVAL = 180 * 24 * 60               # 180 дней в минутах

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')