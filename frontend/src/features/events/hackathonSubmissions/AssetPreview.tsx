import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Box, Download } from "lucide-react";
import { ActionControl, Callout, Spinner } from "../../../components/ui";
import { ASK_PREVIEW_BYTES, checkMesh, MAX_PREVIEW_BYTES, MAX_PREVIEW_MS } from "./previewBounds";
import type { PreviewResult } from "./types";

const MeshCanvas = lazy(() => import("./MeshCanvas"));
const KicadCanvas = lazy(() => import("./KicadCanvas"));

/** Validate generated SVG and display as an image, never insert SVG markup. */
export function safeSvg(value: string) {
  if (value.length > 4 * 1024 ** 2 || /<!DOCTYPE|<!ENTITY/i.test(value)) throw new Error("Unsafe preview output.");
  const doc = new DOMParser().parseFromString(value, "image/svg+xml");
  if (doc.querySelector("parsererror") || doc.documentElement.localName !== "svg") throw new Error("Invalid preview image.");
  const tags = new Set(["svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "clipPath", "mask", "use", "title", "desc"]);
  const nodes = doc.querySelectorAll("*");
  if (nodes.length > 100000) throw new Error("Preview output limit.");
  for (const node of nodes) {
    if (!tags.has(node.localName)) throw new Error("Unsafe preview output.");
    for (const attr of node.attributes) {
      const normalized = attr.value.replace(/\s/g, "").toLowerCase();
      if (/^on/i.test(attr.localName) || /javascript:|data:|https?:|\/\//i.test(normalized)
        && attr.name !== "xmlns" && !attr.name.startsWith("xmlns:")
        || attr.localName === "href" && !attr.value.startsWith("#")
        || /url\(/i.test(attr.value) && !/^url\(#[a-z0-9_-]+\)$/i.test(attr.value)) throw new Error("Unsafe preview output.");
    }
  }
  return new XMLSerializer().serializeToString(doc);
}

export function AssetPreview({ assetId, bytes, filename, extension, load, download }: {
  assetId: number; bytes: number; filename: string; extension: string;
  load: (signal: AbortSignal) => Promise<Blob>; download: () => void;
}) {
  const [state, setState] = useState<"idle" | "confirm" | "loading" | "ready" | "failed">("idle");
  const kicad = extension === "kicad_pcb" || extension === "kicad_sch";
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const stop = useRef<() => void>(() => {});
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true; setState("idle"); setResult(null); setImage(null);
    return () => { mounted.current = false; stop.current(); };
  }, [assetId]);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);
  const run = async () => {
    if (bytes >= ASK_PREVIEW_BYTES && state !== "confirm") { setState("confirm"); return; }
    if (bytes > MAX_PREVIEW_BYTES) { setState("failed"); return; }
    stop.current(); setState("loading"); setResult(null); setImage(null);
    const controller = new AbortController();
    let worker: Worker | undefined;
    const finish = () => { controller.abort(); worker?.terminate(); clearTimeout(timer); };
    const timer = setTimeout(() => { finish(); if (mounted.current) setState("failed"); }, MAX_PREVIEW_MS);
    stop.current = finish;
    try {
      const blob = await load(controller.signal);
      if (controller.signal.aborted || blob.size !== bytes || blob.size > MAX_PREVIEW_BYTES) throw new Error("Preview unavailable.");
      const buffer = await blob.arrayBuffer();
      worker = new Worker(new URL("./preview.worker.ts", import.meta.url), { type: "module" });
      worker.onerror = () => { finish(); if (mounted.current) setState("failed"); };
      worker.onmessage = (event: MessageEvent<{ ok: boolean; result?: PreviewResult }>) => {
        try {
          const parsed = event.data.result;
          if (!event.data.ok || !parsed) throw new Error();
          if (parsed.kind === "mesh") {
            for (const mesh of parsed.meshes) checkMesh(mesh.positions);
          } else if (parsed.kind === "svg") setImage(URL.createObjectURL(new Blob([safeSvg(parsed.svg)], { type: "image/svg+xml" })));
          if (mounted.current) { setResult(parsed); setState("ready"); }
        } catch { if (mounted.current) setState("failed"); }
        finally { finish(); }
      };
      worker.postMessage({ buffer, extension, filename }, [buffer]);
    } catch { const aborted = controller.signal.aborted; finish(); if (mounted.current && !aborted) setState("failed"); }
  };
  return <section aria-label={`Preview ${filename}`} className="grid gap-4">
    <div className="flex flex-wrap items-center gap-3"><Box aria-hidden size={20} /><span className="font-semibold text-ink">Maker file preview</span></div>
    {state === "confirm" ? <Callout size="panel" tone="warn" lead="This is a large file."
      body="Loading the preview may use significant memory. You can download the original instead." /> : null}
    {state === "failed" ? <p role="status" className="text-sm text-muted">{kicad
      ? "We couldn't preview this KiCad file. Download it to open in KiCad." : "Preview unavailable. You can still download the original file."}</p> : null}
    {state === "loading" ? <div role="status"><Spinner />Preparing preview… <ActionControl action={{ label: "Cancel preview", onClick: () => { stop.current(); setState("idle"); } }} /></div> : null}
    {state === "ready" && result?.kind === "mesh" ? <Suspense fallback={<Spinner />}><MeshCanvas meshes={result.meshes} /></Suspense> : null}
    {state === "ready" && result?.kind === "kicad" ? <Suspense fallback={<Spinner />}>
      <KicadCanvas text={result.text} variant={result.variant} filename={filename} download={download} /></Suspense> : null}
    {state === "ready" && image ? <img src={image} alt={`PCB preview of ${filename}`} className="max-h-96 w-full rounded-xl border border-line bg-panel object-contain" /> : null}
    <div className="flex flex-wrap gap-3">{state !== "loading" ? <ActionControl action={{
      label: state === "confirm" ? "Load large preview" : "Load preview", onClick: () => void run() }} /> : null}
      <button type="button" className="desk-button min-h-11 gap-2" onClick={download}><Download aria-hidden size={20} />Download original</button>
    </div>
  </section>;
}
