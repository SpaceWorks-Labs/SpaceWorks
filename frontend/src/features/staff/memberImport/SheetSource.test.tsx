import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProgrammeImport } from "../../organizations/idProgrammes/ProgrammeImport";
import type { Programme } from "../../organizations/idProgrammes/api";
import { MemberImportWizard } from "./MemberImportWizard";
import { sheetLinkProblem } from "./SheetSource";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const LINK = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit#gid=0";
const SHA = "a".repeat(64);
const memberPreview = {
  headers: ["Email"], mapping: { email: "Email" }, suggested_mapping: { email: "Email" }, counts: { create: 1, update: 0, skip: 0 },
  total_rows: 1, rows: [{ row: 2, action: "create", reason: "", data: { email: "a@example.test" } }],
  source: "google_sheet", sheet_sha256: SHA,
};
const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{node}</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("sheet link validation", () => {
  it("accepts share and published links and names the fix otherwise", () => {
    expect(sheetLinkProblem(LINK)).toBe("");
    expect(sheetLinkProblem("https://docs.google.com/spreadsheets/d/e/2PACX-1AbCdEfGhIjKlMnOpQrStUv/pubhtml")).toBe("");
    expect(sheetLinkProblem("")).toMatch(/Paste/);
    expect(sheetLinkProblem("https://example.test/sheet.csv")).toMatch(/docs\.google\.com/);
    expect(sheetLinkProblem("http://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUv")).not.toBe("");
  });
});

describe("member import from a Google Sheet (L13)", () => {
  it("hides the sheet source while its switch is off", () => {
    wrap(<MemberImportWizard makerspaceId={4} open onClose={vi.fn()} />);
    expect(screen.queryByRole("radio", { name: "Google Sheets link" })).toBeNull();
    expect(screen.getByLabelText("Member file")).toBeVisible();
  });

  it("previews and applies a sheet, sending the preview's digest back", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(String(path).endsWith("/preview") ? memberPreview
      : { batch_id: 3, counts: { invited: 1, record_only: 0, updated: 0, skipped: 0 }, rows: [] }));
    wrap(<MemberImportWizard makerspaceId={4} open onClose={vi.fn()} sheetsEnabled />);
    fireEvent.click(screen.getByRole("radio", { name: "Google Sheets link" }));
    expect(screen.getByText(/Anyone with the link · Viewer/)).toBeVisible();
    const field = screen.getByLabelText("Sheet link");
    fireEvent.change(field, { target: { value: "https://example.test/x" } });
    fireEvent.blur(field);
    expect(screen.getByText(/starts with https:\/\/docs\.google\.com\/spreadsheets/)).toBeVisible();
    expect(field).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(field, { target: { value: LINK } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText(/Dry run: 1 new/)).toBeVisible();
    const previewBody = staffRequest.mock.calls[0][1].body as FormData;
    expect(previewBody.get("source")).toBe("google_sheet");
    expect(previewBody.get("url")).toBe(LINK);
    expect(previewBody.get("file")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByText("Import finished")).toBeVisible();
    const applyBody = staffRequest.mock.calls.find(([path]) => String(path).endsWith("/apply"))![1].body as FormData;
    expect(applyBody.get("sheet_sha256")).toBe(SHA);
    expect(applyBody.get("source")).toBe("google_sheet");
  });
});

const programme = { id: 9, form_schema: [] } as unknown as Programme;

describe("ID-programme import from a Google Sheet (L13)", () => {
  it("only offers the sheet with its switch on", () => {
    wrap(<ProgrammeImport programme={programme} onDone={vi.fn()} />);
    expect(screen.queryByRole("radio", { name: "Google Sheets link" })).toBeNull();
  });

  it("previews and commits a sheet with the digest", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(String(path).endsWith("/preview")
      ? { headers: ["Name", "Email"], rows: [["A", "a@example.test"]], mapping: { name: 0, email: 1 }, rows_total: 1,
        to_create: 1, skipped: [], source: "google_sheet", sheet_sha256: SHA }
      : { created: 1, skipped: [] }));
    const onDone = vi.fn();
    wrap(<ProgrammeImport programme={programme} onDone={onDone} sheetImport />);
    fireEvent.click(screen.getByRole("radio", { name: "Google Sheets link" }));
    const preview = screen.getByRole("button", { name: "Preview" });
    expect(preview).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Sheet link"), { target: { value: LINK } });
    fireEvent.click(preview);
    fireEvent.click(await screen.findByRole("button", { name: "Add 1 people" }));
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    const [, previewInit] = staffRequest.mock.calls[0];
    expect(JSON.parse(previewInit.body)).toEqual({ source: "google_sheet", url: LINK });
    const [, commitInit] = staffRequest.mock.calls[1];
    expect(JSON.parse(commitInit.body)).toMatchObject({ source: "google_sheet", url: LINK, sheet_sha256: SHA,
      mapping: { name: 0, email: 1 }, approve: false });
  });
});
