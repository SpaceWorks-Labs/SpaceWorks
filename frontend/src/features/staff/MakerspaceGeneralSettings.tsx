import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { MakerspaceLoanPolicySettings } from "./MakerspaceLoanPolicySettings";
import { MakerspacePublicSiteSettings } from "./MakerspacePublicSiteSettings";
import type { Makerspace } from "./panels/shared";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

export function MakerspaceGeneralSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const currentDefaultLoanDays = settings?.default_loan_days ?? makerspace.default_loan_days ?? 7;
  const publicInventoryEnabled =
    settings?.public_inventory_enabled ?? makerspace.public_inventory_enabled ?? true;
  const [defaultLoanDays, setDefaultLoanDays] = useState(String(currentDefaultLoanDays));

  useEffect(() => {
    setDefaultLoanDays(String(currentDefaultLoanDays));
  }, [currentDefaultLoanDays, makerspace.id]);

  const refreshSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["staff", "loan-policy", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };

  const updateDefaultLoanDays = useMutation({
    mutationFn: (value: string) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ default_loan_days: Number(value) || 7 }),
      }),
    onSuccess: refreshSettings,
  });

  const updatePublicInventory = useMutation({
    mutationFn: (next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_inventory_enabled: next }),
      }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updatePublicInventory`),
    onSuccess: async (_data, next) => {
      await (refreshSettings)();
      toast(`Public inventory turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updatePublicInventory`, undo: async () => {
        await ((next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_inventory_enabled: next }),
      }))(!next);
        await (refreshSettings)();
      } });
    },
  });

  return <>
    <SettingsRow label="Default loan days" helper="Set the default return window applied when a hardware request is issued."><form
          className="@container grid min-w-0 gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            updateDefaultLoanDays.mutate(defaultLoanDays);
          }}
        >
          <label className="text-sm font-semibold text-ink" htmlFor="default-loan-days">
            Default loan days
          </label>
          <input
            id="default-loan-days"
            className="desk-input"
            type="number"
            min="1"
            value={defaultLoanDays}
            disabled={loading || updateDefaultLoanDays.isPending}
            onChange={(event) => setDefaultLoanDays(event.target.value)}
          />

          <div>
            <SettingsEditorActions dirty={defaultLoanDays !== String(currentDefaultLoanDays)} onDiscard={() => setDefaultLoanDays(String(currentDefaultLoanDays))} pending={updateDefaultLoanDays.isPending} disabled={loading || updateDefaultLoanDays.isPending} />
          </div>
          {updateDefaultLoanDays.error ? (
            <p className="text-sm text-danger">{updateDefaultLoanDays.error.message}</p>
          ) : null}
        </form></SettingsRow>
    <SettingsRow label="Public inventory" helper="Show the public catalogue. Turning this off keeps your inventory data.">
      <div className="@container grid gap-3"><Badge label="" tone={publicInventoryEnabled ? "success" : "neutral"}>{publicInventoryEnabled ? "On" : "Off"}</Badge>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={publicInventoryEnabled}
          disabled={loading || updatePublicInventory.isPending} onChange={event => updatePublicInventory.mutate(event.target.checked)} />Show public inventory</label>
        {updatePublicInventory.error ? <p role="alert" className="text-sm text-danger">{updatePublicInventory.error.message}</p> : null}
      </div>
    </SettingsRow>
    <MakerspacePublicSiteSettings makerspace={settings ?? makerspace} loading={loading} />
    {makerspace.enabled_features?.includes("loans.enabled") ? <MakerspaceLoanPolicySettings makerspaceId={makerspace.id} /> : null}
  </>;
}
