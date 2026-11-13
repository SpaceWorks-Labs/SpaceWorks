import type { AccountProfile, ProfileLink, ProfilePatch, ProfileSkill, StatusPreset } from "../accountProfileTypes";
import { tagsToText, textToTags } from "../../members/memberProfile/helpers";
import { MAX_DOMAINS } from "../../members/memberProfile/PublicContentFields";
import type { ProjectDraft } from "../../members/memberProfile/types";

/** What the single "Save changes" form holds. Toggles, timeline, achievements and handle save on their own. */
export type ProfileDraft = {
  preset: StatusPreset; note: string; headline: string; institution: string; bio: string;
  domains: string; skills: ProfileSkill[]; links: ProfileLink[]; interests: string; languages: string;
  projects: ProjectDraft[]; github: string;
};

export function seedDraft(profile: AccountProfile): ProfileDraft {
  return {
    preset: profile.status?.preset ?? "", note: profile.status?.note ?? "", headline: profile.headline, institution: profile.institution, bio: profile.bio,
    domains: tagsToText(profile.domains), skills: profile.skills.map(row => ({ ...row })), links: profile.links.map(row => ({ ...row })),
    interests: tagsToText(profile.interests), languages: tagsToText(profile.languages),
    github: profile.github_username ?? "",
    projects: profile.projects.map(({ id, title, subtitle, tags, public_visible, description, links }) => ({ id, title, subtitle, tags, public_visible, description, links: links.map(row => ({ ...row })) })),
  };
}

/** Projects REPLACE the server list (a merge could not express deleting one), so the full list is always sent. */
export function draftToPatch(draft: ProfileDraft): ProfilePatch {
  return {
    status: draft.preset, status_note: draft.note.trim(), headline: draft.headline, institution: draft.institution, bio: draft.bio,
    domains: textToTags(draft.domains).slice(0, MAX_DOMAINS),
    skills: draft.skills.filter(row => row.name.trim()).map(row => ({ name: row.name.trim(), level: row.level })),
    links: draft.links.filter(row => row.url.trim()).map(row => ({ kind: row.kind, url: row.url.trim() })),
    interests: textToTags(draft.interests), languages: textToTags(draft.languages), github_username: draft.github.trim(),
    projects: draft.projects.filter(row => row.title.trim()).map(row => ({
      ...(row.id ? { id: row.id } : {}), title: row.title.trim(), subtitle: row.subtitle ?? "", tags: row.tags ?? [],
      public_visible: Boolean(row.public_visible), description: row.description,
      links: row.links.filter(link => link.label.trim() && link.url.trim()),
    })),
  };
}
