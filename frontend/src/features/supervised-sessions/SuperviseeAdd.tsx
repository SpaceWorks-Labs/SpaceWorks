import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";

import { SuperviseePeoplePicker } from "./SuperviseePeoplePicker";

/** Add a supervisee. The default control searches the people the instructor may supervise
 *  (checked in, or registered for the session's event); staff pass their own picker instead. */
export function SuperviseeAdd({ sessionId, onAdd, pending, picker }: {
  sessionId: number; onAdd: (userId: number, done: () => void) => void; pending: boolean;
  picker?: (value: string, onChange: (value: string) => void) => ReactNode;
}) {
  const [value, setValue] = useState("");
  const ready = /^\d+$/.test(value) && Number(value) > 0;
  return <form className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end" onSubmit={event => {
    event.preventDefault();
    if (ready && !pending) onAdd(Number(value), () => setValue(""));
  }}>
    {picker ? picker(value, setValue) : <SuperviseePeoplePicker sessionId={sessionId} value={value} onChange={setValue} />}
    <button type="submit" className="desk-button-primary" disabled={!ready || pending}>{pending ? t`Adding…` : t`Add supervisee`}</button>
  </form>;
}
