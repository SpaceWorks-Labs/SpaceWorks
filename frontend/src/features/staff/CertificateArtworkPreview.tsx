import { useEffect, useState } from "react";

import { Skeleton } from "../../components/ui";
import { useCertificateArtwork } from "./eventsCertificateDesignerApi";

/**
 * Shows the private certificate artwork back to the designer. The bytes need the staff session,
 * so they are fetched as a blob and shown through an object URL, revoked whenever the artwork
 * changes or the designer unmounts so a replaced image never lingers in memory.
 */
export function CertificateArtworkPreview({ eventId, artworkId }: { eventId: number; artworkId: number }) {
  const artwork = useCertificateArtwork(eventId, artworkId);
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!artwork.data) { setSrc(""); return; }
    const url = URL.createObjectURL(artwork.data);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [artwork.data]);
  if (artwork.isError) return <p className="text-sm text-muted">The artwork preview is unavailable. It is still attached and appears in the PDF preview.</p>;
  if (!src) return <div role="status"><span className="sr-only">Loading certificate artwork…</span><Skeleton className="h-40 w-full" /></div>;
  return <img className="max-h-64 w-full rounded-lg border border-line bg-surface object-contain" src={src} alt="Certificate artwork" />;
}
