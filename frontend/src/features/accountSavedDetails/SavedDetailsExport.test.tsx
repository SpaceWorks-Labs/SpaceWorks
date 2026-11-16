import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { SavedDetailsExport } from "./SavedDetailsExport";
import { downloadExport, exportStatus, requestExport, saveBlob } from "./api";
import type { ExportJob } from "./types";

vi.mock("./api", () => ({ downloadExport: vi.fn(), exportStatus: vi.fn(), requestExport: vi.fn(), saveBlob: vi.fn() }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionGeneration: () => 1 }));
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function fixture() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const ui = (actorId: number) => <QueryClientProvider client={client}><SavedDetailsExport actorId={actorId} /></QueryClientProvider>;
  return { ...render(ui(1)), ui };
}
beforeEach(() => { vi.resetAllMocks(); vi.mocked(requestExport).mockResolvedValue({ job_id: "job-one", state: "queued" }); vi.mocked(exportStatus).mockResolvedValue({ job_id: "job-one", state: "ready" }); });

it("recovers a lost create response by replaying its original operation ID", async () => {
  vi.mocked(requestExport).mockRejectedValueOnce(new Error("Connection lost"));
  fixture(); fireEvent.click(screen.getByRole("button", { name: "Create saved details archive" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Create saved details archive" }));
  expect(await screen.findByRole("button", { name: "Download archive" })).toBeVisible();
  expect(vi.mocked(requestExport).mock.calls[0][0]).toBe(vi.mocked(requestExport).mock.calls[1][0]);
});

it("retains the existing job across a status failure and offers explicit status retry", async () => {
  vi.mocked(exportStatus).mockRejectedValueOnce(new Error("Status unavailable"));
  fixture(); fireEvent.click(screen.getByRole("button", { name: "Create saved details archive" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry archive status" }));
  expect(await screen.findByRole("button", { name: "Download archive" })).toBeVisible();
  expect(requestExport).toHaveBeenCalledOnce();
  expect(vi.mocked(exportStatus).mock.calls.map(call => call[0])).toEqual(["job-one", "job-one"]);
});

it("discards a previous account's pending create and download results", async () => {
  const creating = deferred<ExportJob>(); vi.mocked(requestExport).mockReturnValueOnce(creating.promise);
  const result = fixture(); fireEvent.click(screen.getByRole("button", { name: "Create saved details archive" }));
  await waitFor(() => expect(requestExport).toHaveBeenCalledOnce());
  result.rerender(result.ui(2)); await act(async () => creating.resolve({ job_id: "foreign-job", state: "queued" }));
  expect(exportStatus).not.toHaveBeenCalled(); expect(screen.queryByRole("button", { name: "Download archive" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Create saved details archive" }));
  const downloading = deferred<Blob>(); vi.mocked(downloadExport).mockReturnValueOnce(downloading.promise);
  fireEvent.click(await screen.findByRole("button", { name: "Download archive" }));
  result.rerender(result.ui(3)); await act(async () => downloading.resolve(new Blob(["private archive"])));
  expect(saveBlob).not.toHaveBeenCalled();
});
