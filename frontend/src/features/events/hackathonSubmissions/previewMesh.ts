import { checkMesh, checkPreviewZip, MAX_VERTICES } from "./previewBounds";
import type { PreviewMesh, PreviewResult } from "./types";

/**
 * STL, OBJ and 3MF to checked numeric mesh buffers, inside a worker. Shared by the hackathon asset
 * preview and the machine-job file preview (GAP2 M5); three.js (MIT) loads lazily, and vendor output
 * is untrusted until `checkMesh` passes.
 */
type Geometry = { attributes: { position: { array: ArrayLike<number> } }; index: unknown;
  clone: () => Geometry; applyMatrix4: (matrix: unknown) => void; toNonIndexed: () => Geometry; dispose: () => void };
type Model = { updateMatrixWorld: (force: boolean) => void;
  traverse: (visit: (node: { isMesh?: boolean; geometry: Geometry; matrixWorld: unknown }) => void) => void };

export const MESH_EXTENSIONS = ["stl", "obj", "3mf", "gcode.3mf"];

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

export async function meshPreview(buffer: ArrayBuffer, extension: string): Promise<PreviewResult> {
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
