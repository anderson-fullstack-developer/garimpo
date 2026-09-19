import { pt } from "@/i18n/pt";
import type { Plan } from "@/lib/api/types";

export interface PlanConfig {
  id: Plan;
  name: string;
  monthly: number;
  yearly: number;
  recommended: boolean;
  description: string;
}

export const PLANS: PlanConfig[] = [
  {
    id: "FREE",
    get name() {
      return pt.misc.planFree;
    },
    monthly: 0,
    yearly: 0,
    recommended: false,
    get description() {
      return pt.misc.planFreeDesc;
    },
  },
  {
    id: "PRO",
    name: "Pro",
    monthly: 19,
    yearly: 190,
    recommended: true,
    get description() {
      return pt.misc.planProDesc;
    },
  },
  {
    id: "ELITE",
    name: "Elite",
    monthly: 49,
    yearly: 490,
    recommended: false,
    get description() {
      return pt.misc.planEliteDesc;
    },
  },
];

export const CURRENCY = "EUR";
