from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.entitlements import entitlements_for

INSECURE_SECRET = "troque-isto-em-producao"
# A cache curta das buscas nunca pode durar mais do que o menor intervalo entre buscas de um plano (ELITE: 10 s):
# senão quem paga pelo intervalo mais curto receberia resultados repetidos.
MAX_FETCH_CACHE_SECONDS = round(min(entitlements_for(p).min_interval_minutes for p in ("FREE", "PRO", "ELITE")) * 60, 6)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./garimpo.db"

    jwt_secret: str = INSECURE_SECRET
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False
    cookie_domain: str | None = None

    web_url: str = "http://localhost:3200"
    cors_origins: list[str] = ["http://localhost:3200"]
    trust_proxy: bool = False

    # OPEN = qualquer pessoa cria conta; APPROVAL = você aprova cada uma. (Não há mais cadastro por convite.)
    registration_mode: Literal["OPEN", "APPROVAL"] = "OPEN"
    # A conta só é liberada depois de vincular um chat PRIVADO do Telegram (não há verificação por e-mail).
    require_verification: bool = True
    default_plan: Literal["FREE", "PRO", "ELITE"] = "PRO"
    # Teste grátis (sem cartão) que começa quando a conta é ativada; depois só com assinatura.
    trial_days: int = 7
    # Stripe (assinatura Garimpo Pro). Sem as chaves, o pagamento fica indisponível (o resto funciona).
    stripe_secret_key: str | None = None
    stripe_price_id: str | None = None
    stripe_webhook_secret: str | None = None
    turnstile_secret: str | None = None


    # Vinted: "live" = site de verdade; "fake" = anúncios de mentira (desenvolvimento sem internet)
    vinted_source: Literal["live", "fake"] = "live"
    vinted_min_interval_seconds: float = 1.0  # pausa entre chamadas à Vinted (proteção contra bloqueio)
    # Na 1ª busca de um alerta só entra o que foi publicado nesta janela; depois, só o que aparece de novo.
    first_run_window_seconds: float = 300.0
    # Busca contínua (botão Buscar): pausa mínima entre ciclos (na prática vale o intervalo do plano, que é
    # maior) e limite de segurança (tempo ligada sem parar).
    manual_search_pause_seconds: float = 5.0
    manual_search_max_seconds: float = 3600
    # Resultado de cada busca à Vinted reaproveitado por tantos segundos entre monitor, "Buscar" e prévia
    # (0 desliga). No máximo MAX_FETCH_CACHE_SECONDS.
    fetch_cache_seconds: float = 10.0

    # Monitor em segundo plano (desligado automaticamente nos testes)
    live_exchange_rates: bool = True  # consulta o câmbio (BCE); desligado nos testes
    # Anúncios não vistos há tantos dias saem do banco (e, em cascata, casamentos e avisos deles).
    retention_days: int = 30
    # Sem nenhum usuário com monitor ligado, o servidor só confere o banco de tantos em tantos segundos
    # (assim a Neon consegue "dormir"). Ligar o monitor acorda o servidor na hora.
    monitor_idle_seconds: int = 240
    monitor_autostart: bool = True
    monitor_tick_seconds: int = 5  # de quanto em quanto o servidor vê quem já está na hora de buscar
    translate_enabled: bool = True
    max_items_per_message: int = 5  # cartões com foto por aviso; o resto fica em Resultados

    telegram_bot_token: str | None = None
    telegram_bot_username: str = "GarimpoAlertasBot"
    telegram_webhook_secret: str | None = None

    @field_validator("registration_mode", mode="before")
    @classmethod
    def _legacy_invite_is_open(cls, value: object) -> object:
        return "OPEN" if isinstance(value, str) and value.strip().upper() == "INVITE" else value

    @field_validator(
        "cookie_domain",
        "turnstile_secret",
        "stripe_secret_key",
        "stripe_price_id",
        "stripe_webhook_secret",
        "telegram_bot_token",
        "telegram_webhook_secret",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        """`CHAVE=` vazio (ou só espaços) significa "não configurado"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("fetch_cache_seconds")
    @classmethod
    def _fetch_cache_limit(cls, value: float) -> float:
        if not 0 <= value <= MAX_FETCH_CACHE_SECONDS:
            raise ValueError(f"FETCH_CACHE_SECONDS precisa estar entre 0 e {MAX_FETCH_CACHE_SECONDS:g}")
        return value

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.environment == "production":
            if self.jwt_secret == INSECURE_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET precisa ser definido (32+ caracteres) em produção")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE precisa ser true em produção (HTTPS)")
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
