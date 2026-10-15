import { useMutation, useQuery } from "@tanstack/react-query";
import { reauthenticationSessionKey, reauthenticationStatus, requestEnrollmentEmail } from "./reauthenticationApi";
import { reauthenticateSocial } from "./reauthenticationSocial";

export function PasswordlessMfaProof() {
  const status = useQuery({ queryKey: reauthenticationSessionKey(), queryFn: reauthenticationStatus, retry: false });
  const social = useMutation({ mutationFn: reauthenticateSocial });
  const email = useMutation({ mutationFn: requestEnrollmentEmail });
  const error = status.error || social.error || email.error;
  return <section className="grid gap-3" aria-label="Verify enrollment">
    <p>Verify a freshly entered linked identity-provider credential, or confirm the emailed one-time link in this browser before enrolling.</p>
    <p>Google and Apple accounts use the email confirmation option to enroll an authenticator.</p>
    {status.isLoading ? <p role="status">Loading identity providers...</p> : null}
    {status.data?.providers.map((provider) => <button key={provider} type="button" className="desk-button-secondary" disabled={social.isPending || email.isPending} onClick={() => social.mutate(provider)}>Verify with {provider}</button>)}
    <button type="button" className="desk-button-secondary" disabled={social.isPending || email.isPending} onClick={() => email.mutate()}>Email enrollment confirmation</button>
    {social.isSuccess ? <p role="status">Identity verified. You can enroll an authenticator now.</p> : null}
    {email.isSuccess ? <p role="status">Open the confirmation link in this browser within 15 minutes, then return here to enroll.</p> : null}
    {error ? <p role="alert" className="text-danger">{error.message}</p> : null}
  </section>;
}
