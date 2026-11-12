import { plural, t } from "@lingui/core/macro";
import { useInRouterContext, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ListLayout } from "../../components/layouts";
import { ErrorBlock, ListRow, Modal, RelativeTime, SegmentedControl, StatusPill } from "../../components/ui";
import { toast } from "../../components/ui/toastStore";
import { staffRequest } from "../../lib/api";
import type { Page } from "./PersonalInbox";
import { SuppressionAdmin } from "./SuppressionAdmin";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

type Delivery = {
  id: number; kind: "email" | "channel"; channel: string; feature: string; event: string;
  destination_id: number | null; destination_label: string; status: string; error: string;
  attempts: number; retry_generation: number; created_at: string; sent_at: string | null;
};
type Destination = { id: number; label: string; channel: string; is_active: boolean };
type TestResult = { kind: string; id: number; status: string };
const FAMILIES = (): Record<string, string> => ({ hardware_requests: t`Hardware`, printing: t`Printing`, events: t`Events`, bookings: t`Bookings`,
  maintenance: t`Maintenance`, members: t`Members`, payments: t`Payments`, stock: t`Stock`, certifications: t`Machine access`, devices: t`Devices`, api_access: t`API access` });
const CHANNELS = ["email", "telegram", "slack", "mattermost", "discord", "webhook", "native_push"];
const STATUSES = ["sent", "failed", "pending", "sending", "skipped"];
const statusLabel = (status: string) => {
  switch (status) {
    case "sent": return t`Sent`;
    case "failed": return t`Failed`;
    case "pending": return t`Queued`;
    case "sending": return t`Sending`;
    case "skipped": return t`Skipped`;
    case "delivered": return t`Delivered`;
    case "suppressed": return t`Suppressed`;
    default: return t`Unknown`;
  }
};
const words = (value: string) => { const text = value.replace(/[_.]+/g, " "); return text.charAt(0).toUpperCase() + text.slice(1); };

