import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Box } from "lucide-react";

import { ActionControl, Callout, Spinner } from "../../../../../components/ui";
import { safeSvg } from "../../../../events/hackathonSubmissions/AssetPreview";
import { ASK_PREVIEW_BYTES, checkMesh, MAX_PREVIEW_BYTES, MAX_PREVIEW_MS } from "../../../../events/hackathonSubmissions/previewBounds";
import type { PreviewResult } from "../../../../events/hackathonSubmissions/types";
import { extensionOf, KIND_LABELS, previewKind } from "./previewKinds";
import { MAX_SVG_BYTES, sanitizeSvg } from "./svgFile";

const MeshCanvas = lazy(() => import("../../../../events/hackathonSubmissions/MeshCanvas"));
type State = "idle" | "confirm" | "loading" | "ready" | "failed";

/** The theme's drawing colour for generated SVG (an <img> cannot read CSS variables). */
function strokeColour() {
  const channels = getComputedStyle(document.documentElement).getPropertyValue("--color-brand-boundary").trim().split(/\s+/).map(Number);
  return channels.length === 3 && channels.every(n => Number.isFinite(n) && n >= 0 && n <= 255) ? `rgb(${channels.join(",")})` : "currentColor";
}

/**
 * One job file's in-browser preview (#142 OQ-12): loaded only when staff ask, through a private
 * short-lived signed URL, parsed in a worker with size and time limits; failures fall back to download.
 */
export function JobFilePreview({ fileId, filename, bytes, load }: {
  fileId: number; filename: string; bytes: number; load: (signal: AbortSignal) => Promise<Blob>;
}) {
  const extension = extensionOf(filename), kind = previewKind(extension);
  const limit = kind === "image" ? MAX_SVG_BYTES : MAX_PREVIEW_BYTES;
  const [state, setState] = useState<State>("idle");
  const [mesh, setMesh] = useState<PreviewResult | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const stop = useRef<() => void>(() => {});
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; stop.current(); };
  }, [fileId]);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image); }, [image]);
  if (!kind) return null;
  const fail = () => { if (mounted.current) setState("failed"); };
  const showSvg = (svg: string) => { if (mounted.current) { setImage(URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }))); setState("ready"); } };
  const run = async () => {
    if (bytes > limit) { setState("failed"); return; }
    if (bytes >= ASK_PREVIEW_BYTES && state !== "confirm") { setState("confirm"); return; }
    stop.current(); setState("loading"); setMesh(null); setImage(null);
    const controller = new AbortController();
    let worker: Worker | undefined;
    const finish = () => { controller.abort(); worker?.terminate(); clearTimeout(timer); };
    const timer = setTimeout(() => { finish(); fail(); }, MAX_PREVIEW_MS);
    stop.current = finish;
    try {
      const blob = await load(controller.signal);
      if (controller.signal.aborted || !blob.size || blob.size > limit) throw new Error("Preview unavailable.");
      if (kind === "image") { const svg = sanitizeSvg(await blob.text()); finish(); showSvg(svg); return; }
      const buffer = await blob.arrayBuffer();
      worker = new Worker(new URL("./jobPreview.worker.ts", import.meta.url), { type: "module" });
      worker.onerror = () => { finish(); fail(); };
      worker.onmessage = (event: MessageEvent<{ ok: boolean; result?: PreviewResult }>) => {
        try {
          const parsed = event.data.result;
          if (!event.data.ok || !parsed) throw new Error();
          if (parsed.kind === "mesh") {
            for (const part of parsed.meshes) checkMesh(part.positions);
            if (mounted.current) { setMesh(parsed); setState("ready"); }
          } else showSvg(safeSvg(parsed.svg));
        } catch { fail(); } finally { finish(); }
      };
      worker.postMessage({ buffer, extension, stroke: strokeColour() }, [buffer]);
    } catch { const aborted = controller.signal.aborted; finish(); if (!aborted) fail(); }
  };
  return <section aria-label={`Preview of ${filename}`} className="grid gap-3">
    <div className="flex flex-wrap items-center gap-2 text-sm text-muted"><Box aria-hidden="true" size={18} />{KIND_LABELS[kind]}</div>
    {state === "confirm" ? <Callout size="panel" tone="warn" lead="This is a large file."
      body="The preview may use a lot of memory on this device. You can download the original instead." /> : null}
    {state === "failed" ? <p role="status" className="text-sm text-muted">Preview unavailable. You can still download the original file.</p> : null}
    {state === "loading" ? <div role="status" className="flex flex-wrap items-center gap-2"><Spinner />Preparing preview…
      <ActionControl action={{ label: "Cancel preview", onClick: () => { stop.current(); setState("idle"); } }} /></div> : null}
    {state === "ready" && mesh?.kind === "mesh" ? <Suspense fallback={<Spinner />}><MeshCanvas meshes={mesh.meshes} label={`3D preview of ${filename}`} /></Suspense> : null}
    {state === "ready" && image ? <img src={image} alt={`${KIND_LABELS[kind]} of ${filename}`}
      className="max-h-96 w-full rounded-xl border border-line bg-panel object-contain p-2" /> : null}
    {state !== "loading" && state !== "ready" ? <div><ActionControl action={{
      label: state === "confirm" ? "Load large preview" : "Load preview", onClick: () => { void run(); } }} /></div> : null}
  </section>;
}
