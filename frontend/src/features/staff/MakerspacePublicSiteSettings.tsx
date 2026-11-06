import { t } from "@lingui/core/macro";
import { WebsiteEmbedOrigins } from "./WebsiteEmbedOrigins";
import { ClosedNoticeSettings } from "./ClosedNoticeSettings";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./panels/shared";

export function MakerspacePublicSiteSettings({ makerspace, loading }: { makerspace: Makerspace; loading: boolean }) {
  const client = useQueryClient();
  const [embedOpen, setEmbedOpen] = useState(false);
  const update = useMutation({
    mutationFn: (patch: Pick<Makerspace, "public_site_enabled" | "public_landing_page">) =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: () => {
      for (const key of ["makerspace-settings", "makerspaces", "tenant-bootstrap", "runtime-tenant", "runtime-tenant-origin", "public-makerspaces", "member"])
        void client.invalidateQueries({ queryKey: [key] });
      void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
    },
  });
  return <div className="mt-5 space-y-3">
    <label className="min-h-11 flex gap-3 text-sm font-semibold"><input type="checkbox"
      checked={makerspace.public_site_enabled ?? true} disabled={loading || update.isPending}
      onChange={(event) => update.mutate({ public_site_enabled: event.target.checked })} />{t`Publish public site`}</label>
    <p className="text-xs text-muted">{t`Controls directory visibility, browser embed keys and public machine pages. The inventory catalogue has its own switch.`}</p>
    <label className="grid gap-2 text-sm font-semibold">{t`Public home`}<select className="desk-input max-w-full" value={makerspace.public_landing_page ?? "auto"} disabled={loading || update.isPending}
        onChange={(event) => update.mutate({ public_landing_page: event.target.value as Makerspace["public_landing_page"] })}>
        {[["auto", "Automatic"], ["inventory", "Inventory"], ["events", "Events"], ["bookings", "Bookings"], ["machines", "Machines"], ["membership", "Membership"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
    <p className="text-xs text-muted">{t`Automatic and Inventory now show the combined makerspace page. If the selected family is disabled, the home uses an available family.`}</p>
    {makerspace.enabled_features?.includes("public_site.closed_notice") ? <ClosedNoticeSettings makerspaceId={makerspace.id} /> : null}
    <details onToggle={(event) => setEmbedOpen(event.currentTarget.open)}><summary className="cursor-pointer font-semibold">{t`Website embedding`}</summary>{embedOpen ? <WebsiteEmbedOrigins makerspaceId={makerspace.id} /> : null}</details>
    {update.error ? <p role="alert" className="text-sm text-danger">{update.error.message}</p> : null}
  </div>;
}
