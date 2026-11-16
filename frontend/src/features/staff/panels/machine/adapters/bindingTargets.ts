import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";
import { collectionResults, getMachines, getMachineTypes, machineKeys } from "../../../machinesApi";
import type { Binding, TargetType } from "./adaptersApi";

export type TargetOption = { value: string; label: string };
type Rows<T> = { results: T[] };
/** Door targets have no list to pick from: staff type the name the bridge uses. */
export const FREE_TEXT_TARGETS: TargetType[] = ["door"];
export const TARGET_TYPES: TargetType[] = ["machine", "machine_type", "storage_location", "item", "box", "door", "space"];

const unique = (options: TargetOption[]) => options.filter((option, index) => option.value && options.findIndex(other => other.value === option.value) === index);

type Data = ReturnType<typeof useTargetData>;

/** The lists behind the target pickers, from the existing staff APIs (never a public endpoint: storage locations stay staff-only). Only the wanted types are fetched. */
function useTargetData(makerspaceId: number, wanted: TargetType[]) {
  const on = (...kinds: TargetType[]) => kinds.some(kind => wanted.includes(kind));
  const machines = useQuery({ queryKey: machineKeys.list(makerspaceId), queryFn: () => getMachines(makerspaceId), enabled: on("machine") });
  const types = useQuery({ queryKey: machineKeys.types(makerspaceId), queryFn: () => getMachineTypes(makerspaceId), enabled: on("machine_type") });
  const inventory = useQuery({ queryKey: ["adapter-targets", makerspaceId, "inventory"], enabled: on("item", "storage_location"),
    queryFn: () => staffRequest<Rows<{ id: number; name: string; storage_location?: string | null }>>(`/admin/makerspace/${makerspaceId}/inventory?page_size=1000`) });
  const boxes = useQuery({ queryKey: ["adapter-targets", makerspaceId, "boxes"], enabled: on("box"),
    queryFn: () => staffRequest<Rows<{ id: number; label: string; code?: string }>>(`/admin/makerspace/${makerspaceId}/containers?page_size=1000`) });
  const spaces = useQuery({ queryKey: ["adapter-targets", makerspaceId, "spaces"], enabled: on("space"),
    queryFn: () => staffRequest<Rows<{ id: number; name: string }>>(`/admin/makerspaces/${makerspaceId}/spaces/`) });
  return { machines, types, inventory, boxes, spaces };
}

function optionsOf(type: TargetType, data: Data): { options: TargetOption[]; loading: boolean } {
  switch (type) {
    case "machine": return { loading: data.machines.isLoading, options: (data.machines.data?.results ?? []).filter(row => row.is_active).map(row => ({ value: String(row.id), label: row.name })) };
    case "machine_type": return { loading: data.types.isLoading, options: collectionResults(data.types.data).map(row => ({ value: String(row.id), label: row.name })) };
    case "item": return { loading: data.inventory.isLoading, options: (data.inventory.data?.results ?? []).map(row => ({ value: String(row.id), label: row.name })) };
    case "storage_location": return { loading: data.inventory.isLoading, options: unique((data.inventory.data?.results ?? []).map(row => ({ value: row.storage_location ?? "", label: row.storage_location ?? "" }))) };
    case "box": return { loading: data.boxes.isLoading, options: (data.boxes.data?.results ?? []).map(row => ({ value: String(row.id), label: row.code ? `${row.label} (${row.code})` : row.label })) };
    case "space": return { loading: data.spaces.isLoading, options: (data.spaces.data?.results ?? []).map(row => ({ value: String(row.id), label: row.name })) };
    default: return { loading: false, options: [] };
  }
}

export function useTargetOptions(makerspaceId: number, type: TargetType) {
  return optionsOf(type, useTargetData(makerspaceId, [type]));
}

/** A readable name for a binding's target ("Prusa MK4", "Shelf B2"), falling back to the stored id. */
export function useTargetLabel(makerspaceId: number, bindings: Binding[]) {
  const data = useTargetData(makerspaceId, bindings.map(binding => binding.target_type));
  return (type: TargetType, machineId: number | null, targetId: string, externalRef = "") => {
    const key = type === "machine" ? String(machineId ?? "") : targetId;
    const found = optionsOf(type, data).options.find(option => option.value === key)?.label;
    return found || externalRef || (type === "machine" ? t`Machine #${key}` : key) || targetTypeText(type);
  };
}
const targetTypeText = (type: TargetType) => type.replace(/_/g, " ");

