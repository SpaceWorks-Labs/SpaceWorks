import { Field } from "../../components/ui";

/** Phone replacement for the settings section strip: one native select instead of a scrolling chip row. */
export function SettingsSectionJump({ sections }: { sections: { id: string; title: string }[] }) {
  return <div className="w-full md:hidden">
    <Field label="Jump to section">
      <select className="desk-input w-full" value="" onChange={event => {
        const target = document.getElementById(event.target.value);
        target?.scrollIntoView({ block: "start" });
        target?.focus({ preventScroll: true });
      }}>
        <option value="" disabled>Choose a section</option>
        {sections.map(section => <option key={section.id} value={section.id}>{section.title}</option>)}
      </select>
    </Field>
  </div>;
}
