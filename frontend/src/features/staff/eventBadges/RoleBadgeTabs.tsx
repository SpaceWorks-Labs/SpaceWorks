// The event's badges, one tab per role: the attendee badge every role uses, plus (with events.role_badges)
// crew, volunteer, speaker, mentor, judge and organiser badges that either use the attendee design or have
// their own. A badge converted to a free canvas opens in the card designer instead.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { CardDesigner } from "../../../components/card-designer/CardDesigner";
import { useCardDesignQuery } from "../../../components/card-designer/designerApi";
import { ConfirmDialog, ErrorBlock, SegmentedControl } from "../../../components/ui";
import { useBadgeDesigns, useStartRoleBadge, type BadgeDesigns, type BadgeRoleRow } from "./badgeApi";
import { BadgeDesigner } from "./BadgeDesigner";
import { roleLabels, type BadgeRole } from "./badgeLabels";
import { LogoLoader } from "../../../components/LogoLoader";

export function RoleBadgeTabs({ eventId, makerspaceId }: { eventId: number; makerspaceId?: number }) {
  const info = useBadgeDesigns(eventId);
  const [role, setRole] = useState<BadgeRole>("attendee");
  if (info.isLoading) return <LogoLoader size={48} className="min-h-96 py-3" />;
  if (info.isError || !info.data) return <ErrorBlock error={info.error} resource={t`badge designs`} onRetry={() => void info.refetch()} />;
  const labels = roleLabels();
  const rows = info.data.role_badges ? info.data.roles : info.data.roles.filter((row) => row.role === "attendee");
  const row = rows.find((item) => item.role === role) ?? rows[0];
  return <div className="grid gap-3">
    {rows.length > 1 ? <SegmentedControl label={t`Badge for`} value={row.role} onChange={(value) => setRole(value as BadgeRole)}
      options={rows.map((item) => ({ value: item.role, label: labels[item.role] }))} /> : null}
    <RoleBody key={row.role} eventId={eventId} makerspaceId={makerspaceId} row={row} info={info.data} label={labels[row.role]} />
  </div>;
}

function RoleBody({ eventId, makerspaceId, row, info, label }: { eventId: number; makerspaceId?: number; row: BadgeRoleRow; info: BadgeDesigns; label: string }) {
  const start = useStartRoleBadge(eventId);
  const [confirmRestart, setConfirmRestart] = useState(false);
  const attendee = row.role === "attendee";
  const begin = (restart = false) => start.mutate({ role: row.role, restart }, { onSettled: () => setConfirmRestart(false) });
  const failure = start.error ? <ErrorBlock error={start.error} /> : null;
  if (row.format === "none" || !row.design_id) {
    return <div className="grid justify-items-start gap-2 rounded-xl border border-dashed border-line p-4">
      <p className="text-sm text-ink">{attendee ? t`This event has no badge design yet. Start from the Classic badge and adjust it.`
        : t`${label} badges use the attendee design, with their own label.`}</p>
      <button type="button" className="desk-button-primary min-h-11" disabled={start.isPending} onClick={() => begin()}>
        {attendee ? t`Start the badge design` : t`Give ${label} badges their own design`}</button>
      {failure}
    </div>;
  }
  if (row.format === "free_canvas") {
    return <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface p-3 text-sm text-ink">
        <span className="flex-1">{t`This badge is a free canvas, edited in the card designer.`}</span>
        <button type="button" className="desk-button min-h-11" onClick={() => setConfirmRestart(true)}>{t`Start a badge designer design instead…`}</button>
      </div>
      {failure}
      <ConfirmDialog open={confirmRestart} tone="danger" pending={start.isPending} title={t`Replace this draft with a new badge design?`}
        message={t`The free-canvas draft is replaced by a fresh badge from the badge designer. The published version keeps printing until you publish again.`}
        confirmLabel={t`Replace the draft`} onCancel={() => setConfirmRestart(false)} onConfirm={() => begin(true)} />
      <FreeCanvas designId={row.design_id} makerspaceId={makerspaceId} />
    </div>;
  }
  return <BadgeDesignLoader eventId={eventId} designId={row.design_id} info={info} label={label} />;
}

function FreeCanvas({ designId, makerspaceId }: { designId: number; makerspaceId?: number }) {
  const design = useCardDesignQuery(designId);
  if (!design.data) return design.isError ? <ErrorBlock error={design.error} resource={t`card design`} /> : <LogoLoader size={48} className="min-h-96 py-3" />;
  return <CardDesigner key={designId} designId={designId} makerspaceId={makerspaceId} canEdit={design.data.can_edit} title={t`Badge (free canvas)`} />;
}

function BadgeDesignLoader({ eventId, designId, info, label }: { eventId: number; designId: number; info: BadgeDesigns; label: string }) {
  const design = useCardDesignQuery(designId);
  if (design.isLoading) return <LogoLoader size={48} className="min-h-96 py-3" />;
  if (design.isError || !design.data) return <ErrorBlock error={design.error} resource={t`badge design`} onRetry={() => void design.refetch()} />;
  return <BadgeDesigner key={designId} eventId={eventId} design={design.data} info={info} roleLabel={label}
    onConverted={() => void design.refetch()} />;
}
