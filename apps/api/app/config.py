from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_files() -> tuple[str, ...]:
    """Load .env from repo root (local) and/or app cwd (Docker/Railway)."""
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    for root in (here, *here.parents):
        candidates.append(root / ".env")
        candidates.append(root / ".env.local")
    candidates.extend([Path(".env"), Path(".env.local")])

    found: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            resolved = str(path.resolve())
        except OSError:
            continue
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        found.append(str(path))
    return tuple(found) if found else (".env",)


class Settings(BaseSettings):
    # Later files override earlier ones; .env.local wins over .env when both exist.
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
