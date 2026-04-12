import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация приложения"""

    BOT_TOKEN = os.getenv('BOT_TOKEN')

    DB_NAME = os.getenv('DB_NAME', 'participants.db')
    DATABASE_URL = f'sqlite+aiosqlite:///{DB_NAME}'
