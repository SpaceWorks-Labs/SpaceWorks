import { EMPTY_SCOPE, type RecipientKind, type RecipientRule, type RecipientRulesResponse } from "../../../notificationDestinationTypes";

/** The machine-service events in the routing catalogue (`feature`/`event` as the recipient-rule endpoint names them). */
export const MACHINE_EVENTS: { feature: string; event: string; suggestedBy?: "job_finished" | "job_failed" | "low_stock" }[] = [
  // Machine-service job notices (decision 343): staff recipients per type; the member's own notices are untouched.
  ...["submitted", "accepted", "rejected", "started"].map(event => ({ feature: "printing", event })),
  { feature: "printing", event: "completed", suggestedBy: "job_finished" },
  { feature: "printing", event: "failed", suggestedBy: "job_failed" },
  ...["cancelled", "collected", "reprinted", "changes_requested", "resubmitted", "quoted", "quote_approved",
    "quote_declined", "quote_expired", "requeued", "uncollected", "no_show_flagged", "session_auto_stopped"]
    .map(event => ({ feature: "printing", event })),
  { feature: "stock", event: "low_stock", suggestedBy: "low_stock" },
  { feature: "devices", event: "adapter_job_review", suggestedBy: "job_finished" },
  { feature: "devices", event: "adapter_attention", suggestedBy: "job_failed" },
  { feature: "devices", event: "adapter_runout" },
  { feature: "maintenance", event: "due_soon" },
  { feature: "maintenance", event: "overdue" },
  { feature: "maintenance", event: "issue_reported" },
  { feature: "maintenance", event: "incident_reported" },
];

export type RuleBody = { kind: RecipientKind; role_id: number | null; user_id: number | null; scope: RecipientRule["scope"] };
const toBody = (rule: RecipientRule): RuleBody => ({ kind: rule.kind, role_id: rule.role_id, user_id: rule.user_id, scope: rule.scope ?? EMPTY_SCOPE });

/** A rule is "for this type" when its machine-type scope names the type. */
export const forType = (rule: RecipientRule, typeId: number) => (rule.scope?.machine_type_ids ?? []).includes(typeId);

export const eventRules = (data: RecipientRulesResponse, feature: string, event: string) =>
  data.rules.filter(rule => rule.feature === feature && rule.event === event);

/** The events this space can route: only those the endpoint lists for a feature that is installed. */
export const offeredEvents = (data: RecipientRulesResponse) =>
  MACHINE_EVENTS.filter(item => data.features.find(feature => feature.key === item.feature)?.events.includes(item.event));

/** The PUT body replaces the whole caller-owned list for the event, so every other rule is sent back unchanged. */
export function bodyWithAdded(data: RecipientRulesResponse, feature: string, event: string, typeId: number, added: Omit<RuleBody, "scope">) {
  const rules = eventRules(data, feature, event).map(toBody);
  return { feature, event, rules: [...rules, { ...added, scope: { ...EMPTY_SCOPE, machine_type_ids: [typeId] } }] };
}

export function bodyWithout(data: RecipientRulesResponse, feature: string, event: string, removeId: number) {
  return { feature, event, rules: eventRules(data, feature, event).filter(rule => rule.id !== removeId).map(toBody) };
}

export function ruleLabel(rule: RecipientRule, data: RecipientRulesResponse, labels: { role: string; user: string; members: string; requester: string }) {
  if (rule.kind === "role") return data.roles.find(role => role.id === rule.role_id)?.name ?? labels.role;
  if (rule.kind === "user") return data.members.find(member => member.id === rule.user_id)?.username ?? labels.user;
  return rule.kind === "members" ? labels.members : labels.requester;
}
