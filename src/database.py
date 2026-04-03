from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.asyncio.session import AsyncSession

from models import Base, Participant

DB_NAME = 'participants.db'
DATABASE_URL = f'sqlite+aiosqlite:///{DB_NAME}'

engine = create_async_engine(
    DATABASE_URL,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db() -> None:
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Контекстный менеджер для async сессии"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка БД: {e}")
            raise
        finally:
            await session.close()


async def save_participant(user_data: dict) -> None:
    """Сохраняет или обновляет данные участника"""
    async with get_db_session() as session:
        result = await session.execute(
            select(Participant).where(Participant.participant_code == user_data['participant_code'])
        )
        participant = result.scalar_one_or_none()

        if not participant:
            participant = Participant()
            session.add(participant)

        # Заполняем поля
        for key, value in user_data.items():
            if hasattr(participant, key):
                setattr(participant, key, value)

        await session.commit()

    print(f"✅ Данные сохранены: {user_data['participant_code']}")

async def get_participant_by_telegram_id(telegram_id: int) -> Optional[Participant]:
    """Возвращает участника по telegram_id"""
    async with get_db_session() as session:
        result = await session.execute(
            select(Participant).where(Participant.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def get_user_group(telegram_id: int) -> Optional[str]:
    """Получает группу пользователя"""
    async with get_db_session() as session:
        result = await session.execute(
            select(Participant.group_name).where(Participant.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

