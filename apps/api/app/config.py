from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _env_files() -> tuple[str, ...]:
    candidates = (
        _REPO_ROOT / ".env",
        _REPO_ROOT / ".env.local",
        Path(".env"),
        Path(".env.local"),
    )
    found = tuple(str(p) for p in candidates if p.is_file())
    return found if found else (".env",)


class Settings(BaseSettings):
    # Later files override earlier ones; .env.local wins over .env.
    model_config = SettingsConfigDict(env_file=_env_files(), extra="ignore")

    database_url: str = "postgresql://hummingbird:hummingbird@localhost:5432/hummingbird"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    moderator_token: str = "dev-moderator-token"
    # Production must set USE_DEMO_STORE=false and DATABASE_URL.
    use_demo_store: bool = False
    # Optional Slack/Discord/generic webhook for new crowd tips.
    report_notify_webhook: str = ""

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
