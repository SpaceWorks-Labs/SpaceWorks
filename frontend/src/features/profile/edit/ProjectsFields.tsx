import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { SettingsSection } from "../../../components/ui";
import { ProjectEditor } from "../../members/memberProfile/ProjectEditor";
import type { ProjectDraft } from "../../members/memberProfile/types";
import type { AccountProfile } from "../accountProfileTypes";
import { fieldError, ownProfileKey } from "./profileEditApi";
import { useImportableSubmissions, useImportSubmission } from "./achievementsApi";
import { SectionToggle } from "./SectionToggle";
import { LogoLoader } from "../../../components/LogoLoader";

/** "Import from my hackathon submissions": only the caller's own, never already-imported ones. Title, summary and https links are copied. */
function ImportFromSubmissions() {
  const [open, setOpen] = useState(false);
  const list = useImportableSubmissions(open);
  const imported = useImportSubmission();
  const rows = list.data ?? [];
  return <div className="grid gap-3">
    <button type="button" className="desk-button w-fit" aria-expanded={open} onClick={() => { imported.reset(); setOpen(value => !value); }}>{t`Import from my hackathon submissions`}</button>
    {open ? <div className="grid gap-2 rounded-control border border-line p-3">
      {list.isLoading ? <LogoLoader size={48} className="min-h-12 py-3" /> : null}
      {list.error ? <p role="alert" className="text-sm text-danger">{t`Couldn't load your submissions. Try again.`}</p> : null}
      {!list.isLoading && !list.error && !rows.length ? <p className="text-sm text-muted">{t`No submissions to import yet.`}</p> : null}
      <ul className="grid gap-2">{rows.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-3">
        <span className="grid min-w-0"><span className="break-words font-semibold text-ink">{row.title}</span>
          <span className="text-sm text-muted">{[row.event_title, row.space_name].filter(Boolean).join(" · ")}</span></span>
        {row.already_imported ? <span className="chip">{t`Imported`}</span>
          : <button type="button" className="desk-button" disabled={imported.isPending} onClick={() => imported.mutate(row.id)}>{t`Import ${row.title}`}</button>}
      </li>)}</ul>
      {imported.error ? <p role="alert" className="text-sm text-danger">{fieldError(imported.error, "projects")}</p> : null}
      {imported.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Imported "${imported.data.title}". Find it in your projects.`}</p> : null}
    </div> : null}
  </div>;
}

/** Edits the project list inside the profile form (the list is replaced on save); images attach to saved projects only. */
export function ProjectsFields({ projects, saved, onChange }: {
  projects: ProjectDraft[]; saved: AccountProfile["projects"]; onChange: (next: ProjectDraft[]) => void;
}) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ownProfileKey });
  return <SettingsSection title={t`Projects`} description={t`Things you have built. Imported ones come from your own hackathon submissions.`}>
    <div className="grid gap-3 py-4">
      {projects.map((project, index) => <ProjectEditor key={project.id ?? `new-${index}`} project={project}
        imageUrl={saved.find(row => row.id === project.id)?.image_url ?? null}
        onChange={next => onChange(projects.map((row, position) => position === index ? next : row))}
        onRemove={() => onChange(projects.filter((_, position) => position !== index))} onImageChanged={() => { void refresh(); }} />)}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button-ghost" onClick={() => onChange([...projects, { title: "", subtitle: "", tags: [], public_visible: true, description: "", links: [] }])}>{t`Add a project`}</button>
      </div>
      <ImportFromSubmissions />
      <SectionToggle section="projects" label={t`Show my projects`} />
    </div>
  </SettingsSection>;
}
