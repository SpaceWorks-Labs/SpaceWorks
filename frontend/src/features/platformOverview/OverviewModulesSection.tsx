import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { DataTable, type DataTableColumn } from "../../components/ui";
import type { OverviewSpace, PlatformOverview } from "./platformOverviewApi";

type ModuleRow = PlatformOverview["modules"][number];
const SHOWN = 5;

/** The first few space names, then a count, so a large platform keeps one readable line per module. */
function spaceList(ids: number[], spaces: Map<number, OverviewSpace>) {
  const names = ids.slice(0, SHOWN).map(id => spaces.get(id)?.name ?? `#${id}`).join(", ");
  return ids.length > SHOWN ? `${names} and ${ids.length - SHOWN} more` : names;
}

/** Which spaces have which module on, plus the blocks hidden because their module is off everywhere. */
export function OverviewModulesSection({ data, spaces }: { data: PlatformOverview; spaces: Map<number, OverviewSpace> }) {
  const columns: DataTableColumn<ModuleRow>[] = [
    { key: "label", header: "Module", phone: "title", render: row => <span className="font-semibold">{row.label}</span> },
    { key: "on_in", header: "On in", phone: "detail", className: "tabular-nums", render: row => row.on_in.toLocaleString(formatLocale()) },
    { key: "off_in", header: "Off in", phone: "detail", className: "tabular-nums", render: row => row.off_in.toLocaleString(formatLocale()) },
    { key: "spaces", header: "Spaces with it on", phone: "detail", render: row => row.space_ids.length
      ? spaceList(row.space_ids, spaces) : <span className="text-muted">{t`None`}</span> },
  ];
  return <div className="grid min-w-0 gap-4">
    {data.hidden_blocks.length ? <ul className="grid gap-2" aria-label={t`Sections with their module off in every space`}>
      {data.hidden_blocks.map(block => <li key={block.key} className="rounded-xl border border-dashed border-line px-4 py-3 text-sm">
        <span className="font-semibold">{block.label}</span> {t` is hidden: its module is off in all ${block.off_in} ${block.off_in === 1 ? "space" : "spaces"}.`}</li>)}
    </ul> : null}
    <DataTable caption={t`Modules switched on per space`} data={data.modules} getRowId={row => row.key} columns={columns} />
  </div>;
}
