from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.core.settings import get_settings


@dataclass(frozen=True)
class AISummaryResult:
    summary: str
    risk_score: float
    risk_notes: list[str]


class AIProvider(Protocol):
    """Protocol for AI providers (OpenAI, Anthropic, etc.)."""

    async def summarize_pr(self, *, title: str, body: str | None, diff_stats: dict | None) -> AISummaryResult: ...


class StubAIProvider:
    """Deterministic placeholder AI provider."""

    async def summarize_pr(self, *, title: str, body: str | None, diff_stats: dict | None) -> AISummaryResult:
        risk = 25.0
        notes = ["Stubbed AI provider"]
        if body and ("auth" in body.lower() or "oauth" in body.lower()):
            risk = 60.0
            notes.append("Auth keywords detected")
        return AISummaryResult(
            summary=f"Placeholder summary: {title}.",
            risk_score=risk,
            risk_notes=notes,
        )


# PUBLIC_INTERFACE
def get_ai_provider() -> AIProvider:
    """Factory for configured AI provider implementation."""
    settings = get_settings()
    # For now only stub is implemented.
    _ = settings.ai_provider
    return StubAIProvider()
