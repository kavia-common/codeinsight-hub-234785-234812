from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.auth import router as auth_router
from src.api.routes.docs_extra import router as docs_router
from src.api.routes.oauth import router as oauth_router
from src.api.routes.orgs import router as orgs_router
from src.api.routes.repos import router as repos_router
from src.api.routes.webhooks import router as webhooks_router
from src.api.schemas import HealthResponse
from src.core.settings import get_settings

openapi_tags = [
    {"name": "Health", "description": "Service health and diagnostics."},
    {"name": "Auth", "description": "Session and organization selection."},
    {"name": "OAuth", "description": "GitHub/GitLab OAuth connect endpoints."},
    {"name": "Orgs", "description": "Organization, users, PRs, analytics, and audit logs."},
    {"name": "Repos", "description": "Repository operations and sync orchestration."},
    {"name": "Webhooks", "description": "Git provider webhook ingestion endpoints."},
    {"name": "Docs", "description": "Human-readable usage notes."},
]

app = FastAPI(
    title="DevTrackr Backend API",
    description="DevTrackr backend for OAuth-based GitHub/GitLab integrations, sync, analytics, RBAC, and audit logs.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"], response_model=HealthResponse, summary="Health check")
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(message="Healthy")


# Routers
app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(orgs_router)
app.include_router(repos_router)
app.include_router(webhooks_router)
app.include_router(docs_router)
