import { useMutation, useQueryClient } from "@tanstack/react-query";
import { machineKeys, setMachineStatus, type MachineStatus } from "../../machinesApi";
import { downtimeKeys } from "./machineDowntimeApi";

type Downtime = { reason?: string; expected_back_at?: string | null };

/** Both status controls use the existing endpoint and refresh the same fleet/detail caches. */
export function useMachineStatus(machineId: number, makerspaceId: number, status: MachineStatus, downtime?: Downtime) {
  const client = useQueryClient();
  return useMutation({ mutationFn: () => setMachineStatus(machineId, status, downtime),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: machineKeys.detail(machineId) }),
        client.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }),
        client.invalidateQueries({ queryKey: downtimeKeys.downtime(machineId) }),
      ]);
    } });
}
