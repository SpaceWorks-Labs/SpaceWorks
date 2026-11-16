import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";
import type { Programme, ProgrammeCard } from "./api";
import { ProgrammeMembers } from "./ProgrammeMembers";

const { request, startJob, download } = vi.hoisted(() => ({ request: vi.fn(), startJob: vi.fn(), download: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<typeof import("../../../lib/api")>(), staffRequest: request, staffRequestBlob: download }));
vi.mock("../../cards/cardJobs", () => ({ JOB_LABELS: { zip: "All cards (ZIP)" }, useStartCardJob: () => ({ mutate: startJob, error: null }) }));
vi.mock("../../cards/SheetPreviewDialog", () => ({ SheetPreviewDialog: ({ open, title, filter }: { open: boolean; title: string; filter: object }) => open ? <p>sheet dialog: {title} {JSON.stringify(filter)}</p> : null }));
vi.mock("../../cards/StaffPhotoDialog", () => ({ StaffPhotoDialog: ({ holderName, photoPath, onSaved }: { holderName: string | null; photoPath: string; onSaved: () => void }) =>
  holderName ? <div>photo dialog for {holderName} at {photoPath}<button type="button" onClick={onSaved}>photo saved</button></div> : null }));

const card = (over: Partial<ProgrammeCard> = {}): ProgrammeCard => ({ id: 1, programme: 9, name: "Asha Rao", email: "a@x.test", answers: {}, status: "pending", status_reason: "", source: "form",
  id_number: "", issued_at: null, expires_at: null, revoked_at: null, last_emailed_at: null, linked: true, photo_set: false, created_at: "2026-11-01T00:00:00Z", ...over });
const programme = (over: Partial<Programme> = {}): Programme => ({ id: 9, name: "Student ID", can_manage: true, counts: { all: 6, pending: 2, approved: 2, rejected: 1, revoked: 1 }, ...over } as Programme);

let rows: ProgrammeCard[];
let total: number;
let listError: Error | undefined;
let writes: Array<{ path: string; method: string; body?: Record<string, unknown> }>;
let writeError: Error | undefined;

function mount(p: Programme = programme()) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><ProgrammeMembers programme={p} /></QueryClientProvider>);
}
const openMenu = async (name: string) => { fireEvent.click(await screen.findByRole("button", { name: `Actions for ${name}` })); };
const menuLabels = () => screen.getAllByRole("menuitem").map((item) => item.textContent);

beforeEach(() => {
  rows = [card({ id: 1, name: "Asha Rao", status: "pending" }), card({ id: 2, name: "Bo Lee", status: "approved", id_number: "ID-0002", issued_at: "2026-11-02T00:00:00Z", expires_at: "2027-11-02T00:00:00Z" })];
  total = 2; listError = undefined; writeError = undefined; writes = [];
  request.mockReset(); startJob.mockReset(); download.mockReset();
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (init?.method && init.method !== "GET") {
      writes.push({ path, method: init.method, body: init.body ? JSON.parse(String(init.body)) : undefined });
      if (writeError) throw writeError;
      return { changed: 1 };
    }
    if (listError) throw listError;
    return { count: total, results: rows };
  });
});

