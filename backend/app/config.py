from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://cinemetrics:cinemetrics@localhost:5433/cinemetrics'
    tmdb_token: str = ''
    cors_origins: str = 'http://localhost:3000'
    raw_data_dir: str = './data/raw'
    raw_archive_mode: Literal['file', 'database'] = 'file'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

@lru_cache
def settings():
    return Settings()
