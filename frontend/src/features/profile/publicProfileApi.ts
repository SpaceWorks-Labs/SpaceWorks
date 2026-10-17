import { useQuery } from "@tanstack/react-query";

import { publicV1Request as profileRequest, StructuredApiError } from "../../lib/api";
import { personalRecipientKey } from "../notifications/personalQueryKeys";

/** Shapes of the frozen Phase 1b anonymous profile contract (public_profile_serializers.py). */
export type ProfileSkill = { name: string; level: number };
export type ProfileLink = { kind: string; url: string };
export type TimelineKind = "experience" | "education" | "volunteering";
export type PublicTimelineEntry = {
  kind: TimelineKind; title: string; organization: string; location: string;
  start: string; end: string | null; description: string; order: number;
};
export type PublicProject = {
  title: string; subtitle: string; description: string; tags: string[];
  image_url: string | null; links: ProfileLink[];
};
export type FamilyFlags = {
  show_activity_graph: boolean; show_events: boolean; show_speaking: boolean; show_projects: boolean;
  show_machine_activity: boolean; show_bookings: boolean; show_loans: boolean;
};
export type PublicProfile = FamilyFlags & {
  viewer_is_owner: boolean;
  handle: string; display_name: string; avatar_url: string | null; verified: boolean;
  headline: string; institution: string; bio: string; domains: string[]; skills: ProfileSkill[];
  links: ProfileLink[]; timeline: PublicTimelineEntry[]; projects: PublicProject[];
  vouched_by: { handle: string; display_name: string }[]; vouched_count: number;
};
export type PublicProfileEvent = {
  title: string; starts_at: string; ends_at: string; badge: "ATTENDED" | "HOSTED" | "SPOKE"; host: string;
};
export type DailyBucket = { date: string; count: number; families?: Record<string, number> };
export type PublicActivity = { from: string; to: string; timezone: string; days: DailyBucket[] };
/**
 * The GitHub calendar is added by the parallel profile-be lane and is not part of the frozen
 * contract. Only `days` is relied on; anything else (or a 404) hides the graph.
 */
export type GithubCalendar = { days: { date: string; count: number }[]; total?: number };
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export const HANDLE_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])$/;

export const publicProfileKeys = {
  // Ownership is personalized; never reuse an owner's response for another viewer.
  root: (handle: string) => ["public-profile", handle, "viewer", personalRecipientKey()] as const,
  activity: (handle: string) => ["public-profile", handle, "activity"] as const,
  events: (handle: string, page: number) => ["public-profile", handle, "events", page] as const,
  projects: (handle: string, page: number) => ["public-profile", handle, "projects", page] as const,
  github: (handle: string) => ["public-profile", handle, "github"] as const,
};

const base = (handle: string) => `/public/profiles/${encodeURIComponent(handle)}/`;
const notFound = (error: unknown) => error instanceof StructuredApiError && error.status === 404;
// A missing profile cannot be retried into existence; other failures retry once.
const retryUnlessMissing = (count: number, error: unknown) => !notFound(error) && count < 1;

export function isProfileMissing(error: unknown) {
  return notFound(error);
}

export function usePublicProfile(handle: string, sessionReady = true) {
  return useQuery({
    queryKey: publicProfileKeys.root(handle),
    queryFn: () => profileRequest<PublicProfile>(base(handle)),
    enabled: sessionReady && HANDLE_PATTERN.test(handle),
    retry: retryUnlessMissing,
  });
}

export function usePublicProfileActivity(handle: string, enabled: boolean) {
  return useQuery({
    queryKey: publicProfileKeys.activity(handle),
    queryFn: () => profileRequest<PublicActivity>(`${base(handle)}activity`),
    enabled, retry: retryUnlessMissing,
  });
}

export function usePublicProfileEvents(handle: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: publicProfileKeys.events(handle, page),
    queryFn: () => profileRequest<Page<PublicProfileEvent>>(`${base(handle)}events?page=${page}`),
    enabled, retry: retryUnlessMissing,
  });
}

export function usePublicProfileProjects(handle: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: publicProfileKeys.projects(handle, page),
    queryFn: () => profileRequest<Page<PublicProject>>(`${base(handle)}projects?page=${page}`),
    enabled, retry: retryUnlessMissing,
  });
}

/** Resolves to null when the endpoint is absent (404) or answers with an unexpected shape. */
export function usePublicProfileGithub(handle: string, enabled: boolean) {
  return useQuery({
    queryKey: publicProfileKeys.github(handle),
    queryFn: async () => {
      try {
        const body = await profileRequest<GithubCalendar>(`${base(handle)}github`);
        return Array.isArray(body?.days) ? body : null;
      } catch (error) {
        if (notFound(error)) return null;
        throw error;
      }
    },
    enabled, retry: false,
  });
}
