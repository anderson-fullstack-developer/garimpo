import { httpApi } from "./client";
import { mockApi } from "./mock";
import type { Api } from "./types";

export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

export const api: Api = USE_MOCK ? mockApi : httpApi;

export * from "./types";
