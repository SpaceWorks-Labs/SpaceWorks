import { useId, useState } from "react";
import { ConfirmDialog } from "./ConfirmDialog";
import { RouteLink } from "./RouteLink";
import { Icon } from "./icon";
import type { Action } from "./types";
export type ActionControlProps = { action: Action; primary?: boolean; className?: string };
/** Shared action slots keep pending, disabled reasons and confirmation copy consistent. */
export function ActionControl({ action, primary = false, className = "" }: ActionControlProps) {
  const reasonId = useId();
  const [confirming, setConfirming] = useState(false);
  const run = () => { if (action.confirm) setConfirming(true); else action.onClick?.(); };
  const blocked = Boolean(action.disabled || action.pending);
  const label = action.pending ? action.pendingLabel ?? "Working…" : action.confirms && !action.label.endsWith("…")
    ? `${action.label}…` : action.label;
  const style = action.tone === "danger" ? "desk-button-danger-outline"
    : primary ? "desk-button-primary" : "desk-button";
  const classes = `${style} min-w-11 gap-2 ${className}`;
  const content = <>{action.icon ? <Icon name={action.icon} /> : null}{label}</>;
  return <>
    {action.href ? <RouteLink href={blocked ? undefined : action.href} role={blocked ? "link" : undefined}
      title={action.disabledReason} aria-disabled={blocked || undefined} aria-busy={action.pending || undefined}
      aria-describedby={action.disabledReason ? reasonId : undefined} tabIndex={blocked ? -1 : undefined}
      target={action.external ? "_blank" : undefined} rel={action.external ? "noopener noreferrer" : undefined}
      className={`${classes} ${blocked ? "cursor-not-allowed border-line bg-surface text-muted" : ""}`}
      onClick={event => { if (blocked) event.preventDefault(); else run(); }}>{content}</RouteLink>
      : <button type="button" className={classes} title={action.disabledReason} disabled={blocked} aria-busy={action.pending || undefined}
        aria-describedby={action.disabledReason ? reasonId : undefined} onClick={run}>{content}</button>}
    {action.disabledReason ? <span id={reasonId} className="sr-only">{action.disabledReason}</span> : null}
    {confirming && action.confirm ? <ConfirmDialog open title={action.confirm.title} message={action.confirm.message}
      confirmLabel={action.confirm.confirmLabel ?? action.label} tone={action.tone === "danger" ? "danger" : "default"}
      onCancel={() => setConfirming(false)} onConfirm={() => { setConfirming(false); action.onClick?.(); }} /> : null}
  </>;
}
