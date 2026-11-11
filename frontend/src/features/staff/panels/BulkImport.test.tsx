import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { BulkImport } from "./BulkImport";
import type { Makerspace } from "./shared";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
function setup(errors = 0) {
 request.mockResolvedValue({ summary: { create: 1, update: 0, errors, warnings: 0, total: 1 }, rows: [{ row: 1, action: "create", data: { name: "Drill" } }] });
 render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkImport makerspace={{ id: 7, slug: "forge" } as Makerspace} /></QueryClientProvider>);
 fireEvent.click(screen.getByText("Use JSON instead"));
 fireEvent.change(screen.getByLabelText("JSON rows"), { target: { value: '[{"name":"Drill","total_quantity":"1"}]' } });
 fireEvent.click(screen.getByRole("button", { name: "Preview JSON" }));
}
beforeEach(() => { request.mockReset(); });
it("lets a partially valid preview import, skipping the rows with errors", async () => {
 setup(1);
 expect(await screen.findByRole("button", { name: "Import 0 valid rows, skip 1" })).toBeEnabled();
 expect(request).not.toHaveBeenCalledWith(expect.stringContaining("/apply"), expect.anything());
});
it("imports exactly the reviewed JSON payload", async () => {
 setup();
 fireEvent.click(await screen.findByRole("button", { name: "Import 1 row" }));
 await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/inventory/import/apply", { method: "POST", body: JSON.stringify({ rows: [{ name: "Drill", total_quantity: "1" }] }) }));
 expect(await screen.findByText("Import complete")).toBeInTheDocument();
});

it("keeps the source draft available after an import fails", async () => {
 setup();
 const apply = await screen.findByRole("button", { name: "Import 1 row" });
 request.mockRejectedValueOnce(new Error("Storage unavailable"));
 fireEvent.click(apply);
 fireEvent.click(await screen.findByRole("button", { name: "Review and try again" }));
 expect(screen.getByLabelText("JSON rows")).toHaveValue('[{"name":"Drill","total_quantity":"1"}]');
 expect(screen.getByRole("button", { name: "Preview JSON" })).toBeInTheDocument();
});

it("reads an .xlsx on the server and moves to column matching with its headers", async () => {
 request.mockResolvedValueOnce({ rows: [{ Item: "Drill", Qty: 2 }] });
 render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkImport makerspace={{ id: 7, slug: "forge" } as Makerspace} /></QueryClientProvider>);
 const file = new File(["PK"], "stock.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
 fireEvent.change(screen.getByLabelText("Upload CSV or XLSX"), { target: { files: [file] } });
 await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/makerspace/7/inventory/import/sheet", { method: "POST", body: expect.any(FormData) }));
 const body = request.mock.calls[0][1].body as FormData;
 expect(body.get("file")).toBe(file);
 expect(await screen.findByLabelText("name")).toHaveValue("Item");
 expect(screen.getByLabelText("total quantity")).toHaveValue("Qty");
});

it("shows the server's reason when an .xlsx cannot be read", async () => {
 request.mockRejectedValueOnce(new Error("XLSX file could not be read."));
 render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkImport makerspace={{ id: 7, slug: "forge" } as Makerspace} /></QueryClientProvider>);
 fireEvent.change(screen.getByLabelText("Upload CSV or XLSX"), { target: { files: [new File(["x"], "bad.xlsx")] } });
 expect(await screen.findByText(/XLSX file could not be read/)).toBeInTheDocument();
});

it("blocks import until QR code conflicts in the file are fixed", async () => {
 request.mockResolvedValue({ valid: false, summary: { create: 1, update: 0, errors: 1, warnings: 0, total: 2 },
  errors: [{ row: 3, errors: { qr_code: "Duplicate QR code in this file (also row 2)." } }],
  rows: [{ row: 2, action: "create", data: { name: "Drill", qr_code: "A-1" } }, { row: 3, action: "error", data: { name: "Saw", qr_code: "A-1" } }] });
 render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BulkImport makerspace={{ id: 7, slug: "forge" } as Makerspace} /></QueryClientProvider>);
 fireEvent.click(screen.getByText("Use JSON instead"));
 fireEvent.change(screen.getByLabelText("JSON rows"), { target: { value: '[{"name":"Drill","qr_code":"A-1"},{"name":"Saw","qr_code":"A-1"}]' } });
 fireEvent.click(screen.getByRole("button", { name: "Preview JSON" }));
 expect(await screen.findByText("qr_code: Duplicate QR code in this file (also row 2).")).toBeInTheDocument();
 expect(screen.getByRole("button", { name: "Import 1 valid row, skip 1" })).toBeDisabled();
 expect(screen.getAllByText(/Fix the QR code problems in your file/).length).toBeGreaterThan(0);
});

it("suggests the qr_code column from a QR header", async () => {
 const { suggestMapping } = await import("./BulkImportHelpers");
 expect(suggestMapping(["Item", "QR Code"]).qr_code).toBe("QR Code");
});
