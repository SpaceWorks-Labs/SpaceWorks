import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { publicV1Request, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useOptionalTenant } from "../../lib/tenant";
import { PublicHandlePage } from "./PublicHandlePage";

vi.mock("../../lib/api", async original => ({ ...(await original<typeof import("../../lib/api")>()), publicV1Request: vi.fn(), refreshAccessToken: vi.fn() }));
vi.mock("../../lib/tenant", async original => ({ ...(await original<typeof import("../../lib/tenant")>()), useOptionalTenant: vi.fn() }));

const shown = { status: true, about: true, experience: true, education: true, achievements: true, projects: true, skills: true, links: true, interests: true, events: true, spaces: true, certifications: true };
const profile = {
  audience: "public", handle: "ada", account_id: null, display_name: "Ada Lovelace", avatar_url: null, headline: "Analytical engines", institution: "", shown,
  status: null, bio: "Writes programs for machines.", timeline: [], education: [], skills: [], domains: [], links: [], interests: [], languages: [], projects: [],
  achievements: { verified: [], self_reported: [] }, events_attended: null, certifications: [], spaces: [], organizations: [],
};
const resolution = { kind: "member", handle: "ada", canonical_url: "http://localhost/ada", redirected: false, content_url: "/api/v1/public/profiles/ada/" };
const missing = () => new StructuredApiError(404, { detail: "Not found." });

function show(path = "/ada") {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/:handle" element={<PublicHandlePage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

describe("PublicHandlePage with global member handles", () => {
  beforeEach(() => {
    vi.mocked(publicV1Request).mockReset();
    vi.mocked(refreshAccessToken).mockReset().mockResolvedValue(false);
    vi.mocked(useOptionalTenant).mockReturnValue(null);
  });

  it("renders the global profile when the handle resolves to a member", async () => {
    vi.mocked(publicV1Request).mockImplementation(async (path: string) => path.startsWith("/public/page-handles/") ? resolution : profile);
    show();
    expect(await screen.findByRole("heading", { level: 1, name: "Ada Lovelace" })).toBeVisible();
    expect(screen.getByText("Writes programs for machines.")).toBeVisible();
    expect(publicV1Request).toHaveBeenCalledWith("/public/page-handles/ada/", expect.anything());
    expect(publicV1Request).toHaveBeenCalledWith("/public/profiles/ada/");
  });

  it("still reads the profile when the resolver refuses, so a signed-in member can open a profile that is not on the open web", async () => {
    vi.mocked(publicV1Request).mockImplementation(async (path: string) => { if (path.startsWith("/public/page-handles/")) throw missing(); return { ...profile, audience: "member" }; });
    show();
    expect(await screen.findByRole("heading", { level: 1, name: "Ada Lovelace" })).toBeVisible();
  });

  it("shows the shared not-found page when neither the resolver nor the profile read finds the handle", async () => {
    vi.mocked(publicV1Request).mockImplementation(async () => { throw missing(); });
    show("/nobody");
    expect(await screen.findByRole("heading", { name: "Loan slip not found" })).toBeVisible();
  });

  it("never asks the server about a handle that breaks the grammar", () => {
    show("/-bad-");
    expect(screen.getByRole("heading", { name: "Loan slip not found" })).toBeVisible();
    expect(publicV1Request).not.toHaveBeenCalled();
  });
});
