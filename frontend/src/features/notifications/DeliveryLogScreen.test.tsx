import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DeliveryLogScreen } from "./DeliveryLogScreen";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request }));
beforeEach(() => {
  request.mockReset();
  request.mockImplementation((url: string, options?: { method?: string }) => {
    if (url.endsWith("/delivery-test")) return Promise.resolve({ kind: "email", id: 17, status: "pending" });
    if (options?.method) return Promise.resolve({});
    if (url.includes("notification-destinations")) return Promise.resolve([]);
    if (url.includes("email-suppressions")) return Promise.resolve({ count: 1, results: [{ id: 3, reason: "bounce", address_hash: "private-hash", created_at: "2026-10-10T00:00:00Z" }] });
    return Promise.resolve({ count: 1, results: [{ id: 9, kind: "email", channel: "email", feature: "members", event: "joined", destination_label: "Member", status: "failed", attempts: 2, retry_generation: 7, error: "SMTP unavailable", created_at: "2026-10-10T00:00:00Z" }] });
  });
});
function open(url = "/admin/email-logs") {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><DeliveryLogScreen makerspaceId={7} /></MemoryRouter>
  </QueryClientProvider>);
}
it("retries the selected failed delivery with its generation", async () => {
  open();
  fireEvent.click(await screen.findByRole("button", { name: "Retry failed delivery" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/integrations/makerspace/7/delivery-logs/email/9/retry", {
    method: "POST", body: JSON.stringify({ generation: 7 }),
  }));
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});
it("opens suppressions from a deep link and confirms removal before deleting", async () => {
  open("/admin/email-logs?delivery_view=suppression");
  fireEvent.click(await screen.findByRole("button", { name: "Remove suppression" }));
  expect(request.mock.calls.filter(call => call[1]?.method === "DELETE")).toHaveLength(0);
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove suppression" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/integrations/makerspace/7/email-suppressions/3", { method: "DELETE" }));
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});

it("opens a routed target dialog, submits the selected active destination and keeps the result visible", async () => {
  const fallback = request.getMockImplementation()!;
  request.mockImplementation((url: string, options?: { method?: string }) => url.includes("notification-destinations") ? Promise.resolve([
    { id: 5, label: "Workshop", channel: "slack", is_active: true }, { id: 6, label: "Disabled room", channel: "slack", is_active: false },
  ]) : fallback(url, options));
  open();
  fireEvent.click(screen.getByRole("button", { name: "Send test" }));
  const dialog = within(screen.getByRole("dialog"));
  await dialog.findByRole("option", { name: "Workshop (Slack)" });
  expect(dialog.queryByRole("option", { name: /disabled room/i })).toBeNull();
  expect(request.mock.calls.filter(call => call[1]?.method === "POST")).toHaveLength(0);
  fireEvent.change(dialog.getByRole("combobox", { name: "Test target" }), { target: { value: "5" } });
  fireEvent.click(dialog.getByRole("button", { name: "Send test" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/integrations/makerspace/7/delivery-test", {
    method: "POST", body: JSON.stringify({ destination_id: 5 }),
  }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(await screen.findByRole("status")).toHaveTextContent("Test email #17: Queued");
  expect(screen.getByRole("link", { name: "View in log" })).toHaveAttribute("href", "?delivery_view=deliveries");
});
it("retains immediate default tests for existing non-router embedders", async () => {
  render(<QueryClientProvider client={new QueryClient()}><DeliveryLogScreen makerspaceId={7} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Send test" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/integrations/makerspace/7/delivery-test", { method: "POST", body: "{}" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(await screen.findByRole("status")).toHaveTextContent("Test email #17: pending");
});
it("counts only visible page failures and humanizes rows, status chips and family labels", async () => {
  const fallback = request.getMockImplementation()!;
  request.mockImplementation(async (url: string, options?: { method?: string }) => {
    const result = await fallback(url, options);
    return url.includes("delivery-logs?") ? { ...result, count: 245 } : result;
  });
  open();
  expect(await screen.findByText("1 delivery failed on this page.")).toBeInTheDocument();
  expect(screen.getByText("Members \u00b7 Joined")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Suppressed addresses" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Show failed/ }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/integrations/makerspace/7/delivery-logs?page=1&status=failed"));
  fireEvent.click(screen.getByRole("button", { name: /^Filters/ }));
  expect(screen.getByRole("radio", { name: "Failed" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("option", { name: "Hardware" })).toHaveValue("hardware_requests");
});
it("keeps a failed test in its dialog for retry", async () => {
  const fallback = request.getMockImplementation()!;
  request.mockImplementation((url: string, options?: { method?: string }) => url.endsWith("/delivery-test") ? Promise.reject(new Error("Destination unavailable")) : fallback(url, options));
  open();
  fireEvent.click(screen.getByRole("button", { name: "Send test" }));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Send test" }));
  expect(await within(screen.getByRole("dialog")).findByText("Destination unavailable")).toBeInTheDocument();
});
it("shows a removable chip for each active filter and clears them", async () => {
  open();
  fireEvent.click(await screen.findByRole("button", { name: /Show failed/ }));
  const chip = await screen.findByRole("button", { name: "Remove status: Failed" });
  fireEvent.click(chip);
  await waitFor(() => expect(screen.queryByRole("button", { name: "Remove status: Failed" })).toBeNull());
});
