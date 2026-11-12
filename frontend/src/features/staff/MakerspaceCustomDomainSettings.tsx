import { t } from "@lingui/core/macro";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import type { ApiPath } from "../../generated/api";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";
import { CustomDomainGuide, domainStatusLabel, domainStatusTone, type DomainRecord, type DomainStatus } from "./CustomDomainGuide";
import { BoxArt } from "../../components/BoxSpinner";

type Props = {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
};

type VerifyDomainResponse = {
  status: DomainStatus;
  token: string;
  expected_record: DomainRecord | null;
  verified_at: string | null;
  detail: string;
};

const VERIFY_DOMAIN_API_PATH: ApiPath = "/api/v1/admin/makerspace/{makerspace_id}/verify-domain";

function verifyDomainStaffPath(makerspaceId: number) {
  return VERIFY_DOMAIN_API_PATH.replace("/api/v1", "").replace("{makerspace_id}", String(makerspaceId));
}

/** The space's own domain or frontend (#192). Any Space Manager may set it, on self-host too;
 *  it is trusted only once VERIFIED (the operator's own domain at once, anyone else's after the
 *  DNS TXT proof). Directory visibility is a separate row (MakerspaceDirectoryVisibility). */
export function MakerspaceCustomDomainSettings({ makerspace, settings, loading }: Props) {
  const queryClient = useQueryClient();
  const [domainInput, setDomainInput] = useState("");
  const [verifyDetail, setVerifyDetail] = useState("");

  const currentDomain = settings?.frontend_domain ?? makerspace.frontend_domain ?? null;
  const status = settings?.frontend_domain_status ?? makerspace.frontend_domain_status ?? "pending";
  const record = settings?.domain_verification_record ?? makerspace.domain_verification_record ?? null;
  const token = settings?.domain_verification_token ?? makerspace.domain_verification_token ?? "";

  useEffect(() => {
    setDomainInput(currentDomain ?? "");
    setVerifyDetail("");
  }, [currentDomain, makerspace.id]);

  const refreshSettings = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };

  const trimmedDomain = domainInput.trim();
  const domainChanged = trimmedDomain !== (currentDomain ?? "");

  const updateCustomDomain = useMutation({
    mutationFn: () =>
      staffRequest<Makerspace>(`/admin/makerspaces/${makerspace.id}`, {
        method: "PATCH",
        body: JSON.stringify({ frontend_domain: trimmedDomain }),
      }),
    onSuccess: (updated) => {
      setDomainInput(updated.frontend_domain ?? "");
      setVerifyDetail("");
      refreshSettings();
    },
  });

  const verifyDomain = useMutation({
    mutationFn: () =>
      staffRequest<VerifyDomainResponse>(verifyDomainStaffPath(makerspace.id), {
        method: "POST",
      }),
    onSuccess: (result) => {
      setVerifyDetail(result.detail);
      refreshSettings();
    },
  });

  const domainSaveDisabled = loading || updateCustomDomain.isPending || !domainChanged;
  const verifyDisabled = loading || verifyDomain.isPending || !currentDomain || domainChanged;

  return (
    <SettingsRow label={t`Your own domain or frontend`}
      helper={t`Run this space's public site and staff console on a domain you control, served by this deployment or by your own SpaceWorks frontend.`}><div className="@container grid min-w-0 gap-4">
      <form
        className="grid min-w-0 gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!domainSaveDisabled) {
            updateCustomDomain.mutate();
          }
        }}
      >
        <div className="grid min-w-0 gap-3 md:items-start">
          {currentDomain ? <div className="flex flex-wrap items-center gap-2">
            <Badge label="" tone={domainStatusTone(status)}>{domainStatusLabel(status)}</Badge>
          </div> : null}
          <SettingsEditorActions dirty={domainChanged} onDiscard={() => { setDomainInput(currentDomain ?? ""); setVerifyDetail(""); }}
            pending={updateCustomDomain.isPending} disabled={domainSaveDisabled} />
        </div>

        <div className="grid min-w-0 max-w-xl gap-2">
          <label className="text-sm font-semibold text-ink" htmlFor="custom-domain">
            {t`Domain`}</label>
          <input
            id="custom-domain"
            className="desk-input"
            placeholder="alphamakerspace.com"
            value={domainInput}
            onChange={(event) => setDomainInput(event.target.value)}
          />
        </div>

        {currentDomain && !domainChanged ? (
          <div className="grid min-w-0 gap-3 rounded-md border border-line bg-surface p-3">
            <CustomDomainGuide domain={currentDomain} record={record} status={status} />
            {status !== "verified" ? (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="desk-button w-full max-w-full sm:w-auto"
                  type="button"
                  disabled={verifyDisabled}
                  onClick={() => verifyDomain.mutate()}
                >
                  {verifyDomain.isPending ? <><BoxArt size={16} mono />{t`Checking...`}</> : t`Verify domain`}
                </button>
                {token ? <span className="break-all text-xs text-muted">{t`Token: ${token}`}</span> : null}
              </div>
            ) : null}
          </div>
        ) : null}
        {domainChanged && trimmedDomain ? (
          <p className="text-sm text-muted">{t`Save the domain first; the DNS steps and the verification check appear after.`}</p>
        ) : null}
        {verifyDetail ? <p role="status" className="text-sm text-ink">{verifyDetail}</p> : null}
        {updateCustomDomain.error ? (
          <p role="alert" className="text-sm text-danger">{updateCustomDomain.error.message}</p>
        ) : null}
        {verifyDomain.error ? (
          <p role="alert" className="text-sm text-danger">{verifyDomain.error.message}</p>
        ) : null}
      </form>
    </div></SettingsRow>
  );
}
