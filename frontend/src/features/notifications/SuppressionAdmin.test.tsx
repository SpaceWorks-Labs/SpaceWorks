import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DeliveryLogScreen } from "./DeliveryLogScreen";
import { SuppressionAdmin } from "./SuppressionAdmin";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: request }));
beforeEach(() => {
  request.mockReset();
  request.mockImplementation((url: string, options?: { method?: string }) => Promise.resolve(options?.method ? {} :
    url.includes("notification-destinations") ? [] : { count: 0, results: [] }));
});
function Harness() {
  const [open, setOpen] = useState(true);
  return <SuppressionAdmin makerspaceId={7} embedded dialogOpen={open} onDialogClose={() => setOpen(false)} />;
}
it("opens the existing suppress form from the routed header and closes only after success", async () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/admin/email-log?delivery_view=suppression"]}>
    <DeliveryLogScreen makerspaceId={7} />
  </MemoryRouter></QueryClientProvider>);
  expect(screen.queryByRole("textbox", { name: "Email address" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Suppress an address" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Email address" }), { target: { value: "bounce@example.test" } });
  fireEvent.change(screen.getByRole("combobox", { name: "Reason" }), { target: { value: "complaint" } });
  fireEvent.click(screen.getByRole("button", { name: "Suppress email" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/integrations/makerspace/7/email-suppressions", {
    method: "POST", body: JSON.stringify({ address: "bounce@example.test", reason: "complaint" }),
  }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});
it("keeps suppression errors inside the open form", async () => {
  request.mockImplementation((_url: string, options?: { method?: string }) => options?.method ? Promise.reject(new Error("Could not suppress this address")) : Promise.resolve({ count: 0, results: [] }));
  render(<QueryClientProvider client={new QueryClient()}><Harness /></QueryClientProvider>);
  fireEvent.change(screen.getByRole("textbox", { name: "Email address" }), { target: { value: "bounce@example.test" } });
  fireEvent.click(screen.getByRole("button", { name: "Suppress email" }));
  expect(await screen.findByText("Could not suppress this address")).toBeInTheDocument();
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});
it("preserves the inline form for independent existing embedders", () => {
  render(<QueryClientProvider client={new QueryClient()}><SuppressionAdmin makerspaceId={7} embedded /></QueryClientProvider>);
  expect(screen.getByRole("textbox", { name: "Email address" })).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).toBeNull();
});
