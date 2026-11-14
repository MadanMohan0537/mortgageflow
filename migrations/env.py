from alembic import context

from app.config import engine
from app.models import Base

configured_connection = context.config.attributes.get("connection")
if context.is_offline_mode():
    context.configure(dialect_name="postgresql", target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif configured_connection is not None:
    context.configure(connection=configured_connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
