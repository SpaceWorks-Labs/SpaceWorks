import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContainerDetail } from "./ContainerDetail";
import type { Container } from "./ContainersPanel";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));
vi.mock("../shelf/ShowOnShelf", () => ({ ShowOnShelf: ({ targetId }: { targetId: number }) => <p>shelf box {targetId}</p> }));
vi.mock("../WarrantySection", () => ({ WarrantySection: ({ hostId, disabled }: { hostId: number; disabled: boolean }) => <p>warranty asset {hostId} disabled={String(disabled)}</p> }));
vi.mock("./QrImage", () => ({ QrImage: ({ qrId, label }: { qrId: number; label: string }) => <p>qr {qrId} for {label}</p> }));
vi.mock("../../inventory/KitChecklist", () => ({ KitDefinitionEditor: ({ value, onChange }: { value: unknown[]; onChange: (v: unknown[]) => void }) =>
  <button type="button" onClick={() => onChange([...value, { key: "lid", label: "Lid", quantity: 1 }])}>kit editor {value.length}</button> }));

const container = { id: 5, code: "BX-5", label: "Soldering box", location: "Shelf A", is_active: true, kit_components: [] } as unknown as Container;
const contents = { products: [{ id: 1, name: "Solder", available_quantity: 3, tracking_mode: "quantity" }],
  assets: [{ id: 9, asset_tag: "AS-9", product: "Iron", status: "available" }], children: [{ id: 6, label: "Inner" }, { id: 7, label: "Other" }] };
const history = { scans: [{ id: "a", source: "box_scan", context: "issue", actor: 2, created_at: "2026-11-01T10:00:00Z" }, { id: "b", source: "qr", context: "", actor: null, created_at: "2026-11-02T10:00:00Z" }] };

let contentsResult: () => Promise<unknown>;
let historyResult: () => Promise<unknown>;
let moveError: Error | undefined;
let posts: Array<{ path: string; body: Record<string, unknown> }>;

