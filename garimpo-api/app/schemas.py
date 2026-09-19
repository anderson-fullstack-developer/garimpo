"""Formato JSON da API. O front usa camelCase; aqui os campos são snake_case com alias automático."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

from app.countries import VALID_COUNTRIES

Condition = Literal["new_with_tags", "new_without_tags", "very_good", "good", "satisfactory"]
Preset = Literal["PHONES", "CONSOLES_GAMES", "AUDIO_VIDEO"]
Word = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# ---------------------------------------------------------------- auth / usuário
class UserOut(CamelModel):
    id: str
    email: str
    role: Literal["USER", "ADMIN"]
    plan: Literal["FREE", "PRO", "ELITE"]
    status: Literal["PENDING", "ACTIVE", "SUSPENDED"]
    verified: bool  # Telegram vinculado (a conta está liberada)
    created_at: datetime
    trial_ends_at: datetime | None = None
    subscription_status: str | None = None
    subscription_ends_at: datetime | None = None
    has_access: bool = True  # teste em andamento ou assinatura ativa
    country: str | None = None
    language: str = "pt"
    currency: str = "EUR"


class PublicConfigOut(CamelModel):
    registration_mode: Literal["OPEN", "INVITE", "APPROVAL"]
    bot_username: str


class RegisterIn(CamelModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    invite_code: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=2)
    captcha_token: str = Field(default="", max_length=4000)


class PreferencesPatch(CamelModel):
    country: str | None = Field(default=None, max_length=2)
    language: str | None = Field(default=None, max_length=2)
    currency: str | None = Field(default=None, max_length=3)


class ForgotIn(CamelModel):
    email: EmailStr
    via: Literal["email", "telegram"] = "email"


class LoginIn(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenIn(CamelModel):
    token: str = Field(min_length=10, max_length=200)


class EmailIn(CamelModel):
    email: EmailStr


class ResetIn(CamelModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=128)


class ChangePasswordIn(CamelModel):
    current: str = Field(min_length=1, max_length=128)
    next: str = Field(min_length=10, max_length=128)


# ---------------------------------------------------------------- alertas
class AlertIn(CamelModel):
    name: str = Field(default="", max_length=80)
    query: str = Field(min_length=2, max_length=100)
    match_type: Literal["PHRASE", "ALL_WORDS"] = "PHRASE"
    required_words: list[Word] = Field(default_factory=list, max_length=20)
    exclude_words: list[Word] = Field(default_factory=list, max_length=20)
    exclude_presets: list[Preset] = Field(default_factory=list, max_length=3)
    min_price: float = Field(default=0, ge=0, le=1_000_000)
    max_price: float | None = Field(default=None, ge=0, le=1_000_000)
    status_filter: list[Condition] = Field(default_factory=list, max_length=5)
    max_age_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)
    pages: int = Field(default=1, ge=1, le=3)
    country: str = "pt"
    notify_on_first_run: bool = False
    vinted_params: dict[str, str | int | list[str | int]] | None = None
    source_url: str | None = Field(default=None, max_length=2000)
    perfect_min: float | None = Field(default=None, ge=0, le=1_000_000)
    perfect_max: float | None = Field(default=None, ge=0, le=1_000_000)
    destination_id: str | None = None
    active: bool = True

    @model_validator(mode="after")
    def _check(self) -> "AlertIn":
        self.query = self.query.strip()
        if len(self.query) < 2:
            raise ValueError("query: enter at least 2 characters")
        if self.max_price is not None and self.max_price < self.min_price:
            raise ValueError("maxPrice: the maximum price must be higher than the minimum")
        if (
            self.perfect_min is not None
            and self.perfect_max is not None
            and self.perfect_max < self.perfect_min
        ):
            raise ValueError("perfectMax: must be higher than perfectMin")
        if self.country not in VALID_COUNTRIES:
            raise ValueError("country: invalid country")
        return self


class AlertPatch(CamelModel):
    """Todos os campos opcionais; só o que vier no JSON é alterado."""

    name: str | None = None
    query: str | None = None
    match_type: str | None = None
    required_words: list | None = None
    exclude_words: list | None = None
    exclude_presets: list | None = None
    min_price: float | None = None
    max_price: float | None = None
    status_filter: list | None = None
    max_age_minutes: int | None = None
    pages: int | None = None
    country: str | None = None
    notify_on_first_run: bool | None = None
    vinted_params: dict | None = None
    source_url: str | None = None
    perfect_min: float | None = None
    perfect_max: float | None = None
    destination_id: str | None = None
    active: bool | None = None


class AlertOut(AlertIn):
    id: str
    created_at: datetime
    new_today: int = 0


class PresetOut(CamelModel):
    id: Preset
    label: str
    words: list[str]


# ---------------------------------------------------------------- destinos / canais
class ChannelOut(CamelModel):
    id: Literal["TELEGRAM"]
    name: str
    supports_groups: bool
    supports_images: bool
    instructions: dict[str, list[str]]


class DestinationOut(CamelModel):
    id: str
    channel: Literal["TELEGRAM"]
    kind: Literal["PRIVATE", "GROUP", "CHANNEL"] | None
    title: str | None
    status: Literal["LINKED", "PENDING", "DISCONNECTED"]
    is_default: bool
    linked_at: datetime | None
    language: str = "pt"  # idioma efetivo dos avisos (o do destino, ou o da conta se não houver)


class LinkCodeIn(CamelModel):
    channel: Literal["TELEGRAM"] = "TELEGRAM"
    kind: Literal["PRIVATE", "GROUP", "CHANNEL"]
    language: str | None = Field(default=None, max_length=2)


class LinkCodeOut(CamelModel):
    destination_id: str
    code: str
    expires_at: datetime
    deep_link: str | None
    command: str | None


class SendItemsIn(CamelModel):
    item_ids: list[str] = Field(min_length=1, max_length=20)


class DestinationPatch(CamelModel):
    title: str | None = Field(default=None, max_length=120)
    is_default: bool | None = None
    language: str | None = Field(default=None, max_length=2)


# ---------------------------------------------------------------- monitor / config
class SettingsOut(CamelModel):
    interval_minutes: float


class SettingsPatch(CamelModel):
    interval_minutes: float | None = Field(default=None, ge=0.1, le=1440)


class MonitorRunOut(CamelModel):
    id: str
    started_at: datetime
    duration_ms: int
    analyzed: int
    matches: int
    sent: int
    status: Literal["ok", "error", "rate_limited"]
    error: str | None


class MonitorStatusOut(CamelModel):
    state: Literal["ACTIVE", "PAUSED", "DEGRADED", "RATE_LIMITED"]
    enabled: bool
    interval_minutes: float
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_error: str | None
    runs: list[MonitorRunOut]
    median_detection_seconds: float | None


# ---------------------------------------------------------------- busca manual / prévia
class SearchRunIn(CamelModel):
    mode: Literal["alerts", "all"] = "alerts"


class ApiErrorOut(CamelModel):
    code: str
    message: str


class SearchStatusOut(CamelModel):
    state: Literal["idle", "running", "stopping", "done", "error"]
    analyzed: int = 0
    new_items: int = 0
    cycles: int = 0
    error: ApiErrorOut | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_cycle_at: datetime | None = None


# ---------------------------------------------------------------- resultados
class ItemOut(CamelModel):
    id: str
    title: str
    title_pt: str | None
    price: float
    price_eur: float
    price_user: float
    user_currency: str
    currency: str
    condition: Condition | None
    seller_login: str
    url: str
    photo_url: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    alert_id: str
    alert_name: str
    is_perfect: bool


class PreviewRowOut(CamelModel):
    item: ItemOut
    matched: bool
    reasons: list[str]


class PreviewOut(CamelModel):
    matched: list[PreviewRowOut]
    discarded: list[PreviewRowOut]
    analyzed: int


class ItemPageOut(CamelModel):
    items: list[ItemOut]
    next_cursor: str | None
    total: int
