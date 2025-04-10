from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import create_engine

from server.config import DB_URI

async_engine = create_async_engine(DB_URI, echo=True)
sync_engine = create_engine(DB_URI.replace("+asyncpg", ""))  # usado por SQLDatabase
