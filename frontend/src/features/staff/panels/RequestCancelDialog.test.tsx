import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { RequestCancelDialog } from "./RequestCancelDialog";
import type { HardwareRequest } from "./Queues";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));

const row = { id: 12, status: "accepted", requester_username: "maya", requester_display: "Maya", items: [] } as unknown as HardwareRequest;

it("cancels with an optional reason and refreshes the queues", async () => {
  request.mockResolvedValue({ id: 12, status: "cancelled", closed_at: "2026-11-02T10:00:00Z" });
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const onClose = vi.fn();
  render(<QueryClientProvider client={client}><RequestCancelDialog row={row} makerspaceId={7} onClose={onClose} /></QueryClientProvider>);
  expect(screen.getByText(/go back on the shelf/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/Reason/), { target: { value: "Member asked" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/requests/12/cancel", { method: "POST", body: JSON.stringify({ reason: "Member asked" }) }));
  await waitFor(() => expect(onClose).toHaveBeenCalled());
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["accepted", 7] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["pending", 7] });
});

it("shows the server's refusal and keeps the dialog open", async () => {
  request.mockRejectedValue(new Error("Only pending or accepted requests can be cancelled."));
  const onClose = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><RequestCancelDialog row={row} makerspaceId={7} onClose={onClose} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Cancel request" }));
  expect(await screen.findByText("Only pending or accepted requests can be cancelled.")).toBeInTheDocument();
  expect(onClose).not.toHaveBeenCalled();
});
