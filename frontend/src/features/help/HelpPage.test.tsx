import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StaffAuthUser } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import { HelpPage } from "./HelpPage";

const state = vi.hoisted(() => ({
  user: null as StaffAuthUser | null,
  tenant: { mode: "central" } as Record<string, unknown>,
  bootstrap: undefined as Record<string, unknown> | undefined,
}));

vi.mock("../../lib/api", async () => ({
  ...await vi.importActual("../../lib/api"),
  refreshAccessToken: async () => Boolean(state.user),
  fetchMe: async () => state.user,
}));
vi.mock("../../lib/tenant", () => ({ useTenant: () => state.tenant }));
vi.mock("../inventory/usePublicInventory", () => ({
  useTenantBootstrap: () => ({ data: state.bootstrap, isLoading: false, isError: false }),
}));
vi.mock("../NotFoundPage", () => ({ NotFoundPage: () => <p>Page not found</p> }));

function bootstrap(features: string[], modules: string[] = ["request_workflow"]) {
  return { makerspace: { id: 1, slug: "tinkerspace", name: "Tinkerspace" }, branding: { display_name: "Tinkerspace" }, modules, features };
}

function technician(): StaffAuthUser {
  return { username: "tech", email_verified: true, role: "staff", is_superuser: false, must_change_password: false, kind: "person",
    makerspaces: [{ id: 1, slug: "tinkerspace", role: null, role_id: null, role_ids: [], role_slugs: ["technician"], role_names: ["Technician"],
      role_name: "Technician", role_slug: "technician", source: "membership", actions: ["work_repairs", "run_maintenance", "set_service_state"],
      can_configure_machine_types: false, is_machine_only: false, can_refer: false, can_verify: false, verified_at: null, referrals_enabled: false }] };
}

function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/help" element={<HelpPage />} />
    <Route path="/help/:sectionId" element={<HelpPage />} />
    <Route path="/help/:sectionId/:articleSlug" element={<HelpPage />} />
    <Route path="/m/:slug/help" element={<HelpPage />} />
    <Route path="/m/:slug/help/:sectionId/:articleSlug" element={<HelpPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  state.user = null; state.tenant = { mode: "central" }; state.bootstrap = undefined;
});

describe("/help", () => {
  it("shows a visitor the member guides only, with search over them", async () => {
    const { container } = open("/help");
    expect(await screen.findByRole("heading", { level: 1, name: "How can we help?" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Members and visitors" })).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Technician" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Space Manager" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Search the guide"), { target: { value: "stocktake" } });
    expect(screen.getByText("0 articles match")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search the guide"), { target: { value: "borrow" } });
    expect(screen.getByRole("list", { name: "Search results" })).toHaveTextContent("Borrow tools from Inventory");
    await expectNoA11yViolations(container);
  });

  it("shows a Technician their section", async () => {
    state.user = technician();
    open("/help");
    expect(await screen.findByRole("heading", { name: "Technician" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Finance" })).toBeNull();
  });

  it("resolves a deep link to an article, with steps and no uncaptured screenshot placeholder", async () => {
    state.user = technician();
    const { container } = open("/help/technician/your-jobs");
    expect(await screen.findByRole("heading", { level: 1, name: "Your repair jobs" })).toBeInTheDocument();
    await waitFor(() => expect(container.querySelector("ol li")).not.toBeNull());
    expect(container.querySelector("[data-screenshot='tech-repair-job']")).toBeNull();
    expect(screen.getAllByRole("link", { name: "Help" })[0]).toHaveAttribute("href", "/help");
    await expectNoA11yViolations(container);
  });

  it("explains a staff article to a member instead of showing it", async () => {
    open("/help/finance/refunds");
    expect(await screen.findByText(/This article is written for/)).toBeInTheDocument();
    expect(screen.queryByText(/Decide a case/)).toBeNull();
  });

  it("answers page not found for a space that switched the help centre off", async () => {
    state.tenant = { mode: "single", loading: false, bootstrap: bootstrap(["ui.delight"]) };
    open("/help");
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
  });

  it("serves a space's guide when its switch is on, hiding what it doesn't run", async () => {
    state.bootstrap = bootstrap(["platform.help_centre"]);
    open("/m/tinkerspace/help/member/book-a-room");
    expect(await screen.findByText(/feature this space has not switched on/)).toBeInTheDocument();
  });

  it("says so for an article that doesn't exist", async () => {
    open("/help/member/no-such-article");
    expect(await screen.findByRole("heading", { name: "We couldn't find that article" })).toBeInTheDocument();
  });
});
