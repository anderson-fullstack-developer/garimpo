import { Clock, ExternalLink, ImageOff, Send, Star, Flame } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { pt, t } from "@/i18n/pt";
import { formatMoney, relativeTime } from "@/lib/format";
import type { Highlight } from "@/lib/highlights";
import type { Item } from "@/lib/api/types";

export function HighlightBadge({ highlight }: { highlight: Highlight }) {
  if (highlight === "PERFECT") {
    return (
      <Badge className="gap-1 border-transparent bg-perfect text-perfect-foreground">
        <Star className="size-3" aria-hidden /> {pt.feed.badgePerfect}
      </Badge>
    );
  }
  if (highlight === "BEST_DEAL") {
    return (
      <Badge className="gap-1 border-transparent bg-primary text-primary-foreground">
        <Flame className="size-3" aria-hidden /> {pt.feed.badgeBest}
      </Badge>
    );
  }
  return null;
}

interface ItemActionsProps {
  item: Item;
  onSend: (item: Item) => void;
}

/** Foto do anúncio; se faltar ou falhar ao carregar, mostra um bloco neutro (sem "buraco" no card). */
function ItemPhoto({ src, alt }: { src: string | null; alt: string }) {
  const [failed, setFailed] = useState(false);
  const size = "size-24 shrink-0 rounded-lg sm:size-28";
  if (!src || failed) {
    return (
      <div className={`${size} flex items-center justify-center bg-muted text-muted-foreground`}>
        <ImageOff className="size-6" aria-hidden />
        <span className="sr-only">{pt.misc.noPhoto}</span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`${size} bg-muted object-cover`}
    />
  );
}

export function ItemCard({ item, highlight, onSend }: ItemActionsProps & { highlight: Highlight }) {
  return (
    <article className="surface flex gap-3 overflow-hidden p-3">
      <ItemPhoto src={item.photoUrl} alt={item.title} />
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <HighlightBadge highlight={highlight} />
          <Badge variant="outline">{item.alertName}</Badge>
        </div>
        <h3 className="truncate text-sm font-medium">{item.title}</h3>
        {item.titlePt ? (
          <p className="truncate text-xs text-muted-foreground">{item.titlePt}</p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="text-base font-semibold text-foreground">
            {formatMoney(item.priceUser, item.userCurrency)}
          </span>
          {item.currency !== item.userCurrency ? (
            <span>({formatMoney(item.price, item.currency)})</span>
          ) : null}
          {item.condition ? <span>{pt.condition[item.condition]}</span> : null}
          {item.sellerLogin.startsWith("#") ? null : <span>{item.sellerLogin}</span>}
          <span className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-1.5 py-0.5 font-medium text-foreground">
            <Clock className="size-3.5 text-primary" aria-hidden />
            {item.postedAt
              ? t(pt.feed.postedAgo, { when: relativeTime(item.postedAt) })
              : t(pt.feed.seenAgo, { when: relativeTime(item.firstSeenAt) })}
          </span>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button asChild size="sm" variant="default">
            <a href={item.url} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-1 size-3.5" aria-hidden /> {pt.feed.open}
            </a>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline">
                {pt.misc.actions}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onSelect={() => onSend(item)}>
                <Send className="mr-2 size-4" aria-hidden /> {pt.feed.sendNow}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </article>
  );
}
