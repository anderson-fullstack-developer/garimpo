"""Camada de canais de notificação (D16): o monitor só conhece `AlertMessage` e a interface `Channel`.

Telegram é o primeiro canal. Para trocar/adicionar outro (WhatsApp, e-mail, push...) basta implementar
`Channel` e registrar com `register_channel`; alertas, monitor e banco não mudam.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.models import Destination


class ChannelError(Exception):
    """Falha ao entregar uma mensagem."""


class TransientChannelError(ChannelError):
    """Tente de novo depois (limite de envio, rede, servidor do canal fora)."""


class PermanentChannelError(ChannelError):
    """Não adianta tentar de novo (bot removido, chat inexistente, bloqueado)."""


class ChannelNotConfigured(ChannelError):
    """O canal não tem credenciais configuradas neste servidor."""


Highlight = Literal["PERFECT", "BEST"] | None


@dataclass
class MessageItem:
    title: str
    price: float
    currency: str
    url: str
    condition: str | None = None
    seller: str | None = None
    highlight: Highlight = None
    photo_url: str | None = None
    price_eur: float | None = None  # equivalente em euros (mostrado só se a moeda não for EUR)
    price_user: float | None = None  # equivalente na moeda do usuário (tem prioridade sobre o euro)
    user_currency: str | None = None
    original_title: str | None = None  # título antes da tradução
    domain: str | None = None  # país do anúncio (pt, fr, pl...)
    age_seconds: float | None = None  # há quanto tempo foi publicado (estimado)
    price_vs_avg_pct: float | None = None  # % abaixo da média histórica deste alerta (só quando é notável)


@dataclass
class AlertMessage:
    alert_name: str
    items: list[MessageItem] = field(default_factory=list)
    extra_count: int = 0  # anúncios que ficaram de fora da mensagem (limite por mensagem)
    language: str = "pt"  # idioma do usuário (pt/en)


class Channel(Protocol):
    name: str

    def send(self, destination: Destination, message: AlertMessage) -> None: ...

    def send_text(self, destination: Destination, text: str) -> None: ...


_registry: dict[str, Channel] = {}


def register_channel(channel: Channel) -> None:
    _registry[channel.name] = channel


def get_channel(name: str) -> Channel:
    if name not in _registry:
        raise ChannelNotConfigured(f"Canal desconhecido: {name}")
    return _registry[name]


def reset_channels() -> None:
    _registry.clear()
