import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { NotificationRecipientPicker } from "./NotificationRecipientPicker";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
vi.mock("./NotificationDestinations", () => ({ useScopeOptions: () => ({
  machineTypes: [], machines: [], categories: [],
}) }));
vi.mock("./NotificationRecipientEvent", () => ({
  EventRecipients: ({ feature, event }: { feature: string; event: string }) =>
    <div data-testid="selected-event">{feature}:{event}</div>,
}));

it("labels the new families and changes the selected event to that family's first key", async () => {
  staffRequest.mockResolvedValue({ delegated: false, features: [
    { key: "payments", events: ["charge_raised", "payment_received"] },
    { key: "stock", events: ["low_stock", "procurement_received"] },
    { key: "certifications", events: ["granted", "expiring"] },
  ], roles: [], members: [], rules: [], managed_policy_markers: [],
  scope_options: { machine_types: [], machines: [], categories: [] } });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <NotificationRecipientPicker makerspaceId={7} />
  </QueryClientProvider>);
  await screen.findByRole("option", { name: "Payments" });
  expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/notification-recipient-rules");
  const area = screen.getByRole("combobox", { name: "Area" });
  fireEvent.change(area, { target: { value: "stock" } });
  expect(screen.getByRole("option", { name: "Stock and procurement" })).toBeInTheDocument();
  expect(screen.getByTestId("selected-event")).toHaveTextContent("stock:low_stock");
  fireEvent.change(area, { target: { value: "certifications" } });
  expect(screen.getByRole("option", { name: "Machine access" })).toBeInTheDocument();
  expect(screen.getByTestId("selected-event")).toHaveTextContent("certifications:granted");
  expect(screen.queryByRole("option", { name: "Payment received" })).not.toBeInTheDocument();
});
it("preserves the selected event across visibility changes", async () => {
  staffRequest.mockResolvedValue({ features: [{ key: "payments", events: ["charge_raised", "payment_received"] }], roles: [], members: [], rules: [] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = (visible: boolean) => <QueryClientProvider client={client}><NotificationRecipientPicker makerspaceId={9} visible={visible} /></QueryClientProvider>;
  const { rerender } = render(view(true));
  fireEvent.change(await screen.findByRole("combobox", { name: "Event" }), { target: { value: "payment_received" } });
  rerender(view(false));
  expect(screen.queryByRole("combobox", { name: "Event" })).not.toBeInTheDocument();
  rerender(view(true));
  expect(screen.getByRole("combobox", { name: "Event" })).toHaveValue("payment_received");
  expect(screen.getByTestId("selected-event")).toHaveTextContent("payments:payment_received");
});
