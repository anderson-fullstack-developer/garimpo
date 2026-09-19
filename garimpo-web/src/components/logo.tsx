import Image from "next/image";

import { APP_NAME } from "@/config/brand";
import { cn } from "@/lib/utils";

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <Image
        src="/logo.png"
        alt=""
        width={32}
        height={32}
        unoptimized
        className="size-8 rounded-lg"
      />
      {compact ? null : <span className="text-base">{APP_NAME}</span>}
    </span>
  );
}
