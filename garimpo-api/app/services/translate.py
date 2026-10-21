"""Tradução dos títulos para o idioma do usuário (português ou inglês) (MyMemory, gratuito e sem chave).

Qualquer falha (limite diário, rede, resposta estranha) devolve o texto original: um aviso nunca
deixa de sair por causa da tradução.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.config import get_settings

log = logging.getLogger("garimpo.translate")

URL = "https://api.mymemory.translated.net/get"
WORKERS = 6
_cache: dict[str, str] = {}
_MAX_CACHE = 5000
QUOTA_PAUSE_SECONDS = 3600  # cota diária acabou: nem tenta durante 1 h (cada tentativa só devolveria o aviso)
_paused_until = 0.0
_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()


def _executor() -> ThreadPoolExecutor:
    """Um conjunto de threads para a vida do servidor (antes eram 6 threads novas a cada aviso)."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="garimpo-translate")
        return _pool


def _translate_one(text: str, target: str) -> str:
    global _paused_until
    key = f"{target}|{text}"
    if key in _cache:
        return _cache[key]
    if time.monotonic() < _paused_until:
        return text  # sem guardar: quando a cota voltar, este título ainda pode ser traduzido
    result = text
    try:
        response = httpx.get(URL, params={"q": text, "langpair": f"autodetect|{target}"}, timeout=2.5)
        data = response.json()
        translated = (data.get("responseData") or {}).get("translatedText")
        # Quando o limite diário acaba, a API devolve um aviso em vez da tradução.
        if translated and "MYMEMORY WARNING" in str(translated).upper():
            _paused_until = time.monotonic() + QUOTA_PAUSE_SECONDS
            log.warning("Cota diária da tradução esgotada; pausando a tradução por 1 h")
            return text
        if str(data.get("responseStatus")) == "200" and translated:
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
    return list(_executor().map(lambda title: _translate_one(title, target), titles))
