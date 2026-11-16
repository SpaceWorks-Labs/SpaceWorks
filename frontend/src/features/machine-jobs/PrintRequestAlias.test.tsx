import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { TenantProvider } from "../../lib/tenant";
import { PrintRequestAlias } from "./PrintRequestAlias";

const space = vi.hoisted(() => ({ features: ["machines.job_requests"] }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ isLoading: false, isError: false,
  data: { makerspace: { slug: "lab" }, features: space.features, modules: [] } }) }));
vi.mock("../printing/PublicPrintRequestPage", () => ({ PublicPrintRequestPage: () => <p>Old print form</p> }));

function Where() { const location = useLocation(); return <p>{location.pathname + location.search}</p>; }
function show(url: string) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[url]}><TenantProvider><Routes>
    <Route path="/m/:slug/print" element={<PrintRequestAlias />} />
    <Route path="*" element={<Where />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

describe("PrintRequestAlias", () => {
  it("sends an old tracking link to the status page", () => {
    show("/m/lab/print?token=abc");
    expect(screen.getByText("/m/lab/machine-service/requests/abc")).toBeInTheDocument();
  });
  it("opens the job form with the printer chosen", () => {
    show("/m/lab/print");
    expect(screen.getByText("/m/lab/machine-jobs/new?type=printer")).toBeInTheDocument();
  });
  it("keeps the old form where job requests are off", () => {
    space.features = [];
    show("/m/lab/print");
    expect(screen.getByText("Old print form")).toBeInTheDocument();
  });
});
