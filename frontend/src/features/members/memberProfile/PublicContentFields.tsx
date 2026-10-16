import { X } from "lucide-react";
import { IconButton } from "../../../components/ui";
import type { ProfileLink, ProfileSkill } from "../../profile/publicProfileApi";
import { SKILL_LEVELS } from "../../profile/profileFormat";
import { Field } from "./Field";

export const MAX_DOMAINS = 20;
export const MAX_SKILLS = 30;
export const MAX_LINKS = 10;

/** True for what the server accepts: https and no credentials in the URL. */
export function isPublicLink(url: string) {
  try { const parsed = new URL(url); return parsed.protocol === "https:" && !parsed.username && !parsed.password; } catch { return false; }
}

export function SkillsField({ skills, onChange }: { skills: ProfileSkill[]; onChange: (next: ProfileSkill[]) => void }) {
  const update = (index: number, changes: Partial<ProfileSkill>) => onChange(skills.map((row, position) => position === index ? { ...row, ...changes } : row));
  return <Field id="profile-skill-0" label="Skills and languages" hint="Rate yourself: familiar, comfortable or fluent.">
    <div className="grid gap-2">
      {skills.map((skill, index) => <div key={index} className="flex flex-wrap gap-2">
        <input id={`profile-skill-${index}`} aria-label={`Skill ${index + 1}`} className="desk-input min-w-0 grow basis-40" maxLength={60}
          placeholder="e.g. Python" value={skill.name} onChange={event => update(index, { name: event.target.value })} />
        <select aria-label={`Level for skill ${index + 1}`} className="desk-input w-auto" value={skill.level}
          onChange={event => update(index, { level: Number(event.target.value) })}>
          {SKILL_LEVELS.map((label, level) => <option key={label} value={level + 1}>{label}</option>)}
        </select>
        <IconButton label={`Remove skill ${index + 1}`} onClick={() => onChange(skills.filter((_, position) => position !== index))}><X aria-hidden="true" className="h-4 w-4" /></IconButton>
      </div>)}
      <button type="button" className="desk-button-ghost w-fit" disabled={skills.length >= MAX_SKILLS}
        onClick={() => onChange([...skills, { name: "", level: 1 }])}>Add a skill</button>
    </div>
  </Field>;
}

const LINK_KINDS = ["Website", "GitHub", "X", "LinkedIn", "Instagram", "Other"];

export function LinksField({ links, onChange }: { links: ProfileLink[]; onChange: (next: ProfileLink[]) => void }) {
  const update = (index: number, changes: Partial<ProfileLink>) => onChange(links.map((row, position) => position === index ? { ...row, ...changes } : row));
  return <Field id="profile-link-0" label="Links" hint="Shown as buttons on your public page. HTTPS links only.">
    <div className="grid gap-2">
      {links.map((link, index) => {
        const bad = link.url.trim() !== "" && !isPublicLink(link.url.trim());
        return <div key={index} className="grid gap-1">
          <div className="flex flex-wrap gap-2">
            <select aria-label={`Link ${index + 1} type`} className="desk-input w-auto" value={LINK_KINDS.includes(link.kind) ? link.kind : "Other"}
              onChange={event => update(index, { kind: event.target.value })}>
              {LINK_KINDS.map(kind => <option key={kind}>{kind}</option>)}
            </select>
            <input id={`profile-link-${index}`} aria-label={`Link ${index + 1} URL`} type="url" inputMode="url" className="desk-input min-w-0 grow basis-48"
              placeholder="https://…" maxLength={500} value={link.url} aria-invalid={bad || undefined}
              aria-describedby={bad ? `profile-link-${index}-error` : undefined} onChange={event => update(index, { url: event.target.value })} />
            <IconButton label={`Remove link ${index + 1}`} onClick={() => onChange(links.filter((_, position) => position !== index))}><X aria-hidden="true" className="h-4 w-4" /></IconButton>
          </div>
          {bad ? <p id={`profile-link-${index}-error`} className="text-sm text-danger">Use a link that starts with https://.</p> : null}
        </div>;
      })}
      <button type="button" className="desk-button-ghost w-fit" disabled={links.length >= MAX_LINKS}
        onClick={() => onChange([...links, { kind: "Website", url: "" }])}>Add a link</button>
    </div>
  </Field>;
}
