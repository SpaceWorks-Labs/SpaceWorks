import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { publicV1Request, refreshAccessToken, setAccessToken, clearAccessToken, StructuredApiError } from "../../lib/api";
import { useOptionalTenant } from "../../lib/tenant";
import type { AccountProfile } from "./accountProfileTypes";
import { PublicProfilePage } from "./PublicProfilePage";
import { publicProfileKeys } from "./publicProfileApi";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), publicV1Request: vi.fn(), refreshAccessToken: vi.fn() }));
vi.mock("../../lib/tenant", async original => ({ ...(await original<typeof import("../../lib/tenant")>()), useOptionalTenant: vi.fn() }));

const shown = { status: true, about: true, experience: true, education: true, achievements: true, projects: true, skills: true, links: true, interests: true, events: true, spaces: true, certifications: true };
export const base: AccountProfile = {
  audience: "member", handle: "shaan.s", account_id: 12, display_name: "Shaan Shoukath", avatar_url: null,
  headline: "Builds robots", institution: "School of Engineering CUSAT", shown,
  status: { preset: "open_to_collaborate", note: "Looking for a laser buddy" }, bio: "Nothing much here..",
  timeline: [
    { id: 1, kind: "experience", title: "Hardware intern", organization: "Acme", location: "Kochi", start: "2024-01-01", end: null, description: "", order: 0 },
    { id: 2, kind: "education", title: "B.Tech, Electronics", organization: "CUSAT", location: "Kochi", start: "2023-08-01", end: null, description: "", order: 0 },
  ],
  education: [], skills: [{ name: "Python", level: 3 }], domains: ["AI", "Robotics"], links: [{ kind: "GitHub", url: "https://github.com/shaan" }],
  interests: ["Gliders"], languages: ["English"],
  projects: [{ id: 1, title: "Line follower", subtitle: "", tags: ["robots"], public_visible: true, description: "A fast one", links: [], image_url: null, imported: false }],
  achievements: {
    verified: [{ kind: "award", event_title: "HackFest", verified_by: "Space A", occurred_on: "2026-01-02", rank: 1, prize_name: "Best build" }],
    self_reported: [{ id: 5, title: "Robotics club lead", issuer: "CUSAT", achieved_on: null, url: "", description: "", order: 0 }],
  },
  events_attended: { count: 3, recent: [{ id: 1, title: "Laser night", starts_at: "2026-06-26T20:00:00Z", space_name: "Space A" }] },
  certifications: [{ name: "Laser basics", space_name: "Space A" }],
  spaces: [{ slug: "space-a", name: "Space A", kind: "makerspace", role_title: "Member" }],
  organizations: [{ slug: "guild", name: "Maker Guild", source: "explicit" }],
};
const missing = () => new StructuredApiError(404, { detail: "Not found." });

function serve(profile: AccountProfile | Error) {
  vi.mocked(publicV1Request).mockImplementation(async () => { if (profile instanceof Error) throw profile; return profile; });
}
function show(path = "/shaan.s") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/:handle" element={<PublicProfilePage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

