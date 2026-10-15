import { machineStatusLabel } from "./machineStatusLabel";
import { ListRow, RelativeTime, StatusPill } from "../../../../components/ui";
import { MachineTabContent } from "./MachineTabContent";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addMachineErrorLog, collectionResults, getMachineErrorLogs, machineKeys } from "../../machinesApi";

export function ErrorsTab({ machineId, canOperate }: { machineId: number; canOperate: boolean }) {
  const queryClient = useQueryClient();
  const [severity, setSeverity] = useState("error");
  const [message, setMessage] = useState("");
  const logs = useQuery({
    queryKey: machineKeys.errors(machineId),
    queryFn: () => getMachineErrorLogs(machineId),
  });
  const items = collectionResults(logs.data);
  const add = useMutation({
    mutationFn: () => addMachineErrorLog(machineId, {
      severity: severity.trim(),
      message: message.trim(),
    }),
    onSuccess: async () => {
      setMessage("");
      await queryClient.invalidateQueries({ queryKey: machineKeys.errors(machineId) });
    },
  });

  return (
    <section>
      <h3 className="title-section mb-3">Error logs</h3>
      <MachineTabContent query={logs} resource="error logs" empty={!items.length} message="No errors logged. Add a log when something needs attention.">
      <div className="grid gap-2">
        {items.map((entry) => (
          <ListRow key={entry.id} title={entry.message} meta={<>{entry.logged_by_username ? `Logged by ${entry.logged_by_username} · ` : ""}<RelativeTime date={entry.created_at} exact /></>}
            right={<StatusPill label={machineStatusLabel(entry.severity)} tone={entry.severity === "warning" ? "warn" : entry.severity === "info" ? "info" : "danger"} />} />
        ))}
      </div>
      </MachineTabContent>
      {canOperate ? (
        <form className="mt-3 grid gap-2" onSubmit={(event) => { event.preventDefault(); add.mutate(); }}>
          <label className="eyebrow grid gap-1">Severity
            <input className="desk-input" maxLength={16} value={severity}
              onChange={(event) => setSeverity(event.target.value)} required />
          </label>
          <label className="eyebrow grid gap-1">Message
            <textarea className="desk-input min-h-20" value={message}
              onChange={(event) => setMessage(event.target.value)} required />
          </label>
          <button className="desk-button-primary justify-self-start" type="submit"
            disabled={add.isPending || !severity.trim() || !message.trim()}>
            {add.isPending ? "Logging..." : "Add error log"}
          </button>
        </form>
      ) : null}
      {add.error instanceof Error ? <p className="mt-2 text-sm text-danger">{add.error.message}</p> : null}
    </section>
  );
}
