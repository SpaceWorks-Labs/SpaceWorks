// CARD-STUDIO-2 in the whole designer: keyboard arrange, lock and zoom, the File menu's print-ready export, and the
// phone preview mode (quick edits only, no free-canvas dragging).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CardDesign } from "./cardTypes";
import { CardDesigner } from "./CardDesigner";
import { doc, layer } from "./designerFixtures.test";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), ...api }));

const document = doc([
  layer({ id: "band", kind: "band", name: "Band", x_mm: 0, y_mm: 0, w_mm: 85.6, h_mm: 10, fill: "#006E63" }),
  layer({ id: "name", kind: "data_field", name: "Name", field: "name", text: "{{name}}", colour: "#142C2A", x_mm: 5, y_mm: 15, w_mm: 30, h_mm: 6 }),
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
const canvas = () => screen.findByRole("group", { name: /front of the card/i });

beforeEach(() => { api.staffRequest.mockReset(); api.staffRequestBlob.mockReset(); window.localStorage.setItem("spaceworks.card-studio-mode", "advanced"); });
afterEach(() => vi.unstubAllGlobals());

describe("arrange from the keyboard", () => {
  it("sends the selection to the back and locks it", async () => {
    open();
    fireEvent.focus(within(await canvas()).getByRole("button", { name: /Name layer/ }));
    key("[", { ctrlKey: true, shiftKey: true });
    const order = within(await canvas()).getAllByRole("button", { name: /layer/ }).map((item) => item.getAttribute("aria-label"));
    expect(order[0]).toMatch(/^Name layer/);
    key("L", { ctrlKey: true, shiftKey: true });
    expect(within(await canvas()).getByRole("button", { name: /Name layer, locked/ })).toBeInTheDocument();
  });
});

describe("print-ready export", () => {
  it("asks the server for a PDF with the bleed and crop marks", async () => {
    api.staffRequestBlob.mockResolvedValue(new Blob(["%PDF"]));
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    open();
    await canvas();
    fireEvent.click(screen.getByRole("button", { name: "File" }));
    fireEvent.click(screen.getByRole("menuitem", { name: /Print-ready PDF/ }));
    await waitFor(() => expect(api.staffRequestBlob).toHaveBeenCalled());
    const [path, init] = api.staffRequestBlob.mock.calls[0];
    expect(path).toBe("/admin/card-designs/7/preview");
    expect(JSON.parse(init.body)).toEqual(expect.objectContaining({ format: "pdf", bleed_mm: 3, crop_marks: true, dpi: 300 }));
  });
});

describe("on a phone", () => {
  it("shows a preview with quick edits only", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("max-width: 639px"), media: query,
      addEventListener: () => undefined, removeEventListener: () => undefined }));
    open();
    await canvas();
    expect(screen.queryByRole("radiogroup", { name: "Design mode" })).toBeNull();
    expect(screen.getByRole("note")).toHaveTextContent("On a phone you see a preview");
    expect(within(await canvas()).getByRole("button", { name: /Name layer/ })).toHaveAttribute("tabindex", "-1");
  });
});
