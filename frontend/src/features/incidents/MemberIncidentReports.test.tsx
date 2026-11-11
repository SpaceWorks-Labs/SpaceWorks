import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import type { MemberIncident } from "./api";
import { MemberIncidentReports } from "./MemberIncidentReports";

const api = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), memberRequest: api.memberRequest }));

const report: MemberIncident = { id: 3, kind: "near_miss", severity: "medium", status: "triaged", area: "machines",
  title: "Loose blade", description: "", location: "", occurred_at: "2026-11-08T15:00:00Z", machine: 2, room: null, event: null,
  loan: null, booking: null, created_at: "2026-11-08T15:01:00Z" };
const page = (rows: MemberIncident[]) => ({ count: rows.length, next: null, previous: null, results: rows });

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemberIncidentReports makerspaceId={9} /></QueryClientProvider>);
}

describe("MemberIncidentReports", () => {
  beforeEach(() => { api.memberRequest.mockReset(); });

  it("lists the member's own reports and encourages near-miss reporting", async () => {
    api.memberRequest.mockResolvedValue(page([report]));
    const { container } = show();
    expect(await screen.findByText("Loose blade")).toBeInTheDocument();
    expect(screen.getByText("Triaged")).toBeInTheDocument();
    expect(screen.getByText(/Near misses count too/)).toBeInTheDocument();
    expect(api.memberRequest).toHaveBeenCalledWith("/member/makerspaces/9/incidents?page=1");
    await expectNoA11yViolations(container);
  });

  it("sends a report with only the filled fields and thanks the member", async () => {
    api.memberRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? report : page([])));
    show();
    expect(await screen.findByText("You haven't reported anything here.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Report an incident or near miss" }));
    fireEvent.change(screen.getByRole("combobox", { name: "What happened" }), { target: { value: "near_miss" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Short summary" }), { target: { value: "Loose blade" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Machine number" }), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    await waitFor(() => expect(api.memberRequest).toHaveBeenCalledWith("/member/makerspaces/9/incidents", {
      method: "POST", body: JSON.stringify({ kind: "near_miss", severity: "low", title: "Loose blade", machine_id: 2 }) }));
    expect(await screen.findByText("Thank you. Your report reached the staff.")).toBeInTheDocument();
  });

  it("explains a refusal in plain words", async () => {
    api.memberRequest.mockImplementation((_path: string, init?: RequestInit) => init?.method === "POST"
      ? Promise.reject(new StructuredApiError(404, { detail: "off", code: "feature_disabled", feature: "safety.incidents" }))
      : Promise.resolve(page([])));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Report an incident or near miss" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Short summary" }), { target: { value: "Spill" } });
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The incident register is switched off for this space.");
  });
});
