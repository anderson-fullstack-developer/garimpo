import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.filters import (
    Rules,
    dedupe,
    evaluate,
    excluded_word,
    query_matches,
)
from app.services.presets import PHONES


def item(title="iPhone 12 64GB", price=80, total=None, condition=None, posted_at=None, seller="v1"):
    return SimpleNamespace(
        title=title,
        price=Decimal(str(price)),
        total_price=None if total is None else Decimal(str(total)),
        condition=condition,
        posted_at=posted_at,
        seller_login=seller,
    )


# ------------------------------------------------------------------ termo de busca
@pytest.mark.parametrize(
    "title,query,expected",
    [
        ("iPhone 12 64GB", "iphone 12", True),
        ("IPHONE12 azul", "iphone 12", True),  # sem espaço, caixa alta
        ("iPhone 12mini", "iphone 12", True),  # "12mini" ainda é iPhone 12
        ("iPhone 12-Pro", "iphone 12", True),
        ("iPhone 120", "iphone 12", False),  # o número não pode continuar
        ("iPhone 13", "iphone 12", False),
        ("Apple iphone 11 Pro Max", "iphone 11", True),
        ("Sapatilhas Nike Air Max 90", "nike air max", True),
        ("Consola PS5 Slim", "ps5", True),
        ("PS5s", "ps5", True),
        ("Caixa de ferramentas", "caixa", True),
        ("Caixas", "caixa", True),  # plural
        ("Caixaria", "caixa", False),  # prefixo de outra palavra
        ("iPhone-12 azul", "iphone 12", True),  # hífen, sublinhado e ponto valem como espaço
        ("iphone_12 azul", "iphone 12", True),
        ("iPhone 12", "iphone-12", True),  # e também na busca digitada
        ("iPhone12", "iphone 12", True),
        ("12 iPhone", "iphone 12", False),  # frase: ordem importa
    ],
)
def test_phrase_matching(title, query, expected):
    assert query_matches(title, query) is expected


def test_all_words_any_order_and_no_partial_words():
    assert query_matches("Air Max 90 Nike branco", "nike air max", "ALL_WORDS")
    assert not query_matches("Nike Air 90", "nike air max", "ALL_WORDS")
    assert not query_matches("Air Max 90 Nike", "nike air max", "PHRASE")  # frase exige a ordem


def test_accents_are_ignored():
    assert query_matches("Máquina fotográfica Canon", "maquina fotografica")
    assert excluded_word("Película de vidro", ["pelicula"]) == "pelicula"


# ------------------------------------------------------------------ palavras a excluir
def test_excluded_words_do_not_fire_inside_other_words():
    assert excluded_word("iPhone 12 Capacidade 128GB", ["capa"]) is None
    assert excluded_word("Capa para iPhone 12", ["capa"]) == "capa"
    assert excluded_word("Capas iPhone 12", ["capa"]) == "capa"  # plural
    assert excluded_word("Telefoonhoesje iPhone 12", ["hoesje"]) == "hoesje"  # sufixo colado
    assert excluded_word("iPhone 12", []) is None


def test_reasons_use_the_codes_the_front_understands():
    rules = Rules(query="iphone 12", exclude_words=["capa"], required_words=["64gb"], min_price=50, max_price=90)
    assert evaluate(rules, item("iPhone 12 64GB", 80)) == []
    assert evaluate(rules, item("Capa iPhone 12 64GB", 80)) == ["excluded_by_word:capa"]
    assert evaluate(rules, item("iPhone 12 128GB", 80)) == ["missing_required_word:64gb"]
    assert evaluate(rules, item("iPhone 12 64GB", 20)) == ["below_min_price"]
    assert evaluate(rules, item("iPhone 12 64GB", 200)) == ["above_max_price"]
    assert evaluate(rules, item("Samsung S21", 80)) == ["query_not_matched", "missing_required_word:64gb"]


def test_presets_add_words():
    rules = Rules(query="ps5", exclude_presets=["CONSOLES_GAMES"])
    assert evaluate(rules, item("Consola PS5 completa", 300)) == []
    assert evaluate(rules, item("Comando PS5 DualSense", 40)) == ["excluded_by_word:comando"]
    assert evaluate(Rules(query="ps5"), item("Comando PS5", 40)) == []  # sem preset, nada é excluído


