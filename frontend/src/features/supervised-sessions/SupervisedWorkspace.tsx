import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";

import { SupervisedSessionList } from "./SupervisedSessionList";
import { SupervisedSessionManager } from "./SupervisedSessionManager";
import { SupervisedStartForm } from "./SupervisedStartForm";

/** Start form, the chosen session's manager and the instructor's sessions: shared by the staff
 *  machine drawer and the member page. Opening a session selects it straight away. */
export function SupervisedWorkspace({ makerspaceId, machineId, picker, initialSessionId = null }: {
  makerspaceId: number; machineId?: number; initialSessionId?: number | null;
  picker?: (value: string, onChange: (value: string) => void) => ReactNode;
}) {
  const [selected, setSelected] = useState<number | null>(initialSessionId);
  return <div className="grid min-w-0 gap-5">
    {selected ? <>
      <SupervisedSessionManager key={selected} sessionId={selected} picker={picker} />
      <button type="button" className="desk-button justify-self-start" onClick={() => setSelected(null)}>{t`Start another session`}</button>
    </> : <SupervisedStartForm makerspaceId={makerspaceId} machineId={machineId} onOpened={session => setSelected(session.id)} />}
    <SupervisedSessionList makerspaceId={makerspaceId} machineId={machineId} selectedId={selected} onOpen={setSelected} />
  </div>;
}
