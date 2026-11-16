import { plural, t } from "@lingui/core/macro";
import { publicWidgetVisible, type PublicStatsCurrentLoan, type PublicStatsHardware, type PublicStatsPrinting, type PublicStatsVisibility } from "./api";
import { DataTable, EmptyState, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { ImageThumbnail } from "../../components/ui/ImageThumbnail";
import { BarChart, CompactList, Section, StatTile, formatDate, formatNumber } from "./StatsParts";

export function PrintingSection({ printing, visibility }: { printing: PublicStatsPrinting; visibility?: PublicStatsVisibility }) {
  const shown = (key: string) => publicWidgetVisible(visibility, `printing.${key}`);
  const queue = printing.jobs.queue;
  const queueTotal = queue ? queue.pending + queue.accepted + queue.printing : 0;
  return <Section title={t`Printing`}>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {shown("hours_all_time") && printing.hours_all_time !== null ? <StatTile label={t`Print hours all time`} value={formatNumber(printing.hours_all_time)} /> : null}
      {shown("hours_this_month") && printing.hours_this_month !== null ? <StatTile label={t`Print hours this month`} value={formatNumber(printing.hours_this_month)} /> : null}
      {shown("grams_all_time") && printing.grams_all_time !== null ? <StatTile label={t`Filament used`} value={`${formatNumber(printing.grams_all_time)} g`} /> : null}
      {shown("completed_jobs") && printing.jobs.completed !== null ? <StatTile label={t`Completed jobs`} value={printing.jobs.completed} /> : null}
    </div>
    <div className="grid gap-5 lg:grid-cols-3">
      {shown("busiest_printer") ? <div><h3 className="title-section mb-3">{t`Busiest printer`}</h3>{printing.busiest_printer ? <ListRow title={printing.busiest_printer.name}
        identity={printing.busiest_printer.image_url ? { kind: "image", src: printing.busiest_printer.image_url } : { kind: "icon", icon: "Printer", tone: "accent" }}
        meta={<>{printing.busiest_printer.model}<span className="block tabular-nums">{t`${formatNumber(printing.busiest_printer.hours)} hours / ${printing.busiest_printer.completed} completed`}</span></>} />
        : <EmptyState message={t`No printer activity yet. Completed jobs will appear here.`} />}</div> : null}
      {shown("queue") && queue ? <div><h3 className="title-section mb-3">{t`Queue`}</h3><div className="flex flex-wrap gap-2">
        <StatusPill label={`${queue.pending} pending`} tone="warn" /><StatusPill label={`${queue.accepted} accepted`} tone="info" />
        <StatusPill label={`${queue.printing} printing`} tone="accent" /><StatusPill label={`${queueTotal} active`} tone="neutral" />
      </div></div> : null}
      {shown("by_brand") ? <div><h3 className="title-section">{t`By brand`}</h3><CompactList empty="No filament records yet. Recorded usage will appear here." rows={printing.by_brand.map(row => ({ label: row.brand, value: `${formatNumber(row.grams)} g` }))} /></div> : null}
    </div>
    {shown("filament_trend") ? <div><h3 className="title-section mb-4">{t`Filament trend`}</h3><BarChart rows={printing.filament_trend.map(row => ({ label: row.period, value: row.grams }))} valueLabel="g" /></div> : null}
    {shown("per_printer") ? <div><h3 className="title-section mb-4">{t`Per printer`}</h3><DataTable data={printing.per_printer.map((row, rowId) => ({ ...row, rowId }))} getRowId={row => row.rowId}
      emptyTitle={t`No printer activity yet.`} emptyDescription={t`Printer totals appear as jobs are recorded.`}
      columns={[
        { key: "name", header: t`Printer`, render: row => <div className="flex min-w-0 items-center gap-3"><ImageThumbnail src={row.image_url} alt={row.name} /><span className="min-w-0 break-words">{row.name}{row.model ? <span className="block text-sm text-muted">{row.model}</span> : null}</span></div> },
        { key: "jobs", header: t`Completed jobs`, className: "tabular-nums md:text-right" },
        { key: "hours", header: t`Hours`, className: "tabular-nums md:text-right", render: row => formatNumber(row.hours) },
        { key: "grams", header: t`Filament (g)`, className: "tabular-nums md:text-right", render: row => formatNumber(row.grams) },
      ]} /></div> : null}
  </Section>;
}

export function HardwareSection({ hardware, visibility }: { hardware: PublicStatsHardware; visibility?: PublicStatsVisibility }) {
  const shown = (key: string) => publicWidgetVisible(visibility, `lending.${key}`);
  return <Section title={t`Inventory`}>
    <div className="grid gap-4 sm:grid-cols-3">
      {shown("library") && hardware.library.library_size !== null ? <StatTile label={t`Public library`} value={hardware.library.library_size} /> : null}
      {shown("available") && hardware.library.available_count !== null ? <StatTile label={t`Available now`} value={hardware.library.available_count} /> : null}
      {shown("currently_out") && hardware.library.currently_out_count !== null ? <StatTile label={t`Currently out`} value={hardware.library.currently_out_count} /> : null}</div>
    <div className="grid gap-6 lg:grid-cols-3">
      {shown("most_popular") ? <div><h3 className="title-section">{t`Most popular`}</h3><CompactList empty={t`No loan history yet. Loans will appear here as tools are borrowed.`} rows={hardware.most_popular.map(row => ({ label: row.name, value: plural(row.times_lent, { one: `# loan / ${row.total_quantity_lent} total`, other: `# loans / ${row.total_quantity_lent} total` }) }))} /></div> : null}
      {shown("tools_out") ? <div><h3 className="title-section">{t`Tools out`}</h3><CompactList empty="No tools are out. Browse inventory to find your next tool." rows={hardware.tools_out.map(row => ({ label: row.name, value: `${row.quantity_out} out` }))} /></div> : null}
      {shown("recently_added") ? <div><h3 className="title-section">{t`Recently added`}</h3><div className="mt-3 grid gap-3">{hardware.recently_added.length ? hardware.recently_added.map((row, index) => <ListRow key={`${row.name}-${index}`} title={row.name} right={<RelativeTime date={row.created_at} />} />) : <EmptyState message={t`No new public gear this month. Check back for new tools.`} />}</div></div> : null}
    </div>
  </Section>;
}

export function CurrentLoansSection({ loans }: { loans: PublicStatsCurrentLoan[] }) {
  return <Section title={t`Out right now`}>{loans.length ? <div className="grid gap-3">{loans.map((loan, index) => <ListRow key={`${loan.item_name}-${index}`}
    title={loan.item_name} meta={<>{t`With ${loan.holder_name}`}{loan.since ? <span className="block">{t`Borrowed `}<RelativeTime date={loan.since} /></span> : null}</>}
    right={<StatusPill label={loan.due ? t`Due ${formatDate(loan.due)}` : t`No due date`} tone="accent" />} />)}</div>
    : <EmptyState message={t`No public tools are currently out. Browse inventory to borrow something.`} />}</Section>;
}
