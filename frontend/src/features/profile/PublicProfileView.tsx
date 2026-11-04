import { Tabs } from "../../components/ui";
import type { Tab } from "../../components/ui/types";
import { ProfileEventsTab } from "./ProfileEventsTab";
import { ProfileHeader } from "./ProfileHeader";
import { ProfileOverviewTab } from "./ProfileOverviewTab";
import { ProfileTimelineTab, TIMELINE_COPY } from "./ProfileSectionTabs";
import { ProfileProjectsPage } from "./ProfileProjectsPage";
import type { PublicProfile, TimelineKind } from "./publicProfileApi";

const TIMELINE_KINDS: TimelineKind[] = ["experience", "education", "volunteering"];

/**
 * Visitors only get tabs that have something to show (gated tabs are omitted, never
 * disabled). The owner also gets the empty ones, each with its own way to add content.
 */
export function profileTabs(profile: PublicProfile, owner: boolean): Tab[] {
  const tabs: Tab[] = [{ key: "profile", label: "Profile" }];
  if (profile.show_events || profile.show_speaking) tabs.push({ key: "activities", label: "Activities" });
  if (profile.show_projects || owner) tabs.push({ key: "projects", label: "Projects" });
  for (const kind of TIMELINE_KINDS) {
    if (owner || profile.timeline.some(entry => entry.kind === kind)) tabs.push({ key: kind, label: TIMELINE_COPY[kind].title });
  }
  return tabs;
}

export function PublicProfileView({ profile, tab, onTab, editHref, preview = false }: {
  profile: PublicProfile; tab: string; onTab: (key: string) => void; editHref?: string; preview?: boolean;
}) {
  const tabs = profileTabs(profile, !preview && profile.viewer_is_owner);
  const active = tabs.some(row => row.key === tab) ? tab : "profile";
  return <div className="grid min-w-0 gap-8">
    <ProfileHeader profile={profile} editHref={editHref} preview={preview} />
    <Tabs label="Profile sections" tabs={tabs} activeKey={active} onChange={onTab}>
      {active === "profile" ? <ProfileOverviewTab profile={profile} preview={preview} /> : null}
      {active === "activities" ? <ProfileEventsTab handle={profile.handle} preview={preview} /> : null}
      {active === "projects" ? <ProfileProjectsPage handle={profile.handle} preview={preview}
        projects={profile.projects} visible={profile.show_projects} addHref={editHref} /> : null}
      {TIMELINE_KINDS.includes(active as TimelineKind)
        ? <ProfileTimelineTab kind={active as TimelineKind} entries={profile.timeline} addHref={editHref} /> : null}
    </Tabs>
  </div>;
}
