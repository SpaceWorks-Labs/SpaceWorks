import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { ReceiptViewer } from "./ReceiptViewer";
import { MaskedPayoutExport } from "./MaskedPayoutExport";
import { scope } from "./testData";
import type { Receipt } from "./types";
vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn(), memberRequest: vi.fn(), staffRequestBlob: vi.fn() }));
afterEach(() => vi.restoreAllMocks());
const receipt: Receipt = { id: "receipt", generation: 1, bytes: 30, sha256: "safe-hash", state: "ready", mime: "image/png", allowed_actions: ["download"] };
function urls() {
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:private-file") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
}
describe("private finance files", () => {
  it("fetches receipts through authenticated no-store requests and revokes URLs on blur", async () => {
    urls(); vi.mocked(staffRequestBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    render(<ReceiptViewer scope={scope} receipt={receipt} />);
    fireEvent.click(screen.getByRole("button", { name: "Open finance receipt" }));
    await screen.findByRole("img");
    expect(staffRequestBlob).toHaveBeenCalledWith("/admin/makerspaces/2/event-payouts/attachments/receipt/download/", expect.objectContaining({ cache: "no-store" }));
    fireEvent.blur(window); expect(screen.queryByRole("img")).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:private-file");
  });
  it("discards late receipt responses after unmount", async () => {
    urls(); let resolve!: (value: Blob) => void;
    vi.mocked(staffRequestBlob).mockReturnValue(new Promise(value => { resolve = value; }));
    const view = render(<ReceiptViewer scope={scope} receipt={receipt} />);
    fireEvent.click(screen.getByRole("button", { name: "Open finance receipt" })); view.unmount();
    await act(async () => resolve(new Blob(["png"], { type: "image/png" })));
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
  it("does not offer expired bytes or render unexpected MIME as active content", async () => {
    urls(); vi.mocked(staffRequestBlob).mockResolvedValue(new Blob(["<script>"], { type: "text/html" }));
    const view = render(<ReceiptViewer scope={scope} receipt={receipt} />);
    fireEvent.click(screen.getByRole("button", { name: "Open finance receipt" })); await screen.findByRole("alert");
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    view.rerender(<ReceiptViewer scope={scope} receipt={{ ...receipt, state: "expired", allowed_actions: [] }} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
  it("previews a server batch and downloads masked CSV without recording a payment", async () => {
    urls(); const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.mocked(staffRequest).mockResolvedValue({ id: "batch", expires_at: "2099-01-01T00:00:00Z", allowed_actions: ["export"],
      preview: [{ obligation_id: "obligation", currency: "INR", remaining_minor: 1000, masked_payee: "••••7890" }] });
    vi.mocked(staffRequestBlob).mockResolvedValue(new Blob(["masked,csv"], { type: "text/csv" }));
    render(<MaskedPayoutExport scope={scope} ids={["obligation"]} allowed />);
    fireEvent.click(screen.getByRole("button", { name: "Preview masked CSV" })); await screen.findByText(/••••7890/);
    expect(staffRequest).toHaveBeenLastCalledWith("/admin/makerspaces/2/event-payouts/exports/", expect.objectContaining({ method: "POST", cache: "no-store" }));
    fireEvent.click(screen.getByRole("button", { name: "Download masked CSV" }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(staffRequestBlob).toHaveBeenLastCalledWith("/admin/makerspaces/2/event-payouts/exports/batch/download/", expect.objectContaining({ cache: "no-store" }));
    expect(vi.mocked(staffRequest).mock.calls.every(([path]) => !path.includes("/record/"))).toBe(true);
  });
  it("blocks expired downloads and creates a new UUID for a replacement batch", async () => {
    vi.mocked(staffRequest).mockClear();
    vi.mocked(staffRequest).mockResolvedValue({ id: "batch", expires_at: "2000-01-01T00:00:00Z", allowed_actions: ["export"],
      preview: [{ obligation_id: "obligation", currency: "INR", remaining_minor: 1000, masked_payee: "••••7890" }] });
    render(<MaskedPayoutExport scope={scope} ids={["obligation"]} allowed />);
    fireEvent.click(screen.getByRole("button", { name: "Preview masked CSV" })); await screen.findByText(/This batch expired/);
    expect(screen.getByRole("button", { name: "Download masked CSV" })).toBeDisabled();
    const first = JSON.parse(vi.mocked(staffRequest).mock.calls[0][1]!.body as string);
    fireEvent.click(screen.getByRole("button", { name: "Preview masked CSV" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
    expect(JSON.parse(vi.mocked(staffRequest).mock.calls[1][1]!.body as string).operation_id).not.toBe(first.operation_id);
  });
});
