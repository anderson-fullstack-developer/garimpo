"""Conversão para euro.

Os limites de preço dos alertas são em EUR, mas cada país da Vinted mostra o preço na moeda local
(DKK, SEK, PLN, CZK, HUF, RON...). Comparar o número cru deixaria passar, por exemplo, 287 kr (≈ 38 €)
num filtro "entre 150 e 400 €". Taxas do Banco Central Europeu via Frankfurter (grátis, sem chave),
atualizadas a cada 12 h; se falhar, usa uma tabela aproximada.
"""

import logging
import threading
import time

import httpx

from app.config import get_settings

log = logging.getLogger("garimpo.currency")

URL = "https://api.frankfurter.dev/v1/latest"
REFRESH_SECONDS = 12 * 3600

# Unidades da moeda por 1 EUR (aproximado; só é usado se a consulta ao vivo falhar).
STATIC_RATES: dict[str, float] = {
    "EUR": 1.0, "DKK": 7.46, "SEK": 11.3, "PLN": 4.36, "CZK": 24.4, "HUF": 365.0, "RON": 5.26,
    "BGN": 1.96, "GBP": 0.86, "CHF": 0.94, "NOK": 11.6, "USD": 1.08,
}  # fmt: skip

_lock = threading.Lock()
_rates: dict[str, float] = dict(STATIC_RATES)
_fetched_at = float("-inf")  # nunca atualizou: a 1ª consulta busca o câmbio de verdade
_warned: set[str] = set()


def _refresh() -> None:
    global _fetched_at
    try:
        data = httpx.get(URL, params={"base": "EUR"}, timeout=8).json()
        fresh = {code: float(rate) for code, rate in (data.get("rates") or {}).items() if rate}
        if fresh:
            _rates.update(fresh)
            _rates["EUR"] = 1.0
    except (httpx.HTTPError, ValueError, TypeError):
        log.warning("Não consegui atualizar o câmbio; usando as taxas em memória")
    _fetched_at = time.monotonic()  # também em caso de falha: não insiste a cada anúncio


def rates() -> dict[str, float]:
    if get_settings().live_exchange_rates and time.monotonic() - _fetched_at > REFRESH_SECONDS:
        with _lock:
            if time.monotonic() - _fetched_at > REFRESH_SECONDS:
                _refresh()
    return _rates


def to_eur(amount: float, currency: str | None) -> float:
    """`amount` na moeda `currency` -> euros. Moeda desconhecida é tratada como euro (e avisada 1 vez)."""
    code = (currency or "EUR").upper()
    rate = rates().get(code)
    if not rate:
        if code not in _warned:
            _warned.add(code)
            log.warning("Moeda sem taxa de câmbio: %s (tratada como EUR)", code)
        return float(amount)
    return float(amount) / rate


def from_eur(amount: float, currency: str | None) -> float:
    """Euros -> `currency` (moeda sem taxa conhecida fica em euro)."""
    rate = rates().get((currency or "EUR").upper())
    return float(amount) * rate if rate else float(amount)
