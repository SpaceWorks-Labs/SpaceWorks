import { Fragment } from "react";
import { Info } from "lucide-react";
import { RouteLink } from "../../components/ui/RouteLink";
import { parseHelpBlocks, parseHelpInline } from "./helpMarkdown";
import { HELP_SCREENSHOTS } from "./helpScreenshots";

const LINK = "rounded-control font-semibold text-accent-ink underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

function Inline({ text, hrefFor }: { text: string; hrefFor: (target: string) => string }) {
  return <>{parseHelpInline(text).map((part, index) => {
    if (part.kind === "strong") return <strong key={index} className="font-bold text-ink">{part.text}</strong>;
    if (part.kind === "code") return <code key={index} className="code-text rounded-md border border-line bg-surface px-1.5 py-0.5 text-ink">{part.text}</code>;
    if (part.kind === "article") return <RouteLink key={index} className={LINK} href={hrefFor(part.target)}>{part.text}</RouteLink>;
    if (part.kind === "external") return <a key={index} className={LINK} href={part.url} target="_blank" rel="noopener noreferrer">{part.text} ↗</a>;
    return <Fragment key={index}>{part.text}</Fragment>;
  })}</>;
}

/**
 * Renders an article from the guide's small Markdown vocabulary (see `helpMarkdown.ts`).
 * Only reviewed captures are shown; uncaptured editorial slots remain in the source.
 */
export function HelpArticleBody({ body, hrefFor }: { body: string; hrefFor: (target: string) => string }) {
  return <div className="grid gap-5 text-base leading-7 text-ink">
    {parseHelpBlocks(body).map((block, index) => {
      if (block.kind === "heading") {
        return block.level === 2
          ? <h2 key={index} className="title-panel mt-3"><Inline text={block.text} hrefFor={hrefFor} /></h2>
          : <h3 key={index} className="title-section mt-1"><Inline text={block.text} hrefFor={hrefFor} /></h3>;
      }
      if (block.kind === "steps") {
        return <ol key={index} className="grid gap-3">{block.items.map((item, step) => <li key={step} className="flex gap-3">
          <span aria-hidden="true" className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent-ink">{step + 1}</span>
          <span className="min-w-0 pt-0.5 [overflow-wrap:anywhere]"><Inline text={item} hrefFor={hrefFor} /></span>
        </li>)}</ol>;
      }
      if (block.kind === "bullets") {
        return <ul key={index} className="grid list-disc gap-2 pl-6 marker:text-muted">{block.items.map((item, n) => <li key={n} className="[overflow-wrap:anywhere]"><Inline text={item} hrefFor={hrefFor} /></li>)}</ul>;
      }
      if (block.kind === "note") {
        return <aside key={index} className="flex gap-3 rounded-2xl border border-line bg-surface p-4 text-sm leading-6">
          <Info aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-accent-ink" />
          <p className="min-w-0 [overflow-wrap:anywhere]"><Inline text={block.text} hrefFor={hrefFor} /></p>
        </aside>;
      }
      if (block.kind === "screenshot") {
        const image = HELP_SCREENSHOTS[block.key];
        if (!image) return null;
        return <figure key={index} data-screenshot={block.key} className="grid gap-2">
          <img src={image.src} width={image.width} height={image.height} alt={block.alt} loading="lazy" decoding="async" className="h-auto w-full rounded-2xl border border-line" />
          <figcaption className="text-sm text-muted">{block.alt}</figcaption>
        </figure>;
      }
      return <p key={index} className="[overflow-wrap:anywhere]"><Inline text={block.text} hrefFor={hrefFor} /></p>;
    })}
  </div>;
}
