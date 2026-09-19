import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import eslintPluginPrettier from "eslint-plugin-prettier/recommended";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  eslintPluginPrettier,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
      // Regras novas do React Compiler: padrões comuns (buscar sessão ao montar, ler
      // localStorage/matchMedia, código gerado do shadcn) disparam falsos positivos.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/purity": "warn",
      // Fotos vêm de hosts arbitrários do marketplace; next/image exigiria allowlist de domínios.
      "@next/next/no-img-element": "off",
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
