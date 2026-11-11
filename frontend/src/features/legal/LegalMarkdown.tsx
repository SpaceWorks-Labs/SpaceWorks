import { t } from "@lingui/core/macro";
import { ExternalLink } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";
import Markdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";
import "../docs/docs.css";

/**
 * Operator- or space-written Markdown on /privacy and /terms, through the same renderer the docs use
 * (react-markdown + GFM, `sw-doc-prose`). Raw HTML is never rendered (react-markdown's default) and
 * unsafe URL schemes are stripped by its URL transform. Links: a site path stays in the app, anything
 * else opens in a new tab.
 */
const heading = (Tag: "h2" | "h3" | "h4") => ({ children }: ComponentPropsWithoutRef<"h2">) =>
  <Tag className="sw-doc-heading">{children}</Tag>;

const components: Components = {
  h1: heading("h2"), h2: heading("h2"), h3: heading("h3"), h4: heading("h4"), h5: heading("h4"), h6: heading("h4"),
  a({ href = "", children }) {
    if (href.startsWith("/") && !href.startsWith("//")) return <Link to={href}>{children}</Link>;
    if (href.startsWith("#")) return <a href={href}>{children}</a>;
    return <a href={href} target="_blank" rel="noreferrer noopener">{children}
      <ExternalLink size={12} className="sw-doc-external" aria-hidden="true" /><span className="sr-only">{t`(opens in a new tab)`}</span></a>;
  },
  // Images are not part of a legal page; an alt text stands in so nothing loads from a third party.
  img({ alt }) { return alt ? <span>{alt}</span> : null; },
  table({ children }) {
    return <div className="sw-doc-table" tabIndex={0} role="region" aria-label={t`Table`}><table>{children}</table></div>;
  },
};

/** Splits a leading `# Title` off the body, so the page shows one heading, not two. */
export function splitTitle(markdown: string): { title: string | null; body: string } {
  const match = /^\s*#\s+(.+?)\s*(?:\n|$)/.exec(markdown);
  return match ? { title: match[1], body: markdown.slice(match[0].length) } : { title: null, body: markdown };
}

export function LegalMarkdown({ body }: { body: string }) {
  return <div className="sw-doc-prose"><Markdown remarkPlugins={[remarkGfm]} components={components}>{body}</Markdown></div>;
}
