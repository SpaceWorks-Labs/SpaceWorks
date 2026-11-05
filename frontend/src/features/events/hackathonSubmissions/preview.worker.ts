import { checkMesh, checkPreviewZip, MAX_PREVIEW_BYTES, MAX_VERTICES } from "./previewBounds";
import { meshPreview } from "./previewMesh";
import type { PreviewResult } from "./types";

async function brepPreview(buffer: ArrayBuffer, extension: string): Promise<PreviewResult> {
  const [{ default: factory }, { default: wasmUrl }] = await Promise.all([
    import("occt-import-js"), import("occt-import-js/dist/occt-import-js.wasm?url")]);
  const engine = await factory({ locateFile: (filename: string) => {
    if (!filename.endsWith(".wasm")) throw new Error("Unexpected CAD runtime resource.");
    return wasmUrl;
  } });
  const result = ["step", "stp"].includes(extension) ? engine.ReadStepFile(new Uint8Array(buffer), null)
    : engine.ReadIgesFile(new Uint8Array(buffer), null);
  if (!result.success || !Array.isArray(result.meshes) || result.meshes.length > 1000) throw new Error("Invalid CAD model.");
  let count = 0;
  const meshes = result.meshes.map((mesh: { attributes: { position: { array: number[] } }; index: { array: number[] } }) => {
    const coordinates = mesh.attributes.position.array;
    checkMesh(coordinates);
    const indices = mesh.index.array;
    count += indices.length;
    if (!indices.length || indices.length % 3 || count > MAX_VERTICES) throw new Error("CAD mesh limit.");
    const positions = new Float32Array(indices.length * 3);
    indices.forEach((index, i) => {
      if (!Number.isSafeInteger(index) || index < 0 || index * 3 + 2 >= coordinates.length) throw new Error("Invalid CAD indices.");
      positions.set(coordinates.slice(index * 3, index * 3 + 3), i * 3);
    });
    return { positions };
  });
  return { kind: "mesh", meshes };
}

self.onmessage = async (event: MessageEvent<{ buffer: ArrayBuffer; extension: string; filename: string }>) => {
  try {
    const { buffer, extension, filename } = event.data;
    if (!buffer.byteLength || buffer.byteLength > MAX_PREVIEW_BYTES) throw new Error("Preview size limit.");
    let result: PreviewResult;
    if (["stl", "obj", "3mf", "gcode.3mf"].includes(extension)) result = await meshPreview(buffer, extension);
    else if (["step", "stp", "iges", "igs"].includes(extension)) result = await brepPreview(buffer, extension);
    else {
      const { read, plot, renderLayers, renderBoard } = await import("@tracespace/core");
      let files = [new File([buffer], filename)];
      if (extension === "zip") {
        checkPreviewZip(buffer);
        const { unzipSync } = await import("fflate");
        const entries = unzipSync(new Uint8Array(buffer)) as Record<string, Uint8Array>;
        files = Object.entries(entries).filter(([name]) => /\.(gbr|ger|gt[lsop]|gb[lsop]|gko|gm1|g\d+|drl|xln)$/i.test(name))
          .map(([name, bytes]) => new File([new Uint8Array(bytes)], name));
      }
      const rendered = renderBoard(renderLayers(plot(await read(files))));
      if (typeof rendered.top !== "string" || rendered.top.length > 4 * 1024 ** 2) throw new Error("Gerber output limit.");
      result = { kind: "svg", svg: rendered.top };
    }
    self.postMessage({ ok: true, result });
  } catch {
    self.postMessage({ ok: false, message: "Preview unavailable. You can still download the original file." });
  }
};
