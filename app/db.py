"""Database engine and session factory (PostgreSQL in production, SQLite by default)."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def make_session_factory(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine, sessionmaker(bind=engine, expire_on_commit=False)
