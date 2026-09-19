"""Telegram (bot central): envio de mensagens e o canal `TELEGRAM`."""

import html
import logging
import re

import httpx

from app.config import get_settings
from app.models import Destination
from app.services.messages import tr
from app.services.channels import (
    AlertMessage,
    ChannelNotConfigured,
    PermanentChannelError,
    TransientChannelError,
    register_channel,
)

log = logging.getLogger("garimpo.telegram")

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4000  # o limite real do Telegram é 4096


class TelegramClient:
    def __init__(self, token: str | None = None, timeout: float = 15.0) -> None:
        self.token = token or get_settings().telegram_bot_token
        self.timeout = timeout

    def _call(self, method: str, payload: dict) -> dict:
        if not self.token:
            raise ChannelNotConfigured("TELEGRAM_BOT_TOKEN is not set")
        try:
            response = httpx.post(API.format(token=self.token, method=method), json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise TransientChannelError(f"Telegram unreachable: {type(exc).__name__}") from exc
        try:
            data = response.json()
        except ValueError:
            data = {}
        description = str(data.get("description") or response.status_code)
        if response.status_code == 429:
            retry = (data.get("parameters") or {}).get("retry_after", 5)
            raise TransientChannelError(f"Telegram asked to wait {retry}s")
        if response.status_code >= 500:
            raise TransientChannelError(f"Telegram unavailable ({response.status_code})")
        if response.status_code in (400, 401, 403, 404) or not data.get("ok", False):
            raise PermanentChannelError(description)
        if method in ("sendMessage", "sendPhoto"):
            log.info("Telegram %s delivered (chat %s)", method, payload.get("chat_id"))
        return data.get("result") or ([] if method == "getUpdates" else {})

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        thread_id: int | None = None,
        parse_mode: str | None = None,
        buttons: list[tuple[str, str]] | None = None,
    ) -> None:
        for part in chunk_text(text):
            payload: dict = {"chat_id": chat_id, "text": part, "disable_web_page_preview": True}
            if thread_id:
                payload["message_thread_id"] = thread_id
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "url": u} for t, u in buttons]]}
            self._call("sendMessage", payload)

    def send_photo(
        self,
        chat_id: str | int,
        photo_url: str,
        caption: str,
        thread_id: int | None = None,
        buttons: list[tuple[str, str]] | None = None,
    ) -> None:
        payload: dict = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
        if thread_id:
            payload["message_thread_id"] = thread_id
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "url": u} for t, u in buttons]]}
        self._call("sendPhoto", payload)

    def get_chat_member_status(self, chat_id: str | int, user_id: int) -> str:
        return str(self._call("getChatMember", {"chat_id": chat_id, "user_id": user_id}).get("status", ""))

    def set_webhook(self, url: str, secret: str) -> None:
        self._call(
            "setWebhook",
            {
                "url": url,
                "secret_token": secret,
                "allowed_updates": ["message", "channel_post", "my_chat_member"],
                "drop_pending_updates": True,
            },
        )

    def set_profile(self, commands: list[tuple[str, str]], description: str, short_description: str) -> None:
        """Menu de comandos e textos do perfil do bot (aparecem antes de a pessoa iniciar a conversa)."""
        self._call("setMyCommands", {"commands": [{"command": c, "description": d} for c, d in commands]})
        self._call("setMyDescription", {"description": description})
        self._call("setMyShortDescription", {"short_description": short_description})

    def get_me(self) -> dict:
        return self._call("getMe", {})

    def get_updates(self, offset: int | None = None, wait: int = 0) -> list[dict]:
        """Lê as mensagens pendentes (só funciona sem webhook; serve para desenvolver sem HTTPS)."""
        payload: dict = {"timeout": wait, "allowed_updates": ["message", "channel_post", "my_chat_member"]}
        if offset is not None:
            payload["offset"] = offset
        previous, self.timeout = self.timeout, wait + 15.0
        try:
            result = self._call("getUpdates", payload)
        finally:
            self.timeout = previous
        return result if isinstance(result, list) else []


