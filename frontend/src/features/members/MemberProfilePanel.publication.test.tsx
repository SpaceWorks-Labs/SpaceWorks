import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest } from "../../lib/api";
import { MemberProfilePanel, type MemberProfile } from "./MemberProfilePanel";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), memberRequest: vi.fn() }));
vi.mock("../staff/ImageUploader", () => ({ ImageUploader: () => null }));

const profile: MemberProfile = {
  verified: false,
  membership_id: 2, display_name: "Maker", is_visible: false, show_attended_events: false, headline: "", institution: "", bio: "",
  avatar_url: null, interests: [], languages: [], education: [], github_username: "", github_contributions: null, activity: {},
  handle: "maker", public_visible: false, domains: ["AI"], skills: [{ name: "Python", level: 2 }], links: [],
  projects: [{ id: 7, title: "Rover", subtitle: "", tags: [], public_visible: false, description: "", links: [], image_url: null }],
};

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberProfilePanel makerspaceId={3} /></QueryClientProvider>);
}
const putBody = () => {
  const call = vi.mocked(memberRequest).mock.calls.find(([, options]) => options?.method === "PUT");
  return call ? JSON.parse(String(call[1]?.body)) : undefined;
};

describe("MemberProfilePanel public content", () => {
  beforeEach(() => {
    vi.mocked(memberRequest).mockReset();
    vi.mocked(memberRequest).mockImplementation(async (path: string) => path.includes("/timeline")
      ? { count: 0, next: null, previous: null, results: [] } : profile);
  });

  it("saves domains, rated skills, https links and project publication fields", async () => {
    show();
    fireEvent.change(await screen.findByRole("textbox", { name: "Domains" }), { target: { value: "AI, Robotics" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Level for skill 1" }), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Add a link" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Link 1 URL" }), { target: { value: "https://example.org" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Project subtitle" }), { target: { value: "Mars rover" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Project tags" }), { target: { value: "robotics, rust" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Show on my public profile page" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(putBody()).toBeDefined());
    expect(putBody()).toMatchObject({
      domains: ["AI", "Robotics"], skills: [{ name: "Python", level: 3 }], links: [{ kind: "Website", url: "https://example.org" }],
      projects: [{ id: 7, title: "Rover", subtitle: "Mars rover", tags: ["robotics", "rust"], public_visible: true }],
    });
    expect(putBody()).not.toHaveProperty("public_visible");
  });

  it("blocks saving a non-https link", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Add a link" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Link 1 URL" }), { target: { value: "http://example.org" } });
    expect(screen.getByText("Use a link that starts with https://.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});
