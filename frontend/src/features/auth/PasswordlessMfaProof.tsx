import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ErrorText } from "../../components/ui";
import { reauthenticationSessionKey, reauthenticationStatus, requestEnrollmentEmail } from "./reauthenticationApi";
import { reauthenticateSocial } from "./reauthenticationSocial";

export function PasswordlessMfaProof() {
  const status = useQuery({ queryKey: reauthenticationSessionKey(), queryFn: reauthenticationStatus, retry: false });
  const social = useMutation({ mutationFn: reauthenticateSocial });
  const email = useMutation({ mutationFn: requestEnrollmentEmail });
  const error = status.error || social.error || email.error;
  const busy = social.isPending || email.isPending;
  return <section className="grid gap-3" aria-label={t`Verify enrollment`}>
    <p className="text-sm text-muted">{t`Verify a freshly entered linked identity-provider credential, or confirm the emailed one-time link in this browser before enrolling.`}</p>
    <p className="text-sm text-muted">{t`Google and Apple accounts use the email confirmation option to enroll an authenticator.`}</p>
    {status.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading identity providers...`}</p> : null}
    <div className="grid gap-2">
      {status.data?.providers.map((provider) => <button key={provider} type="button" className="desk-button w-full" disabled={busy} onClick={() => social.mutate(provider)}>{t`Verify with ${provider}`}</button>)}
      <button type="button" className="desk-button w-full" disabled={busy} onClick={() => email.mutate()}>{t`Email enrollment confirmation`}</button>
    </div>
    {social.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Identity verified. You can enroll an authenticator now.`}</p> : null}
    {email.isSuccess ? <p role="status" className="text-sm text-ink">{t`Open the confirmation link in this browser within 15 minutes, then return here to enroll.`}</p> : null}
    {error ? <ErrorText message={error.message} /> : null}
  </section>;
}