def chunk_text(text: str, limit: int = MAX_LEN) -> list[str]:
    """Quebra em blocos de até `limit` caracteres, preferindo cortar entre anúncios (linhas em branco)."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        while len(block) > limit:  # bloco gigante: corta no limite
            if current:
                parts.append(current)
                current = ""
            parts.append(block[:limit])
            block = block[limit:]
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit:
            parts.append(current)
            current = block
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _money(price: float) -> str:
    return f"{price:,.2f}"


def render_message(message: AlertMessage) -> str:
    lang = message.language
    n = len(message.items) + message.extra_count
    lines = [tr(lang, "alert_header", name=message.alert_name, n=n, new=tr(lang, "new_one" if n == 1 else "new_many"))]
    for item in message.items:
        prefix = {"PERFECT": tr(lang, "perfect") + "\n", "BEST": tr(lang, "best") + "\n"}.get(item.highlight or "", "")
        price = f"{_money(item.price)} {item.currency}"
        if item.user_currency and item.price_user is not None:
            if item.currency != item.user_currency:
                price += f" (≈ {_money(item.price_user)} {item.user_currency})"
        elif item.currency != "EUR" and item.price_eur:
            price += f" (≈ {_money(item.price_eur)} EUR)"
        facts = " | ".join(x for x in (price, item.condition, item.seller) if x)
        lines.append(f"{prefix}{facts}\n{item.title}\n{item.url}")
    if message.extra_count:
        lines.append(tr(lang, "and_more", n=message.extra_count))
    return "\n\n".join(lines)


_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}
# A Telegram recusa a foto (link ruim/imagem inválida) sem que o chat tenha problema: aí mandamos só o texto.
_PHOTO_PROBLEMS = ("wrong file identifier", "failed to get http url content", "wrong type of the web page",
                   "image_process_failed", "photo_invalid_dimensions", "wrong remote file")  # fmt: skip


def format_price(amount: float, currency: str, language: str) -> str:
    """179.2 EUR -> "€179.20" (en) / "179,20 €" (pt). Moedas sem símbolo comum ficam com o código."""
    number = f"{amount:,.2f}" if language == "en" else f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    symbol = _SYMBOLS.get(currency)
    if language == "en":
        return f"{symbol}{number}" if symbol else f"{number} {currency}"
    return f"{number} {symbol or currency}"


def flag(domain: str | None) -> str:
    if not domain or len(domain) != 2 or not domain.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("a")) for c in domain.lower())


def posted_text(age_seconds: float | None, language: str) -> str | None:
    if age_seconds is None:
        return None
    minutes = int(age_seconds // 60)
    if minutes < 1:
        return tr(language, "posted_now")
    if minutes < 60:
        return tr(language, "posted_ago", n=minutes, u="min")
    hours = minutes // 60
    if hours < 24:
        return tr(language, "posted_ago", n=hours, u="h")
    return tr(language, "posted_ago", n=hours // 24, u="d")


def render_card(item: MessageItem, alert_name: str, language: str) -> str:
    """Um anúncio como cartão (HTML do Telegram): destaque, título, preço, estado, país e há quanto tempo saiu."""
    esc = html.escape
    lines: list[str] = []
    if item.highlight:
        lines.append(f"<b>{esc(tr(language, 'perfect' if item.highlight == 'PERFECT' else 'best'))}</b>")
    lines.append(f"🛍 <b>{esc(item.title[:200])}</b>")
    if item.original_title and item.original_title.strip() != item.title.strip():
        lines.append(f"<i>{esc(item.original_title[:200])}</i>")
    if item.user_currency and item.price_user is not None:
        price = f"<b>{esc(format_price(item.price_user, item.user_currency, language))}</b>"
        if item.currency != item.user_currency:
            price += f"  ({esc(format_price(item.price, item.currency, language))})"
    else:
        price = f"<b>{esc(format_price(item.price, item.currency, language))}</b>"
    lines.append(f"💰 {price}")
    facts = " · ".join(x for x in (item.condition and f"✨ {item.condition}", flag(item.domain) and f"{flag(item.domain)} {item.domain.upper()}") if x)
    if facts:
        lines.append(facts)
    if item.seller and not item.seller.startswith("#"):
        lines.append(f"👤 {esc(item.seller)}")
    when = posted_text(item.age_seconds, language)
    if when:
        lines.append(f"⏱ <b>{esc(when)}</b>")
    lines.append(esc(tr(language, "alert_line", name=alert_name)))
    return "\n".join(lines)[:1000]


class TelegramChannel:
    name = "TELEGRAM"

    def __init__(self, client: TelegramClient | None = None) -> None:
        self._client = client

    @property
    def client(self) -> TelegramClient:
        return self._client or TelegramClient()

    def _target(self, destination: Destination) -> tuple[str, int | None]:
        if not destination.external_id:
            raise PermanentChannelError("Destination not linked yet")
        thread = (destination.config or {}).get("threadId")
        return destination.external_id, int(thread) if thread else None

    def send(self, destination: Destination, message: AlertMessage) -> None:
        """Um cartão por anúncio (foto, preço, estado, quando saiu e botão para abrir)."""
        chat_id, thread = self._target(destination)
        for item in message.items:
            if item.age_seconds is not None:
                log.info("Alert sent: listing was published ~%.0f s ago", item.age_seconds)
            caption = render_card(item, message.alert_name, message.language)
            buttons = [(tr(message.language, "open_button"), item.url)]
            if item.photo_url:
                try:
                    self.client.send_photo(chat_id, item.photo_url, caption, thread, buttons)
                    continue
                except PermanentChannelError as exc:
                    if not any(p in str(exc).lower() for p in _PHOTO_PROBLEMS):
                        raise  # chat inexistente, bot bloqueado etc.: é do destino, não da foto
            self.client.send_message(chat_id, caption, thread, parse_mode="HTML", buttons=buttons)
        if message.extra_count:
            self.client.send_message(chat_id, tr(message.language, "and_more", n=message.extra_count), thread)

    def send_rich(self, destination: Destination, html_text: str, plain_text: str, buttons: list[tuple[str, str]]) -> None:
        """HTML com botão; se o Telegram recusar o botão ou o HTML (ex.: endereço localhost em desenvolvimento),
        cai para HTML sem botão e, por último, para texto simples com o link à mostra."""
        chat_id, thread = self._target(destination)
        try:
            self.client.send_message(chat_id, html_text, thread, parse_mode="HTML", buttons=buttons)
            return
        except PermanentChannelError as exc:
            if not any(w in str(exc).lower() for w in ("url", "parse", "entities", "button")):
                raise
        try:
            self.client.send_message(chat_id, html_text, thread, parse_mode="HTML")
            return
        except PermanentChannelError as exc:
            if not any(w in str(exc).lower() for w in ("url", "parse", "entities")):
                raise
        self.client.send_message(chat_id, plain_text, thread)

    def send_text(self, destination: Destination, text: str) -> None:
        chat_id, thread = self._target(destination)
        self.client.send_message(chat_id, text, thread)


def install_telegram_channel() -> None:
    register_channel(TelegramChannel())


CODE_RE = re.compile(r"^/(start|link)(?:@\w+)?\s+([\w-]{6,64})\s*$")
# Quem digita o código à mão no chat privado (sem o comando) também vincula: os códigos têm 12 caracteres.
PLAIN_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{12}$")
