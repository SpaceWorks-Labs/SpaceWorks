import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

export function MakerspaceFilamentSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const currentThreshold =
    settings?.filament_low_stock_threshold_grams ??
    makerspace.filament_low_stock_threshold_grams ??
    "0.00";
  const [thresholdInput, setThresholdInput] = useState(String(currentThreshold));

  useEffect(() => {
    setThresholdInput(String(currentThreshold));
  }, [currentThreshold, makerspace.id]);

  const updateThreshold = useMutation({
    mutationFn: (next: string) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ filament_low_stock_threshold_grams: next || "0" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
      queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
      queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });

  const normalizedThreshold = thresholdInput.trim() || "0";
  const currentNumber = Number(currentThreshold);
  const nextNumber = Number(normalizedThreshold);
  const invalid = Number.isNaN(nextNumber) || nextNumber < 0;
  const saveDisabled =
    loading || updateThreshold.isPending || invalid || nextNumber === currentNumber;

  return (
    <SettingsRow label="Filament low-stock threshold" helper="Auto-add a printing to-buy item when an active spool reaches this remaining weight. Set 0 to turn it off."><div className="grid min-w-0 gap-4">
      <form
        className="grid min-w-0 gap-3  md:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          if (!saveDisabled) {
            updateThreshold.mutate(normalizedThreshold);
          }
        }}
      >
        <div className="grid min-w-0 max-w-2xl gap-2 md:items-start">
          <div className="flex flex-wrap items-center gap-2">

            <Badge label="" tone={currentNumber > 0 ? "success" : "neutral"}>
              {currentNumber > 0 ? `${currentThreshold}g` : "Off"}
            </Badge>
          </div>

          {updateThreshold.error ? (
            <p className="text-sm text-danger">{updateThreshold.error.message}</p>
          ) : null}
          {invalid ? <p className="text-sm text-danger">Enter zero or a positive gram value.</p> : null}
        </div>
        <label className="grid gap-1 text-sm font-semibold text-ink">
          Threshold (g)
          <input
            className="desk-input"
            type="number"
            min={0}
            step="0.01"
            value={thresholdInput}
            disabled={loading || updateThreshold.isPending}
            onChange={(event) => setThresholdInput(event.target.value)}
          />
        </label>
        <SettingsEditorActions dirty={nextNumber !== currentNumber} onDiscard={() => setThresholdInput(String(currentThreshold))} pending={updateThreshold.isPending} disabled={saveDisabled} />
      </form>
    </div></SettingsRow>
  );
}