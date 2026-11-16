import { useQuery } from "@tanstack/react-query";

import { memberRequest, publicV1Request as profileRequest, StructuredApiError } from "../../lib/api";
import { publicAnonymousRequest } from "../../lib/api/requests";
import { personalRecipientKey } from "../notifications/personalQueryKeys";
import type { AccountProfile } from "./accountProfileTypes";

export type PublicAccountCard = {
  display_name: string; avatar_url: string | null;
  handle?: string; bio?: string;
  projects?: { title: string; subtitle: string; description: string; tags: string[];
    image_url: string | null; links: { kind: string; url: string }[] }[];
  memberships?: { slug: string; name: string; role_title: string | null; started_on: string }[];
};

export type {
  AccountProfile, Audience, ProfileLink, ProfileSkill, TimelineKind,
} from "./accountProfileTypes";

/** Account usernames: 3-30 of [a-z0-9._-], starting and ending alphanumeric. */
export const HANDLE_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])$/;

export const publicProfileKeys = {
  // Version the public card so a previously cached rich owner response cannot fill this query.
  root: (handle: string) => ["public-profile", "card-549", handle] as const,
  // The authenticated by-account reader retains viewer isolation.
  account: (accountId: string) => ["public-profile", "account", accountId, "viewer", personalRecipientKey()] as const,
};

const notFound = (error: unknown) => error instanceof StructuredApiError && error.status === 404;
// A missing profile cannot be retried into existence; other failures retry once.
const retryUnlessMissing = (count: number, error: unknown) => !notFound(error) && count < 1;

/** Missing handles use the shared not-found page. */
export function isProfileMissing(error: unknown) {
  return notFound(error);
}

export function isSignedOutError(error: unknown) {
  return error instanceof StructuredApiError && error.status === 401;
}

/** Always-on anonymous card. Fetch follows retired-handle redirects. */
export function usePublicProfile(handle: string, sessionReady = true) {
  return useQuery({
    queryKey: publicProfileKeys.root(handle),
    queryFn: () => publicAnonymousRequest<PublicAccountCard>(`/public/profiles/${encodeURIComponent(handle)}/`),
    enabled: sessionReady && HANDLE_PATTERN.test(handle),
    retry: retryUnlessMissing,
  });
}

/** GET /profiles/by-account/<id>/: signed-in only (401 logged out). */
export function useAccountProfile(accountId: string, enabled = true) {
  return useQuery({
    queryKey: publicProfileKeys.account(accountId),
    queryFn: () => memberRequest<AccountProfile>(`/profiles/by-account/${encodeURIComponent(accountId)}/`),
    enabled: enabled && /^\d+$/.test(accountId),
    retry: (count, error) => !notFound(error) && !isSignedOutError(error) && count < 1,
  });
}

type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type DailyBucket = { date: string; count: number; families?: Record<string, number> };
export type PublicActivity = { from: string; to: string; timezone: string; days: DailyBucket[] };
export type GithubCalendar = { source?: "github"; days: { date: string; count: number }[] };
export type ProfileProject = { title: string; subtitle: string; description: string; tags: string[]; image_url: string | null; links: { label: string; url: string }[] };
export type ProfileEvent = { title: string; starts_at: string; ends_at: string; badge: "ATTENDED" | "HOSTED" | "SPOKE"; host: string };

const base = (handle: string) => `/public/profiles/${encodeURIComponent(handle)}/`;

/** Account-level counts-only graph across the person's spaces. Empty unless the graph switch is on. */
export function usePublicProfileActivity(handle: string, enabled: boolean) {
  return useQuery({
    queryKey: ["public-profile", handle, "activity", personalRecipientKey()],
    queryFn: () => profileRequest<PublicActivity>(`${base(handle)}activity`), enabled, retry: retryUnlessMissing,
  });
}

/** `404` when the graph is off: that is "no graph", never an error state. */
export function usePublicProfileGithub(handle: string, enabled: boolean) {
  return useQuery({
    queryKey: ["public-profile", handle, "github", personalRecipientKey()],
    queryFn: async () => {
      try { const body = await profileRequest<GithubCalendar>(`${base(handle)}github`); return Array.isArray(body?.days) ? body : null; }
      catch (error) { if (notFound(error)) return null; throw error; }
    },
    enabled, retry: false,
  });
}

/** Events history (hosted, spoke, attended); empty unless `show_events`. */
export function usePublicProfileEvents(handle: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: ["public-profile", handle, "events", page, personalRecipientKey()],
    queryFn: () => profileRequest<Page<ProfileEvent>>(`${base(handle)}events?page=${page}`), enabled, retry: retryUnlessMissing,
  });
}

/** Paginated public projects (empty unless `show_projects`). The main payload already carries the list; this serves paging. */
export function usePublicProfileProjects(handle: string, page: number, enabled: boolean) {
  return useQuery({
    queryKey: ["public-profile", handle, "projects", page, personalRecipientKey()],
    queryFn: () => profileRequest<Page<ProfileProject>>(`${base(handle)}projects?page=${page}`), enabled, retry: retryUnlessMissing,
  });
}
