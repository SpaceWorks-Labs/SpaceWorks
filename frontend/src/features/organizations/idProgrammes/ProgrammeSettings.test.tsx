import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";
import type { Programme, Question } from "./api";
import { ProgrammeSettings } from "./ProgrammeSettings";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request }));

const question = (over: Partial<Question> = {}): Question => ({ key: "q1", label: "Department", type: "text", required: false, placement: "hidden", ...over });
const programme = (over: Partial<Programme> = {}): Programme => ({ id: 9, organization: 3, organization_slug: "guild", makerspace: 7, name: "Student ID", slug: "student-id", description: "For students",
  status: "draft", registration_open: false, requires_approval: true, id_prefix: "STU", next_sequence: 1, validity_mode: "none", valid_until: null, validity_days: null, photo_mode: "optional",
  form_schema: [], public_verify: false, email_daily_cap: 50, counts: { all: 0, pending: 0, approved: 0, rejected: 0, revoked: 0 }, can_manage: true,
  created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z", ...over });

let saveError: Error | undefined;
let patches: Array<Record<string, unknown>>;
function mount(p: Programme = programme()) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><ProgrammeSettings programme={p} /></QueryClientProvider>);
}
const save = () => fireEvent.click(screen.getByRole("button", { name: "Save settings" }));
const lastPatch = () => patches[patches.length - 1];

beforeEach(() => {
  saveError = undefined; patches = [];
  request.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    patches.push(JSON.parse(String(init?.body)));
    expect(path).toBe("/admin/id-programmes/9");
    expect(init?.method).toBe("PATCH");
    if (saveError) throw saveError;
    return programme();
  });
});

describe("basic fields", () => {
  it("shows the current values and PATCHes edited fields without server-owned ones", async () => {
    mount();
    expect(screen.getByLabelText("Name")).toHaveValue("Student ID");
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Volunteer ID" } });
    fireEvent.change(screen.getByLabelText("Description (shown on the join page)"), { target: { value: "For volunteers" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "active" } });
    fireEvent.change(screen.getByLabelText("Number prefix (2-6 letters)"), { target: { value: "vol" } });
    fireEvent.change(screen.getByLabelText("Photo"), { target: { value: "required" } });
    save();
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(lastPatch()).toMatchObject({ name: "Volunteer ID", description: "For volunteers", status: "active", id_prefix: "VOL", photo_mode: "required" });
    for (const owned of ["counts", "can_manage", "id", "organization", "organization_slug", "makerspace", "slug", "next_sequence", "created_at", "updated_at"]) expect(lastPatch()).not.toHaveProperty(owned);
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });
  it("the three switches toggle independently", async () => {
    mount();
    fireEvent.click(screen.getByLabelText("Joining is open (needs the Open status)"));
    fireEvent.click(screen.getByLabelText("New people need approval"));
    fireEvent.click(screen.getByLabelText("Public check page for these cards"));
    save();
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(lastPatch()).toMatchObject({ registration_open: true, requires_approval: false, public_verify: true });
  });
  it("shows the server's typed error, keeps the edits, and no Saved message", async () => {
    saveError = new StructuredApiError(422, { detail: "Prefix already used", code: "prefix_taken" });
    mount();
    fireEvent.change(screen.getByLabelText("Number prefix (2-6 letters)"), { target: { value: "dup" } });
    save();
    expect(await screen.findByText(/Prefix already used/)).toBeInTheDocument();
    expect(screen.getByLabelText("Number prefix (2-6 letters)")).toHaveValue("DUP");
    expect(screen.queryByText("Saved.")).toBeNull();
  });
  it("shows Saving… and disables the button while the request is in flight", async () => {
    let release: (value: unknown) => void = () => undefined;
    request.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
    mount();
    save();
    expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
    release(programme());
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });
});

