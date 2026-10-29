# Garimpo web (Next.js)

Front-end of the listing-alerts app, migrated from TanStack Start (generated with Lovable) to **Next.js 16 (App Router)**. The product name lives in `src/config/brand.ts`.

## Running

```bash
cp .env.example .env     # NEXT_PUBLIC_USE_MOCK=true by default
npm install
npm run dev              # http://localhost:3000
npm run typecheck && npm run lint && npm run build
```

Demo accounts (mock mode): `demo@garimpo.app` and `admin@garimpo.app`, password `demo12345678`.

## Mock vs. real backend

All data access goes through `src/lib/api/`:

- `types.ts`: types and the `Api` contract
- `client.ts`: real implementation (`fetch`, `credentials: "include"`, `ApiError` errors)
- `mock/`: fake data, 300–900 ms latency, occasional failures, state in `localStorage`
- `index.ts`: picks mock or real based on `NEXT_PUBLIC_USE_MOCK`

For the real backend: `NEXT_PUBLIC_USE_MOCK=false`, `NEXT_PUBLIC_API_URL=/api` and `API_PROXY_TARGET=http://localhost:8000`. Next.js forwards `/api/*` to the FastAPI backend (`next.config.ts`), so the browser only talks to one domain: **first-party cookies and no CORS**.

Session handling in the real client: on a 401, a single refresh (`/auth/refresh`) is shared by concurrent requests; auth endpoints never trigger a refresh or a redirect; the redirect to `/login` only happens inside `/app`; and `?redirect=` only accepts internal paths (`src/lib/safe-redirect.ts`).

Linking destinations: `createLinkCode` returns a `destinationId`; the destination starts as `PENDING` and the wizard waits for it to become `LINKED`.

## Structure

```text
src/
  app/                 routes (App Router). Each route: page.tsx (server: metadata) + view.tsx (client)
    layout.tsx         html, font, theme without flash, <Providers>
    providers.tsx      React Query, theme, auth, toasts
    app/layout.tsx     guard for the signed-in area (/app/**)
  config/              brand.ts, plans.ts
  i18n/pt.ts           all visible text (Portuguese)
  lib/                 api/, entitlements.ts, highlights.ts, format.ts, safe-redirect.ts
  hooks/useGarimpo.ts  TanStack Query hooks
  components/          design system (shadcn/ui), app shell, states, UpgradeHint
  features/            auth, alerts, feed, destinations, history
```

Components never call `fetch` or `localStorage` for business data; they always use the hooks in `src/hooks/useGarimpo.ts`.

## Notes

- Pages that read the query string (`/login`, `/reset`, `/verify-email`, the feed) are wrapped in `<Suspense>` and render on the client; the rest are prerendered.
- `react-hooks/set-state-in-effect` and `react-hooks/purity` (new React Compiler rules) are set to *warn* because of legitimate patterns (loading the session on mount, `matchMedia`).
