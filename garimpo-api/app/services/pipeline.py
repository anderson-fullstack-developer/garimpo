"""Busca -> guarda -> casa com os alertas -> decide o que é novo -> avisa.

Ideias principais:
- **Busca compartilhada** (D9): alertas com o mesmo (país, termo, páginas, filtros da Vinted) geram UMA
  chamada à Vinted por ciclo, mesmo que sejam de usuários diferentes.
- **Baseline por alerta**: na primeira vez que um alerta é processado, o que já existe é gravado como
  "visto", sem avisar (a menos que o usuário peça `notifyOnFirstRun`).
- **Idempotência**: `Match` é único por (alerta, anúncio) e `Notification` por (usuário, anúncio).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.countries import COUNTRY_CODES, EUROPE
from app.models import Alert, Destination, Item, MonitorRun, Match, Notification, PriceSnapshot, User, new_id, utcnow
from app.services import channels, idclock
from app.services.channels import (
    AlertMessage,
    ChannelError,
    MessageItem,
    PermanentChannelError,
    TransientChannelError,
)
from app.services.currency import from_eur, to_eur
from app.services.messages import normalize_language, tr
from app.services.filters import Rules, dedupe, evaluate, price_of
from app.services.translate import translate_titles
from app.services.vinted import (
    ItemSource,
    RateLimitedError,
    RawItem,
    VintedError,
)

log = logging.getLogger("garimpo.pipeline")

# `last_seen_at` só serve para decidir o que apagar (retenção): precisão de 1 h basta.
SEEN_REFRESH = timedelta(hours=1)

# ------------------------------------------------------------------ chaves de busca
@dataclass(frozen=True)
class SearchKey:
    domain: str
    query: str
    pages: int
    params_json: str = "{}"

    @property
    def label(self) -> str:
        return f"{self.domain}|{self.query}|{self.pages}"[:200]

    @property
    def params(self) -> dict:
        return json.loads(self.params_json)


def domains_for(country: str) -> list[str]:
    return list(COUNTRY_CODES) if country == EUROPE else [country]


def keys_for(alert_like: object) -> list[SearchKey]:
    query = " ".join(str(getattr(alert_like, "query")).lower().split())
    params = getattr(alert_like, "vinted_params", None) or {}
    params_json = json.dumps(params, sort_keys=True)
    pages = int(getattr(alert_like, "pages"))
    return [SearchKey(d, query, pages, params_json) for d in domains_for(getattr(alert_like, "country"))]


@dataclass
class KeyResult:
    key: SearchKey
    items: list[RawItem] = field(default_factory=list)
    status: str = "ok"  # ok | error | rate_limited | skipped
    error: str | None = None
    started_at: datetime = field(default_factory=utcnow)
    ended_at: datetime | None = None


def fetch_keys(source: ItemSource, keys: list[SearchKey]) -> tuple[dict[SearchKey, KeyResult], bool]:
    """Busca cada chave uma vez. Ao tomar 429, para de insistir nas demais. Devolve (resultados, limitado)."""
    results: dict[SearchKey, KeyResult] = {}
    limited = False
    for key in dict.fromkeys(keys):  # únicas, na ordem
        result = KeyResult(key)
        results[key] = result
        if limited:
            result.status, result.error = "skipped", "Skipped after the request limit"
            continue
        try:
            for page in range(1, key.pages + 1):
                page_items = source.fetch(key.domain, key.query, page, key.params or None)
                result.items.extend(page_items)
                if not page_items:
                    break
        except RateLimitedError as exc:
            limited = True
            result.status, result.error = "rate_limited", str(exc)
        except VintedError as exc:
            log.warning("Falha ao buscar %s: %s", key.label, exc)
            result.status, result.error = "error", str(exc)
        result.ended_at = utcnow()
    return results, limited


# ------------------------------------------------------------------ guardar anúncios
MAX_ESTIMATE_AGE = 7 * 86400  # acima disso o número do anúncio é velho demais para estimar com segurança


def _estimate_posted_at(vinted_id: int, now: datetime) -> datetime | None:
    """A Vinted não informa a hora da postagem; estimamos pelo número do anúncio (relógio de ids)."""
    age = idclock.clock.age_seconds(vinted_id)
    if age is None or age > MAX_ESTIMATE_AGE:
        return None
    return now - timedelta(seconds=age)


def store_items(db: Session, raws: list[RawItem]) -> dict[int, Item]:
    """Cria/atualiza o catálogo global. Devolve {vinted_id: Item}."""
    unique = {r.vinted_id: r for r in raws}
    if not unique:
        return {}
    existing = {
        i.vinted_id: i for i in db.scalars(select(Item).where(Item.vinted_id.in_(list(unique))))
    }
    now = utcnow()
    created: list[Item] = []
    price_points: list[PriceSnapshot] = []
    for vid, raw in unique.items():
        price = price_of(raw)
        item = existing.get(vid)
        if item is None:
            item = Item(
                id=new_id(),
                vinted_id=vid,
                domain=raw.domain,
                title=raw.title[:300],
                price=price,
                currency=raw.currency,
                condition=raw.condition,
                seller_login=raw.seller_login[:80],
                url=raw.url[:500],
                photo_url=(raw.photo_url or None) and raw.photo_url[:500],
                posted_at=raw.posted_at or _estimate_posted_at(vid, now),
                first_seen_at=now,
                last_seen_at=now,
            )
            created.append(item)
            price_points.append(PriceSnapshot(item_id=item.id, price=price, at=now))
            existing[vid] = item
        else:
            if now - item.last_seen_at > SEEN_REFRESH:  # evita 96 UPDATEs por busca a cada ciclo
                item.last_seen_at = now
            if float(item.price) != float(price):
                item.price = price
                price_points.append(PriceSnapshot(item_id=item.id, price=price, at=now))
    # Em lote: com o banco na nuvem cada ida e volta custa dezenas de ms (96 anúncios ≠ 96 idas).
    db.add_all(created)
    db.flush()  # os anúncios antes do histórico de preço, que aponta para eles
    db.add_all(price_points)
    return existing


# ------------------------------------------------------------------ casar com alertas
@dataclass
class AlertOutcome:
    alert: Alert
    new: list[Item] = field(default_factory=list)  # novos casamentos a AVISAR (já sem os silenciosos)
    matched_now: int = 0  # quantos casamentos novos foram criados (avisados ou não)


def _mark_seen(db: Session, user_id: str, item_ids: list[str], reason: str) -> None:
    db.flush()  # a sessão não grava sozinha: sem isso não enxergaríamos avisos pendentes do mesmo usuário
    already = set(
        db.scalars(select(Notification.item_id).where(Notification.user_id == user_id, Notification.item_id.in_(item_ids)))
    )
    for item_id in item_ids:
        if item_id not in already:
            db.add(Notification(user_id=user_id, item_id=item_id, ok=True, error=reason))


def process_alert(
    db: Session,
    alert: Alert,
    raws: list[RawItem],
    items_by_vid: dict[int, Item],
    *,
    silent_reason: str | None = None,
    first_run_floor: int | None = None,
) -> AlertOutcome:
    """`first_run_floor`: na 1ª busca do alerta, só conta anúncio com id maior que isto (None = sem corte)."""
    rules = Rules.from_alert(alert)
    first_run = alert.baselined_at is None
    if first_run:
        alert.min_item_id = first_run_floor
    floor = alert.min_item_id or 0
    candidates = dedupe([r for r in raws if r.vinted_id > floor and not evaluate(rules, r)])
    outcome = AlertOutcome(alert)
    db.flush()
    if candidates:
        item_ids = [items_by_vid[r.vinted_id].id for r in candidates]
        matched = set(db.scalars(select(Match.item_id).where(Match.alert_id == alert.id, Match.item_id.in_(item_ids))))
        for raw in candidates:
            item = items_by_vid[raw.vinted_id]
            if item.id in matched:
                continue
            db.add(Match(user_id=alert.user_id, alert_id=alert.id, item_id=item.id))
            matched.add(item.id)
            outcome.new.append(item)
    outcome.matched_now = len(outcome.new)

    alert.baselined_at = alert.baselined_at or utcnow()
    if silent_reason:
        _mark_seen(db, alert.user_id, [i.id for i in outcome.new], silent_reason)
        outcome.new = []
    elif first_run and not alert.notify_on_first_run:
        _mark_seen(db, alert.user_id, [i.id for i in outcome.new], "baseline")
        outcome.new = []
    return outcome


@dataclass
class RunSummary:
    analyzed: int = 0
    new_matches: int = 0
    sent: int = 0
    errors: list[str] = field(default_factory=list)
    rate_limited: bool = False
    outcomes: list[AlertOutcome] = field(default_factory=list)


def run_alerts(db: Session, source: ItemSource, alerts: list[Alert], *, silent_reason: str | None = None) -> RunSummary:
    """Busca e casa `alerts` (sem enviar nada). O envio é feito por `notify_outcomes`."""
    summary = RunSummary()
    keys_by_alert = {a.id: keys_for(a) for a in alerts}
    all_keys = [k for keys in keys_by_alert.values() for k in keys]
    results, summary.rate_limited = fetch_keys(source, all_keys)

    # O mesmo anúncio pode aparecer em vários países (com o preço na moeda de cada um). Vale UM registro
    # por id, o do primeiro país consultado; as comparações de preço são feitas em euros.
    canonical: dict[int, RawItem] = {}
    for key in dict.fromkeys(all_keys):
        for raw in results[key].items:
            canonical.setdefault(raw.vinted_id, raw)
    summary.analyzed = len(canonical)
    first_run_floor = None
    if getattr(source, "has_id_clock", False):
        # O relógio dos anúncios serve à janela da 1ª busca e ao "publicado há X min" dos avisos.
        domain = all_keys[0].domain if all_keys else "pt"
        if idclock.clock.refresh(source, domain):
            for raw in canonical.values():
                idclock.clock.observe(raw.vinted_id)
            if any(a.baselined_at is None for a in alerts):
                first_run_floor = idclock.clock.cutoff_id(get_settings().first_run_window_seconds)
    items_by_vid = store_items(db, list(canonical.values()))

    matched_by_key: dict[SearchKey, int] = {}
    for alert in alerts:
        keys = keys_by_alert[alert.id]
        ok = [results[k].status == "ok" for k in keys]
        # Sem nenhuma busca funcionando não há o que processar. E um alerta que ainda não fez o baseline
        # só começa com TODAS as buscas ok: com dados parciais, o país que falhou "invadiria" depois.
        if not any(ok) or (alert.baselined_at is None and not all(ok)):
            continue
        raws = list({raw.vinted_id: canonical[raw.vinted_id] for k in keys for raw in results[k].items}.values())
        outcome = process_alert(
            db, alert, raws, items_by_vid, silent_reason=silent_reason, first_run_floor=first_run_floor
        )
        summary.outcomes.append(outcome)
        summary.new_matches += outcome.matched_now
        for k in keys:
            matched_by_key[k] = matched_by_key.get(k, 0) + outcome.matched_now

    for key, result in results.items():
        if result.error:
            summary.errors.append(result.error)
        db.add(
            MonitorRun(
                search_key=key.label,
                started_at=result.started_at,
                ended_at=result.ended_at,
                status=result.status if result.status in ("ok", "error", "rate_limited") else "error",
                raw_count=len(result.items),
                match_count=matched_by_key.get(key, 0),
                error=result.error,
            )
        )
    return summary


# ------------------------------------------------------------------ avisar
def _destination_for(db: Session, alert: Alert) -> Destination | None:
    if alert.destination_id:
        dest = db.get(Destination, alert.destination_id)
        if dest is not None and dest.status == "LINKED":
            return dest
    linked = db.scalars(
        select(Destination).where(Destination.user_id == alert.user_id, Destination.linked_at.is_not(None))
    ).all()
    linked = [d for d in linked if d.disconnected_at is None]
    return next((d for d in linked if d.is_default), linked[0] if linked else None)


def _is_perfect(alert: Alert, price_eur: float) -> bool:
    lo, hi = alert.perfect_min, alert.perfect_max
    if lo is None and hi is None:
        return False
    return (lo is None or price_eur >= float(lo)) and (hi is None or price_eur <= float(hi))


def _age_seconds(item: Item) -> float | None:
    """Há quanto tempo foi publicado: pela data, se a Vinted deu; senão, pelo relógio dos números."""
    if item.posted_at is not None:
        return max(0.0, (utcnow() - item.posted_at).total_seconds())
    return idclock.clock.age_seconds(item.vinted_id)


_CONDITIONS = {"new_with_tags", "new_without_tags", "very_good", "good", "satisfactory"}

# Só falamos de "preço abaixo da média" com uma base mínima de anúncios anteriores (senão a "média" é ruído).
MIN_PRICE_HISTORY = 3
# E só quando a diferença é grande o bastante para valer a pena chamar atenção (ruído normal de preço, não).
BELOW_AVG_THRESHOLD_PCT = -10.0


def _price_history_eur(db: Session, alert: Alert, exclude_item_ids: set[str]) -> list[float]:
    """Preço (em EUR) dos anúncios que já bateram com este alerta antes, para servir de "preço normal"."""
    query = select(Item.price, Item.currency).join(Match, Match.item_id == Item.id).where(Match.alert_id == alert.id)
    if exclude_item_ids:
        query = query.where(Item.id.notin_(exclude_item_ids))
    return [to_eur(float(price), currency) for price, currency in db.execute(query).all()]


def build_message(
    db: Session, alert: Alert, items: list[Item], user: User | None = None, language: str | None = None
) -> AlertMessage:
    """`language`: idioma do destino; sem ele vale o da conta."""
    limit = get_settings().max_items_per_message
    ordered = sorted(items, key=lambda i: to_eur(float(i.price), i.currency))
    shown = ordered[:limit]
    language = normalize_language(language or (user.language if user else None))
    currency = user.currency if user else "EUR"
    titles = translate_titles([i.title for i in shown], language)
    history = _price_history_eur(db, alert, {i.id for i in items})
    avg_price_eur = sum(history) / len(history) if len(history) >= MIN_PRICE_HISTORY else None
    message_items: list[MessageItem] = []
    for index, (item, title) in enumerate(zip(shown, titles)):
        price = float(item.price)
        price_eur = to_eur(price, item.currency)
        if language == "pt" and title != item.title:
            item.title_pt = title[:300]
        highlight = "PERFECT" if _is_perfect(alert, price_eur) else ("BEST" if len(ordered) >= 4 and index < 3 else None)
        vs_avg_pct = ((price_eur - avg_price_eur) / avg_price_eur * 100) if avg_price_eur else None
        if vs_avg_pct is not None and vs_avg_pct > BELOW_AVG_THRESHOLD_PCT:
            vs_avg_pct = None  # só vale destacar quando é bem mais barato que o normal
        message_items.append(
            MessageItem(
                title=title,
                price=price,
                price_eur=round(price_eur, 2),
                price_user=round(from_eur(price_eur, currency), 2),
                user_currency=currency,
                currency=item.currency,
                url=item.url,
                condition=tr(language, f"cond_{item.condition}") if item.condition in _CONDITIONS else None,
                seller=item.seller_login,
                highlight=highlight,
                photo_url=item.photo_url,
                original_title=item.title,
                domain=item.domain,
                age_seconds=_age_seconds(item),
                price_vs_avg_pct=round(vs_avg_pct, 1) if vs_avg_pct is not None else None,
            )
        )
    return AlertMessage(alert.name, message_items, extra_count=len(ordered) - len(shown), language=language)


def _pending_items(db: Session, alert: Alert) -> list[Item]:
    """Anúncios que casaram com o alerta e ainda não foram avisados a este usuário.

    Isso (e não só "o que é novo neste ciclo") é o que garante que um envio que falhou por motivo
    passageiro seja refeito no ciclo seguinte, em vez de o aviso se perder.
    """
    db.flush()
    already = exists().where(Notification.user_id == alert.user_id, Notification.item_id == Item.id)
    return list(
        db.scalars(select(Item).join(Match, Match.item_id == Item.id).where(Match.alert_id == alert.id, ~already))
    )


def notify_outcomes(db: Session, outcomes: list[AlertOutcome]) -> tuple[int, list[str]]:
    """Envia o que está pendente. Devolve (anúncios avisados, erros)."""
    sent, errors = 0, []
    for outcome in outcomes:
        alert = outcome.alert
        # Um anúncio pode casar com 2 alertas do mesmo usuário: quem chega primeiro avisa (e o segundo
        # já o encontra registrado em Notification).
        items = _pending_items(db, alert)
        if not items:
            continue

        destination = _destination_for(db, alert)
        if destination is None:
            for item in items:
                db.add(Notification(user_id=alert.user_id, item_id=item.id, ok=False, error="sem destino conectado"))
            continue

        owner = db.get(User, alert.user_id)
        message = build_message(db, alert, items, owner, destination.language)
        try:
            channels.get_channel(destination.channel).send(destination, message)
        except TransientChannelError as exc:
            errors.append(str(exc))  # sem Notification: tenta de novo no próximo ciclo
            continue
        except PermanentChannelError as exc:
            destination.disconnected_at = utcnow()  # bot removido/bloqueado: o usuário precisa reconectar
            errors.append(str(exc))
            for item in items:
                db.add(Notification(user_id=alert.user_id, item_id=item.id, ok=False, error=str(exc)[:500]))
            continue
        except ChannelError as exc:
            errors.append(str(exc))
            continue
        for item in items:
            db.add(Notification(user_id=alert.user_id, item_id=item.id, ok=True))
        sent += len(items)
    return sent, errors


def due_interval(user: User, settings_interval: float) -> timedelta:
    from app.entitlements import entitlements_for

    return timedelta(minutes=max(settings_interval, entitlements_for(user.plan).min_interval_minutes))
