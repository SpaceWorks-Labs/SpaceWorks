import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bootstrapTenant, memberRequest, tenantMemberRequest, publicV1Request, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { PublicProfilePage } from "./PublicProfilePage";
import type { PublicProfile } from "./publicProfileApi";
import { publicProfileKeys } from "./publicProfileApi";
import { setAccessToken, clearAccessToken } from "../../lib/api";
import { useOptionalTenant } from "../../lib/tenant";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()),
  publicV1Request: vi.fn(), memberRequest: vi.fn(), tenantMemberRequest: vi.fn(), bootstrapTenant: vi.fn(), refreshAccessToken: vi.fn() }));
vi.mock("../../lib/tenant", async original => ({ ...(await original<typeof import("../../lib/tenant")>()), useOptionalTenant: vi.fn() }));

const base: PublicProfile = {
  viewer_is_owner: false,
  handle: "shaan.s", display_name: "Shaan Shoukath", avatar_url: null, verified: true, headline: "Builds robots",
  institution: "School of Engineering CUSAT", bio: "Nothing much here..", domains: ["AI", "Robotics"],
  skills: [{ name: "Python", level: 3 }, { name: "C++", level: 2 }], links: [{ kind: "GitHub", url: "https://github.com/shaan" }],
  timeline: [{ kind: "education", title: "B.Tech, Electronics", organization: "CUSAT", location: "Kochi", start: "2023-08-01", end: null, description: "", order: 0 }],
  projects: [], vouched_by: [{ handle: "rishi", display_name: "Rishi" }], vouched_count: 10,
  show_activity_graph: true, show_events: true, show_speaking: false, show_projects: false,
  show_machine_activity: false, show_bookings: false, show_loans: false,
};
const days = [{ date: "2026-10-01", count: 2 }, { date: "2026-10-02", count: 0 }, { date: "2026-10-03", count: 1 }];
const missing = () => new StructuredApiError(404, { detail: "Not found." });

