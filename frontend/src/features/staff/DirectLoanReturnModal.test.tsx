import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DirectLoanReturnModal } from "./DirectLoanReturnModal";
import type { DirectLoan } from "./DirectLoanList";
vi.mock("./panels/EvidenceUpload", () => ({ EvidenceUpload: ({ onUploaded }: { onUploaded: (id: number) => void }) => <button onClick={() => onUploaded(9)}>Upload return photo</button> }));
vi.mock("../inventory/KitChecklist", () => ({ useKitChecklist: () => ({ ready: true, counts: [] }), KitChecklistCapture: () => null }));
const loan: DirectLoan = { id: 8, public_token: "loan", status: "checked_out", target_label: "Ada", due_at: null, issued_by: null, items: [{ product_name: "Drill", quantity: 2 }], return_scan_required: true,
  return_items: [{ item_id: 4, product_name: "Drill", remaining_quantity: 2, tracking_mode: "bulk", assets: [] }] };
it("keeps photo, required QR, notes, and every item resolution mandatory across the return steps", async () => {
  const submit = vi.fn();
  function ReturnTask() {
    const [evidence, setEvidence] = useState<number | null>(null);
    const [notes, setNotes] = useState("");
    const [qr, setQr] = useState("");
    return <DirectLoanReturnModal loan={loan} makerspaceId={1} evidenceId={evidence} notes={notes} qrPayload={qr}
      pending={false} error="" onEvidenceUploaded={setEvidence} onNotesChange={setNotes}
      onQrPayloadChange={setQr} onCancel={vi.fn()} onSubmit={submit} />;
  }
  render(<ReturnTask />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Returned"), { target: { value: "1" } });
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Returned"), { target: { value: "2" } });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Upload return photo" }));
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Return QR scan"), { target: { value: "TOOL-QR" } });
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByRole("button", { name: "Submit return" })).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox", { name: "Return notes" }), { target: { value: "Both drills returned in good condition." } });
  fireEvent.click(screen.getByRole("button", { name: "Submit return" }));
  expect(submit).toHaveBeenCalledWith([{ item_id: 4, returned: 2, damaged: 0, missing: 0 }], []);
  expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  expect(document.querySelectorAll("h2.title-page")).toHaveLength(1);
});

it("rejects negative or fractional outcome buckets even when their sum resolves every unit", () => {
  render(<DirectLoanReturnModal loan={loan} makerspaceId={1} evidenceId={9} notes="Returned" qrPayload="QR"
    pending={false} error="" onEvidenceUploaded={vi.fn()} onNotesChange={vi.fn()} onQrPayloadChange={vi.fn()}
    onCancel={vi.fn()} onSubmit={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Returned"), { target: { value: "-1" } });
  fireEvent.change(screen.getByLabelText("Damaged"), { target: { value: "3" } });
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Returned"), { target: { value: "0.5" } });
  fireEvent.change(screen.getByLabelText("Damaged"), { target: { value: "1.5" } });
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Returned"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Damaged"), { target: { value: "0" } });
  expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
});
