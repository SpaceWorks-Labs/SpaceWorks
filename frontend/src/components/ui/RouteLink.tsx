import type { AnchorHTMLAttributes } from "react";
import { Link, useInRouterContext } from "react-router-dom";

/**
 * An in-app link that navigates client-side (no full reload and no "Opening makerspace…" flash)
 * when rendered inside the router, and degrades to a plain anchor outside it (isolated tests,
 * embeds). External links, hash links, new-tab links and disabled links (no href) stay plain anchors.
 */
export function RouteLink({ href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  const inRouter = useInRouterContext();
  const internal = href !== undefined && href.startsWith("/") && !href.startsWith("//") && props.target !== "_blank";
  return inRouter && internal ? <Link to={href} {...props} /> : <a href={href} {...props} />;
}
