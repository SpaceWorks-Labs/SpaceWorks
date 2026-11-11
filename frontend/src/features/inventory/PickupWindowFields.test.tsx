import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { pickupWindowPayload, pickupWindowProblem } from "./PickupWindowFields";
import { PublicRequestPanel } from "./PublicRequestPanel";

const { submit } = vi.hoisted(() => ({ submit: vi.fn() }));
vi.mock("./api", () => ({ submitPublicRequest: submit, requestContactCode: vi.fn() }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
// Member borrowing only submits for a verified signed-in owner (#75f): session owner must match /auth/me.
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => true, getSessionOwner: () => "1" }));
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), memberRequest: vi.fn().mockResolvedValue({ id: 1 }) }));

const items = [{ productId: 4, name: "Drill", quantity: 1 }];
const local = (offsetHours: number) => {
  const date = new Date(Date.now() + offsetHours * 3_600_000);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
};

beforeEach(() => { submit.mockReset(); submit.mockResolvedValue({ public_token: "t", status: "pending_approval" }); });

function setup(features: string[]) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
    <PublicRequestPanel items={items} makerspaceSlug="forge" onClear={vi.fn()} features={features} /></QueryClientProvider>);
}

it("sends the collection window as ISO datetimes when reservations are on", async () => {
  setup(["loans.reservations"]);
  fireEvent.change(screen.getByLabelText("From"), { target: { value: local(24) } });
  fireEvent.change(screen.getByLabelText("Until"), { target: { value: local(26) } });
  fireEvent.change(screen.getByPlaceholderText("What do you need these items for?"), { target: { value: "Shelf build" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Submit request" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
  await waitFor(() => expect(submit).toHaveBeenCalled());
  const payload = submit.mock.calls[0][1];
  expect(payload.pickup_from).toBe(new Date(local(24)).toISOString());
  expect(payload.pickup_until).toBe(new Date(local(26)).toISOString());
});

it("blocks a window that ends before it starts", () => {
  setup(["loans.reservations"]);
  fireEvent.change(screen.getByLabelText("From"), { target: { value: local(26) } });
  fireEvent.change(screen.getByLabelText("Until"), { target: { value: local(24) } });
  fireEvent.change(screen.getByPlaceholderText("What do you need these items for?"), { target: { value: "Shelf build" } });
  expect(screen.getByRole("alert")).toHaveTextContent("must end after it starts");
  expect(screen.getByRole("button", { name: "Submit request" })).toBeDisabled();
});

it("has no collection fields and sends no window while reservations are off", async () => {
  setup([]);
  expect(screen.queryByText(/When will you collect/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("What do you need these items for?"), { target: { value: "Shelf build" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Submit request" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
  await waitFor(() => expect(submit).toHaveBeenCalled());
  expect(submit.mock.calls[0][1]).not.toHaveProperty("pickup_from");
});

it("validates and serialises windows", () => {
  expect(pickupWindowProblem({ from: local(-2), until: "" })).toMatch(/hasn't passed/);
  expect(pickupWindowProblem({ from: "", until: "" })).toBe("");
  expect(pickupWindowPayload({ from: "", until: "" })).toEqual({});
});
