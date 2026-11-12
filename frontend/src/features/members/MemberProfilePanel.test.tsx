import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, publicV1Request } from "../../lib/api";
import type { AccountProfile } from "../profile/accountProfileTypes";
import { MemberProfilePanel } from "./MemberProfilePanel";

vi.mock("../../lib/api", async original => ({ ...(await original<typeof import("../../lib/api")>()), memberRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../staff/ImageUploader", () => ({ ImageUploader: () => null }));

const shown = { status: true, about: true, experience: true, education: true, achievements: true, projects: true, skills: true, links: true, interests: true, events: true, spaces: true, certifications: true };
const profile: AccountProfile = {
  audience: "owner", handle: "maker", account_id: 2, display_name: "Maker", avatar_url: null, headline: "", institution: "", shown, status: null, bio: "",
  timeline: [], education: [], skills: [], domains: [], links: [], interests: [], languages: [], projects: [],
  achievements: { verified: [], self_reported: [] }, events_attended: null, certifications: [], spaces: [], organizations: [],
  is_visible: true, public_visible: false, public_consented_at: null, toggles: { is_visible: true, show_status: true, show_about: true, show_experience: true, show_education: true, show_achievements: true, show_projects: true, show_skills: true, show_links: true, show_interests: true, show_events: true, show_spaces: true, show_certifications: true },
};
function show() { render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberProfilePanel /></QueryClientProvider>); }
const serve = () => vi.mocked(memberRequest).mockImplementation(async (path: string) => path.startsWith("/member/profile/timeline") ? { count: 0, next: null, previous: null, results: [] }
  : path === "/member/profile/achievements" ? [] : profile);

describe("MemberProfilePanel", () => {
  beforeEach(() => { vi.mocked(memberRequest).mockReset(); vi.mocked(publicV1Request).mockReset().mockResolvedValue({ available: true, reason: "", suggestion: null }); });

  it("loads and saves the global profile through the member session", async () => {
    serve(); show();
    fireEvent.change(await screen.findByRole("textbox", { name: "Headline" }), { target: { value: "Builds robots" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/profile", expect.objectContaining({ method: "PATCH", body: expect.stringContaining('"headline":"Builds robots"') })));
  });

  it("never calls the deprecated per-space profile routes", async () => {
    serve(); show(); await screen.findByRole("textbox", { name: "Headline" });
    expect(vi.mocked(memberRequest).mock.calls.every(([path]) => !String(path).includes("/member/makerspaces/"))).toBe(true);
  });

  it("shows loading and a read error instead of disappearing", async () => {
    vi.mocked(memberRequest).mockRejectedValue(new Error("Profile unavailable")); show();
    expect(screen.getByRole("status", { name: "Loading your profile…" })).toBeVisible(); expect(await screen.findByRole("alert")).toHaveTextContent("Profile unavailable");
  });

  it("discards an unsaved profile without sending a mutation", async () => {
    serve(); show();
    const headline = await screen.findByRole("textbox", { name: "Headline" });
    fireEvent.change(headline, { target: { value: "Unsaved headline" } });
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(headline).toHaveValue("");
    expect(vi.mocked(memberRequest).mock.calls.every(([, options]) => !options?.method)).toBe(true);
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  });
});
