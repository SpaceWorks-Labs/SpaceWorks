import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { publicV1Request } from "../../lib/api";
import { isRetryable } from "../../lib/api/errors";

/**
 * Landing page for an email unsubscribe link (`/unsubscribe/:token`). The signed token is the
 * authority, so no sign-in is needed. Opening the page changes nothing: mail scanners prefetch
 * links, so the opt-out is sent only when the person presses the button (RFC 8058 one-click body).
 */
export function UnsubscribePage() {
  const { token = "" } = useParams();
  const unsubscribe = useMutation({
    mutationFn: () => publicV1Request<{ detail: string }>(`/notifications/unsubscribe/${encodeURIComponent(token)}`, {
      method: "POST", body: JSON.stringify({ "List-Unsubscribe": "One-Click" }),
    }),
  });
  const done = unsubscribe.isSuccess;
  // Only a server-side failure (5xx, 429 or no response) is worth retrying. A bad or expired token (400) or a
  // switched-off feature (typed 404) will never succeed, so it gets the "link didn't work" copy and a way out.
  const error = unsubscribe.error;
  const retryable = unsubscribe.isError && isRetryable(error);
  const invalid = unsubscribe.isError && !retryable;
  return <CenteredCardLayout width={480} state={{ status: "ready" }}
    media={{ banner: done ? "success" : unsubscribe.isError ? "danger" : "accent" }} eyebrow={t`Email preferences`}
    title={done ? t`You're unsubscribed` : unsubscribe.isError ? invalid ? t`This link didn't work` : t`Email preferences could not be updated` : t`Stop these emails?`}
    body={done ? unsubscribe.data.detail || t`Optional emails of this kind are off. Safety and account emails still arrive.`
      : unsubscribe.isError ? retryable ? unsubscribe.error.message : t`The link may have expired or this space no longer offers email choices. You can change email settings from your account instead.`
        : t`You'll stop getting optional emails of this kind from this makerspace. Safety and account emails still arrive.`}
    primary={done ? { label: t`Go to Space Works`, href: "/" }
      : invalid ? { label: t`Go to Space Works`, href: "/" }
      : retryable ? { label: t`Retry`, onClick: () => unsubscribe.mutate() }
      : { label: t`Unsubscribe`, pending: unsubscribe.isPending, onClick: () => unsubscribe.mutate() }}
    escape={done || invalid ? undefined : retryable ? { label: t`Go to Space Works`, href: "/" } : { label: t`Keep getting them`, href: "/" }} />;
}
