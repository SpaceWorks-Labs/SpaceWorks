import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { CenteredCardLayout } from "../../components/layouts";

export function CanonicalPageRedirect({ url }: { url: string }) {
  useEffect(() => { window.location.replace(url); }, [url]);
  return <CenteredCardLayout state={{ status: "ready" }} title={t`This page has moved`} body={t`Opening the current public address.`} primary={{ label: t`Open current page`, href: url }} />;
}
