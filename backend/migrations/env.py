from alembic import context
from app.db import engine, Base, require_direct_connection
from app.config import settings
from app import models

require_direct_connection(settings().database_url)

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
