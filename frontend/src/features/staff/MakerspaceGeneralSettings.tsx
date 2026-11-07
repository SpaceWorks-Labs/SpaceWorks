import { t } from "@lingui/core/macro";
import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { SettingsRow } from "../../components/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { MakerspacePublicSiteSettings } from "./MakerspacePublicSiteSettings";
import type { Makerspace } from "./panels/shared";
import { SUPPORTED_LOCALES } from "../../generated/locales";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

/**
 * Default loan days and the rest of the loan policy moved to the Lending section (and the
 * Inventory Manager's Lending settings): they are one policy, edited through one endpoint.
 */
export function MakerspaceGeneralSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const publicInventoryEnabled =
    settings?.public_inventory_enabled ?? makerspace.public_inventory_enabled ?? true;

  const refreshSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };

  const updatePublicInventory = useMutation({
    mutationFn: (next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_inventory_enabled: next }),
      }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updatePublicInventory`),
    onSuccess: async (_data, next) => {
      await (refreshSettings)();
      toast(t`Public inventory turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updatePublicInventory`, undo: async () => {
        await ((next: boolean) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ public_inventory_enabled: next }),
      }))(!next);
        await (refreshSettings)();
      } });
    },
  });

  const defaultLocale = settings?.default_locale ?? makerspace.default_locale ?? "en";
  const updateLocale = useMutation({
    mutationFn: (next: string) => staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ default_locale: next }),
    }),
    onSuccess: async () => {
      refreshSettings();
      await queryClient.invalidateQueries({ queryKey: ["runtime-tenant"] });
      await queryClient.invalidateQueries({ queryKey: ["runtime-tenant-origin"] });
      toast(t`Default language saved.`);
    },
  });

  return <>
    <SettingsRow label={t`Default language`} helper={t`Shared notices, the space feed and members without their own choice use this language.`}>
      <div className="grid gap-2">
        <select aria-label={t`Default language`} className="min-h-11 rounded-control border border-line bg-panel px-3 text-ink"
          value={defaultLocale} disabled={loading || updateLocale.isPending} onChange={event => updateLocale.mutate(event.target.value)}>
          {SUPPORTED_LOCALES.map(locale => <option key={locale.code} value={locale.code} lang={locale.code}>{locale.label}</option>)}
        </select>
        {updateLocale.error ? <p role="alert" className="text-sm text-danger">{updateLocale.error.message}</p> : null}
      </div>
    </SettingsRow>
    <SettingsRow label={t`Public inventory`} helper={t`Show the public catalogue. Turning this off keeps your inventory data.`}>
      <div className="@container grid gap-3"><Badge label="" tone={publicInventoryEnabled ? "success" : "neutral"}>{publicInventoryEnabled ? t`On` : t`Off`}</Badge>
        <label className="flex min-h-11 items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={publicInventoryEnabled}
          disabled={loading || updatePublicInventory.isPending} onChange={event => updatePublicInventory.mutate(event.target.checked)} />{t`Show public inventory`}</label>
        {updatePublicInventory.error ? <p role="alert" className="text-sm text-danger">{updatePublicInventory.error.message}</p> : null}
      </div>
    </SettingsRow>
    <MakerspacePublicSiteSettings makerspace={settings ?? makerspace} loading={loading} />
  </>;
}
