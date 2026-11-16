import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import type { Batch, BatchItem } from "./api";
import { PhotoBatchDialog } from "./PhotoBatchDialog";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: vi.fn() }));

const item = (over: Partial<BatchItem>): BatchItem => ({ id: 1, filename: "TNK-0001", status: "matched", match_kind: "number", holder_id: 11,
  holder_name: "Priya Raman", candidates: [], decision: "apply", state: "pending", error_code: "", thumbnail_url: "https://files.test/1.png", ...over });
const holders = [{ id: 11, name: "Priya Raman", number: "TNK-0001" }, { id: 12, name: "Sam Lee", number: "TNK-0002" }, { id: 13, name: "Sam Lee", number: "TNK-0003" }];
const batch = (over: Partial<Batch> = {}): Batch => ({ id: 5, kind: "member_card", event_id: null, state: "draft", remove_backgrounds: false,
  eraser_available: false, file_count: 4, applied_count: 0, skipped_count: 0, failed_count: 0, expires_at: "2026-11-18T00:00:00Z", holders,
  items: [item({}), item({ id: 2, filename: "Sam Lee", status: "ambiguous", holder_id: null, holder_name: "", decision: "skip", candidates: holders.slice(1) }),
    item({ id: 3, filename: "IMG_9", status: "unmatched", holder_id: null, holder_name: "", decision: "skip", match_kind: "" }),
    item({ id: 4, filename: "TNK-0002", status: "has_photo", holder_id: 12, holder_name: "Sam Lee", decision: "keep" })], ...over });

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <PhotoBatchDialog open makerspaceId={3} kind="member_card" onClose={() => undefined} /></QueryClientProvider>);
const upload = (count = 1) => fireEvent.change(screen.getByLabelText("Photos or a zip of photos"),
  { target: { files: Array.from({ length: count }, (_, n) => new File(["x"], `p${n}.jpg`, { type: "image/jpeg" })) } });

describe("PhotoBatchDialog", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

  it("will not start until staff confirm the holders agreed", () => {
    show();
    expect(screen.getByRole("button", { name: "Choose photos or a zip" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /agreed to them being stored privately/ }));
    expect(screen.getByRole("button", { name: "Choose photos or a zip" })).toBeEnabled();
  });

  it("creates the batch with consent, uploads in chunks of 20 and shows the review table", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce(batch({ items: [], file_count: 0 })).mockResolvedValue(batch());
    show();
    fireEvent.click(screen.getByRole("checkbox", { name: /agreed to them being stored privately/ }));
    upload(45);
    await screen.findByText("Matched");
    expect(staffRequest).toHaveBeenNthCalledWith(1, "/admin/makerspaces/3/card-photo-batches", { method: "POST",
      body: JSON.stringify({ kind: "member_card", event_id: null, holders_consented: true, remove_backgrounds: false }) });
    const posts = vi.mocked(staffRequest).mock.calls.filter(([path]) => String(path).endsWith("/files"));
    expect(posts).toHaveLength(3); // 20 + 20 + 5
    expect(screen.getByText("Pick one")).toBeVisible();
    expect(screen.getByText("No match")).toBeVisible();
    expect(screen.getByText("Has a photo")).toBeVisible();
    expect(screen.queryByRole("checkbox", { name: "Remove backgrounds after upload" })).not.toBeInTheDocument();
  });

  it("lets staff pick for an ambiguous file, skip, and keep or replace an existing photo", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce(batch({ items: [], file_count: 0 })).mockResolvedValue(batch());
    show();
    fireEvent.click(screen.getByRole("checkbox", { name: /agreed to them being stored privately/ }));
    upload();
    const pick = await screen.findByLabelText("Choose the person for Sam Lee");
    expect(Array.from((pick as HTMLSelectElement).options).map(option => option.text)).toEqual(["Skip this photo", "Sam Lee (TNK-0002)", "Sam Lee (TNK-0003)"]);
    fireEvent.change(pick, { target: { value: "13" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/card-photo-batches/5/items/2",
      { method: "PATCH", body: JSON.stringify({ holder_id: 13 }) }));
    fireEvent.change(screen.getByLabelText("What to do with TNK-0002"), { target: { value: "replace" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/card-photo-batches/5/items/4",
      { method: "PATCH", body: JSON.stringify({ decision: "replace" }) }));
  });

  it("applies the chosen photos, and offers the eraser follow-up only when it is available", async () => {
    const withEraser = batch({ eraser_available: true });
    vi.mocked(staffRequest).mockResolvedValueOnce(batch({ items: [], file_count: 0 })).mockResolvedValue(withEraser);
    show();
    fireEvent.click(screen.getByRole("checkbox", { name: /agreed to them being stored privately/ }));
    upload();
    fireEvent.click(await screen.findByRole("checkbox", { name: "Remove backgrounds after upload" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply 1 photos" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/card-photo-batches/5/apply",
      { method: "POST", body: JSON.stringify({ remove_backgrounds: true }) }));
  });

  it("shows progress while applying and the totals when done", async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce(batch({ items: [], file_count: 0 }))
      .mockResolvedValue(batch({ state: "done", applied_count: 2, skipped_count: 2 }));
    show();
    fireEvent.click(screen.getByRole("checkbox", { name: /agreed to them being stored privately/ }));
    upload();
    expect(await screen.findByText("Done: 2 photos attached, 2 skipped, 0 failed.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Apply/ })).not.toBeInTheDocument();
  });
});
