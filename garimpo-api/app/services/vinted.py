"""Leitura pública da Vinted.

A API JSON antiga (`/api/v2/catalog/items`) hoje responde 404. A página de busca do site, porém,
traz os anúncios embutidos no HTML (JSON dentro de `self.__next_f.push`). É isso que lemos aqui.
Todo o conhecimento sobre esse formato fica neste arquivo: se a Vinted mudar a página, só ele muda
(e o erro `FormatChangedError` avisa em vez de gerar lixo).

A página NÃO informa a data de postagem nem o login do vendedor; usamos o momento em que o anúncio
foi detectado e o id do vendedor.
"""

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.config import get_settings
from app.services.filters import normalize

log = logging.getLogger("garimpo.vinted")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class VintedError(Exception):
    """Erro ao ler a Vinted."""


class RateLimitedError(VintedError):
    """HTTP 429: pedimos demais. O monitor reduz o ritmo."""


class BlockedError(VintedError):
    """A proteção do site (Cloudflare/DataDome) barrou o acesso."""


class FormatChangedError(VintedError):
    """A página mudou e não achamos mais os anúncios."""


class UpstreamError(VintedError):
    """Falha de rede ou resposta inesperada."""


@dataclass(frozen=True)
class RawItem:
    vinted_id: int
    domain: str
    title: str
    price: Decimal
    total_price: Decimal | None
    currency: str
    condition: str | None  # new_with_tags | new_without_tags | very_good | good | satisfactory
    condition_text: str | None
    seller_login: str
    url: str
    photo_url: str | None
    posted_at: datetime | None = None


# ------------------------------------------------------------------ estado do produto (por idioma)
_CONDITIONS: dict[str, tuple[str, ...]] = {
    "new_with_tags": (
        "novo com etiquetas", "novo com etiqueta", "neuf avec etiquette", "neuf avec etiquettes",
        "nuevo con etiquetas", "nuovo con cartellino", "neu mit etikett", "neu mit etiketten",
        "nieuw met kaartje", "nowy z metka", "new with tags",
    ),
    "new_without_tags": (
        "novo sem etiquetas", "novo sem etiqueta", "neuf sans etiquette", "neuf sans etiquettes",
        "nuevo sin etiquetas", "nuovo senza cartellino", "neu ohne etikett", "nieuw zonder kaartje",
        "nowy bez metki", "new without tags",
    ),
    "very_good": (
        "muito bom", "tres bon etat", "muy bueno", "ottime condizioni", "sehr gut", "zeer goed",
        "bardzo dobry", "very good",
    ),
    "good": ("bom", "bon etat", "bueno", "buone condizioni", "gut", "goed", "dobry", "good"),
    "satisfactory": (
        "satisfatorio", "satisfaisant", "satisfactorio", "condizioni soddisfacenti",
        "zufriedenstellend", "voldoende", "zadowalajacy", "satisfactory",
    ),
}  # fmt: skip
_CONDITION_LOOKUP = {text: key for key, texts in _CONDITIONS.items() for text in texts}


def condition_from_text(text: str | None) -> str | None:
    """"36 · Novo com etiquetas" -> new_with_tags. Idioma não mapeado -> None (não elimina o anúncio)."""
    if not text:
        return None
    for part in reversed(re.split(r"[·•]", text)):
        found = _CONDITION_LOOKUP.get(re.sub(r"\s+", " ", normalize(part)).strip())
        if found:
            return found
    return None


# ------------------------------------------------------------------ extração da página
_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
_MARKER = '"items":{"items":'


def _money(node: Any) -> Decimal | None:
    try:
        return Decimal(str(node["amount"]))
    except (TypeError, KeyError, InvalidOperation):
        return None


def parse_catalog_html(html: str, domain: str) -> list[RawItem]:
    chunks = _CHUNK_RE.findall(html)
    if not chunks:
        raise FormatChangedError("The search page no longer contains the expected data")
    try:
        blob = json.loads('"' + "".join(chunks) + '"')
        start = blob.find(_MARKER)
        if start < 0:
            raise FormatChangedError("Listing list not found on the page")
        entries, _ = json.JSONDecoder().raw_decode(blob, start + len(_MARKER))
    except (json.JSONDecodeError, ValueError) as exc:
        raise FormatChangedError(f"Could not read the listings on the page: {exc}") from exc
    if not isinstance(entries, list):
        raise FormatChangedError("Unexpected format of the listing list")

    base = f"https://www.vinted.{domain}"
    items: list[RawItem] = []
    for entry in entries:
        product = entry.get("productItem") if isinstance(entry, dict) else None
        if not isinstance(product, dict):
            continue
        price = _money(product.get("price"))
        try:
            vinted_id, title = int(product["id"]), str(product["title"])
        except (KeyError, TypeError, ValueError):
            continue
        if price is None or not title:
            continue
        photos = product.get("photos") or []
        photo = product.get("thumbnailUrl") or (photos[0].get("url") if photos else None)
        second_line = (product.get("itemBox") or {}).get("secondLine")
        url = str(product.get("url") or f"/items/{vinted_id}")
        user = product.get("user") or {}
        items.append(
            RawItem(
                vinted_id=vinted_id,
                domain=domain,
                title=title,
                price=price,
                total_price=_money(product.get("totalItemPrice")),
                currency=str((product.get("price") or {}).get("currencyCode") or "EUR"),
                condition=condition_from_text(second_line),
                condition_text=second_line if isinstance(second_line, str) else None,
                seller_login=f"#{user.get('id')}" if user.get("id") else "vendedor",
                url=url if url.startswith("http") else base + url,
                photo_url=photo if isinstance(photo, str) else None,
            )
        )
    return items


