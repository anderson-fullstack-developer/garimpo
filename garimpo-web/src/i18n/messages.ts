import type { ptDict } from "./dict-pt";

type Widen<T> = { -readonly [K in keyof T]: T[K] extends string ? string : Widen<T[K]> };

/** Formato de todo dicionário de idioma: as chaves do português (a fonte), com textos livres. */
export type Messages = Widen<typeof ptDict>;
