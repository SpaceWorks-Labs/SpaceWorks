// CARD-STUDIO-2 (decision 344(b)) views: icon and polygon layers, the cut-out framing, the arrange toolbar, the brand
// kit swatches, the artwork library, the CSV merge dialog and the rulers.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), ...api }));

import { AssetLibrary } from "./AssetLibrary";
import { BrandKitProvider } from "./brandKit";
import { CanvasFrame } from "./CanvasFrame";
import { CanvasToolbar } from "./CanvasToolbar";
import { CardLayerView } from "./CardLayerView";
import type { CardDesign } from "./cardTypes";
import { CsvMergeDialog } from "./CsvMergeDialog";
import { doc, layer, side } from "./designerFixtures.test";
import { ColourInput } from "./inspectorFields";
import type { DesignerEditing } from "./useDesignerEditing";

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
beforeEach(() => { api.staffRequest.mockReset(); api.staffRequestBlob.mockReset(); });

describe("icon and polygon layers", () => {
  it("draws the vendored icon paths in the layer colour, even-odd", () => {
    const { container } = render(<CardLayerView layer={layer({ kind: "icon", icon: "pin", colour: "#006E63" })} px={4} values={{}} designId={1} mono={false} />);
    const paths = container.querySelectorAll("path");
    expect(paths.length).toBeGreaterThan(0);
    expect(paths[0].getAttribute("fill")).toBe("rgb(0, 110, 99)");
    expect(paths[0].getAttribute("fill-rule")).toBe("evenodd");
  });
  it("prints an icon black or white in black-and-white mode, and nothing for an unknown key", () => {
    const mono = render(<CardLayerView layer={layer({ kind: "icon", icon: "star", colour: "#DFFF8F" })} px={4} values={{}} designId={1} mono />);
    expect(mono.container.querySelector("path")?.getAttribute("fill")).toBe("#FFFFFF");
    mono.unmount();
    const unknown = render(<CardLayerView layer={layer({ kind: "icon", icon: "nope", colour: "#000000" })} px={4} values={{}} designId={1} mono={false} />);
    expect(unknown.container.querySelector("path")).toBeNull();
  });
  it("draws a star shape as an SVG polygon", () => {
    const { container } = render(<CardLayerView layer={layer({ kind: "shape", shape: "star", fill: "#006E63", w_mm: 10, h_mm: 10 })} px={4} values={{}} designId={1} mono={false} />);
    expect(container.querySelector("polygon")?.getAttribute("points")?.split(" ")).toHaveLength(10);
  });
});

describe("the cut-out on a photo layer", () => {
  it("frames the cut-out like the server (cover, zoom, focal point) and flips it", () => {
    const photo = layer({ kind: "photo", variant: "cutout", zoom: 2, focal_x_pct: 30, flip_y: true, w_mm: 20, h_mm: 25 });
    const { container } = render(<CardLayerView layer={photo} px={4} values={{}} designId={1} mono={false}
      photoState={{ cutout: "blob:cut", useCutout: false, sample: false }} />);
    const image = container.querySelector("img")!;
    expect(image.getAttribute("src")).toBe("blob:cut");
    expect(image.style.transform).toContain("scaleY(-1)");
  });
});

describe("the arrange toolbar", () => {
  it("restacks, locks and hides the selection", () => {
    const editing = { canEdit: true, restack: vi.fn(), toggleFlag: vi.fn(), align: vi.fn(), distribute: vi.fn(), group: vi.fn(), ungroup: vi.fn() } as unknown as DesignerEditing;
    render(<CanvasToolbar side={side([layer({ id: "a" })])} selection={["a"]} editing={editing} />);
    fireEvent.click(screen.getByRole("button", { name: /Bring to front/ }));
    fireEvent.click(screen.getByRole("button", { name: /Send backward/ }));
    fireEvent.click(screen.getByRole("button", { name: "Lock the selection" }));
    fireEvent.click(screen.getByRole("button", { name: "Hide the selection" }));
    expect(editing.restack).toHaveBeenNthCalledWith(1, "front");
    expect(editing.restack).toHaveBeenNthCalledWith(2, "backward");
    expect(editing.toggleFlag).toHaveBeenCalledWith("locked");
    expect(editing.toggleFlag).toHaveBeenCalledWith("hidden");
    expect(screen.getByRole("button", { name: "Align left edges to the card" })).toBeEnabled();
  });
});

