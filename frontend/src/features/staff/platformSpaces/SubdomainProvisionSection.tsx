import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorText, KeyValueCard } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { staffRequest, StructuredApiError } from "../../../lib/api";
import type { Makerspace } from "../panels/shared";
import { healthKey, post } from "./spacesApi";
import { BoxArt } from "../../../components/BoxSpinner";

type SpaceDomain = Pick<Makerspace, "id" | "frontend_domain" | "frontend_domain_status" | "platform_hosting" | "is_platform_subdomain">;

export const spaceDomainKey = (id: number) => ["platform-space-domain", id] as const;

/**
 * Spaces › one space › Web address (0.12.0 row 24, #219(h)): the superadmin gives a space a
 * platform subdomain directly (`POST admin/makerspace/<id>/provision-subdomain`), without
 * waiting for the space to ask. The server validates the label, verifies the domain and
 * audits `makerspace.subdomain_provisioned`; a self-hosted deployment has no platform
 * subdomains, so the form is not offered there.
 */
export function SubdomainProvisionSection({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [label, setLabel] = useState("");
  const space = useQuery({ queryKey: spaceDomainKey(makerspaceId),
    queryFn: () => staffRequest<SpaceDomain>(`/admin/makerspaces/${makerspaceId}`, {}, "platform") });
  const provision = useMutation({
    mutationFn: (value: string) => post<SpaceDomain>(`/admin/makerspace/${makerspaceId}/provision-subdomain`, { label: value }),
    onSuccess: (row) => {
      client.setQueryData(spaceDomainKey(makerspaceId), row);
      void client.invalidateQueries({ queryKey: healthKey });
      setLabel("");
      toast(t`Subdomain provisioned: ${row.frontend_domain ?? ""}`);
    },
  });
  if (space.isLoading) return null;
  // A suspended or archived space is not servable: there is nothing to provision.
  if (space.error instanceof StructuredApiError && space.error.status === 404) return null;
  if (space.isError) return <ErrorText resource={t`this space's web address`} onRetry={() => { void space.refetch(); }} />;
  if (!space.data?.platform_hosting) return null;
  const domain = space.data.frontend_domain;
  // Provisioning REPLACES the space's address: say so when a custom domain is set.
  const replacesCustom = Boolean(domain) && !space.data.is_platform_subdomain;
  return <section aria-label={t`Web address`} className="grid gap-3">
    <KeyValueCard title={t`Web address`} items={[{ label: t`Current domain`, value: domain ? `${domain}${space.data.is_platform_subdomain ? t` (platform subdomain)` : ""}` : t`None — the space uses its /m/ path` }]} />
    <form className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end" onSubmit={event => {
      event.preventDefault();
      if (label.trim() && !provision.isPending) provision.mutate(label.trim());
    }}>
      <label className="grid gap-2 text-sm font-semibold text-ink" htmlFor={`provision-subdomain-${makerspaceId}`}>
        {space.data.is_platform_subdomain ? t`New subdomain label` : t`Subdomain label`}
        <input id={`provision-subdomain-${makerspaceId}`} className="desk-input" placeholder="alpha" maxLength={63}
          value={label} onChange={event => setLabel(event.target.value)} />
      </label>
      <button type="submit" className="desk-button-primary" disabled={!label.trim() || provision.isPending}>
        {provision.isPending ? <><BoxArt size={16} mono />{t`Provisioning…`}</> : t`Provision subdomain`}
      </button>
    </form>
    {replacesCustom ? <p className="text-sm text-warn-ink">{t`This replaces the custom domain ${domain ?? ""}.`}</p> : null}
    {provision.error ? <ErrorText message={provision.error.message} /> : null}
  </section>;
}