function mount(props: Partial<Parameters<typeof ContainerDetail>[0]> = {}, tab = "") {
  const onClose = vi.fn();
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/admin/containers${tab}`]}>
      <ContainerDetail container={container} makerspaceId={7} canEditInventory kitEnabled={false} onClose={onClose} {...props} /></MemoryRouter></QueryClientProvider>);
  return { onClose, ...view };
}
beforeEach(() => {
  contentsResult = async () => contents; historyResult = async () => history; moveError = undefined; posts = [];
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ path, body: JSON.parse(String(init.body)) });
      if (path.endsWith("/move") && moveError) throw moveError;
      return path.includes("/qr") ? { id: 55 } : {};
    }
    if (path.endsWith("/contents")) return contentsResult();
    if (path.endsWith("/history")) return historyResult();
    return {};
  });
});

describe("contents tab", () => {
  it("shows identity, tabs, products, assets and sub-containers", async () => {
    mount();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(await screen.findByText("Solder - 3 available")).toBeInTheDocument();
    expect(screen.getByText("AS-9")).toBeInTheDocument();
    expect(screen.getByText("Sub-containers: Inner, Other")).toBeInTheDocument();
    expect(screen.getByText("shelf box 5")).toBeInTheDocument();
    expect(request).not.toHaveBeenCalledWith("/admin/containers/5/history");
    expect(screen.getByRole("link", { name: "History" })).toHaveAttribute("href", expect.stringContaining("containerTab=history"));
  });
  it("shows the empty message twice (no products, no assets) and no sub-container line", async () => {
    contentsResult = async () => ({ products: [], assets: [], children: [] });
    mount();
    await waitFor(() => expect(screen.getAllByText("This container is empty.")).toHaveLength(2));
    expect(screen.queryByText(/Sub-containers/)).toBeNull();
  });
  it("shows a load error with retry, and does not claim the container is empty", async () => {
    contentsResult = async () => { throw new Error("Contents down"); };
    mount();
    expect(await screen.findAllByText(/Couldn't load container contents|Contents down/)).not.toHaveLength(0);
    expect(screen.queryByText("This container is empty.")).toBeNull();
  });
  it("marks an inactive container as Inactive", async () => {
    mount({ container: { ...container, is_active: false } as Container });
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    await screen.findByText("Solder - 3 available");
  });
  it("falls back to the id when the container has no code", async () => {
    mount({ container: { ...container, code: undefined, location: undefined } as unknown as Container });
    await screen.findByText("Solder - 3 available");
    expect(screen.getAllByText(/5/).length).toBeGreaterThan(0);
  });
});

describe("asset QR rows and warranty", () => {
  it("loads the unit QR through a POST, then shows the image and the shown label", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Show QR" }));
    expect(await screen.findByText("qr 55 for AS-9")).toBeInTheDocument();
    expect(posts[0].path).toBe("/admin/assets/9/qr");
    expect(screen.getByRole("button", { name: "QR shown" })).toBeInTheDocument();
  });
  it("shows the QR failure message", async () => {
    mount();
    request.mockImplementation(async (path: string, init?: RequestInit) => {
      if (init?.method === "POST") throw new Error("QR service down");
      return path.endsWith("/contents") ? contents : history;
    });
    fireEvent.click(await screen.findByRole("button", { name: "Show QR" }));
    expect(await screen.findByText("QR service down")).toBeInTheDocument();
  });
  it("toggles warranty through the actions menu, read-only without edit rights", async () => {
    mount({ canEditInventory: false });
    fireEvent.click(await screen.findByRole("button", { name: "Actions for AS-9" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Warranty" }));
    expect(await screen.findByText("warranty asset 9 disabled=true")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Actions for AS-9" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Hide warranty" }));
    expect(screen.queryByText(/warranty asset 9/)).toBeNull();
  });
  it("hides the warranty menu when the warranty module is off", async () => {
    mount({ warrantyEnabled: false });
    await screen.findByText("AS-9");
    expect(screen.queryByRole("button", { name: "Actions for AS-9" })).toBeNull();
  });
});

describe("history tab", () => {
  it("lists scans with their context and handover wording, and does not fetch contents", async () => {
    mount({}, "?containerTab=history");
    expect(await screen.findByText(/issue · reviewed handover/)).toBeInTheDocument();
    expect(screen.getByText(/Scan · QR scan/)).toBeInTheDocument();
    expect(request).not.toHaveBeenCalledWith("/admin/containers/5/contents");
  });
  it("shows the empty state when there are no scans", async () => {
    historyResult = async () => ({ scans: [] });
    mount({}, "?containerTab=history");
    expect(await screen.findByText("No scans yet.")).toBeInTheDocument();
  });
  it("shows the history error instead of the empty state", async () => {
    historyResult = async () => { throw new Error("History down"); };
    mount({}, "?containerTab=history");
    expect(await screen.findAllByText(/History down|scan history/)).not.toHaveLength(0);
    expect(screen.queryByText("No scans yet.")).toBeNull();
  });
});

describe("details tab", () => {
  const detailsTab = "?containerTab=details";
  it("shows no save bar until something changes, then saves the trimmed values and discards on request", async () => {
    mount({}, detailsTab);
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "  New label  " } });
    fireEvent.change(screen.getByLabelText("Location"), { target: { value: " Shelf B " } });
    fireEvent.click(screen.getByLabelText("Active"));
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByLabelText("Label")).toHaveValue("Soldering box");
    expect(screen.getByLabelText("Location")).toHaveValue("Shelf A");
    expect(screen.getByLabelText("Active")).toBeChecked();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "  New label  " } });
    fireEvent.change(screen.getByLabelText("Location"), { target: { value: " Shelf B " } });
    fireEvent.click(screen.getByLabelText("Active"));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].path).toBe("/admin/containers/5/move");
    expect(posts[0].body).toEqual({ label: "New label", location: "Shelf B", is_active: false });
  });
  it("cannot save a blank label", () => {
    mount({}, detailsTab);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
  it("shows the server error when the move fails and keeps the edits", async () => {
    moveError = new Error("Label already used");
    mount({}, detailsTab);
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Clash" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Label already used")).toBeInTheDocument();
    expect(screen.getByLabelText("Label")).toHaveValue("Clash");
  });
  it("includes kit components only when the kit module is on, and a kit change alone makes the form dirty", async () => {
    const { unmount } = mount({ kitEnabled: false }, detailsTab);
    expect(screen.queryByRole("button", { name: /kit editor/ })).toBeNull();
    unmount();
    mount({ kitEnabled: true }, detailsTab);
    fireEvent.click(screen.getByRole("button", { name: "kit editor 0" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body).toMatchObject({ kit_components: [{ key: "lid", label: "Lid", quantity: 1 }] });
  });
  it("closes the drawer", async () => {
    const { onClose } = mount({}, detailsTab);
    const dialog = screen.queryByRole("dialog");
    const close = within(dialog ?? document.body).getAllByRole("button", { name: /close/i })[0];
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalled();
  });
});
