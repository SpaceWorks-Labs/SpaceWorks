import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { BookingCalendar } from "./BookingCalendar";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
const session = vi.hoisted(() => ({ owner: "1", listeners: new Set<(context: "person") => void>() }));
const notify = () => session.listeners.forEach(fn => fn("person"));
vi.mock("../../lib/api", () => ({ memberRequest, getAccessToken: () => null }));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: session.owner }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionOwner: () => session.owner }));
vi.mock("../../lib/api/sessionContext", () => ({ onSessionCleared: (fn: (context: "person") => void) => { session.listeners.add(fn); return () => { session.listeners.delete(fn); }; } }));

beforeEach(() => { memberRequest.mockReset(); session.owner = "1"; });

it("shows a newly issued private link and clears it after revocation", async () => {
  let enabled = false;
  memberRequest.mockImplementation(async (_path: string, options?: { method: string }) => {
    if (options?.method === "POST") { enabled = true; return { feed_url: "https://example.test/private.ics" }; }
    if (options?.method === "DELETE") { enabled = false; return; }
    return { enabled };
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { unmount } = render(<QueryClientProvider client={client}><BookingCalendar slug="forge" /></QueryClientProvider>);
  try {
    await waitFor(() => expect(screen.getByRole("button", { name: "Create calendar link" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Create calendar link" }));
    expect(await screen.findByLabelText("Private calendar URL")).toHaveValue("https://example.test/private.ics");
    fireEvent.click(await screen.findByRole("button", { name: "Revoke calendar link" }));
    await waitFor(() => expect(screen.queryByLabelText("Private calendar URL")).toBeNull());
    expect(memberRequest).toHaveBeenCalledWith("/public/forge/my-bookings/calendar/", { method: "DELETE" });
  } finally { unmount(); client.clear(); }
});

it("conceals a private URL on owner change and ignores a late issue response after returning", async () => {
  session.owner = "1";
  let finish!: (value: { feed_url: string }) => void;
  memberRequest.mockImplementation((_path: string, options?: { method: string }) => options?.method === "POST"
    ? new Promise(resolve => { finish = resolve; }) : Promise.resolve({ enabled: false }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = () => <QueryClientProvider client={client}><BookingCalendar slug="forge" /></QueryClientProvider>;
  const mounted = render(view());
  try {
    await waitFor(() => expect(screen.getByRole("button", { name: "Create calendar link" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Create calendar link" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(expect.any(String), { method: "POST" }));
    act(() => { session.owner = "2"; notify(); session.owner = "1"; notify(); });
    mounted.rerender(view());
    await act(async () => finish({ feed_url: "https://example.test/private.ics" }));
    expect(screen.queryByLabelText("Private calendar URL")).toBeNull();
    memberRequest.mockImplementation((_path: string, options?: { method: string }) => Promise.resolve(
      options?.method === "POST" ? { feed_url: "https://example.test/fresh.ics" } : { enabled: false },
    ));
    await waitFor(() => expect(screen.getByRole("button", { name: "Create calendar link" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Create calendar link" }));
    expect(await screen.findByLabelText("Private calendar URL")).toHaveValue("https://example.test/fresh.ics");
  } finally { mounted.unmount(); client.clear(); session.owner = "1"; }
});

it("keeps the issued link on a same-owner refresh", async () => {
  session.owner = "1";
  memberRequest.mockImplementation((_path: string, options?: { method: string }) => Promise.resolve(
    options?.method === "POST" ? { feed_url: "https://example.test/private.ics" } : { enabled: true },
  ));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const mounted = render(<QueryClientProvider client={client}><BookingCalendar slug="forge" /></QueryClientProvider>);
  try {
    await waitFor(() => expect(screen.getByRole("button", { name: "Rotate calendar link" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Rotate calendar link" }));
    expect(await screen.findByLabelText("Private calendar URL")).toHaveValue("https://example.test/private.ics");
    act(() => notify());
    expect(screen.getByLabelText("Private calendar URL")).toHaveValue("https://example.test/private.ics");
  } finally { mounted.unmount(); client.clear(); }
});
