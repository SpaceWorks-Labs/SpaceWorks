import { useState } from "react";
import { Avatar } from "./Avatar";
import { DateChip } from "./DateChip";
import { Icon } from "./icon";
import { toneClasses } from "./tones";
import type { Identity } from "./types";
export type IdentityChipProps = { identity: Identity; label?: string; draft?: boolean };
export function IdentityChip({ identity, label = "Identity", draft = false }: IdentityChipProps) {
  const [failedSrc, setFailedSrc] = useState<string>();
  if (identity.kind === "date") return <DateChip date={identity.date} draft={draft} />;
  if (identity.kind === "avatar") return <Avatar name={identity.name} seed={identity.seed} size="lg" tone={draft ? "neutral" : undefined} />;
  if (identity.kind === "image" && failedSrc !== identity.src) return <img src={identity.src} alt={label}
    className="h-13 w-13 shrink-0 rounded-md border border-line object-cover" onError={() => setFailedSrc(identity.src)} />;
  return <span role="img" aria-label={label}
    className={`inline-flex h-13 w-13 shrink-0 items-center justify-center rounded-md border ${toneClasses[!draft && identity.kind === "icon" ? identity.tone : "neutral"]}`}>
    <Icon name={identity.kind === "icon" ? identity.icon : "User"} /></span>;
}
