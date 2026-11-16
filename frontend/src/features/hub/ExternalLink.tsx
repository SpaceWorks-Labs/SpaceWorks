import { ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";

/**
 * A link that leaves the app: a new tab, no opener and no referrer, and an accessible name that says
 * where it goes and that it opens a new tab. `label` must start with the visible text (WCAG 2.5.3,
 * label in name), so speech users can say what they see.
 */
export function ExternalLink({ href, label, className, children, iconSize = 16 }:
  { href: string; label: string; className?: string; children: ReactNode; iconSize?: number }) {
  return <a href={href} target="_blank" rel="noopener noreferrer" aria-label={label} className={className}>
    {children}<ArrowUpRight size={iconSize} aria-hidden="true" className="shrink-0" />
  </a>;
}
