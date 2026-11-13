import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";
import type { Programme } from "./api";
import { ProgrammesTab } from "./ProgrammesTab";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));
vi.mock("../../help/HelpLink", () => ({ ScreenHelp: () => null }));
vi.mock("../../cards/cardJobs", () => ({ CardJobList: () => <p>card jobs</p>, JOB_LABELS: {}, useStartCardJob: () => ({ mutate: vi.fn(), error: null }) }));
vi.mock("./ProgrammeMembers", () => ({ ProgrammeMembers: ({ programme }: { programme: { name: string } }) => <p>members of {programme.name}</p> }));
vi.mock("./ProgrammeImport", () => ({ ProgrammeImport: ({ sheetImport, onDone }: { sheetImport: boolean; onDone: () => void }) => <button type="button" onClick={onDone}>import sheet={String(sheetImport)}</button> }));
vi.mock("./ProgrammeSettings", () => ({ ProgrammeSettings: () => <p>programme settings form</p> }));
vi.mock("../../../components/card-designer/CardDesigner", () => ({ CardDesigner: ({ designId, canEdit, makerspaceId }: { designId: number; canEdit: boolean; makerspaceId: number }) => <p>designer {designId} edit={String(canEdit)} space={makerspaceId}</p> }));

const programme = (over: Partial<Programme> = {}): Programme => ({ id: 9, organization: 3, organization_slug: "guild", makerspace: 7, name: "Student ID", slug: "student-id", description: "",
  status: "active", registration_open: true, requires_approval: true, id_prefix: "STU", next_sequence: 1, validity_mode: "none", valid_until: null, validity_days: null, photo_mode: "none",
  form_schema: [], public_verify: false, email_daily_cap: 50, counts: { all: 5, pending: 1, approved: 3, rejected: 0, revoked: 1 }, can_manage: true, archived_at: null,
  created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", ...over });

let orgs: unknown[];
let programmes: Programme[];
let archived: Programme[];
let orgError: Error | undefined;
let listError: Error | undefined;
let createError: Error | undefined;
let one: Programme | undefined;
let approval: unknown;
let design: unknown;
let designError: Error | undefined;
let posts: Array<{ path: string; method: string; body?: Record<string, unknown> }>;

function mount(props: Partial<Parameters<typeof ProgrammesTab>[0]> = {}) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><ProgrammesTab makerspaceId={7} {...props} /></QueryClientProvider>);
}
beforeEach(() => {
  orgs = [{ id: 3, name: "Maker Guild" }, { id: 4, name: "Robotics Club" }];
  programmes = [programme(), programme({ id: 10, name: "Other space", makerspace: 99 })]; archived = [programme({ id: 11, name: "Old ID", status: "closed", archived_at: "2026-01-01T00:00:00Z" })];
  orgError = undefined; listError = undefined; createError = undefined; one = programme(); posts = [];
  approval = { required: null, inherited: false }; design = { id: 55, can_edit: true }; designError = undefined;
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method !== "GET") {
      posts.push({ path, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (path.includes("/approval")) return { required: true, inherited: false };
      if (createError) throw createError;
      return programme({ id: 21, name: "New one" });
    }
    if (path.startsWith("/admin/organizations/?")) { if (orgError) throw orgError; return { count: orgs.length, results: orgs }; }
    if (path.includes("/id-programmes?archived=true")) { if (listError) throw listError; return archived; }
    if (path.endsWith("/id-programmes")) { if (listError) throw listError; return programmes; }
    if (path.endsWith("/approval")) return approval;
    if (path.endsWith("/design")) { if (designError) throw designError; return design; }
    if (/\/admin\/id-programmes\/\d+$/.test(path)) return one;
    return {};
  });
});

describe("organisation and programme list", () => {
  it("shows an empty state when the space belongs to no organisation", async () => {
    orgs = [];
    mount();
    expect(await screen.findByText("No organisations yet")).toBeInTheDocument();
  });
  it("shows an organisation load error", async () => {
    orgError = new Error("Orgs down");
    mount();
    expect(await screen.findByText("Couldn't load organisations. Try again.")).toBeInTheDocument();
  });
  it("lists only this space's programmes for the first organisation with counts and status", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "Student ID" })).toBeInTheDocument();
    expect(screen.queryByText("Other space")).toBeNull();
    expect(screen.getByText("3 approved · 1 waiting · 5 in all · joining open")).toBeInTheDocument();
    expect(screen.getByText("Open", { selector: "span" })).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/organizations/3/id-programmes");
  });
  it("switching organisation loads that organisation's programmes", async () => {
    mount();
    await screen.findByRole("heading", { name: "Student ID" });
    fireEvent.change(screen.getByLabelText("Organisation"), { target: { value: "4" } });
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/organizations/4/id-programmes"));
  });
  it("says there are none yet, and for archived ones too, hiding the create form while archived are shown", async () => {
    programmes = [];
    mount();
    expect(await screen.findByText("No programmes yet for this organisation here.")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Show archived programmes"));
    expect(await screen.findByText("Old ID")).toBeInTheDocument();
    expect(screen.getByText("Archived", { selector: "span" })).toBeInTheDocument();
    expect(screen.queryByLabelText("New programme")).toBeNull();
    archived = [];
    fireEvent.click(screen.getByLabelText("Show archived programmes"));
    fireEvent.click(screen.getByLabelText("Show archived programmes"));
    expect(await screen.findByText("No archived programmes for this organisation here.")).toBeInTheDocument();
  });
  it("shows a programmes load error", async () => {
    listError = new Error("Programmes down");
    mount();
    expect(await screen.findByText("Couldn't load programmes. Try again.")).toBeInTheDocument();
  });
  it("labels draft and closed programmes", async () => {
    programmes = [programme({ id: 12, name: "Draft one", status: "draft", registration_open: false }), programme({ id: 13, name: "Shut one", status: "closed", registration_open: false })];
    mount();
    await screen.findByText("Draft one");
    expect(screen.getByText("Draft", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("Closed", { selector: "span" })).toBeInTheDocument();
  });
});

