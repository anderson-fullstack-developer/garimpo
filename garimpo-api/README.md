# Garimpo API

Garimpo's backend (Python 3.12+ / FastAPI). It handles sign-in, stores alerts and destinations, **searches Vinted, filters the listings, decides what is new and notifies Telegram**. The front-end (`../garimpo-web`) talks to this API through the `/api` proxy.

## Running

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Linux/Mac: .venv/bin/python
cp .env.example .env
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

- Interactive docs (development only): http://localhost:8000/docs
- Without a Postgres `DATABASE_URL`, it uses SQLite (`garimpo.db`) and creates the tables itself.
- Without `RESEND_API_KEY`, emails (verification, password reset) **are printed to the server log**.
- The **monitor runs inside the server** (a background thread) and checks the users who have it switched on.
- `VINTED_SOURCE=fake` uses fake listings (offline development); the default is `live`.

To point the front-end at this API, set `NEXT_PUBLIC_USE_MOCK=false` and `API_PROXY_TARGET=http://localhost:8000` in `garimpo-web/.env`. On Windows with Git Bash, set these variables with `MSYS_NO_PATHCONV=1` on the command line, otherwise `/api` is turned into a Git path.

## How notifications work

```text
every cycle (user's interval, at least the plan minimum)
  └─ group active alerts by search: (country, term, pages)  → ONE Vinted request per search
  └─ store the listings (global catalogue) and the price history
  └─ apply each alert's rules (term, words, price in EUR, condition)  → "matches"
  └─ matches not yet notified → translate the title → send to the alert's destination (Telegram)
```

- **Baseline:** the first time an alert is processed (or when its filter changes, or when it is re-enabled), existing listings are recorded **without notifying**, unless the user turns on "Notify on first run".
- **No duplicates:** a `Match` is unique per (alert, listing) and a `Notification` per (user, listing).
- **Temporary failure** (slow Telegram or 429): the notification **is not lost**; it is retried in the next cycle. **Permanent failure** (bot removed or blocked): the destination becomes "Disconnected" in the app.
- **Vinted 429:** the monitor pauses (1 minute, doubling up to 15 minutes) and resumes on its own.
- **Prices:** alert limits are in **EUR**; listings in other currencies (DKK, PLN, SEK…) are converted using ECB rates from Frankfurter, refreshed every 12 hours, with a fallback table.
- **"Search now"** shows the results on screen and does **not** send them to Telegram, since the user is already looking at them.

## Connecting Telegram (central bot)

1. In Telegram, talk to **@BotFather** → `/newbot` → keep the **token**.
2. In `.env`: `TELEGRAM_BOT_TOKEN=...`, `TELEGRAM_BOT_USERNAME=...` (without @) and a long random `TELEGRAM_WEBHOOK_SECRET` (`python -c "import secrets;print(secrets.token_urlsafe(32))"`).
3. `python -m app.cli bot-info` checks the token.
4. With the API published over HTTPS: `python -m app.cli set-webhook --url https://YOUR-API/webhooks/telegram`. Telegram only delivers events over HTTPS; for local development use a tunnel such as ngrok or cloudflared.
5. In the app: Settings → Telegram → Connect, then follow the steps. For a private chat, use the "Open in Telegram" button. For a group or channel, add the bot and send `/link CODE`; in a group, **the sender must be an administrator**.

Commands in a linked chat: `/status` and `/stop` (pauses the monitor).

## Database (Neon Postgres)

1. Create the project on Neon and copy the **pooled** connection string (`...-pooler...`) for the app.
2. Put it in `.env` (**never** in Git): `DATABASE_URL=postgresql://...?sslmode=require`
3. Create the tables: `.venv/Scripts/alembic upgrade head`. Alembic switches to the **direct** connection (without `-pooler`) on its own, as Neon recommends for migrations.

Changed a model in `app/models.py`? Generate the migration (a test fails if it is missing): `.venv/Scripts/alembic revision --autogenerate -m "what changed"`.

**Testing against real Postgres** (optional; the default suite uses SQLite): set `TEST_DATABASE_URL` to the same connection string. The tests use **only the isolated `garimpo_test` schema** (with a safety check) and never touch `public`. Because of network latency it takes a few minutes: `TEST_DATABASE_URL=... python -m pytest -q`.

### Growth and cost

- **Retention** (`app/services/maintenance.py`, runs every 6 hours inside the monitor): deletes listings not seen for `RETENTION_DAYS` (30, cascading to matches, notifications and price history), monitor runs older than 7 days, expired email tokens and sessions, and unused link codes.
- **Fewer writes:** listings are written in batches and `last_seen_at` is only refreshed once an hour.
- **Neon sleeps:** when nobody has the monitor on, the server only checks the database every `MONITOR_IDLE_SECONDS` (240 s); switching the monitor on wakes the cycle immediately. While a monitor is on, the database stays awake and uses compute hours, so check your Neon plan.
- **Region:** host the API **in the same region as Neon** (e.g. Frankfurt / `eu-central-1`). Each query costs about 65 ms from Portugal to Frankfurt, and about 1–3 ms within the same region.

