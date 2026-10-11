"""Identity: Google sign-in, an email allowlist, and 7-day bearer tokens.

Flow (same shape as the user's other apps): the browser obtains a Google ID
token with Google Identity Services, POSTs it to /api/auth/google, and gets
back an HS256 JWT it then sends as `Authorization: Bearer ...`. Protected
routers depend on `require_user`, which stores the user id in a ContextVar so
the rest of the code keeps calling `current_user_id()`.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, select

from . import config
from .db import get_session
from .models import Book, ReadingPosition, User, VocabEntry, utcnow

log = logging.getLogger("innesto.auth")

_current_user: ContextVar[str | None] = ContextVar("innesto_current_user", default=None)


def current_user_id() -> str:
    uid = _current_user.get()
    if uid is None:
        raise HTTPException(401, "Not signed in", headers={"WWW-Authenticate": "Bearer"})
    return uid


# -- Google ------------------------------------------------------------------

def verify_google_id_token(id_token: str) -> dict:
    """Verify a Google ID token for our client id and return its claims.
    Raises ValueError on any problem (bad signature, wrong audience, expired)."""
    if not config.GOOGLE_CLIENT_ID:
        raise ValueError("Google sign-in is not configured (INNESTO_GOOGLE_CLIENT_ID)")
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token
    claims = google_id_token.verify_oauth2_token(id_token, google_requests.Request(), config.GOOGLE_CLIENT_ID)
    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Unexpected token issuer")
    if not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("Google account has no verified email")
    claims["email"] = claims["email"].lower()
    return claims


def is_allowed(email: str) -> bool:
    return email.lower() in config.ALLOWED_EMAILS


# -- Access tokens -------------------------------------------------------------

def mint_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user.id, "email": user.email, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(days=config.TOKEN_TTL_DAYS)).timestamp())}
    return jwt.encode(payload, config.jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.jwt_secret(), algorithms=["HS256"], options={"require": ["sub", "exp"]})


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


async def require_user(request: Request, session: Session = Depends(get_session)) -> User:
    """FastAPI dependency: validate the bearer token, load the user, and make
    the user id available to `current_user_id()` for this request.

    Async on purpose: a sync dependency runs in a worker thread with a *copy*
    of the request context, so a ContextVar set there would not be visible to
    the route handler. The DB lookup is a primary-key read."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Not signed in")
    try:
        claims = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired, please sign in again")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token")
    user = session.get(User, claims["sub"])
    if user is None:
        raise _unauthorized("Unknown user")
    if user.email and not is_allowed(user.email):
        # Removed from the allowlist since the token was issued.
        raise HTTPException(403, "This account is no longer allowed to use Innesto")
    _current_user.set(user.id)
    return user


# -- Sign-in -------------------------------------------------------------------

def sign_in_with_google(session: Session, id_token: str) -> tuple[User, str]:
    """Exchange a Google ID token for (user, access_token). Raises HTTPException."""
    try:
        claims = verify_google_id_token(id_token)
    except ValueError as exc:
        log.info("rejected Google token: %s", exc)
        raise HTTPException(401, f"Google sign-in failed: {exc}") from exc
    email = claims["email"]
    if not is_allowed(email):
        log.warning("sign-in refused for %s (allowlist has %d entries)", email, len(config.ALLOWED_EMAILS))
        raise HTTPException(403, f"{email} is not on the guest list for this Innesto instance.")

    user = session.get(User, claims["sub"])
    if user is None:
        user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(id=claims["sub"], email=email)
        session.add(user)
    user.email = email
    user.display_name = claims.get("name") or user.display_name
    user.picture_url = claims.get("picture") or user.picture_url
    user.last_login = utcnow()
    session.commit()
    session.refresh(user)
    adopt_legacy_local_user(session, user)
    return user, mint_token(user)


def adopt_legacy_local_user(session: Session, user: User) -> bool:
    """Phase 1 ran with an implicit `local` account. The first real person to
    sign in inherits its library, positions and vocabulary (only while no
    other real user exists, so a second guest never grabs it)."""
    legacy = session.get(User, config.LEGACY_LOCAL_USER_ID)
    if legacy is None or user.id == legacy.id:
        return False
    others = session.exec(select(User).where(User.id != legacy.id, User.id != user.id)).first()
    if others is not None:
        return False
    for model in (Book, ReadingPosition, VocabEntry):
        for row in session.exec(select(model).where(model.user_id == legacy.id)):
            row.user_id = user.id
            session.add(row)
    # Keep the newcomer's language preference if the legacy one was changed.
    user.target_lang = legacy.target_lang
    user.native_lang = legacy.native_lang
    session.delete(legacy)
    session.add(user)
    session.commit()
    log.info("adopted legacy local data into %s", user.email)
    return True
