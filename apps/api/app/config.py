from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://hummingbird:hummingbird@localhost:5432/hummingbird"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    moderator_token: str = "dev-moderator-token"
    # Production must set USE_DEMO_STORE=false and DATABASE_URL.
    use_demo_store: bool = False

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
