import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { ConsumableKitPlan } from "./ConsumableKitPlan";
import { PendingIntake, type SelfBody } from "./contextualIntake";
const mock = vi.hoisted(() => ({ member: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: mock.member, staffRequest: vi.fn() }));

it("saves a consumable-only plan with no fabricated loan or manual items", async () => {
  mock.member.mockReset(); mock.member.mockImplementation((path: string) => path.includes("equipment-kits")
    ? Promise.resolve({ results: [{ id: 9, name: "Materials", version: 2, lines: [{ product_id: 3, display_name: "Glue", quantity_per_person: 1, kind: "consumable" }] }], next: null, previous: null })
    : Promise.resolve({ kind: "consumable_plan", plan_id: 12, replayed: false }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ConsumableKitPlan scope="owner" slug="forge" pendingOwner={new PendingIntake<SelfBody>()} admitted={() => true} onLock={vi.fn()} onDone={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Materials" }));
  fireEvent.change(screen.getByLabelText("Purpose"), { target: { value: "Workshop" } });
  fireEvent.click(screen.getByRole("button", { name: "Save plan" }));
  await screen.findByText("Consumable plan saved. No stock was used.");
  expect(screen.getByLabelText("Purpose")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Save plan" })).toBeDisabled();
  const call = mock.member.mock.calls.find(row => String(row[0]).endsWith("/requests/contextual"));
  expect(JSON.parse(call![1].body)).toMatchObject({ kit: { id: 9, version: 2 }, event_registration_id: null, booking_token: null });
  expect(JSON.parse(call![1].body).items).toBeUndefined();
  await waitFor(() => expect(mock.member).toHaveBeenCalledTimes(2));
});
