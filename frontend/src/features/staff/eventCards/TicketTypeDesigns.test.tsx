import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<object>(), staffRequest }));
vi.mock("../../../components/card-designer/CardDesigner", () => ({
  CardDesigner: ({ designId, title }: { designId: number; title: string }) => <p>{title} #{designId}</p>,
}));

import { TicketTypeDesigns } from "./TicketTypeDesigns";

const eventDesign = { id: 10, can_edit: true } as never;
const wrap = (ui: import("react").ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>;

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string) => {
    if (path.startsWith("/admin/events/7/ticket-types/")) return { results: [{ id: 3, name: "VIP" }, { id: 4, name: "Student" }], next: null };
    if (path === "/admin/events/7/card-designs?ticket_type=3") return { event_ticket: { id: 33, can_edit: true } };
    throw new Error(`unexpected ${path}`);
  });
});

it("edits the event's ticket design by default and a ticket type's own design when picked (parity D17)", async () => {
  render(wrap(<TicketTypeDesigns eventId={7} eventDesign={eventDesign} ticketTypesOn />));
  expect(screen.getByText("Ticket design #10")).toBeVisible();
  const picker = await screen.findByRole("combobox", { name: /Design for/ });
  fireEvent.change(picker, { target: { value: "3" } });
  expect(await screen.findByText("Ticket design: VIP #33")).toBeVisible();
  expect(screen.getByText("Holders of VIP get this design instead of the event's.")).toBeVisible();
  fireEvent.change(picker, { target: { value: "" } });
  expect(screen.getByText("Ticket design #10")).toBeVisible();
});

it("shows no picker while ticket types are off", () => {
  render(wrap(<TicketTypeDesigns eventId={7} eventDesign={eventDesign} ticketTypesOn={false} />));
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(staffRequest).not.toHaveBeenCalled();
});
