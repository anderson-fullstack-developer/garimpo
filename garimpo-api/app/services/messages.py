"""Textos que o servidor escreve sozinho (Telegram). Sempre em inglês, para todos os usuários."""

DEFAULT = "en"

_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "alert_header": "🔔 {name} — {n} new",
        "new_one": "new",
        "new_many": "new",
        "perfect": "⭐ PERFECT PRICE ⭐",
        "best": "🔥 BEST DEAL 🔥",
        "and_more": "… and {n} more in the app.",
        "cond_new_with_tags": "New with tags",
        "cond_new_without_tags": "New without tags",
        "cond_very_good": "Very good",
        "cond_good": "Good",
        "cond_satisfactory": "Satisfactory",
        "linked": "✅ Connected! Garimpo alerts will arrive here.",
        "invalid_code": "Invalid or expired code. Generate a new one in Settings → Telegram.",
        "kind_mismatch": "This code is for linking a {kind}.",
        "kind_PRIVATE": "private chat",
        "kind_GROUP": "group",
        "kind_CHANNEL": "channel",
        "kind_other": "destination",
        "not_admin": "Only group admins can link. Ask an admin.",
        "already_yours": "This chat is already linked to your account.",
        "already_other": "This chat is already linked to another account.",
        "help": "Hi! To connect this chat, generate a code in Settings → Telegram in the app.",
        "unlinked": "This chat is not linked to any account yet.",
        "stopped": "⏸ Monitor paused. To receive alerts again, turn it on in the app.",
        "status": "Monitor {state}. Active alerts: {n}.",
        "test": "✅ Garimpo test: your alerts will arrive here.",
        "selected": "Selected listings",
        "open_button": "🛒 Open on Vinted",
        "posted_now": "Posted just now",
        "posted_ago": "Posted {n} {u} ago",
        "below_avg": "📉 {pct}% below the usual price for this search",
        "alert_line": "🔔 {name}",
        "on": "on",
        "off": "paused",
    },
}


def normalize_language(language: str | None = None) -> str:
    """Telegram fala inglês com todo mundo (decisão de produto): qualquer idioma vira \"en\"."""
    return "en"


def tr(language: str | None, key: str, **values: object) -> str:
    return _TEXTS[normalize_language(language)][key].format(**values)


RESET_BUTTON = "🔑 Reset password"


def reset_message_html(link: str, minutes: int, code: str = "") -> str:
    """Aviso de redefinição de senha. Sempre em inglês (é o mesmo para todos os usuários).

    Traz o link e também o CÓDIGO: em desenvolvimento (localhost) o Telegram não deixa o link tocável, e
    o código (toque para copiar) vale na página de redefinição.
    """
    import html

    url = html.escape(link, quote=True)
    text = (
        "🔐 <b>Reset your Garimpo password</b>\n\n"
        "We received a request to reset the password of your account.\n"
        f'Tap <a href="{url}"><b>Reset password</b></a> to choose a new one.\n\n'
    )
    if code:
        text += (
            "Link not opening? Open the Garimpo reset page and paste this code "
            "(tap it to copy):\n"
            f"<code>{html.escape(code)}</code>\n\n"
        )
    return (
        text + f"⏱ <b>This link and code are valid for {minutes} minutes</b> and can be used only once.\n\n"
        "<i>Didn't ask for this? Just ignore this message: your password won't change.</i>"
    )


def reset_message_plain(link: str, minutes: int, code: str = "") -> str:
    text = (
        "🔐 Reset your Garimpo password\n\n"
        "We received a request to reset the password of your account.\n"
        f"Open this link to choose a new one:\n{link}\n\n"
    )
    if code:
        text += f"Link not opening? Open the Garimpo reset page and paste this code:\n{code}\n\n"
    return (
        text + f"⏱ This link and code are valid for {minutes} minutes and can be used only once.\n\n"
        "Didn't ask for this? Just ignore this message: your password won't change."
    )
