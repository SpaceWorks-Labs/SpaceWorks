import { staffRequest } from "../../../lib/api";

/** Shapes of `GET admin/makerspace/{id}/area-overview/{section}` (decision 241), kept local
 * until the generated client catches up. The server scopes and groups; the console only
 * filters by area, collapses groups and words the labels. */
export type AreaSection = "finance" | "tobuy" | "consumables" | "repairs" | "warranties";
export type GroupKind = "area" | "domain" | "machine_type" | "machine" | "category" | "room" | "event";
export type AreaMoney = { currency: string; amount: string };
export type AreaFinance = {
  currency: string; income: string; other_income: string; refunds: string; expenses: string; owed: string;
  money_in: string; payouts?: string; money_out?: string; net?: string;
};
export type AreaItem = {
  id: number; label: string; status: string; source?: string; priority?: string; quantity?: string | number;
  unit?: string; threshold?: string | null; amount?: string | null; currency?: string; expires_on?: string | null;
};
export type AreaGroup = {
  kind: GroupKind | "root"; key: string; label: string; count: number; attention: number;
  money: AreaMoney[]; finance: AreaFinance[]; children: AreaGroup[]; items: AreaItem[];
};
export type AreaOverview = { view: AreaSection; areas: string[]; totals: AreaGroup; groups: AreaGroup[]; truncated: boolean };

export const areaOverviewKeys = {
  section: (makerspaceId: number, section: AreaSection, params: string) => ["area-overview", makerspaceId, section, params] as const,
};

export function fetchAreaOverview(makerspaceId: number, section: AreaSection, params: URLSearchParams) {
  const query = params.toString();
  return staffRequest<AreaOverview>(`/admin/makerspace/${makerspaceId}/area-overview/${section}${query ? `?${query}` : ""}`);
}
