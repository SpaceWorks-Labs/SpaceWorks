import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { WhatsAppApprovalRefresh } from "./WhatsAppApprovalRefresh";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
beforeEach(() => { staffRequest.mockReset(); });
const binding = { event: "notification_opt_in", audience: "member", locale: "en", template_name: "HX123", variables: ["code"], approved: true };
function mount(disabled = false) {
  const refreshed = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}><WhatsAppApprovalRefresh makerspaceId={8}
    disabled={disabled} onRefresh={refreshed} /></QueryClientProvider>);
  return refreshed;
}

it("refreshes saved bindings with Twilio and reads provider-owned approval", async () => {
  staffRequest.mockResolvedValueOnce({ checked: 1, approved: 1, unavailable: 0 }).mockResolvedValueOnce({ templates: [binding] });
  const refreshed = mount();
  fireEvent.click(screen.getByRole("button", { name: "Refresh approval" }));
  await screen.findByText("1 of 1 templates approved.");
  expect(staffRequest.mock.calls).toEqual([
    ["/integrations/makerspace/8/whatsapp/twilio/templates/refresh", { method: "POST", body: "{}" }],
    ["/integrations/makerspace/8/channels/whatsapp"],
  ]);
  expect(refreshed).toHaveBeenCalledWith([binding]);
});

it("keeps refresh disabled until credentials and changed bindings are saved", () => {
  mount(true);
  expect(screen.getByRole("button", { name: "Refresh approval" })).toBeDisabled();
  expect(staffRequest).not.toHaveBeenCalled();
});

it("reports approval failures and supports retry", async () => {
  staffRequest.mockRejectedValueOnce(new Error("provider unavailable"));
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Refresh approval" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("provider unavailable");
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh approval" })).toBeEnabled());
});
