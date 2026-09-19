from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.countries import COUNTRY_CODES, CURRENCIES, LANGUAGES
from app.db import get_db
from app.deps import get_current_user
from app.errors import ApiError
from app.models import User
from app.presenters import user_out
from app.routers.auth import _issue_session, revoke_all_sessions
from app.schemas import ChangePasswordIn, PreferencesPatch, UserOut
from app.security import clear_auth_cookies, hash_password, is_weak_password, verify_password

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)


@router.patch("/preferences", response_model=UserOut)
def patch_preferences(
    body: PreferencesPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserOut:
    """País, idioma e moeda são independentes: quem mora fora pode manter o idioma de casa."""
    if body.country is not None:
        country = body.country.lower()
        if country not in COUNTRY_CODES:
            raise ApiError(422, "VALIDATION_ERROR", "Invalid country")
        user.country = country
    if body.language is not None:
        if body.language.lower() not in LANGUAGES:
            raise ApiError(422, "VALIDATION_ERROR", "Language not available")
        user.language = body.language.lower()
    if body.currency is not None:
        if body.currency.upper() not in CURRENCIES:
            raise ApiError(422, "VALIDATION_ERROR", "Currency not available")
        user.currency = body.currency.upper()
    db.commit()
    return user_out(user)


@router.post("/password", status_code=204, response_class=Response)
def change_password(
    body: ChangePasswordIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    # 400 (e não 401): o front trataria 401 como "sessão expirada".
    if not verify_password(body.current, user.password_hash):
        raise ApiError(400, "INVALID_CREDENTIALS", "Current password is incorrect")
    if is_weak_password(body.next):
        raise ApiError(422, "VALIDATION_ERROR", "Choose a less common password")

    user.password_hash = hash_password(body.next)
    revoke_all_sessions(db, user.id)  # derruba todas as outras sessões
    response = Response(status_code=204)
    _issue_session(db, user, request, response)  # e mantém esta logada
    db.commit()
    return response


@router.delete("", status_code=204, response_class=Response)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """Exclui a conta e todos os dados dela (LGPD/GDPR)."""
    db.delete(user)
    db.commit()
    response = Response(status_code=204)
    clear_auth_cookies(response)
    return response
