import { useState } from "react";
import type { MessagingCatalogEntry, WhatsAppBindingWrite } from "../messaging/messagingApi";

const catalogKey = (entry: Pick<MessagingCatalogEntry, "feature" | "event" | "audience">) => `${entry.feature}:${entry.event}:${entry.audience}`;

export function WhatsAppBindingForm({ catalog, initial, pending, onSave, onCancel }: {
  catalog: MessagingCatalogEntry[]; initial?: WhatsAppBindingWrite; pending: boolean;
  onSave: (body: WhatsAppBindingWrite) => void; onCancel: () => void;
}) {
  const [selection, setSelection] = useState(initial ? catalogKey(initial) : catalog[0] ? catalogKey(catalog[0]) : "");
  const entry = catalog.find(item => catalogKey(item) === selection);
  const [name, setName] = useState(initial?.template_name ?? "");
  const [language, setLanguage] = useState(initial?.language ?? entry?.supported_languages[0] ?? "");
  const [parameters, setParameters] = useState<string[]>(initial?.parameters ?? []);
  const [active, setActive] = useState(initial?.is_active ?? true);
  const [validation, setValidation] = useState("");
  const move = (index: number, offset: number) => {
    const next = [...parameters];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    setParameters(next);
  };
  return <form className="grid gap-3 rounded-md border border-line p-4" noValidate onSubmit={event => {
    event.preventDefault();
    if (!entry || !/^[a-z0-9_]{1,512}$/.test(name) || !entry.supported_languages.includes(language)
      || parameters.length > 100 || parameters.some(key => !entry.allowed_projection_keys.includes(key))) {
      setValidation("Choose a catalog event, supported language, lowercase template name (letters, numbers, underscores), and allowed BODY variables.");
      return;
    }
    setValidation("");
    onSave({ feature: entry.feature, event: entry.event, audience: entry.audience, template_name: name, language, parameters, is_active: active });
  }}>
    <fieldset disabled={pending} className="grid gap-3">
      <legend className="title-section">{initial ? "Edit template binding" : "New template binding"}</legend>
      <label className="grid gap-1 text-sm font-semibold">Feature / event / audience
        <select className="desk-input" value={selection} onChange={event => {
          const next = catalog.find(item => catalogKey(item) === event.target.value);
          setSelection(event.target.value); setParameters([]); setLanguage(next?.supported_languages.includes(language) ? language : next?.supported_languages[0] ?? "");
        }}>{!entry ? <option value={selection}>Choose a reviewed event</option> : null}
          {catalog.map(item => <option key={catalogKey(item)} value={catalogKey(item)}>{item.feature} / {item.event} / {item.audience}</option>)}
        </select>
      </label>
      <label className="grid gap-1 text-sm font-semibold">Template name<input className="desk-input" value={name} maxLength={512} onChange={event => setName(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold">Template language<select className="desk-input" value={language} onChange={event => setLanguage(event.target.value)}>
        {!entry?.supported_languages.includes(language) ? <option value={language}>Choose a supported language</option> : null}
        {entry?.supported_languages.map(code => <option key={code} value={code}>{code}</option>)}
      </select></label>
      <p className="text-sm text-muted">Allowed variable keys: {entry?.allowed_projection_keys.join(", ") || "None"}. Match the order of Meta BODY placeholders: {"{{1}}, {{2}}, …"}</p>
      <ol className="grid gap-2">{parameters.map((key, index) => <li key={index} className="flex flex-wrap items-center gap-2">
        <label className="grid min-w-0 flex-1 gap-1 text-sm">BODY parameter {index + 1}<select className="desk-input" value={key} onChange={event => setParameters(parameters.map((item, i) => i === index ? event.target.value : item))}>
          {!entry?.allowed_projection_keys.includes(key) ? <option value={key}>Choose an allowed key</option> : null}
          {entry?.allowed_projection_keys.map(allowed => <option key={allowed} value={allowed}>{allowed}</option>)}
        </select></label>
        <button className="desk-button" type="button" aria-label={`Move parameter ${index + 1} up`} disabled={index === 0} onClick={() => move(index, -1)}>Up</button>
        <button className="desk-button" type="button" aria-label={`Move parameter ${index + 1} down`} disabled={index === parameters.length - 1} onClick={() => move(index, 1)}>Down</button>
        <button className="desk-button" type="button" aria-label={`Remove parameter ${index + 1}`} onClick={() => setParameters(parameters.filter((_, i) => i !== index))}>Remove</button>
      </li>)}</ol>
      {!parameters.length ? <p className="text-sm text-muted">No BODY parameters.</p> : null}
      <button type="button" className="desk-button w-fit" disabled={!entry?.allowed_projection_keys.length || parameters.length >= 100} onClick={() => setParameters([...parameters, entry!.allowed_projection_keys[0]])}>Add BODY parameter</button>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input className="h-4 w-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} />Active binding</label>
      <div className="flex flex-wrap gap-2"><button className="desk-button-primary" type="submit">{pending ? "Saving…" : "Save binding"}</button>
        <button className="desk-button" type="button" onClick={onCancel}>Cancel binding</button></div>
    </fieldset>
    {validation ? <p role="alert" className="text-sm text-danger">{validation}</p> : null}
  </form>;
}
