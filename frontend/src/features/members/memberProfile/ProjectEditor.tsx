import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { ImageUploader } from "../../staff/ImageUploader";
import { memberRequest } from "../../../lib/api";
import { profileToneForIdentity, tagsToText, textToTags } from "./helpers";
import { type ProjectDraft } from "./types";

export function ProjectEditor({
  makerspaceId,
  project,
  imageUrl,
  onChange,
  onRemove,
  onImageChanged,
}: {
  makerspaceId: number;
  project: ProjectDraft;
  imageUrl: string | null;
  onChange: (next: ProjectDraft) => void;
  onRemove: () => void;
  onImageChanged: () => void;
}) {
  const tags = project.tags ?? [];
  // Typed text is kept as-is so a trailing comma survives; the parsed list is what saves.
  const [tagsText, setTagsText] = useState(() => tagsToText(tags));
  const tagsKey = JSON.stringify(tags);
  // Re-sync only when the saved list changes underneath (discard, reload), not on every keystroke.
  useEffect(() => {
    const next = JSON.parse(tagsKey) as string[];
    setTagsText(current => (JSON.stringify(textToTags(current)) === tagsKey ? current : tagsToText(next)));
  }, [tagsKey]);
  return (
    <div className={`rounded-lg border ${profileToneForIdentity(project.id)} p-3`}>
      <input
        className="desk-input w-full"
        placeholder={t`Project title`}
        aria-label={t`Project title`}
        value={project.title}
        onChange={(event) => onChange({ ...project, title: event.target.value })}
      />
      <input
        className="desk-input mt-2 w-full"
        placeholder={t`Subtitle, e.g. FPGA design for DVCon`}
        aria-label={t`Project subtitle`}
        maxLength={200}
        value={project.subtitle ?? ""}
        onChange={(event) => onChange({ ...project, subtitle: event.target.value })}
      />
      <textarea
        className="desk-input mt-2 w-full"
        rows={2}
        placeholder={t`What is it?`}
        aria-label={t`Project description`}
        value={project.description}
        onChange={(event) => onChange({ ...project, description: event.target.value })}
      />
      <input
        className="desk-input mt-2 w-full"
        placeholder={t`Tags, comma separated`}
        aria-label={t`Project tags`}
        value={tagsText}
        onChange={(event) => { setTagsText(event.target.value); onChange({ ...project, tags: textToTags(event.target.value).slice(0, 20) }); }}
      />
      <label className="mt-2 flex min-h-11 items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          className="h-5 w-5"
          checked={Boolean(project.public_visible)}
          onChange={(event) => onChange({ ...project, public_visible: event.target.checked })}
        />
        {t`Show on my public profile page`}</label>
      {/* An image can only be attached to a project that exists server-side — a new one
          has no id to attach it to, so it appears after the first save. */}
      {project.id ? (
        <div className="mt-3">
          <ImageUploader
            request={memberRequest}
            endpoint={`/member/makerspaces/${makerspaceId}/profile/image`}
            currentUrl={imageUrl}
            label={t`Project image`}
            extraBody={{ project_id: project.id }}
            clearQuery={`?project_id=${project.id}`}
            onChanged={onImageChanged}
          />
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">{t`Save the project to add an image.`}</p>
      )}
      <div className="mt-2 space-y-2">
        {project.links.map((link, index) => (
          <div key={index} className={`flex flex-col gap-2 border-l-2 ${profileToneForIdentity(`${link.label}|${link.url}`)} p-2 sm:flex-row`}>
            <input
              className="desk-input w-full sm:w-40"
              placeholder={t`Label`}
              aria-label={t`Link label`}
              value={link.label}
              onChange={(event) =>
                onChange({
                  ...project,
                  links: project.links.map((row, position) =>
                    position === index ? { ...row, label: event.target.value } : row,
                  ),
                })
              }
            />
            <input
              className="desk-input w-full"
              placeholder="https://…"
              aria-label={t`Link URL`}
              value={link.url}
              onChange={(event) =>
                onChange({
                  ...project,
                  links: project.links.map((row, position) =>
                    position === index ? { ...row, url: event.target.value } : row,
                  ),
                })
              }
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          className="desk-button-ghost"
          type="button"
          onClick={() =>
            onChange({ ...project, links: [...project.links, { label: "", url: "" }] })
          }
        >
          {t`Add link`}</button>
        <button className="desk-button-danger" type="button" onClick={onRemove}>
          {t`Remove project`}</button>
      </div>
    </div>
  );
}