describe("the brand kit", () => {
  it("offers the space colours as swatches under a colour field and applies one", async () => {
    api.staffRequest.mockResolvedValue({ colours: [{ label: "Space colour", hex: "#123456" }], logos: [], fonts: [] });
    const onChange = vi.fn();
    wrap(<BrandKitProvider designId={7}><ColourInput label="Fill" value="#FFFFFF" onChange={onChange} /></BrandKitProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "Space colour #123456" }));
    expect(onChange).toHaveBeenCalledWith("#123456");
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/card-designs/7/brand-kit");
  });
});

describe("the artwork library", () => {
  const asset = { asset_id: "a1", kind: "background", width_px: 1200, height_px: 800, mean_colour: "#336699", size_bytes: 1000, created_at: "2026-11-12T00:00:00Z" };
  it("uses a library picture as the background or a new image layer", async () => {
    api.staffRequest.mockResolvedValue([asset]);
    api.staffRequestBlob.mockResolvedValue(new Blob(["x"]));
    const onBackground = vi.fn(), onAdd = vi.fn();
    wrap(<AssetLibrary designId={3} side={side([])} stock="cr80-landscape" readOnly={false} onBackground={onBackground} onAdd={onAdd} onAssetColour={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Background" }));
    expect(onBackground).toHaveBeenCalledWith(expect.objectContaining({ kind: "image", asset_id: "a1", fit: "cover" }));
    fireEvent.click(screen.getByRole("button", { name: "Add to card" }));
    expect(onAdd).toHaveBeenCalledWith(expect.objectContaining({ kind: "image", asset_id: "a1" }));
  });
  it("deletes an unused picture after a confirm", async () => {
    api.staffRequest.mockResolvedValueOnce([asset]).mockResolvedValueOnce(undefined).mockResolvedValue([]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    wrap(<AssetLibrary designId={3} side={side([])} stock="cr80-landscape" readOnly={false} onBackground={vi.fn()} onAdd={vi.fn()} onAssetColour={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/card-designs/3/asset-library/a1", { method: "DELETE" }));
    expect(await screen.findByText(/storage is free again/)).toBeInTheDocument();
  });
});

describe("cards from a CSV", () => {
  const design = { id: 9, document: doc([layer({ kind: "data_field", field: "name", text: "{{name}}" })]) } as unknown as CardDesign;
  it("checks the file, shows ignored columns and prints only a published design", async () => {
    api.staffRequest.mockResolvedValue({ columns: ["name", "role"], unknown_columns: ["shoe_size"], rows: 2,
      preview: [{ name: "Asha Rao", role: "Volunteer" }, { name: "Ben Ode", role: "Crew" }], published: false, images: [] });
    wrap(<CsvMergeDialog design={design} open onClose={vi.fn()} />);
    const file = new File(["name,role,shoe_size\nAsha Rao,Volunteer,7\nBen Ode,Crew,9\n"], "people.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Choose a CSV file"), { target: { files: [file] } });
    expect(await screen.findByText(/Ignored columns .*shoe_size/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Publish the design first");
    expect(screen.getByRole("button", { name: "Print 2 cards" })).toBeDisabled();
    expect(JSON.parse(api.staffRequest.mock.calls[0][1].body)).toEqual(expect.objectContaining({ dry_run: true }));
  });
});

describe("rulers", () => {
  it("adds a guide line where a ruler is clicked", () => {
    const onAddGuide = vi.fn();
    const { container } = render(<CanvasFrame widthMm={85.6} heightMm={53.98} px={5} bleedMm={3} rulers onAddGuide={onAddGuide}><span /></CanvasFrame>);
    const [top] = container.querySelectorAll("svg");
    top.getBoundingClientRect = () => ({ left: 0, top: 0, right: 428, bottom: 20, width: 428, height: 20, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.click(top, { clientX: 101, clientY: 5 });
    expect(onAddGuide).toHaveBeenCalledWith("x", 20);
  });
});

describe("cards from a CSV, published preview", () => {
  it("shows the server's renders of the published version", async () => {
    const design = { id: 9, document: doc([]) } as unknown as CardDesign;
    api.staffRequest.mockResolvedValue({ columns: ["name"], unknown_columns: [], rows: 1, preview: [{ name: "Asha Rao" }],
      published: true, images: ["data:image/png;base64,AAAA"] });
    wrap(<CsvMergeDialog design={design} open onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Choose a CSV file"), { target: { files: [new File(["name,Asha Rao"], "a.csv")] } });
    expect(await screen.findByRole("img", { name: "Card for Asha Rao" })).toHaveAttribute("src", "data:image/png;base64,AAAA");
    expect(screen.getByRole("button", { name: "Print 1 cards" })).toBeEnabled();
  });
});
