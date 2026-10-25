from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://cinemetrics:cinemetrics@localhost:5433/cinemetrics'
    tmdb_token: str = ''
    cors_origins: str = 'http://localhost:3000'
    raw_data_dir: str = './data/raw'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

@lru_cache
def settings():
    return Settings()
