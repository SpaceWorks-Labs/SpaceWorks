// @ts-nocheck -- bodies restored verbatim from 0.11.0; they target removed per-space UI and are skipped (rule 244).
/* eslint-disable */
// removed in 0.12.0: per-space publish flow, release-handle and family switches are replaced by the global profile (decisions 302, 304, 308).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, StructuredApiError } from "../../../lib/api";
import type { MemberProfile } from "../../members/memberProfile/types";
const PublicPageSettings = (_props) => null; // component removed in 0.12.0

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn() }));

const profile: MemberProfile = {
  verified: true,
  membership_id: 2, display_name: "Maker One", is_visible: false, show_attended_events: false, headline: "Builds robots",
  institution: "", bio: "", avatar_url: null, interests: [], languages: [], education: [], github_username: "",
  github_contributions: null, activity: {}, handle: null, public_visible: false, public_consented_at: null,
  show_activity_graph: false, show_events: false, show_speaking: false, show_projects: false,
  show_machine_activity: false, show_bookings: false, show_loans: false, domains: ["Robotics"], skills: [], links: [],
  projects: [{ id: 5, title: "Rover", subtitle: "Mars rover", tags: ["robotics"], public_visible: true, description: "", links: [], image_url: null }],
};
type Call = [string, RequestInit | undefined];
const calls = () => vi.mocked(memberRequest).mock.calls as Call[];
const mutations = () => calls().filter(([, options]) => options?.method);

function show(node: React.ReactNode) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
}

beforeEach(() => {
  vi.mocked(memberRequest).mockReset();
  vi.mocked(memberRequest).mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.includes("/timeline") && !options?.method) return { count: 0, next: null, previous: null, results: [] };
    if (path.endsWith("/handle") && options?.method === "POST") return { handle: "maker.one", claimed_at: "", changed_at: "" };
    return { ...profile, ...(options?.body ? JSON.parse(String(options.body)) : {}) };
  });
});

describe("handle claim", () => {
  it.skip("checks the grammar locally and claims a lowercased handle", async () => {
    show(<PublicPageSettings makerspaceId={3} profile={profile} />);
    const input = screen.getByRole("textbox", { name: "Public handle" });
    fireEvent.change(input, { target: { value: "-x" } });
    expect(screen.getByRole("alert")).toHaveTextContent("3–30 lowercase letters");
    expect(screen.getByRole("button", { name: "Claim handle" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "Maker.One" } });
    fireEvent.click(screen.getByRole("button", { name: "Claim handle" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/profile/handle",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ handle: "maker.one" }) })));
  });

  it.skip("surfaces the server's reserved-name error", async () => {
    vi.mocked(memberRequest).mockImplementation(async (path: string) => {
      if (path.endsWith("/handle")) throw new StructuredApiError(400, { handle: ["This name is reserved."] });
      return { count: 0, next: null, previous: null, results: [] };
    });
    show(<PublicPageSettings makerspaceId={3} profile={profile} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Public handle" }), { target: { value: "admin" } });
    fireEvent.click(screen.getByRole("button", { name: "Claim handle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This name is reserved.");
  });

  it.skip("explains the cooldown when changing, and releases only after confirming", async () => {
    show(<PublicPageSettings makerspaceId={3} profile={{ ...profile, handle: "maker.one" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Change handle" }));
    expect(screen.getByText(/once every 30 days/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Release handle" }));
    expect(mutations()).toHaveLength(0);
    const dialog = screen.getByRole("dialog", { name: "Release your handle?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Release handle" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/profile/handle", expect.objectContaining({ method: "DELETE" })));
  });
});

describe("publication", () => {
  it.skip("cannot publish before a handle is claimed", () => {
    show(<PublicPageSettings makerspaceId={3} profile={profile} />);
    expect(screen.getByRole("button", { name: "Publish…" })).toBeDisabled();
  });

  it.skip("requires a fresh, explicit consent tick before publishing", async () => {
    show(<PublicPageSettings makerspaceId={3} profile={{ ...profile, handle: "maker.one" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Publish…" }));
    const dialog = screen.getByRole("dialog", { name: "Publish your public profile?" });
    const publish = within(dialog).getByRole("button", { name: "Publish profile" });
    expect(publish).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /I agree to publish it/ }));
    fireEvent.click(publish);
    await waitFor(() => expect(mutations()).toEqual([["/member/makerspaces/3/profile",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ public_visible: true, publication_consent: true }) })]]));
  });

  it.skip("starts every family switch off and saves one switch at a time", async () => {
    show(<PublicPageSettings makerspaceId={3} profile={{ ...profile, handle: "maker.one" }} />);
    const switches = screen.getAllByRole("switch");
    expect(switches).toHaveLength(7);
    switches.forEach(item => expect(item).not.toBeChecked());
    fireEvent.click(screen.getByRole("switch", { name: /Events/ }));
    await waitFor(() => expect(mutations()).toEqual([["/member/makerspaces/3/profile",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ show_events: true }) })]]));
  });

  it.skip("unpublishes after confirming, without sending consent", async () => {
    show(<PublicPageSettings makerspaceId={3} profile={{ ...profile, handle: "maker.one", public_visible: true, public_consented_at: "2026-10-01T00:00:00Z" }} />);
    expect(screen.getByRole("link", { name: /View public page/ })).toHaveAttribute("href", "/maker.one");
    fireEvent.click(screen.getByRole("button", { name: "Unpublish" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Unpublish" }));
    await waitFor(() => expect(mutations()[0][1]?.body).toBe(JSON.stringify({ public_visible: false })));
  });

  it.skip("previews the public page from the saved profile before publishing", async () => {
    show(<PublicPageSettings makerspaceId={3} profile={{ ...profile, handle: "maker.one", show_projects: true }} />);
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    const dialog = screen.getByRole("dialog", { name: "Preview: what visitors see" });
    expect(within(dialog).getByRole("heading", { level: 2, name: "Maker One" })).toBeVisible();
    expect(within(dialog).getByRole("img", { name: "Verified member" })).toBeVisible();
    expect(within(dialog).getByText("ROBOTICS".toLowerCase(), { exact: false })).toBeVisible();
    fireEvent.click(within(dialog).getByRole("tab", { name: "Projects" }));
    expect(within(dialog).getByText("Mars rover")).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "Share" })).toBeNull();
  });

  it.skip("does not show a verified badge for an unverified saved profile", () => {
    show(<PublicPageSettings makerspaceId={3} profile={{ ...profile, verified: false }} />);
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(within(screen.getByRole("dialog")).queryByRole("img", { name: "Verified member" })).toBeNull();
  });
});
