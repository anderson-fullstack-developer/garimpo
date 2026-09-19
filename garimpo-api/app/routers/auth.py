"""Cadastro, login, sessão (com renovação rotativa), verificação de e-mail e recuperação de senha."""

import logging
from datetime import timedelta

import httpx
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.access import start_trial
from app.config import get_settings
from app.db import get_db
from app.deps import client_ip
from app.entitlements import entitlements_for
from app.errors import ApiError
from app.services.channels import ChannelError, get_channel
from app.services.messages import RESET_BUTTON, reset_message_html, reset_message_plain
from app.models import Destination, EmailToken, RefreshToken, User, UserSettings, new_id, utcnow
from app.presenters import user_out
from app.countries import COUNTRY_CODES, default_currency, default_language
from app.ratelimit import email_limiter, login_failures, register_limiter
from app.schemas import EmailIn, ForgotIn, LoginIn, RegisterIn, ResetIn, TokenIn, UserOut
from app.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_access_token,
    hash_password,
    hash_token,
    is_weak_password,
    new_token,
    set_auth_cookies,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("garimpo.auth")

VERIFY = "VERIFY_EMAIL"
RESET = "RESET_PASSWORD"
# Duas abas renovando ao mesmo tempo usam o mesmo refresh token; dentro desta janela isso é normal.
REFRESH_REUSE_GRACE = timedelta(seconds=10)


def _verify_captcha(token: str, ip: str) -> None:
    secret = get_settings().turnstile_secret
    if not secret:
        return
    try:
        result = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token, "remoteip": ip},
            timeout=8,
        ).json()
    except (httpx.HTTPError, ValueError):
        result = {}
    if not result.get("success"):
        raise ApiError(400, "VALIDATION_ERROR", "We could not confirm that you are not a robot")


def _issue_session(
    db: Session, user: User, request: Request, response: Response, family_id: str | None = None
) -> None:
    settings = get_settings()
    raw = new_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or new_id(),
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
            user_agent=(request.headers.get("user-agent") or "")[:255],
            ip=client_ip(request),
        )
    )
    set_auth_cookies(response, create_access_token(user.id), raw)


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def revoke_all_sessions(db: Session, user_id: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def _create_email_token(db: Session, user: User, kind: str, ttl: timedelta) -> str:
    raw = new_token()
    db.add(EmailToken(user_id=user.id, kind=kind, token_hash=hash_token(raw), expires_at=utcnow() + ttl))
    db.commit()
    return raw


def _consume_email_token(db: Session, raw: str, kind: str) -> EmailToken:
    token = db.scalar(
        select(EmailToken).where(EmailToken.token_hash == hash_token(raw), EmailToken.kind == kind)
    )
    if token is None or token.used_at is not None or token.expires_at < utcnow():
        raise ApiError(400, "TOKEN_EXPIRED", "Invalid or expired link")
    token.used_at = utcnow()
    return token


@router.post("/register", status_code=204, response_class=Response)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    ip = client_ip(request)
    register_limiter.check(ip)
    register_limiter.record(ip)
    _verify_captcha(body.captcha_token, ip)
    if is_weak_password(body.password):
        raise ApiError(422, "VALIDATION_ERROR", "Choose a less common password")

    email = body.email.lower()

    # Resposta idêntica exista ou não a conta: não revela quais e-mails estão cadastrados.
    if db.scalar(select(User).where(User.email == email)) is not None:
        return Response(status_code=204)

    country = (body.country or "").lower() or None
    if country is not None and country not in COUNTRY_CODES:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid country")
    user = User(
        country=country,
        language=default_language(country),
        currency=default_currency(country),
        email=email,
        password_hash=hash_password(body.password),
        plan=settings.default_plan,
        status="PENDING" if settings.registration_mode == "APPROVAL" else "ACTIVE",
        email_verified_at=None if settings.require_verification else utcnow(),
    )
    if not settings.require_verification:
        start_trial(user)  # sem verificação, o teste começa no cadastro
    user.settings = UserSettings(interval_minutes=entitlements_for(user.plan).min_interval_minutes)
    db.add(user)
    db.commit()
    return Response(status_code=204)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> UserOut:
    settings = get_settings()
    email = body.email.lower()
    key = f"{client_ip(request)}|{email}"
    login_failures.check(key)

    user = db.scalar(select(User).where(User.email == email))
    valid = verify_password(body.password, user.password_hash if user else None)
    if user is None or not valid:
        login_failures.record(key)
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password")
    if user.status == "SUSPENDED":
        raise ApiError(403, "ACCOUNT_SUSPENDED", "Account suspended")

    login_failures.reset(key)
    user.last_login_at = utcnow()
    _issue_session(db, user, request, response)
    db.commit()
    return user_out(user)


@router.post("/refresh", status_code=204, response_class=Response)
def refresh(request: Request, db: Session = Depends(get_db)) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))) if raw else None
    expired = ApiError(401, "TOKEN_EXPIRED", "Session expired")
    if token is None:
        raise expired

    now = utcnow()
    if token.revoked_at is not None:
        if now - token.revoked_at <= REFRESH_REUSE_GRACE:
            # Corrida entre duas abas: o navegador já recebeu o token novo; só renova o acesso.
            response = Response(status_code=204)
            user = db.get(User, token.user_id)
            if user is None or user.status == "SUSPENDED":
                raise expired
            set_access_only(response, user.id)
            return response
        # Token antigo reaparecendo depois da janela = possível roubo: derruba a sessão inteira.
        _revoke_family(db, token.family_id)
        db.commit()
        raise expired
    if token.expires_at < now:
        raise expired

    user = db.get(User, token.user_id)
    if user is None or user.status == "SUSPENDED":
        raise expired

    token.revoked_at = now
    response = Response(status_code=204)
    _issue_session(db, user, request, response, family_id=token.family_id)
    db.commit()
    return response