export function DeliveryLogScreen(props: { makerspaceId: number }) {
  const routed = useInRouterContext();
  return routed ? <RoutedDeliveryLog {...props} /> : <DeliveryLogContent {...props} search={new URLSearchParams(window.location.search)} dialogs={false} />;
}
function RoutedDeliveryLog(props: { makerspaceId: number }) {
  const [search] = useSearchParams();
  return <DeliveryLogContent {...props} search={search} dialogs />;
}
function DeliveryLogContent({ makerspaceId, search, dialogs }: { makerspaceId: number; search: URLSearchParams; dialogs: boolean }) {
  const client = useQueryClient();
  const suppressed = search.get("delivery_view") === "suppression";
  const viewHref = (view: string) => { const next = new URLSearchParams(search); next.set("delivery_view", view); return `?${next}`; };
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ channel: "", status: "", feature: "", event: "", destination: "" });
  const [testDestination, setTestDestination] = useState("");
  const [testOpen, setTestOpen] = useState(false);
  const [suppressOpen, setSuppressOpen] = useState(false);
  const path = `/integrations/makerspace/${makerspaceId}`;
  const params = new URLSearchParams({ page: String(page) });
  Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value); });
  const logs = useQuery({ queryKey: ["notification-deliveries", makerspaceId, params.toString()],
    queryFn: () => staffRequest<Page<Delivery>>(`${path}/delivery-logs?${params}`), refetchInterval: 30_000 });
  const destinations = useQuery({ queryKey: ["notification-delivery-destinations", makerspaceId],
    queryFn: () => staffRequest<Destination[]>(`/admin/makerspace/${makerspaceId}/notification-destinations`) });
  const refresh = () => client.invalidateQueries({ queryKey: ["notification-deliveries", makerspaceId] });
  const retry = useMutation({ mutationFn: (row: Delivery) => staffRequest<Delivery>(
    `${path}/delivery-logs/${row.kind}/${row.id}/retry`, { method: "POST", body: JSON.stringify({ generation: row.retry_generation }) },
  ), onSuccess: refresh });
  const test = useMutation({ mutationFn: () => staffRequest<TestResult>(`${path}/delivery-test`, {
    method: "POST", body: JSON.stringify(testDestination ? { destination_id: Number(testDestination) } : {}),
  }), onSuccess: result => { setTestOpen(false); toast(t`Test ${result.kind} #${result.id}: ${statusLabel(result.status)}.`, { tone: result.status === "failed" ? "error" : "success" }); return refresh(); } });
  const update = (key: keyof typeof filters, value: string) => { setFilters({ ...filters, [key]: value }); setPage(1); };
  const clearFilters = () => { setFilters({ channel: "", status: "", feature: "", event: "", destination: "" }); setPage(1); };
  const destinationName = destinations.data?.find(row => String(row.id) === filters.destination)?.label ?? filters.destination;
  const chipText: Record<keyof typeof filters, string> = { status: t`status: ${statusLabel(filters.status)}`, channel: t`channel: ${words(filters.channel)}`,
    feature: t`family: ${FAMILIES()[filters.feature] ?? words(filters.feature)}`, event: t`event: ${filters.event}`,
    destination: t`destination: ${destinationName}` };
  const chips = (Object.keys(filters) as (keyof typeof filters)[]).filter(key => filters[key]).map(key => ({ key, label: chipText[key], onRemove: () => update(key, "") }));
  const failed = logs.data?.results.filter(row => row.status === "failed").length ?? 0;
  const target = <label className="grid gap-2 text-sm font-semibold">{t`Test target`}<select className="desk-input" value={testDestination} onChange={event => setTestDestination(event.target.value)}>
    <option value="">{t`Email to my account`}</option>{destinations.data?.filter(row => row.is_active).map(row => <option key={row.id} value={row.id}>{row.label} ({words(row.channel)})</option>)}
  </select></label>;
  const destinationState = <>{destinations.isLoading ? <LogoLoader size={48} className="min-h-11 py-3 max-w-48" /> : null}
    {destinations.error ? <ErrorBlock error={new Error(t`Couldn't load delivery destinations. Try again.`)} onRetry={() => { void destinations.refetch(); }} /> : null}</>;
  return <ListLayout header={{ title: t`Delivery log`, subtitle: t`Every email and alert this space sent, and whether it arrived.`,
      primary: suppressed ? { label: t`Suppress an address`, onClick: () => setSuppressOpen(true) } : {
        label: t`Send test`, pending: test.isPending, onClick: () => dialogs ? setTestOpen(true) : test.mutate() } }}
    callout={!suppressed && !logs.isLoading && !logs.error && failed > 0 ? { size: "banner", tone: "danger",
      lead: plural(failed, { one: "# delivery failed on this page.", other: "# deliveries failed on this page." }), body: t`Check the reason and retry the affected deliveries.`,
      action: filters.status === "failed" ? { label: t`Refresh failures`, onClick: () => { void logs.refetch(); } } : { label: t`Show failed`, onClick: () => update("status", "failed") } } : undefined}
    tabs={[{ key: "deliveries", label: t`Deliveries`, href: viewHref("deliveries"), count: logs.data?.count },
      { key: "suppression", label: t`Suppressed addresses`, href: viewHref("suppression") }]}
    activeTab={suppressed ? "suppression" : "deliveries"}
    state={{ status: suppressed ? "ready" : logs.isLoading ? "loading" : logs.error ? "error" : "ready",
      error: t`Couldn't load deliveries. Try again.`, onRetry: () => { void logs.refetch(); } }}
    isEmpty={!suppressed && logs.data?.results.length === 0}
    empty={{ message: t`Nothing sent yet. Send a test to check your setup.` }}
    filtered={Object.values(filters).some(Boolean)} filteredEmpty={{ message: t`No deliveries match. Try another filter.`,
      action: { label: t`Clear filters`, onClick: clearFilters } }}
    filters={suppressed ? undefined : { activeCount: chips.length, chips, onClear: clearFilters, controls: <div className="grid gap-4">
      <SegmentedControl label={t`Delivery status`} value={filters.status} options={[{ value: "", label: t`All` }, ...STATUSES.map(value => ({ value, label: statusLabel(value) }))]} onChange={value => update("status", value)} />
      {destinationState}<div className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1 text-sm">{t`Channel`}<select className="desk-input" value={filters.channel} onChange={event => update("channel", event.target.value)}>
          <option value="">{t`All channels`}</option>{CHANNELS.map(value => <option key={value} value={value}>{words(value)}</option>)}
        </select></label>
        <label className="grid gap-1 text-sm">{t`Destination`}<select className="desk-input" value={filters.destination} onChange={event => update("destination", event.target.value)}>
          <option value="">{t`All destinations`}</option>{destinations.data?.map(row => <option key={row.id} value={row.id}>{row.label} ({words(row.channel)})</option>)}
        </select></label>
        <label className="grid gap-1 text-sm">{t`Family`}<select className="desk-input" value={filters.feature} onChange={event => update("feature", event.target.value)}>
          <option value="">{t`All families`}</option>{Object.entries(FAMILIES()).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        <label className="grid gap-1 text-sm">{t`Event`}<input className="desk-input" maxLength={64} value={filters.event} onChange={event => update("event", event.target.value)} /></label>
      </div>{!dialogs ? target : null}
    </div> }}
    body={{ kind: "rows", rows: suppressed ? <SuppressionAdmin makerspaceId={makerspaceId} embedded dialogOpen={suppressOpen} onDialogClose={() => setSuppressOpen(false)} /> : <>
      {logs.data?.results.map(row => <ListRow key={`${row.kind}:${row.id}`} title={`${FAMILIES()[row.feature] ?? words(row.feature)} · ${words(row.event)}`}
        identity={{ kind: "icon", icon: row.channel === "email" ? "ArrowUpRight" : "Info", tone: "accent" }}
        meta={<span className="grid gap-1"><span>{words(row.channel)} · {row.destination_label || t`Personal devices`} {t` · ${row.attempts} attempts · `}<RelativeTime date={row.created_at} /></span>
          {row.error ? <span className="break-words text-danger">{row.error}</span> : null}</span>}
        right={<div className="flex items-center gap-3"><StatusPill label={statusLabel(row.status)} tone={row.status === "failed" ? "danger" : row.status === "sent" ? "success" : "neutral"} />
          {row.status === "failed" ? <button className="desk-button" aria-label={t`Retry failed delivery`} disabled={retry.isPending} onClick={() => retry.mutate(row)}>{t`Retry`}</button> : null}</div>} />)}
    </> }} pagination={suppressed ? undefined : { page, pageSize: 24, count: logs.data?.count ?? 0, onChange: setPage }}
    detail={<><div className="mt-4 grid gap-3">
      {test.data ? <p className="text-sm text-muted" role="status">{t`Test ${test.data.kind} #${test.data.id}: ${dialogs ? statusLabel(test.data.status) : test.data.status}. `}<a className="rounded-control font-semibold text-accent-ink underline underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" href={viewHref("deliveries")}>{t`View in log`}</a></p> : null}
      {retry.error || (!testOpen && test.error) ? <ErrorBlock error={(retry.error ?? test.error)!} /> : null}
    </div>
    <Modal open={testOpen} title={t`Send a test to…`} onClose={() => { if (!test.isPending) setTestOpen(false); }}>
      <form className="grid gap-4" onSubmit={event => { event.preventDefault(); test.mutate(); }}>
        {target}{destinationState}{test.error ? <ErrorBlock error={test.error} /> : null}
        <div className="flex flex-wrap justify-end gap-3"><button className="desk-button" type="button" disabled={test.isPending} onClick={() => setTestOpen(false)}>{t`Cancel`}</button>
          <button className="desk-button-primary" disabled={test.isPending}>{test.isPending ? <><BoxArt size={16} mono />{t`Sending…`}</> : t`Send test`}</button></div>
      </form>
    </Modal></>} />;
}
