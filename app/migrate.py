from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.config import engine


def handler(event, context):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine().begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(735090247)"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return {"status": "migrated"}
