import { useEffect, useState } from "react";

import { ListRow, StatusPill } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { opsQueryState } from "./opsPresentation";
import { StructuredApiError } from "../../lib/api";
import { BookableSpaceForm } from "./BookableSpaceForm";
import { BookingDrawer } from "./BookingDrawer";
import { useBookableSpaces, useCreateBookableSpace } from "./bookingsApi";
import { useUrlListState } from "../../lib/useUrlListState";
import { ListViewControls } from "./ListViewControls";
import { useSearchParams } from "react-router-dom";
import { useQuickCreate } from "./quickCreate";

export function BookingsPanel({ makerspaceId, recurringEnabled = false }: { makerspaceId: number; recurringEnabled?: boolean }) {
  const list = useUrlListState({ q: "", ordering: "name", page: "1" });
  const { page, setPage } = list;
  const [params, setParams] = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  const [choosingBooking, setChoosingBooking] = useState(false);
  useQuickCreate("booking", () => setChoosingBooking(true));
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get("space")) || null);
  const linkedId = params.get("space");
  useEffect(() => { setSelectedId(Number(linkedId) || null); }, [linkedId]);
  const closeSelection = () => { setSelectedId(null); setParams((current) => { const next = new URLSearchParams(current); next.delete("space"); next.delete("booking"); return next; }); };
  const spaces = useBookableSpaces(makerspaceId, page, list.query);
  const create = useCreateBookableSpace(makerspaceId);
  const apiError = spaces.error instanceof StructuredApiError ? spaces.error : null;

  const unavailable = apiError?.status === 403 ? "Only Space Managers can manage bookings."
    : apiError?.status === 400 && apiError.body.module ? "The Bookings module is not enabled for this makerspace." : undefined;
  if (!unavailable && selectedId !== null) return <BookingDrawer recurringEnabled={recurringEnabled} key={selectedId}
    makerspaceId={makerspaceId} spaceId={selectedId} onClose={closeSelection} />;
  if (!unavailable && createOpen) return <BookableSpaceForm mode="create" makerspaceId={makerspaceId}
    onSubmit={payload => create.mutate(payload, { onSuccess: space => { setCreateOpen(false); setSelectedId(space.id); } })}
    pending={create.isPending} error={create.error?.message} submitLabel="Create space" onCancel={() => setCreateOpen(false)} />;
  return <ListLayout header={{ title: "Bookings",
    subtitle: choosingBooking ? "Choose a space below, then enter the booking details." : "Manage spaces, booking requests and public availability.",
    primary: unavailable ? undefined : { label: "New space", onClick: () => setCreateOpen(true) },
    secondary: unavailable ? undefined : { label: "New booking", onClick: () => setChoosingBooking(true) } }}
    state={unavailable ? { status: "ready" } : opsQueryState(spaces, "bookable spaces")}
    stats={[{ label: "Spaces", value: spaces.data?.count ?? 0 }]}
    filters={unavailable ? undefined : { toolbar: <ListViewControls state={list} makerspaceId={makerspaceId} entity="bookings" searchLabel="Search spaces"
      sorts={[["name", "Name"], ["-name", "Name descending"], ["kind", "Type"]]} /> }}
    filtered={Boolean(list.values.q)} isEmpty={Boolean(unavailable) || spaces.data?.results.length === 0}
    empty={{ message: unavailable ?? "No bookable spaces yet. Create one to start taking bookings.",
      action: unavailable ? undefined : { label: "New space", onClick: () => setCreateOpen(true) } }}
    filteredEmpty={{ message: "No spaces match your search. Try another name.", action: { label: "Clear filters", onClick: () => list.setFilter("q", "") } }}
    body={{ kind: "rows", rows: spaces.data?.results.map(space => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Calendar", tone: "info" }} onClick={() => setSelectedId(space.id)}
      meta={<>{space.kind.replace(/_/g, " ")} · {space.location || "No location label"}</>}
      right={<div className="flex flex-wrap items-center gap-2">
        <StatusPill label={space.approval_mode === "approve" ? "Staff approval" : "Instant"} tone="neutral" />
        <StatusPill label={space.is_public ? "Public" : "Private"} tone={space.is_public ? "success" : "neutral"} />
        <StatusPill label={space.is_active ? "Active" : "Inactive"} tone={space.is_active ? "success" : "neutral"} />
        <button className="desk-button" type="button" onClick={() => setSelectedId(space.id)}>View bookings</button>
      </div>} />) }}
    pagination={spaces.data ? { page, pageSize: 24, count: spaces.data.count, onChange: setPage } : undefined} />;
}
