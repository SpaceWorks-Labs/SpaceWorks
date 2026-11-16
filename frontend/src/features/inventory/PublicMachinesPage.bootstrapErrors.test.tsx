import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { bootstrapTenant, StructuredApiError, tenantPublicRequest, type TenantBootstrap } from "../../lib/api";
import { PublicMachinesPage } from "./PublicMachinesPage";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  bootstrapTenant: vi.fn(), tenantPublicRequest: vi.fn(),
}));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "central" }), useTenantPath: () => (path: string) => `/m/lab/${path}` }));
vi.mock("../../lib/useTenantBranding", () => ({ useTenantBranding: () => ({}) }));

const bootstrap: TenantBootstrap = {
  makerspace: { id: 1, slug: "lab", name: "Lab", public_code: "LAB", location: "", geofence_enabled: false, membership_policy: "open" },
  frontend: { type: "central", hostname: "", allowed_origins: [] }, modules: ["machines"], features: [], workflows: [],
  theme: {}, branding: {}, email_enabled: false, public_api: { base_url: "", publishable_key: "", inventory_path: "" },
};

beforeEach(() => { vi.mocked(bootstrapTenant).mockReset(); vi.mocked(tenantPublicRequest).mockReset(); });

it.each([[503, "service_unavailable"], [403, "permission_denied"], [404, "not_found"]] as const)(
  "shows the central bootstrap %s %s and retries only an outage", async (status, code) => {
    vi.mocked(bootstrapTenant).mockRejectedValue(new StructuredApiError(status, { code, detail: `Bootstrap ${code}` }));
    vi.mocked(tenantPublicRequest).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/machines"]}><Routes>
      <Route path="/m/:slug/machines" element={<PublicMachinesPage />} />
    </Routes></MemoryRouter></QueryClientProvider>);
    await screen.findByRole("alert");
    const state = client.getQueryState(["tenant-bootstrap", "lab"]);
    expect([state?.status, (state?.error as StructuredApiError).status, (state?.error as StructuredApiError).code])
      .toEqual(["error", status, code]);
    expect(bootstrapTenant).toHaveBeenCalledTimes(1);
    expect(tenantPublicRequest).not.toHaveBeenCalled();
    if (status === 503) {
      vi.mocked(bootstrapTenant).mockResolvedValue(bootstrap);
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
      await screen.findByText("No machines listed yet. Check back soon.");
      expect(bootstrapTenant).toHaveBeenCalledTimes(2);
      expect(tenantPublicRequest).toHaveBeenCalledTimes(1);
      expect(tenantPublicRequest).toHaveBeenCalledWith("lab", "/public/lab/machines?page=1&page_size=24");
      await waitFor(() => expect(client.getQueryState(["tenant-bootstrap", "lab"])?.status).toBe("success"));
      expect(screen.queryByRole("alert")).toBeNull();
    } else {
      expect(screen.getByRole("alert")).toHaveTextContent(status === 404 ? "We couldn't find this makerspace. Check the link." : "Bootstrap permission_denied");
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
      expect(screen.queryByText(/Try again|wait a moment|service is unavailable/i)).toBeNull();
    }
  },
);
