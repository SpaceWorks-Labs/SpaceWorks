import { afterEach, expect, it, vi } from "vitest";
import { DEFAULT_COVER_EDITS, renderCover } from "./coverImage";
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function fakeCanvas(types: string[]) {
  const bitmap = { width: 2000, height: 2000, close: vi.fn() };
  vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue(bitmap));
  const context = { filter: "none", translate: vi.fn(), rotate: vi.fn(), scale: vi.fn(), drawImage: vi.fn() };
  const canvas = document.createElement("canvas");
  vi.spyOn(canvas, "getContext").mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.spyOn(canvas, "toBlob").mockImplementation((callback, type) => callback(new Blob(["x"], { type: types.includes(String(type)) ? String(type) : "image/png" })));
  const originalCreate = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation(((tag: string) => tag === "canvas" ? canvas : originalCreate(tag)) as typeof document.createElement);
  return { bitmap, context, canvas };
}

it("rejects oversized or unsupported input before image decoding", async () => {
  await expect(renderCover(new Blob(["bad"], { type: "image/svg+xml" }), DEFAULT_COVER_EDITS)).rejects.toThrow("PNG, JPEG or WebP");
});

it("renders the chosen shape as WebP with flips, rotation and the colour filter, and closes the bitmap", async () => {
  const { bitmap, context, canvas } = fakeCanvas(["image/webp", "image/jpeg"]);
  const output = await renderCover(new Blob(["input"], { type: "image/png" }), { ...DEFAULT_COVER_EDITS, shape: "wide", rotation: 90, flipX: true, brightness: 10 });
  expect(output.type).toBe("image/webp");
  expect([canvas.width, canvas.height]).toEqual([1600, 900]);
  expect(context.rotate).toHaveBeenCalledWith(Math.PI / 2);
  expect(context.scale).toHaveBeenCalledWith(-1, 1);
  expect(context.filter).toContain("brightness(1.1)");
  expect(bitmap.close).toHaveBeenCalled();
});

it("falls back to JPEG when the browser cannot encode WebP", async () => {
  fakeCanvas(["image/jpeg"]);
  const output = await renderCover(new Blob(["input"], { type: "image/jpeg" }), DEFAULT_COVER_EDITS);
  expect(output.type).toBe("image/jpeg");
});
