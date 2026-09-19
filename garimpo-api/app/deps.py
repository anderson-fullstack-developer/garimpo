from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ApiError
from app.access import has_access
from app.models import User
from app.security import ACCESS_COOKIE, decode_access_token


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Usuário logado (qualquer status, menos suspenso). Sem sessão -> 401 (o front tenta renovar)."""
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "TOKEN_EXPIRED", "Session expired")
    if user.status == "SUSPENDED":
        raise ApiError(403, "ACCOUNT_SUSPENDED", "Account suspended")
    return user


def require_account(user: User = Depends(get_current_user)) -> User:
    """Conta aprovada, mesmo sem Telegram verificado (serve para quem ainda vai verificar)."""
    if user.status == "PENDING":
        raise ApiError(403, "ACCOUNT_PENDING", "Account awaiting approval")
    return user


def require_active(user: User = Depends(require_account)) -> User:
    """Usuário liberado para usar os dados do app: conta aprovada e Telegram verificado."""
    if get_settings().require_verification and user.email_verified_at is None:
        raise ApiError(403, "TELEGRAM_NOT_VERIFIED", "Connect Telegram to activate your account")
    return user


def require_access(user: User = Depends(require_active)) -> User:
    """Para o que gasta busca (buscar, prévia, ligar o monitor): teste em andamento ou assinatura ativa."""
    if not has_access(user):
        raise ApiError(402, "SUBSCRIPTION_REQUIRED", "Your free trial has ended. Subscribe to keep searching")
    return user
