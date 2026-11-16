export const MAX_PREVIEW_BYTES = 200 * 1024 ** 2;
export const ASK_PREVIEW_BYTES = 50 * 1024 ** 2;
export const MAX_VERTICES = 1_000_000;
export const MAX_PREVIEW_MS = 20_000;
export const MAX_EXPANDED = 64 * 1024 ** 2;

/** Preflight before a vendor ZIP parser allocates uncompressed model buffers. */
export function checkPreviewZip(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer), view = new DataView(buffer);
  if (bytes.length < 22 || view.getUint32(0, true) !== 0x04034b50) throw new Error("Invalid preview archive.");
  let end = bytes.length - 22;
  for (; end >= Math.max(0, bytes.length - 65557); end--) if (view.getUint32(end, true) === 0x06054b50) break;
  if (end < 0 || view.getUint32(end, true) !== 0x06054b50
    || view.getUint16(end + 20, true) + end + 22 !== bytes.length) throw new Error("Invalid preview archive.");
  const count = view.getUint16(end + 10, true), length = view.getUint32(end + 12, true), offset = view.getUint32(end + 16, true);
  if (!count || count > 1000 || length > 1024 ** 2 || offset + length !== end) throw new Error("Preview archive exceeds limits.");
  let position = offset, total = 0, packedTotal = 0;
  const names = new Set<string>();
  for (let i = 0; i < count; i++) {
    if (position + 46 > end || view.getUint32(position, true) !== 0x02014b50) throw new Error("Invalid preview archive.");
    const flags = view.getUint16(position + 8, true), method = view.getUint16(position + 10, true);
    const packed = view.getUint32(position + 20, true), size = view.getUint32(position + 24, true);
    const nameLength = view.getUint16(position + 28, true), extra = view.getUint16(position + 30, true), comment = view.getUint16(position + 32, true);
    const next = position + 46 + nameLength + extra + comment;
    const local = view.getUint32(position + 42, true);
    if (next > end || flags & 0x2041 || ![0, 8].includes(method) || size > Math.max(1, packed) * 100
      || local + 30 > offset || view.getUint32(local, true) !== 0x04034b50) throw new Error("Unsafe preview archive.");
    const name = new TextDecoder("utf-8", { fatal: true }).decode(bytes.slice(position + 46, position + 46 + nameLength)).normalize("NFKC");
    if (!name || /[\\:\x00-\x1f\x7f]/.test(name) || name.startsWith("/") || name.split("/").includes("..")
      || names.has(name.toLowerCase()) || /\.(png|jpg|jpeg|webp|gif|svg)$/i.test(name)) throw new Error("Textures are excluded from this preview.");
    names.add(name.toLowerCase()); total += size; packedTotal += packed;
    if (total > MAX_EXPANDED) throw new Error("Preview archive expands beyond its limit.");
    position = next;
  }
  if (position !== end || total > Math.max(1, packedTotal) * 20) throw new Error("Unsafe preview archive.");
}

export function checkMesh(positions: ArrayLike<number>) {
  if (!positions.length || positions.length % 3 || positions.length / 3 > MAX_VERTICES) throw new Error("Mesh exceeds the preview limit.");
  for (let i = 0; i < positions.length; i++) if (!Number.isFinite(positions[i]) || Math.abs(positions[i]) > 1e12) throw new Error("Invalid mesh coordinates.");
}
