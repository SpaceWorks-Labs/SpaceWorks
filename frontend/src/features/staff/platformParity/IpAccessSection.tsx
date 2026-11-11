import { t } from "@lingui/core/macro";
import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "../platformSpaces/ActionDialog";
import { IpRuleForm } from "./IpRuleForm";
import { useDeleteIpRule, useIpBlocks, useIpRules, useUnblock, type IpBlock, type IpRule } from "./ipAccessApi";
import { PAGE_SIZE } from "./parityRequest";

const pages = (count = 0) => Math.max(1, Math.ceil(count / PAGE_SIZE));

function DeleteRuleDialog({ rule, onClose }: { rule: IpRule; onClose: () => void }) {
  const remove = useDeleteIpRule();
  return <ActionDialog title={t`Delete this rule`} confirmLabel={t`Delete rule`} tone="danger" pending={remove.isPending} error={remove.error}
    onCancel={onClose} message={t`The ${rule.action} rule for ${rule.cidr} stops applying right away.`}
    onSubmit={() => remove.mutate(rule.id, { onSuccess: () => { toast(t`Rule deleted.`); onClose(); } })} />;
}

function UnblockDialog({ block, onClose }: { block: IpBlock; onClose: () => void }) {
  const unblock = useUnblock();
  return <ActionDialog title={t`Lift this block`} confirmLabel={t`Lift block`} pending={unblock.isPending} error={unblock.error}
    onCancel={onClose} message={t`Requests from ${block.network} are accepted again right away. Failed sign-ins against many accounts can block it again.`}
    onSubmit={() => unblock.mutate(block.id, { onSuccess: () => { toast(t`Block lifted.`); onClose(); } })} />;
}

function RulesList() {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<IpRule | null>(null);
  const list = useIpRules(page);
  const rows = list.data?.results ?? [];
  return <section className="grid gap-3" aria-labelledby="ip-rules-heading">
    <h3 id="ip-rules-heading" className="title-section">{t`Rules`}</h3>
    <CollapsibleSection title={t`New rule`} open={adding} onToggle={() => setAdding(!adding)}><IpRuleForm /></CollapsibleSection>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource={t`IP rules`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No rules. Every address is allowed unless it is blocked automatically.`} />
      : <div className="grid gap-3">{rows.map(rule => <ListRow key={rule.id} title={rule.cidr}
        meta={<>{rule.note ? `${rule.note} · ` : ""}{rule.expires_at ? <>expires <RelativeTime date={rule.expires_at} exact /></> : t`no expiry`}
          {t` · added `}<RelativeTime date={rule.created_at} exact />{rule.created_by ? ` by ${rule.created_by}` : ""}</>}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={rule.action === "allow" ? t`Allow` : t`Deny`} tone={rule.action === "allow" ? "success" : "danger"} />
          {rule.active ? null : <StatusPill label={t`Not in force`} />}
          <button type="button" className="desk-button-danger-outline" aria-label={t`Delete the rule for ${rule.cidr}`}
            onClick={() => setDeleting(rule)}>{t`Delete…`}</button>
        </div>} />)}</div>}
    <Pagination page={page} totalPages={pages(list.data?.count)} onChange={setPage} count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {deleting ? <DeleteRuleDialog rule={deleting} onClose={() => setDeleting(null)} /> : null}
  </section>;
}

function BlocksList() {
  const [page, setPage] = useState(1);
  const [lifting, setLifting] = useState<IpBlock | null>(null);
  const list = useIpBlocks(page);
  const rows = list.data?.results ?? [];
  return <section className="grid gap-3" aria-labelledby="ip-blocks-heading">
    <h3 id="ip-blocks-heading" className="title-section">{t`Automatic blocks`}</h3>
    <p className="text-sm text-muted">{t`Networks blocked after failed sign-ins against many different accounts. Each block lifts on its own when its time runs out.`}</p>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource={t`automatic blocks`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`Nothing has been blocked.`} />
      : <div className="grid gap-3">{rows.map(block => <ListRow key={block.id} title={block.network}
        meta={<>{block.active ? t`blocked until ` : "ended "}<RelativeTime date={block.blocked_until} exact />
          {t` · started `}<RelativeTime date={block.created_at} exact /></>}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={block.active ? t`Blocked` : t`Ended`} tone={block.active ? "warn" : "neutral"} />
          {block.active ? <button type="button" className="desk-button"
            onClick={() => setLifting(block)}>{t`Lift now…`}{" "}<span className="sr-only">{block.network}</span></button> : null}
        </div>} />)}</div>}
    <Pagination page={page} totalPages={pages(list.data?.count)} onChange={setPage} count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    {lifting ? <UnblockDialog block={lifting} onClose={() => setLifting(null)} /> : null}
  </section>;
}

/** Deployment-wide IP rules and the automatic sign-in blocks, as /control/ had them. */
export function IpAccessSection() {
  return <div className="grid gap-6">
    <p className="text-sm text-muted">
      {t`An allow rule beats every deny rule and every automatic block. A deny rule always applies. A rule that would lock you out is refused.`}</p>
    <RulesList />
    <BlocksList />
  </div>;
}
