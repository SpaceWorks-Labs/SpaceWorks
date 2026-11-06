// /oauth/authorize (#196): the consent screen an app sends you to. It shows the app, its space
// and what it asks for; Allow asks for a fresh sign-in check, then hands you back to the app.
import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { CenteredCardLayout } from "../../../components/layouts";
import { ErrorText } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { MemberAuthPanel } from "../MemberAuthPanel";
import { decideConsent, previewConsent } from "./personalApiAccessApi";

export function OAuthConsentPage() {
  const query = useLocation().search.replace(/^\?/, "");
  const preview = useQuery({ queryKey: ["oauth-consent", query], queryFn: () => previewConsent(query), retry: false });
  const decide = useMutation({
    mutationFn: (allow: boolean) => decideConsent(query, allow),
    onSuccess: (result) => { window.location.assign(result.redirect_to); },
  });
  if (preview.error instanceof StructuredApiError && preview.error.status === 401) {
    return <MemberAuthPanel onAuthenticated={() => { void preview.refetch(); }} />;
  }
  const app = preview.data;
  return <CenteredCardLayout media={{ icon: "KeyRound", tone: "accent" }} eyebrow={t`Connect an app`}
    title={app ? t`${app.app_name} wants to act as you` : t`Connect an app`}
    state={preview.isLoading ? { status: "loading" } : { status: "ready" }}
    body={app ? `Registered by ${app.space_name}. It can do only what you could do yourself, and you can disconnect it any time under API access.`
      : "This app request could not be read. Go back to the app and try again."}
    content={<>
      {app ? <ul className="grid gap-2">{app.scopes.map((scope) => <li key={scope.value} className="grid">
        <span className="font-semibold text-ink">{scope.label}</span>
        <span className="text-xs text-muted">{scope.description}</span></li>)}</ul> : null}
      {app ? <p className="mt-3 text-xs text-muted [overflow-wrap:anywhere]">{t`You will return to ${app.redirect_uri}`}</p> : null}
      {preview.error && !(preview.error instanceof StructuredApiError && preview.error.status === 401)
        ? <ErrorText message={preview.error.message} /> : null}
      {decide.error ? <ErrorText message={decide.error.message} /> : null}
    </>}
    primary={{ label: t`Allow`, onClick: () => decide.mutate(true), pending: decide.isPending, pendingLabel: "Connecting…",
      disabled: !app, disabledReason: "The app request is not valid." }}
    escape={app ? { label: t`Deny`, onClick: () => decide.mutate(false) } : undefined} />;
}
