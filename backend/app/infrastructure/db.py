"""Database connection and session management."""

import asyncio
import os
from weakref import WeakKeyDictionary

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/marketplace",
)

# Отдельный async engine на каждый event loop (pytest-asyncio, ASGI-тесты и т.д.).
_loop_engines: WeakKeyDictionary = WeakKeyDictionary()
_loop_sessionmakers: WeakKeyDictionary = WeakKeyDictionary()


def get_engine():
    loop = asyncio.get_running_loop()
    eng = _loop_engines.get(loop)
    if eng is None:
        eng = create_async_engine(DATABASE_URL, echo=True)
        _loop_engines[loop] = eng
    return eng


def get_sessionmaker():
    loop = asyncio.get_running_loop()
    maker = _loop_sessionmakers.get(loop)
    if maker is None:
        maker = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
        _loop_sessionmakers[loop] = maker
    return maker


class _EngineProxy:
    __slots__ = ()

    def __getattr__(self, name):
        return getattr(get_engine(), name)


class _SessionLocalProxy:
    __slots__ = ()

    def __call__(self, *args, **kwargs):
        return get_sessionmaker()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_sessionmaker(), name)


engine = _EngineProxy()
SessionLocal = _SessionLocalProxy()


def dispose_all_loop_engines_sync() -> None:
    """
    Закрывает все AsyncEngine, созданные на разных event loop (pytest-asyncio).
    sync_engine.dispose() не требует «родного» цикла и нужен, чтобы процесс
    pytest/контейнер не зависал после выхода из тестов.
    """
    engines = list(_loop_engines.values())
    _loop_engines.clear()
    _loop_sessionmakers.clear()
    for eng in engines:
        try:
            eng.sync_engine.dispose()
        except Exception:
            pass


async def get_db() -> AsyncSession:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
