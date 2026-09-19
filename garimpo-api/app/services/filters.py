"""Motor de filtros: decide se um anúncio satisfaz um alerta e, se não, por quê.

Portado de `find_iphone11.py` (app antigo) e generalizado. O comportamento do preset PHONES é
idêntico ao `looks_like_phone` original (há teste de paridade em tests/test_filters.py).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Protocol

from app.services.currency import to_eur
from app.services.presets import PRESETS

_PRESET_WORDS = {p["id"]: p["words"] for p in PRESETS}


def strip_accents(text: str) -> str:
    """'Película' -> 'Pelicula'. As listas de palavras ficam em ASCII e comparam com o título normalizado."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    return strip_accents(text).lower()


@lru_cache(maxsize=2048)
def _word_regex(word: str) -> re.Pattern[str]:
    # Sem limite de palavra à esquerda (aceita sufixo colado, ex.: "Telefoonhoesje"), "s" opcional de
    # plural e barra letras logo depois (evita "capa" dentro de "Capacidade").
    return re.compile(re.escape(normalize(word).strip()) + r"s?(?![a-z])")


_SEPARATORS = r"[\s\-_./]"  # "iPhone 12", "iPhone-12", "iphone_12", "iphone.12" e "iphone12" são o mesmo termo


def _tokens(query: str) -> list[str]:
    return [t for t in re.split(_SEPARATORS + "+", normalize(query)) if t]


@lru_cache(maxsize=1024)
def _phrase_regex(query: str) -> re.Pattern[str] | None:
    tokens = _tokens(query)
    if not tokens:
        return None
    return re.compile((_SEPARATORS + "*").join(re.escape(t) for t in tokens) + _tail(tokens[-1]))


def _tail(last_token: str) -> str:
    # Termo terminado em número ("iphone 12"): só barra se continuar com mais dígitos ("iphone 120"),
    # mas aceita "iPhone 12mini". Senão: aceita plural e barra prefixo de outra palavra.
    return r"(?!\d)" if last_token[-1:].isdigit() else r"s?(?![a-z])"


@lru_cache(maxsize=1024)
def _token_regexes(query: str) -> tuple[re.Pattern[str], ...]:
    tokens = _tokens(query)
    return tuple(re.compile(re.escape(t) + _tail(t)) for t in tokens)


def query_matches(title: str, query: str, match_type: str = "PHRASE") -> bool:
    text = normalize(title)
    if match_type == "ALL_WORDS":
        regexes = _token_regexes(query)
        if bool(regexes) and all(r.search(text) for r in regexes):
            return True
        # "lego star wars" também casa com "Lego StarWars" (palavras coladas): vale a frase, sem exigir espaço.
        phrase = _phrase_regex(query)
        return phrase is not None and phrase.search(text) is not None
    phrase = _phrase_regex(query)
    return phrase is not None and phrase.search(text) is not None


def excluded_word(title: str, words: list[str]) -> str | None:
    """Primeira palavra proibida encontrada no título (ou None)."""
    text = normalize(title)
    for word in words:
        if word.strip() and _word_regex(word).search(text):
            return word
    return None


class ItemLike(Protocol):
    title: str
    price: Decimal
    total_price: Decimal | None
    condition: str | None
    posted_at: datetime | None
    seller_login: str


@dataclass
class Rules:
    """As regras de um alerta (independe de banco/schemas)."""

    query: str
    match_type: str = "PHRASE"
    required_words: list[str] = field(default_factory=list)
    exclude_words: list[str] = field(default_factory=list)
    exclude_presets: list[str] = field(default_factory=list)
    min_price: float = 0
    max_price: float | None = None
    status_filter: list[str] = field(default_factory=list)
    max_age_minutes: int | None = None

    @classmethod
    def from_alert(cls, alert: object) -> "Rules":
        g = lambda name: getattr(alert, name)  # noqa: E731
        return cls(
            query=g("query"),
            match_type=g("match_type"),
            required_words=list(g("required_words") or []),
            exclude_words=list(g("exclude_words") or []),
            exclude_presets=list(g("exclude_presets") or []),
            min_price=float(g("min_price") or 0),
            max_price=None if g("max_price") is None else float(g("max_price")),
            status_filter=list(g("status_filter") or []),
            max_age_minutes=g("max_age_minutes"),
        )

    @property
    def all_excluded_words(self) -> list[str]:
        words = list(self.exclude_words)
        for preset in self.exclude_presets:
            words.extend(_PRESET_WORDS.get(preset, []))
        return words


def price_of(item: ItemLike) -> float:
    """Preço final que o comprador paga (com taxa de proteção) quando disponível."""
    return float(item.total_price if item.total_price else item.price)


def price_eur_of(item: ItemLike) -> float:
    """Preço em euros (os limites dos alertas são em EUR; cada país mostra a moeda local)."""
    return to_eur(price_of(item), getattr(item, "currency", "EUR"))


def evaluate(rules: Rules, item: ItemLike, now: datetime | None = None) -> list[str]:
    """Motivos pelos quais o anúncio NÃO casa com o alerta. Lista vazia = casa."""
    reasons: list[str] = []
    if not query_matches(item.title, rules.query, rules.match_type):
        reasons.append("query_not_matched")

    text = normalize(item.title)
    for word in rules.required_words:
        if word.strip() and not _word_regex(word).search(text):
            reasons.append(f"missing_required_word:{word}")

    bad = excluded_word(item.title, rules.all_excluded_words)
    if bad:
        reasons.append(f"excluded_by_word:{bad}")

    price = price_eur_of(item)
    if price < rules.min_price:
        reasons.append("below_min_price")
    if rules.max_price is not None and price > rules.max_price:
        reasons.append("above_max_price")

    # Estado desconhecido (idioma não mapeado) não elimina o anúncio.
    if rules.status_filter and item.condition and item.condition not in rules.status_filter:
        reasons.append("condition_not_allowed")

    # Sem data de postagem (a Vinted não a informa na busca) o filtro de idade não se aplica.
    if rules.max_age_minutes is not None and item.posted_at is not None:
        now = now or datetime.now(timezone.utc)
        if (now - item.posted_at).total_seconds() / 60 > rules.max_age_minutes:
            reasons.append("too_old")
    return reasons


def dedupe(items: list, key=None) -> list:
    """Remove anúncios repetidos (mesmo vendedor + mesmo título + mesmo preço), mantendo o primeiro."""
    key = key or (lambda i: (i.seller_login, i.title.strip().lower(), round(price_of(i), 2)))
    seen: set = set()
    out = []
    for item in items:
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out
