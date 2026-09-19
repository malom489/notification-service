from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession,create_async_engine
from sqlalchemy.orm import sessionmaker,declarative_base

from app.core .config import settings


engine=create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10
)
SessionLocal=sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
Base=declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()