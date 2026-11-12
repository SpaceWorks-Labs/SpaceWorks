import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FeatureModulePage } from "./FeatureModulePage";
import { FeaturesPage } from "../FeaturesPage";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/api", () => ({ publicV1Request: request }));
vi.mock("../../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false, isPending: false }) }));
vi.mock("../../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/features" element={<FeaturesPage />} /><Route path="/features/:module" element={<FeatureModulePage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

// Decision 306 (c): the features pages work whether the landing switch (HUB_LANDING_ENABLED) is on or off.
describe.each([[true], [false]])("features pages with landing_enabled = %s", enabled => {
  beforeEach(() => { request.mockReset(); request.mockResolvedValue({ landing_enabled: enabled }); });

  it("render the overview", async () => {
    renderAt("/features");
    expect(await screen.findByRole("heading", { level: 1, name: /module by module/ })).toBeInTheDocument();
  });

  it("render a module page", async () => {
    renderAt("/features/machines");
    expect(await screen.findByRole("heading", { level: 1, name: "Machines" })).toBeInTheDocument();
  });
});
