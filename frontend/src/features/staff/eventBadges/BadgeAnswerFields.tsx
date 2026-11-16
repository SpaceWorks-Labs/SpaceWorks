// Registration answers on the badge: add from the event's sign-up form (plus Team and Role), reorder, relabel,
// remove. At most `max` print. Keys this event's form doesn't have (usually from an imported design) are
// listed apart, with one action to remove them all. Adding an answer always writes its label, because the
// server prints `printFieldLabels` (or a label made from the key), never the form's own wording.
import { t } from "@lingui/core/macro";

import type { BadgeField } from "./badgeApi";
import { Section } from "./badgeControls";
import type { BadgeSettings } from "./badgeNormalize";
import type { Update } from "./BadgeSections";

/** The form field a stored key refers to (a bare key matches `registration:<key>`), or null when unmatched. */
export function matchField(fields: BadgeField[], key: string) {
  return fields.find((field) => field.key === key || field.key === `registration:${key}`) ?? null;
}

export function unmatchedKeys(settings: BadgeSettings, fields: BadgeField[]) {
  return settings.printFieldKeys.filter((key) => !matchField(fields, key));
}

export function BadgeAnswerFields({ settings, fields, max, update }: { settings: BadgeSettings; fields: BadgeField[]; max: number;
  update: Update }) {
  const keys = settings.printFieldKeys;
  const available = fields.filter((field) => !keys.some((key) => matchField([field], key)));
  const unmatched = unmatchedKeys(settings, fields);
  const full = keys.length >= max;
  const move = (index: number, by: -1 | 1) => {
    const next = [...keys];
    const [item] = next.splice(index, 1);
    next.splice(index + by, 0, item);
    update({ printFieldKeys: next });
  };
  const remove = (gone: string[]) => update({ printFieldKeys: keys.filter((key) => !gone.includes(key)),
    printFieldLabels: Object.fromEntries(Object.entries(settings.printFieldLabels).filter(([key]) => !gone.includes(key))) });
  return <Section title={t`Registration answers`}>
    {keys.length ? <ol className="grid gap-2">
      {keys.map((key, index) => {
        const field = matchField(fields, key);
        const name = field?.label ?? key;
        return <li key={key} className="grid gap-2 rounded-control border border-line p-2.5">
          <div className="flex min-w-0 items-baseline justify-between gap-2">
            <span className="min-w-0 truncate text-sm font-semibold text-ink">{name}</span>
            {!field ? <span className="shrink-0 text-xs text-warn-ink">{t`Not on this event's form`}</span> : null}
          </div>
          <div className="flex flex-wrap gap-1">
            <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Move ${name} up`} disabled={index === 0}
              onClick={() => move(index, -1)}>{t`Up`}</button>
            <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Move ${name} down`} disabled={index === keys.length - 1}
              onClick={() => move(index, 1)}>{t`Down`}</button>
            <button type="button" className="desk-button-ghost min-h-11" aria-label={t`Remove ${name}`} onClick={() => remove([key])}>{t`Remove`}</button>
          </div>
          <input className="desk-input min-h-11" aria-label={t`Printed label for ${name}`} maxLength={60}
            value={settings.printFieldLabels[key] ?? name} placeholder={t`No label, just the answer`}
            onChange={(event) => update({ printFieldLabels: { ...settings.printFieldLabels, [key]: event.target.value } })} />
        </li>;
      })}
    </ol> : <p className="text-xs text-muted">{t`Print answers like company or role under the name.`}</p>}
    {unmatched.length ? <div role="status" className="grid gap-2 rounded-control border border-line bg-surface p-2.5 text-sm text-ink">
      <p>{t`${unmatched.length} chosen answers aren't on this event's sign-up form, so they print empty.`}</p>
      <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => remove(unmatched)}>
        {t`Remove the unmatched answers`}</button>
    </div> : null}
    {available.length ? <div role="group" aria-label={t`Add an answer`} className="flex flex-wrap gap-1.5">
      {available.map((field) => <button key={field.key} type="button" disabled={full}
        onClick={() => update({ printFieldKeys: [...keys, field.key],
          printFieldLabels: { ...settings.printFieldLabels, [field.key]: settings.printFieldLabels[field.key] ?? field.label } })}
        className="inline-flex min-h-11 items-center rounded-full border border-dashed border-line px-3 text-sm font-semibold text-muted hover:bg-surface hover:text-ink disabled:opacity-50">
        {t`Add ${field.label}`}</button>)}
    </div> : fields.length ? null : <p className="text-xs text-muted">{t`This event's sign-up form has no questions to print.`}</p>}
    {full ? <p className="text-xs text-muted">{t`A badge prints at most ${max} answers.`}</p> : null}
  </Section>;
}
