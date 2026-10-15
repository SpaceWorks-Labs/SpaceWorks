import { plural } from "../../lib/plural";
import type { PublicStatsCurrentLoan, PublicStatsHardware, PublicStatsPrinting } from "./api";
import { DataTable, EmptyState, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { ImageThumbnail } from "../../components/ui/ImageThumbnail";
import { BarChart, CompactList, Section, StatTile, formatDate, formatNumber } from "./StatsParts";

export function PrintingSection({ printing }: { printing: PublicStatsPrinting }) {
  const queueTotal = printing.jobs.queue.pending + printing.jobs.queue.accepted + printing.jobs.queue.printing;
  return <Section title="Printing">
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatTile label="Print hours all time" value={formatNumber(printing.hours_all_time)} />
      <StatTile label="Print hours this month" value={formatNumber(printing.hours_this_month)} />
      <StatTile label="Filament used" value={`${formatNumber(printing.grams_all_time)} g`} />
      <StatTile label="Completed jobs" value={printing.jobs.completed} />
    </div>
    <div className="grid gap-5 lg:grid-cols-3">
      <div><h3 className="title-section mb-3">Busiest printer</h3>{printing.busiest_printer ? <ListRow title={printing.busiest_printer.name}
        identity={printing.busiest_printer.image_url ? { kind: "image", src: printing.busiest_printer.image_url } : { kind: "icon", icon: "Printer", tone: "accent" }}
        meta={<>{printing.busiest_printer.model}<span className="block tabular-nums">{formatNumber(printing.busiest_printer.hours)} hours / {printing.busiest_printer.completed} completed</span></>} />
        : <EmptyState message="No printer activity yet. Completed jobs will appear here." />}</div>
      <div><h3 className="title-section mb-3">Queue</h3><div className="flex flex-wrap gap-2">
        <StatusPill label={`${printing.jobs.queue.pending} pending`} tone="warn" /><StatusPill label={`${printing.jobs.queue.accepted} accepted`} tone="info" />
        <StatusPill label={`${printing.jobs.queue.printing} printing`} tone="accent" /><StatusPill label={`${queueTotal} active`} tone="neutral" />
      </div></div>
      <div><h3 className="title-section">By brand</h3><CompactList empty="No filament records yet. Recorded usage will appear here." rows={printing.by_brand.map(row => ({ label: row.brand, value: `${formatNumber(row.grams)} g` }))} /></div>
    </div>
    <div><h3 className="title-section mb-4">Filament trend</h3><BarChart rows={printing.filament_trend.map(row => ({ label: row.period, value: row.grams }))} valueLabel="g" /></div>
    <div><h3 className="title-section mb-4">Per printer</h3><DataTable data={printing.per_printer.map((row, rowId) => ({ ...row, rowId }))} getRowId={row => row.rowId}
      emptyTitle="No printer activity yet." emptyDescription="Printer totals appear as jobs are recorded."
      columns={[
        { key: "name", header: "Printer", render: row => <div className="flex items-center gap-3"><ImageThumbnail src={row.image_url} alt={row.name} /><span>{row.name}{row.model ? <span className="block text-sm text-muted">{row.model}</span> : null}</span></div> },
        { key: "jobs", header: "Completed jobs", className: "tabular-nums md:text-right" },
        { key: "hours", header: "Hours", className: "tabular-nums md:text-right", render: row => formatNumber(row.hours) },
        { key: "grams", header: "Filament (g)", className: "tabular-nums md:text-right", render: row => formatNumber(row.grams) },
      ]} /></div>
  </Section>;
}

export function HardwareSection({ hardware }: { hardware: PublicStatsHardware }) {
  return <Section title="Lending">
    <div className="grid gap-4 sm:grid-cols-3"><StatTile label="Public library" value={hardware.library.library_size} />
      <StatTile label="Available now" value={hardware.library.available_count} /><StatTile label="Currently out" value={hardware.library.currently_out_count} /></div>
    <div className="grid gap-6 lg:grid-cols-3">
      <div><h3 className="title-section">Most popular</h3><CompactList empty="No lending history yet. Loans will appear here as tools are borrowed." rows={hardware.most_popular.map(row => ({ label: row.name, value: `${plural(row.times_lent, "loan")} / ${row.total_quantity_lent} total` }))} /></div>
      <div><h3 className="title-section">Tools out</h3><CompactList empty="No tools are out. Browse the catalogue to find your next tool." rows={hardware.tools_out.map(row => ({ label: row.name, value: `${row.quantity_out} out` }))} /></div>
      <div><h3 className="title-section">Recently added</h3><div className="mt-3 grid gap-3">{hardware.recently_added.length ? hardware.recently_added.map((row, index) => <ListRow key={`${row.name}-${index}`} title={row.name} right={<RelativeTime date={row.created_at} />} />) : <EmptyState message="No new public gear this month. Check back for new tools." />}</div></div>
    </div>
  </Section>;
}

export function CurrentLoansSection({ loans }: { loans: PublicStatsCurrentLoan[] }) {
  return <Section title="Out right now">{loans.length ? <div className="grid gap-3">{loans.map((loan, index) => <ListRow key={`${loan.item_name}-${index}`}
    title={loan.item_name} meta={<>With {loan.holder_name}{loan.since ? <span className="block">Borrowed <RelativeTime date={loan.since} /></span> : null}</>}
    right={<StatusPill label={loan.due ? `Due ${formatDate(loan.due)}` : "No due date"} tone="accent" />} />)}</div>
    : <EmptyState message="No public tools are currently out. Browse the catalogue to borrow something." />}</Section>;
}
