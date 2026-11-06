import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgePercent } from "lucide-react";

import { ListLayout } from "../../../components/layouts";
import { ActionControl, ListRow, StatusPill } from "../../../components/ui";
import { DISCOUNT_RULES, DiscountEditor } from "./DiscountEditor";
import { describeDiscount } from "./discountForm";
import { pricingApi, pricingError, pricingKeys, type PriceDiscount, type PricingDomain } from "./pricingApi";

const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(formatLocale()) : "");

function windowText(rule: PriceDiscount) {
  if (rule.starts_at && rule.ends_at) return t` · ${when(rule.starts_at)} to ${when(rule.ends_at)}`;
  if (rule.starts_at) return t` · from ${when(rule.starts_at)}`;
  return rule.ends_at ? t` · until ${when(rule.ends_at)}` : "";
}

/** Member discount rules: a list with an Active / Archived switch, and the editor in place of the list. */
export function DiscountsPanel({ makerspaceId, currency, domains, membershipOn, canEdit }: {
  makerspaceId: number; currency: string; domains: PricingDomain[]; membershipOn: boolean; canEdit: boolean;
}) {
  const client = useQueryClient();
  const [view, setView] = useState<"active" | "archived">("active");
  const [editing, setEditing] = useState<PriceDiscount | "new" | null>(null);
  const archived = view === "archived";
  const rules = useQuery({ queryKey: pricingKeys.discounts(makerspaceId, archived),
    queryFn: () => pricingApi.discounts(makerspaceId, archived) });
  const archive = useMutation({
    mutationFn: (rule: PriceDiscount) => pricingApi.archiveDiscount(makerspaceId, rule.id),
    onSuccess: () => client.invalidateQueries({ queryKey: ["pricing-discounts", makerspaceId] }),
  });
  if (editing) {
    return <DiscountEditor makerspaceId={makerspaceId} rule={editing === "new" ? null : editing} currency={currency}
      domains={domains} membershipOn={membershipOn} onDone={() => setEditing(null)} />;
  }
  const shown = (rules.data ?? []).filter(rule => (rule.archived_at !== null) === archived);
  return <ListLayout
    header={{ title: t`Member discounts`, subtitle: DISCOUNT_RULES, headingLevel: 2,
      primary: canEdit ? { label: t`New discount`, onClick: () => setEditing("new") } : undefined }}
    state={rules.isLoading ? { status: "loading" } : rules.error
      ? { status: "error", error: pricingError(rules.error), onRetry: () => { void rules.refetch(); } } : { status: "ready" }}
    tabs={[{ key: "active", label: t`Active` }, { key: "archived", label: t`Archived` }]} activeTab={view}
    onTabChange={key => setView(key as typeof view)}
    isEmpty={!shown.length}
    empty={{ message: archived ? t`No archived discounts. Archived rules stop applying but stay on past receipts.`
      : t`No member discounts yet. Everyone pays the listed price.` }}
    body={{ kind: "rows", rows: <>
      {archived ? <p className="text-sm text-muted">{t`Archived rules stop applying. They cannot be changed or deleted, so past receipts keep naming them.`}</p> : null}
      {shown.map(rule => <ListRow key={rule.id} title={rule.name}
        identityContent={<span className="grid size-10 shrink-0 place-items-center rounded-full border border-line bg-surface text-muted">
          <BadgePercent aria-hidden="true" size={18} /></span>}
        meta={`${describeDiscount(rule, currency)}${windowText(rule)}`}
        onClick={canEdit && !archived ? () => setEditing(rule) : undefined}
        right={<div className="flex flex-wrap items-center gap-2">
          <StatusPill label={archived ? t`Archived` : rule.is_active ? t`Active` : t`Paused`}
            tone={archived ? "neutral" : rule.is_active ? "success" : "warn"} />
          {canEdit && !archived ? <ActionControl action={{ label: t`Archive`, tone: "danger", pending: archive.isPending
            && archive.variables?.id === rule.id, pendingLabel: "Archiving…", onClick: () => archive.mutate(rule),
            confirm: { title: t`Archive ${rule.name}?`, confirmLabel: t`Archive discount`,
              message: t`Archived rules stop applying to new charges. Past receipts keep naming it. This cannot be undone.` } }} /> : null}
        </div>} />)}
      {archive.error ? <p role="alert" className="text-sm text-danger">{pricingError(archive.error)}</p> : null}
    </> }} />;
}
