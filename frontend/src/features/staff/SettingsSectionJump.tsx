import { Field } from "../../components/ui";

/** Wrap a SettingsLayout with this so its chip strip yields to SettingsSectionJump below md. */
export const PHONE_HIDES_SETTINGS_NAV = "max-md:[&_.sw-settings-nav]:hidden";

/** Phone replacement for the settings section strip: one native select instead of a scrolling chip row.
 *  Mirrors SettingsLayout, which only shows its strip from five sections up. */
export function SettingsSectionJump({ sections }: { sections: { id: string; title?: string }[] }) {
  if (sections.length < 5) return null;
  return <div className="w-full md:hidden">
    <Field label="Jump to section">
      <select className="desk-input w-full" value="" onChange={event => {
        const target = document.getElementById(event.target.value);
        target?.scrollIntoView({ block: "start" });
        target?.focus({ preventScroll: true });
      }}>
        <option value="" disabled>Choose a section</option>
        {sections.map(section => <option key={section.id} value={section.id}>{section.title ?? section.id}</option>)}
      </select>
    </Field>
  </div>;
}
