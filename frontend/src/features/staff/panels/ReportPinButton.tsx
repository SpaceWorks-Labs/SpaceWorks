import { t } from "@lingui/core/macro";

export function ReportPinButton({ title, pinned, onToggle }: { title: string; pinned: boolean; onToggle: () => void }) {
  return <button type="button" aria-pressed={pinned} onClick={onToggle}
    aria-label={pinned ? t`Unpin ${title}` : t`Pin ${title}`} title={pinned ? t`Unpin` : t`Pin to the top`}
    className="grid size-11 shrink-0 place-items-center rounded-control text-lg text-muted hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus aria-pressed:text-accent">
    <span aria-hidden="true">{pinned ? "★" : "☆"}</span>
  </button>;
}
