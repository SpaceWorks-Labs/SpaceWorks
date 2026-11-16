import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { AllowedTabsContext } from "../areaOverview/allowedTabsContext";
import { RelatedLinks } from "./RelatedLinks";
import { staffHref, useCrossLink } from "./staffHref";
import { useSubjectIncidents } from "./subjectIncidents";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

function wrap(node: React.ReactNode, tabs: string[] = [], path = "/m/lab/admin/machines") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><AllowedTabsContext.Provider value={tabs}>{node}</AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}

function Probe({ tab }: { tab: string }) {
  const link = useCrossLink();
  return <p>{link(tab, { machine: 12, empty: "", none: null }) ?? "no link"}</p>;
}

function IncidentProbe({ subject }: { subject: "machine" | "product" }) {
  const result = useSubjectIncidents(4, subject, 12);
  return <p>{result.hidden ? "hidden" : `count:${String(result.count)} rows:${result.rows.map(row => row.id).join(",")}`}</p>;
}

describe("staff cross-links", () => {
  beforeEach(() => { api.staffRequest.mockReset(); api.staffRequest.mockImplementation(() => new Promise(() => {})); });

  it("builds a same-space console link and drops empty query values", () => {
    expect(staffHref("/m/lab/admin/inventory", "machines", { machine: 12, empty: "", none: null }))
      .toBe("/m/lab/admin/machines?machine=12");
    expect(staffHref("/admin/inventory", "incidents", { incident: 3 })).toBe("/admin/incidents?incident=3");
  });

  it("offers a link only into tabs this person can open (decision 224)", () => {
    const { rerender } = wrap(<Probe tab="incidents" />, ["machines"]);
    expect(screen.getByText("no link")).toBeInTheDocument();
    rerender(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/m/lab/admin/machines"]}>
      <AllowedTabsContext.Provider value={["incidents"]}><Probe tab="incidents" /></AllowedTabsContext.Provider></MemoryRouter></QueryClientProvider>);
    expect(screen.getByText("/m/lab/admin/incidents?machine=12")).toBeInTheDocument();
  });

  it("never passes unrelated incidents off as linked when the server ignores the filter", async () => {
    api.staffRequest.mockResolvedValue({ count: 3, next: null, previous: null,
      results: [{ id: 1, machine: 12, status: "reported" }, { id: 2, machine: 99, status: "reported" }, { id: 3, machine: 12, status: "closed" }] });
    wrap(<IncidentProbe subject="machine" />);
    expect(await screen.findByText("count:2 rows:1,3")).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/incidents?machine=12&page=1", expect.anything());
  });

  it("trusts the server's count for subjects the row does not carry", async () => {
    api.staffRequest.mockResolvedValue({ count: 7, next: null, previous: null, results: [{ id: 5, status: "reported" }] });
    wrap(<IncidentProbe subject="product" />);
    expect(await screen.findByText("count:7 rows:5")).toBeInTheDocument();
  });

  it("hides the incident block when the register is off or closed to this person", async () => {
    api.staffRequest.mockImplementation(() => Promise.reject(new StructuredApiError(404, { detail: "off" })));
    wrap(<IncidentProbe subject="machine" />);
    expect(await screen.findByText("hidden")).toBeInTheDocument();
  });

  it("renders related links with counts, a loading marker and an empty state", () => {
    const { rerender } = wrap(<RelatedLinks links={[{ key: "a", label: "Incidents", href: "/admin/incidents", count: 2 },
      { key: "b", label: "Jobs", href: "/admin/machines", count: null }]} />);
    expect(screen.getByRole("link", { name: /Incidents/ })).toHaveAttribute("href", "/admin/incidents");
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Loading count" })).toBeInTheDocument();
    rerender(<MemoryRouter><RelatedLinks links={[]} empty="Nothing here." /></MemoryRouter>);
    expect(screen.getByText("Nothing here.")).toBeInTheDocument();
  });
});