def set_access_only(response: Response, user_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        create_access_token(user_id),
        max_age=settings.access_token_minutes * 60,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
        if token:
            _revoke_family(db, token.family_id)
            db.commit()
    response = Response(status_code=204)
    clear_auth_cookies(response)
    return response


RESET_TELEGRAM_MINUTES = 15


def _send_reset_via_telegram(db: Session, user: User) -> None:
    """Manda o link de redefinição para o chat PRIVADO vinculado (nunca grupo/canal). Falhas não aparecem
    ao usuário: a resposta é igual exista a conta, tenha Telegram ou não."""
    destination = db.scalar(
        select(Destination)
        .where(
            Destination.user_id == user.id,
            Destination.channel == "TELEGRAM",
            Destination.kind == "PRIVATE",
            Destination.linked_at.is_not(None),
            Destination.disconnected_at.is_(None),
        )
        .order_by(Destination.is_default.desc(), Destination.linked_at.desc())
    )
    if destination is None:
        return
    raw = _create_email_token(db, user, RESET, timedelta(minutes=RESET_TELEGRAM_MINUTES))
    link = f"{get_settings().web_url}/reset?token={raw}"
    channel = get_channel(destination.channel)
    try:
        if hasattr(channel, "send_rich"):
            channel.send_rich(
                destination,
                reset_message_html(link, RESET_TELEGRAM_MINUTES, raw),
                reset_message_plain(link, RESET_TELEGRAM_MINUTES, raw),
                [(RESET_BUTTON, link)],
            )
        else:
            channel.send_text(destination, reset_message_plain(link, RESET_TELEGRAM_MINUTES, raw))
    except ChannelError:
        log.warning("Could not send the password reset link on Telegram")


@router.post("/forgot", status_code=204, response_class=Response)
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)) -> Response:
    email = body.email.lower()
    key = f"{client_ip(request)}|{email}"
    email_limiter.check(key)
    email_limiter.record(key)
    user = db.scalar(select(User).where(User.email == email))
    if user:
        _send_reset_via_telegram(db, user)
    return Response(status_code=204)


@router.post("/reset", status_code=204, response_class=Response)
def reset(body: ResetIn, db: Session = Depends(get_db)) -> Response:
    if is_weak_password(body.password):
        raise ApiError(422, "VALIDATION_ERROR", "Choose a less common password")
    token = _consume_email_token(db, body.token, RESET)
    user = db.get(User, token.user_id)
    if user is None:
        raise ApiError(400, "TOKEN_EXPIRED", "Invalid or expired link")
    user.password_hash = hash_password(body.password)
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()  # quem recebeu o link no Telegram comprovou que é dono
        start_trial(user)
    revoke_all_sessions(db, user.id)
    db.commit()
    return Response(status_code=204)
