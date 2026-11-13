import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { publicV1Request } from "../../lib/api";

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
  return <CenteredCardLayout width={480} state={{ status: "ready" }}
    media={{ banner: done ? "success" : unsubscribe.isError ? "danger" : "accent" }} eyebrow={t`Email preferences`}
    title={done ? t`You're unsubscribed` : unsubscribe.isError ? t`This link didn't work` : t`Stop these emails?`}
    body={done ? unsubscribe.data.detail || t`Optional emails of this kind are off. Safety and account emails still arrive.`
      : unsubscribe.isError ? t`The link may have expired or this space no longer offers email choices. You can change email settings from your account instead.`
        : t`You'll stop getting optional emails of this kind from this makerspace. Safety and account emails still arrive.`}
    primary={done || unsubscribe.isError ? { label: t`Go to Space Works`, href: "/" }
      : { label: t`Unsubscribe`, pending: unsubscribe.isPending, onClick: () => unsubscribe.mutate() }}
    escape={done || unsubscribe.isError ? undefined : { label: t`Keep getting them`, href: "/" }} />;
}
