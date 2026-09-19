import { cookies } from "next/headers";

import { DEFAULT_LANGUAGE, LANGUAGE_COOKIE, isLanguage, messagesFor } from "./pt";

/** Textos no idioma do usuário (cookie), para metadados de página gerados no servidor. */
export async function serverMessages() {
  const stored = (await cookies()).get(LANGUAGE_COOKIE)?.value;
  return messagesFor(isLanguage(stored) ? stored : DEFAULT_LANGUAGE);
}
