# Garimpo API

Backend do Garimpo (Python 3.12+ / FastAPI). Faz login, guarda alertas e destinos, **busca na Vinted, filtra,
decide o que é novo e avisa no Telegram**. O front (`../garimpo-web`) conversa com esta API pelo proxy `/api`.

## Rodando

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt     # Linux/Mac: .venv/bin/python
cp .env.example .env
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

- Documentação interativa (só em desenvolvimento): http://localhost:8000/docs
- Sem `DATABASE_URL` de Postgres, usa SQLite (`garimpo.db`) e cria as tabelas sozinho.
- Sem `RESEND_API_KEY`, os e-mails (confirmação, recuperação de senha) **aparecem no log do servidor**.
- O **monitor roda dentro do servidor** (uma thread de fundo) e verifica os usuários com o monitor ligado.
- `VINTED_SOURCE=fake` usa anúncios de mentira (desenvolvimento sem internet); o padrão é `live`.

Ligar o front nesta API: em `garimpo-web/.env` use `NEXT_PUBLIC_USE_MOCK=false` e
`API_PROXY_TARGET=http://localhost:8000`. No Windows/Git Bash, defina essas variáveis com
`MSYS_NO_PATHCONV=1` na linha de comando, senão `/api` vira um caminho do Git.

## Como funciona o aviso

```
a cada ciclo (intervalo do usuário, mín. do plano)
  └─ agrupa os alertas ativos por busca: (país, termo, páginas)  → UMA chamada à Vinted por busca
  └─ guarda os anúncios (catálogo global) e o histórico de preço
  └─ aplica as regras de cada alerta (termo, palavras, preço em EUR, estado)  → "matches"
  └─ o que casou e ainda não foi avisado → traduz o título → manda ao destino do alerta (Telegram)
```

- **Baseline:** na primeira vez que um alerta é processado (ou quando o filtro muda, ou ao reativar), o que já
  existe é registrado **sem avisar** — a menos que o usuário ligue "Notificar no primeiro ciclo".
- **Sem duplicar:** `Match` é único por (alerta, anúncio) e `Notification` por (usuário, anúncio).
- **Falha passageira** (Telegram lento/429): o aviso **não se perde**, é refeito no ciclo seguinte.
  **Falha permanente** (bot removido/bloqueado): o destino vira "Desconectado" no app.
- **429 da Vinted:** o monitor pausa (1 min, dobrando até 15 min) e volta sozinho.
- **Preços:** os limites do alerta são em **EUR**; anúncios em outras moedas (DKK, PLN, SEK...) são
  convertidos (câmbio do BCE via Frankfurter, atualizado a cada 12 h, com tabela de reserva).
- **"Buscar agora"** mostra os resultados na tela e **não** manda ao Telegram (o usuário já está vendo).

## Conectar o Telegram (bot central)

1. No Telegram, fale com **@BotFather** → `/newbot` → guarde o **token**.
2. Em `.env`: `TELEGRAM_BOT_TOKEN=...`, `TELEGRAM_BOT_USERNAME=...` (sem @) e um
   `TELEGRAM_WEBHOOK_SECRET` longo e aleatório (`python -c "import secrets;print(secrets.token_urlsafe(32))"`).
3. `python -m app.cli bot-info` confere o token.
4. Com a API publicada em HTTPS: `python -m app.cli set-webhook --url https://SUA-API/webhooks/telegram`.
   (O Telegram só entrega eventos em HTTPS; em desenvolvimento local use um túnel como ngrok/cloudflared.)
5. No app: Configurações → Telegram → Conectar → siga o passo a passo (privado: botão "Abrir no Telegram";
   grupo/canal: adicione o bot e envie `/link CODIGO`; em grupo, **quem envia precisa ser administrador**).

Comandos no chat vinculado: `/status` e `/stop` (pausa o monitor).

## Banco de dados (Neon Postgres)

1. Crie o projeto na Neon e copie a string de conexão **com pooler** (`...-pooler...`) para o app.
2. Coloque em `.env` (**nunca** no Git nem em conversa): `DATABASE_URL=postgresql://...?sslmode=require`
3. Aplique as tabelas: `.venv/Scripts/alembic upgrade head` — o Alembic troca sozinho para a conexão
   **direta** (sem `-pooler`), como a Neon recomenda para migrações.

Mudou um modelo em `app/models.py`? Gere a migração (um teste falha se faltar):
`.venv/Scripts/alembic revision --autogenerate -m "o que mudou"`.

**Testar em Postgres de verdade** (opcional; a suíte padrão usa SQLite): defina `TEST_DATABASE_URL` com a
mesma string. Os testes usam **só o schema isolado `garimpo_test`** (com trava de segurança) e nunca tocam o
`public`. Leva alguns minutos por causa da rede: `TEST_DATABASE_URL=... python -m pytest -q`.

### Crescimento e custo
- **Retenção** (`app/services/maintenance.py`, roda a cada 6 h dentro do monitor): apaga anúncios não vistos há
  `RETENTION_DAYS` (30; junto vão casamentos, avisos e histórico de preço, em cascata), execuções do monitor com
  +7 dias, tokens de e-mail/sessões vencidos e códigos de vínculo esquecidos.
