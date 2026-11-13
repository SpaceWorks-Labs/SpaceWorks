import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { CollectionSheet } from "./CollectionSheet";
import { localToday, parsePasted, rowProblem, toInput, type SheetRow } from "./collectionSheetRows";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const today = localToday();
const paste = (text: string) => {
  fireEvent.click(screen.getByText("Paste from a spreadsheet"));
  fireEvent.change(screen.getByLabelText("Copied cells"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Add pasted rows" }));
};

beforeEach(() => { staffRequest.mockReset(); });

describe("collection sheet rows", () => {
  it("reads tab-separated cells, skips a header and maps method words and day-first dates", () => {
    let key = 0;
    const rows = parsePasted("Charge\tMethod\tRef\tDate\n#12\tGPay\tUTR9\t05/11/2026\n13\t\t\t", { method: "cash", date: "2026-11-10" }, () => ++key);
    expect(rows).toEqual([
      { key: 1, payment: "12", method: "upi", reference: "UTR9", date: "2026-11-05" },
      { key: 2, payment: "13", method: "cash", reference: "", date: "2026-11-10" },
    ]);
  });

  it("flags a missing number, a duplicate, an unknown method and a future date", () => {
    const row = (payment: string, extra: Partial<SheetRow> = {}): SheetRow => ({ key: 1, payment, method: "cash", reference: "", date: "2026-11-10", ...extra });
    expect(rowProblem(row(""), [], "2026-11-11")).toMatch(/charge number/);
    expect(rowProblem(row("4"), [row("4")], "2026-11-11")).toMatch(/already on the sheet/);
    expect(rowProblem(row("4", { method: "bitcoin" }), [], "2026-11-11")).toMatch(/how the money was paid/);
    expect(rowProblem(row("4", { date: "2026-11-12" }), [], "2026-11-11")).toMatch(/future/);
    expect(rowProblem(row("4"), [], "2026-11-11")).toBeNull();
  });

  it("sends a past date at local noon and today's date as the moment of recording", () => {
    const now = new Date("2026-11-11T09:30:00");
    expect(toInput({ key: 1, payment: " 7 ", method: "upi", reference: " R1 ", date: "2026-11-11" }, "2026-11-11", now))
      .toEqual({ payment_id: 7, method: "upi", reference: "R1", received_at: now.toISOString() });
    expect(toInput({ key: 1, payment: "7", method: "cash", reference: "", date: "2026-11-01" }, "2026-11-11", now).received_at)
      .toBe(new Date("2026-11-01T12:00:00").toISOString());
  });
});

describe("CollectionSheet", () => {
  it("explains the two-person check when maker-checker is on", () => {
    wrap(<CollectionSheet makerspaceId={3} makerChecker />);
    expect(screen.getByTestId("maker-checker-note")).toHaveTextContent(/Two-person check is on/);
    expect(screen.getByTestId("maker-checker-note")).toHaveTextContent(/can't confirm rows you recorded yourself/);
  });

  it("has no maker-checker note when the check is off", () => {
    wrap(<CollectionSheet makerspaceId={3} makerChecker={false} />);
    expect(screen.queryByTestId("maker-checker-note")).not.toBeInTheDocument();
  });

  it("blocks recording while a pasted row is invalid", () => {
    wrap(<CollectionSheet makerspaceId={3} makerChecker={false} />);
    paste(`5\tcash\t\t${today}\n5\tcash\t\t${today}`);
    expect(screen.getByText("This charge is already on the sheet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record 2 payments" })).toBeDisabled();
  });

  it("records the sheet and shows each row's own result", async () => {
    staffRequest.mockResolvedValue({ summary: { rows: 3, recorded: 1, awaiting_confirmation: 1, failed: 1 }, results: [
      { index: 0, payment_id: 5, outcome: "recorded", code: "", detail: "" },
      { index: 1, payment_id: 6, outcome: "awaiting_confirmation", code: "", detail: "" },
      { index: 2, payment_id: 7, outcome: "failed", code: "payment_terminal", detail: "Payment is already final." },
    ] });
    wrap(<CollectionSheet makerspaceId={3} makerChecker={false} />);
    paste(`5\tcash\n6\tupi\n7\tcheque\tCHQ 1`);
    fireEvent.click(screen.getByRole("button", { name: "Record 3 payments" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/billing/collection-sheet",
      expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(staffRequest.mock.calls[0][1].body as string);
    expect(body.rows.map((row: { payment_id: number; method: string }) => [row.payment_id, row.method])).toEqual([[5, "cash"], [6, "upi"], [7, "cheque"]]);
    const grid = screen.getByRole("region", { name: "Collection sheet rows" });
    expect(await within(grid).findByText("Recorded")).toBeInTheDocument();
    expect(within(grid).getByText("Waiting for a second person")).toBeInTheDocument();
    expect(within(grid).getByText("Already paid, waived or closed.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 recorded, 1 waiting for a second person, 1 not recorded");
    // Only the failed row is still open; the recorded ones are locked.
    expect(screen.getByRole("button", { name: "Record 1 payment" })).toBeEnabled();
    expect(within(grid).getByLabelText("Charge number, row 1")).toBeDisabled();
  });

  it("says when the monthly allowance refuses the whole sheet", async () => {
    staffRequest.mockRejectedValue(new StructuredApiError(409, { code: "collection_sheet_rows_monthly_quota_reached", detail: "Quota." }));
    wrap(<CollectionSheet makerspaceId={3} makerChecker />);
    paste(`9\tcash`);
    fireEvent.click(screen.getByRole("button", { name: "File 1 payment for confirmation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/monthly allowance/);
  });
});
