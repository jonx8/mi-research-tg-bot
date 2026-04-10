import asyncio
import json
from pathlib import Path

from sqlalchemy import delete

from src.database import get_db_session
from src.models import Technique


async def seed_techniques():
    """Загружает техники из JSON файла в БД"""

    file_path = Path(__file__).parent.parent / "config" / "techniques.json"

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    async with get_db_session() as session:
        for t in data['techniques']:
            technique = Technique(**t)
            await session.merge(technique)
            print(f"✅ Сохранена техника: {t['name']}")


async def clear_techniques():
    """Очищает таблицу техник"""
    async with get_db_session() as session:
        await session.execute(delete(Technique))
        await session.commit()
        print("🗑️ Таблица techniques очищена")



if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        asyncio.run(clear_techniques())
        print("---")
    else:
       asyncio.run(seed_techniques())
