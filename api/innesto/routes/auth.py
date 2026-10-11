from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from .. import config
from ..auth import require_user, sign_in_with_google
from ..db import get_session
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class GoogleSignIn(BaseModel):
    idToken: str


class UserOut(BaseModel):
    id: str
    email: str | None
    displayName: str | None
    pictureUrl: str | None
    targetLang: str

    @classmethod
    def of(cls, u: User) -> "UserOut":
        return cls(id=u.id, email=u.email, displayName=u.display_name, pictureUrl=u.picture_url,
                   targetLang=u.target_lang)


class SignInOut(BaseModel):
    accessToken: str
    user: UserOut


@router.get("/config")
def auth_config() -> dict:
    """Public: what the browser needs to start Google sign-in."""
    return {"clientId": config.GOOGLE_CLIENT_ID, "configured": bool(config.GOOGLE_CLIENT_ID),
            "allowlistSize": len(config.ALLOWED_EMAILS)}


@router.post("/google")
def google_sign_in(body: GoogleSignIn, session: Session = Depends(get_session)) -> SignInOut:
    user, token = sign_in_with_google(session, body.idToken)
    return SignInOut(accessToken=token, user=UserOut.of(user))


@router.get("/me")
def me(user: User = Depends(require_user)) -> UserOut:
    return UserOut.of(user)
