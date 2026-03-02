from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional


def _split_csv(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    postgres_url: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_port: str

    cors_allow_origins: List[str]

    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    access_token_ttl_minutes: int
    refresh_token_ttl_days: int

    cookie_secure: bool
    cookie_samesite: str

    site_url: str

    github_client_id: Optional[str]
    github_client_secret: Optional[str]

    gitlab_client_id: Optional[str]
    gitlab_client_secret: Optional[str]
    gitlab_base_url: str

    ai_provider: str
    ai_model: str

    default_webhook_secret: Optional[str]


_CACHED: Optional[Settings] = None


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Return cached Settings loaded from environment variables."""
    global _CACHED
    if _CACHED is not None:
        return _CACHED

    cors = os.getenv("CORS_ALLOW_ORIGINS", "*")
    cors_allow_origins = ["*"] if cors.strip() == "*" else _split_csv(cors)

    def _req(name: str) -> str:
        val = os.getenv(name)
        if not val:
            raise RuntimeError(
                f"Missing required environment variable: {name}. "
                "Ask the orchestrator/user to set it in the container .env."
            )
        return val

    _CACHED = Settings(
        postgres_url=_req("POSTGRES_URL"),
        postgres_user=_req("POSTGRES_USER"),
        postgres_password=_req("POSTGRES_PASSWORD"),
        postgres_db=_req("POSTGRES_DB"),
        postgres_port=_req("POSTGRES_PORT"),
        cors_allow_origins=cors_allow_origins,
        jwt_secret=_req("JWT_SECRET"),
        jwt_issuer=os.getenv("JWT_ISSUER", "devtrackr"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "devtrackr-web"),
        access_token_ttl_minutes=int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60")),
        refresh_token_ttl_days=int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30")),
        cookie_secure=os.getenv("COOKIE_SECURE", "true").lower() in ("1", "true", "yes"),
        cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax"),
        site_url=os.getenv("SITE_URL", "http://localhost:3000").rstrip("/"),
        github_client_id=os.getenv("GITHUB_CLIENT_ID"),
        github_client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
        gitlab_client_id=os.getenv("GITLAB_CLIENT_ID"),
        gitlab_client_secret=os.getenv("GITLAB_CLIENT_SECRET"),
        gitlab_base_url=os.getenv("GITLAB_BASE_URL", "https://gitlab.com").rstrip("/"),
        ai_provider=os.getenv("AI_PROVIDER", "stub"),
        ai_model=os.getenv("AI_MODEL", "stub"),
        default_webhook_secret=os.getenv("DEFAULT_WEBHOOK_SECRET"),
    )
    return _CACHED
