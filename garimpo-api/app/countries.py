"""Países aceitos (código = domínio do marketplace). "eu" = todos os países da Europa."""

EUROPE = "eu"

COUNTRY_CODES = (
    "pt", "es", "fr", "it", "de", "nl", "be", "lu", "at", "ie", "pl",
    "cz", "sk", "hu", "ro", "hr", "lt", "fi", "se", "dk", "gr",
)  # fmt: skip

VALID_COUNTRIES = frozenset((*COUNTRY_CODES, EUROPE))

# Idiomas da interface disponíveis (os outros entram um a um; até lá, quem não é PT vê EN).
LANGUAGES = ("pt", "en")
# Moedas que o app sabe converter (mesmas do módulo de câmbio).
CURRENCIES = ("EUR", "PLN", "SEK", "DKK", "CZK", "HUF", "RON", "BGN", "GBP", "CHF", "NOK", "USD")

_CURRENCY_BY_COUNTRY = {"pl": "PLN", "cz": "CZK", "hu": "HUF", "ro": "RON", "se": "SEK", "dk": "DKK"}


def default_language(country: str | None) -> str:
    return "en" if country and country != "pt" else "pt"  # sem país (contas antigas): português


def default_currency(country: str | None) -> str:
    return _CURRENCY_BY_COUNTRY.get(country or "", "EUR")
