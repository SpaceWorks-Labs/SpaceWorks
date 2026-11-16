import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api/errors";
import { ScannerPanel } from "./ScannerPanel";
import type { Makerspace } from "./shared";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
vi.mock("../../../components/ui/QrScanner", () => ({ default: ({ onScan }: { onScan: (value: string) => void }) => <button onClick={() => onScan("opaque-possession-token")}>Simulate scan</button> }));
const notFound = () => { throw new StructuredApiError(404, { detail: "Not found." }); };
const linked = { qr: { id: 9, payload: "x", status: "active", makerspace_id: 7, source: "external" }, target: { id: 4, type: "product", name: "Drill" }, created: true };
function renderPanel() {
 render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ScannerPanel makerspace={{ id: 7 } as Makerspace} makerspaces={[]} isSuperadmin={false} /></QueryClientProvider>);
}
function scan() {
 fireEvent.click(screen.getByRole("button", { name: "Start scanning" }));
 fireEvent.click(screen.getByRole("button", { name: "Simulate scan" }));
}
function me(actions: string[]) { return { makerspaces: [{ id: 7, actions }] }; }
beforeEach(() => { request.mockReset(); });

it("starts the camera explicitly and never echoes its possession token into manual entry", async () => {
 request.mockImplementation(async path => path === "/auth/me" ? { makerspaces: [] } : { qr: { id: 3, payload: "opaque-possession-token", status: "active", makerspace_id: 7 }, target: { id: 4, type: "product", name: "Drill" }, allowed_actions: [] });
 renderPanel();
 expect(screen.queryByRole("button", { name: "Simulate scan" })).not.toBeInTheDocument();
 scan();
 await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/qr/resolve", { method: "POST", body: JSON.stringify({ payload: "opaque-possession-token", makerspace_id: 7 }) }));
 expect(await screen.findByText("Product: Drill")).toBeInTheDocument();
 expect(screen.getByLabelText("QR payload")).toHaveValue("");
 expect(screen.queryByText(/opaque-possession-token/)).not.toBeInTheDocument();
 expect(screen.queryByRole("button", { name: "Rename & rebind" })).not.toBeInTheDocument();
});

it("creates a new item for an unrecognized code and links the code when it is saved", async () => {
 let registered = false;
 request.mockImplementation(async (path: string) => {
  if (path === "/auth/me") return me(["manage_qr", "edit_inventory"]);
  if (path === "/admin/qr/external") { registered = true; return linked; }
  if (path === "/admin/qr/resolve") return registered ? { ...linked, allowed_actions: [] } : notFound();
  return [];
 });
 renderPanel();
 scan();
 expect(await screen.findByText("This QR code isn't linked to anything yet")).toBeInTheDocument();
 expect(screen.getByLabelText("Scanned code")).toHaveValue("opaque-possession-token");
 fireEvent.click(screen.getByRole("button", { name: "Create new item" }));
 fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Drill" } });
 fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "2" } });
 fireEvent.click(screen.getByRole("button", { name: "Save item and link code" }));
 await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/qr/external", { method: "POST", body: JSON.stringify({ makerspace_id: 7, value: "opaque-possession-token", create_product: { name: "Drill", total_quantity: 2, available_quantity: 2, tracking_mode: "quantity" } }) }));
 expect(await screen.findByText("Product: Drill")).toBeInTheDocument();
 expect(screen.getByText("Code linked.")).toBeInTheDocument();
});

it("links an unrecognized code to an existing item only after confirmation", async () => {
 request.mockImplementation(async (path: string) => {
  if (path === "/auth/me") return me(["manage_qr"]);
  if (path === "/admin/qr/resolve") return notFound();
  if (String(path).startsWith("/admin/makerspace/7/inventory")) return { results: [{ id: 4, name: "Drill", tracking_mode: "quantity" }] };
  if (path === "/admin/qr/external") return linked;
  return [];
 });
 renderPanel();
 scan();
 await screen.findByText("This QR code isn't linked to anything yet");
 expect(screen.queryByRole("button", { name: "Create new item" })).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole("button", { name: "Link to existing item" }));
 await screen.findByRole("option", { name: "Drill" });
 fireEvent.change(screen.getByLabelText("Item"), { target: { value: "4" } });
 fireEvent.click(screen.getByRole("button", { name: "Link code" }));
 expect(screen.getByText("Link this code to Drill? Existing links are never replaced.")).toBeInTheDocument();
 expect(request).not.toHaveBeenCalledWith("/admin/qr/external", expect.anything());
 fireEvent.click(screen.getByRole("button", { name: "Confirm link" }));
 await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/qr/external", { method: "POST", body: JSON.stringify({ makerspace_id: 7, value: "opaque-possession-token", product_id: 4 }) }));
});

it("shows the item an already-linked code belongs to and keeps that link", async () => {
 request.mockImplementation(async (path: string) => {
  if (path === "/auth/me") return me(["manage_qr"]);
  if (path === "/admin/qr/resolve") return notFound();
  if (String(path).startsWith("/admin/makerspace/7/inventory")) return { results: [{ id: 5, name: "Saw", tracking_mode: "quantity" }] };
  if (path === "/admin/qr/external") throw new StructuredApiError(409, { code: "already_assigned", detail: "This QR code is already linked. The existing link was kept.", target: { id: 4, type: "product", name: "Drill" } });
  return [];
 });
 renderPanel();
 scan();
 fireEvent.click(await screen.findByRole("button", { name: "Link to existing item" }));
 await screen.findByRole("option", { name: "Saw" });
 fireEvent.change(screen.getByLabelText("Item"), { target: { value: "5" } });
 fireEvent.click(screen.getByRole("button", { name: "Link code" }));
 fireEvent.click(screen.getByRole("button", { name: "Confirm link" }));
 expect(await screen.findByText("This QR code is already linked. The existing link was kept.")).toBeInTheDocument();
 expect(screen.getByText("Linked to Product: Drill")).toBeInTheDocument();
});

it("never offers registration to staff without QR management", async () => {
 request.mockImplementation(async (path: string) => {
  if (path === "/auth/me") return me(["view_inventory"]);
  if (path === "/admin/qr/resolve") return notFound();
  return [];
 });
 renderPanel();
 scan();
 expect(await screen.findByText("Not found.")).toBeInTheDocument();
 expect(screen.queryByText("This QR code isn't linked to anything yet")).not.toBeInTheDocument();
});
