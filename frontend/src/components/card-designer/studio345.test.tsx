// Decision 345: barcode symbologies drawn from the server's encoding (with their minimum sizes), the version compare
// (diff and side-by-side dialog) and the member's background-eraser notice and opt-out.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn(), memberRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), ...api }));

import { CutoutPanel } from "../../features/cardEraser/CutoutPanel";
import { resizedFor } from "./BarcodeInspector";
import { barcodeMinimum, barcodeRects, carriesDesk } from "./barcodes";
import { CardLayerView } from "./CardLayerView";
import { doc, layer, side } from "./designerFixtures.test";
import { diffDocuments, isUnchanged } from "./documentDiff";
import { VersionCompare } from "./VersionCompare";

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
beforeEach(() => { api.staffRequest.mockReset(); api.memberRequest.mockReset(); });

describe("barcodes", () => {
  it("lays out linear bars across the quiet zones and matrix modules square and centred", () => {
    const linear = barcodeRects({ symbology: "code39", kind: "linear", bars: "1101", quiet: [2, 2], text: "A" }, 16, 10, 2, 0.4);
    expect(linear).toEqual([[4, 0.2, 4, 7.6], [10, 0.2, 2, 7.6]]);
    const matrix = barcodeRects({ symbology: "datamatrix", kind: "matrix", rows: ["10", "11"] }, 20, 10);
    expect(matrix).toEqual([[5, 0, 5, 5], [5, 5, 10, 5]]);
  });
  it("keeps each symbology's minimum box and refuses the desk code where it cannot fit", () => {
    expect(barcodeMinimum("code128", "desk")).toEqual({ w: 75, h: 6 });
    expect(barcodeMinimum("aztec", "number")).toEqual({ w: 10, h: 10 });
    expect(carriesDesk("ean13")).toBe(false);
    const grown = resizedFor(layer({ kind: "barcode", source: "desk", w_mm: 80, h_mm: 9, x_mm: 2, y_mm: 2 }), side([]), "datamatrix", "desk");
    expect(grown).toMatchObject({ symbology: "datamatrix", w_mm: 12, h_mm: 12 });
    expect(resizedFor(layer({ kind: "barcode", symbology: "aztec", w_mm: 12, h_mm: 12 }), side([]), "code128", "number")).toMatchObject({ symbology: undefined, w_mm: 30 });
  });
  it("draws the server's encoding of the previewed value", async () => {
    api.staffRequest.mockResolvedValue({ symbology: "aztec", kind: "matrix", rows: ["101", "010", "101"] });
    const { container } = wrap(<CardLayerView layer={layer({ kind: "barcode", symbology: "aztec", source: "number", w_mm: 12, h_mm: 12 })}
      px={4} values={{ number: "TNK-0042" }} designId={7} mono={false} />);
    await waitFor(() => expect(container.querySelectorAll("rect[fill='#000000']")).toHaveLength(5));
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/card-designs/7/barcode",
      expect.objectContaining({ body: JSON.stringify({ symbology: "aztec", value: "TNK-0042" }) }));
  });
});

describe("version compare", () => {
  const before = doc([layer({ id: "a", x_mm: 5 }), layer({ id: "b", kind: "text", text: "Hi" }), layer({ id: "c" })]);
  const after = { ...doc([layer({ id: "b", kind: "text", text: "Hello", colour: "#FF0000" }), layer({ id: "a", x_mm: 9 }), layer({ id: "d" })]),
    mono: true };
  it("lists added, removed and changed layers with the kind of change", () => {
    const diff = diffDocuments(before, after);
    expect(diff.front.added.map((item) => item.id)).toEqual(["d"]);
    expect(diff.front.removed.map((item) => item.id)).toEqual(["c"]);
    expect(diff.front.changed).toEqual([{ id: "b", name: "Text", kinds: ["colour", "text"] }, { id: "a", name: "Shape", kinds: ["position"] }]);
    expect(diff.front.reordered).toBe(true);
    expect(diff.card).toEqual(["mono"]);
    expect(isUnchanged(diffDocuments(before, before))).toBe(true);
  });
  it("shows the two versions side by side with the changes in words", async () => {
    api.staffRequest.mockImplementation(async (path: string) => ({ revision: path.endsWith("/3") ? 3 : 5, created_at: "", created_by: "",
      is_current: false, is_published: false, review: "", layers: 3, document: path.endsWith("/3") ? before : after }));
    wrap(<VersionCompare designId={7} older={3} newer={5} values={{}} onClose={vi.fn()} />);
    expect(await screen.findByText("Added: Shape")).toBeInTheDocument();
    expect(screen.getByText("Removed: Shape")).toBeInTheDocument();
    expect(screen.getByText("Changed: Text (colour, text)")).toBeInTheDocument();
    expect(screen.getByText("Black and white printing changed.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Version 3" })).toBeInTheDocument();
  });
});

describe("the eraser notice and opt-out", () => {
  const status = { available: true, state: "none", error_code: "", use: "original", image_url: "", width: 0, height: 0, requested_at: null,
    notice: "Card photos may be sent to this space's background-removal service.", notice_version: "2026-11-12", opted_out: false };
  it("shows members the notice on the photo upload and lets them opt out", async () => {
    api.memberRequest.mockResolvedValueOnce(status).mockResolvedValueOnce({ ...status, opted_out: true });
    wrap(<CutoutPanel target={{ scope: "member", cardPath: "/member/cards/member_card/4" }} photoSet={false} />);
    expect(await screen.findByText(/may be sent to this space's background-removal service/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Never send my photo to the background-removal service" }));
    await waitFor(() => expect(api.memberRequest).toHaveBeenCalledWith("/member/cards/member_card/4/photo/cutout",
      { method: "PUT", body: JSON.stringify({ opted_out: true }) }));
    expect(await screen.findByRole("checkbox", { name: "Never send my photo to the background-removal service" })).toBeChecked();
  });
  it("tells staff when a member opted out and offers no removal", async () => {
    api.staffRequest.mockResolvedValue({ ...status, opted_out: true });
    wrap(<CutoutPanel target={{ scope: "staff", photoPath: "/admin/member-cards/4/photo" }} />);
    expect(await screen.findByText(/opted out of background removal/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove background" })).toBeNull();
  });
});
