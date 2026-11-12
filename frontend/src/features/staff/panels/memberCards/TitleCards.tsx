// Role cards (parity C6): every title with its own card design, whether that design is a draft, live or has
// unpublished changes, its number pattern and how many live cards use it. A title with no design of its own
// inherits the plan or space card; "Add design" gives it one.
import { plural, t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { Badge, ErrorBlock } from "../../../../components/ui";
import { staffRequest } from "../../../../lib/api";
import { LogoLoader } from "../../../../components/LogoLoader";

export type TitleCardRow = { title_id: number; title: string; design_id: number | null;
  status: "inherits" | "draft" | "published" | "changes"; number_pattern: string; live_cards: number };

const STATUS = (): Record<TitleCardRow["status"], { label: string; tone: "neutral" | "warn" | "success" }> => ({
  inherits: { label: t`Uses the default card`, tone: "neutral" }, draft: { label: t`Draft`, tone: "warn" },
  published: { label: t`Live`, tone: "success" }, changes: { label: t`Live, unpublished changes`, tone: "warn" },
});

export function TitleCards({ makerspaceId, canEdit, onOpen, onAdd, adding }: {
  makerspaceId: number; canEdit: boolean; onOpen: (designId: number) => void; onAdd: (titleId: number) => void; adding: boolean;
}) {
  const rows = useQuery({ queryKey: ["title-cards", makerspaceId],
    queryFn: () => staffRequest<TitleCardRow[]>(`/admin/makerspaces/${makerspaceId}/card-designs/titles`) });
  if (rows.isLoading) return <LogoLoader size={48} className="min-h-24 py-3" />;
  if (rows.isError) return <ErrorBlock error={rows.error} resource={t`role cards`} onRetry={() => void rows.refetch()} />;
  if (!rows.data?.length) return null;
  const statuses = STATUS();
  return <section className="grid gap-2 rounded-card border border-line bg-panel p-4" aria-label={t`Role cards`}>
    <h3 className="text-sm font-semibold text-ink">{t`Role cards`}</h3>
    <p className="text-xs text-muted">{t`Each title can have its own card. Members take the card of their primary title.`}</p>
    <ul className="grid gap-2">{rows.data.map((row) => <li key={row.title_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <span className="flex flex-wrap items-center gap-2"><span className="font-medium text-ink">{row.title}</span>
        <Badge tone={statuses[row.status].tone}>{statuses[row.status].label}</Badge>
        {row.number_pattern ? <span className="font-mono text-xs text-muted">{row.number_pattern}</span> : null}
        <span className="text-xs text-muted">{plural(row.live_cards, { one: "# live card", other: "# live cards" })}</span></span>
      {row.design_id !== null ? <button type="button" className="desk-button-ghost min-h-11" onClick={() => onOpen(row.design_id!)}>{canEdit ? t`Edit design` : t`View design`}</button>
        : canEdit ? <button type="button" className="desk-button-ghost min-h-11" disabled={adding} onClick={() => onAdd(row.title_id)}>{t`Add design`}</button> : null}
    </li>)}</ul>
  </section>;
}
