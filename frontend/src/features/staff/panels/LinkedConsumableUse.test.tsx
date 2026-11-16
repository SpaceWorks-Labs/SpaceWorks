import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { PendingIntake } from "../../inventory/contextualIntake";
import { LinkedConsumableUse } from "./LinkedConsumableUse";
import type { LinkedUseBody } from "./linkedConsumableApi";
const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: mock.request }));

it("uses only a paged authorized source and retries the identical operation after uncertainty", async () => {
  let attempts = 0; mock.request.mockReset(); mock.request.mockImplementation((path: string) => {
    if (path.includes("equipment-sources")) return Promise.resolve({ count: 1, next: null, previous: null, results: [{ kind: "plan", id: 7, planned_quantity: 3, used_quantity: 1 }] });
    attempts++; return attempts === 1 ? Promise.reject(new Error("offline")) : Promise.resolve({ status: "recorded", replayed: true });
  });
  const lock = vi.fn(); const owner = new PendingIntake<LinkedUseBody>();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><LinkedConsumableUse tenant={4} product={8} scope="actor:4:8" owner={owner} admitted={() => true} acquire={() => () => {}} onLockChange={lock} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: /Consumable plan/ }));
  fireEvent.change(screen.getByLabelText("How many were used"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Record linked use" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry the same use" }));
  await screen.findByText("Use recorded.");
  const calls = mock.request.mock.calls.filter(row => String(row[0]).endsWith("/use"));
  expect(calls).toHaveLength(2); expect(calls[0][1].body).toBe(calls[1][1].body);
  expect(JSON.parse(calls[0][1].body)).toMatchObject({ plan_id: 7, allocation_id: null, quantity: 2 });
  expect(mock.request.mock.calls.some(row => row[0] === "/admin/makerspace/4/consumables/8/equipment-sources?page=1")).toBe(true);
  await waitFor(() => expect(lock).toHaveBeenLastCalledWith(false));
});

it("does not send a captured action after the semantic owner changes", async () => {
  let allowed = true; mock.request.mockReset(); mock.request.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ kind: "plan", id: 7, planned_quantity: 1, used_quantity: 0 }] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><LinkedConsumableUse tenant={4} product={8} scope="actor:4:8" owner={new PendingIntake<LinkedUseBody>()} admitted={() => allowed} acquire={() => () => {}} onLockChange={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: /Consumable plan/ }));
  const button = screen.getByRole("button", { name: "Record linked use" }); allowed = false; fireEvent.click(button);
  expect(mock.request.mock.calls.some(row => String(row[0]).endsWith("/use"))).toBe(false);
});

it("keeps source pages separate for different products even with the same scope", async () => {
  mock.request.mockReset();
  mock.request.mockImplementation((path: string) => Promise.resolve({ count: 1, next: null, previous: null,
    results: [{ kind: "plan", id: path.includes("/8/") ? 8 : 9, planned_quantity: path.includes("/8/") ? 8 : 9, used_quantity: 0 }] }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const view = render(<QueryClientProvider client={client}><LinkedConsumableUse tenant={4} product={8} scope="same" owner={new PendingIntake<LinkedUseBody>()} admitted={() => true} acquire={() => () => {}} onLockChange={vi.fn()} /></QueryClientProvider>);
  await screen.findByText(/8 planned/);
  view.rerender(<QueryClientProvider client={client}><LinkedConsumableUse tenant={4} product={9} scope="same" owner={new PendingIntake<LinkedUseBody>()} admitted={() => true} acquire={() => () => {}} onLockChange={vi.fn()} /></QueryClientProvider>);
  await screen.findByText(/9 planned/);
  expect(mock.request.mock.calls.some(row => String(row[0]).includes("/8/equipment-sources"))).toBe(true);
  expect(mock.request.mock.calls.some(row => String(row[0]).includes("/9/equipment-sources"))).toBe(true);
});

it("reconciles a remounted form when the old request completes", async () => {
  let resolve!: (value: unknown) => void; const delayed = new Promise<unknown>(done => { resolve = done; });
  mock.request.mockReset(); mock.request.mockImplementation((path: string) => path.includes("equipment-sources")
    ? Promise.resolve({ count: 1, next: null, previous: null, results: [{ kind: "plan", id: 7, planned_quantity: 1, used_quantity: 0 }] }) : delayed);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const owner = new PendingIntake<LinkedUseBody>(); const lock = vi.fn();
  const component = () => <QueryClientProvider client={client}><LinkedConsumableUse tenant={4} product={8} scope="same" owner={owner} admitted={() => true} acquire={() => () => {}} onLockChange={lock} /></QueryClientProvider>;
  const first = render(component()); fireEvent.click(await screen.findByRole("button", { name: /Consumable plan/ }));
  fireEvent.click(screen.getByRole("button", { name: "Record linked use" })); first.unmount();
  render(component()); expect(await screen.findByRole("button", { name: "Retry the same use" })).toBeInTheDocument();
  resolve({ status: "recorded", replayed: false });
  await waitFor(() => expect(screen.queryByRole("button", { name: "Retry the same use" })).not.toBeInTheDocument());
  expect(lock).toHaveBeenLastCalledWith(false);
});
