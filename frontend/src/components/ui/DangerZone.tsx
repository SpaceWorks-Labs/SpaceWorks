import { useId } from "react";
import { ActionControl } from "./ActionControl";
import type { Action } from "./types";
export type DangerZoneProps = { title: string; consequence: string; action: Action };
export function DangerZone({ title, consequence, action }: DangerZoneProps) {
  const id = useId();
  return <section aria-labelledby={id} className="mt-10 flex flex-wrap items-center gap-4 rounded-xl border border-danger-line bg-panel p-5">
    <div className="min-w-0 flex-1 basis-64"><h2 id={id} className="title-section text-danger">{title}</h2>
      <p className="mt-2 text-sm text-ink">{consequence}</p></div>
    <ActionControl action={{ ...action, tone: "danger", confirms: true }} />
  </section>;
}
