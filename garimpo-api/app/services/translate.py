"""Tradução dos títulos para o idioma do usuário (português ou inglês) (MyMemory, gratuito e sem chave).

Qualquer falha (limite diário, rede, resposta estranha) devolve o texto original: um aviso nunca
deixa de sair por causa da tradução.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.config import get_settings

log = logging.getLogger("garimpo.translate")

URL = "https://api.mymemory.translated.net/get"
WORKERS = 6
_cache: dict[str, str] = {}
_MAX_CACHE = 5000


def _translate_one(text: str, target: str) -> str:
    key = f"{target}|{text}"
    if key in _cache:
        return _cache[key]
    result = text
    try:
        response = httpx.get(URL, params={"q": text, "langpair": f"autodetect|{target}"}, timeout=2.5)
        data = response.json()
        translated = (data.get("responseData") or {}).get("translatedText")
        # Quando o limite diário acaba, a API devolve um aviso em vez da tradução.
        if str(data.get("responseStatus")) == "200" and translated and "MYMEMORY WARNING" not in translated.upper():
            result = translated
    except (httpx.HTTPError, ValueError):
        pass
    if len(_cache) >= _MAX_CACHE:
        _cache.clear()
    _cache[key] = result
    return result


def translate_titles(titles: list[str], target: str = "pt") -> list[str]:
    """Traduz para `target` ("pt" ou "en")."""
    if not titles or not get_settings().translate_enabled:
        return list(titles)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(lambda title: _translate_one(title, target), titles))
