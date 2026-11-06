import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useLayoutMedia } from "./useLayoutMedia";

/** Section jump: a link rail from tablet up, one native select on phones (no sideways-scrolling row). */
export function SettingsNav({ sections }: { sections: { id: string; title?: string }[] }) {
  const [active, setActive] = useState(sections[0]?.id);
  const phone = useLayoutMedia("(max-width: 767px)");
  useEffect(() => {
    if (!window.IntersectionObserver) return;
    const observer = new IntersectionObserver(entries => {
      const first = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (first) setActive(first.target.id);
    }, { rootMargin: "-10% 0px -65% 0px" });
    sections.forEach(section => { const element = document.getElementById(section.id); if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [sections]);
  if (phone) return <nav aria-label={t`Settings sections`} className="sw-settings-nav min-w-0">
    <label className="grid gap-2"><span className="text-sm font-semibold text-ink">{t`Jump to section`}</span>
      <select className="desk-input w-full" value={active} onChange={event => {
        const id = event.target.value;
        setActive(id);
        const target = document.getElementById(id);
        target?.scrollIntoView?.({ block: "start" });
        target?.focus({ preventScroll: true });
      }}>
        {sections.map(section => <option key={section.id} value={section.id}>{section.title ?? section.id}</option>)}
      </select>
    </label>
  </nav>;
  return <nav aria-label={t`Settings sections`} className="sw-settings-nav flex min-w-0 gap-2 overflow-x-auto pb-2 xl:flex-col">
    {sections.map(section => <a key={section.id} href={`#${section.id}`} onClick={() => setActive(section.id)}
      aria-current={active === section.id ? "location" : undefined}
      className={`flex min-h-11 shrink-0 items-center rounded-control px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${active === section.id ? "bg-hover text-ink" : "text-muted hover:bg-hover hover:text-ink"}`}>
      {section.title ?? section.id}</a>)}
  </nav>;
}
