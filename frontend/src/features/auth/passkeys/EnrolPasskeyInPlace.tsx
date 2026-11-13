import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Fingerprint } from "lucide-react";

import { ErrorText } from "../../../components/ui";
import { setAccessToken } from "../../../lib/api";
import { authErrorMessage } from "../../../lib/api/authErrorCopy";
import { MfaRecoveryCodes } from "../MfaRecoveryCodes";
import { invalidateAccountSecurity } from "../securityQueries";
import { registerPasskey } from "./passkeyApi";
import { isPasskeyCancelled } from "./webauthn";
import { BoxArt } from "../../../components/BoxSpinner";

/**
 * Add a passkey right where a signed-in person is asked for two-step sign-in (S-D follow-up; GAP2).
 * Needs the session's recent re-authentication, which the shared client asks for. Any first
 * recovery codes are shown here and the session is refreshed only once they are saved, so the
 * screen that asked cannot vanish with them.
 */
export function EnrolPasskeyInPlace() {
  const client = useQueryClient();
  const [codes, setCodes] = useState<string[]>();
  const add = useMutation({ mutationFn: () => registerPasskey(""), onSuccess: result => {
    setAccessToken(result.access);
    if (result.recovery_codes?.length) setCodes(result.recovery_codes);
    else void invalidateAccountSecurity(client);
  } });
  if (codes) return <div className="grid gap-3">
    <p role="status" className="text-sm text-ink">{t`Passkey added. Save these recovery codes: each works once if you lose your device.`}</p>
    <MfaRecoveryCodes codes={codes} />
    <div><button type="button" className="desk-button-primary min-h-11"
      onClick={() => { setCodes(undefined); void invalidateAccountSecurity(client); }}>{t`I've saved my codes`}</button></div>
  </div>;
  return <div className="grid gap-2">
    <div><button type="button" className="desk-button-primary min-h-11 gap-2" disabled={add.isPending} aria-busy={add.isPending || undefined}
      onClick={() => add.mutate()}><Fingerprint aria-hidden="true" size={20} />{add.isPending ? <><BoxArt size={16} mono />{t`Waiting for your device…`}</> : t`Add a passkey now`}</button></div>
    {add.error && !isPasskeyCancelled(add.error) ? <ErrorText message={authErrorMessage(add.error, "Couldn't add a passkey. Try again, or set up an authenticator app.")} /> : null}
  </div>;
}
