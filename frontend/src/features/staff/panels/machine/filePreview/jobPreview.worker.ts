import { meshPreview } from "../../../../events/hackathonSubmissions/previewMesh";
import { MAX_PREVIEW_BYTES } from "../../../../events/hackathonSubmissions/previewBounds";
import type { PreviewResult } from "../../../../events/hackathonSubmissions/types";
import { dxfToSvg, gcodeToSvg } from "./drawings";
import { previewKind } from "./previewKinds";

/** Machine-job file preview worker (GAP2 M5): meshes through three.js, toolpaths and drawings to SVG. */
self.onmessage = async (event: MessageEvent<{ buffer: ArrayBuffer; extension: string; stroke: string }>) => {
  try {
    const { buffer, extension, stroke } = event.data;
    if (!buffer.byteLength || buffer.byteLength > MAX_PREVIEW_BYTES) throw new Error("Preview size limit.");
    const kind = previewKind(extension);
    let result: PreviewResult;
    if (kind === "mesh") result = await meshPreview(buffer, extension);
    else if (kind === "toolpath" || kind === "drawing") {
      const text = new TextDecoder("utf-8").decode(buffer);
      result = { kind: "svg", svg: kind === "toolpath" ? gcodeToSvg(text, stroke) : dxfToSvg(text, stroke) };
    } else throw new Error("Not previewable here.");
    self.postMessage({ ok: true, result });
  } catch {
    self.postMessage({ ok: false });
  }
};
