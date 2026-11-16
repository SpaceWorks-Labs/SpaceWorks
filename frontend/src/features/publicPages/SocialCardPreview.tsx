import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

export function SocialCardPreview({ title, description, url, image }: { title: string; description: string; url: string; image?: ReactNode }) {
  return <div className="grid min-w-0 gap-2 rounded-xl border border-line bg-panel p-4" aria-label={t`Open Graph preview`}>
    {image}<p className="font-semibold text-ink">{title}</p>{description ? <p className="text-sm text-muted">{description.slice(0, 300)}</p> : null}
    <p className="break-all text-sm text-muted">{url}</p>
  </div>;
}