# ------------------------------------------------------------------ fontes de anúncios
class ItemSource(Protocol):
    def fetch(self, domain: str, query: str, page: int = 1, params: dict | None = None) -> list[RawItem]: ...


def _query_params(query: str, page: int, params: dict | None) -> list[tuple[str, str]]:
    out = [("search_text", query), ("order", "newest_first"), ("page", str(page))]
    for key, value in (params or {}).items():
        name = "catalog[]" if key == "catalog_ids" else f"{key}[]" if key.endswith("_ids") else key
        for v in value if isinstance(value, list) else [value]:
            out.append((name, str(v)))
    return out


class VintedClient:
    """Cliente real. Sessões por país, uma requisição por vez e com intervalo mínimo entre elas."""

    has_id_clock = True  # a busca sem termo mostra o que acabou de ser publicado (âncora do relógio de ids)

    def __init__(self, min_interval: float = 1.5, timeout: float = 30.0) -> None:
        self.min_interval = min_interval
        self.timeout = timeout
        self._sessions: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._last = 0.0

    def _session(self, domain: str) -> Any:
        if domain not in self._sessions:
            import cloudscraper  # importado aqui: só quem usa a fonte real precisa dele

            self._sessions[domain] = cloudscraper.create_scraper()
        return self._sessions[domain]

    def fetch(self, domain: str, query: str, page: int = 1, params: dict | None = None) -> list[RawItem]:
        with self._lock:  # educado com a Vinted e evita rajadas
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            try:
                response = self._session(domain).get(
                    f"https://www.vinted.{domain}/catalog",
                    params=_query_params(query, page, params),
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"},
                    timeout=self.timeout,
                )
            except Exception as exc:  # rede, timeout, desafio não resolvido...
                raise UpstreamError(f"Failed to reach vinted.{domain}: {type(exc).__name__}") from exc
            finally:
                self._last = time.monotonic()

        if response.status_code == 429:
            raise RateLimitedError(f"vinted.{domain} asked to slow down (429)")
        if response.status_code in (401, 403, 503) or "cf-chl" in response.text[:2000]:
            self._sessions.pop(domain, None)  # próxima vez começa uma sessão nova
            raise BlockedError(f"vinted.{domain} blocked access ({response.status_code})")
        if response.status_code != 200:
            raise UpstreamError(f"vinted.{domain} answered {response.status_code}")
        return parse_catalog_html(response.text, domain)


class FakeSource:
    """Anúncios de mentira (desenvolvimento sem internet). Aparece um anúncio novo por minuto."""

    _TEMPLATES = (
        "{q} 64GB preto", "Capa {q} silicone", "{q} 128GB como novo", "Película de vidro {q}",
        "{q} muito bom estado", "Carregador para {q}", "{q} com caixa e acessórios", "{q} ecrã partido para peças",
    )  # fmt: skip

    def fetch(self, domain: str, query: str, page: int = 1, params: dict | None = None) -> list[RawItem]:
        if page > 1:
            return []
        minute = int(time.time() // 60)
        items = []
        for offset in range(0, 24):
            m = minute - offset
            seed = (m * 7919 + sum(map(ord, query))) % 100000
            title = self._TEMPLATES[seed % len(self._TEMPLATES)].format(q=query.title())
            price = Decimal(20 + seed % 160)
            items.append(
                RawItem(
                    vinted_id=1_000_000_000 + m * 10 + (sum(map(ord, domain)) % 10),
                    domain=domain,
                    title=title,
                    price=price,
                    total_price=price + Decimal("1.90"),
                    currency="EUR",
                    condition=("very_good", "good", "new_without_tags")[seed % 3],
                    condition_text=None,
                    seller_login=f"#{seed}",
                    url=f"https://www.vinted.{domain}/items/{1_000_000_000 + m * 10}",
                    photo_url=f"https://picsum.photos/seed/{seed}/310/430",
                )
            )
        return items


_source: ItemSource | None = None


def get_source() -> ItemSource:
    global _source
    if _source is None:
        settings = get_settings()
        _source = (
            FakeSource()
            if settings.vinted_source == "fake"
            else VintedClient(min_interval=settings.vinted_min_interval_seconds)
        )
    return _source


def set_source(source: ItemSource | None) -> None:
    """Troca a fonte (testes) ou volta ao padrão (None)."""
    global _source
    _source = source
