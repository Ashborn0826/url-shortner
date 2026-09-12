from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://urlshort:urlshort@localhost:5432/urlshort"
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    cache_ttl_seconds: int = 3600
    short_code_length: int = 7
    api_host: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:5173"
    debug: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20


settings = Settings()