// /member/cards/accept?invite=…&card=… — link an emailed programme invite to this account.
// The server checks the invite against the account's verified email.
import { t } from "@lingui/core/macro";
import { useSearchParams } from "react-router-dom";

import { CenteredCardLayout } from "../../../components/layouts";
import { ErrorText } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { MemberAuthPanel } from "../MemberAuthPanel";
import { useAcceptInvite, useMemberIdentity } from "./api";

export function InviteAcceptPage() {
  const [params] = useSearchParams();
  const invite = params.get("invite") ?? "";
  const card = Number(params.get("card") ?? 0);
  const { restoring, identity } = useMemberIdentity();
  const accept = useAcceptInvite();
  const status = identity.error instanceof StructuredApiError ? identity.error.status : undefined;
  if (status === 401) return <MemberAuthPanel onAuthenticated={() => { void identity.refetch(); }} />;
  const valid = Boolean(invite) && card > 0;
  return <CenteredCardLayout title={accept.isSuccess ? t`Invite accepted` : t`Accept your ID card invite`}
    state={restoring || identity.isLoading ? { status: "loading" } : { status: "ready" }}
    body={accept.isSuccess ? (accept.data.status === "approved" ? t`Your card is ready in My cards.`
      : t`You're on the list. Your card appears in My cards once it's approved.`)
      : valid ? t`This links the card to the account you're signed in with. Use the account whose email received the invite.`
        : t`This invite link is incomplete. Open the link from your email again.`}
    content={accept.error ? <ErrorText message={accept.error.message} /> : undefined}
    primary={accept.isSuccess ? { label: t`Open My cards`, href: "/member/cards" }
      : { label: t`Accept the invite`, onClick: () => accept.mutate({ card, invite }), pending: accept.isPending,
        pendingLabel: "Accepting…", disabled: !valid, disabledReason: "The invite link is incomplete." }} />;
}
