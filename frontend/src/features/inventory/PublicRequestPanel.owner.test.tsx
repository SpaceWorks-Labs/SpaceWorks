import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { PublicRequestPanel } from "./PublicRequestPanel";
import { notifySessionCleared } from "../../lib/api/sessionContext";

const mock = vi.hoisted(() => ({ owner: "1", member: vi.fn(), contexts: vi.fn(), submit: vi.fn(), tenant: null as null | { mode: "single" } }));
vi.mock("./useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: mock.owner }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => true, getSessionOwner: () => mock.owner }));
vi.mock("../../lib/api", () => ({ memberRequest: mock.member }));
vi.mock("./api", () => ({ submitPublicRequest: mock.submit }));
vi.mock("./ContextualRequest", () => ({ ContextualRequest: ({ scope, onSuccess }: { scope: string; onSuccess: (result: unknown, scope: string) => void }) => { mock.contexts(); return <div>Context intake<button onClick={() => onSuccess({ kind: "consumable_plan", plan_id: 1, replayed: false }, scope)}>Complete plan</button></div>; } }));
vi.mock("./BorrowRequestCard", () => ({ BorrowRequestCard: ({ canSubmit, onSubmit }: { canSubmit: boolean; onSubmit: () => void }) => <button disabled={!canSubmit} onClick={onSubmit}>Ordinary submit</button> }));
vi.mock("./PublicToolScanPanel", () => ({ PublicToolScanPanel: () => null }));
vi.mock("../payments/PricePreview", () => ({ PricePreview: () => null }));
vi.mock("./useRequestDraft", () => ({ useRequestDraft: () => ({ requestedFor: "Workshop", setRequestedFor: vi.fn(), submitted: false, setSubmitted: vi.fn(), website: "", setWebsite: vi.fn(), pickup: { from: "", until: "" }, setPickup: vi.fn() }) }));
vi.mock("./useContactRequest", () => ({ useContactRequest: () => ({ ready: true, payload: {}, details: {}, clear: vi.fn() }) }));
vi.mock("../../lib/tenant", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/tenant")>(), useOptionalTenant: () => mock.tenant }));

it("retains the standalone confirmation on same-owner refresh but retires it on A to B to A", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.member.mockResolvedValue({ id: 1 });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="space" makerspaceId={44} modules={["events"]} onClear={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Complete plan" }));
  const message = "Consumable plan saved. No equipment was issued or stock used.";
  expect(await screen.findByText(message)).toBeInTheDocument();
  act(() => { notifySessionCleared("person"); });
  expect(screen.getByText(message)).toBeInTheDocument();
  act(() => { mock.owner = "2"; notifySessionCleared("person"); mock.owner = "1"; notifySessionCleared("person"); });
  expect(screen.queryByText(message)).toBeNull();
});

it("conceals both submission paths when notified owner changes before verified actor", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.contexts.mockReset(); mock.submit.mockReset();
  mock.member.mockResolvedValue({ id: 1 });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = () => <QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="space" makerspaceId={4} modules={["events"]} onClear={vi.fn()} /></QueryClientProvider>;
  const view = render(tree());
  await screen.findByText("Context intake");
  const before = mock.contexts.mock.calls.length;
  const oldButton = screen.getByRole("button", { name: "Ordinary submit" });
  mock.owner = "2"; fireEvent.click(oldButton); view.rerender(tree());
  expect(screen.queryByText("Context intake")).toBeNull();
  expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  await waitFor(() => expect(mock.contexts.mock.calls.length).toBe(before));
  expect(mock.submit).not.toHaveBeenCalled();
  expect(mock.member).toHaveBeenCalledTimes(1);
  mock.owner = "1";
});

it("retains an unknown ordinary outcome across remount until owned history is available and reviewed", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.submit.mockReset();
  mock.member.mockImplementation((path: string) => path === "/auth/me" ? Promise.resolve({ id: 1 }) : Promise.resolve({ results: [{ id: 55, status: "pending_approval", created_at: "2026-11-09" }] }));
  mock.submit.mockRejectedValue(new Error("network lost"));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const tree = () => <QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="space" makerspaceId={4} modules={["events"]} onClear={vi.fn()} /></QueryClientProvider>;
  const view = render(tree()); await screen.findByText("Context intake");
  fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  await screen.findByText(/previous request may have been submitted/i);
  view.unmount(); render(tree());
  expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /load my borrowing history/i }));
  await screen.findByText(/#55/);
  expect(screen.queryByText(/2026-11-09/)).toBeNull();
  // The member sees a request stage, never the raw status code.
  expect(screen.getByText(/Request #55 · Requested/)).toBeInTheDocument();
  expect(screen.queryByText(/pending_approval/)).toBeNull();
  expect(screen.getByRole("link", { name: /open full borrowing history/i })).toHaveAttribute("href", "/m/space/member/loans/history");
  fireEvent.click(screen.getByRole("button", { name: /reviewed my history/i }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeEnabled());
  expect(mock.submit).toHaveBeenCalledTimes(1);
});

it("releases the ordinary fence on a definitive initial validation rejection", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.submit.mockReset(); mock.member.mockResolvedValue({ id: 1 });
  mock.submit.mockRejectedValue(Object.assign(new Error("invalid"), { status: 400 }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="other-space" makerspaceId={5} modules={["events"]} onClear={vi.fn()} /></QueryClientProvider>);
  await screen.findByText("Context intake"); fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  await waitFor(() => expect(mock.submit).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeEnabled());
  expect(screen.queryByText(/previous request may have been submitted/i)).toBeNull();
});

it("releases the ordinary fence after success and clears the original cart", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.submit.mockReset(); mock.member.mockResolvedValue({ id: 1 }); mock.submit.mockResolvedValue({});
  const clear = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="success-space" makerspaceId={6} modules={["events"]} onClear={clear} /></QueryClientProvider>);
  await screen.findByText("Context intake"); fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  await waitFor(() => expect(clear).toHaveBeenCalledTimes(1));
  expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeEnabled();
});

