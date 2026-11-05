/** Which machine-job files the browser previews (#142 OQ-12: safe formats only), by extension. */
export type PreviewKind = "mesh" | "toolpath" | "drawing" | "image";

const KINDS: Record<string, PreviewKind> = {
  stl: "mesh", obj: "mesh", "3mf": "mesh", "gcode.3mf": "mesh",
  gcode: "toolpath", gco: "toolpath", g: "toolpath", nc: "toolpath", ngc: "toolpath", tap: "toolpath", cnc: "toolpath",
  dxf: "drawing", svg: "image",
};

/** The registry-style extension of a file name (`gcode.3mf` kept whole). */
export function extensionOf(filename: string) {
  const name = filename.toLowerCase();
  if (name.endsWith(".gcode.3mf")) return "gcode.3mf";
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1) : "";
}

export function previewKind(extension: string): PreviewKind | null {
  return KINDS[extension] ?? null;
}

export const KIND_LABELS: Record<PreviewKind, string> = {
  mesh: "3D model", toolpath: "Toolpath seen from above", drawing: "Drawing", image: "Image",
};
