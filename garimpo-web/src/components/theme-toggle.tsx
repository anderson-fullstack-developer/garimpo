import { Monitor, Moon, Sun } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme-provider";
import { pt } from "@/i18n/pt";

export function ThemeToggle() {
  const { theme, resolved, setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={pt.common.theme}>
          {resolved === "dark" ? (
            <Moon className="size-4" aria-hidden />
          ) : (
            <Sun className="size-4" aria-hidden />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => setTheme("light")} aria-current={theme === "light"}>
          <Sun className="mr-2 size-4" aria-hidden /> {pt.common.themeLight}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("dark")} aria-current={theme === "dark"}>
          <Moon className="mr-2 size-4" aria-hidden /> {pt.common.themeDark}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("system")} aria-current={theme === "system"}>
          <Monitor className="mr-2 size-4" aria-hidden /> {pt.common.themeSystem}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
