import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../lib/api";
import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { ScannerPage } from "./ScannerPage";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));
vi.mock("../../components/ui/QrScanner", () => ({ default: ({ onScan }: { onScan: (value: string) => void }) =>
  <button onClick={() => onScan("qr:camera")}>Read camera label</button> }));
beforeEach(() => { vi.clearAllMocks(); setRouteSessionContext("person"); });
afterEach(() => setRouteSessionContext("person"));
function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><ScannerPage /></QueryClientProvider>);
}
it("resolves a manual label using the existing endpoint and resets the readable result", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ target: { type: "asset", id: 3, product: "Multimeter", asset_tag: "MM-3", status: "issued" }, allowed_actions: ["return_asset"] });
  const { container } = show();
  expect(container.querySelectorAll("h1")).toHaveLength(1);
  fireEvent.change(screen.getByRole("searchbox", { name: "QR payload" }), { target: { value: "  qr:manual  " } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  await screen.findByRole("heading", { name: "Multimeter" });
  expect(staffRequest).toHaveBeenCalledWith("/admin/qr/resolve", { method: "POST", body: JSON.stringify({ payload: "qr:manual" }) }, "person");
  expect(screen.getByText("Return asset")).toBeVisible();
  expect(container.querySelector("pre")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Next scan" }));
  await waitFor(() => expect(screen.queryByRole("heading", { name: "Multimeter" })).toBeNull());
});
it("starts the camera only on intent and sends decoded labels through the same mutation", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ target: { type: "box", label: "Box B-04", code: "B-04" }, allowed_actions: [] });
  show();
  expect(screen.queryByRole("button", { name: "Read camera label" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Start scanning" }));
  fireEvent.click(screen.getByRole("button", { name: "Read camera label" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/qr/resolve", { method: "POST", body: JSON.stringify({ payload: "qr:camera" }) }, "person"));
  await screen.findByRole("heading", { name: "Box B-04" });
});
it("keeps a refused label recoverable without dropping its payload", async () => {
  vi.mocked(staffRequest).mockRejectedValueOnce(new Error("This label was revoked.")).mockResolvedValueOnce({ target: { name: "Tool" }, allowed_actions: [] });
  show();
  fireEvent.change(screen.getByRole("searchbox", { name: "QR payload" }), { target: { value: "qr:retry" } });
  fireEvent.click(screen.getByRole("button", { name: "Find" }));
  await screen.findByRole("heading", { name: "Couldn't resolve this label" });
  expect(screen.getByText("This label was revoked.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByRole("heading", { name: "Tool" });
  expect(staffRequest).toHaveBeenCalledTimes(2);
});

