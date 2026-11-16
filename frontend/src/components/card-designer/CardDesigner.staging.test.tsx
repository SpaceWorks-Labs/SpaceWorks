import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { CardDesigner } from "./CardDesigner";
import type { CardDesign } from "./cardTypes";

const { staffRequest, staffRequestBlob } = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest, staffRequestBlob };
});

const side = { page_width_mm: 85.6, page_height_mm: 53.98, background: { kind: "colour" as const, colour: "#FFFFFF" }, layers: [] };
const design: CardDesign = {
  id: 9, domain: "member_cards", name: "", plan_id: null, title_id: null, programme_id: null, organization_id: null, event_id: null,
  ticket_type_id: null, target_label: "Space default", status: "draft", revision: 1, published_revision: null, published_at: null,
  has_unpublished_changes: true, pending_approval: null, last_review: null, needs_approval: false, can_approve: true, can_edit: true,
  updated_at: "2026-11-01T00:00:00Z",
  document: { version: 2, stock: "cr80-landscape", back_enabled: false, mono: false,
    watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: -30, colour: "#006E63" }, front: side, back: side },
};

function renderDesigner(canEdit = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><CardDesigner designId={9} canEdit={canEdit} /></QueryClientProvider>);
}

beforeEach(() => {
  window.localStorage.setItem("spaceworks.card-studio-mode", "advanced");
  staffRequest.mockReset();
  staffRequestBlob.mockReset();
  staffRequest.mockImplementation((path: string, options?: RequestInit) => {
    if (path === "/admin/card-designs/9" && options?.method === "PUT") {
      const body = JSON.parse(String(options.body));
      return Promise.resolve({ ...design, revision: body.revision + 1, document: body.document });
    }
    if (path === "/admin/card-designs/9") return Promise.resolve(design);
    if (path.endsWith("/templates")) return Promise.resolve([{ key: "classic", label: "Classic", document: design.document }]);
    if (path.includes("/fonts")) return Promise.resolve({ count: 0, results: [] });
    if (path.endsWith("/publish")) return Promise.resolve({ ...design, status: "published", published_at: "2026-11-02T00:00:00Z" });
    return Promise.resolve({});
  });
});

describe("CardDesigner", () => {
  it("adds a layer, autosaves the draft with the current revision, and publishes", async () => {
    const { container } = renderDesigner();
    fireEvent.click(await screen.findByRole("button", { name: "Text" }));
    expect(screen.getByRole("button", { name: /^text layer/i })).toBeVisible();
    expect(screen.getByText("Unsaved changes")).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/card-designs/9",
      expect.objectContaining({ method: "PUT" })), { timeout: 3000 });
    const put = staffRequest.mock.calls.find(([, options]) => options?.method === "PUT")!;
    const body = JSON.parse(String(put[1].body));
    expect(body.revision).toBe(1);
    expect(body.document.front.layers[0]).toMatchObject({ kind: "text", text: "Your text" });
    fireEvent.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/card-designs/9/publish", expect.objectContaining({ method: "POST" })));
    await expectNoA11yViolations(container);
  });

  it("undoes an added layer", async () => {
    renderDesigner();
    fireEvent.click(await screen.findByRole("button", { name: "Shape" }));
    expect(screen.getByRole("button", { name: /^shape layer/i })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(screen.queryByRole("button", { name: /^shape layer/i })).toBeNull();
  });

  it("is read-only without edit rights", async () => {
    renderDesigner(false);
    expect(await screen.findByText("You can view this design but not change it.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
  });
});
