import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CardHolder } from "./designerHistoryApi";
import { CardLayerView } from "./CardLayerView";
import { setGroupMeta } from "./designDocument";
import { doc, layer } from "./designerFixtures.test";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), ...api }));

import { useHolderCutout } from "./designerHistoryApi";

const photo = layer({ id: "p", kind: "photo", variant: "cutout", w_mm: 30, h_mm: 40 });
const draw = (props: Partial<Parameters<typeof CardLayerView>[0]>) => render(
  <CardLayerView layer={photo} px={4} values={{ name: "Ada Lovelace" }} designId={1} mono={false} {...props} />);
const wrap = ({ children }: { children: ReactNode }) =>
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
const holder = (cutout: CardHolder["cutout"]): CardHolder => ({ id: 5, kind: "member_card", name: "Ada", number: "1", label: "", cutout });

beforeEach(() => api.staffRequest.mockReset());

describe("the real cut-out on a photo layer", () => {
  it("draws the designer's previewed holder cut-out instead of the silhouette", () => {
    const { container } = draw({ photoState: { cutout: "https://signed.example/cutout.png", useCutout: false, sample: false } });
    expect(container.querySelector("img")).toHaveAttribute("src", "https://signed.example/cutout.png");
  });

  it("draws the wallet face cut-out only when the holder chose it", () => {
    const live = { photo: "data:image/png;base64,AAA", photo_cutout: "data:image/png;base64,BBB", logos: {}, assets: {}, desk_qr: null, verify_qr: null };
    const chosen = draw({ live: { ...live, use_cutout: true } });
    expect(chosen.container.querySelector("img")).toHaveAttribute("src", live.photo_cutout);
    chosen.unmount();
    const original = draw({ layer: { ...photo, variant: "auto" }, live: { ...live, use_cutout: false } });
    expect(original.container.querySelector("img")).toHaveAttribute("src", live.photo);
    expect(screen.queryByText("BBB")).toBeNull();
  });
});

describe("useHolderCutout", () => {
  it("reads the short-lived link from the photo-cutout status route when the holder has a cut-out", async () => {
    api.staffRequest.mockResolvedValue({ image_url: "https://signed.example/c.png" });
    const { result } = renderHook(() => useHolderCutout(holder({ available: true, use_cutout: true })), { wrapper: wrap });
    await waitFor(() => expect(result.current.data).toBe("https://signed.example/c.png"));
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/member-cards/5/photo-cutout");
  });

  it("does not ask when there is no cut-out", () => {
    renderHook(() => useHolderCutout(holder({ available: false, use_cutout: false })), { wrapper: wrap });
    renderHook(() => useHolderCutout(null), { wrapper: wrap });
    expect(api.staffRequest).not.toHaveBeenCalled();
  });

  it("still asks when the holder chose the original: a cut-out layer prints the cut-out anyway (server rule)", async () => {
    api.staffRequest.mockResolvedValue({ image_url: "https://signed.example/c.png" });
    const { result } = renderHook(() => useHolderCutout(holder({ available: true, use_cutout: false })), { wrapper: wrap });
    await waitFor(() => expect(result.current.data).toBe("https://signed.example/c.png"));
  });
});

describe("saved-template group rows", () => {
  it("persists a group's name, lock and hide in side.groups and on its members", () => {
    const base = doc([layer({ id: "a", group: "g1" }), layer({ id: "b", group: "g1" }), layer({ id: "c" })]);
    const named = setGroupMeta(base, "front", "g1", { name: "Header" });
    const locked = setGroupMeta(named, "front", "g1", { locked: true });
    const hidden = setGroupMeta(locked, "front", "g1", { hidden: true });
    expect(hidden.front.groups).toEqual([{ id: "g1", name: "Header", locked: true, hidden: true }]);
    expect(hidden.front.layers.map((item) => [item.id, item.locked, item.hidden])).toEqual([["a", true, true], ["b", true, true], ["c", false, false]]);
    expect(JSON.parse(JSON.stringify(hidden)).front.groups[0].name).toBe("Header");
  });
});
