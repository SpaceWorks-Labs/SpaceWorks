import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";
import { incidentErrorMessage } from "../api";
import { IncidentRegister } from "../IncidentRegister";

// Decision 246: loading, error (refusal copy + retry) and the create flow's query invalidation.
const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const empty = { count: 0, next: null, previous: null, results: [] };
function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><IncidentRegister makerspace={{ id: 4 }} /></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { api.staffRequest.mockReset(); });

describe("incident register states", () => {
  it("shows neither rows nor the empty message while loading", async () => {
    let release: (value: typeof empty) => void = () => undefined;
    api.staffRequest.mockReturnValue(new Promise(resolve => { release = resolve; }));
    show();
    expect(screen.queryByText(/No incidents recorded/)).toBeNull();
    release(empty);
    expect(await screen.findByText(/No incidents recorded/)).toBeInTheDocument();
  });

  it.each([
    [new StructuredApiError(404, { code: "feature_disabled" }), /switched off for this space/],
    [new StructuredApiError(404, { detail: "x" }), /could not be found/],
    [new StructuredApiError(403, {}), /can't change this incident/],
    [new StructuredApiError(429, {}), /Too many reports/],
    [new Error("Network down"), /Network down/],
  ])("explains a failed load (%s) and retries on request", async (error, copy) => {
    // Path-aware: the register also asks for saved views, which must not consume the failure.
    let failed = false;
    api.staffRequest.mockImplementation((path?: string) => {
      if (path?.includes("/incidents?") && !failed) { failed = true; return Promise.reject(error); }
      return Promise.resolve(empty);
    });
    show();
    expect(await screen.findByText(copy)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry|try again/i }));
    expect(await screen.findByText(/No incidents recorded/)).toBeInTheDocument();
    expect(api.staffRequest.mock.calls.filter(([path]) => path?.includes("/incidents?"))).toHaveLength(2);
  });

  it("falls back to a generic line for an unreadable error", () => {
    expect(incidentErrorMessage(new Error(""))).toBe("Something went wrong. Try again.");
    expect(incidentErrorMessage("boom")).toBe("Something went wrong. Try again.");
  });
});

describe("recording an incident", () => {
  it("posts once, then refreshes the register list", async () => {
    api.staffRequest.mockImplementation((_path: string, init?: RequestInit) =>
      Promise.resolve(init?.method === "POST" ? { id: 9, title: "Cut", actions: [], status: "reported", severity: "low", kind: "incident", area: "lending" } : empty));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Record incident" }));
    const dialog = await screen.findByRole("dialog");
    const listCalls = () => api.staffRequest.mock.calls.filter(([path, init]) => path.endsWith("/incidents?page=1") && !init?.method).length;
    const before = listCalls();
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Short summary" }), { target: { value: "Cut" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record incident" }));
    await waitFor(() => expect(api.staffRequest.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
    await waitFor(() => expect(listCalls()).toBeGreaterThan(before));
  });

  it("keeps the dialog open and shows the refusal when the server says no", async () => {
    api.staffRequest.mockImplementation((_path: string, init?: RequestInit) =>
      init?.method === "POST" ? Promise.reject(new StructuredApiError(429, {})) : Promise.resolve(empty));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Record incident" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Short summary" }), { target: { value: "Cut" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record incident" }));
    expect(await within(dialog).findByText(/Too many reports/)).toBeInTheDocument();
  });
});
