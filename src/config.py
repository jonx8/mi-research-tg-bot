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

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')