# ------------------------------------------------------------------ preço / estado / idade
def test_price_uses_total_with_buyer_protection():
    rules = Rules(query="iphone 12", max_price=90)
    assert evaluate(rules, item(price=85, total=89.95)) == []
    assert evaluate(rules, item(price=85, total=95.0)) == ["above_max_price"]


def test_condition_filter_and_unknown_condition():
    rules = Rules(query="iphone 12", status_filter=["very_good", "good"])
    assert evaluate(rules, item(condition="very_good")) == []
    assert evaluate(rules, item(condition="satisfactory")) == ["condition_not_allowed"]
    assert evaluate(rules, item(condition=None)) == []  # estado desconhecido não elimina


def test_age_filter_only_when_posted_at_is_known():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    rules = Rules(query="iphone 12", max_age_minutes=60)
    assert evaluate(rules, item(posted_at=now - timedelta(minutes=30)), now) == []
    assert evaluate(rules, item(posted_at=now - timedelta(minutes=90)), now) == ["too_old"]
    assert evaluate(rules, item(posted_at=None), now) == []


def test_dedupe_keeps_first_of_same_seller_title_price():
    a, b, c = item("iPhone 12", 80, seller="x"), item("iphone 12 ", 80, seller="x"), item("iPhone 12", 80, seller="y")
    assert dedupe([a, b, c]) == [a, c]


# ------------------------------------------------------------------ paridade com o app antigo
LEGACY = Path(__file__).resolve().parents[2] / "find_iphone11.py"

TITLES = [
    "iPhone 11 64GB preto", "iPhone 11 Pro Max 256GB", "IPHONE11 azul", "Apple iPhone 11 128 Go très bon état",
    "Capa iPhone 11 transparente", "Capas iPhone 11 Pro", "Coque iPhone 11 silicone", "Hoesje iPhone 11",
    "Telefoonhoesje iPhone 11", "Funda iPhone 11 Pro Max", "Película de vidro iPhone 11", "Vidro temperado iPhone 11",
    "Carregador rápido iPhone 11", "Cabo lightning para iPhone 11", "Chargeur iPhone 11 20W", "Cargador iPhone 11",
    "iPhone 11 ecrã partido", "iPhone 11 écran cassé à remplacer", "iPhone 11 para peças", "iPhone 11 avariado",
    "iPhone 11 defeito na bateria", "Caixa vazia iPhone 11", "Boîte vide iPhone 11", "iPhone 11 caja vacía",
    "Suporte carro iPhone 11", "Airpods para iPhone 11", "Auriculares iPhone 11", "Cuffie iPhone 11",
    "iPhone 11 Capacidade 128GB", "iPhone 11 com capacidade de 64GB", "Samsung Galaxy S21", "iPhone 12 128GB",
    "iPhone 120", "iPhone 11 skin adesiva", "iPhone 11 wallet case", "Scatola iPhone 11", "iPhone 11 reparar",
    "iPhone 11 riparazione display", "Adaptador iPhone 11", "Adaptateur iPhone 11", "iPhone 11 cristal templado",
    "iPhone 11 - excelente estado", "iPhone 11 64 GB desbloqueado", "iPhone 11 hs", "iPhone 11 hs code",
    "Apple iPhone 11 verre trempé", "iPhone 11 case", "Cover iPhone 11", "iPhone 11 bumper", "iPhone 11 pouch",
    "iPhone 12 Pro Max", "iPhone 12 mini azul", "Capa iPhone 12", "iPhone 12 Capacidade 256", "IPHONE12 verde",
    "iPhone 12 tela quebrada", "iPhone 12 protetor de tela", "Peças iPhone 12", "iPhone 12 vazio",
]  # fmt: skip


