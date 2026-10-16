import { useLocation } from "react-router-dom";
import { CenteredCardLayout } from "../components/layouts";

/** The one not-found page. Unknown routes and unpublished profiles render it identically. */
export function NotFoundPage() {
  const { pathname } = useLocation();
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Compass", tone: "accent" }}
    eyebrow="404" title="We couldn't find that page" body="The link may be old, or the page moved."
    primary={{ label: "Go to home", href: "/" }}
    escape={pathname.startsWith("/admin") ? { label: "Staff sign-in", href: "/admin" } : undefined} />;
}
