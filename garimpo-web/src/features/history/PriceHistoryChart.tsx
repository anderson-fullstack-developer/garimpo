import { pt } from "@/i18n/pt";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMoney, formatDateTime } from "@/lib/format";
import type { PricePoint } from "@/lib/api/types";

export function PriceHistoryChart({
  points,
  currency = "EUR",
  perfectMin,
  perfectMax,
}: {
  points: PricePoint[];
  currency?: string;
  perfectMin?: number | null;
  perfectMax?: number | null;
}) {
  const data = points.map((p) => ({
    at: p.at,
    price: p.price,
    label: formatDateTime(p.at),
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
          <XAxis
            dataKey="at"
            tickFormatter={(v: string) => formatDateTime(v).slice(0, 5)}
            stroke="var(--color-muted-foreground)"
            fontSize={11}
          />
          <YAxis
            stroke="var(--color-muted-foreground)"
            fontSize={11}
            width={54}
            tickFormatter={(v: number) => formatMoney(v, currency)}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-popover)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-lg)",
              color: "var(--color-popover-foreground)",
              fontSize: 12,
            }}
            labelFormatter={(v: string) => formatDateTime(v)}
            formatter={(value: number) => [formatMoney(value, currency), pt.misc.price]}
          />
          {perfectMin != null ? (
            <ReferenceLine y={perfectMin} stroke="var(--color-perfect)" strokeDasharray="4 4" />
          ) : null}
          {perfectMax != null ? (
            <ReferenceLine y={perfectMax} stroke="var(--color-perfect)" strokeDasharray="4 4" />
          ) : null}
          <Line
            type="monotone"
            dataKey="price"
            stroke="var(--color-primary)"
            strokeWidth={2}
            dot={{ r: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