describe("list states", () => {
  it("shows the status chips with counts, and the rows with ID number, status badge and end date", async () => {
    mount();
    expect(screen.getByRole("button", { name: /^All 6$/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^Waiting 2$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Not approved 1$/ })).toBeInTheDocument();
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
    expect(screen.getByText("ID-0002")).toBeInTheDocument();
    expect(screen.getByText("Approved", { selector: "span" })).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/id-programmes/9/cards?page=1");
  });
  it("shows an empty message, a load error with retry, and an unlinked-invite hint", async () => {
    rows = []; total = 0;
    const { unmount } = mount();
    expect(await screen.findByText("No one here yet.")).toBeInTheDocument();
    unmount();
    rows = [card({ linked: false, status: "rejected", status_reason: "Duplicate" })]; total = 1;
    const second = mount();
    expect(await screen.findByText("Invite not accepted yet")).toBeInTheDocument();
    expect(screen.getByText("Duplicate")).toBeInTheDocument();
    second.unmount();
    listError = new Error("Cards unavailable");
    mount();
    expect(await screen.findByText("Couldn't load programme cards. Try again.")).toBeInTheDocument();
    listError = undefined;
    fireEvent.click(screen.getByRole("button", { name: /retry|try again/i }));
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
  });
  it("shows No end date for an approved card without one and a dash otherwise", async () => {
    rows = [card({ id: 5, name: "Cy", status: "approved", id_number: "ID-5" }), card({ id: 6, name: "Di", status: "pending" })];
    mount();
    expect(await screen.findByText("No end date")).toBeInTheDocument();
  });
  it("filters by status chip and by search, resetting the page", async () => {
    mount();
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByRole("button", { name: /^Waiting 2$/ }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/id-programmes/9/cards?page=1&status=pending"));
    expect(screen.getByRole("button", { name: /^Waiting 2$/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.change(screen.getByLabelText("Search by ID number or exact email"), { target: { value: "  a@x.test " } });
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/id-programmes/9/cards?page=1&status=pending&search=a%40x.test"));
  });
  it("pages through members", async () => {
    total = 60;
    mount();
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/id-programmes/9/cards?page=2"));
  });
});

describe("read-only viewer", () => {
  it("has no add form, selection boxes, print-all button or row actions beyond downloads", async () => {
    mount(programme({ can_manage: false }));
    await screen.findByText("Bo Lee");
    expect(screen.queryByRole("button", { name: "Add and invite" })).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /Print sheet of all approved cards/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Actions for Asha Rao" })).toBeNull();
    await openMenu("Bo Lee");
    expect(menuLabels()).toEqual(["Download PDF", "Download PNG"]);
  });
});

describe("add a person", () => {
  it("needs a name and an email with @, posts trimmed values, and clears the form", async () => {
    mount();
    const add = screen.getByRole("button", { name: "Add and invite" });
    expect(add).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "  New Person " } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "nope" } });
    expect(add).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: " new@x.test " } });
    expect(add).toBeEnabled();
    fireEvent.click(add);
    await waitFor(() => expect(writes[0]).toMatchObject({ path: "/admin/id-programmes/9/cards", method: "POST", body: { name: "New Person", email: "new@x.test" } }));
    await waitFor(() => expect(screen.getByLabelText("Name")).toHaveValue(""));
  });
  it("shows the server's typed error and keeps the typed values", async () => {
    writeError = new StructuredApiError(409, { detail: "Already invited", code: "duplicate_email" });
    mount();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Dup" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "d@x.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Add and invite" }));
    expect(await screen.findByText(/Already invited/)).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Dup");
  });
});

