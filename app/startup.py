"""
Creates database tables on first run (dev convenience).
For production, use Alembic migrations.
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base
# Import all models so Base knows about them
import app.db.models.user       # noqa
import app.db.models.framework  # noqa
import app.db.models.document   # noqa
import app.db.models.task       # noqa
import app.db.models.igaming    # noqa
import app.db.models.euai       # noqa

logger = logging.getLogger(__name__)


async def create_tables():
    try:
        engine = create_async_engine(settings.DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        logger.info('Database tables created / verified')
    except Exception as exc:
        logger.error('Database startup check failed: %s', exc)
        # Non-fatal: app continues; DB errors will surface per-request


if __name__ == '__main__':
    asyncio.run(create_tables())
