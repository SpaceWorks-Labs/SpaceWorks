import { useEffect, useRef, useState } from "react";
import { ActionControl } from "../../../components/ui";

/** Plays the verified original, without transcoding or external embeds. Judge
 * callers supply their assignment-gated authenticated reader, never a presign. */
export function OriginalVideo({ bytes, playable, load, download, label = "Project demonstration" }: {
  bytes: number; playable: boolean; load: (signal: AbortSignal) => Promise<Blob>;
  download: () => void; label?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const alive = useRef(true), controller = useRef<AbortController | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  async function play() {
    setPending(true); setFailed(false); controller.current = new AbortController();
    try {
      const video = await load(controller.current.signal);
      if (video.size !== bytes || controller.current.signal.aborted) throw new Error();
      if (alive.current) setUrl(URL.createObjectURL(video));
    } catch { if (alive.current) setFailed(true); }
    finally { if (alive.current) setPending(false); }
  }
  return <section aria-label={label} className="grid gap-3">
    {url ? <video controls playsInline preload="metadata" src={url} aria-label={label}
      className="max-h-96 w-full rounded-xl border border-line bg-panel" onError={() => setFailed(true)} /> : null}
    {!playable ? <p className="text-sm text-muted">This codec needs a player on your device. Download the original video to watch it.</p> : null}
    {failed ? <p role="status" className="text-sm text-muted">The original video could not be loaded. You can retry or download it.</p> : null}
    <div className="flex flex-wrap gap-3">{playable && !url ? <ActionControl action={{ label: "Load original video", pending,
      onClick: () => void play(), confirm: bytes >= 50 * 1024 ** 2 ? { title: "Load this large video?",
        message: "The original video may use significant memory and network data." } : undefined }} /> : null}
      <ActionControl action={{ label: "Download original video", onClick: download }} /></div>
  </section>;
}
