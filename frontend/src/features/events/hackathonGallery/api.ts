import { t } from "@lingui/core/macro";
import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { memberRequest, tenantPublicRequest } from '../../../lib/api';
import { onSessionCleared } from '../../../lib/api/sessionContext';
import { galleryConsent, galleryEntry, galleryFilters, page, publicResults, sponsorConsent } from './parsers';
import { command, type Envelope, type Page, type SponsorConsent, type SponsorOption } from './types';
import { useClearOnAccessLoss } from './accessLoss';

export type MemberScope = { makerspaceId: number; eventId: number; actorId: number };
export const memberKey = (scope: MemberScope) => ['programme-sharing', 'member', scope.actorId, scope.makerspaceId, scope.eventId] as const;
export function useSharing(scope: MemberScope, loadConsents = true, pageNumber = 1) {
  const client = useQueryClient(); const key = memberKey(scope);
  useEffect(() => onSessionCleared(() => client.removeQueries({ queryKey: key })), [client, ...key]);
  useEffect(() => () => { void client.cancelQueries({ queryKey: key }); client.removeQueries({ queryKey: key }); }, [client, ...key]);
  const base = `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/`;
  const consents = useQuery({ queryKey: [...key, 'resume-consents', pageNumber], retry: false, enabled: loadConsents,
    queryFn: async () => {
      const value = await memberRequest<Page<SponsorConsent> & { sponsors: SponsorOption[] }>(`${base}resume-consents/?page=${pageNumber}`);
      if (!Array.isArray(value.sponsors) || value.sponsors.some(s => !Number.isSafeInteger(s.id) || typeof s.name !== 'string' || !Number.isSafeInteger(s.disclosure_revision))) throw new Error(t`Invalid sponsor options.`);
      return { ...page(value, sponsorConsent), sponsors: value.sponsors };
    } });
  const mutate = useMutation({ retry: false, mutationFn: ({ suffix, version, fields = {} }: { suffix: string; version: number; fields?: Record<string, unknown> }) => {
    const body = { ...fields, ...command(version) };
    return memberRequest<Envelope>(base + suffix, { method: 'POST', headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) });
  }, onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  useClearOnAccessLoss(key, [consents.error, mutate.error]);
  return { consents, mutate, base, key };
}
export function useGalleryConsent(scope: MemberScope, teamId: number) {
  const sharing = useSharing(scope, false);
  const query = useQuery({ queryKey: [...sharing.key, 'team', teamId], retry: false,
    queryFn: async () => galleryConsent(await memberRequest(`${sharing.base}teams/${teamId}/gallery-consent/`)) });
  useClearOnAccessLoss(sharing.key, [query.error, sharing.mutate.error]);
  return { query, mutate: sharing.mutate };
}
export type GallerySearch = { q?: string; sort?: 'newest' | 'az' | 'awards'; awards?: 'only'; fields?: Record<string, string> };
/** Gallery search params (L21b, X54) are sent only when set, so a space with search off still gets the plain list.
 *  S7: each chosen public choice field goes as `field.<key>=<choice>`, in key order so the query key is stable. */
export function gallerySearchQuery(search: GallerySearch = {}) {
  const params = new URLSearchParams();
  if (search.q?.trim()) params.set('q', search.q.trim());
  if (search.sort && search.sort !== 'newest') params.set('sort', search.sort);
  if (search.awards) params.set('awards', search.awards);
  for (const key of Object.keys(search.fields ?? {}).sort()) {
    const choice = search.fields?.[key];
    if (choice) params.set(`field.${key}`, choice);
  }
  return params.toString();
}
/** True when any search, sort, award or field filter is set (a failure then means "search unavailable"). */
export function isGallerySearching(search: GallerySearch) {
  return Boolean(search.q || search.awards || (search.sort && search.sort !== 'newest')
    || Object.values(search.fields ?? {}).some(Boolean));
}
export function usePublicGallery(slug: string, token: string, pageNumber: number, entryId?: string, search: GallerySearch = {}) {
  const base = `/public/event-programmes/${encodeURIComponent(token)}/gallery/`;
  const filters = gallerySearchQuery(search);
  return useQuery({ queryKey: ['public-project-gallery', slug, token, entryId, pageNumber, filters], staleTime: 0, gcTime: 0, retry: false,
    queryFn: async () => {
      if (entryId) return galleryEntry(await tenantPublicRequest(slug, `${base}${encodeURIComponent(entryId)}/`, { cache: 'no-store' }));
      const value = await tenantPublicRequest(slug, `${base}?${filters ? `${filters}&` : ''}page=${pageNumber}`, { cache: 'no-store' });
      return { ...page(value, galleryEntry), filters: galleryFilters(value) };
    } });
}
export function usePublicResults(slug: string, token: string) {
  return useQuery({ queryKey: ['public-hackathon-results', slug, token], staleTime: 0, gcTime: 0, retry: false,
    queryFn: async () => publicResults(await tenantPublicRequest(slug, `/public/event-programmes/${encodeURIComponent(token)}/results/`, { cache: 'no-store' })) });
}
