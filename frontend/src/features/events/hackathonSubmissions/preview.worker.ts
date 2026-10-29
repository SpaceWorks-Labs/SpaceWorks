import { checkKicad, kicadVariant } from "./kicadCheck";
import { checkMesh, checkPreviewZip, MAX_PREVIEW_BYTES, MAX_VERTICES } from "./previewBounds";
import type { PreviewMesh, PreviewResult } from "./types";

type Geometry = { attributes: { position: { array: ArrayLike<number> } }; index: unknown;
  clone: () => Geometry; applyMatrix4: (matrix: unknown) => void; toNonIndexed: () => Geometry; dispose: () => void };
type Model = { updateMatrixWorld: (force: boolean) => void;
  traverse: (visit: (node: { isMesh?: boolean; geometry: Geometry; matrixWorld: unknown }) => void) => void };

function meshesFromObject(object: Model): PreviewMesh[] {
  const meshes: PreviewMesh[] = [];
  let count = 0;
  object.updateMatrixWorld(true);
  object.traverse(node => {
    if (!node.isMesh) return;
    let geometry = node.geometry.clone();
    geometry.applyMatrix4(node.matrixWorld);
    if (geometry.index) {
      const expanded = geometry.toNonIndexed(); geometry.dispose(); geometry = expanded;
    }
    const array = geometry.attributes.position.array;
    checkMesh(array); count += array.length / 3;
    if (count > MAX_VERTICES) throw new Error("Preview geometry limit.");
    meshes.push({ positions: Float32Array.from(array) });
    geometry.dispose(); node.geometry.dispose();
  });
  if (!meshes.length) throw new Error("No preview geometry.");
  return meshes;
}

async function meshPreview(buffer: ArrayBuffer, extension: string): Promise<PreviewResult> {
  if (extension === "stl") {
    const { STLLoader } = await import("three/addons/loaders/STLLoader.js");
    const geometry = new STLLoader().parse(buffer) as Geometry;
    checkMesh(geometry.attributes.position.array);
    const positions = Float32Array.from(geometry.attributes.position.array); geometry.dispose();
    return { kind: "mesh", meshes: [{ positions }] };
  }
  if (extension === "obj") {
    const { OBJLoader } = await import("three/addons/loaders/OBJLoader.js");
    const text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
    if (/^(?:mtllib|map_\w+)\s+/m.test(text)) throw new Error("External materials are excluded from this preview.");
    return { kind: "mesh", meshes: meshesFromObject(new OBJLoader().parse(text) as Model) };
  }
  checkPreviewZip(buffer);
  const [{ ThreeMFLoader }, { DOMParser }, { unzipSync }] = await Promise.all([
    import("three/addons/loaders/3MFLoader.js"), import("linkedom/worker"), import("fflate")]);
  const entries = unzipSync(new Uint8Array(buffer)) as Record<string, Uint8Array>;
  for (const [name, data] of Object.entries(entries)) {
    if (!/\.(model|rels|xml)$/i.test(name)) continue;
    const xml = new TextDecoder("utf-8", { fatal: true }).decode(data);
    if (/<!ENTITY|<!DOCTYPE|<script\b|\bTargetMode\s*=\s*["']External|\b(?:href|Target)\s*=\s*["'](?:https?:|\/\/|data:)/i.test(xml)) {
      throw new Error("Unsafe model references.");
    }
  }
  (globalThis as unknown as { DOMParser: unknown }).DOMParser = DOMParser;
  return { kind: "mesh", meshes: meshesFromObject(new ThreeMFLoader().parse(buffer) as Model) };
}

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
    // KiCad: check shape only; the renderer parses on the main thread inside KicadCanvas.
    else if (kicadVariant(extension)) result = { kind: "kicad", ...checkKicad(buffer, extension) };
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