- **Menos escrita:** anúncios são gravados em lote e `last_seen_at` só é renovado a cada hora.
- **Neon dorme:** sem ninguém com o monitor ligado, o servidor só confere o banco a cada `MONITOR_IDLE_SECONDS`
  (240 s); ligar o monitor acorda o ciclo na hora. Com monitor ligado, o banco fica acordado (consome horas de
  computação: confira o plano da Neon).
- **Região:** hospede a API **na mesma região da Neon** (ex.: Frankfurt/`eu-central-1`). Cada consulta custa ~65 ms
  daqui de Portugal até Frankfurt; na mesma região são ~1–3 ms.

## Administração

```bash
.venv/Scripts/python -m app.cli create-admin --email voce@exemplo.com     # pede a senha
.venv/Scripts/python -m app.cli approve --email usuario@exemplo.com        # modo APPROVAL
.venv/Scripts/python -m app.cli bot-info | set-webhook --url ...
```

## Testes

```bash
.venv/Scripts/python -m pytest -q      # 162 testes
```
Cobrem: login/sessão, alertas, destinos, filtros (inclusive **paridade com o `looks_like_phone` do app antigo**),
extração da página da Vinted (com dados reais salvos), monitor/baseline/duplicação, Telegram, câmbio e migrações.

## Rotas

| Área | Rotas |
|---|---|
| Sessão | `/auth/register`, `/login`, `/logout`, `/refresh`, `/verify-email`, `/resend-verification`, `/forgot`, `/reset` |
| Conta | `GET /me`, `POST /me/password`, `DELETE /me` |
| Alertas | `/alerts` (CRUD), `/alerts/{id}/duplicate`, `/alerts/presets`, `POST /alerts/preview` |
| Busca / resultados | `POST /search/run`, `GET /items` |
| Destinos | `/channels`, `/destinations`, `/destinations/link-code`, `PATCH/DELETE`, `POST .../test`, `POST .../send` |
| Monitor / config | `/monitor/status\|start\|stop`, `/settings` |
| Webhook | `POST /webhooks/telegram` (exige o segredo do webhook) |

Erros seguem o formato do front: `{ "code": "...", "message": "..." }`.

## Limitações conhecidas (leia)

- **A Vinted não tem API pública.** A API JSON antiga (`/api/v2/catalog/items`) hoje responde 404; o app lê a
  **página de busca** do site, que traz os anúncios embutidos no HTML (`app/services/vinted.py`). Isso pode
  quebrar se a Vinted mudar a página — o monitor então registra `FormatChangedError` em vez de gerar lixo,
  mas é preciso ajustar o extrator. Acesso automatizado pode violar os termos da Vinted: **consulte um advogado
  antes de vender isto**.
- **Sem data de postagem nem nome do vendedor** na busca: o app mostra "detectado há X" (momento em que viu) e
  ordena por número do anúncio (crescente no tempo). O filtro "idade máxima" só vale quando a data existir.
- **Custo de "Europa":** um alerta "Europa" faz **uma busca por país (~21)** por ciclo. Medido: ~68 s para o
  "Buscar agora" e ~7 MB de página descompactada por país por ciclo. Sem bloqueio nos testes, mas em produção
  use intervalos maiores, poucos alertas "Europa" por usuário e considere proxy.
- **Filtro por palavras não entende todos os idiomas:** as listas de acessórios cobrem PT/ES/FR/IT/NL/DE.
  Em "Europa" passam acessórios em outros idiomas (ex.: "ovladač", "spel"). Use preço mínimo e palavras próprias.
- **Fila em memória:** o limitador de tentativas e o monitor rodam dentro de 1 processo. Com mais de uma
  réplica, mova o limitador para Redis e garanta que só uma réplica execute o monitor.

## Segurança (resumo)

- Senhas com **argon2id**; tokens de e-mail e de renovação guardados só como hash (SHA-256).
- Sessão em cookies **httpOnly** + SameSite=Lax. Renovação **rotativa**: reaproveitar um token antigo
  derruba a sessão inteira (com tolerância de 10 s para duas abas renovando juntas).
- Cadastro/recuperação respondem igual exista ou não o e-mail; login gasta o mesmo tempo com usuário
  inexistente; 5 falhas em 15 min bloqueiam o login.
- Todo dado é filtrado pelo usuário do token; recurso de outra pessoa responde `404`.
- Vincular **grupo** exige administrador; um chat só pode pertencer a uma conta; o webhook exige segredo.
- Em produção o app **recusa iniciar** com `JWT_SECRET` fraco ou `COOKIE_SECURE=false`.
- No `.env`, **não** escreva comentário na mesma linha do valor (`CHAVE=   # texto`): use linha própria.

## Ao publicar (Railway/Fly/Render)

- `ENVIRONMENT=production`, `JWT_SECRET` longo e aleatório, `COOKIE_SECURE=true`, `WEB_URL` e `CORS_ORIGINS` reais.
- Atrás do proxy do Next, ligue `TRUST_PROXY=true` para o limite de tentativas contar por IP real
  (só se a API **não** estiver exposta direto à internet: `X-Forwarded-For` pode ser falsificado).
- Rode `alembic upgrade head` a cada publicação e registre o webhook do Telegram (`set-webhook`).
- Precisa de processo **sempre ligado** (o monitor): não serve para funções serverless (Vercel).
