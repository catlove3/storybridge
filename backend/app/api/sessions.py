from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import get_config
from app.public_usage import public_usage

COOKIE = "storybridge_session"
LIFETIME = 30 * 86400
session_router = APIRouter(prefix="/api")


class SessionResponse(BaseModel):
    visitor_id: str
    csrf_token: str
    expires_at: float | None = None


def credential_hash(credential: str) -> str:
    return hashlib.sha256(credential.encode()).hexdigest()


def csrf_token(credential: str) -> str:
    return hmac.new(credential.encode(), b"storybridge-csrf-v1", hashlib.sha256).hexdigest()


def check_origin(request: Request) -> None:
    # Compare to configured origin, never to caller-controlled forwarding headers.
    configured = get_config().share.public_url
    expected = configured or str(request.base_url).rstrip("/")
    origin = request.headers.get("origin", "")
    if origin != expected or request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, {"code": "origin_rejected", "message": "请从网站首页重新打开。"})


def find_session(request: Request):
    credential = request.cookies.get(COOKIE, "")
    if not credential or len(credential) > 200:
        return None
    with public_usage().database.transaction() as connection:
        return connection.execute(
            "SELECT * FROM visitor_sessions WHERE credential_hash=? AND expires_at>?",
            (credential_hash(credential), time.time()),
        ).fetchone()


def session_owner(request: Request) -> str:
    session = find_session(request)
    if session is None:
        raise HTTPException(
            401, {"code": "session_expired", "message": "体验身份已过期，请刷新页面。"}
        )
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        expected = csrf_token(request.cookies[COOKIE])
        if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), expected):
            raise HTTPException(403, {"code": "csrf_rejected", "message": "请刷新页面后再操作。"})
    return session["owner_id"]


@session_router.post("/session", response_model=SessionResponse)
async def session(request: Request, response: Response):
    config = get_config()
    if not config.share.enabled:
        from app.api.security import require_owner

        owner = await require_owner(request, request.headers.get("X-API-Key"))
        return SessionResponse(visitor_id=owner, csrf_token="")
    check_origin(request)
    existing = find_session(request)
    credential = request.cookies.get(COOKIE, "")
    if existing:
        owner, expires = existing["owner_id"], existing["expires_at"]
    else:
        credential = secrets.token_urlsafe(32)
        owner = "visitor_" + secrets.token_hex(16)
        expires = time.time() + LIFETIME
        with public_usage().database.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM visitor_sessions WHERE expires_at<=?", (time.time(),))
            connection.execute(
                "INSERT INTO visitor_sessions VALUES(?,?,?)",
                (credential_hash(credential), owner, expires),
            )
    response.set_cookie(
        COOKIE,
        credential,
        max_age=max(1, int(expires - time.time())),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(visitor_id=owner, csrf_token=csrf_token(credential), expires_at=expires)


def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("公开地址必须是 HTTPS 首页地址，且不包含身份、路径或参数。")
