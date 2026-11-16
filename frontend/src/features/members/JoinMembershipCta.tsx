import { t } from "@lingui/core/macro";
import type { MembershipPolicyEnum } from "../../generated/api";

export type JoinCtaState = {
  title: string;
  description: string;
  action: "join" | "sign_in" | "none";
  actionLabel?: string;
};

export function joinCtaState(policy: MembershipPolicyEnum, signedIn: boolean): JoinCtaState {
  if (policy === "invite_only") {
    return {
      title: t`Invite-only makerspace`,
      description: t`This makerspace does not accept self-join requests. Ask a space manager for an invitation.`,
      action: "none",
    };
  }
  const instantly = policy === "open";
  return {
    title: t`Join this makerspace`,
    description: instantly ? t`You will become a member immediately.` : t`Your request will be sent to staff for approval.`,
    action: signedIn ? "join" : "sign_in",
    actionLabel: signedIn ? (instantly ? t`Join instantly` : t`Request to join`) : t`Sign in to join`,
  };
}

export function JoinMembershipCta({ policy, signedIn, pending, onJoin, onSignIn }: {
  policy: MembershipPolicyEnum;
  signedIn: boolean;
  pending: boolean;
  onJoin: () => void;
  onSignIn: () => void;
}) {
  const state = joinCtaState(policy, signedIn);
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{state.title}</h2>
    <p className="mt-1 text-sm text-muted">{state.description}</p>
    {state.action !== "none" ? <button className="desk-button-brand mt-4 w-full sm:w-fit" type="button" disabled={pending} onClick={state.action === "join" ? onJoin : onSignIn}>
      {pending && state.action === "join" ? t`Sending…` : state.actionLabel}
    </button> : null}
  </section>;
}
