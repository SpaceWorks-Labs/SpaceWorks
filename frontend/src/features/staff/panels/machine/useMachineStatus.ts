import { useMutation, useQueryClient } from "@tanstack/react-query";
import { machineKeys, setMachineStatus, type MachineStatus } from "../../machinesApi";

/** Both status controls use the existing endpoint and refresh the same fleet/detail caches. */
export function useMachineStatus(machineId: number, makerspaceId: number, status: MachineStatus) {
  const client = useQueryClient();
  return useMutation({ mutationFn: () => setMachineStatus(machineId, status),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: machineKeys.detail(machineId) }),
        client.invalidateQueries({ queryKey: machineKeys.list(makerspaceId) }),
      ]);
    } });
}
