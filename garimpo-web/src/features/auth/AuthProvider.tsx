import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useLanguage } from "@/i18n/LanguageProvider";
import { isLanguage } from "@/i18n/pt";
import type { User } from "@/lib/api/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();
  const { language, setLanguage } = useLanguage();

  // O idioma salvo na conta manda: vale em qualquer aparelho em que o usuário entrar.
  const preferred = user?.language;
  useEffect(() => {
    if (isLanguage(preferred) && preferred !== language) setLanguage(preferred);
  }, [preferred, language, setLanguage]);

  const reload = useCallback(async () => {
    try {
      setUser(await api.me.get());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const login = useCallback(
    async (email: string, password: string) => {
      const logged = await api.auth.login({ email, password });
      setUser(logged);
      await queryClient.invalidateQueries();
      return logged;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    await api.auth.logout();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo(
    () => ({ user, loading, login, logout, reload }),
    [user, loading, login, logout, reload],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de AuthProvider");
  return ctx;
}
