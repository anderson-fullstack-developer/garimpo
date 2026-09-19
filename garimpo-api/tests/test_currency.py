"""Preços em moedas diferentes e o mesmo anúncio aparecendo em vários países."""

from dataclasses import replace
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import Item, Match
from app.services import currency
from app.services.channels import AlertMessage, MessageItem
from app.services.filters import Rules, evaluate
from app.services.telegram import render_message
from tests.conftest import ALERT, T, make_raw


def raw(price, currency, title="Playstation 5", domain="pt", vid=1):
    return replace(make_raw(vid, title, price, domain=domain), currency=currency)


# ------------------------------------------------------------------ conversão
def test_static_rates_convert_to_euro(settings):
    assert currency.to_eur(100, "EUR") == 100
    assert currency.to_eur(746, "DKK") == pytest.approx(100, rel=0.01)
    assert currency.to_eur(436, "PLN") == pytest.approx(100, rel=0.01)
    assert currency.to_eur(50, "dkk") == currency.to_eur(50, "DKK")  # não diferencia maiúsculas
    assert currency.to_eur(70, None) == 70  # sem moeda = euro


def test_unknown_currency_is_treated_as_euro(settings):
    assert currency.to_eur(10, "XYZ") == 10


def test_live_rates_update_and_failure_falls_back(settings, monkeypatch):
    monkeypatch.setattr(settings, "live_exchange_rates", True)
    monkeypatch.setattr(currency, "_fetched_at", float("-inf"))
    monkeypatch.setitem(currency._rates, "DKK", 7.46)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, json={"rates": {"DKK": 10.0}}, request=httpx.Request("GET", "x")))
    assert currency.to_eur(100, "DKK") == pytest.approx(10.0)

    monkeypatch.setattr(currency, "_fetched_at", float("-inf"))

    def boom(*a, **k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "get", boom)
    assert currency.to_eur(100, "DKK") == pytest.approx(10.0)  # mantém a última taxa conhecida


# ------------------------------------------------------------------ filtros em euro
def test_price_limits_are_applied_in_euros(settings):
    rules = Rules(query="playstation 5", min_price=150, max_price=400)
    # 287 kr ≈ 38 €: antes passava (287 está entre 150 e 400), agora é barato demais
    assert evaluate(rules, raw(286.86, "DKK")) == ["below_min_price"]
    # 320 zł ≈ 73 €
    assert evaluate(rules, raw(320, "PLN")) == ["below_min_price"]
    # 2.500 kr ≈ 335 €: dentro da faixa mesmo o número sendo grande
    assert evaluate(rules, raw(2500, "DKK")) == []
    assert evaluate(rules, raw(250, "EUR")) == []
    assert evaluate(rules, raw(74.2, "EUR")) == ["below_min_price"]
    assert evaluate(rules, raw(9000, "DKK")) == ["above_max_price"]  # ≈ 1.200 €


# ------------------------------------------------------------------ mesmo anúncio em vários países
def test_listing_visible_in_two_countries_is_one_item_matched_once(client, signup, link_destination, fake_source, fake_channel, engine_, session_factory):
    signup(client)
    link_destination("ana@example.com")
    client.post("/alerts", json={**ALERT, "query": "playstation 5", "country": "eu", "minPrice": 150, "maxPrice": 400, "notifyOnFirstRun": True})
    client.post("/monitor/start")
    # O MESMO anúncio (id 7) em três países: 74,20 € na Finlândia, ~320 zł na Polônia, 553 kr na Dinamarca.
    fake_source.put("playstation 5", [raw(74.2, "EUR", domain="fi", vid=7)], domain="fi")
    fake_source.put("playstation 5", [raw(320, "PLN", domain="pl", vid=7)], domain="pl")
    fake_source.put("playstation 5", [raw(553, "DKK", domain="dk", vid=7)], domain="dk")
    fake_source.put("playstation 5", [raw(250, "EUR", domain="pt", vid=8, title="Playstation 5 Slim")], domain="pt")

    result = engine_.tick(T(0))
    with session_factory() as db:
        items = db.scalars(select(Item)).all()
        assert sorted(i.vinted_id for i in items) == [7, 8]  # um registro por anúncio, sem duplicar
        matched = {i.vinted_id for i in db.scalars(select(Item).join(Match, Match.item_id == Item.id))}
    assert matched == {8}  # o anúncio 7 vale ~74 € em qualquer país: abaixo do mínimo de 150 €
    assert result.analyzed == 2 and result.sent == 1


# ------------------------------------------------------------------ mensagem
def test_message_shows_euro_equivalent_for_other_currencies():
    text = render_message(
        AlertMessage("ps5", [MessageItem("Playstation 5", 2500, "DKK", "https://x/1", price_eur=335.1), MessageItem("PS5", 250, "EUR", "https://x/2", price_eur=250)])
    )
    assert "2,500.00 DKK (≈ 335.10 EUR)" in text
    assert "250.00 EUR\n" in text and "250.00 EUR (≈" not in text  # euro não repete a conversão


def test_notifications_sort_and_convert_by_euro_value(client, signup, link_destination, fake_channel, fake_source, engine_):
    signup(client)
    link_destination("ana@example.com")
    client.post("/alerts", json={**ALERT, "query": "playstation 5", "country": "eu", "maxPrice": None, "notifyOnFirstRun": True})
    client.post("/monitor/start")
    fake_source.put("playstation 5", [raw(3000, "DKK", title="Playstation 5 cara", domain="dk", vid=1)], domain="dk")  # ≈ 401 €
    fake_source.put("playstation 5", [raw(300, "EUR", title="Playstation 5 barata", domain="pt", vid=2)], domain="pt")
    engine_.tick(T(0))
    items = fake_channel.sent[0][1].items
    assert [i.title for i in items] == ["Playstation 5 barata", "Playstation 5 cara"]  # ordenado em euros, não pelo número cru
    assert items[1].price_eur == pytest.approx(401.6, rel=0.02) and items[0].price_eur == 300
    assert Decimal("3000") == Decimal(str(items[1].price))  # o preço original continua sendo mostrado
