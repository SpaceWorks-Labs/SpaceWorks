import { useEffect, useState } from "react";

export function SettingsNav({ sections }: { sections: { id: string; title?: string }[] }) {
  const [active, setActive] = useState(sections[0]?.id);
  useEffect(() => {
    if (!window.IntersectionObserver) return;
    const observer = new IntersectionObserver(entries => {
      const first = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (first) setActive(first.target.id);
    }, { rootMargin: "-10% 0px -65% 0px" });
    sections.forEach(section => { const element = document.getElementById(section.id); if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [sections]);
  return <nav aria-label="Settings sections" className="sw-settings-nav flex min-w-0 gap-2 overflow-x-auto pb-2 xl:flex-col">
    {sections.map(section => <a key={section.id} href={`#${section.id}`} onClick={() => setActive(section.id)}
      aria-current={active === section.id ? "location" : undefined}
      className={`desk-button shrink-0 justify-start ${active === section.id ? "border-accent bg-accent-soft text-accent-ink" : ""}`}>
      {section.title ?? section.id}</a>)}
  </nav>;
}
