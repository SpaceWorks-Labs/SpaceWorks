import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MakerspaceDiscovery } from "./MakerspaceDiscovery";

const { fetchPublicMakerspaces, tenant } = vi.hoisted(() => ({ fetchPublicMakerspaces: vi.fn(), tenant: { mode: "central" as "central" | "single" } }));
vi.mock("../inventory/api", () => ({ fetchPublicMakerspaces }));
vi.mock("../../lib/tenant", async (original) => ({ ...await original<typeof import("../../lib/tenant")>(), useOptionalTenant: () => tenant }));

const space = (slug: string, name: string, location = "") => ({ slug, name, location, public_code: slug.toUpperCase(), map_url: "", logo_url: null, cover_image_url: null });
function show(props: Partial<Parameters<typeof MakerspaceDiscovery>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}><MakerspaceDiscovery currentSlug="alpha" {...props} /></QueryClientProvider></MemoryRouter>);
}
beforeEach(() => { tenant.mode = "central"; fetchPublicMakerspaces.mockReset(); });

describe("Find a makerspace", () => {
  it("lists other directory spaces, marks memberships and pending requests, and links to each space", async () => {
    fetchPublicMakerspaces.mockResolvedValue([space("alpha", "Alpha Lab"), space("beta", "Beta Works", "Kochi"), space("gamma", "Gamma Shop"), space("delta", "Delta Den")]);
    show({ memberships: [{ makerspace: { slug: "beta" }, membership_status: "active" }], requests: [{ makerspace: { slug: "gamma" }, state: "pending" }] });
    const list = await screen.findByRole("list");
    expect(within(list).queryByText("Alpha Lab")).toBeNull();
    expect(within(list).getByRole("link", { name: /Beta Works/ })).toHaveAttribute("href", "/m/beta/member");
    expect(within(list).getByText("Member")).toBeVisible();
    expect(within(list).getByText("Request pending")).toBeVisible();
    expect(within(list).getByRole("link", { name: /Delta Den/ })).toHaveAttribute("href", "/m/delta/member");
  });

  it("searches once the directory is long", async () => {
    fetchPublicMakerspaces.mockResolvedValue(["a", "b", "c", "d", "e", "f", "g"].map(key => space(key, `Space ${key.toUpperCase()}`, key === "c" ? "Kochi" : "")));
    show({ currentSlug: "none" });
    fireEvent.change(await screen.findByRole("searchbox", { name: "Search makerspaces" }), { target: { value: "kochi" } });
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText("Space C")).toBeVisible();
  });

  it("never lists other spaces on a single-tenant domain", () => {
    tenant.mode = "single";
    show();
    expect(screen.queryByText("Find a makerspace")).toBeNull();
    expect(fetchPublicMakerspaces).not.toHaveBeenCalled();
  });

  it("offers a retry when the directory fails to load", async () => {
    fetchPublicMakerspaces.mockRejectedValue(new Error("down"));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("We couldn't load the makerspace list.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});