it("does not clear a different owner's cart when the first owner completes late", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.submit.mockReset(); mock.member.mockResolvedValue({ id: 1 });
  let finish!: (value: unknown) => void; mock.submit.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const clear = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const tree = () => <QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="owner-switch" makerspaceId={7} modules={["events"]} onClear={clear} /></QueryClientProvider>;
  const view = render(tree()); await screen.findByText("Context intake"); fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  await waitFor(() => expect(mock.submit).toHaveBeenCalledTimes(1)); mock.owner = "2"; view.rerender(tree()); finish({});
  await waitFor(() => expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeDisabled());
  expect(clear).not.toHaveBeenCalled(); mock.owner = "1";
});

it("shows recovery after an in-flight ordinary request rejects following a panel remount", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.submit.mockReset(); mock.member.mockResolvedValue({ id: 1 });
  let fail!: (reason: Error) => void;
  mock.submit.mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const tree = () => <QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="remount-pending" makerspaceId={8} modules={["events"]} onClear={vi.fn()} /></QueryClientProvider>;
  const first = render(tree()); await screen.findByText("Context intake");
  fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  await waitFor(() => expect(mock.submit).toHaveBeenCalledTimes(1));
  first.unmount(); render(tree());
  expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: /load my borrowing history/i })).toBeNull();
  fail(new Error("network outcome unknown"));
  await screen.findByRole("button", { name: /load my borrowing history/i });
  expect(screen.getByRole("button", { name: "Ordinary submit" })).toBeDisabled();
});

it("reconciles an exact pending intent completed between render and subscription", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.member.mockResolvedValue({ id: 1 });
  const done = vi.fn(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const owner = { current: vi.fn().mockReturnValueOnce({ operation_id: "old" }).mockReturnValue(undefined), subscribe: vi.fn(() => () => {}) };
  render(<QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="completion-gap" makerspaceId={9} modules={["events"]} pendingOwner={owner as never} contextualLocked onContextDone={done} onClear={vi.fn()} /></QueryClientProvider>);
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(owner.subscribe).toHaveBeenCalled();
});

it("links borrowing history through the single-tenant path", async () => {
  mock.owner = "1"; mock.member.mockReset(); mock.submit.mockReset(); mock.tenant = { mode: "single" };
  mock.member.mockImplementation((path: string) => path === "/auth/me" ? Promise.resolve({ id: 1 }) : Promise.resolve({ results: [{ id: 56, status: "pending_approval", created_at: "2026-11-09T10:00:00Z" }] }));
  mock.submit.mockRejectedValue(new Error("network lost"));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><PublicRequestPanel items={[{ productId: 8, name: "Drill", quantity: 1 }]} makerspaceSlug="solo" makerspaceId={9} modules={["events"]} onClear={vi.fn()} /></QueryClientProvider>);
  await screen.findByText("Context intake");
  fireEvent.click(screen.getByRole("button", { name: "Ordinary submit" }));
  fireEvent.click(await screen.findByRole("button", { name: /load my borrowing history/i }));
  await screen.findByText(/#56/);
  expect(screen.getByRole("link", { name: /open full borrowing history/i })).toHaveAttribute("href", "/member/loans/history");
  mock.tenant = null;
});
