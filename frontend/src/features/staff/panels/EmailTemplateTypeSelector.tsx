import { SegmentedControl } from "../../../components/ui";
export type MachineTypeOption = {
  id: number;
  name: string;
  is_active: boolean;
  is_overridden: boolean;
};

export function EmailTemplateTypeSelector({
  canEditSpaceDefault,
  types,
  selectedTypeId,
  onSelect,
}: {
  canEditSpaceDefault: boolean;
  types: MachineTypeOption[];
  selectedTypeId: number | null;
  onSelect: (machineType: MachineTypeOption | null) => void;
}) {
  return <SegmentedControl label="Machine type" value={selectedTypeId === null ? "space" : String(selectedTypeId)}
    options={[...(canEditSpaceDefault ? [{ value: "space", label: "Space default" }] : []), ...types.map(type => ({ value: String(type.id), label: `${type.name}${type.is_overridden ? " · Edited" : ""}` }))]}
    onChange={value => onSelect(value === "space" ? null : types.find(type => String(type.id) === value) ?? null)} />;
}
