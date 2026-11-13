import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WarrantySection } from "./WarrantySection";
import type { Warranty } from "./warrantyApi";

const api = vi.hoisted(() => ({ getWarranty: vi.fn(), saveWarranty: vi.fn(), uploadWarrantyDocument: vi.fn(), deleteWarrantyDocument: vi.fn(), getWarrantyDocumentUrl: vi.fn() }));
vi.mock("./warrantyApi", () => api);

const warranty = (over: Partial<Warranty> = {}): Warranty => ({ id: 3, host_kind: "asset", host_id: 9, host_label: "Iron", asset_id: 9, asset_tag: "AS-9", serial_number: null, printer_id: null, printer_name: null,
  printer_model: null, machine_id: null, machine_name: null, purchased_on: "2026-01-05", warranty_expires_on: "2027-01-05", vendor_name: "Hakko", vendor_contact: "sales@hakko.test", status: "active",
  documents: [{ id: 1, original_filename: "invoice.pdf", content_type: "application/pdf", size_bytes: 512, created_at: "2026-01-06T00:00:00Z" },
    { id: 2, original_filename: "scan.png", content_type: "image/png", size_bytes: 2048, created_at: "2026-01-06T00:00:00Z" },
    { id: 3, original_filename: "big.pdf", content_type: "application/pdf", size_bytes: 3 * 1024 * 1024, created_at: "2026-01-06T00:00:00Z" }], ...over });

function mount(props: Partial<Parameters<typeof WarrantySection>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}><WarrantySection hostKind="asset" hostId={9} {...props} /></QueryClientProvider>) };
}
const dateInput = (label: string) => screen.getByText(label).closest("div")!.parentElement!.querySelector("input")! as HTMLInputElement;

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  api.getWarranty.mockResolvedValue(warranty());
  api.saveWarranty.mockImplementation(async (_k: string, _i: number, payload: object) => ({ ...warranty(), ...payload }));
  api.uploadWarrantyDocument.mockResolvedValue({});
  api.deleteWarrantyDocument.mockResolvedValue({});
  api.getWarrantyDocumentUrl.mockResolvedValue({ url: "https://files.test/doc" });
});

