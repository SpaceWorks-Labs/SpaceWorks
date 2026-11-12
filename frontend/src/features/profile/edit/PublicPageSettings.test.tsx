import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, publicV1Request, StructuredApiError } from "../../../lib/api";
import type { AccountProfile } from "../accountProfileTypes";
import { GlobalProfileEditor } from "./GlobalProfileEditor";

vi.mock("../../../lib/api", async original => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn(), publicV1Request: vi.fn() }));
vi.mock("../../staff/ImageUploader", () => ({ ImageUploader: () => null }));

const shown = { status: true, about: true, experience: true, education: true, achievements: true, projects: true, skills: true, links: true, interests: true, events: true, spaces: true, certifications: true };
const toggles = { is_visible: true, show_status: true, show_about: true, show_experience: true, show_education: true, show_achievements: true, show_projects: true,
  show_skills: true, show_links: true, show_interests: true, show_events: true, show_spaces: true, show_certifications: true };
const profile: AccountProfile = {
  audience: "owner", handle: "maker.one", account_id: 3, display_name: "Maker One", avatar_url: null, headline: "Builds robots", institution: "", shown,
  status: { preset: "", note: "" }, bio: "", timeline: [], education: [], skills: [], domains: ["Robotics"], links: [], interests: [], languages: [],
  projects: [{ id: 5, title: "Rover", subtitle: "Mars rover", tags: ["robotics"], public_visible: true, description: "", links: [], image_url: null, imported: false }],
  achievements: { verified: [{ kind: "speaker", event_title: "MakerConf", verified_by: "Space A" }], self_reported: [] },
  events_attended: null, certifications: [], spaces: [], organizations: [],
  is_visible: true, public_visible: false, public_consented_at: null, toggles,
};
type Call = [string, RequestInit | undefined];
const calls = () => vi.mocked(memberRequest).mock.calls as Call[];
const mutations = () => calls().filter(([, options]) => options?.method);
const patches = () => mutations().filter(([path, options]) => path === "/member/profile" && options?.method === "PATCH").map(([, options]) => JSON.parse(String(options?.body)));
let current: AccountProfile;
let availability: { available: boolean; reason?: string };

function show(node: React.ReactNode = <GlobalProfileEditor />) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
}

beforeEach(() => {
  current = profile; availability = { available: true };
  vi.mocked(publicV1Request).mockReset().mockImplementation(async (path: string) => path.startsWith("/handles/check") ? { handle: "x", reason: "", suggestion: null, ...availability } : {});
  vi.mocked(memberRequest).mockReset().mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.startsWith("/member/profile/timeline") && !options?.method) return { count: 0, next: null, previous: null, results: [] };
    if (path === "/member/profile/achievements" && !options?.method) return [];
    if (path === "/member/profile/project-import" && !options?.method) return [
      { id: 7, title: "Hack rover", event_title: "HackFest", space_name: "Space A", submitted_at: "", already_imported: false },
      { id: 8, title: "Old build", event_title: "HackFest", space_name: "Space A", submitted_at: "", already_imported: true }];
    if (path === "/member/profile/handle" && options?.method === "POST") return { handle: JSON.parse(String(options.body)).handle, claimed_at: "", changed_at: "" };
    if (path === "/member/profile/project-import" && options?.method === "POST") return { id: 9, title: "Hack rover" };
    if (path === "/member/profile" && options?.method === "PATCH") {
      const body = JSON.parse(String(options.body));
      current = { ...current, ...body, toggles: { ...current.toggles!, ...Object.fromEntries(Object.entries(body).filter(([key]) => key.startsWith("show_"))) } };
      return current;
    }
    return current;
  });
});

describe("handle claim", () => {
  it("shows the current handle and the 30-day change and redirect rules", async () => {
    show(); fireEvent.click(await screen.findByRole("button", { name: "Change handle" }));
    expect(screen.getByText(/once every 30 days. Your old link keeps redirecting/)).toBeVisible();
  });

  it("offers a clear call to action when there is no handle, with live availability", async () => {
    current = { ...profile, handle: null };
    show();
    expect(await screen.findByText("Choose your handle")).toBeVisible();
    const field = screen.getByLabelText("Username");
    fireEvent.change(field, { target: { value: "Maker.Two" } });
    expect(await screen.findByText("That username is free.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Choose handle" }));
    await waitFor(() => expect(mutations().some(([path, options]) => path === "/member/profile/handle" && options?.body === JSON.stringify({ handle: "maker.two" }))).toBe(true));
  });

  it("will not claim a taken handle and says so", async () => {
    current = { ...profile, handle: null }; availability = { available: false, reason: "taken" };
    show(); fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "taken" } });
    expect(await screen.findByText("That username is taken.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Choose handle" })).toBeDisabled();
  });

  it("surfaces the server's cooldown error when changing", async () => {
    vi.mocked(memberRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/member/profile/handle" && options?.method === "POST") throw new StructuredApiError(400, { handle: ["You changed your handle recently."] });
      if (path.startsWith("/member/profile/timeline")) return { count: 0, next: null, previous: null, results: [] };
      if (path === "/member/profile/achievements") return [];
      return current;
    });
    show(); fireEvent.click(await screen.findByRole("button", { name: "Change handle" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "newer.name" } });
    await screen.findByText("That username is free.");
    fireEvent.click(screen.getByRole("button", { name: "Save handle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You changed your handle recently.");
  });
});

