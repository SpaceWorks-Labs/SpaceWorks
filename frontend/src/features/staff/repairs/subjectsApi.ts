import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { getMachines } from "../machinesApi/machines";
import type { SubjectType } from "./repairsApi";

export type SubjectOption = { id: number; label: string };

/** What a repair job or a schedule can be about: this space's machines, items or rooms. */
export function useSubjectOptions(makerspaceId: number, type: SubjectType, on = true): { options: SubjectOption[]; loading: boolean } {
  const machines = useQuery({ queryKey: ["repairs", "subjects", "machines", makerspaceId], enabled: on && type === "machine",
    queryFn: () => getMachines(makerspaceId) });
  const items = useQuery({ queryKey: ["repairs", "subjects", "items", makerspaceId], enabled: on && type === "inventory_product",
    queryFn: () => staffRequest<{ results: { id: number; name: string }[] }>(`/admin/makerspace/${makerspaceId}/inventory?page_size=1000`) });
  const rooms = useQuery({ queryKey: ["repairs", "subjects", "rooms", makerspaceId], enabled: on && type === "bookable_space",
    queryFn: () => staffRequest<{ results: { id: number; name: string }[] }>(`/admin/makerspaces/${makerspaceId}/spaces/?page_size=200`) });
  if (type === "machine") return { loading: machines.isLoading,
    options: (machines.data?.results ?? []).map(row => ({ id: row.id, label: `${row.name} · ${row.machine_type.name}` })) };
  if (type === "bookable_space") return { loading: rooms.isLoading,
    options: (rooms.data?.results ?? []).map(row => ({ id: row.id, label: row.name })) };
  return { loading: items.isLoading, options: (items.data?.results ?? []).map(row => ({ id: row.id, label: row.name })) };
}
