import { useEffect } from "react";
import { CenteredCardLayout } from "../../components/layouts";

export function CanonicalPageRedirect({ url }: { url: string }) {
  useEffect(() => { window.location.replace(url); }, [url]);
  return <CenteredCardLayout state={{ status: "ready" }} title="This page has moved" body="Opening the current public address." primary={{ label: "Open current page", href: url }} />;
}
