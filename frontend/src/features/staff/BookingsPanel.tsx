import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { EmptyState, ListRow, Modal, StatusPill } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { opsQueryState } from "./opsPresentation";
import { StructuredApiError } from "../../lib/api";
import { BookableSpaceForm } from "./BookableSpaceForm";
import { MakerspaceBookingRulesSettings } from "./MakerspaceBookingRulesSettings";
import { BookingDrawer } from "./BookingDrawer";
import { useBookableSpaces, useCreateBookableSpace } from "./bookingsApi";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { useSearchParams } from "react-router-dom";
import { useQuickCreate } from "./quickCreate";
import { useDomainSettingsDialog } from "./useDomainSettingsDialog";
import { BookingQueuePanel } from "./BookingQueuePanel";
import { BookingIssuesList } from "./BookingIssuesList";
import { useBookingIssues, type QueueStatus } from "./bookingQueueApi";

type PanelView = "requests" | "spaces" | "issues";
const QUEUE_STATUSES: QueueStatus[] = ["pending", "confirmed", "rejected", "cancelled", "completed", "no_show", "all"];

export function BookingsPanel({ makerspaceId, recurringEnabled = false }: { makerspaceId: number; recurringEnabled?: boolean }) {
  const queryClient = useQueryClient();
  const list = useUrlListState({ q: "", ordering: "name", page: "1" });
  const { page, setPage } = list;
  const [params, setParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const [choosingBooking, setChoosingBooking] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  useQuickCreate("booking", () => setChoosingBooking(true));
  const domainSettings = useDomainSettingsDialog(makerspaceId, "bookings");
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get("space")) || null);
  // "New booking" picks a space, then opens that space with its booking form already up.
  const [bookingSpaceId, setBookingSpaceId] = useState<number | null>(null);
  // The Requests queue is the landing view; a dashboard link `?status=pending` lands on it filtered.
  const view: PanelView = (["spaces", "issues"] as const).find(value => value === params.get("view")) ?? "requests";
  const queueStatus: QueueStatus = QUEUE_STATUSES.find(value => value === params.get("status")) ?? "pending";
  const setParam = (key: string, value: string | null) => setParams(current => {
    const next = new URLSearchParams(current); if (value) next.set(key, value); else next.delete(key); return next;
  });
  const openIssues = useBookingIssues(makerspaceId, "open");
  const linkedId = params.get("space");
  useEffect(() => { setSelectedId(Number(linkedId) || null); }, [linkedId]);
  const closeSelection = () => { setSelectedId(null); setBookingSpaceId(null); setParams((current) => { const next = new URLSearchParams(current); next.delete("space"); next.delete("booking"); return next; }); };
  const spaces = useBookableSpaces(makerspaceId, page, list.query);
  const create = useCreateBookableSpace(makerspaceId);
  const apiError = spaces.error instanceof StructuredApiError ? spaces.error : null;

  const unavailable = apiError?.status === 403 ? "Booking management requires the Booking Manager role or a resource permission."
    : apiError?.status === 400 && apiError.body.module ? "The Bookings module is not enabled for this makerspace." : undefined;
  if (!unavailable && selectedId !== null) return <BookingDrawer recurringEnabled={recurringEnabled} key={selectedId}
    makerspaceId={makerspaceId} spaceId={selectedId} onClose={closeSelection} initialCreateOpen={bookingSpaceId === selectedId} />;
  if (!unavailable && createOpen) return <BookableSpaceForm mode="create" makerspaceId={makerspaceId}
    onSubmit={payload => create.mutate(payload, { onSuccess: space => { setCreateOpen(false); setSelectedId(space.id);
      void queryClient.invalidateQueries({ queryKey: ["booking-rule-spaces", makerspaceId] }); } })}
    pending={create.isPending} error={create.error?.message} submitLabel="Create space" onCancel={() => setCreateOpen(false)} />;
  const activeSpaces = spaces.data?.results.filter(space => space.is_active) ?? [];
  const chooseSpace = (spaceId: number) => { setChoosingBooking(false); setBookingSpaceId(spaceId); setSelectedId(spaceId); };
  const openBooking = (spaceId: number, bookingId: number) => setParams(current => {
    const next = new URLSearchParams(current);
    next.set("space", String(spaceId)); next.set("booking", String(bookingId)); next.set("bookingTab", "requests");
    return next;
  });
  const tabs = unavailable ? undefined : [
    { key: "requests", label: "Requests" }, { key: "spaces", label: "Spaces", count: spaces.data?.count },
    { key: "issues", label: "Issues", count: openIssues.data?.open_count },
  ];
  const queueBody = view === "requests" ? <BookingQueuePanel makerspaceId={makerspaceId} status={queueStatus}
      onStatus={status => setParam("status", status === "pending" ? null : status)} onOpenBooking={booking => openBooking(booking.space_id, booking.id)} />
    : view === "issues" ? <BookingIssuesList makerspaceId={makerspaceId} onOpenBooking={issue => openBooking(issue.space_id, issue.booking_id)} />
    : null;
  return <><ListLayout header={{ title: "Bookings",
    subtitle: "Manage spaces, booking requests and public availability.",
    primary: unavailable ? undefined : { label: "New space", onClick: () => setCreateOpen(true) },
    secondary: unavailable ? undefined : { label: "New booking", onClick: () => setChoosingBooking(true) },
    // Booking rules are keyed on manage_bookings, so a Booking Manager edits them here, not in space settings.
    overflow: unavailable ? undefined : [{ label: "Booking rules", icon: "Settings", onClick: () => setRulesOpen(true) }, ...domainSettings.actions] }}
    tabs={tabs} activeTab={view} onTabChange={key => setParams(current => {
      const next = new URLSearchParams(current); next.delete("status"); if (key === "requests") next.delete("view"); else next.set("view", key); return next;
    })}
    state={unavailable || queueBody ? { status: "ready" } : opsQueryState(spaces, "bookable spaces")}
    stats={[{ label: "Spaces", value: spaces.data?.count ?? 0 }]}
    filters={unavailable || queueBody ? undefined : { toolbar: <ListViewControls state={list} makerspaceId={makerspaceId} entity="bookings" searchLabel="Search spaces"
      sorts={[["name", "Name"], ["-name", "Name descending"], ["kind", "Type"]]} /> }}
    filtered={!queueBody && Boolean(list.values.q)} isEmpty={Boolean(unavailable) || (!queueBody && spaces.data?.results.length === 0)}
    empty={{ message: unavailable ?? "No bookable spaces yet. Create one to start taking bookings.",
      action: unavailable ? undefined : { label: "New space", onClick: () => setCreateOpen(true) } }}
    filteredEmpty={{ message: "No spaces match your search. Try another name.", action: { label: "Clear filters", onClick: () => list.setFilter("q", "") } }}
    body={{ kind: "rows", rows: queueBody ?? spaces.data?.results.map(space => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Calendar", tone: "info" }} onClick={() => setSelectedId(space.id)}
      meta={<>{space.kind.replace(/_/g, " ")} · {space.location || "No location label"}</>}
      right={<div className="flex flex-wrap items-center gap-2">
        <StatusPill label={space.approval_mode === "approve" ? "Staff approval" : "Instant"} tone="neutral" />
        <StatusPill label={space.is_public ? "Public" : "Private"} tone={space.is_public ? "success" : "neutral"} />
        <StatusPill label={space.is_active ? "Active" : "Inactive"} tone={space.is_active ? "success" : "neutral"} />
        <button className="desk-button" type="button" onClick={() => setSelectedId(space.id)}>View bookings</button>
      </div>} />) }}
    pagination={spaces.data && !queueBody ? { page, pageSize: 24, count: spaces.data.count, onChange: setPage } : undefined} />
    <Modal open={choosingBooking && !unavailable} title="New booking" onClose={() => setChoosingBooking(false)}>
      <div className="grid gap-3">
        <p className="text-sm text-muted">Choose the space to book.{spaces.data?.next ? " Search the list to find a space on another page." : ""}</p>
        {activeSpaces.length ? activeSpaces.map(space => <ListRow key={space.id} title={space.name} identity={{ kind: "icon", icon: "Calendar", tone: "info" }}
          meta={space.location || "No location label"} onClick={() => chooseSpace(space.id)}
          right={<button className="desk-button" type="button" onClick={() => chooseSpace(space.id)}>Book this space</button>} />)
          : <EmptyState message="No active spaces on this page. Create a space before taking bookings." />}
      </div>
    </Modal>
    <Modal open={rulesOpen && !unavailable} title="Booking rules" size="xl" onClose={() => setRulesOpen(false)}>
      <MakerspaceBookingRulesSettings makerspace={{ id: makerspaceId }} />
    </Modal>
    {domainSettings.dialog}
  </>;
}