function serve(profile: PublicProfile | Error, { github = true, events = [] as unknown[], projects = [] as unknown[] } = {}) {
  vi.mocked(publicV1Request).mockImplementation(async (path: string) => {
    if (path.endsWith("/activity")) return { from: "2026-06-05", to: "2026-10-02", timezone: "UTC", days };
    if (path.endsWith("/github")) { if (!github) throw missing(); return { days, total: 3 }; }
    if (path.includes("/events")) return { count: events.length, next: null, previous: null, results: events };
    if (path.includes("/projects")) return { count: projects.length, next: null, previous: null, results: projects };
    if (profile instanceof Error) throw profile;
    return profile;
  });
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
    vi.mocked(memberRequest).mockReset().mockResolvedValue({ memberships: [{ makerspace: { slug: "lab" }, membership_status: "active" }] });
    vi.mocked(bootstrapTenant).mockReset().mockResolvedValue({ makerspace: { id: 3 }, modules: ["membership"] } as Awaited<ReturnType<typeof bootstrapTenant>>);
    vi.mocked(tenantMemberRequest).mockReset().mockResolvedValue({ handle: base.handle });
    vi.mocked(useOptionalTenant).mockReturnValue(null);
  });

  it("renders the header, skills and both separately labelled graphs", async () => {
    serve(base); show();
    expect(await screen.findByRole("heading", { level: 1, name: "Shaan Shoukath" })).toBeVisible();
    expect(screen.getByText("@shaan.s")).toBeVisible();
    expect(screen.getByRole("img", { name: "Verified member" })).toBeVisible();
    expect(within(screen.getByRole("list", { name: "Domains" })).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "GitHub (opens in a new tab)" })).toHaveAttribute("href", "https://github.com/shaan");
    expect(screen.getByRole("link", { name: /Rishi/ })).toHaveAttribute("href", "/rishi");
    expect(screen.getByText("10 makers")).toBeVisible();
    expect(screen.getByRole("img", { name: "Fluent (3 of 3)" })).toBeVisible();
    expect(await screen.findByRole("img", { name: "Activity on Space Works: 3 activities in the past 3 days" })).toBeVisible();
    expect(await screen.findByRole("img", { name: "GitHub contributions: 3 contributions in the past 3 days" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Share" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Edit profile" })).toBeNull();
  });

  it("hides the GitHub graph when the endpoint answers 404", async () => {
    serve(base, { github: false }); show();
    expect(await screen.findByRole("img", { name: /Activity on Space Works/ })).toBeVisible();
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/public/profiles/shaan.s/github"));
    expect(screen.queryByText("GitHub contributions")).toBeNull();
  });

  it("never asks for graphs the member did not consent to", async () => {
    serve({ ...base, show_activity_graph: false }); show();
    await screen.findByRole("heading", { level: 1 });
    expect(vi.mocked(publicV1Request).mock.calls.map(([path]) => path)).toEqual(["/public/profiles/shaan.s/"]);
  });

  it("shows visitors only the tabs with content, and events with their badges", async () => {
    serve(base, { events: [
      { title: "Game night", starts_at: "2026-06-26T20:00:00Z", ends_at: "2026-06-26T22:00:00Z", badge: "HOSTED", host: "Lab" },
      { title: "AMA", starts_at: "2026-06-20T20:00:00Z", ends_at: "2026-06-20T21:00:00Z", badge: "ATTENDED", host: "Lab" },
    ] }); show();
    const tabs = await screen.findByRole("tablist", { name: "Profile sections" });
    expect(within(tabs).getAllByRole("tab").map(tab => tab.textContent)).toEqual(["Profile", "Activities", "Education"]);
    fireEvent.click(within(tabs).getByRole("tab", { name: "Activities" }));
    expect(await screen.findByText("Game night")).toBeVisible();
    expect(screen.getByText("Hosted")).toBeVisible();
    expect(screen.getByText("Attended")).toBeVisible();
    fireEvent.click(within(tabs).getByRole("tab", { name: "Education" }));
    expect(screen.getByRole("heading", { name: "B.Tech, Electronics" })).toBeVisible();
    expect(screen.getByText("CUSAT · Kochi")).toBeVisible();
  });

  it("shows an empty past-events state", async () => {
    serve(base); show("/shaan.s?tab=activities");
    expect(await screen.findByText("No past events yet.")).toBeVisible();
  });

  it("opens speaking history directly without requiring attendance or graph consent", async () => {
    serve({ ...base, show_events: false, show_speaking: true, show_activity_graph: false }, { events: [
      { title: "My talk", starts_at: "2026-06-20T20:00:00Z", ends_at: "2026-06-20T21:00:00Z", badge: "SPOKE", host: "Lab" },
    ] });
    show("/shaan.s?tab=activities");
    expect(await screen.findByText("My talk")).toBeVisible();
    expect(screen.getByText("Spoke")).toBeVisible();
    expect(screen.getByRole("tab", { name: "Activities" })).toHaveAttribute("aria-selected", "true");
    expect(publicV1Request).toHaveBeenCalledWith("/public/profiles/shaan.s/events?page=1");
    expect(vi.mocked(publicV1Request).mock.calls.some(([path]) => path.endsWith("/activity"))).toBe(false);
  });

  it("keeps projects and timeline tabs independent of event, speaking and graph consent", async () => {
    serve({ ...base, show_projects: true, show_events: false, show_speaking: false, show_activity_graph: false });
    show("/shaan.s?tab=projects");
    expect(await screen.findByText("No public projects yet.")).toBeVisible();
    expect(screen.queryByRole("tab", { name: "Activities" })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Education" }));
    expect(screen.getByRole("heading", { name: "B.Tech, Electronics" })).toBeVisible();
  });

  it("falls back from an unconsented activity deep link without requesting event history", async () => {
    serve({ ...base, show_events: false, show_speaking: false, show_activity_graph: false });
    show("/shaan.s?tab=activities");
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByRole("tab", { name: "Profile" })).toHaveAttribute("aria-selected", "true");
    expect(vi.mocked(publicV1Request).mock.calls.some(([path]) => path.includes("/events"))).toBe(false);
  });

  it("gives the owner an edit link and every tab with a way to add", async () => {
    serve({ ...base, viewer_is_owner: true }); show("/shaan.s?tab=experience");
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/m/lab/member/account-portal?section=profile");
    expect(screen.getByText("Build your professional story. Add your work history.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Add experience" })).toBeVisible();
    expect(within(screen.getByRole("tablist")).getAllByRole("tab")).toHaveLength(6);
  });

  it("ignores a stale local owner marker when the server says this viewer is not the owner", async () => {
    window.localStorage.setItem("sw.profile.edit.shaan.s", "/member/account-portal?section=profile");
    serve(base); show();
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("link", { name: "Edit profile" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Experience" })).toBeNull();
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

  it("restores the optional cookie session before requesting ownership on a direct page load", async () => {
    const actualApi = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
    let finish!: (value: boolean) => void;
    vi.mocked(refreshAccessToken).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    serve({ ...base, viewer_is_owner: true });
    const publicRoute = vi.mocked(publicV1Request).getMockImplementation()!;
    // Exercise the real optional-auth transport: it must send the restored member
    // credential when reading server-owned ownership, before rendering an edit link.
    vi.mocked(publicV1Request).mockImplementation((path, ...args) => path === "/public/profiles/shaan.s/"
      ? actualApi.publicV1Request(path, ...args) : publicRoute(path, ...args));
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ ...base, viewer_is_owner: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    show();
    expect(publicV1Request).not.toHaveBeenCalled();
    expect(fetcher).not.toHaveBeenCalled();
    const token = `header.${btoa(JSON.stringify({ user_id: 7 }))}.signature`;
    setAccessToken(token, "person");
    finish(true);
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/m/lab/member/account-portal?section=profile");
    expect(publicV1Request).toHaveBeenCalledWith("/public/profiles/shaan.s/");
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(expect.stringContaining("/public/profiles/shaan.s/"),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${token}` }) }));
  });

  it("matches the profile handle across active own memberships instead of editing the first space", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ memberships: [
      { makerspace: { slug: "inactive" }, membership_status: "suspended" },
      { makerspace: { slug: "other" }, membership_status: "active" },
      { makerspace: { slug: "lab" }, membership_status: "active" },
    ] });
    vi.mocked(bootstrapTenant).mockImplementation(async ({ slug }) => ({ makerspace: { id: slug === "lab" ? 3 : 4 }, modules: ["membership"] } as Awaited<ReturnType<typeof bootstrapTenant>>));
    vi.mocked(tenantMemberRequest).mockImplementation(async slug => ({ handle: slug === "lab" ? base.handle : null }));
    serve({ ...base, viewer_is_owner: true }); show();
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/m/lab/member/account-portal?section=profile");
    expect(bootstrapTenant).not.toHaveBeenCalledWith({ slug: "inactive" }, expect.anything());
    expect(bootstrapTenant).toHaveBeenCalledWith({ slug: "other" }, { activate: false });
    expect(bootstrapTenant).toHaveBeenCalledWith({ slug: "lab" }, { activate: false });
    expect(tenantMemberRequest).toHaveBeenCalledWith("other", "/member/makerspaces/4/profile");
    expect(tenantMemberRequest).toHaveBeenCalledWith("lab", "/member/makerspaces/3/profile");
  });

  it("keeps the public page available if restoring an optional session fails", async () => {
    vi.mocked(refreshAccessToken).mockRejectedValue(new Error("Offline"));
    serve(base); show();
    expect(await screen.findByRole("heading", { level: 1 })).toBeVisible();
    expect(memberRequest).not.toHaveBeenCalled();
    expect(bootstrapTenant).not.toHaveBeenCalled();
  });

  it("uses the tenant-relative editor on a single-tenant site", async () => {
    vi.mocked(useOptionalTenant).mockReturnValue({ mode: "single", slug: "lab", bootstrap: { makerspace: { name: "Lab" } } } as ReturnType<typeof useOptionalTenant>);
    serve({ ...base, viewer_is_owner: true }); show();
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/member/account-portal?section=profile");
    expect(memberRequest).not.toHaveBeenCalled();
    expect(bootstrapTenant).not.toHaveBeenCalled();
  });

  it("offers an editor lookup retry while keeping the public profile visible", async () => {
    vi.mocked(memberRequest).mockRejectedValueOnce(new Error("Unavailable"));
    serve({ ...base, viewer_is_owner: true }); show();
    expect(await screen.findByText("Couldn't find your profile editor. Try again.")).toBeVisible();
    expect(screen.getByRole("heading", { level: 1 })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: "Edit profile" })).toHaveAttribute("href", "/m/lab/member/account-portal?section=profile");
  });

  it("loads projects from each endpoint page, including projects beyond the profile payload cap", async () => {
    const project = (title: string) => ({ title, subtitle: "", description: "", tags: [], image_url: null, links: [] });
    serve({ ...base, show_projects: true, projects: [project("Capped payload")] });
    const profileRoute = vi.mocked(publicV1Request).getMockImplementation()!;
    vi.mocked(publicV1Request).mockImplementation(async (path, ...args) => {
      if (path.includes("/projects?page=")) return { count: 25, next: path.endsWith("=1") ? "?page=2" : null,
        previous: path.endsWith("=2") ? "?page=1" : null,
        results: [project(path.endsWith("=2") ? "Project twenty-five" : "Project one")] };
      return profileRoute(path, ...args);
    });
    show();
    await screen.findByRole("heading", { level: 1 });
    expect(vi.mocked(publicV1Request).mock.calls.some(([path]) => path.includes("/projects"))).toBe(false);
    fireEvent.click(screen.getByRole("tab", { name: "Projects" }));
    expect(await screen.findByText("Project one")).toBeVisible();
    expect(screen.queryByText("Capped payload")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Project twenty-five")).toBeVisible();
    expect(publicV1Request).toHaveBeenCalledWith("/public/profiles/shaan.s/projects?page=2");
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByText("Project one")).toBeVisible();
  });

  it("retries a failed project page and shows the empty state", async () => {
    serve({ ...base, show_projects: true });
    const profileRoute = vi.mocked(publicV1Request).getMockImplementation()!;
    let failed = true;
    vi.mocked(publicV1Request).mockImplementation(async (path, ...args) => {
      if (path.includes("/projects") && failed) throw new StructuredApiError(503, {});
      return profileRoute(path, ...args);
    });
    show("/shaan.s?tab=projects");
    expect(await screen.findByText("Couldn't load projects. Try again.", {}, { timeout: 4000 })).toBeVisible();
    failed = false;
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(await screen.findByText("No public projects yet.")).toBeVisible();
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
