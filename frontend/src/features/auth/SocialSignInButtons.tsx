import { t } from "@lingui/core/macro";
import { MfaFlow } from "./MfaFlow";
import { isMfaChallenge, type MfaChallenge } from "./mfaApi";
import { useEffect, useRef, useState } from "react";

import { publicV1Request } from "../../lib/api";
import { markUsernameReview } from "../profile/username/usernameApi";
import {
  beginOidcBrowser,
  beginGithubBrowser,
  completeOidcBrowserCallback,
  mountGoogleButton,
  signInWithApple,
  type SocialConfig,
  type SocialLoginResult,
  type SocialSurface,
} from "./socialSdk";
import { BoxArt } from "../../components/BoxSpinner";

export function SocialSignInButtons({
  surface,
  onSuccess,
  email = "",
  makerspaceSlug = "",
  onMfaChallenge,
}: {
  surface: SocialSurface;
  onSuccess: (result: SocialLoginResult) => void;
  email?: string;
  makerspaceSlug?: string;
  onMfaChallenge?: (challenge: MfaChallenge) => void;
}) {
  const [challenge, setChallenge] = useState<MfaChallenge>();
  const receive = (result: SocialLoginResult | MfaChallenge) => {
    if (isMfaChallenge(result)) { if (onMfaChallenge) onMfaChallenge(result); else setChallenge(result); }
    else { if (result.outcome === "created") markUsernameReview(); onSuccessRef.current(result); }
  };
  const googleHost = useRef<HTMLDivElement>(null);
  const onSuccessRef = useRef(onSuccess);
  const receiveRef = useRef(receive);
  useEffect(() => {
    receiveRef.current = receive;
  });
  const [config, setConfig] = useState<SocialConfig>();
  const [memberAccounts, setMemberAccounts] = useState(true);
  const [error, setError] = useState("");
  const [applePending, setApplePending] = useState(false);
  const [oidcPending, setOidcPending] = useState("");
  const callbackHandled = useRef(false);

  useEffect(() => {
    onSuccessRef.current = onSuccess;
  }, [onSuccess]);

  useEffect(() => {
    publicV1Request<{ social_auth?: SocialConfig; member_accounts?: { enabled: boolean } }>(
      "/config",
    )
      .then((result) => {
        setConfig(result.social_auth ?? {});
        // Present only when member accounts are switched off, so an absent key means
        // on — which is also what a failed request falls back to.
        setMemberAccounts(result.member_accounts?.enabled !== false);
      })
      .catch(() => setConfig({}));
  }, []);

  useEffect(() => {
    if (callbackHandled.current) return;
    callbackHandled.current = true;
    void completeOidcBrowserCallback()
      .then((result) => {
        if (result) receiveRef.current(result);
      })
      .catch((nextError: unknown) => {
        setError(nextError instanceof Error ? nextError.message : t`Identity-provider sign-in failed.`);
      });
  }, [surface]);

  useEffect(() => {
    const host = googleHost.current;
    if (!host || !config?.google?.enabled) return;
    host.replaceChildren();
    void mountGoogleButton(
      host,
      config.google.web_client_id,
      surface,
      (result) => receiveRef.current(result),
      (nextError) => setError(nextError.message),
    ).catch((nextError: unknown) => {
      setError(nextError instanceof Error ? nextError.message : t`Google sign-in failed.`);
    });
  }, [config, surface]);

  const oidcProviders = Object.entries(config ?? {}).filter(
        (entry): entry is [string, NonNullable<SocialConfig[`oidc:${string}`]>] =>
          entry[0].startsWith("oidc:") && typeof entry[1] === "object" && Boolean(entry[1]?.enabled),
      );
  // Accounts-off hides only the built-in consumer ecosystem. Institution-owned OIDC
  // is the member login path that must remain available; staff still keep the built-ins.
  const showBuiltins = surface === "staff" || memberAccounts;
  const showGoogle = showBuiltins && Boolean(config?.google?.enabled);
  const showApple = showBuiltins && Boolean(config?.apple?.enabled);
  const showGithub = surface === "member" && memberAccounts && config?.github === true;
  if (challenge) return <MfaFlow challenge={challenge} onCancel={() => setChallenge(undefined)}
    onComplete={(result) => { setChallenge(undefined); onSuccessRef.current({ access: result.access, user: result.user as unknown as Record<string, unknown>, outcome: "existing" }); }} />;
  if (!showGoogle && !showApple && !showGithub && oidcProviders.length === 0) return null;
  return (
    <section aria-label={t`Social sign in`}>
      <div className="flex flex-col items-center gap-3">
        {showGoogle ? <div ref={googleHost} className="min-h-10 w-full text-center" /> : null}
        {showGithub ? (
          <button className="desk-button w-full max-w-[360px]" type="button"
            disabled={Boolean(oidcPending)} onClick={async () => {
              setOidcPending("github");
              setError("");
              try { await beginGithubBrowser(); }
              catch (nextError) {
                setOidcPending("");
                setError(nextError instanceof Error ? nextError.message : t`GitHub sign-in failed.`);
              }
            }}>
            {oidcPending === "github" ? t`Connecting to GitHub…` : t`Continue with GitHub`}
          </button>
        ) : null}
        {showApple ? (
          <button
            className="desk-button w-full max-w-[360px]"
            type="button"
            disabled={applePending}
            onClick={async () => {
              setApplePending(true);
              setError("");
              try {
                receive(await signInWithApple(config?.apple?.service_id ?? "", surface));
              } catch (nextError) {
                setError(nextError instanceof Error ? nextError.message : t`Apple sign-in failed.`);
              } finally {
                setApplePending(false);
              }
            }}
          >
            {applePending ? <><BoxArt size={16} mono />{t`Connecting to Apple…`}</> : t`Continue with Apple`}
          </button>
        ) : null}
        {oidcProviders.map(([key, provider]) => {
          const slug = key.slice("oidc:".length);
          return (
            <button
              key={key}
              className="desk-button w-full max-w-[360px]"
              type="button"
              disabled={Boolean(oidcPending)}
              onClick={async () => {
                setOidcPending(key);
                setError("");
                try {
                  await beginOidcBrowser(slug, email, makerspaceSlug, surface);
                } catch (nextError) {
                  setOidcPending("");
                  setError(nextError instanceof Error ? nextError.message : t`Identity-provider sign-in failed.`);
                }
              }}
            >
              {oidcPending === key
                ? t`Connecting to ${provider.display_name}…`
                : t`Continue with ${provider.display_name}`}
            </button>
          );
        })}
      </div>
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}
    </section>
  );
}
