import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import type { DocHeading } from "./docsTypes";

/** The heading most recently scrolled past the top band of the viewport. */
export function useActiveHeading(ids: string[], ready: boolean) {
  const [active, setActive] = useState<string | null>(ids[0] ?? null);
  useEffect(() => {
    if (!ready || !ids.length || typeof IntersectionObserver === "undefined") return;
    const elements = ids.map(id => document.getElementById(id)).filter((node): node is HTMLElement => Boolean(node));
    const visible = new Map<string, number>();
    const observer = new IntersectionObserver(observed => {
      for (const item of observed) {
        if (item.isIntersecting) visible.set(item.target.id, item.boundingClientRect.top);
        else visible.delete(item.target.id);
      }
      if (visible.size) {
        setActive([...visible.entries()].sort((a, b) => a[1] - b[1])[0][0]);
      } else {
        // Between headings: the last one above the viewport is the section being read.
        const above = elements.filter(node => node.getBoundingClientRect().top < 120);
        if (above.length) setActive(above[above.length - 1].id);
      }
    }, { rootMargin: "-96px 0px -60% 0px", threshold: [0, 1] });
    elements.forEach(node => observer.observe(node));
    return () => observer.disconnect();
  }, [ids, ready]);
  return active;
}

export function DocsToc({ headings, ready }: { headings: DocHeading[]; ready: boolean }) {
  const ids = useMemo(() => headings.map(heading => heading.id), [headings]);
  const active = useActiveHeading(ids, ready);
  if (headings.length < 2) return null;
  return <nav aria-labelledby="docs-toc-title" className="sw-doc-toc">
    <h2 id="docs-toc-title" className="sw-doc-toc-title">{t`On this page`}</h2>
    <ol>
      {headings.map(heading => <li key={heading.id} data-depth={heading.depth}>
        <a href={`#${heading.id}`} aria-current={active === heading.id ? "location" : undefined}>{heading.text}</a>
      </li>)}
    </ol>
  </nav>;
}