describe("loading and display", () => {
  it("loads the record for the host, shows its values, status badge, and sized documents", async () => {
    mount();
    expect(await screen.findByDisplayValue("Hakko")).toBeInTheDocument();
    expect(api.getWarranty).toHaveBeenCalledWith("asset", 9);
    expect(dateInput("Purchased")).toHaveValue("2026-01-05");
    expect(dateInput("Expires")).toHaveValue("2027-01-05");
    expect(screen.getByDisplayValue("sales@hakko.test")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("512 B")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("3.0 MB")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  });
  it("shows an unknown status and empty values for a record with nulls", async () => {
    api.getWarranty.mockResolvedValue(warranty({ purchased_on: null, warranty_expires_on: null, vendor_name: "", vendor_contact: "", status: "unknown", documents: [] }));
    mount();
    expect(await screen.findByText("Uncovered / no warranty")).toBeInTheDocument();
    expect(screen.getByText("No documents attached.")).toBeInTheDocument();
    expect(dateInput("Purchased")).toHaveValue("");
  });
  it("shows a load error with a retry", async () => {
    api.getWarranty.mockRejectedValueOnce(new Error("Warranty down")).mockResolvedValue(warranty());
    mount();
    expect(await screen.findByText("Couldn't load warranty details. Try again.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByDisplayValue("Hakko")).toBeInTheDocument();
  });
  it("shows the badge for expiring and expired warranties", async () => {
    api.getWarranty.mockResolvedValue(warranty({ status: "expiring_soon" }));
    const { unmount } = mount();
    expect(await screen.findByText("Expiring soon")).toBeInTheDocument();
    unmount();
    api.getWarranty.mockResolvedValue(warranty({ status: "expired" }));
    mount();
    expect(await screen.findByText("Expired")).toBeInTheDocument();
  });
});

describe("editing", () => {
  it("shows save and discard once changed; save sends trimmed values and null for blank dates", async () => {
    mount();
    await screen.findByDisplayValue("Hakko");
    fireEvent.change(screen.getByDisplayValue("Hakko"), { target: { value: "  Weller  " } });
    fireEvent.change(dateInput("Purchased"), { target: { value: "" } });
    fireEvent.change(screen.getByDisplayValue("sales@hakko.test"), { target: { value: " help@weller.test " } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(api.saveWarranty).toHaveBeenCalledWith("asset", 9, { purchased_on: null, warranty_expires_on: "2027-01-05", vendor_name: "Weller", vendor_contact: "help@weller.test" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull());
  });
  it("discard restores the saved values", async () => {
    mount();
    fireEvent.change(await screen.findByDisplayValue("Hakko"), { target: { value: "Other" } });
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByDisplayValue("Hakko")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  });
  it("shows the save error and keeps the edits", async () => {
    api.saveWarranty.mockRejectedValue(new Error("Expiry before purchase"));
    mount();
    fireEvent.change(await screen.findByDisplayValue("Hakko"), { target: { value: "Other" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText(/Expiry before purchase/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("Other")).toBeInTheDocument();
  });
  it("a host with no warranty yet offers Save immediately and says documents need a saved record", async () => {
    api.getWarranty.mockResolvedValue(null);
    mount();
    expect(await screen.findByText("Save warranty details first to attach documents.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Add warranty documents")).toBeNull();
  });
  it("read-only mode disables fields and hides save, remove and upload", async () => {
    mount({ disabled: true });
    expect(await screen.findByDisplayValue("Hakko")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove…" })).toBeNull();
    expect(screen.queryByLabelText("Add warranty documents")).toBeNull();
    expect(screen.queryByText("Save warranty details first to attach documents.")).toBeNull();
    expect(screen.getAllByRole("button", { name: "View" })).toHaveLength(3);
  });
});

describe("documents", () => {
  it("opens a document through its signed URL in a new window", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);
    mount();
    fireEvent.click((await screen.findAllByRole("button", { name: "View" }))[0]);
    await waitFor(() => expect(open).toHaveBeenCalledWith("https://files.test/doc", "_blank", "noopener"));
    expect(api.getWarrantyDocumentUrl).toHaveBeenCalledWith(1);
    open.mockRestore();
  });
  it("shows why a document could not be opened", async () => {
    api.getWarrantyDocumentUrl.mockRejectedValue(new Error("Link expired"));
    mount();
    fireEvent.click((await screen.findAllByRole("button", { name: "View" }))[0]);
    expect(await screen.findByText("Link expired")).toBeInTheDocument();
  });
  it("removes a document only after confirmation, by id", async () => {
    mount();
    fireEvent.click((await screen.findAllByRole("button", { name: "Remove…" }))[1]);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Remove warranty document?")).toBeInTheDocument();
    expect(api.deleteWarrantyDocument).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(api.deleteWarrantyDocument).toHaveBeenCalled());
    expect(api.deleteWarrantyDocument.mock.calls[0][0]).toBe(2);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
  it("cancelling the removal sends nothing", async () => {
    mount();
    fireEvent.click((await screen.findAllByRole("button", { name: "Remove…" }))[0]);
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(api.deleteWarrantyDocument).not.toHaveBeenCalled();
  });
  it("shows a removal failure", async () => {
    api.deleteWarrantyDocument.mockRejectedValue(new Error("Already gone"));
    mount();
    fireEvent.click((await screen.findAllByRole("button", { name: "Remove…" }))[0]);
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Already gone")).toBeInTheDocument();
  });
  it("uploads every chosen file in order against the warranty id and refreshes", async () => {
    mount();
    const input = await screen.findByLabelText("Add warranty documents");
    expect(input).toHaveAttribute("accept", "application/pdf,image/jpeg,image/png,image/webp");
    const a = new File(["a"], "a.pdf", { type: "application/pdf" }); const b = new File(["b"], "b.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [a, b] } });
    await waitFor(() => expect(api.uploadWarrantyDocument).toHaveBeenCalledTimes(2));
    expect(api.uploadWarrantyDocument.mock.calls.map(([id, file]) => [id, (file as File).name])).toEqual([[3, "a.pdf"], [3, "b.png"]]);
    await waitFor(() => expect(api.getWarranty.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
  it("ignores an empty file selection", async () => {
    mount();
    fireEvent.change(await screen.findByLabelText("Add warranty documents"), { target: { files: [] } });
    expect(api.uploadWarrantyDocument).not.toHaveBeenCalled();
  });
  it("shows Uploading… while pending and the upload failure afterwards", async () => {
    let fail: (error: Error) => void = () => undefined;
    api.uploadWarrantyDocument.mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; }));
    mount();
    fireEvent.change(await screen.findByLabelText("Add warranty documents"), { target: { files: [new File(["a"], "a.pdf")] } });
    expect(await screen.findByText("Uploading…")).toBeInTheDocument();
    expect(screen.getByLabelText("Add warranty documents")).toBeDisabled();
    fail(new Error("File too large"));
    expect(await screen.findByText("File too large")).toBeInTheDocument();
  });
});

describe("fallback messages for non-Error failures", () => {
  it("says Could not open document when the URL request rejects without a message", async () => {
    api.getWarrantyDocumentUrl.mockRejectedValue("nope");
    mount();
    fireEvent.click((await screen.findAllByRole("button", { name: "View" }))[0]);
    expect(await screen.findByText("Could not open document.")).toBeInTheDocument();
  });
  it("says Upload failed. when the upload rejects without a message", async () => {
    api.uploadWarrantyDocument.mockRejectedValue("nope");
    mount();
    fireEvent.change(await screen.findByLabelText("Add warranty documents"), { target: { files: [new File(["a"], "a.pdf")] } });
    expect(await screen.findByText("Upload failed.")).toBeInTheDocument();
  });
});
