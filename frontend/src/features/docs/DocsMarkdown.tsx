import { t } from "@lingui/core/macro";
import { CircleAlert, Info, Lightbulb, OctagonAlert, TriangleAlert, ExternalLink, Link2 } from "lucide-react";
import { useEffect, type ComponentPropsWithoutRef, type ReactNode } from "react";
import Markdown, { type Components, type ExtraProps } from "react-markdown";
import { Link } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { CodeBlock, CodeTabs, type CodeTab } from "./DocsCode";
import { resolveDocLink } from "./docsLinks";
import type { DocEntry } from "./docsTypes";
import { remarkDocs, type CalloutKind } from "./remarkDocs";

// hast types come from react-markdown itself: the app has an older, incompatible @types/hast at the top level.
type Element = NonNullable<ExtraProps["node"]>;
type ElementContent = Element["children"][number];

const hastText = (node: ElementContent): string =>
  node.type === "text" ? node.value : "children" in node ? node.children.map(hastText).join("") : "";

/** The language and source of a `<pre><code class="language-x">` hast node. */
function codeOf(pre: Element | undefined): CodeTab | null {
  const code = pre?.children.find((child): child is Element => child.type === "element" && child.tagName === "code");
  if (!code) return null;
  const classes = ([] as unknown[]).concat(code.properties?.className ?? []).map(String);
  const language = classes.find(name => name.startsWith("language-"))?.slice("language-".length) ?? "";
  const meta = String((code.data as { meta?: string } | undefined)?.meta ?? "");
  const title = /title="([^"]+)"/.exec(meta)?.[1];
  return { language, title, code: hastText(code).replace(/\n$/, "") };
}

const CALLOUTS: Record<CalloutKind, { icon: typeof Info; label: () => string }> = {
  note: { icon: Info, label: () => t`Note` },
  tip: { icon: Lightbulb, label: () => t`Tip` },
  important: { icon: CircleAlert, label: () => t`Important` },
  warning: { icon: TriangleAlert, label: () => t`Warning` },
  caution: { icon: OctagonAlert, label: () => t`Caution` },
};

function Heading({ level, id, children }: { level: 2 | 3 | 4 | 5 | 6; id?: string; children: ReactNode }) {
  const Tag = `h${level}` as const;
  return <Tag id={id} className="sw-doc-heading">
    {children}
    {id ? <a href={`#${id}`} className="sw-doc-anchor" aria-label={t`Link to this section`}><Link2 size={16} aria-hidden="true" /></a> : null}
  </Tag>;
}

function components(source: string, index: readonly DocEntry[]): Components {
  const heading = (level: 2 | 3 | 4 | 5 | 6) => ({ id, children }: ComponentPropsWithoutRef<"h2">) =>
    <Heading level={level} id={id}>{children}</Heading>;
  return {
    // The page prints the document title itself; any further h1 in a body reads as a section.
    h1: heading(2), h2: heading(2), h3: heading(3), h4: heading(4), h5: heading(5), h6: heading(6),
    a({ href = "", children }) {
      const target = resolveDocLink(href, source, index);
      if (target.kind === "internal") return <Link to={target.to}>{children}</Link>;
      if (target.kind === "anchor") return <a href={`#${target.hash}`}>{children}</a>;
      return <a href={target.href} target="_blank" rel="noreferrer noopener">{children}
        <ExternalLink size={12} className="sw-doc-external" aria-hidden="true" /><span className="sr-only">{t`(opens in a new tab)`}</span></a>;
    },
    img({ src = "", alt = "" }) {
      const target = typeof src === "string" ? resolveDocLink(src, source, index) : null;
      const url = target?.kind === "external" ? target.href : target?.kind === "internal" ? target.to : src;
      return <img src={String(url)} alt={alt} loading="lazy" className="sw-doc-image" />;
    },
    pre({ node }) {
      const code = codeOf(node);
      return code ? <CodeBlock language={code.language} code={code.code} /> : <pre className="sw-doc-pre" />;
    },
    div({ node, children, ...rest }) {
      if (node?.properties && "dataCodeTabs" in node.properties) {
        const tabs = node.children.flatMap(child => child.type === "element" && child.tagName === "pre" ? [codeOf(child)] : [])
          .filter((tab): tab is CodeTab => Boolean(tab));
        return <CodeTabs tabs={tabs} />;
      }
      return <div {...rest}>{children}</div>;
    },
    blockquote({ node, children }) {
      const kind = node?.properties?.dataCallout as CalloutKind | undefined;
      if (!kind || !CALLOUTS[kind]) return <blockquote>{children}</blockquote>;
      const { icon: Icon, label } = CALLOUTS[kind];
      return <aside className="sw-doc-callout" data-kind={kind} aria-label={label()}>
        <p className="sw-doc-callout-title"><Icon size={18} aria-hidden="true" />{label()}</p>
        <div className="sw-doc-callout-body">{children}</div>
      </aside>;
    },
    table({ children }) {
      return <div className="sw-doc-table" tabIndex={0} role="region" aria-label={t`Table`}><table>{children}</table></div>;
    },
  };
}

/** Repository Markdown as React elements. Raw HTML in a page is not rendered (react-markdown's default). */
export function DocsMarkdown({ body, source, index, onRendered }: { body: string; source: string; index: readonly DocEntry[]; onRendered?: () => void }) {
  // Tell the page once the headings exist, so it can scroll to #anchor and start the TOC scroll-spy.
  useEffect(() => { onRendered?.(); }, [body, onRendered]);
  return <div className="sw-doc-prose">
    <Markdown remarkPlugins={[remarkGfm, remarkDocs]} components={components(source, index)}>{body}</Markdown>
  </div>;
}
