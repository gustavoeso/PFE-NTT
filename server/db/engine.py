from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import create_engine

from server.config import DB_URI

engine = create_engine(DB_URI, pool_pre_ping=True)
