import json
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.vinted import (
    BlockedError,
    FakeSource,
    FormatChangedError,
    RateLimitedError,
    UpstreamError,
    VintedClient,
    _query_params,
    condition_from_text,
    parse_catalog_html,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "catalog_items.json").read_text(encoding="utf-8"))


def build_html(entries) -> str:
    """Monta uma página no mesmo formato da Vinted (dados dentro de self.__next_f.push)."""
    payload = 'a,"catalog":{"x":1},"items":{"items":' + json.dumps(entries) + '},"general":{}'
    half = len(payload) // 2  # a Vinted parte o conteúdo em vários pedaços
    chunks = [payload[:half], payload[half:]]
    scripts = "".join(f"<script>self.__next_f.push([1,{json.dumps(c)}])</script>" for c in chunks)
    return f"<html><body>{scripts}</body></html>"


# ------------------------------------------------------------------ extração
def test_parses_real_listing_data():
    items = parse_catalog_html(build_html(FIXTURE), "pt")
    assert len(items) == len(FIXTURE) == 8
    first = items[0]
    assert (first.vinted_id, first.title) == (10049897008, "iPhone 12")
    assert first.price == Decimal("85.00") and first.total_price == Decimal("89.95")
    assert first.currency == "EUR" and first.condition == "good" and first.condition_text == "Bom"
    assert first.url == "https://www.vinted.pt/items/10049897008-iphone-12"
    assert first.photo_url.startswith("https://images")
    assert first.seller_login == "#127728042"
    assert first.posted_at is None  # a página não informa a data
    assert any("Funda" in i.title for i in items)


def test_domain_is_used_in_urls():
    assert parse_catalog_html(build_html(FIXTURE), "fr")[0].url.startswith("https://www.vinted.fr/items/")


def test_empty_result_page_is_valid():
    assert parse_catalog_html(build_html([]), "pt") == []


def test_skips_broken_entries_but_keeps_good_ones():
    entries = [{"id": 1, "productItem": {"id": 1, "title": "sem preço"}}, "lixo", FIXTURE[0]]
    assert [i.vinted_id for i in parse_catalog_html(build_html(entries), "pt")] == [10049897008]


@pytest.mark.parametrize(
    "html",
    [
        "<html>sem dados</html>",
        '<script>self.__next_f.push([1,"{\\"outra\\":1}"])</script>',
        '<script>self.__next_f.push([1,"\\"items\\":{\\"items\\":[{quebrado"])</script>',
    ],
)
def test_format_change_is_reported_instead_of_returning_garbage(html):
    with pytest.raises(FormatChangedError):
        parse_catalog_html(html, "pt")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Novo com etiquetas", "new_with_tags"),
        ("36 · Novo com etiquetas", "new_with_tags"),
        ("M · Novo sem etiquetas", "new_without_tags"),
        ("Muito bom", "very_good"),
        ("Bom", "good"),
        ("Satisfatório", "satisfactory"),
        ("Très bon état", "very_good"),
        ("Neu mit Etikett", "new_with_tags"),
        ("Muy bueno", "very_good"),
        ("Estado misterioso", None),
        ("", None),
        (None, None),
    ],
)
def test_condition_from_text(text, expected):
    assert condition_from_text(text) == expected


def test_query_params_build_the_web_search_url():
    assert _query_params("iphone 12", 2, None) == [
        ("search_text", "iphone 12"), ("order", "newest_first"), ("page", "2"),
    ]  # fmt: skip
    params = _query_params("x", 1, {"catalog_ids": [10], "brand_ids": [1, 2], "price_to": "90"})
    assert ("catalog[]", "10") in params and ("brand_ids[]", "2") in params and ("price_to", "90") in params


# ------------------------------------------------------------------ cliente
class FakeSession:
    def __init__(self, status=200, text="", error=None):
        self.status, self.text, self.error, self.calls = status, text, error, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params))
        if self.error:
            raise self.error
        return SimpleNamespace(status_code=self.status, text=self.text)


def client_with(session, domain="pt", min_interval=0):
    client = VintedClient(min_interval=min_interval)
    client._sessions[domain] = session
    return client


def test_client_returns_items_and_calls_the_catalog_page():
    session = FakeSession(text=build_html(FIXTURE))
    items = client_with(session).fetch("pt", "iphone 12", page=1)
    assert len(items) == 8
    assert session.calls[0][0] == "https://www.vinted.pt/catalog"


@pytest.mark.parametrize(
    "status,error",
    [(429, RateLimitedError), (403, BlockedError), (503, BlockedError), (500, UpstreamError), (404, UpstreamError)],
)
def test_client_error_mapping(status, error):
    with pytest.raises(error):
        client_with(FakeSession(status=status, text="x")).fetch("pt", "iphone 12")


def test_challenge_page_counts_as_blocked_and_resets_session():
    client = client_with(FakeSession(status=200, text="<html>cf-chl-bypass ...</html>"))
    with pytest.raises(BlockedError):
        client.fetch("pt", "iphone 12")
    assert "pt" not in client._sessions  # recomeça com sessão nova


def test_network_failure_becomes_upstream_error():
    with pytest.raises(UpstreamError):
        client_with(FakeSession(error=TimeoutError("lento"))).fetch("pt", "iphone 12")


def test_client_spaces_out_requests():
    client = client_with(FakeSession(text=build_html([])), min_interval=0.2)
    start = time.monotonic()
    for _ in range(3):
        client.fetch("pt", "iphone 12")
    assert time.monotonic() - start >= 0.38  # 2 esperas de ~0.2 s


def test_fake_source_produces_stable_ids_and_new_items_over_time():
    items = FakeSource().fetch("pt", "iphone 12")
    assert len(items) == 24 and len({i.vinted_id for i in items}) == 24
    assert FakeSource().fetch("pt", "iphone 12", page=2) == []
    assert all(i.domain == "pt" and i.price > 0 for i in items)
