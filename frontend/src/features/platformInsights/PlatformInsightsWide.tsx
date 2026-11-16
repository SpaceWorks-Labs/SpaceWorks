import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { formatDateTime } from "../../lib/format";
import { formatBytes } from "../platformOverview/overviewFormat";

/** Parity E-B8 (A16): platform-level counts only; no names, addresses, subjects or free text ever arrive here. */
export type InsightsActivity = { events_held: number; registrations: number; check_ins: number; feedback_responses: number;
  broadcasts_sent: number; recent_broadcasts: { completed_at: string; audience_statuses: string[]; audience_attendance: string }[] };
export type InsightsSecurity = { accounts_unverified: number; accounts_with_passkey: number;
  login_methods: { method: string; accounts: number }[]; sensitive_actions: { action: string; count: number }[];
  api_clients: { active: number; revoked: number; rotating: number; unused_in_window: number } };
export type InsightsStorage = { total_bytes: number; spaces: number; largest_bytes: number[] };

const panel = "rounded-2xl border border-line bg-panel p-4";

function Counts({ label, rows }: { label: string; rows: [string, ReactNode][] }) {
  return <dl aria-label={label} className={`grid gap-x-6 gap-y-2 sm:grid-cols-2 ${panel}`}>
    {rows.map(([name, value]) => <div key={name} className="flex items-baseline justify-between gap-3 border-b border-line pb-2">
      <dt className="text-sm text-muted">{name}</dt><dd className="tabular-nums font-semibold text-ink">{value}</dd></div>)}
  </dl>;
}

const methodLabel = (method: string) => ({ google: t`Google`, github: t`GitHub`, microsoft: t`Microsoft`, apple: t`Apple`,
  oidc: t`Organisation sign-in (OIDC)` } as Record<string, string>)[method] ?? method.replace(/_/g, " ");

const actionLabel = (action: string) => ({
  "auth.mfa_reset": t`Two-step sign-in reset`, "auth.ip_auto_blocked": t`Addresses blocked automatically`,
  "auth.passkey_removed": t`Passkeys removed`, "auth.social_identity_unlinked": t`Social sign-ins unlinked`,
  "api_client.created": t`API clients created`, "api_client.revoked": t`API clients revoked`,
  "api_client.secret_rotated": t`API client secrets rotated`, "api_client.scopes_changed": t`API client scopes changed`,
  "account.credentials_revoked": t`Account credentials revoked`, "account.purged": t`Accounts purged`,
} as Record<string, string>)[action] ?? action;

export function activitySection(activity: InsightsActivity | null | undefined) {
  return { title: t`Events activity`, empty: { message: t`The Events module is off on this platform.` }, isEmpty: activity === null,
    content: activity ? <div className="grid gap-3">
      <Counts label={t`Events activity`} rows={[[t`Events held`, activity.events_held], [t`Registrations`, activity.registrations],
        [t`Check-ins`, activity.check_ins], [t`Feedback responses`, activity.feedback_responses], [t`Broadcasts sent`, activity.broadcasts_sent]]} />
      {activity.recent_broadcasts.length ? <div className={panel}><h3 className="font-semibold">{t`Latest broadcasts`}</h3>
        <ul className="mt-2 grid gap-1 text-sm">{activity.recent_broadcasts.map(row => <li key={row.completed_at} className="flex flex-wrap justify-between gap-2">
          <span>{formatDateTime(row.completed_at)}</span>
          <span className="text-muted">{[row.audience_statuses.join(", ").replace(/_/g, " "), row.audience_attendance.replace(/_/g, " ")].filter(Boolean).join(" · ")}</span>
        </li>)}</ul></div> : null}
    </div> : null };
}

export function securitySection(security: InsightsSecurity | undefined) {
  return { title: t`Security posture`, empty: { message: t`No security data for this window.` }, isEmpty: false,
    content: security ? <div className="grid gap-3">
      <Counts label={t`Accounts`} rows={[[t`Unverified email`, security.accounts_unverified], [t`With a passkey`, security.accounts_with_passkey],
        ...security.login_methods.map(row => [t`Signs in with ${methodLabel(row.method)}`, row.accounts] as [string, ReactNode])]} />
      <Counts label={t`API clients`} rows={[[t`Active API clients`, security.api_clients.active], [t`Revoked API clients`, security.api_clients.revoked],
        [t`Rotating a secret`, security.api_clients.rotating], [t`Unused in this window`, security.api_clients.unused_in_window]]} />
      <Counts label={t`Sensitive actions`} rows={security.sensitive_actions.map(row => [actionLabel(row.action), row.count] as [string, ReactNode])} />
    </div> : null };
}

export function storageSection(storage: InsightsStorage | undefined) {
  return { title: t`Storage`, empty: { message: t`No storage recorded yet.` }, isEmpty: storage?.spaces === 0,
    content: storage ? <div className="grid gap-3">
      <Counts label={t`Storage`} rows={[[t`Used across all spaces`, formatBytes(storage.total_bytes)], [t`Spaces`, storage.spaces]]} />
      {storage.largest_bytes.length ? <div className={panel}><h3 className="font-semibold">{t`Largest spaces`}</h3>
        <p className="mt-1 text-xs text-muted">{t`Sizes only; spaces are not named here.`}</p>
        <ol className="mt-2 grid gap-1 text-sm tabular-nums">{storage.largest_bytes.map((bytes, index) => <li key={index}>{formatBytes(bytes)}</li>)}</ol></div> : null}
    </div> : null };
}
