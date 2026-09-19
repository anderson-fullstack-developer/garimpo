# Garimpo — front-end (Next.js)

Front-end do SaaS de alertas de anúncios. Migrado de TanStack Start (gerado pela Lovable)
para **Next.js 16 (App Router)**. O nome do produto está em `src/config/brand.ts`.

## Rodando

```bash
cp .env.example .env     # NEXT_PUBLIC_USE_MOCK=true por padrão
npm install
npm run dev              # http://localhost:3000
npm run typecheck && npm run lint && npm run build
```

Contas de demonstração (modo mock): `demo@garimpo.app` e `admin@garimpo.app`,
senha `demo12345678`.

## Mock x backend real

Toda a comunicação de dados passa por `src/lib/api/`:

- `types.ts` — tipos e o contrato `Api`
- `client.ts` — implementação real (`fetch`, `credentials: "include"`, erros `ApiError`)
- `mock/` — dados fictícios, latência de 300–900 ms, falhas ocasionais, estado em `localStorage`
- `index.ts` — escolhe mock ou real por `NEXT_PUBLIC_USE_MOCK`

Para o backend real: `NEXT_PUBLIC_USE_MOCK=false`, `NEXT_PUBLIC_API_URL=/api` e
`API_PROXY_TARGET=http://localhost:3001`. O Next repassa `/api/*` ao NestJS
(`next.config.ts`), então o navegador fala só com um domínio: **cookies first-party e sem CORS**.

Sessão no cliente real: em 401 a renovação (`/auth/refresh`) é única e compartilhada entre
requisições simultâneas; endpoints de autenticação nunca disparam renovação nem redirect; o
redirect para `/login` só acontece dentro de `/app`; e `?redirect=` aceita apenas caminhos
internos (`src/lib/safe-redirect.ts`).

Vínculo de destinos: `createLinkCode` devolve `destinationId`; o destino nasce `PENDING` e o
assistente espera esse destino virar `LINKED`.

## Estrutura

```
src/
  app/                 rotas (App Router). Cada rota: page.tsx (servidor: metadata) + view.tsx (cliente)
    layout.tsx         html, fonte, tema sem "flash", <Providers>
    providers.tsx      React Query, tema, auth, toasts
    app/layout.tsx     guarda da área logada (/app/**)
  config/              brand.ts, plans.ts
  i18n/pt.ts           todos os textos visíveis (pt-BR)
  lib/                 api/, entitlements.ts, highlights.ts, format.ts, safe-redirect.ts
  hooks/useGarimpo.ts  hooks do TanStack Query
  components/          design system (shadcn), app shell, estados, UpgradeHint
  features/            auth, alerts, feed, destinations, history
```

Componentes nunca chamam `fetch` nem `localStorage` para dados de negócio — sempre os hooks
de `src/hooks/useGarimpo.ts`.

## Observações

- Páginas que leem a query string (`/login`, `/reset`, `/verify-email`, feed) ficam dentro de
  `<Suspense>` e renderizam no cliente; as demais são pré-renderizadas.
- `react-hooks/set-state-in-effect` e `react-hooks/purity` (regras novas do React Compiler)
  estão como *warn* por causa de padrões legítimos (buscar sessão ao montar, `matchMedia`).
