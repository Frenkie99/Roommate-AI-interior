"""Self-service username/password authentication routes."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.services.auth_service import (
    SESSION_COOKIE,
    AuthError,
    AuthUser,
    GenerationReservation,
    QuotaError,
    auth_service,
)


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=8, max_length=128)


def _payload(user: AuthUser) -> dict:
    return {
        "code": 0,
        "message": "success",
        "data": {
            "user": {"id": user.id, "username": user.username},
            "quota": auth_service.quota_snapshot(user.id),
        },
    }


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    secure = request.url.scheme == "https" or forwarded_proto == "https"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=auth_service.session_days * 86400,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def require_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> AuthUser:
    user = auth_service.authenticate(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录后再使用")
    return user


def reserve_generation_or_raise(
    user: AuthUser, endpoint: str
) -> GenerationReservation:
    try:
        return auth_service.reserve_generation(user.id, endpoint)
    except QuotaError as exc:
        status_code = 401 if exc.reason == "inactive" else 429
        raise HTTPException(
            status_code=status_code,
            detail={"message": exc.message, "reason": exc.reason},
        ) from exc


@router.post("/register")
async def register(credentials: Credentials, request: Request, response: Response):
    try:
        user, token = auth_service.register(credentials.username, credentials.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    _set_session_cookie(response, request, token)
    return _payload(user)


@router.post("/login")
async def login(credentials: Credentials, request: Request, response: Response):
    try:
        user, token = auth_service.login(credentials.username, credentials.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    _set_session_cookie(response, request, token)
    return _payload(user)


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
):
    auth_service.logout(session_token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"code": 0, "message": "success", "data": {}}


@router.get("/me")
async def me(user: AuthUser = Depends(require_user)):
    return _payload(user)
