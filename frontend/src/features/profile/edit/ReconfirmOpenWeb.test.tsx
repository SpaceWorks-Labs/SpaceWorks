import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, publicV1Request } from "../../../lib/api";
import type { AccountProfile } from "../accountProfileTypes";
import { GlobalProfileEditor } from "./GlobalProfileEditor";

vi.mock("../../../lib/api", async original => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../staff/ImageUploader", () => ({ ImageUploader: () => null }));

const shown = { status: true, about: true, experience: true, education: true, achievements: true, projects: true, skills: true, links: true, interests: true, events: true, spaces: true, certifications: true };
const toggles = { is_visible: true, show_status: true, show_about: true, show_experience: true, show_education: true, show_achievements: true, show_projects: true,
  show_skills: true, show_links: true, show_interests: true, show_events: true, show_spaces: true, show_certifications: true };
const merged: AccountProfile = {
  audience: "owner", handle: "maker.one", account_id: 3, display_name: "Maker One", avatar_url: null, headline: "", institution: "", shown,
  status: { preset: "", note: "" }, bio: "", timeline: [], education: [], skills: [], domains: [], links: [], interests: [], languages: [],
  projects: [], achievements: { verified: [], self_reported: [] }, events_attended: null, certifications: [], spaces: [], organizations: [],
  is_visible: true, public_visible: false, public_consented_at: null, public_reconfirm_pending: true, toggles,
};
type Call = [string, RequestInit | undefined];
const patches = () => (vi.mocked(memberRequest).mock.calls as Call[])
  .filter(([path, options]) => path === "/member/profile" && options?.method === "PATCH").map(([, options]) => JSON.parse(String(options?.body)));
let current: AccountProfile;

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><GlobalProfileEditor /></QueryClientProvider>);
}

beforeEach(() => {
  current = merged;
  vi.mocked(publicV1Request).mockReset().mockResolvedValue({});
  vi.mocked(memberRequest).mockReset().mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.startsWith("/member/profile/timeline") && !options?.method) return { count: 0, next: null, previous: null, results: [] };
    if (path === "/member/profile/achievements" && !options?.method) return [];
    if (path === "/member/profile/project-import" && !options?.method) return [];
    if (path === "/member/profile" && options?.method === "PATCH") {
      const body = JSON.parse(String(options.body));
      current = { ...current, ...body, public_reconfirm_pending: false };
      return current;
    }
    return current;
  });
});

describe("open-web re-confirmation after the profile merge (decision 335c)", () => {
  it("asks once, and publishing still needs the fresh consent tick", async () => {
    show();
    expect(await screen.findByText("Confirm the open web again.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Publish on the open web/ }));
    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByRole("button", { name: "Show on the open web" })).toBeDisabled();
    fireEvent.click(dialog.getByRole("checkbox"));
    fireEvent.click(dialog.getByRole("button", { name: "Show on the open web" }));
    await waitFor(() => expect(patches()).toEqual([{ public_visible: true, publication_consent: true }]));
  });

  it("keeping it off answers the request without publishing anything", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Keep it off the open web" }));
    await waitFor(() => expect(patches()).toEqual([{ public_visible: false }]));
    await waitFor(() => expect(screen.queryByText("Confirm the open web again.")).toBeNull());
  });

  it("is not shown when nothing is pending or the profile is already on the open web", async () => {
    current = { ...merged, public_reconfirm_pending: false };
    show();
    expect(await screen.findByRole("switch", { name: /Also show it on the open web/ })).toBeVisible();
    expect(screen.queryByText("Confirm the open web again.")).toBeNull();
  });
});
