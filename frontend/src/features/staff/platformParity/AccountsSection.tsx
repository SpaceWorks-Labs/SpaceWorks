import { plural, t } from "@lingui/core/macro";
import { useState, type FormEvent } from "react";
import { EmptyState, ErrorText, Field, ListRow, StatusPill, type Tone } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog, type ReasonSpec } from "../platformSpaces/ActionDialog";
import { useAccountAction, useAccountLookup, type AccountAction, type PlatformAccount } from "./accountsApi";
import { LogoLoader } from "../../../components/LogoLoader";

const getReason = (): ReasonSpec => ({ label: t`Reason`, min: 3, max: 300 });
const accessCopy = (status: string): [string, Tone] => status === "active" ? [t`Access: active`, "success"]
  : status === "restricted" ? [t`Access: restricted`, "warn"] : status === "suspended" ? [t`Access: suspended`, "danger"]
  : [t`Access: ${status}`, "neutral"];
const accountKindLabel = (kind: string) => ({ member: t`Person`, staff: t`Staff-only account`, platform: t`Platform operator` } as Record<string, string>)[kind]
  ?? kind.replace(/_/g, " ");

type Copy = { title: string; confirm: string; message: string; done: string; danger?: boolean; reason?: boolean };
const getCopy = (): Record<AccountAction, Copy> => ({
  disable: { title: t`Disable this account`, confirm: t`Disable account`, done: t`Account disabled.`, danger: true, reason: true,
    message: t`Every session ends and its staff roles are revoked.` },
  enable: { title: t`Re-enable this account`, confirm: t`Re-enable account`, done: t`Account re-enabled.`,
    message: t`Staff roles stay revoked; restore them per space.` },
  "reset-two-step": { title: t`Reset two-step sign-in`, confirm: t`Reset two-step`, done: t`Two-step sign-in reset.`, danger: true, reason: true,
    message: t`Every sign-in factor is cleared and sessions end.` },
});

function AccountDialog({ account, action, onClose }: { account: PlatformAccount; action: AccountAction; onClose: () => void }) {
  const copy = getCopy()[action];
  const mutation = useAccountAction(account.id, action);
  return <ActionDialog title={copy.title} confirmLabel={copy.confirm} tone={copy.danger ? "danger" : "default"}
    message={<><strong className="text-ink">{account.username}</strong>: {copy.message}</>}
    reason={copy.reason ? getReason() : undefined} pending={mutation.isPending} error={mutation.error} onCancel={onClose}
    onSubmit={reason => mutation.mutate(reason, { onSuccess: () => { toast(copy.done); onClose(); } })} />;
}

function AccountCard({ account, onAction }: { account: PlatformAccount; onAction: (action: AccountAction) => void }) {
  const [access, tone] = accessCopy(account.access_status);
  const roles = account.staff_role_count;
  return <ListRow title={account.username}
    meta={`${accountKindLabel(account.account_kind)} · ${plural(roles, { one: "# staff role", other: "# staff roles" })}`}
    right={<div className="grid gap-2">
      <div className="flex flex-wrap gap-2">
        <StatusPill label={account.is_active ? t`Enabled` : t`Disabled`} tone={account.is_active ? "success" : "danger"} />
        <StatusPill label={access} tone={tone} />
        <StatusPill label={account.mfa_enabled ? t`Two-step on` : t`Two-step off`} tone={account.mfa_enabled ? "info" : "neutral"} />
      </div>
      <div className="flex flex-wrap gap-2">
        {account.is_active
          ? <button type="button" className="desk-button-danger-outline" onClick={() => onAction("disable")}>{t`Disable…`}</button>
          : <button type="button" className="desk-button" onClick={() => onAction("enable")}>{t`Re-enable…`}</button>}
        <button type="button" className="desk-button-danger-outline" onClick={() => onAction("reset-two-step")}>{t`Reset two-step…`}</button>
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
    <p className="text-sm text-muted">{t`Look up an account by its exact user name. Email, phone and name are not shown here.`}</p>
    <form className="flex flex-wrap items-end gap-3" aria-label={t`Find an account`} onSubmit={submit}>
      <Field label={t`User name`} className="min-w-0 flex-1 basis-56">
        <input className="desk-input" value={input} autoComplete="off" spellCheck={false} onChange={event => setInput(event.target.value)} />
      </Field>
      <button type="submit" className="desk-button-primary" disabled={!input.trim() || lookup.isFetching}>{t`Find account`}</button>
    </form>
    {!username ? null
      : lookup.isLoading ? <LogoLoader size={48} className="min-h-20 py-3" />
      : lookup.isError ? <ErrorText resource={t`the account`} onRetry={() => { void lookup.refetch(); }} />
      : !found ? <EmptyState message={t`No account is called "${username}".`} />
      : <AccountCard account={found} onAction={action => setActing({ account: found, action })} />}
    {acting ? <AccountDialog account={acting.account} action={acting.action} onClose={() => setActing(null)} /> : null}
  </div>;
}
