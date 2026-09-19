"""Comandos de administração:

    python -m app.cli create-admin --email voce@exemplo.com
    python -m app.cli approve --email usuario@exemplo.com
    python -m app.cli bot-info                       # confere o token do bot
    python -m app.cli set-webhook --url https://SUA-API/webhooks/telegram
    python -m app.cli set-profile                    # menu de comandos e descrição do bot (em inglês)
    python -m app.cli poll [--once]                  # desenvolvimento: lê o bot sem precisar de HTTPS
"""

import argparse
import getpass
import sys
from datetime import timedelta

from sqlalchemy import select

from app import models  # noqa: F401
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import User, UserSettings, utcnow
from app.security import hash_password, hash_token, is_weak_password, new_token


def _ensure_schema() -> None:
    if get_settings().is_sqlite:
        Base.metadata.create_all(engine)


def create_admin(email: str, password: str | None) -> None:
    password = password or getpass.getpass("Senha do administrador (mín. 10 caracteres): ")
    if len(password) < 10 or is_weak_password(password):
        sys.exit("Senha fraca ou curta demais (mínimo 10 caracteres).")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user:
            user.role, user.status = "ADMIN", "ACTIVE"
            user.email_verified_at = user.email_verified_at or utcnow()
            user.password_hash = hash_password(password)
        else:
            user = User(
                email=email.lower(),
                password_hash=hash_password(password),
                role="ADMIN",
                plan="ELITE",
                status="ACTIVE",
                email_verified_at=utcnow(),
            )
            user.settings = UserSettings()
            db.add(user)
        db.commit()
    print(f"Administrador pronto: {email}")


def approve(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if not user:
            sys.exit("Usuário não encontrado.")
        user.status = "ACTIVE"
        db.commit()
    print(f"Conta aprovada: {email}")


def bot_info() -> None:
    from app.services.channels import ChannelError
    from app.services.telegram import TelegramClient

    try:
        me = TelegramClient().get_me()
    except ChannelError as exc:
        sys.exit(f"Não consegui falar com o Telegram: {exc}")
    print(f"Bot OK: @{me.get('username')} (nome: {me.get('first_name')})")
    print(f"Coloque TELEGRAM_BOT_USERNAME={me.get('username')} no .env.")


def set_webhook(url: str) -> None:
    from app.services.channels import ChannelError
    from app.services.telegram import TelegramClient

    secret = get_settings().telegram_webhook_secret
    if not secret:
        sys.exit("Defina TELEGRAM_WEBHOOK_SECRET no .env (um texto longo e aleatório) antes.")
    if not url.startswith("https://"):
        sys.exit("O Telegram só aceita webhook em HTTPS (use o endereço público da API).")
    try:
        TelegramClient().set_webhook(url, secret)
    except ChannelError as exc:
        sys.exit(f"O Telegram recusou: {exc}")
    print(f"Webhook registrado: {url}")


BOT_COMMANDS = [
    ("start", "Connect this chat to your Garimpo account"),
    ("status", "Show whether your monitor is on"),
    ("stop", "Pause your monitor"),
]
BOT_DESCRIPTION = (
    "Garimpo sends you instant alerts when new second-hand listings that match your searches appear. "
    "Create your account in the Garimpo app, then tap Start here to connect Telegram."
)
BOT_SHORT_DESCRIPTION = "Instant alerts for new second-hand listings that match your searches."


def set_profile() -> None:
    from app.services.channels import ChannelError
    from app.services.telegram import TelegramClient

    try:
        TelegramClient().set_profile(BOT_COMMANDS, BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION)
    except ChannelError as exc:
        sys.exit(f"O Telegram recusou: {exc}")
    print("Perfil do bot atualizado (comandos e descrição em inglês).")


def poll(once: bool) -> None:
    """Sem webhook (desenvolvimento local): busca as mensagens do bot e as processa como o webhook faria."""
    import time

    from app.services.channels import ChannelError
    from app.services.telegram import TelegramClient
    from app.services.telegram_webhook import handle_update

    client = TelegramClient()
    offset: int | None = None
    print("Lendo mensagens do bot" + (" (uma vez)..." if once else " (Ctrl+C para parar)..."))
    while True:
        try:
            updates = client.get_updates(offset, wait=0 if once else 25)
        except ChannelError as exc:
            if once:
                sys.exit(f"Não consegui ler o bot: {exc} (se houver um webhook registrado, ele impede a leitura direta)")
            print(f"Erro ao ler o bot: {exc}; tentando de novo em 5 s")
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            with SessionLocal() as db:
                try:
                    print(f"  update {update['update_id']}: {handle_update(db, update, client)}")
                except Exception as exc:  # uma mensagem estranha não derruba a leitura
                    db.rollback()
                    print(f"  update {update['update_id']}: erro {type(exc).__name__}")
        if once:
            if offset is not None:
                client.get_updates(offset)  # confirma: o Telegram descarta o que já foi lido
            print(f"{len(updates)} mensagem(ns) processada(s).")
            return


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_admin = sub.add_parser("create-admin")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--password", help="(evite: fica no histórico do terminal)")

    p_approve = sub.add_parser("approve")
    p_approve.add_argument("--email", required=True)

    sub.add_parser("bot-info")
    sub.add_parser("set-profile")
    p_poll = sub.add_parser("poll")
    p_poll.add_argument("--once", action="store_true")
    p_hook = sub.add_parser("set-webhook")
    p_hook.add_argument("--url", required=True)

    args = parser.parse_args()
    _ensure_schema()
    if args.command == "bot-info":
        bot_info()
    elif args.command == "set-profile":
        set_profile()
    elif args.command == "poll":
        poll(args.once)
    elif args.command == "set-webhook":
        set_webhook(args.url)
    elif args.command == "create-admin":
        create_admin(args.email, args.password)
    else:
        approve(args.email)


if __name__ == "__main__":
    main()
