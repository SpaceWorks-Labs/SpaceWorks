import type { ReactNode } from "react";
import { ActionControl } from "./ActionControl";
import type { EmptyProps } from "./types";
export type EmptyStateProps = EmptyProps | { title: string; description?: string; action?: ReactNode };
export function EmptyState(props: EmptyStateProps) {
  const modern = "message" in props;
  return <div className="flex min-h-32 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line p-6 text-center">
    {modern ? <p role="status" className="max-w-md text-[15px] text-muted">{props.message}</p>
      : <><h3 className="title-section">{props.title}</h3>
        {props.description ? <p className="max-w-md text-sm text-muted">{props.description}</p> : null}</>}
    {modern ? props.action ? <ActionControl action={props.action} /> : null : props.action ? <div>{props.action}</div> : null}
  </div>;
}