describe("PublicProfilePage", () => {
  afterEach(() => vi.unstubAllGlobals());
  beforeEach(() => {
    vi.mocked(publicV1Request).mockReset(); window.localStorage.clear(); clearAccessToken();
    vi.mocked(refreshAccessToken).mockReset().mockResolvedValue(false);
    vi.mocked(useOptionalTenant).mockReturnValue(null);
  });

  it("renders a signed-in member's view as a résumé in the agreed section order", async () => {
    serve(base); show();
    expect(await screen.findByRole("heading", { level: 1, name: "Shaan Shoukath" })).toBeVisible();
    expect(screen.getByText("@shaan.s")).toBeVisible();
    const order = ["Status", "About", "Spaces and organizations", "Experience", "Education", "Achievements", "Certifications", "Projects", "Events attended", "Skills", "Interests and languages", "Links"];
    expect(screen.getAllByRole("heading", { level: 2 }).map(heading => heading.textContent)).toEqual(order);
    expect(screen.getByText("Open to collaborate")).toBeVisible();
    expect(screen.getByRole("link", { name: "Space A" })).toHaveAttribute("href", "/m/space-a");
    expect(screen.getByRole("link", { name: "GitHub (opens in a new tab)" })).toHaveAttribute("href", "https://github.com/shaan");
    expect(screen.getByRole("img", { name: "Fluent (3 of 3)" })).toBeVisible();
    // A signed-in other user never sees owner controls or the share button.
    expect(screen.queryByRole("link", { name: "Edit profile" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
    expect(screen.queryByText("Hidden from others")).toBeNull();
  });

  it("labels verified achievements with the vouching space and self-reported ones as such", async () => {
    serve(base); show();
    const list = within(await screen.findByRole("region", { name: "Achievements" }));
    expect(list.getByText("Won Best build at HackFest")).toBeVisible();
    expect(list.getByText("Verified by Space A")).toBeVisible();
    expect(list.getByText("Robotics club lead")).toBeVisible();
    expect(list.getByText("Self-reported")).toBeVisible();
  });

  it("gives the owner an edit link, hidden-section markers and the share button when on the open web", async () => {
    serve({ ...base, audience: "owner", public_visible: true, is_visible: true, shown: { ...shown, skills: false } }); show();
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/member/profile");
    expect(screen.getByRole("button", { name: "Share" })).toBeVisible();
    expect(within(screen.getByRole("region", { name: "Skills" })).getByText("Hidden from others")).toBeVisible();
  });

  it("shows a logged-out visitor the open-web profile with its share button and meta tags", async () => {
    serve({ ...base, audience: "public" }); show();
    expect(await screen.findByRole("heading", { level: 1, name: "Shaan Shoukath" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Share" })).toBeVisible();
    expect(document.querySelector('meta[property="og:title"]')).toHaveAttribute("content", "Shaan Shoukath");
    expect(screen.queryByRole("link", { name: "Edit profile" })).toBeNull();
  });

  it("adds no share card or meta tags for a signed-in member's view", async () => {
    serve(base); show();
    await screen.findByRole("heading", { level: 1 });
    expect(document.querySelector('meta[property="og:title"]')).toBeNull();
  });

  it("names vouchers only when the server did, and counts the rest", async () => {
    serve({ ...base, vouched_by: [{ handle: "rishi", display_name: "Rishi", space_name: "Space A" }], vouched_count: 3 }); show();
    const spaces = within(await screen.findByRole("region", { name: "Spaces and organizations" }));
    expect(spaces.getByRole("link", { name: "Rishi" })).toHaveAttribute("href", "/rishi");
    expect(spaces.getByText(/2 more vouches/)).toBeVisible();
  });

  it("renders a logged-out reader's payload, whose row ids and account id are absent", async () => {
    serve({ ...base, audience: "public", account_id: null, timeline: base.timeline.map(({ id: _id, ...row }) => row),
      projects: base.projects.map(({ id: _id, ...row }) => row) }); show();
    expect(await screen.findByRole("heading", { level: 1, name: "Shaan Shoukath" })).toBeVisible();
    expect(screen.getByText("Hardware intern")).toBeVisible();
    expect(screen.getByText("Line follower")).toBeVisible();
  });

  it("shows the account-level activity graph and GitHub calendar only when graph families are on", async () => {
    const days = [{ date: "2026-10-01", count: 2 }, { date: "2026-10-02", count: 1 }];
    vi.mocked(publicV1Request).mockImplementation(async (path: string) => path.endsWith("/activity") ? { from: "2026-10-01", to: "2026-10-02", timezone: "UTC", days }
      : path.endsWith("/github") ? { source: "github", days } : { ...base, github_username: "shaan", github_verified: true, activity_shown: { activity_graph: true, speaking: false, machine_activity: false, bookings: false, loans: false } });
    show();
    expect(await screen.findByRole("img", { name: /Activity on Space Works: 3 activities/ })).toBeVisible();
    expect(await screen.findByRole("img", { name: /GitHub contributions: 3 contributions/ })).toBeVisible();
  });

  it("never asks for graphs when none are shown", async () => {
    serve(base); show();
    await screen.findByRole("heading", { level: 1 });
    expect(vi.mocked(publicV1Request).mock.calls.map(([path]) => path)).toEqual(["/public/profiles/shaan.s/"]);
  });

  it("lists the events history (hosted, spoke, attended) on request", async () => {
    vi.mocked(publicV1Request).mockImplementation(async (path: string) => path.includes("/events?page=1")
      ? { count: 2, next: null, previous: null, results: [
        { title: "Game night", starts_at: "2026-06-26T20:00:00Z", ends_at: "2026-06-26T22:00:00Z", badge: "HOSTED", host: "Lab" },
        { title: "My talk", starts_at: "2026-06-20T20:00:00Z", ends_at: "2026-06-20T21:00:00Z", badge: "SPOKE", host: "Lab" }] } : base);
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Show events history" }));
    expect(await screen.findByText("Game night")).toBeVisible();
    expect(screen.getByText("Hosted")).toBeVisible();
    expect(screen.getByText("Spoke")).toBeVisible();
  });

  it("omits sections the server emptied for this audience", async () => {
    serve({ ...base, bio: "", status: null, projects: [], skills: [], domains: [], events_attended: null }); show();
    await screen.findByRole("heading", { level: 1 });
    for (const name of ["Status", "About", "Projects", "Events attended", "Skills"]) expect(screen.queryByRole("region", { name })).toBeNull();
  });

  it("partitions the personalized profile response by viewer", () => {
    const signedOut = publicProfileKeys.root("shaan.s");
    const token = (user_id: number) => `header.${btoa(JSON.stringify({ user_id }))}.signature`;
    setAccessToken(token(1));
    const owner = publicProfileKeys.root("shaan.s");
    setAccessToken(token(2));
    expect(publicProfileKeys.root("shaan.s")).not.toEqual(owner);
    expect(owner).not.toEqual(signedOut);
    clearAccessToken();
    expect(publicProfileKeys.root("shaan.s")).toEqual(signedOut);
  });

  it("restores the optional cookie session before requesting the profile on a direct page load", async () => {
    let finish!: (value: boolean) => void;
    vi.mocked(refreshAccessToken).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    serve({ ...base, audience: "owner" }); show();
    expect(publicV1Request).not.toHaveBeenCalled();
    finish(true);
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/member/profile");
    expect(publicV1Request).toHaveBeenCalledWith("/public/profiles/shaan.s/");
  });

  it("keeps the public page available if restoring an optional session fails", async () => {
    vi.mocked(refreshAccessToken).mockRejectedValue(new Error("Offline"));
    serve({ ...base, audience: "public" }); show();
    expect(await screen.findByRole("heading", { level: 1 })).toBeVisible();
  });

  it("follows a retired handle to the member's current address", async () => {
    serve({ ...base, handle: "new.name" }); show("/shaan.s");
    await screen.findByText("@new.name");
    // The page then moves to the current address (replace, so Back does not return to the retired one).
    await waitFor(() => expect(screen.getByText("@new.name")).toBeVisible());
  });

  // Delight is on by default, so the shared not-found page shows its loan-slip title.
  it("renders the shared not-found page for an unknown or unpublished handle", async () => {
    serve(missing()); show("/nobody");
    expect(await screen.findByRole("heading", { name: "Loan slip not found" })).toBeVisible();
  });

  it("never requests a handle that breaks the grammar", () => {
    serve(base); show("/-bad-");
    expect(screen.getByRole("heading", { name: "Loan slip not found" })).toBeVisible();
    expect(publicV1Request).not.toHaveBeenCalled();
  });

  it("offers a retry when the profile fails to load for another reason", async () => {
    serve(new StructuredApiError(503, {})); show();
    // One automatic retry runs first (only a 404 skips it).
    expect(await screen.findByText(/Couldn't load this profile/, {}, { timeout: 4000 })).toBeVisible();
    expect(screen.getByRole("button", { name: /Try again|Retry/ })).toBeVisible();
  });
});
