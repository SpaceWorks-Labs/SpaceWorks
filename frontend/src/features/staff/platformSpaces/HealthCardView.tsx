import type { ReactNode } from "react";
import { OverflowMenu, ProgressBar, RelativeTime, StatusPill, type Tone } from "../../../components/ui";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { persistSelectedMakerspace } from "../staffTabs";
import { cardActions, type DialogKind } from "./cardActions";
import { percentLevel, STATE_LABELS, type HealthCard, type SpaceState } from "./spacesApi";

const STATE_TONES: Record<SpaceState, Tone> = { active: "success", read_only: "warn", suspended: "danger", archived: "neutral",
  scheduled: "warn", importing: "info", aborted: "danger" };

/** The superadmin's console opens a space by remembering it as the platform session's choice. */
export function openSpaceConsole(card: Pick<HealthCard, "id">) {
  persistSelectedMakerspace(card.id, "platform");
  window.location.assign(consoleSessionHref("/admin/dashboard", "platform"));
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0"><dt className="text-xs text-muted">{label}</dt><dd className="text-sm text-ink [overflow-wrap:anywhere]">{children}</dd></div>;
}

export function HealthCardView({ card, managedPlans, onOpen, onDetails }: {
  card: HealthCard; managedPlans: boolean; onOpen: (kind: DialogKind) => void; onDetails: () => void;
}) {
  const peak = card.usage_peak_percent;
  const level = percentLevel(peak);
  const drill = card.backups.last_drill;
  return <article aria-label={card.name} className="grid min-w-0 gap-4 rounded-2xl border border-line bg-panel p-4">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h3 className="title-section break-words">{card.name}</h3>
        <p className="text-sm text-muted">{card.public_code || card.slug}</p>
      </div>
      <StatusPill label={STATE_LABELS[card.state] ?? card.state} tone={STATE_TONES[card.state] ?? "neutral"} />
    </header>
    {card.suspended ? <p className="text-sm text-danger">Suspended: {card.suspended.reason}</p> : null}
    {card.read_only ? <p className="text-sm text-ink">Read-only{card.read_only.source !== "manual" ? ` (${card.read_only.source.replace(/_/g, " ")})` : ""}: {card.read_only.reason}</p> : null}
    {card.schedule ? <p className="text-sm text-ink">
      {card.schedule.archive_on ? <>Archives <RelativeTime date={card.schedule.archive_on} exact />. </> : null}
      {card.schedule.purge_due_at ? <>Purge due <RelativeTime date={card.schedule.purge_due_at} exact />.</> : null}
    </p> : null}
    <div className="grid gap-1">
      <div className="flex items-center justify-between gap-2 text-sm"><span className="text-muted">Highest usage</span>
        <span className="tabular-nums text-ink">{peak === null ? "No limits" : `${Math.round(peak)}%`}{level === "limit" ? " · At limit" : level === "warning" ? " · Near limit" : ""}</span></div>
      {peak !== null ? <ProgressBar value={peak / 100} label={`${card.name} highest usage`} tone={level === "limit" ? "danger" : level === "warning" ? "warn" : "accent"} /> : null}
    </div>
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <Fact label="Last activity">{card.last_activity_at ? <RelativeTime date={card.last_activity_at} /> : "None yet"}</Fact>
      <Fact label="Last backup">{card.backups.last_backed_up_at ? <RelativeTime date={card.backups.last_backed_up_at} /> : "Never"}</Fact>
      <Fact label="Restore drill">{drill ? `${drill.outcome === "passed" ? "Passed" : "Failed"}` : "Never run"}</Fact>
      <Fact label="Security">{card.security.blocked_accounts} blocked · {card.security.locked_settings} locked</Fact>
      <Fact label="Open issues">{card.open_issues}</Fact>
      <Fact label="Modules">{card.modules.length}</Fact>
      <Fact label="Managers">{card.managers.length ? card.managers.map(row => row.name || row.email).join(", ") : "None"}</Fact>
      {card.plan ? <Fact label="Plan">{card.plan.name}{card.plan.trial_ends_at ? <> · trial ends <RelativeTime date={card.plan.trial_ends_at} exact /></> : null}</Fact> : null}
    </dl>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button" onClick={onDetails}>Details</button>
      {card.archived_at === null && card.lifecycle_state === "active" ? <button type="button" className="desk-button" onClick={() => openSpaceConsole(card)}>Open console</button> : null}
      <OverflowMenu label="Manage" showLabel actions={cardActions(card, managedPlans, onOpen)} />
    </div>
  </article>;
}