describe("creating a programme", () => {
  it("needs a name of 2+ characters, posts the space, name and preset, then opens the new programme", async () => {
    one = programme({ id: 21, name: "New one" });
    mount();
    await screen.findByRole("heading", { name: "Student ID" });
    const create = screen.getByRole("button", { name: "Create" });
    expect(create).toBeDisabled();
    fireEvent.change(screen.getByLabelText("New programme"), { target: { value: "x" } });
    expect(create).toBeDisabled();
    fireEvent.change(screen.getByLabelText("New programme"), { target: { value: "  Volunteers 2026 " } });
    fireEvent.change(screen.getByLabelText("Start from"), { target: { value: "volunteers" } });
    fireEvent.click(create);
    await waitFor(() => expect(posts[0]).toMatchObject({ path: "/admin/organizations/3/id-programmes", method: "POST", body: { makerspace_id: 7, name: "Volunteers 2026", preset: "volunteers" } }));
    expect(await screen.findByRole("heading", { name: "New one" })).toBeInTheDocument();
  });
  it("lists the presets and shows the server's typed error", async () => {
    createError = new StructuredApiError(403, { detail: "Not allowed here", code: "module_disabled" });
    mount();
    await screen.findByRole("heading", { name: "Student ID" });
    expect(within(screen.getByLabelText("Start from")).getAllByRole("option").map((o) => o.textContent)).toEqual(["Blank", "Student ID", "Volunteer ID", "Staff ID"]);
    fireEvent.change(screen.getByLabelText("New programme"), { target: { value: "Fail" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(await screen.findByText(/Not allowed here/)).toBeInTheDocument();
    expect(screen.getByLabelText("New programme")).toHaveValue("Fail");
  });
});

describe("opening a programme", () => {
  async function open() {
    const view = mount({ sheetImport: true });
    fireEvent.click(await screen.findByRole("button", { name: "Open" }));
    await screen.findByRole("heading", { name: "Student ID", level: 2 });
    return view;
  }
  it("shows the join link when active and open, the generated number format, and the tab set for a manager", async () => {
    await open();
    expect(screen.getByText(`${window.location.origin}/o/guild/ids/student-id`)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`Numbers look like STU-${new Date().getFullYear()}-0001\\.`))).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Members 5", "Import", "Card design", "Settings"]);
    expect(screen.getByText("members of Student ID")).toBeInTheDocument();
    expect(screen.getByText("card jobs")).toBeInTheDocument();
  });
  it("copies the join link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/o/guild/ids/student-id`);
  });
  it("says joining is closed for a draft or a non-open programme", async () => {
    one = programme({ status: "draft", registration_open: false });
    await open();
    expect(screen.getByText("Joining is closed. Open it in Settings.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy link" })).toBeNull();
  });
  it("a read-only viewer sees only Members and Card design, without the approval switch", async () => {
    one = programme({ can_manage: false });
    await open();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Members 5", "Card design"]);
    fireEvent.click(screen.getByRole("tab", { name: /Card design/ }));
    expect(await screen.findByText("designer 55 edit=true space=7")).toBeInTheDocument();
    expect(screen.queryByLabelText("Design changes for this programme")).toBeNull();
  });
  it("the manager's design tab shows the approval switch and saves a change", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: /Card design/ }));
    const select = await screen.findByLabelText("Design changes for this programme");
    fireEvent.change(select, { target: { value: "on" } });
    await waitFor(() => expect(posts[0]).toMatchObject({ path: "/admin/id-programmes/9/approval", method: "PUT", body: { required: true } }));
  });
  it("shows a design load error", async () => {
    designError = new Error("Design down");
    await open();
    fireEvent.click(screen.getByRole("tab", { name: /Card design/ }));
    expect(await screen.findByText("Couldn't load card design. Try again.")).toBeInTheDocument();
  });
  it("Import goes back to Members when done, and receives the sheet-import flag", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Import" }));
    fireEvent.click(await screen.findByRole("button", { name: "import sheet=true" }));
    expect(await screen.findByText("members of Student ID")).toBeInTheDocument();
  });
  it("Settings shows the settings form and the archive/delete section; All programmes returns to the list", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Settings" }));
    expect(await screen.findByText("programme settings form")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Remove programme" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "All programmes" }));
    expect(await screen.findByLabelText("Organisation")).toBeInTheDocument();
  });
  it("shows a programme load error with retry", async () => {
    mount();
    const open = await screen.findByRole("button", { name: "Open" });
    one = undefined;
    request.mockImplementation(async (path: string) => {
      if (/\/admin\/id-programmes\/\d+$/.test(path)) throw new Error("Programme down");
      return path.startsWith("/admin/organizations/?") ? { count: 1, results: orgs } : programmes;
    });
    fireEvent.click(open);
    expect(await screen.findByText("Couldn't load programme. Try again.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
