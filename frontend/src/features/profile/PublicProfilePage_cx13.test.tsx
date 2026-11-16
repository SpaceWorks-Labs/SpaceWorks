import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { refreshAccessToken, StructuredApiError } from "../../lib/api";
import { publicAnonymousRequest } from "../../lib/api/requests";
import { formatDate } from "../../lib/format";
import { useOptionalTenant } from "../../lib/tenant";
import { PublicProfilePage } from "./PublicProfilePage";
import type { PublicAccountCard } from "./publicProfileApi";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(),
  refreshAccessToken: vi.fn() }));
vi.mock("../../lib/api/requests", async original => ({ ...await original<typeof import("../../lib/api/requests")>(), publicAnonymousRequest: vi.fn() }));
vi.mock("../../lib/tenant", async original => ({ ...await original<typeof import("../../lib/tenant")>(), useOptionalTenant: vi.fn() }));

const profile: PublicAccountCard = {
  display_name: "Maker 名", avatar_url: "https://example.test/avatar.png", handle: "maker.name", bio: "Builds things",
  projects: [{ title: "Robot", subtitle: "A build", description: "Made together", tags: ["hardware"],
    image_url: null, links: [{ kind: "Code", url: "https://example.test/code" }] }],
  memberships: [{ slug: "public-lab", name: "Public lab", role_title: "Member", started_on: "2025-01-02" }],
};

function Location() { return <output data-testid="location">{useLocation().pathname}</output>; }
function show(path = "/@maker.name") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/:handle" element={<><PublicProfilePage /><Location /></>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

describe("always-on public profile (549 / CX13)", () => {
  beforeEach(() => {
    vi.mocked(publicAnonymousRequest).mockReset(); vi.mocked(refreshAccessToken).mockReset();
    vi.mocked(useOptionalTenant).mockReset().mockReturnValue(null);
  });

  it.each(["light", "dark"])("renders the permitted card and memberships in %s theme", async theme => {
    document.documentElement.dataset.theme = theme;
    vi.mocked(publicAnonymousRequest).mockResolvedValue(profile);
    show();
    expect(await screen.findByRole("heading", { name: "Maker 名", level: 1 })).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 2 }).map(row => row.textContent)).toEqual(["About", "Projects", "Memberships"]);
    expect(screen.getByText("Member")).toBeVisible();
    expect(screen.getByText(/^Member since /)).toBeVisible();
    expect(screen.getByRole("link", { name: "Public lab" })).toHaveAttribute("href", "/m/public-lab");
    expect(screen.getByRole("link", { name: "Code" })).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByRole("link", { name: "Edit profile" })).toBeNull();
    expect(publicAnonymousRequest).toHaveBeenCalledExactlyOnceWith("/public/profiles/maker.name/");
    expect(refreshAccessToken).not.toHaveBeenCalled();
    delete document.documentElement.dataset.theme;
  });

  it("links only the bound membership on a single-space host and retains other spaces' role and since-date", async () => {
    vi.mocked(useOptionalTenant).mockReturnValue({ mode: "single", loading: false, error: null,
      bootstrap: null, slug: "public-lab", makerspaceId: 1, modules: new Set() });
    vi.mocked(publicAnonymousRequest).mockResolvedValue({ ...profile, memberships: [
      ...profile.memberships!,
      { slug: "other-lab", name: "Other lab", role_title: "Inventory Manager", started_on: "2024-03-04" },
    ] });
    show();
    const bound = await screen.findByRole("link", { name: "Public lab" });
    expect(bound).toHaveAttribute("href", "/");
    const boundRow = within(bound.closest("li")!);
    expect(boundRow.getByText("Member")).toBeVisible();
    expect(boundRow.getByText(`Member since ${formatDate("2025-01-02", { dateStyle: "medium", timeZone: "UTC" })}`)).toBeVisible();
    const other = screen.getByText("Other lab");
    expect(other).toBeVisible();
    const otherRow = within(other.closest("li")!);
    expect(otherRow.getByText("Inventory Manager")).toBeVisible();
    expect(otherRow.getByText(`Member since ${formatDate("2024-03-04", { dateStyle: "medium", timeZone: "UTC" })}`)).toBeVisible();
    expect(screen.queryByRole("link", { name: "Other lab" })).toBeNull();
    expect(otherRow.queryByRole("link")).toBeNull();
  });

  it("renders only a name and avatar for a minimal card", async () => {
    vi.mocked(publicAnonymousRequest).mockResolvedValue({ display_name: "Young Maker", avatar_url: profile.avatar_url });
    const { container } = show();
    expect(await screen.findByRole("heading", { name: "Young Maker", level: 1 })).toBeVisible();
    const article = container.querySelector("article")!;
    expect(article.querySelectorAll("img")).toHaveLength(1);
    expect(article.querySelectorAll("section")).toHaveLength(0);
    expect(article.textContent).toBe("Young Maker");
  });

  it("omits empty sections and renders hostile input as text", async () => {
    vi.mocked(publicAnonymousRequest).mockResolvedValue({ ...profile, bio: "<script>secret()</script>", projects: [], memberships: [] });
    const { container } = show();
    expect(await screen.findByText("<script>secret()</script>")).toBeVisible();
    expect(container.querySelector("article script")).toBeNull();
    expect(screen.getAllByRole("heading", { level: 2 }).map(row => row.textContent)).toEqual(["About"]);
  });

  it("uses the new canonical address after a handle redirect", async () => {
    vi.mocked(publicAnonymousRequest).mockResolvedValue({ ...profile, handle: "new.name" });
    show();
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/@new.name"));
    expect(await screen.findByText("@new.name")).toBeVisible();
  });

  it("shows the loading state while the request is pending", () => {
    vi.mocked(publicAnonymousRequest).mockReturnValue(new Promise(() => {}));
    const { container } = show();
    expect(container.querySelector("article")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Maker 名" })).toBeNull();
  });

  it("shows not-found for the exact missing-handle error", async () => {
    vi.mocked(publicAnonymousRequest).mockRejectedValue(new StructuredApiError(404, { code: "not_found", detail: "Not found." }));
    show();
    expect(await screen.findByRole("heading", { name: "Loan slip not found" })).toBeVisible();
    expect(publicAnonymousRequest).toHaveBeenCalledTimes(1);
  });

  it("does not send an invalid handle to the API", () => {
    show("/@bad!");
    expect(screen.getByRole("heading", { name: "Loan slip not found" })).toBeVisible();
    expect(publicAnonymousRequest).not.toHaveBeenCalled();
  });

  it("offers retry after a transient failure and then displays the card", async () => {
    vi.mocked(publicAnonymousRequest).mockRejectedValue(new StructuredApiError(503, {}));
    show();
    const retry = await screen.findByRole("button", { name: /Try again|Retry/ });
    expect(publicAnonymousRequest).toHaveBeenCalledTimes(2);
    vi.mocked(publicAnonymousRequest).mockResolvedValue(profile);
    fireEvent.click(retry);
    expect(await screen.findByRole("heading", { name: "Maker 名" })).toBeVisible();
    expect(publicAnonymousRequest).toHaveBeenCalledTimes(3);
  });
});
