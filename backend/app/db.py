from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool
from .config import settings

class Base(DeclarativeBase):
    pass

def database_url(value):
    """Accept Neon/libpq URLs without selecting the legacy psycopg2 driver."""
    if value.startswith('postgres://'):
        value = 'postgresql+psycopg://' + value[len('postgres://'):]
    elif value.startswith('postgresql://'):
        value = 'postgresql+psycopg://' + value[len('postgresql://'):]
    return value

def require_direct_connection(value):
    # Neon transaction pooling cannot provide session-level advisory locks.
    host = (make_url(database_url(value)).host or '').lower()
    if '-pooler.' in host:
        raise RuntimeError('Use the Neon DIRECT connection for ingestion and migrations, not the pooled endpoint.')

def create_db_engine(value):
    return create_engine(
        database_url(value), poolclass=NullPool, pool_pre_ping=True,
        connect_args={'connect_timeout': 10, 'prepare_threshold': None},
        hide_parameters=True,
    )

# NullPool releases physical connections when each session closes, including
# across serverless suspension. Neon handles server-side pooling for API reads.
engine = create_db_engine(settings().database_url)
Session = sessionmaker(engine)

def get_db():
    with Session() as session:
        yield session
