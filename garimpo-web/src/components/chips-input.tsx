import { X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { pt } from "@/i18n/pt";

interface ChipsInputProps {
  id: string;
  label: string;
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  max?: number;
}

export function ChipsInput({ id, label, value, onChange, placeholder, max = 20 }: ChipsInputProps) {
  const [draft, setDraft] = useState("");

  const add = () => {
    const word = draft.trim();
    if (!word || value.length >= max || value.includes(word)) {
      setDraft("");
      return;
    }
    onChange([...value, word]);
    setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add();
    }
    if (event.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={add}
      />
      <p className="text-xs text-muted-foreground">{pt.alerts.chipsHint}</p>
      {value.length ? (
        <ul className="flex flex-wrap gap-2">
          {value.map((word) => (
            <li key={word}>
              <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-3 py-1 text-xs text-secondary-foreground">
                {word}
                <button
                  type="button"
                  aria-label={`Remover ${word}`}
                  onClick={() => onChange(value.filter((w) => w !== word))}
                  className="rounded-full p-0.5 hover:bg-background"
                >
                  <X className="size-3" aria-hidden />
                </button>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
