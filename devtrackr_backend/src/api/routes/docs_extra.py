from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Docs"])


@router.get(
    "/docs/usage",
    summary="API usage notes (OAuth/Webhooks)",
)
def usage_notes() -> dict:
    """Provide human-readable usage notes for OAuth and webhook endpoints."""
    return {
        "oauth": {
            "start": "POST /oauth/{github|gitlab}/start -> {url} then redirect user to url",
            "callback": "GET /oauth/{github|gitlab}/callback?code=...&state=... sets HttpOnly cookies devtrackr_access/devtrackr_refresh",
            "frontend_site_url": "OAuth redirect URIs are based on SITE_URL env var.",
        },
        "webhooks": {
            "github": "POST /webhooks/github/{repo_id} with X-GitHub-Event and optional signature headers",
            "gitlab": "POST /webhooks/gitlab/{repo_id} with X-Gitlab-Event",
            "persistence": "All deliveries are stored in webhook_deliveries table.",
        },
    }
