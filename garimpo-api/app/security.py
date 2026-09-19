import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Response

from app.config import get_settings

ACCESS_COOKIE = "garimpo_access"
REFRESH_COOKIE = "garimpo_refresh"

_hasher = PasswordHasher()
# Hash de mentira, usado para gastar o mesmo tempo quando o e-mail não existe (evita descobrir contas).
_DUMMY_HASH = _hasher.hash("senha-que-nunca-sera-usada")

COMMON_PASSWORDS = {
    "1234567890", "12345678910", "password123", "qwertyuiop", "1q2w3e4r5t", "senha12345",
    "passw0rd123", "abcdefghij", "0123456789", "iloveyou123", "admin12345", "welcome123",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def is_weak_password(password: str) -> bool:
    return password.lower() in COMMON_PASSWORDS or len(set(password)) < 4


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def create_access_token(user_id: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data.get("sub") if data.get("typ") == "access" else None


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    common = {"httponly": True, "secure": s.cookie_secure, "samesite": "lax", "domain": s.cookie_domain}
    response.set_cookie(ACCESS_COOKIE, access, max_age=s.access_token_minutes * 60, path="/", **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_days * 86400, path="/", **common)


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, path="/", domain=s.cookie_domain)