def _load_legacy():
    stubs = {
        "telegram_notify": types.SimpleNamespace(format_items_for_telegram=None, send_telegram_message=None),
        "vinted": types.SimpleNamespace(Vinted=None),
    }
    for name, mod in stubs.items():
        module = types.ModuleType(name)
        module.__dict__.update(vars(mod))
        sys.modules.setdefault(name, module)
    spec = importlib.util.spec_from_file_location("legacy_find_iphone11", LEGACY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not LEGACY.exists(), reason="app antigo não está na pasta do projeto")
@pytest.mark.parametrize("query", ["iphone 11", "iphone 12"])
def test_phones_preset_matches_legacy_looks_like_phone(query):
    legacy = _load_legacy()
    model_regex = legacy.build_model_regex(query)
    mismatches = []
    for title in TITLES:
        old = legacy.looks_like_phone(title, model_regex)
        new = query_matches(title, query) and excluded_word(title, PHONES) is None
        if old != new:
            mismatches.append((title, old, new))
    assert not mismatches, f"divergências do app antigo: {mismatches}"
    # o teste só vale se o corpus tiver os dois tipos de resultado
    assert sum(legacy.looks_like_phone(t, model_regex) for t in TITLES) >= 3


# ------------------------------------------------------------------ palavras e preços (casos de borda)
@pytest.mark.parametrize(
    "title,words,excluded",
    [
        ("iPhone 12 com capa", ["capa"], True),
        ("iPhone 12 + capas", ["capa"], True),
        ("iPhone 12 capacidade 128", ["capa"], False),  # não é "capa"
        ("iPhone 12 Película", ["pelicula"], True),  # acento
        ("iPhone 12 ecra partido", ["ecrã partido"], True),  # expressão de duas palavras
        ("iPhone 12 5G+", ["5g+"], True),  # símbolos não quebram a expressão
        ("iPhone 12", ["", "   "], False),  # vazios são ignorados
        ("Telefoonhoesje iPhone 12", ["hoesje"], True),  # palavra colada (holandês)
    ],
)
def test_excluded_words_edge_cases(title, words, excluded):
    assert (excluded_word(title, words) is not None) is excluded


@pytest.mark.parametrize(
    "price,total,currency,lo,hi,passes",
    [
        (250, None, "EUR", 100, 400, True),
        (100, None, "EUR", 100, 400, True),  # limites são inclusivos
        (400, None, "EUR", 100, 400, True),
        (99.99, None, "EUR", 100, 400, False),
        (400.01, None, "EUR", 100, 400, False),
        (98, 102.9, "EUR", 0, 100, False),  # vale o total com proteção do comprador
        (9999, None, "EUR", 0, None, True),  # sem máximo
        (287, None, "DKK", 150, 400, False),  # 287 kr ≈ 38 €
        (900, None, "PLN", 150, 400, True),  # 900 zł ≈ 206 €
    ],
)
def test_price_edge_cases(price, total, currency, lo, hi, passes):
    it = SimpleNamespace(**{**vars(item(price=price, total=total)), "currency": currency})
    assert (evaluate(Rules(query="iphone 12", min_price=lo, max_price=hi), it) == []) is passes


def test_all_words_also_matches_glued_words_and_stays_strict_otherwise():
    assert query_matches("Lego StarWars Duell on Geonosis", "lego star wars", "ALL_WORDS")  # coladas
    assert query_matches("Star Wars set Lego", "lego star wars", "ALL_WORDS")  # qualquer ordem
    assert not query_matches("Lego Star Trek", "lego star wars", "ALL_WORDS")
    assert not query_matches("Canone inverso", "canon", "PHRASE")  # outra palavra
    assert not query_matches("Tee shirt Nike noir coton air max 90", "nike air max 90", "PHRASE")  # frase não é contígua


@pytest.mark.parametrize("query", ["c++", "(", "[abc", ".*", "a|b", "\d+", "iphone (12)", "50% off?", "$$$", "日本語 カメラ", "😀 iphone", "x" * 100])
def test_odd_queries_never_break_the_engine(query):
    for match in ("PHRASE", "ALL_WORDS"):
        rules = Rules(query=query, match_type=match, exclude_words=[query, "(", "[x"], required_words=["("], min_price=0, max_price=10)
        assert isinstance(evaluate(rules, item(title=f"algo {query} raro", price=5)), list)  # sem exceção
