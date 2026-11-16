import { t } from "@lingui/core/macro";
import { useState } from "react";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { SpecEditor } from "./SpecEditor";
import { sectionOfMessage, validateSpec } from "./specValidate";
import type { TemplateInput, TypeTemplate } from "./templatesApi";

const keyFrom = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^[^a-z]+|_+$/g, "").slice(0, 50);

/** Edit or copy one template: its details and its whole spec, section by section. A server refusal is shown under the section it names. */
export function TemplateForm({ source, copy, saving, error, onSave, onCancel }: {
  source: TypeTemplate; copy: boolean; saving: boolean; error?: string; onSave: (body: TemplateInput) => void; onCancel: () => void;
}) {
  const [name, setName] = useState(copy ? `${source.name} ${t`copy`}` : source.name);
  const [description, setDescription] = useState(source.description);
  const [category, setCategory] = useState(source.category);
  const [icon, setIcon] = useState(source.icon);
  const [active, setActive] = useState(source.is_active);
  const [spec, setSpec] = useState(source.spec);
  const key = copy ? keyFrom(name) : source.key;
  const problems = validateSpec(spec);
  const blocked = Object.keys(problems).length > 0;
  const serverSection = sectionOfMessage(error);
  const save = () => { if (!blocked) onSave({ key, name: name.trim(), description: description.trim(), category: category.trim(), icon: icon.trim(), spec, is_active: active }); };
  // A div, not a form: the consumable row editor inside is a form of its own and a nested submit would save the whole template.
  return <div className="grid gap-3 rounded-xl border border-line bg-bg p-3">
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="grid gap-1 text-sm">{t`Name`}<input className="desk-input" value={name} maxLength={100} required onChange={event => setName(event.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Category`}<input className="desk-input" value={category} maxLength={60} onChange={event => setCategory(event.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Icon`}<input className="desk-input" value={icon} maxLength={40} onChange={event => setIcon(event.target.value)} /></label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} />{t`Offer this template in the wizard`}</label>
      <label className="grid gap-1 text-sm sm:col-span-2">{t`Description`}<textarea className="desk-input min-h-20" value={description} onChange={event => setDescription(event.target.value)} /></label>
    </div>
    <SpecEditor spec={spec} onChange={setSpec} problems={problems} serverSection={serverSection} serverText={error} />
    <p className="text-xs text-muted">{copy ? t`The copy starts with the same settings and can be changed above.` : t`Machine types already created from this template are not changed.`}</p>
    {error && !serverSection ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <div className="flex flex-wrap justify-end gap-2"><button type="button" className="desk-button-ghost min-h-11" onClick={onCancel}>{t`Cancel`}</button>
      <button type="button" className="desk-button-primary min-h-11" disabled={saving || blocked || !name.trim() || !key} onClick={save}>{saving ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save template`}</button></div>
  </div>;
}
