import { useState } from "react";
import { ScanLine } from "lucide-react";
import { DelightArt } from "../../components/delight/Artwork";
import { useDelight } from "../../components/delight/DelightProvider";

/** Deliberately has no API client, credentials, real QR payload or inventory ID. */
export function SpaceWorksDemo() {
  const [issued, setIssued] = useState(false);
  const { enabled } = useDelight();
  if (!enabled) return null;
  return <section aria-labelledby="demo-title" className="my-8 grid gap-4 rounded-2xl border border-line bg-panel p-5 text-ink">
    <p className="eyebrow">Demo</p><h2 id="demo-title" className="title-panel">Try a sample handover</h2>
    <DelightArt name="demo" className="h-40 w-full" />
    <p>This sample box stays in your browser. Real handovers require a scanned tool and evidence.</p>
    <p role="status">Sample box: {issued ? "Issued" : "On shelf"}</p>
    <div className="flex flex-wrap gap-3"><button type="button" className="desk-button-primary gap-2" onClick={() => setIssued(true)} disabled={issued}>
      <ScanLine size={20} aria-hidden="true" />Scan sample box</button>
      <button type="button" className="desk-button" onClick={() => setIssued(false)} disabled={!issued}>Reset demo</button></div>
  </section>;
}
