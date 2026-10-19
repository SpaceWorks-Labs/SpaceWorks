import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_V1_URL, publicV1Request, staffRequest, StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { personalRecipientKey } from "../notifications/personalQueryKeys";
import type { Collection, EditorState, HandleResolution, PageDocument, PageOwner, PublicPageProjection, PreviewProjection, RevisionMetadata } from "./pageTypes";

export const hostScope = () => `${window.location.origin}|${API_V1_URL}`;
export const publicPagePolicy = {
  throwOnError: false,
  staleTime: 0, gcTime: 0, refetchOnMount: "always" as const, refetchOnWindowFocus: "always" as const,
  refetchInterval: 30_000,
  retry: (count: number, error: unknown) => !(error instanceof StructuredApiError && error.status < 500) && count < 1,
};
export const editorBase = (owner: PageOwner) => `/admin/${owner.kind === "makerspace" ? "makerspaces" : "organizations"}/${owner.id}/public-page/`;
export const editorKey = (owner: PageOwner) => ["page-editor", hostScope(), currentSessionContext(), personalRecipientKey(), owner.kind, owner.id] as const;
export const pageKey = (kind: PageOwner["kind"], slug: string) => ["public-page", hostScope(), kind, slug] as const;

/** A 404 replaces cached content. Query errors otherwise retain their last successful data. */
export async function publicOrMissing<T>(read: () => Promise<T>): Promise<T | null> {
  try { return await read(); } catch (error) {
    if (error instanceof StructuredApiError && error.status === 404) return null;
    throw error;
  }
}

/** Server links may be absolute, but authenticated transports must stay on the configured API. */
export function pageApiPath(value: string) {
  const base = new URL(API_V1_URL, window.location.origin);
  const url = new URL(value, base.origin);
  const prefix = base.pathname.replace(/\/$/, "");
  const path = url.pathname.startsWith(`${prefix}/`) ? url.pathname.slice(prefix.length) : url.pathname;
  if (url.origin !== base.origin || url.username || url.password || url.hash || !path.startsWith("/public/")) {
    throw new Error("The page returned an unsupported content address.");
  }
  return `${path}${url.search}`;
}

export function usePageHandle(handle: string, enabled: boolean) {
  return useQuery({ queryKey: ["page-handle", hostScope(), handle], ...publicPagePolicy, enabled,
    queryFn: () => publicOrMissing(() => publicV1Request<HandleResolution>(`/public/page-handles/${encodeURIComponent(handle)}/`, { cache: "no-store" })),
  });
}
export function usePublicPage(kind: PageOwner["kind"], slug: string, enabled = true) {
  const path = kind === "makerspace" ? `/public/${encodeURIComponent(slug)}/page/` : `/public/organizations/${encodeURIComponent(slug)}/page/`;
  return useQuery({ queryKey: pageKey(kind, slug), ...publicPagePolicy, enabled: enabled && Boolean(slug),
    queryFn: () => publicOrMissing(() => kind === "makerspace" ? tenantPublicRequest<PublicPageProjection>(slug, path, { cache: "no-store" })
      : publicV1Request<PublicPageProjection>(path, { cache: "no-store" })),
  });
}
export function usePageEditor(owner: PageOwner) {
  return useQuery({ queryKey: editorKey(owner), staleTime: 0, gcTime: 0, retry: false,
    queryFn: () => staffRequest<EditorState>(editorBase(owner), { cache: "no-store" }),
  });
}
export type PageOperation = { action: "save" | "preview"; version: number; document: PageDocument }
  | { action: "publish"; version: number; draft_revision_id: string }
  | { action: "unpublish" | "release_handle"; version: number }
  | { action: "handle"; version: number; handle: string }
  | { action: "delete_asset"; version: number; id: number }
  | { action: "upload"; version: number; file: File; alt_text: string };

export function usePageOperation(owner: PageOwner) {
  const client = useQueryClient();
  return useMutation({ mutationFn: async (input: PageOperation): Promise<EditorState | PreviewProjection> => {
    const { action, ...body } = input;
    const base = editorBase(owner);
    if (input.action === "upload") {
      const data = new FormData(); data.set("version", String(input.version)); data.set("file", input.file); data.set("alt_text", input.alt_text);
      return (await staffRequest<Omit<import("../../generated/api").AssetUploadResult, "state"> & { state: EditorState }>(`${base}assets/`, { method: "POST", body: data })).state;
    }
    const path = action === "save" ? base : action === "release_handle" || action === "handle" ? `${base}handle/`
      : input.action === "delete_asset" ? `${base}assets/${input.id}/` : `${base}${action}/`;
    const payload = input.action === "delete_asset" ? { version: input.version } : body;
    return staffRequest<EditorState | PreviewProjection>(path, {
      method: action === "save" || action === "handle" ? "PUT" : action === "release_handle" || action === "delete_asset" ? "DELETE" : "POST",
      body: JSON.stringify(payload),
    });
  }, onSuccess: (data, input) => {
    if (input.action === "preview") return;
    client.setQueryData(editorKey(owner), data);
    // Not awaited: mutate()-level onSuccess must adopt the new base version in the same pass as the
    // editor cache update, or the builder briefly sees a version mismatch and flashes its conflict alert.
    void Promise.all(["public-page", "page-handle", "public-organization", "public-page-collection", "organizations", "public-event", "public-event-website", "page-revisions"].map(key => client.invalidateQueries({ queryKey: [key] })));
  } });
}
export function usePageRevisions(owner: PageOwner, enabled: boolean, page: number) {
  return useQuery({ queryKey: ["page-revisions", ...editorKey(owner), page], enabled, staleTime: 0, gcTime: 0,
    queryFn: () => staffRequest<Collection<RevisionMetadata>>(`${editorBase(owner)}revisions/?page=${page}`, { cache: "no-store" }),
  });
}
