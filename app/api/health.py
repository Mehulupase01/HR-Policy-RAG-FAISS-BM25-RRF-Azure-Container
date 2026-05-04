"""Health and readiness endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from app.config import Settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe. Keep this fast and independent of upstream providers."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    """Readiness probe that verifies Azure OpenAI chat completions are reachable."""
    settings: Settings = request.app.state.settings
    endpoint = str(settings.azure_openai_endpoint).rstrip("/")
    url = (
        f"{endpoint}/openai/deployments/{settings.azure_openai_chat_deployment}"
        f"/chat/completions?api-version={settings.azure_openai_api_version}"
    )
    payload = {
        "messages": [
            {"role": "system", "content": "You are a health check."},
            {"role": "user", "content": "ping"},
        ],
        "max_tokens": 1,
        "temperature": 0,
    }

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "api-key": settings.azure_openai_key.get_secret_value(),
                },
                json=payload,
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI readiness check timed out.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI readiness check failed.",
        ) from exc

    return {"status": "ready"}