## Administration

```bash
.venv/Scripts/python -m app.cli create-admin --email you@example.com     # asks for the password
.venv/Scripts/python -m app.cli approve --email user@example.com         # APPROVAL registration mode
.venv/Scripts/python -m app.cli bot-info | set-webhook --url ...
```

## Tests

```bash
.venv/Scripts/python -m pytest -q      # 200 tests (259 cases with parametrisation)
```

They cover sign-in and sessions, alerts, destinations, filters (including **parity with the old app's `looks_like_phone`**), parsing of the Vinted search page (with saved real data), the monitor, baseline and deduplication, Telegram, billing, currency conversion and migrations.

## Routes

| Area | Routes |
|---|---|
| Session | `/auth/register`, `/login`, `/logout`, `/refresh`, `/verify-email`, `/resend-verification`, `/forgot`, `/reset` |
| Account | `GET /me`, `POST /me/password`, `DELETE /me` |
| Alerts | `/alerts` (CRUD), `/alerts/{id}/duplicate`, `/alerts/presets`, `POST /alerts/preview` |
| Search / results | `POST /search/run`, `GET /items` |
| Destinations | `/channels`, `/destinations`, `/destinations/link-code`, `PATCH/DELETE`, `POST .../test`, `POST .../send` |
| Monitor / settings | `/monitor/status\|start\|stop`, `/settings` |
| Webhook | `POST /webhooks/telegram` (requires the webhook secret) |

Errors follow the front-end format: `{ "code": "...", "message": "..." }`.

## Known limitations

- **Vinted has no public API.** The old JSON API (`/api/v2/catalog/items`) now returns 404, so the app reads the site's **search page**, which embeds the listings in the HTML (`app/services/vinted.py`). This can break if Vinted changes the page. The monitor then logs a `FormatChangedError` instead of producing bad data, but the extractor has to be updated. Automated access may go against Vinted's terms of use.
- **No posting date or seller name** in search results: the app shows "detected X ago" (when it first saw the listing) and sorts by listing ID, which grows over time. The "maximum age" filter only applies when a date is available.
- **Cost of "Europe":** a "Europe" alert makes **one search per country (~21)** per cycle. Measured: about 68 s for "Search now" and about 7 MB of uncompressed page per country per cycle. No blocking was seen in testing, but in production use longer intervals, few "Europe" alerts per user, and consider a proxy.
- **The word filter does not understand every language:** the accessory lists cover PT/ES/FR/IT/NL/DE, so in "Europe" accessories in other languages get through (e.g. "ovladač", "spel"). Use a minimum price and your own excluded words.
- **In-memory state:** the rate limiter and the monitor run inside a single process. With more than one replica, move the limiter to Redis and make sure only one replica runs the monitor.

## Security

- Passwords hashed with **Argon2id**; email and refresh tokens stored only as SHA-256 hashes.
- Session in **httpOnly** cookies with SameSite=Lax. **Rotating** refresh tokens: reusing an old token revokes the whole session (with a 10-second grace period for two tabs refreshing at once).
- Sign-up and password recovery respond the same whether or not the email exists; sign-in takes the same time for unknown users; 5 failures in 15 minutes lock sign-in.
- All data is scoped to the token's user; another user's resource returns `404`.
- Linking a **group** requires an administrator; a chat can belong to only one account; the webhook requires a secret.
- In production the app **refuses to start** with a weak `JWT_SECRET` or `COOKIE_SECURE=false`.
- In `.env`, **do not** put a comment on the same line as a value (`KEY=   # text`); use a separate line.

## Deploying (Railway / Fly / Render)

- `ENVIRONMENT=production`, a long random `JWT_SECRET`, `COOKIE_SECURE=true`, and real `WEB_URL` and `CORS_ORIGINS`.
- Behind the Next.js proxy, set `TRUST_PROXY=true` so the rate limiter counts the real client IP. Only do this if the API is **not** exposed directly to the internet, since `X-Forwarded-For` can be spoofed.
- Run `alembic upgrade head` on every deploy and register the Telegram webhook (`set-webhook`).
- It needs an **always-on** process (the monitor), so it does not run on serverless functions such as Vercel.

## Resource usage

An analysis of what the API uses on Railway (CPU, memory, Vinted requests) and what can be reduced is in [docs/RELATORIO_CONSUMO.md](docs/RELATORIO_CONSUMO.md) (in Portuguese).
