from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx

from src.core.settings import get_settings


# PUBLIC_INTERFACE
def generate_oauth_state() -> str:
    """Generate a cryptographically strong OAuth state string."""
    return secrets.token_urlsafe(32)


def _github_authorize_url(state: str, redirect_uri: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email repo",
        "state": state,
        "allow_signup": "true",
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def _gitlab_authorize_url(state: str, redirect_uri: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.gitlab_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read_user read_api read_repository",
        "state": state,
    }
    return f"{settings.gitlab_base_url}/oauth/authorize?{urlencode(params)}"


# PUBLIC_INTERFACE
def build_authorize_url(provider: str, *, state: str, redirect_uri: str) -> str:
    """Build provider authorization URL."""
    if provider == "github":
        return _github_authorize_url(state, redirect_uri)
    if provider == "gitlab":
        return _gitlab_authorize_url(state, redirect_uri)
    raise ValueError("Unsupported provider")


# PUBLIC_INTERFACE
async def exchange_code_for_token(provider: str, *, code: str, redirect_uri: str) -> dict:
    """Exchange OAuth code for token (GitHub/GitLab)."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "github":
            if not settings.github_client_id or not settings.github_client_secret:
                raise RuntimeError("GitHub OAuth not configured")
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            return resp.json()

        if provider == "gitlab":
            if not settings.gitlab_client_id or not settings.gitlab_client_secret:
                raise RuntimeError("GitLab OAuth not configured")
            resp = await client.post(
                f"{settings.gitlab_base_url}/oauth/token",
                data={
                    "client_id": settings.gitlab_client_id,
                    "client_secret": settings.gitlab_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            return resp.json()

    raise ValueError("Unsupported provider")


# PUBLIC_INTERFACE
async def fetch_user_profile(provider: str, *, access_token: str) -> dict:
    """Fetch authenticated user's profile from provider."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        if provider == "github":
            resp = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}"})
            resp.raise_for_status()
            return resp.json()
        if provider == "gitlab":
            resp = await client.get(
                f"{settings.gitlab_base_url}/api/v4/user", headers={"Authorization": f"Bearer {access_token}"}
            )
            resp.raise_for_status()
            return resp.json()
    raise ValueError("Unsupported provider")
