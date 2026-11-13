import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { FamilyHome } from "./FamilyHome";

const { tenant, query } = vi.hoisted(() => ({ tenant: vi.fn(), query: vi.fn() }));
vi.mock("../../lib/tenant", () => ({ useTenant: tenant }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: query }));
vi.mock("./MakerspacePage", () => ({ MakerspacePage: () => <h1>Space home</h1> }));

function bootstrap(extra: Partial<TenantBootstrap["makerspace"]> = {}): TenantBootstrap {
  return {
    makerspace: { id: 1, name: "Chess Club", slug: "chess", public_code: "CHES", location: "", geofence_enabled: false,
      membership_policy: "request", public_site_enabled: true, ...extra },
    modules: ["events", "bookings", "membership"], features: [], workflows: [], edition: "makerspace",
    frontend: { type: "makerspace", hostname: "", allowed_origins: [] }, theme: {}, branding: {}, email_enabled: false,
    public_api: { base_url: "/api/v1", publishable_key: "pk_test", inventory_path: "" },
  };
}

function show(data: TenantBootstrap, mode: "central" | "single" = "central") {
  tenant.mockReturnValue({ mode, bootstrap: mode === "single" ? data : null });
  query.mockReturnValue({ data });
  const OrgPage = () => <h1>Organization page {useParams().organizationSlug}</h1>;
  return render(<MemoryRouter initialEntries={[mode === "single" ? "/" : "/m/chess"]}><Routes>
    <Route path="/" element={<FamilyHome />} />
    <Route path="/m/:slug" element={<FamilyHome />} />
    <Route path="/o/:organizationSlug" element={<OrgPage />} />
  </Routes></MemoryRouter>);
}

beforeEach(() => vi.clearAllMocks());

it("sends an organization workspace's /m/ home to its public organization page (decision 295)", async () => {
  show(bootstrap({ kind: "organization", space_noun: "organization", organization_page_slug: "chess-society" }));
  expect(await screen.findByRole("heading", { name: "Organization page chess-society" })).toBeVisible();
});

it("keeps the /m/ page while the organization page is not public", () => {
  show(bootstrap({ kind: "organization", space_noun: "organization", organization_page_slug: null }));
  expect(screen.getByRole("heading", { name: "Space home" })).toBeVisible();
});

it("never redirects a makerspace, whose bootstrap has no kind keys", () => {
  show(bootstrap());
  expect(screen.getByRole("heading", { name: "Space home" })).toBeVisible();
});

it("leaves a single-tenant root on its own domain", () => {
  show(bootstrap({ kind: "organization", space_noun: "organization", organization_page_slug: "chess-society" }), "single");
  expect(screen.getByRole("heading", { name: "Space home" })).toBeVisible();
});
