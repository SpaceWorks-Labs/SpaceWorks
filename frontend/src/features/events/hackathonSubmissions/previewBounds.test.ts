import { describe, expect, it } from "vitest";
import { checkMesh, checkPreviewZip, MAX_VERTICES } from "./previewBounds";
import { safeSvg } from "./AssetPreview";

function zip(packed: number, expanded: number, name = "3D/model.model") {
  const encoded = new TextEncoder().encode(name);
  const localLength = 30 + encoded.length + packed;
  const bytes = new Uint8Array(localLength + 46 + encoded.length + 22), view = new DataView(bytes.buffer);
  view.setUint32(0, 0x04034b50, true); view.setUint16(26, encoded.length, true); bytes.set(encoded, 30);
  const cd = localLength;
  view.setUint32(cd, 0x02014b50, true); view.setUint32(cd + 20, packed, true); view.setUint32(cd + 24, expanded, true);
  view.setUint16(cd + 28, encoded.length, true); bytes.set(encoded, cd + 46);
  const end = cd + 46 + encoded.length;
  view.setUint32(end, 0x06054b50, true); view.setUint16(end + 10, 1, true);
  view.setUint32(end + 12, 46 + encoded.length, true); view.setUint32(end + 16, cd, true);
  return bytes.buffer;
}

describe("preview resource floor", () => {
  it("accepts a bounded zip manifest without decompression", () => expect(() => checkPreviewZip(zip(16, 16))).not.toThrow());
  it.each([zip(1, 65536), zip(1, 1, "../escape"), zip(1, 1, "texture.png"), zip(1, 1, "C:x")])("refuses bombs, paths and texture fetches", data => {
    expect(() => checkPreviewZip(data)).toThrow();
  });
  it("refuses malformed meshes before rendering", () => {
    expect(() => checkMesh([0, 0, 0, 1, 1, 1, 0, 1, 0])).not.toThrow();
    for (const values of [[], [0, 0], [NaN, 0, 0], [Infinity, 0, 0], new Float32Array((MAX_VERTICES + 1) * 3)]) {
      expect(() => checkMesh(values)).toThrow();
    }
  });
  it("allows inert generated SVG but refuses markup with behavior or network access", () => {
    expect(safeSvg('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1 1"/></svg>')).toContain("path");
    for (const body of ['<svg onload="alert(1)"/>', '<svg><script/></svg>', '<svg><image href="https://example.com/x"/></svg>',
      '<svg><foreignObject/></svg>', '<svg><path fill="url(https://example.com/x)"/></svg>', '<!DOCTYPE svg><svg/>']) {
      expect(() => safeSvg(body)).toThrow();
    }
  });
});