describe("validity", () => {
  it("none shows no extra field; a fixed date shows Until; days shows the number of days", async () => {
    mount();
    expect(screen.queryByLabelText("Until")).toBeNull();
    expect(screen.queryByLabelText("Days from approval")).toBeNull();
    fireEvent.change(screen.getByLabelText("Cards are valid"), { target: { value: "fixed_date" } });
    fireEvent.change(screen.getByLabelText("Until"), { target: { value: "2027-06-30" } });
    save();
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(lastPatch()).toMatchObject({ validity_mode: "fixed_date", valid_until: "2027-06-30" });
    fireEvent.change(screen.getByLabelText("Until"), { target: { value: "" } });
    save();
    await waitFor(() => expect(patches).toHaveLength(2));
    expect(lastPatch()).toMatchObject({ valid_until: null });
    fireEvent.change(screen.getByLabelText("Cards are valid"), { target: { value: "days" } });
    expect(screen.queryByLabelText("Until")).toBeNull();
    expect(screen.getByLabelText("Days from approval")).toHaveValue(365);
    fireEvent.change(screen.getByLabelText("Days from approval"), { target: { value: "90" } });
    save();
    await waitFor(() => expect(patches).toHaveLength(3));
    expect(lastPatch()).toMatchObject({ validity_mode: "days", validity_days: 90 });
  });
  it("shows an existing day count rather than the default", () => {
    mount(programme({ validity_mode: "days", validity_days: 30 }));
    expect(screen.getByLabelText("Days from approval")).toHaveValue(30);
  });
});

describe("join-form questions", () => {
  it("adds a question (up to the limit of twelve) and removes one", () => {
    mount(programme({ form_schema: [question({ key: "a", label: "First" }), question({ key: "b", label: "Second" })] }));
    expect(screen.getAllByLabelText("Question")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Add a question" }));
    expect(screen.getAllByLabelText("Question")).toHaveLength(3);
    fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    expect(screen.getAllByLabelText("Question")).toHaveLength(2);
    expect(screen.queryByDisplayValue("First")).toBeNull();
  });
  it("hides Add a question at twelve questions", () => {
    mount(programme({ form_schema: Array.from({ length: 12 }, (_, i) => question({ key: `k${i}`, label: `Q${i}` })) }));
    expect(screen.queryByRole("button", { name: "Add a question" })).toBeNull();
  });
  it("edits label, type, placement, saved-details key and required, and sends the schema", async () => {
    mount(programme({ form_schema: [question()] }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Year of study" } });
    fireEvent.change(screen.getByLabelText("Answer type"), { target: { value: "email" } });
    fireEvent.change(screen.getByLabelText("On the card"), { target: { value: "front" } });
    fireEvent.change(screen.getByLabelText("Offer to fill from Saved details"), { target: { value: "study_level" } });
    fireEvent.click(screen.getByLabelText("Required"));
    save();
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(lastPatch().form_schema).toEqual([{ key: "q1", label: "Year of study", type: "email", required: true, placement: "front", saved_details_key: "study_level" }]);
  });
  it("a choice question shows its options, one per line, trimmed and without blanks", async () => {
    mount(programme({ form_schema: [question({ type: "choice", options: ["Red", "Blue"] })] }));
    const options = screen.getByLabelText("Options, one per line");
    expect(options).toHaveValue("Red\nBlue");
    fireEvent.change(options, { target: { value: " Green \n\n Gold " } });
    save();
    await waitFor(() => expect(patches).toHaveLength(1));
    expect((lastPatch().form_schema as Question[])[0].options).toEqual(["Green", "Gold"]);
  });
  it("other types show no options box, and a choice with no options starts empty", () => {
    const { unmount } = mount(programme({ form_schema: [question({ type: "phone" })] }));
    expect(screen.queryByLabelText("Options, one per line")).toBeNull();
    unmount();
    mount(programme({ form_schema: [question({ type: "choice" })] }));
    expect(screen.getByLabelText("Options, one per line")).toHaveValue("");
  });
});
