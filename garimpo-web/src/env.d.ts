declare namespace NodeJS {
  interface ProcessEnv {
    /** "false" liga o backend real; qualquer outro valor usa o mock. */
    NEXT_PUBLIC_USE_MOCK?: string;
    /** Base das chamadas ao backend (padrão "/api", via proxy do Next). */
    NEXT_PUBLIC_API_URL?: string;
    /** Destino do proxy /api (só servidor). */
    API_PROXY_TARGET?: string;
  }
}
