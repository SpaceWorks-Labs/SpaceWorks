import { t } from "@lingui/core/macro";
import { Field } from "../../../components/ui";
import { AUDIT_AREAS, auditAreaLabel } from "./auditAreas";

export type AuditFilters = {
  makerspace: string;
  area: string;
  action: string;
  actor: string;
  targetType: string;
  targetId: string;
  start: string;
  end: string;
};

export const emptyAuditFilters: AuditFilters = {
  makerspace: "", area: "", action: "", actor: "", targetType: "", targetId: "", start: "", end: "",
};

// Query-string form of the filters, exactly as the audit list and the verification POST
// accept them. Dates are local calendar days: `start` inclusive at 00:00 and `end`
// exclusive at the following midnight, matching the server's [start, end) contract.
export function auditFilterParams(filters: AuditFilters): Record<string, string> {
  const params: Record<string, string> = {};
  if (filters.makerspace) params.makerspace = filters.makerspace;
  if (filters.area) params.area = filters.area;
  if (filters.action) params.action = filters.action;
  if (filters.actor) params.actor = filters.actor;
  if (filters.targetType) params.target_type = filters.targetType;
  if (filters.targetId) params.target_id = filters.targetId;
  if (filters.start) {
    const start = new Date(`${filters.start}T00:00:00`);
    params.start = Number.isNaN(start.getTime()) ? filters.start : start.toISOString();
  }
  if (filters.end) {
    const end = new Date(`${filters.end}T00:00:00`);
    end.setDate(end.getDate() + 1);
    params.end = Number.isNaN(end.getTime()) ? filters.end : end.toISOString();
  }
  return params;
}

export function AuditLogFilters({
  filters,
  onChange,
  areas = null,
}: {
  filters: AuditFilters;
  onChange: (next: AuditFilters) => void;
  /** #219e: the areas this reader holds; `null` means the whole space. */
  areas?: readonly string[] | null;
}) {
  const areaOptions = areas ?? AUDIT_AREAS;
  const set = (key: keyof AuditFilters) => (event: { target: { value: string } }) =>
    onChange({ ...filters, [key]: event.target.value });
  return (
    <div className="grid gap-2">
      <Field label={t`Makerspace ID`}><input className="desk-input" inputMode="numeric" value={filters.makerspace} onChange={set("makerspace")} /></Field>
      {areaOptions.length > 1 ? <Field label={t`Area`}><select className="desk-input" value={filters.area} onChange={set("area")}>
        <option value="">{areas ? t`All my areas` : t`All areas`}</option>
        {areaOptions.map(area => <option key={area} value={area}>{auditAreaLabel(area)}</option>)}
      </select></Field> : null}
      <Field label={t`Action`}><input className="desk-input" placeholder={t`e.g. request.issued`} value={filters.action} onChange={set("action")} /></Field>
      <Field label={t`Actor ID`}><input className="desk-input" inputMode="numeric" value={filters.actor} onChange={set("actor")} /></Field>
      <Field label={t`Target type`}><input className="desk-input" placeholder={t`e.g. inventory.inventoryproduct`} value={filters.targetType} onChange={set("targetType")} /></Field>
      <Field label={t`Target ID`}><input className="desk-input" value={filters.targetId} onChange={set("targetId")} /></Field>
      <Field label={t`From`}><input className="desk-input" type="date" value={filters.start} onChange={set("start")} /></Field>
      <Field label={t`To`}><input className="desk-input" type="date" value={filters.end} onChange={set("end")} /></Field>
    </div>
  );
}
