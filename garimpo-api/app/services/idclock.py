"""Relógio dos anúncios da Vinted.

A busca não informa quando o anúncio foi publicado, mas o número (id) cresce com o tempo: ~64 anúncios
novos por segundo em toda a Vinted. Guardamos um "âncora" (o maior id visto e quando) e estimamos a idade
de qualquer id. A âncora vem de uma busca sem termo (o que acabou de ser publicado no site inteiro).
O erro é de segundos, o bastante para "publicado há menos de 5 minutos".
"""

import logging
import threading
import time
from collections import deque

from app.services.vinted import ItemSource, VintedError

log = logging.getLogger("garimpo.idclock")

DEFAULT_RATE = 64.0  # ids por segundo (medido); refinado com as observações
MIN_SPAN_FOR_RATE = 120.0
REFRESH_SECONDS = 20.0


class IdClock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._anchors: deque[tuple[float, int]] = deque(maxlen=200)  # (monotonic, id)
        self._refreshed = float("-inf")

    def reset(self) -> None:
        with self._lock:
            self._anchors.clear()
            self._refreshed = float("-inf")

    # -- estado interno (com o lock) ------------------------------------------------------
    def _rate(self) -> float:
        if len(self._anchors) >= 2:
            (t0, i0), (t1, i1) = self._anchors[0], self._anchors[-1]
            if t1 - t0 >= MIN_SPAN_FOR_RATE and i1 > i0:
                return min(300.0, max(10.0, (i1 - i0) / (t1 - t0)))
        return DEFAULT_RATE

    def _now_id(self, at: float) -> float | None:
        if not self._anchors:
            return None
        t, i = self._anchors[-1]
        return i + self._rate() * (at - t)

    # -- API ------------------------------------------------------------------------------
    def observe(self, max_id: int, at: float | None = None) -> None:
        """Registra um id visto. Só vira âncora se for mais novo do que o relógio estimava."""
        at = time.monotonic() if at is None else at
        with self._lock:
            estimate = self._now_id(at)
            if estimate is None or max_id > estimate:
                self._anchors.append((at, max_id))

    def refresh(self, source: ItemSource, domain: str) -> bool:
        """Consulta o que acabou de ser publicado (busca sem termo). Devolve se há relógio utilizável."""
        now = time.monotonic()
        if now - self._refreshed >= REFRESH_SECONDS or not self._anchors:
            try:
                items = source.fetch(domain, "", 1, None)
                if items:
                    self.observe(max(i.vinted_id for i in items))
                self._refreshed = time.monotonic()
            except VintedError as exc:
                log.warning("Não consegui ajustar o relógio dos anúncios: %s", exc)
        with self._lock:
            return bool(self._anchors)

    def age_seconds(self, vinted_id: int, at: float | None = None) -> float | None:
        """Há quantos segundos o anúncio foi publicado (estimado pelo número). None se não há relógio."""
        at = time.monotonic() if at is None else at
        with self._lock:
            now_id = self._now_id(at)
            if now_id is None:
                return None
            return max(0.0, (now_id - vinted_id) / self._rate())

    def cutoff_id(self, window_seconds: float, at: float | None = None) -> int | None:
        """Menor id que ainda conta como "publicado nos últimos `window_seconds`". None se não há relógio."""
        at = time.monotonic() if at is None else at
        with self._lock:
            now_id = self._now_id(at)
            return None if now_id is None else int(now_id - self._rate() * window_seconds)


clock = IdClock()
