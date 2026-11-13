import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { ActionControl, Card, Modal } from "../ui";
import type { Action } from "../ui";
import { useLayoutMedia } from "./useLayoutMedia";

export type PublicActionCardProps = {
  title: string;
  summary?: ReactNode;
  form?: ReactNode;
  primary?: Action;
  secondary?: Action[];
  note?: string;
  state: "open" | "closed" | "done";
  doneContent?: ReactNode;
  /** onOpen runs before the sheet opens; secondary adds a second verb that opens the same sheet. */
  mobileBar: { summary: string; label: string; initiallyOpen?: boolean; onOpen?: () => void; secondary?: { label: string; onOpen: () => void } };
};
function ActionCardContent({ title, summary, form, primary, secondary, note, state, doneContent, inSheet = false }: PublicActionCardProps & { inSheet?: boolean }) {
  return <Card className="grid gap-4 shadow-overlay">
    {/* The phone sheet already titles itself; repeating it reads as a duplicate heading. */}
    {inSheet ? null : <h2 className="title-panel">{title}</h2>}{summary}
    {state === "done" ? <div role="status">{doneContent ?? t`Complete`}</div> : state === "closed" ? <p role="status">{note ?? t`This action is closed.`}</p>
      : <>{form}{primary ? <ActionControl action={primary} primary className="desk-button-brand w-full" /> : null}</>}
    {secondary?.length ? <div className="flex flex-wrap gap-2">{secondary.map(action => <ActionControl key={action.label} action={action} />)}</div> : null}
    {note && state !== "closed" ? <p className="text-sm text-muted">{note}</p> : null}
  </Card>;
}
/** One form tree: inline at tablet/desktop (beside the content when it keeps 360px, else under it), a sheet on phones. */
export function PublicActionCard(props: PublicActionCardProps) {
  const [open, setOpen] = useState(props.mobileBar.initiallyOpen ?? false);
  const tablet = useLayoutMedia("(min-width: 768px)");
  if (tablet) return <aside aria-label={props.title} className="min-w-0 self-start xl:sticky xl:top-6 xl:max-h-[calc(100dvh-3rem)] xl:overflow-y-auto xl:overscroll-contain"><ActionCardContent {...props} /></aside>;
  return <>
    <div className="sw-public-mobile-bar sw-fixed-bottom-bar flex flex-wrap items-center justify-between gap-3 border-t border-line bg-panel">
      <p className="min-w-0 flex-1 basis-40 text-sm text-ink">{props.mobileBar.summary}</p>
      <div className="flex flex-wrap gap-2">
        {props.mobileBar.secondary ? <ActionControl action={{ label: props.mobileBar.secondary.label, onClick: () => { props.mobileBar.secondary?.onOpen(); setOpen(true); } }} /> : null}
        <ActionControl primary className="desk-button-brand" action={{ label: props.mobileBar.label, onClick: () => { props.mobileBar.onOpen?.(); setOpen(true); } }} />
      </div>
    </div>
    <Modal open={open} onClose={() => setOpen(false)} title={props.title}
      footer={<ActionControl action={{ label: t`Close`, onClick: () => setOpen(false) }} />}>
      <ActionCardContent {...props} inSheet />
    </Modal>
  </>;
}
