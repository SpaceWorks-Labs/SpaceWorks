import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { ResumeVault } from "./ResumeVault";
import { completeResume, createResume, deleteResume, downloadResume, resumeStatus, saveBlob, saveDetail, uploadResume } from "./api";
import type { ResumeAsset, SavedField } from "./types";

vi.mock("./api", () => ({ completeResume: vi.fn(), createResume: vi.fn(), deleteResume: vi.fn(), downloadResume: vi.fn(), resumeStatus: vi.fn(), saveBlob: vi.fn(), saveDetail: vi.fn(), uploadResume: vi.fn() }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionGeneration: () => 1 }));
const asset: ResumeAsset = { asset_id: 41, state: "uploading", sha256: "", bytes: 20, version: 1, generation: 1, upload: { method: "POST", url: "https://storage.example/upload", fields: {}, expires_at: "2099-01-01T00:00:00Z" } };
const ready: ResumeAsset = { ...asset, state: "ready", version: 3, sha256: "abc" };
const saved: SavedField = { field_key: "resume", value: { asset_id: 41, sha256: "abc" }, version: 1, sensitive: true, default_save: false };
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function fixture(actor = 1, value?: SavedField) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const ui = (id: number, row?: SavedField) => <QueryClientProvider client={client}><ResumeVault actorId={id} saved={row} /></QueryClientProvider>;
  return { ...render(ui(actor, value)), ui };
}
function select(name = "resume.pdf") { fireEvent.change(screen.getByLabelText("Private résumé"), { target: { files: [new File(["pdf bytes"], name, { type: "application/pdf" })] } }); }
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(createResume).mockResolvedValue(asset);
  vi.mocked(uploadResume).mockResolvedValue(undefined);
  vi.mocked(completeResume).mockResolvedValue({ ...asset, state: "validating", version: 2 });
  vi.mocked(resumeStatus).mockResolvedValue(ready);
  vi.mocked(deleteResume).mockResolvedValue({ ...ready, state: "deleting" });
});

it("retries a lost create with one operation ID and advances into validation", async () => {
  vi.mocked(createResume).mockRejectedValueOnce(new Error("Connection lost"));
  fixture(); select(); fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await screen.findByRole("checkbox");
  expect(createResume).toHaveBeenCalledTimes(2);
  expect(vi.mocked(createResume).mock.calls[0][1]).toBe(vi.mocked(createResume).mock.calls[1][1]);
  expect(uploadResume).toHaveBeenCalledTimes(1); expect(completeResume).toHaveBeenCalledTimes(1);
});

it("retries completion with the same ID and frozen upload version without reuploading", async () => {
  vi.mocked(completeResume).mockRejectedValueOnce(new Error("Completion response lost"));
  vi.mocked(resumeStatus).mockResolvedValue({ ...asset, state: "validating", version: 2 });
  fixture(); select(); fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Check or finish PDF upload" }));
  await waitFor(() => expect(completeResume).toHaveBeenCalledTimes(2));
  expect(vi.mocked(completeResume).mock.calls[0][1]).toBe(vi.mocked(completeResume).mock.calls[1][1]);
  expect(vi.mocked(completeResume).mock.calls[1][0].version).toBe(1);
  expect(uploadResume).toHaveBeenCalledTimes(1); expect(createResume).toHaveBeenCalledTimes(1);
  expect(await screen.findByText("Résumé: checking file safety")).toBeVisible();
});

it("refreshes an expired upload presign by replaying create without reserving another asset", async () => {
  vi.mocked(uploadResume).mockRejectedValueOnce(new Error("Upload URL expired"));
  fixture(); select(); fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await screen.findByRole("checkbox");
  expect(createResume).toHaveBeenCalledTimes(2);
  expect(vi.mocked(createResume).mock.calls[0][1]).toBe(vi.mocked(createResume).mock.calls[1][1]);
  expect(uploadResume).toHaveBeenCalledTimes(2); expect(completeResume).toHaveBeenCalledOnce();
});

it("aborts a replaced file, ignores its late upload and keeps explicit cleanup", async () => {
  const transport = deferred<void>(); vi.mocked(uploadResume).mockReturnValueOnce(transport.promise);
  fixture(); select(); fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await waitFor(() => expect(uploadResume).toHaveBeenCalledOnce());
  const signal = vi.mocked(uploadResume).mock.calls[0][2]!;
  select("replacement.pdf"); expect(signal.aborted).toBe(true);
  await act(async () => transport.resolve());
  expect(completeResume).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Delete previous PDF resume.pdf" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Delete previous PDF resume.pdf" }));
  await waitFor(() => expect(deleteResume).toHaveBeenCalledOnce());
  expect(vi.mocked(deleteResume).mock.calls[0][0].version).toBe(3);
});

it("never uploads or displays an old account's late asset", async () => {
  const creating = deferred<ResumeAsset>(); vi.mocked(createResume).mockReturnValueOnce(creating.promise);
  const result = fixture(); select(); fireEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
  await waitFor(() => expect(createResume).toHaveBeenCalledOnce());
  result.rerender(result.ui(2));
  await act(async () => creating.resolve(asset));
  expect(uploadResume).not.toHaveBeenCalled(); expect(completeResume).not.toHaveBeenCalled();
  expect(screen.queryByText(/Previous unsaved PDF/)).toBeNull();
  expect(screen.getByRole("button", { name: "Upload PDF" })).toBeDisabled();
});

it("does not download an old account's late private file after switching accounts", async () => {
  const downloading = deferred<Blob>(); vi.mocked(downloadResume).mockReturnValueOnce(downloading.promise);
  const result = fixture(1, saved);
  fireEvent.click(await screen.findByRole("button", { name: "Download PDF" }));
  result.rerender(result.ui(2));
  await act(async () => downloading.resolve(new Blob(["private pdf"])));
  expect(saveBlob).not.toHaveBeenCalled();
});

it("retries a lost deletion response with one frozen command", async () => {
  vi.mocked(deleteResume).mockRejectedValueOnce(new Error("Response lost"));
  fixture(1, saved);
  fireEvent.click(await screen.findByRole("button", { name: "Delete uploaded résumé" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Delete uploaded résumé" }));
  await waitFor(() => expect(deleteResume).toHaveBeenCalledTimes(2));
  expect(vi.mocked(deleteResume).mock.calls[0]).toEqual(vi.mocked(deleteResume).mock.calls[1]);
});

it("keeps a lost résumé save command stable and does not treat a newly selected file as ready", async () => {
  vi.mocked(saveDetail).mockRejectedValueOnce(new Error("Save response lost")).mockResolvedValueOnce({ field_key: "resume", version: 2, value: { asset_id: 41, sha256: "abc" } });
  fixture(1, saved);
  fireEvent.click(await screen.findByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Save résumé" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Save résumé" }));
  await waitFor(() => expect(saveDetail).toHaveBeenCalledTimes(2));
  expect(vi.mocked(saveDetail).mock.calls[0]).toEqual(vi.mocked(saveDetail).mock.calls[1]);
  await waitFor(() => expect(screen.getByRole("button", { name: "Save résumé" })).toBeEnabled());
  select("different.pdf");
  expect(screen.queryByRole("checkbox")).toBeNull();
  expect(screen.getByText("Previously saved résumé: ready")).toBeVisible();
});
