"""Server-side BFF sessions: tokens live in Redis, the browser only holds an opaque session id."""

import json
import secrets
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends
from redis.asyncio import Redis

from app.config import Settings, get_settings

PENDING_PREFIX = "toolmesh:auth:pending:"
SESSION_PREFIX = "toolmesh:auth:session:"
RATE_LIMIT_PREFIX = "toolmesh:auth:rate:"
PENDING_TTL_SECONDS = 600
# Refresh the access token this many seconds before it expires so a request never races its death.
REFRESH_MARGIN_SECONDS = 30


@dataclass
class PendingAuth:
    code_verifier: str
    next_path: str


@dataclass
class Session:
    access_token: str
    refresh_token: str
    expires_at: float
    # Needed for a silent RP-initiated logout (id_token_hint).
    id_token: str | None = None


class SessionStore:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def save_pending(self, state: str, pending: PendingAuth) -> None:
        await self._redis.set(f"{PENDING_PREFIX}{state}", json.dumps(asdict(pending)), ex=PENDING_TTL_SECONDS)

    async def pop_pending(self, state: str) -> PendingAuth | None:
        raw = await self._redis.getdel(f"{PENDING_PREFIX}{state}")
        return PendingAuth(**json.loads(raw)) if raw else None

    async def create_session(self, token_response: dict) -> str:
        session_id = secrets.token_urlsafe(32)
        session = Session(
            access_token=token_response["access_token"],
            refresh_token=token_response["refresh_token"],
            expires_at=time.time() + token_response["expires_in"],
            id_token=token_response.get("id_token"),
        )
        await self._save(session_id, session)
        return session_id

    async def get_session(self, session_id: str) -> Session | None:
        raw = await self._redis.get(f"{SESSION_PREFIX}{session_id}")
        if not raw:
            return None
        session = Session(**json.loads(raw))
        if session.expires_at - REFRESH_MARGIN_SECONDS > time.time():
            return session
        return await self._refresh(session_id, session)

    async def delete_session(self, session_id: str) -> None:
        await self._redis.delete(f"{SESSION_PREFIX}{session_id}")

    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """True if the call is allowed, False once the limit is hit."""
        redis_key = f"{RATE_LIMIT_PREFIX}{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        return count <= limit

    async def _save(self, session_id: str, session: Session) -> None:
        await self._redis.set(
            f"{SESSION_PREFIX}{session_id}", json.dumps(asdict(session)), ex=self._settings.session_ttl_seconds
        )

    async def _refresh(self, session_id: str, session: Session) -> Session | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    self._settings.token_url,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self._settings.bff_client_id,
                        "client_secret": self._settings.bff_client_secret,
                        "refresh_token": session.refresh_token,
                    },
                )
            response.raise_for_status()
            token_response = response.json()
        except (httpx.HTTPError, ValueError):
            await self.delete_session(session_id)
            return None
        session.access_token = token_response["access_token"]
        session.refresh_token = token_response["refresh_token"]
        session.expires_at = time.time() + token_response["expires_in"]
        session.id_token = token_response.get("id_token", session.id_token)
        await self._save(session_id, session)
        return session


@lru_cache
def _redis(url: str) -> Redis:
    return Redis.from_url(url, decode_responses=True)


def get_session_store(settings: Annotated[Settings, Depends(get_settings)]) -> SessionStore:
    return SessionStore(_redis(settings.redis_url), settings)
