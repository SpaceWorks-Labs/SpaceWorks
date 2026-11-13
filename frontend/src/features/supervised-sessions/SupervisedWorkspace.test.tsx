import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import type { SupervisedSession } from "./api";
import { SupervisedWorkspace } from "./SupervisedWorkspace";

const api = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), memberRequest: api.memberRequest }));

const session = (overrides: Partial<SupervisedSession> = {}): SupervisedSession => ({
  id: 5, makerspace: 1, machine: 3, machine_name: "Laser A", instructor: 10, instructor_name: "Ravi", event: null, note: "Intro night",
  opened_at: "2026-11-10T17:00:00Z", closed_at: null, is_open: true,
  participants: [{ user: 21, name: "Mina", added_at: "2026-11-10T17:01:00Z", removed_at: null }],
  uses: [], ...overrides,
});
const page = (rows: SupervisedSession[]) => ({ count: rows.length, next: null, previous: null, results: rows });
const calls = (method: string) => api.memberRequest.mock.calls.filter(([, init]) => init?.method === method).map(([path, init]) => [path, init.body]);

function show(props: Partial<Parameters<typeof SupervisedWorkspace>[0]> = {}) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SupervisedWorkspace makerspaceId={1} {...props} /></QueryClientProvider>);
}

describe("SupervisedWorkspace", () => {
  beforeEach(() => { api.memberRequest.mockReset(); });

  it("opens a session on the machine and shows its manager", async () => {
    api.memberRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(
      init?.method === "POST" ? session({ participants: [] }) : path.startsWith("/member/supervised-sessions/5") ? session({ participants: [] }) : page([])));
    const { container } = show({ machineId: 3 });
    expect(await screen.findByText("No open supervised sessions.")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Note (optional)" }), { target: { value: "Intro night" } });
    fireEvent.click(screen.getByRole("button", { name: "Open session" }));
    await waitFor(() => expect(calls("POST")).toContainEqual(["/member/machines/3/supervised-sessions", JSON.stringify({ note: "Intro night" })]));
    expect(await screen.findByRole("heading", { name: "Supervised session on Laser A" })).toBeInTheDocument();
    expect(screen.getByText(/Nobody yet/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("filters the session list by machine on the server", async () => {
    api.memberRequest.mockResolvedValue(page([]));
    show({ machineId: 3 });
    expect(await screen.findByText("No open supervised sessions.")).toBeInTheDocument();
    expect(api.memberRequest).toHaveBeenCalledWith("/member/makerspaces/1/supervised-sessions?status=open&page=1&machine=3");
  });

  it("picks the machine from the member machine list and maps an instructor refusal to plain copy", async () => {
    const machine = { id: 3, name: "Laser A", machine_type: { name: "Laser", icon: "" }, image_url: null, status: "idle", usage_hours: "1.00" };
    api.memberRequest.mockImplementation((path: string, init?: RequestInit) => init?.method === "POST"
      ? Promise.reject(new StructuredApiError(409, { detail: "busy", code: "machine_in_use" }))
      : Promise.resolve(path.startsWith("/member/makerspaces/1/machines?") ? page([machine] as never[]) : page([])));
    show();
    expect(await screen.findByRole("option", { name: "Laser A · Laser" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Machine" }), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Open session" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Someone is using this machine, or a supervised session is already open on it.");
    expect(calls("POST")).toContainEqual(["/member/machines/3/supervised-sessions", JSON.stringify({})]);
  });

  it("explains that a minor can't open a supervised session", async () => {
    const machine = { id: 3, name: "Laser A", machine_type: { name: "Laser", icon: "" }, image_url: null, status: "idle", usage_hours: "1.00" };
    api.memberRequest.mockImplementation((path: string, init?: RequestInit) => init?.method === "POST"
      ? Promise.reject(new StructuredApiError(403, { detail: "Supervised sessions must be led by an adult.", code: "instructor_must_be_adult" }))
      : Promise.resolve(path.startsWith("/member/makerspaces/1/machines?") ? page([machine] as never[]) : page([])));
    show();
    expect(await screen.findByRole("option", { name: "Laser A · Laser" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Machine" }), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Open session" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Supervised sessions must be led by an adult instructor.");
  });

  it("asks for the machine number when the member machine list is refused", async () => {
    api.memberRequest.mockImplementation((path: string) => path.startsWith("/member/makerspaces/1/machines?")
      ? Promise.reject(new StructuredApiError(403, { detail: "no" })) : Promise.resolve(page([])));
    show();
    expect(await screen.findByRole("textbox", { name: "Machine number" })).toBeInTheDocument();
  });

  it("adds a supervisee, records a use and closes after confirming", async () => {
    let current = session();
    api.memberRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes("/supervised-sessions?")) return Promise.resolve(page([current]));
      if (path.endsWith("/uses")) { current = session({ uses: [{ id: 40, user: 21, instructor: 10, started_at: "2026-11-10T17:05:00Z", ended_at: null, note: "" }] }); return Promise.resolve(current.uses[0]); }
      if (path.endsWith("/close")) { current = session({ is_open: false, closed_at: "2026-11-10T19:00:00Z" }); return Promise.resolve(current); }
      if (path.endsWith("/supervisees")) return Promise.resolve(current);
      if (path === "/member/supervised-sessions/5/people?q=Ka") return Promise.resolve({ results: [{ id: 22, display_name: "Kai" }] });
      return Promise.resolve(init?.method === "POST" ? {} : current);
    });
    show({ initialSessionId: 5 });
    expect(await screen.findByText("Mina")).toBeInTheDocument();
    const search = screen.getByRole("combobox", { name: "Supervisee" });
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: "Ka" } });
    fireEvent.mouseDown(await screen.findByRole("option", { name: "Kai" }));
    fireEvent.click(screen.getByRole("button", { name: "Add supervisee" }));
    await waitFor(() => expect(calls("POST")).toContainEqual(["/member/supervised-sessions/5/supervisees", JSON.stringify({ user_id: 22 })]));
    fireEvent.click(screen.getByRole("button", { name: "Start use for Mina" }));
    await waitFor(() => expect(calls("POST")).toContainEqual(["/member/supervised-sessions/5/uses", JSON.stringify({ user_id: 21 })]));
    expect(await screen.findByRole("button", { name: "End use for Mina" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close session" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Close session" }));
    await waitFor(() => expect(calls("POST")).toContainEqual(["/member/supervised-sessions/5/close", JSON.stringify({})]));
    expect(await screen.findByText(/Nobody was supervised|Mina/)).toBeInTheDocument();
  });

  it("falls back to the account number when the person does not lead the session", async () => {
    api.memberRequest.mockImplementation((path: string) => path.includes("/people?")
      ? Promise.reject(new StructuredApiError(404, { detail: "Not found." }))
      : Promise.resolve(path.includes("/supervised-sessions?") ? page([session()]) : session()));
    show({ initialSessionId: 5 });
    const search = await screen.findByRole("combobox", { name: "Supervisee" });
    fireEvent.change(search, { target: { value: "Mi" } });
    fireEvent.change(await screen.findByRole("textbox", { name: "Supervisee's account number" }), { target: { value: "22" } });
    expect(screen.getByRole("button", { name: "Add supervisee" })).toBeEnabled();
  });
});
