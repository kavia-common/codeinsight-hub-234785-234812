from __future__ import annotations

import hmac
import uuid
from hashlib import sha256
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status


from src.core.db import get_db
from src.core.settings import get_settings
from src.models.models import Repository, WebhookDelivery

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _verify_github_signature(secret: str, body: bytes, signature_header: str) -> bool:
    # GitHub: X-Hub-Signature-256: sha256=...
    if not signature_header.startswith("sha256="):
        return False
    sent = signature_header.split("=", 1)[1]
    digest = hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()
    return hmac.compare_digest(sent, digest)


@router.post(
    "/github/{repo_id}",
    summary="GitHub webhook receiver",
)
async def github_webhook(
    repo_id: uuid.UUID,
    request: Request,
    x_github_event: str = Header(default="unknown"),
    x_github_delivery: Optional[str] = Header(default=None),
):
    """Ingest GitHub webhook events and persist delivery record."""
    settings = get_settings()
    body_bytes = await request.body()

    # Best-effort repo lookup for secret verification
    with next(get_db()) as db:  # type: ignore
        repo = db.get(Repository, repo_id)
        org_id = repo.org_id if repo else None

        error = None
        # If repo secret exists, verify signature
        if repo and repo.webhook_secret:
            sig = request.headers.get("x-hub-signature-256", "")
            if not _verify_github_signature(repo.webhook_secret, body_bytes, sig):
                error = "Invalid signature"
        elif settings.default_webhook_secret:
            sig = request.headers.get("x-hub-signature-256", "")
            if not _verify_github_signature(settings.default_webhook_secret, body_bytes, sig):
                error = "Invalid signature"

        row = WebhookDelivery(
            org_id=org_id,
            repo_id=repo_id,
            provider="github",
            event=x_github_event,
            delivery_id=x_github_delivery,
            request_headers=dict(request.headers),
            request_body=_safe_json(await request.json()),
            status="received" if not error else "error",
            error=error,
        )
        db.add(row)
        db.commit()

        if error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error)

    return {"ok": True}


@router.post(
    "/gitlab/{repo_id}",
    summary="GitLab webhook receiver",
)
async def gitlab_webhook(
    repo_id: uuid.UUID,
    request: Request,
    x_gitlab_event: str = Header(default="unknown"),
    x_gitlab_delivery: Optional[str] = Header(default=None),
):
    """Ingest GitLab webhook events and persist delivery record."""
    with next(get_db()) as db:  # type: ignore
        repo = db.get(Repository, repo_id)
        org_id = repo.org_id if repo else None

        row = WebhookDelivery(
            org_id=org_id,
            repo_id=repo_id,
            provider="gitlab",
            event=x_gitlab_event,
            delivery_id=x_gitlab_delivery,
            request_headers=dict(request.headers),
            request_body=_safe_json(await request.json()),
            status="received",
        )
        db.add(row)
        db.commit()

    return {"ok": True}


def _safe_json(payload: Any) -> Any:
    # Ensure payload is JSON-serializable for SQLAlchemy JSON column.
    return payload
