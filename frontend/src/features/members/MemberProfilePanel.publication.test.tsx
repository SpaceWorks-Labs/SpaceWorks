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
  timeline: [], education: [], skills: [{ name: "Python", level: 2 }], domains: ["AI"], links: [], interests: [], languages: [],
  projects: [{ id: 7, title: "Rover", subtitle: "", tags: [], public_visible: false, description: "", links: [], image_url: null, imported: false }],
  achievements: { verified: [], self_reported: [] }, events_attended: null, certifications: [], spaces: [], organizations: [],
  is_visible: true, public_visible: false,
};

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberProfilePanel /></QueryClientProvider>);
}
const patchBody = () => {
  const call = vi.mocked(memberRequest).mock.calls.find(([path, options]) => path === "/member/profile" && options?.method === "PATCH");
  return call ? JSON.parse(String(call[1]?.body)) : undefined;
};

describe("MemberProfilePanel public content", () => {
  beforeEach(() => {
    vi.mocked(memberRequest).mockReset();
    vi.mocked(publicV1Request).mockReset().mockResolvedValue({ available: true, reason: "", suggestion: null });
    vi.mocked(memberRequest).mockImplementation(async (path: string) => path.startsWith("/member/profile/timeline")
      ? { count: 0, next: null, previous: null, results: [] } : path === "/member/profile/achievements" ? [] : profile);
  });

  it("saves domains, rated skills, https links and project publication fields", async () => {
    show();
    fireEvent.change(await screen.findByRole("textbox", { name: "Domains" }), { target: { value: "AI, Robotics" } });
    fireEvent.change(screen.getByLabelText("Level for skill 1"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Add a link" }));
    fireEvent.change(screen.getByLabelText("Link 1 URL"), { target: { value: "https://github.com/maker" } });
    fireEvent.click(screen.getByLabelText("Show this project on my profile"));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patchBody()).toMatchObject({
      domains: ["AI", "Robotics"], skills: [{ name: "Python", level: 3 }], links: [{ kind: "Website", url: "https://github.com/maker" }],
      projects: [expect.objectContaining({ id: 7, public_visible: true })],
    }));
  });

  it("blocks saving a non-https link", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Add a link" }));
    fireEvent.change(screen.getByLabelText("Link 1 URL"), { target: { value: "http://example.test" } });
    expect(screen.getByText("Use a link that starts with https://.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});
