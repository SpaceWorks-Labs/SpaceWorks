import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import type { Incident } from "./api";
import { IncidentRegister } from "./IncidentRegister";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const incident = (overrides: Partial<Incident> = {}): Incident => ({
  id: 7, makerspace: 4, kind: "near_miss", severity: "high", status: "reported", area: "machines", title: "Guard left open",
  description: "Bandsaw guard was up.", location: "Wood shop", occurred_at: "2026-11-09T10:00:00Z", reporter: 3, reporter_name: "Asha",
  involved_user: null, involved_name: "", involved_note: "", sponsor_user: null, machine: 12, room: null, event: null, loan: null,
  booking: null, repair_issue: null, guest_pass: null, triaged_by: null, resolution_note: "", closed_at: null,
  created_at: "2026-11-09T10:05:00Z", updated_at: "2026-11-09T10:05:00Z",
  actions: [{ id: 31, description: "Add a guard interlock", assignee: null, assignee_name: "", due_date: "2026-11-20", done_at: null, created_at: "2026-11-09T11:00:00Z" }],
  ...overrides,
});
const page = (rows: Incident[]) => ({ count: rows.length, next: null, previous: null, results: rows });

function show(path = "/") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><IncidentRegister makerspace={{ id: 4 }} /></MemoryRouter></QueryClientProvider>);
}

describe("IncidentRegister", () => {
  beforeEach(() => { api.staffRequest.mockReset(); });

  it("lists incidents and narrows the register by filter", async () => {
    api.staffRequest.mockResolvedValue(page([incident()]));
    const { container } = show();
    expect(await screen.findByText("Guard left open")).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents?page=1");
    fireEvent.change(screen.getByRole("combobox", { name: "Severity" }), { target: { value: "critical" } });
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents?severity=critical&page=1"));
    await expectNoA11yViolations(container);
  });

  it("explains an empty register and a filtered-out one", async () => {
    api.staffRequest.mockResolvedValue(page([]));
    show();
    expect(await screen.findByText(/No incidents recorded/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "closed" } });
    expect(await screen.findByText("No incidents match these filters.")).toBeInTheDocument();
  });

  it("records an incident with the staff-only fields", async () => {
    api.staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? incident({ id: 8 }) : page([])));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Record incident" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Short summary" }), { target: { value: "Cut finger" } });
    fireEvent.change(within(dialog).getByRole("combobox", { name: "Area" }), { target: { value: "lending" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record incident" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(api.staffRequest.mock.calls.find(([, init]) => init?.method === "POST")![1].body);
    expect(body).toEqual({ kind: "incident", severity: "low", title: "Cut finger", area: "lending" });
  });

  it("triages with only the changed fields and works the follow-up actions", async () => {
    api.staffRequest.mockImplementation((path: string, init?: RequestInit) => Promise.resolve(
      path === "/admin/incidents/7/assignees" ? { results: [{ id: 15, display_name: "Priya" }] }
        : init?.method === "PATCH" && path === "/admin/incidents/7" ? incident({ status: "triaged", updated_at: "2026-11-10T09:00:00Z" })
        : init?.method ? { id: 32 } : incident()));
    show("/?incident=7");
    expect(await screen.findByRole("heading", { name: "Guard left open" })).toBeInTheDocument();
    expect(screen.getByText("#12")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), { target: { value: "triaged" } });
    fireEvent.click(screen.getByRole("button", { name: "Save triage" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/incidents/7", { method: "PATCH", body: JSON.stringify({ status: "triaged" }) }));
    fireEvent.click(screen.getByRole("button", { name: "Mark done: Add a guard interlock" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/incident-actions/31", { method: "PATCH", body: JSON.stringify({ done: true }) }));
    fireEvent.change(screen.getByRole("textbox", { name: "New follow-up action" }), { target: { value: "Retrain the group" } });
    fireEvent.click(screen.getByRole("button", { name: "Add action" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/incidents/7/actions", { method: "POST", body: JSON.stringify({ description: "Retrain the group" }) }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "New follow-up action" })).toHaveValue(""));
    fireEvent.change(screen.getByRole("textbox", { name: "New follow-up action" }), { target: { value: "Fit the interlock" } });
    expect(await screen.findByRole("option", { name: "Priya" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Assign to (optional)" }), { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Add action" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/incidents/7/actions",
      { method: "POST", body: JSON.stringify({ description: "Fit the interlock", assignee_id: 15 }) }));
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/incidents/7/assignees", expect.anything());
  });
});
