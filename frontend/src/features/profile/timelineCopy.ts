import { t } from "@lingui/core/macro";
import { Briefcase, GraduationCap, HeartHandshake, type LucideIcon } from "lucide-react";
import type { TimelineKind } from "./accountProfileTypes";

export const TIMELINE_KINDS: TimelineKind[] = ["experience", "education", "volunteering"];

export const TIMELINE_COPY: Record<TimelineKind, { title: string; Icon: LucideIcon; tone: string; owner: string; visitor: string }> = {
  experience: { title: t`Experience`, Icon: Briefcase, tone: "bg-info-soft text-info-ink",
    owner: t`Build your professional story. Add your work history.`, visitor: t`No experience shared yet.` },
  education: { title: t`Education`, Icon: GraduationCap, tone: "bg-warn-soft text-warn-ink",
    owner: t`Add the schools, courses and programmes you've studied.`, visitor: t`No education shared yet.` },
  volunteering: { title: t`Volunteering`, Icon: HeartHandshake, tone: "bg-accent-soft text-accent-ink",
    owner: t`Add the communities and causes you give time to.`, visitor: t`No volunteering shared yet.` },
};
