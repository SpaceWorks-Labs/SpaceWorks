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
  mobileBar: { summary: string; label: string };
};
function ActionCardContent({ title, summary, form, primary, secondary, note, state, doneContent }: PublicActionCardProps) {
  return <Card className="grid gap-4 shadow-overlay">
    <h2 className="title-panel">{title}</h2>{summary}
    {state === "done" ? <div role="status">{doneContent ?? "Complete"}</div> : state === "closed" ? <p role="status">{note ?? "This action is closed."}</p>
      : <>{form}{primary ? <ActionControl action={primary} primary className="desk-button-brand w-full" /> : null}</>}
    {secondary?.length ? <div className="flex flex-wrap gap-2">{secondary.map(action => <ActionControl key={action.label} action={action} />)}</div> : null}
    {note && state !== "closed" ? <p className="text-sm text-muted">{note}</p> : null}
  </Card>;
}
/** One form tree: inline at tablet/desktop, opened as a sheet on phones. */
export function PublicActionCard(props: PublicActionCardProps) {
  const [open, setOpen] = useState(false);
  const tablet = useLayoutMedia("(min-width: 768px)");
  if (tablet) return <aside aria-label={props.title} className="min-w-0 self-start xl:sticky xl:top-6"><ActionCardContent {...props} /></aside>;
  return <>
    <div className="sw-public-mobile-bar flex flex-wrap items-center justify-between gap-3 border-t border-line bg-panel p-4">
      <p className="text-sm text-ink">{props.mobileBar.summary}</p>
      <ActionControl primary className="desk-button-brand" action={{ label: props.mobileBar.label, onClick: () => setOpen(true) }} />
    </div>
    <Modal open={open} onClose={() => setOpen(false)} title={props.title}
      footer={<ActionControl action={{ label: "Close", onClick: () => setOpen(false) }} />}>
      <ActionCardContent {...props} />
    </Modal>
  </>;
}
