import type { AccountProfile } from "../accountProfileTypes";
import { AboutSection, AchievementsSection, CertificationsSection, EducationSection, ExperienceSection, SpacesSection, StatusSection } from "./ResumeSections";
import { ActivitySection } from "./ActivitySection";
import { EventsSection, InterestsSection, LinksSection, ProjectsSection, SkillsSection } from "./WorkSections";

/** The one place the section order lives: status, about, spaces, experience, education, achievements, projects, events, skills, links. */
export function ResumeBlocks({ profile }: { profile: AccountProfile }) {
  return <div className="grid gap-6">
    <StatusSection profile={profile} />
    <AboutSection profile={profile} />
    <SpacesSection profile={profile} />
    <ExperienceSection profile={profile} />
    <EducationSection profile={profile} />
    <AchievementsSection profile={profile} />
    <CertificationsSection profile={profile} />
    <ProjectsSection profile={profile} />
    <EventsSection profile={profile} />
    <ActivitySection profile={profile} />
    <SkillsSection profile={profile} />
    <InterestsSection profile={profile} />
    <LinksSection profile={profile} />
  </div>;
}
