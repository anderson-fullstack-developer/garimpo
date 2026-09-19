"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/components/states";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/features/auth/AuthProvider";
import { LANGUAGE_NAMES } from "@/config/languages";
import { COUNTRIES, CURRENCIES, countryLabel } from "@/config/countries";
import { api } from "@/lib/api";
import { pt } from "@/i18n/pt";

/** País, idioma e moeda são independentes: quem mora fora pode manter o idioma de casa. */
export function RegionSettings() {
  const { user, reload } = useAuth();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);

  const save = async (input: { country?: string; language?: string; currency?: string }) => {
    setSaving(true);
    try {
      await api.me.updatePreferences(input);
      await reload(); // o idioma novo chega pelo usuário e remonta a tela
      await queryClient.invalidateQueries({ queryKey: ["items"] }); // preços na moeda nova
      toast.success(pt.settings.saved);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="surface space-y-4 p-5">
      <p className="text-sm text-muted-foreground">{pt.settings.regionHelp}</p>

      <div className="space-y-2">
        <Label htmlFor="pref-country">{pt.settings.country}</Label>
        <Select
          value={user?.country ?? ""}
          onValueChange={(country) => void save({ country })}
          disabled={saving}
        >
          <SelectTrigger id="pref-country">
            <SelectValue placeholder={pt.auth.countryPlaceholder} />
          </SelectTrigger>
          <SelectContent>
            {COUNTRIES.map((c) => (
              <SelectItem key={c.code} value={c.code}>
                {countryLabel(c.code)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="pref-language">{pt.settings.language}</Label>
        <Select
          value={user?.language ?? "pt"}
          onValueChange={(language) => void save({ language })}
          disabled={saving}
        >
          <SelectTrigger id="pref-language">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(LANGUAGE_NAMES).map(([code, name]) => (
              <SelectItem key={code} value={code}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="pref-currency">{pt.settings.currency}</Label>
        <Select
          value={user?.currency ?? "EUR"}
          onValueChange={(currency) => void save({ currency })}
          disabled={saving}
        >
          <SelectTrigger id="pref-currency">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CURRENCIES.map((code) => (
              <SelectItem key={code} value={code}>
                {code}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
