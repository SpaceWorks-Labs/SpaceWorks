import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Modal } from "../../../components/ui";
import type { MemberProfile } from "../../members/memberProfile/types";
import type { PublicProfile } from "../publicProfileApi";
import { PublicProfileView } from "../PublicProfileView";
import type { TimelineEntry } from "./profileEditApi";

const httpsOnly = (url: string) => { try { return new URL(url).protocol === "https:"; } catch { return false; } };

/**
 * Mirrors the server's anonymous projection from the member's saved profile, so the preview
 * works before publishing. Verification comes from the saved member response; vouches
 * appear on the live page only.
 */
export function toPublicPreview(profile: MemberProfile, timeline: TimelineEntry[]): PublicProfile {
  const showProjects = Boolean(profile.show_projects);
  return {
    handle: profile.handle || "your-handle", display_name: profile.display_name, avatar_url: profile.avatar_url,
    verified: profile.verified, viewer_is_owner: true,
    headline: profile.headline, institution: profile.institution, bio: profile.bio,
    domains: profile.domains ?? [], skills: profile.skills ?? [], links: (profile.links ?? []).filter(link => httpsOnly(link.url)),
    timeline: timeline.map(({ id: _id, ...entry }) => entry),
    projects: showProjects ? profile.projects.filter(project => project.public_visible).map(project => ({
      title: project.title, subtitle: project.subtitle ?? "", description: project.description, tags: project.tags ?? [],
      image_url: project.image_url, links: project.links.filter(link => httpsOnly(link.url)).map(link => ({ kind: link.label, url: link.url })),
    })) : [],
    vouched_by: [], vouched_count: 0,
    show_activity_graph: Boolean(profile.show_activity_graph), show_events: Boolean(profile.show_events),
    show_speaking: Boolean(profile.show_speaking), show_projects: showProjects,
    show_machine_activity: Boolean(profile.show_machine_activity), show_bookings: Boolean(profile.show_bookings),
    show_loans: Boolean(profile.show_loans),
  };
}

export function ProfilePreviewDialog({ open, onClose, profile, timeline }: {
  open: boolean; onClose: () => void; profile: MemberProfile; timeline: TimelineEntry[];
}) {
  const [tab, setTab] = useState("profile");
  return <Modal open={open} onClose={onClose} size="xl" title={t`Preview: what visitors see`}>
    <p className="mb-6 rounded-control bg-info-soft p-3 text-sm text-info-ink">
      {t`Built from your saved profile. Save any edits first. Vouches appear on the live page.`}</p>
    {open ? <PublicProfileView profile={toPublicPreview(profile, timeline)} tab={tab} onTab={setTab} preview /> : null}
  </Modal>;
}
