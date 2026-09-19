import { useState } from "react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDestinations } from "@/hooks/useGarimpo";
import { api } from "@/lib/api";
import { errorMessage } from "@/components/states";
import { pt } from "@/i18n/pt";
import type { Item } from "@/lib/api/types";

export function SendToDestinationDialog({
  item,
  onOpenChange,
}: {
  item: Item | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: destinations } = useDestinations();
  const linked = (destinations ?? []).filter((d) => d.status === "LINKED");
  const [selected, setSelected] = useState<string>("");
  const [sending, setSending] = useState(false);

  const destinationId = selected || linked.find((d) => d.isDefault)?.id || linked[0]?.id || "";

  return (
    <Dialog open={Boolean(item)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{pt.feed.sendNow}</DialogTitle>
          <DialogDescription>{item?.title}</DialogDescription>
        </DialogHeader>

        {linked.length ? (
          <div className="space-y-2">
            <Label htmlFor="destination">{pt.alerts.destination}</Label>
            <Select value={destinationId} onValueChange={setSelected}>
              <SelectTrigger id="destination">
                <SelectValue placeholder={pt.alerts.destination} />
              </SelectTrigger>
              <SelectContent>
                {linked.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.title ?? d.channel}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{pt.alerts.noDestination}</p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {pt.common.cancel}
          </Button>
          <Button
            disabled={!destinationId || sending}
            onClick={async () => {
              if (!item) return;
              setSending(true);
              try {
                await api.destinations.send(destinationId, [item.id]);
                toast.success(pt.feed.sent);
                onOpenChange(false);
              } catch (error) {
                toast.error(errorMessage(error));
              } finally {
                setSending(false);
              }
            }}
          >
            {sending ? pt.common.loading : pt.feed.sendNow}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
