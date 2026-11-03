import type { ReactNode } from "react";
import { Callout } from "../../../components/ui";
import { roleLabel, type MergePreview, type MergeResult, type RoleGrant } from "./accountLinkApi";

const GRACE_COPY = "You'll get staff roles without two-step sign-in. You have 3 days to set it up before staff screens are blocked; member features keep working.";

function Grants({ grants, empty }: { grants: RoleGrant[]; empty: string }) {
  if (!grants.length) return <p className="text-sm text-muted">{empty}</p>;
  return <ul className="grid gap-2">{grants.map(grant => <li key={grant.makerspace.id} className="rounded-control border border-line p-3">
    <p className="font-semibold text-ink">{grant.makerspace.name}</p>
    <p className="text-sm text-muted">{grant.roles.map(roleLabel).join(", ") || "No roles"}</p>
  </li>)}</ul>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="grid gap-2"><h3 className="title-section">{title}</h3>{children}</section>;
}

const Counts = ({ rows }: { rows: [string, number][] }) => <dl className="grid gap-2 sm:grid-cols-2">{rows.map(([label, value]) =>
  <div key={label} className="rounded-control border border-line p-3"><dt className="text-sm text-muted">{label}</dt>
    <dd className="text-lg font-semibold tabular-nums text-ink">{value}</dd></div>)}</dl>;

export const GraceCallout = () => <Callout size="panel" tone="warn" lead="Two-step sign-in needed." body={GRACE_COPY}
  action={{ label: "Set up two-step sign-in now", href: "/mfa" }} />;

/** What the link would do, exactly as the server computed it; the confirm sends this preview's hash back. */
export function ReviewStep({ preview }: { preview: MergePreview }) {
  const { source, privilege_diff: diff, moves, conflicts } = preview;
  return <div className="grid gap-6">
    <p className="text-sm text-muted">Linking <strong className="text-ink">{source.display_name || source.username}</strong>
      {source.display_name && source.username ? <> (@{source.username})</> : null} into this account. Nothing has changed yet.</p>
    {preview.grace_opens ? <GraceCallout /> : null}
    <Section title="Staff roles you gain"><Grants grants={diff.roles_gained} empty="No new staff roles." /></Section>
    {diff.duplicate_staff_rows.length ? <Section title="Roles you already hold">
      <p className="text-sm text-muted">These appear on both accounts; you keep one copy.</p>
      <Grants grants={diff.duplicate_staff_rows} empty="" /></Section> : null}
    <Section title="Records">
      <Counts rows={[["Moved to this account", moves.repoint.rows], ["Stay with the old account", moves.keep_on_shell.rows],
        ["One-per-person records checked", moves.unique_resolve.rows], ["Of those, kept on the old account", moves.unique_resolve.kept_on_shell]]} />
    </Section>
    <Section title="Conflicts">
      {conflicts.length ? <ul className="grid gap-2 text-sm">{conflicts.map(conflict => <li key={`${conflict.model}.${conflict.field}`}
        className="break-words rounded-control border border-line p-3"><span className="font-semibold text-ink">{conflict.model}</span> · {conflict.field}
        <span className="text-muted"> — {conflict.kept_on_shell ? "the old account's value stays with it" : "this account's value is kept"}</span></li>)}</ul>
        : <p className="text-sm text-muted">No conflicts.</p>}
    </Section>
  </div>;
}

export function ConfirmStep({ preview, understood, onUnderstood }: { preview: MergePreview; understood: boolean; onUnderstood: (value: boolean) => void }) {
  const name = preview.source.display_name || preview.source.username;
  return <div className="grid gap-4">
    <p>After linking, <strong>{name}</strong> stops signing in. Its roles and history live in this account.</p>
    {preview.grace_opens ? <p className="text-sm text-muted">Next you'll be asked to set up two-step sign-in for your new staff roles.</p> : null}
    <label className="flex min-h-11 items-start gap-3">
      <input type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        checked={understood} onChange={event => onUnderstood(event.target.checked)} />
      <span>I understand the other account stops signing in and this can't be undone</span>
    </label>
  </div>;
}

/** Sits on the result panel's solid tone, so it inherits that ink instead of using surface tokens. */
export function ResultCounts({ result }: { result: MergeResult }) {
  const { counts } = result;
  const rows: [string, number][] = [["Records moved", counts.repointed], ["Kept on the old account", counts.kept_on_shell],
    ["One-per-person records moved", counts.unique_moved], ["One-per-person records kept", counts.unique_kept], ["Old sign-ins ended", counts.revoked]];
  return <div className="grid gap-4">
    <dl className="grid gap-2 sm:grid-cols-2">{rows.map(([label, value]) => <div key={label} className="rounded-control border border-current p-3">
      <dt className="text-sm">{label}</dt><dd className="text-lg font-semibold tabular-nums">{value}</dd></div>)}</dl>
    {result.roles_gained.length ? <div className="grid gap-2"><h3 className="font-semibold">Staff roles added</h3>
      <ul className="grid gap-1">{result.roles_gained.map(grant => <li key={grant.makerspace.id}>
        {grant.makerspace.name}: {grant.roles.map(roleLabel).join(", ")}</li>)}</ul></div> : null}
  </div>;
}