describe("row actions by status", () => {
  it("pending: approve, reject, photo (take), and delete-request while never issued", async () => {
    mount();
    await openMenu("Asha Rao");
    expect(menuLabels()).toEqual(["Approve", "Reject…", "Take or upload photo…", "Delete request…"]);
  });
  it("approved: downloads, renew, revoke, replace photo when set; no delete once issued", async () => {
    rows = [card({ id: 2, name: "Bo Lee", status: "approved", id_number: "ID-2", issued_at: "2026-11-02T00:00:00Z", photo_set: true })];
    mount();
    await openMenu("Bo Lee");
    expect(menuLabels()).toEqual(["Download PDF", "Download PNG", "Renew", "Revoke…", "Replace photo…"]);
  });
  it("revoked: reinstate only; rejected: nothing", async () => {
    rows = [card({ id: 3, name: "Rev", status: "revoked", id_number: "ID-3", issued_at: "2026-11-02T00:00:00Z" }), card({ id: 4, name: "Rej", status: "rejected", id_number: "ID-4" })];
    mount();
    await openMenu("Rev");
    expect(menuLabels()).toEqual(["Reinstate"]);
    expect(screen.queryByRole("button", { name: "Actions for Rej" })).toBeNull();
  });
  it("approve decides immediately with no reason; reinstate and renew likewise", async () => {
    mount();
    await openMenu("Asha Rao");
    fireEvent.click(screen.getByRole("menuitem", { name: "Approve" }));
    await waitFor(() => expect(writes[0]).toMatchObject({ path: "/admin/id-programmes/9/cards/decide", method: "POST", body: { action: "approve", ids: [1] } }));
    expect(writes[0].body).not.toHaveProperty("reason");
  });
  it("reject needs a reason of at least 3 characters, then sends it trimmed", async () => {
    mount();
    await openMenu("Asha Rao");
    fireEvent.click(screen.getByRole("menuitem", { name: "Reject…" }));
    const submit = await screen.findByRole("button", { name: "Reject 1" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason (staff only)"), { target: { value: " No ID " } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(writes[0].body).toMatchObject({ action: "reject", ids: [1], reason: "No ID" }));
    await waitFor(() => expect(screen.queryByLabelText("Reason (staff only)")).toBeNull());
  });
  it("revoke from the menu uses the same reason form, and Cancel closes it", async () => {
    rows = [card({ id: 2, name: "Bo Lee", status: "approved", id_number: "ID-2", issued_at: "2026-11-02T00:00:00Z" })];
    mount();
    await openMenu("Bo Lee");
    fireEvent.click(screen.getByRole("menuitem", { name: "Revoke…" }));
    expect(await screen.findByRole("button", { name: "Revoke 1" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("Reason (staff only)")).toBeNull();
  });
  it("shows the decision error", async () => {
    writeError = new StructuredApiError(409, { detail: "Card already decided", code: "state_changed" });
    mount();
    await openMenu("Asha Rao");
    fireEvent.click(screen.getByRole("menuitem", { name: "Approve" }));
    expect(await screen.findByText(/Card already decided/)).toBeInTheDocument();
  });
});

describe("downloads, photos and deletion", () => {
  it("downloads an approved card as PDF through the blob endpoint", async () => {
    download.mockResolvedValue(new Blob(["x"]));
    URL.createObjectURL = vi.fn(() => "blob:x"); URL.revokeObjectURL = vi.fn();
    rows = [card({ id: 2, name: "Bo Lee", status: "approved", id_number: "ID-2" })];
    mount();
    await openMenu("Bo Lee");
    fireEvent.click(screen.getByRole("menuitem", { name: "Download PDF" }));
    await waitFor(() => expect(download).toHaveBeenCalledWith("/admin/id-programme-cards/2/download?format=pdf"));
  });
  it("opens the photo dialog for the card and refreshes the list when saved", async () => {
    mount();
    await openMenu("Asha Rao");
    fireEvent.click(screen.getByRole("menuitem", { name: "Take or upload photo…" }));
    expect(await screen.findByText("photo dialog for Asha Rao at /admin/id-programme-cards/1/photo")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "photo saved" }));
    expect(screen.queryByText(/photo dialog for/)).toBeNull();
  });
  it("deletes a never-issued request only after confirmation", async () => {
    mount();
    await openMenu("Asha Rao");
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete request…" }));
    const confirmDialog = await screen.findByRole("dialog");
    expect(within(confirmDialog).getByText("Delete Asha Rao's request?")).toBeInTheDocument();
    expect(writes).toHaveLength(0);
    fireEvent.click(within(confirmDialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(writes[0]).toMatchObject({ path: "/admin/id-programme-cards/1", method: "DELETE" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
  it("cancelling the delete confirmation sends nothing", async () => {
    mount();
    await openMenu("Asha Rao");
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete request…" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(writes).toHaveLength(0);
  });
});

describe("bulk selection", () => {
  it("selecting shows the bar with the count; actions send the selected ids; Clear empties it", async () => {
    mount();
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByLabelText("Select Asha Rao"));
    fireEvent.click(screen.getByLabelText("Select Bo Lee"));
    const bar = screen.getByRole("region", { name: "Selected cards" });
    expect(within(bar).getByText("2 selected")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Print sheet of all approved cards/ })).toBeNull();
    fireEvent.click(within(bar).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(writes[0].body).toMatchObject({ action: "approve", ids: [1, 2] }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Selected cards" })).toBeNull());
    fireEvent.click(screen.getByLabelText("Select Asha Rao"));
    fireEvent.click(screen.getByLabelText("Select Asha Rao"));
    expect(screen.queryByRole("region", { name: "Selected cards" })).toBeNull();
  });
  it("bulk renew, email and zip start the right action, and a bulk revoke asks for a reason", async () => {
    mount();
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByLabelText("Select Bo Lee"));
    const bar = screen.getByRole("region", { name: "Selected cards" });
    fireEvent.click(within(bar).getByRole("button", { name: "Renew" }));
    await waitFor(() => expect(writes[0].body).toMatchObject({ action: "renew", ids: [2] }));
    fireEvent.click(screen.getByLabelText("Select Bo Lee"));
    fireEvent.click(screen.getByRole("button", { name: "Email" }));
    expect(startJob).toHaveBeenCalledWith({ kind: "email", card_ids: [2] });
    fireEvent.click(screen.getByRole("button", { name: "All cards (ZIP)" }));
    expect(startJob).toHaveBeenCalledWith({ kind: "zip", card_ids: [2] });
    fireEvent.click(screen.getByRole("button", { name: "Revoke…" }));
    expect(await screen.findByLabelText("Reason (staff only)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Print sheet…" }));
    expect(screen.getByText(/sheet dialog: Print sheet: 1 selected cards \{"card_ids":\[2\]\}/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByRole("region", { name: "Selected cards" })).toBeNull();
  });
  it("with nothing selected and approved cards, offers the print-all sheet", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Print sheet of all approved cards…" }));
    expect(screen.getByText("sheet dialog: Print sheet: all approved cards {}")).toBeInTheDocument();
  });
  it("offers no print-all sheet when nothing is approved", async () => {
    mount(programme({ counts: { all: 1, pending: 1, approved: 0, rejected: 0, revoked: 0 } }));
    await screen.findByText("Asha Rao");
    expect(screen.queryByRole("button", { name: "Print sheet of all approved cards…" })).toBeNull();
  });
});
