"""LangGraph Asynchronous SQLite Checkpointer Factory.
Provides durable, thread-safe asynchronous state persistence using aiosqlite and AsyncSqliteSaver.
"""
from pathlib import Path
from typing import Optional
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.core.config import settings
from app.core.logging import logger


class AsyncCheckpointerManager:
    """Manages AsyncSqliteSaver connection lifecycle."""

    def __init__(self, db_path: str = settings.CHECKPOINTER_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
        self._saver: Optional[AsyncSqliteSaver] = None

    async def get_saver(self) -> AsyncSqliteSaver:
        """Obtain or initialize AsyncSqliteSaver instance."""
        if self._saver is None:
            self._connection = await aiosqlite.connect(
                str(self.db_path),
                check_same_thread=False
            )
            await self._connection.execute("PRAGMA journal_mode=WAL;")
            self._saver = AsyncSqliteSaver(conn=self._connection)
            await self._saver.setup()
            logger.info(f"Initialized AsyncSqliteSaver at {self.db_path}")

        return self._saver

    async def close(self) -> None:
        """Close aiosqlite connection on application shutdown."""
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._saver = None


async_checkpointer_manager = AsyncCheckpointerManager()
