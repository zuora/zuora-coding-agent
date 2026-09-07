"""Minimal Zuora REST OAuth + describe client for the coding-agent workflow engine.

Uses ``ZUORA_BASE_URL``, ``ZUORA_CLIENT_ID``, and ``ZUORA_CLIENT_SECRET`` from the
environment (same vars as MCP / workflow-build curl recipes). Falls back silently
when credentials are absent so offline cached-describe mode still works.
"""

from __future__ import annotations

import os
import time
from typing import Any

import structlog

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from workflow_engine.workflow_reference.describe_parser import parse_object_describe

logger = structlog.get_logger(__name__)

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_DESCRIBE_TIMEOUT_S = 30.0


def normalize_zuora_rest_base_url(url: str) -> str:
    """Strip MCP suffix and trailing slashes from a configured base URL."""
    base = (url or "").strip().rstrip("/")
    if base.endswith("/mcp"):
        base = base[: -len("/mcp")]
    return base.rstrip("/")


def credentials_available() -> bool:
    return bool(
        os.environ.get("ZUORA_BASE_URL")
        and os.environ.get("ZUORA_CLIENT_ID")
        and os.environ.get("ZUORA_CLIENT_SECRET")
    )


def load_env_session_state() -> dict[str, Any] | None:
    """Build an invocation_state dict from ``ZUORA_*`` environment variables."""
    base = os.environ.get("ZUORA_BASE_URL", "").strip()
    client_id = os.environ.get("ZUORA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("ZUORA_CLIENT_SECRET", "").strip()
    if not (base and client_id and client_secret):
        return None
    return {
        "zuora_base_url": normalize_zuora_rest_base_url(base),
        "zuora_client_id": client_id,
        "zuora_client_secret": client_secret,
    }


class ZuoraSession:
    """Minimal stand-in for Strands ``ToolContext`` with ``invocation_state``."""

    def __init__(self, state: dict[str, Any]):
        self.invocation_state = state


def session_from_env() -> ZuoraSession | None:
    state = load_env_session_state()
    return ZuoraSession(state) if state else None


async def _get_bearer_token(state: dict[str, Any]) -> str:
    if httpx is None:
        raise RuntimeError("httpx is required for live Zuora API calls")

    base_url = normalize_zuora_rest_base_url(str(state.get("zuora_base_url") or ""))
    client_id = str(state.get("zuora_client_id") or "")
    client_secret = str(state.get("zuora_client_secret") or "")
    if not (base_url and client_id and client_secret):
        raise ValueError("Zuora credentials missing from session state")

    cache_key = f"{client_id}:{base_url}"
    cached = _TOKEN_CACHE.get(cache_key)
    if cached and cached[1] > time.time():
        return cached[0]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{base_url}/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    token = str(data["access_token"])
    expires_in = int(data.get("expires_in") or 3600)
    _TOKEN_CACHE[cache_key] = (token, time.time() + max(expires_in - 30, 30))
    return token


def _build_zuora_headers(
    *,
    bearer_token: str,
    entity_ids: str | None = None,
    zuora_version: str | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }
    if entity_ids:
        headers["Zuora-Entity-Ids"] = entity_ids
    if zuora_version:
        headers["zuora-version"] = zuora_version
    return headers


async def fetch_object_describe(
    object_name: str,
    state: dict[str, Any],
):
    """Fetch ``GET /v1/describe/{object}?showRelationships=true`` when creds exist."""
    from workflow_engine.workflow_reference.object_metadata import ObjectMetadataResult

    if httpx is None:
        return None
    try:
        token = await _get_bearer_token(state)
        headers = _build_zuora_headers(
            bearer_token=token,
            entity_ids=state.get("entity_ids"),
            zuora_version=state.get("zuora_version"),
        )
        headers["Accept"] = "application/xml"
        base_url = normalize_zuora_rest_base_url(str(state.get("zuora_base_url") or ""))
        url = f"{base_url}/v1/describe/{object_name}?showRelationships=true"
        async with httpx.AsyncClient(timeout=_DESCRIBE_TIMEOUT_S) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        return ObjectMetadataResult(describe=parse_object_describe(resp.text), source="api")
    except Exception as exc:
        logger.info(
            "zuora_http.describe_failed",
            object_name=object_name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None