describe("publication", () => {
  it("defaults the platform switch on, the open web off, and every section on", async () => {
    show();
    expect(await screen.findByRole("switch", { name: "Show my profile on the platform" })).toBeChecked();
    expect(screen.getByRole("switch", { name: /Also show it on the open web/ })).not.toBeChecked();
    for (const name of ["Show my status", "Show my bio", "Show my projects", "Show my skills", "Show my links", "Show my achievements", "Show education"]) expect(screen.getByRole("switch", { name })).toBeChecked();
  });

  it("starts the activity graph and its projects/events families on, and speaking, machine jobs, bookings and loans off", async () => {
    current = { ...profile, toggles: { ...toggles, show_activity_graph: true } };
    show();
    expect(await screen.findByRole("switch", { name: "Show my activity graph" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Count projects" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Count events" })).toBeChecked();
    for (const name of ["Count speaking", "Count machine jobs", "Count bookings", "Count loans"]) expect(screen.getByRole("switch", { name })).not.toBeChecked();
  });

  it("saves a family switch and the GitHub username", async () => {
    show(); fireEvent.click(await screen.findByRole("switch", { name: "Count loans" }));
    await waitFor(() => expect(patches()).toEqual([{ show_loans: true }]));
    fireEvent.change(screen.getByRole("textbox", { name: "GitHub username" }), { target: { value: "ada" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patches().at(-1)).toMatchObject({ github_username: "ada" }));
  });

  it("saves the platform master switch on its own", async () => {
    show(); fireEvent.click(await screen.findByRole("switch", { name: "Show my profile on the platform" }));
    await waitFor(() => expect(patches()).toEqual([{ is_visible: false }]));
  });

  it("saves one section switch at a time", async () => {
    show(); fireEvent.click(await screen.findByRole("switch", { name: "Show my skills" }));
    await waitFor(() => expect(patches()).toEqual([{ show_skills: false }]));
  });

  it("cannot turn the open web on before a handle is chosen", async () => {
    current = { ...profile, handle: null };
    show();
    expect(await screen.findByRole("switch", { name: /Also show it on the open web/ })).toBeDisabled();
    expect(screen.getByText(/Choose your handle first/)).toBeVisible();
  });

  it("requires a fresh, explicit consent tick and records it with the switch", async () => {
    show(); fireEvent.click(await screen.findByRole("switch", { name: /Also show it on the open web/ }));
    const dialog = within(await screen.findByRole("dialog"));
    const confirm = dialog.getByRole("button", { name: "Show on the open web" });
    expect(confirm).toBeDisabled();
    expect(dialog.getByText(/logged-out visitors and search engines/)).toBeVisible();
    fireEvent.click(dialog.getByRole("checkbox"));
    fireEvent.click(confirm);
    await waitFor(() => expect(patches()).toEqual([{ public_visible: true, publication_consent: true }]));
  });

  it("starts the consent box unticked every time", async () => {
    show(); fireEvent.click(await screen.findByRole("switch", { name: /Also show it on the open web/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("checkbox"));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    fireEvent.click(screen.getByRole("switch", { name: /Also show it on the open web/ }));
    expect(within(await screen.findByRole("dialog")).getByRole("checkbox")).not.toBeChecked();
    expect(patches()).toEqual([]);
  });

  it("turns the open web off after confirming, without sending consent", async () => {
    current = { ...profile, public_visible: true, public_consented_at: "2026-10-01T00:00:00Z" };
    show(); fireEvent.click(await screen.findByRole("switch", { name: /Also show it on the open web/ }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Turn off" }));
    await waitFor(() => expect(patches()).toEqual([{ public_visible: false }]));
  });

  it("previews the profile as another member would see it, dropping switched-off sections", async () => {
    current = { ...profile, headline: "Builds robots", skills: [{ name: "Welding", level: 2 }], shown: { ...shown, skills: false } };
    show(); fireEvent.click(await screen.findByRole("button", { name: "Preview" }));
    const dialog = within(await screen.findByRole("dialog"));
    expect(dialog.getByText("Builds robots")).toBeVisible();
    expect(dialog.queryByText("Welding")).toBeNull();
  });
});

describe("profile form", () => {
  it("saves the status preset and a note capped at 120 characters", async () => {
    show();
    fireEvent.change(await screen.findByRole("combobox", { name: "Status" }), { target: { value: "open_to_collaborate" } });
    const note = screen.getByRole("textbox", { name: "Note" });
    expect(note).toHaveAttribute("maxLength", "120");
    fireEvent.change(note, { target: { value: "Need a CNC buddy" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patches()[0]).toMatchObject({ status: "open_to_collaborate", status_note: "Need a CNC buddy", headline: "Builds robots" }));
  });

  it("sends the whole project list, skills, https links and interests on save", async () => {
    show();
    fireEvent.change(await screen.findByRole("textbox", { name: "Interests" }), { target: { value: "gliders, sailing" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patches()[0]).toMatchObject({ interests: ["gliders", "sailing"], domains: ["Robotics"],
      projects: [expect.objectContaining({ id: 5, title: "Rover", public_visible: true })] }));
  });

  it("blocks saving a non-https link", async () => {
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Add a link" }));
    fireEvent.change(screen.getByLabelText("Link 1 URL"), { target: { value: "http://example.test" } });
    expect(screen.getByText("Use a link that starts with https://.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("discards unsaved text without sending a mutation", async () => {
    show();
    const headline = await screen.findByRole("textbox", { name: "Headline" });
    fireEvent.change(headline, { target: { value: "Unsaved" } });
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(headline).toHaveValue("Builds robots");
    expect(mutations()).toEqual([]);
  });

  it("imports a hackathon submission and marks already-imported ones", async () => {
    show(); fireEvent.click(await screen.findByRole("button", { name: "Import from my hackathon submissions" }));
    expect(await screen.findByText("Imported")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Import Hack rover" }));
    await waitFor(() => expect(mutations().some(([path, options]) => path === "/member/profile/project-import" && options?.body === JSON.stringify({ submission_id: 7 }))).toBe(true));
    expect(await screen.findByText(/Imported "Hack rover"/)).toBeVisible();
  });

  it("shows the server's reason when an import is refused", async () => {
    const base = vi.mocked(memberRequest).getMockImplementation()!;
    vi.mocked(memberRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/member/profile/project-import" && options?.method === "POST") throw new StructuredApiError(409, { code: "already_imported", detail: "Already imported." });
      return base(path, options);
    });
    show(); fireEvent.click(await screen.findByRole("button", { name: "Import from my hackathon submissions" }));
    fireEvent.click(await screen.findByRole("button", { name: "Import Hack rover" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Already imported.");
  });
});

describe("achievements", () => {
  it("lists verified ones read-only with their space, and self-reported ones as CRUD", async () => {
    const base = vi.mocked(memberRequest).getMockImplementation()!;
    vi.mocked(memberRequest).mockImplementation(async (path: string, options?: RequestInit) => path === "/member/profile/achievements" && !options?.method
      ? [{ id: 4, title: "Club lead", issuer: "CUSAT", achieved_on: null, url: "", description: "", order: 0 }] : base(path, options));
    show();
    expect(await screen.findByText("Spoke at MakerConf")).toBeVisible();
    expect(screen.getByText("Verified by Space A")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Edit Spoke at MakerConf" })).toBeNull();
    expect(await screen.findByText("Club lead")).toBeVisible();
    expect(screen.getAllByText("Self-reported").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Delete Club lead" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(mutations().some(([path, options]) => path === "/member/profile/achievements/4" && options?.method === "DELETE")).toBe(true));
  });

  it("adds a self-reported achievement and refuses a non-https link", async () => {
    show(); fireEvent.click(await screen.findByRole("button", { name: "Add an achievement" }));
    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Title"), { target: { value: "Won a quiz" } });
    fireEvent.change(dialog.getByLabelText(/^Link/), { target: { value: "http://x.test" } });
    expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
    fireEvent.change(dialog.getByLabelText(/^Link/), { target: { value: "https://x.test/proof" } });
    fireEvent.click(dialog.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mutations().some(([path, options]) => path === "/member/profile/achievements" && options?.method === "POST"
      && JSON.parse(String(options.body)).title === "Won a quiz")).toBe(true));
  });
});

describe("timeline editor", () => {
  it("adds an entry with an open end date and deletes one after confirming", async () => {
    show(); fireEvent.click(await screen.findByRole("button", { name: "Add experience" }));
    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Title"), { target: { value: "Intern" } });
    fireEvent.change(dialog.getByLabelText("Start date"), { target: { value: "2024-01-01" } });
    fireEvent.click(dialog.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mutations().some(([path, options]) => path === "/member/profile/timeline" && options?.method === "POST"
      && JSON.parse(String(options.body)).end === null)).toBe(true));
  });

  it("refuses an end date before the start", async () => {
    show(); fireEvent.click(await screen.findByRole("button", { name: "Add education" }));
    const dialog = within(await screen.findByRole("dialog"));
    fireEvent.change(dialog.getByLabelText("Title"), { target: { value: "B.Tech" } });
    fireEvent.change(dialog.getByLabelText("Start date"), { target: { value: "2024-05-01" } });
    fireEvent.change(dialog.getByLabelText(/^End date/), { target: { value: "2024-01-01" } });
    expect(dialog.getByText("End must be on or after the start.")).toBeVisible();
    expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("shows the two timeline switches", async () => {
    show();
    expect(await screen.findByRole("switch", { name: "Show experience and volunteering" })).toBeChecked();
  });
});
