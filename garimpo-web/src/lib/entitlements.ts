import type { Plan } from "./api/types";

export interface Entitlements {
  minIntervalMinutes: number;
  maxAlerts: number;
  maxDestinations: number;
  maxPages: number;
  priority: "normal" | "alta" | "máxima";
  domains: number;
  historyDays: number | null;
}

const TABLE: Record<Plan, Entitlements> = {
  FREE: {
    minIntervalMinutes: 1,
    maxAlerts: 1,
    maxDestinations: 1,
    maxPages: 1,
    priority: "normal",
    domains: 1,
    historyDays: 7,
  },
  PRO: {
    minIntervalMinutes: 0.25,
    maxAlerts: 10,
    maxDestinations: 3,
    maxPages: 2,
    priority: "alta",
    domains: 3,
    historyDays: 90,
  },
  ELITE: {
    minIntervalMinutes: 1 / 6,
    maxAlerts: 30,
    maxDestinations: 10,
    maxPages: 3,
    priority: "máxima",
    domains: 10,
    historyDays: null,
  },
};

export function entitlementsFor(plan: Plan): Entitlements {
  return TABLE[plan];
}

export function nextPlan(plan: Plan): Plan | null {
  if (plan === "FREE") return "PRO";
  if (plan === "PRO") return "ELITE";
  return null;
}
