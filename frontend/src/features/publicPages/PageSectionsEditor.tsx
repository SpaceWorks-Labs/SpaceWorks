import { useRef, useState } from "react";
import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import { pageInput, pageLabel, newSection, sectionLabels } from "./documentDefaults";
import { PageSectionForm } from "./PageSectionForm";
import type { PageAsset, PageDocument, PageOwner, SectionType } from "./pageTypes";

export function PageSectionsEditor({ document, assets, allowed, required, maxSections = 20, kind, disabled, onChange }: {
  document: PageDocument; assets: PageAsset[]; allowed: SectionType[]; required: SectionType[]; maxSections?: number;
  kind: PageOwner["kind"] | "event"; disabled: boolean; onChange: (document: PageDocument) => void;
}) {
  const refs = useRef(new Map<string, HTMLHeadingElement>());
  const addRef = useRef<HTMLButtonElement>(null);
  const [adding, setAdding] = useState<SectionType | "">("");
  const [announcement, announce] = useState("");
  const focus = (id?: string) => requestAnimationFrame(() => id ? refs.current.get(id)?.focus() : addRef.current?.focus());
  function move(index: number, offset: number) {
    const sections = [...document.sections];
    const section = sections[index];
    [sections[index], sections[index + offset]] = [sections[index + offset], sections[index]];
    onChange({ ...document, sections }); focus(section.id);
    announce(`${sectionLabels[section.type] ?? "Section"} moved to position ${index + offset + 1} of ${sections.length}.`);
  }
  return <section aria-label="Page sections" className="grid min-w-0 gap-4">
    <h3 className="title-section">Sections</h3>
    <p className="text-sm text-muted">Move sections into reading order. Required groups stay enabled and cannot be removed.</p>
    <p role="status" aria-live="polite" className="sr-only">{announcement}</p>
    <ol className="grid min-w-0 gap-4">{document.sections.map((section, index) => {
      const supported = Boolean(sectionLabels[section.type]);
      const mandatory = required.includes(section.type);
      return <li key={section.id} className="grid min-w-0 gap-4 rounded-xl border border-line bg-panel p-4">
        <h4 className="title-section rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" tabIndex={-1} ref={node => { if (node) refs.current.set(section.id, node); else refs.current.delete(section.id); }}>{index + 1}. {sectionLabels[section.type] ?? "Section supported by a newer editor"}</h4>
        <div className="flex flex-wrap items-center gap-2">
          <label className="mr-auto flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={section.enabled} disabled={disabled || mandatory || !supported} onChange={e => onChange({ ...document, sections: document.sections.map(row => row.id === section.id ? { ...row, enabled: e.target.checked } : row) })} />{mandatory ? "Required" : "Enabled"}</label>
          <button className="desk-button" type="button" disabled={disabled || index === 0} aria-label={`Move ${sectionLabels[section.type] ?? "section"} up`} onClick={() => move(index, -1)}><ArrowUp size={20} aria-hidden="true" />Up</button>
          <button className="desk-button" type="button" disabled={disabled || index === document.sections.length - 1} aria-label={`Move ${sectionLabels[section.type] ?? "section"} down`} onClick={() => move(index, 1)}><ArrowDown size={20} aria-hidden="true" />Down</button>
          <button className="desk-button-danger-outline" type="button" disabled={disabled || mandatory || !supported} aria-label={`Remove ${sectionLabels[section.type] ?? "section"}`} onClick={() => {
            const next = document.sections.filter(row => row.id !== section.id); onChange({ ...document, sections: next }); focus(next[Math.min(index, next.length - 1)]?.id);
            announce(`${sectionLabels[section.type]} removed. ${next.length} sections remain.`);
          }}><Trash2 size={20} aria-hidden="true" />Remove</button>
        </div>
        {supported ? <fieldset className="min-w-0" disabled={disabled}><legend className="sr-only">Edit {sectionLabels[section.type]}</legend>
          <PageSectionForm section={section} assets={assets} kind={kind} onChange={changed => onChange({ ...document, sections: document.sections.map(row => row.id === section.id ? changed : row) })} />
        </fieldset> : <p className="text-sm text-muted">This section is preserved when you save. Use a newer editor to change its fields.</p>}
      </li>;
    })}</ol>
    <div className="flex flex-wrap items-end gap-3">
      <label className={`${pageLabel} flex-1`}>New section<select className={pageInput} value={adding} disabled={disabled} onChange={e => setAdding(e.target.value as SectionType)}><option value="">Choose a section</option>
        {allowed.filter(type => sectionLabels[type] && document.sections.filter(row => row.type === type).length < (type === "about" ? 2 : 1)).map(type => <option key={type} value={type}>{sectionLabels[type]}</option>)}
      </select></label>
      <button ref={addRef} className="desk-button" type="button" disabled={disabled || !adding || document.sections.length >= Math.min(20, maxSections)} onClick={() => {
        if (!adding) return; const section = newSection(adding); onChange({ ...document, sections: [...document.sections, section] }); setAdding(""); focus(section.id); announce(`${sectionLabels[section.type]} added at position ${document.sections.length + 1}.`);
      }}>Add section</button>
    </div>
  </section>;
}
