from fastapi import APIRouter

from app.config import get_settings
from app.schemas import PublicConfigOut

router = APIRouter(tags=["public"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/public/config", response_model=PublicConfigOut)
def public_config() -> PublicConfigOut:
    settings = get_settings()
    return PublicConfigOut(
        registration_mode=settings.registration_mode,
        bot_username=settings.telegram_bot_username,
    )
