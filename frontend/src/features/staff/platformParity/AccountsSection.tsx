import { useState, type FormEvent } from "react";
import { EmptyState, ErrorText, Field, ListRow, Skeleton, StatusPill, type Tone } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog, type ReasonSpec } from "../platformSpaces/ActionDialog";
import { useAccountAction, useAccountLookup, type AccountAction, type PlatformAccount } from "./accountsApi";

const REASON: ReasonSpec = { label: "Reason", min: 3, max: 300 };
const ACCESS: Record<PlatformAccount["access_status"], [string, Tone]> = {
  active: ["Access: active", "success"], restricted: ["Access: restricted", "warn"], suspended: ["Access: suspended", "danger"],
};

type Copy = { title: string; confirm: string; message: string; done: string; danger?: boolean; reason?: boolean };
const COPY: Record<AccountAction, Copy> = {
  disable: { title: "Disable this account", confirm: "Disable account", done: "Account disabled.", danger: true, reason: true,
    message: "Every session ends and its staff roles are revoked." },
  enable: { title: "Re-enable this account", confirm: "Re-enable account", done: "Account re-enabled.",
    message: "Staff roles stay revoked; restore them per space." },
  "reset-two-step": { title: "Reset two-step sign-in", confirm: "Reset two-step", done: "Two-step sign-in reset.", danger: true, reason: true,
    message: "Every sign-in factor is cleared and sessions end." },
};

function AccountDialog({ account, action, onClose }: { account: PlatformAccount; action: AccountAction; onClose: () => void }) {
  const copy = COPY[action];
  const mutation = useAccountAction(account.id, action);
  return <ActionDialog title={copy.title} confirmLabel={copy.confirm} tone={copy.danger ? "danger" : "default"}
    message={<><strong className="text-ink">{account.username}</strong>: {copy.message}</>}
    reason={copy.reason ? REASON : undefined} pending={mutation.isPending} error={mutation.error} onCancel={onClose}
    onSubmit={reason => mutation.mutate(reason, { onSuccess: () => { toast(copy.done); onClose(); } })} />;
}

function AccountCard({ account, onAction }: { account: PlatformAccount; onAction: (action: AccountAction) => void }) {
  const [access, tone] = ACCESS[account.access_status] ?? [`Access: ${account.access_status}`, "neutral"];
  const roles = account.staff_role_count;
  return <ListRow title={account.username}
    meta={`${account.account_kind.replace(/_/g, " ")} · ${roles} staff ${roles === 1 ? "role" : "roles"}`}
    right={<div className="grid gap-2">
      <div className="flex flex-wrap gap-2">
        <StatusPill label={account.is_active ? "Enabled" : "Disabled"} tone={account.is_active ? "success" : "danger"} />
        <StatusPill label={access} tone={tone} />
        <StatusPill label={account.mfa_enabled ? "Two-step on" : "Two-step off"} tone={account.mfa_enabled ? "info" : "neutral"} />
      </div>
      <div className="flex flex-wrap gap-2">
        {account.is_active
          ? <button type="button" className="desk-button-danger-outline" onClick={() => onAction("disable")}>Disable…</button>
          : <button type="button" className="desk-button" onClick={() => onAction("enable")}>Re-enable…</button>}
        <button type="button" className="desk-button-danger-outline" onClick={() => onAction("reset-two-step")}>Reset two-step…</button>
      </div>
    </div>} />;
}

/** Find one account by its exact user name, then disable, re-enable or reset its two-step sign-in. */
export function AccountsSection() {
  const [input, setInput] = useState("");
  const [username, setUsername] = useState("");
  const [acting, setActing] = useState<{ account: PlatformAccount; action: AccountAction } | null>(null);
  const lookup = useAccountLookup(username);
  const found = lookup.data?.[0];
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = input.trim();
    if (next === username) void lookup.refetch(); else setUsername(next);
  };
  return <div className="grid gap-4">
    <p className="text-sm text-muted">Look up an account by its exact user name. Email, phone and name are not shown here.</p>
    <form className="flex flex-wrap items-end gap-3" aria-label="Find an account" onSubmit={submit}>
      <Field label="User name" className="min-w-0 flex-1 basis-56">
        <input className="desk-input" value={input} autoComplete="off" spellCheck={false} onChange={event => setInput(event.target.value)} />
      </Field>
      <button type="submit" className="desk-button-primary" disabled={!input.trim() || lookup.isFetching}>Find account</button>
    </form>
    {!username ? null
      : lookup.isLoading ? <Skeleton className="h-20 w-full" />
      : lookup.isError ? <ErrorText resource="the account" onRetry={() => { void lookup.refetch(); }} />
      : !found ? <EmptyState message={`No account is called "${username}".`} />
      : <AccountCard account={found} onAction={action => setActing({ account: found, action })} />}
    {acting ? <AccountDialog account={acting.account} action={acting.action} onClose={() => setActing(null)} /> : null}
  </div>;
}
