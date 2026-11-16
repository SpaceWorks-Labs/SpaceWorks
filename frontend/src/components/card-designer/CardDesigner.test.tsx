import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CardDesign } from "./cardTypes";
import { CardDesigner } from "./CardDesigner";
import { doc, layer } from "./designerFixtures.test";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), ...api }));

const document = doc([
  layer({ id: "band", kind: "band", name: "Band", x_mm: 0, y_mm: 0, w_mm: 85.6, h_mm: 10, fill: "#006E63" }),
  layer({ id: "name", kind: "data_field", name: "Name", field: "name", text: "{{name}}", colour: "#142C2A", x_mm: 5, y_mm: 15, w_mm: 30, h_mm: 6 }),
  layer({ id: "qr", kind: "desk_qr", name: "QR", x_mm: 60, y_mm: 20, w_mm: 18, h_mm: 18 }),
]);
const design = { id: 7, domain: "member_cards", name: "Default", plan_id: null, title_id: null, programme_id: null,
  organization_id: null, event_id: null, ticket_type_id: null, target_label: "Space default", status: "published", document,
  revision: 4, published_revision: 4, published_at: "2026-11-01T10:00:00Z", has_unpublished_changes: false,
  pending_approval: null, last_review: null, needs_approval: false, can_approve: false, can_edit: true,
  updated_at: "2026-11-01T10:00:00Z" } as CardDesign;

function open() {
  api.staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === "/admin/card-designs/7" && (!init || !init.method)) return design;
    if (path === "/admin/card-designs/7" && init?.method === "PUT") return { ...design, revision: design.revision + 1 };
    return [];
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CardDesigner designId={7} canEdit title="Test design" /></QueryClientProvider>);
}
const key = (key: string, extra: Partial<KeyboardEventInit> = {}) => fireEvent.keyDown(window.document.body, { key, ...extra });
const canvasLayer = (name: RegExp) => within(screen.getByRole("group", { name: /front of the card/i })).getByRole("button", { name });

beforeEach(() => { api.staffRequest.mockReset(); window.localStorage.setItem("spaceworks.card-studio-mode", "advanced"); });

describe("card designer editing", () => {
  it("selects all, groups, and shows the group in the layer list", async () => {
    open();
    await screen.findByRole("group", { name: /front of the card/i });
    key("a", { ctrlKey: true });
    expect(screen.getByRole("heading", { name: "3 layers selected" })).toBeInTheDocument();
    key("g", { ctrlKey: true });
    fireEvent.click(screen.getByRole("button", { name: "Layers" }));
    expect(screen.getByRole("button", { name: "Name, group A" })).toBeInTheDocument();
    expect(canvasLayer(/QR layer, group A/)).toBeInTheDocument();
    key("g", { ctrlKey: true, shiftKey: true });
    expect(screen.getByRole("button", { name: "Name" })).toBeInTheDocument();
  });

  it("Shift-click in the layer list builds a selection; Escape clears it", async () => {
    open();
    await screen.findByRole("group", { name: /front of the card/i });
    fireEvent.click(screen.getByRole("button", { name: "Layers" }));
    fireEvent.click(screen.getByRole("button", { name: "Name" }));
    expect(screen.getByRole("heading", { name: "Name" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "QR" }), { shiftKey: true });
    expect(screen.getByRole("heading", { name: "2 layers selected" })).toBeInTheDocument();
    key("Escape");
    expect(screen.getByText(/select a layer on the card/i)).toBeInTheDocument();
  });

  it("copies, pastes, duplicates and deletes with the keyboard; undo puts it back", async () => {
    open();
    await screen.findByRole("group", { name: /front of the card/i });
    fireEvent.click(screen.getByRole("button", { name: "Layers" }));
    fireEvent.click(screen.getByRole("button", { name: "QR" }));
    key("c", { ctrlKey: true });
    key("v", { ctrlKey: true });
    key("d", { metaKey: true });
    expect(within(screen.getByRole("list", { name: /layers, top first/i })).getAllByRole("listitem")).toHaveLength(5);
    key("Delete");
    expect(within(screen.getByRole("list", { name: /layers, top first/i })).getAllByRole("listitem")).toHaveLength(4);
    key("z", { ctrlKey: true });
    expect(within(screen.getByRole("list", { name: /layers, top first/i })).getAllByRole("listitem")).toHaveLength(5);
  });

  it("aligns the selection from the toolbar and keeps locked layers still", async () => {
    open();
    await screen.findByRole("group", { name: /front of the card/i });
    fireEvent.click(screen.getByRole("button", { name: "Layers" }));
    fireEvent.click(screen.getByRole("button", { name: "Name" }));
    fireEvent.click(screen.getByRole("button", { name: "Align left edges to the card" }));
    expect(screen.getByRole("spinbutton", { name: /left/i })).toHaveValue(0);
  });

  it("lists preflight checks and opens the shortcuts dialog", async () => {
    open();
    await screen.findByRole("group", { name: /front of the card/i });
    fireEvent.click(screen.getByRole("button", { name: /^checks/i }));
    expect(screen.getByRole("heading", { name: "Checks before printing" })).toBeInTheDocument();
    key("?", { shiftKey: true });
    expect(await screen.findByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  });
});
