import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { publicV1Request } from "../../../lib/api";
import { HANDLE_PATTERN } from "../publicProfileApi";

/**
 * Decision 308 contract (PROFILE-CONTRACT-0.12.0, "Username required"):
 *   GET /handles/check?handle=&username=&display_name= -> { handle, available: boolean|null, reason: ""|"invalid"|"reserved"|"taken", suggestion: string|null }
 *   The check is advisory (the claim re-checks under a lock) and throttled, so typing is debounced.
 *   Auth payload `user`: { handle, handle_required, handle_suggestion }.
 */
export type UsernameStatus = "idle" | "invalid" | "checking" | "available" | "taken" | "reserved" | "error";
export type HandleCheck = { handle?: string; available: boolean | null; reason: "" | "invalid" | "reserved" | "taken"; suggestion: string | null };

/** Offline fallback when the check fails: a display-name slug that fits the grammar. */
export function slugifyUsername(source: string) {
  const slug = source.toLowerCase().normalize("NFKD").replace(/[^a-z0-9._-]+/g, "-").replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, "").slice(0, 30);
  return slug.length >= 3 ? slug : "";
}

export const usernameKeys = {
  suggestion: (seed: string) => ["handles", "suggestion", seed] as const,
  availability: (value: string) => ["handles", "availability", value] as const,
  required: ["auth", "handle-required"] as const,
};

const check = (params: Record<string, string>) => publicV1Request<HandleCheck>(`/handles/check?${new URLSearchParams(params)}`);

/** Pre-filled suggestion from the server (account username, then display-name slug, then slug + digits). `known` skips the call. */
export function useUsernameSuggestion(seed: { displayName?: string; email?: string; known?: string | null }, enabled: boolean) {
  const key = `${seed.known ?? ""}|${seed.displayName ?? ""}|${seed.email ?? ""}`;
  const fallback = slugifyUsername(seed.displayName || seed.email?.split("@")[0] || "");
  return useQuery({
    queryKey: usernameKeys.suggestion(key), enabled, retry: false, staleTime: 60_000,
    queryFn: async () => {
      if (seed.known) return seed.known;
      try {
        const body = await check({ display_name: seed.displayName ?? "", username: seed.email?.split("@")[0] ?? "" });
        return body.suggestion || fallback;
      } catch { return fallback; }
    },
  });
}

/** Live availability: grammar is checked locally, then the server decides (debounced). */
export function useUsernameAvailability(raw: string): UsernameStatus {
  const value = raw.trim().toLowerCase();
  const [settled, setSettled] = useState(value);
  useEffect(() => { const timer = window.setTimeout(() => setSettled(value), 350); return () => window.clearTimeout(timer); }, [value]);
  const valid = HANDLE_PATTERN.test(settled);
  const query = useQuery({ queryKey: usernameKeys.availability(settled), enabled: valid, retry: false, staleTime: 15_000, queryFn: () => check({ handle: settled }) });
  if (!value) return "idle";
  if (!HANDLE_PATTERN.test(value)) return "invalid";
  if (settled !== value || query.isLoading) return "checking";
  if (query.error) return "error";
  if (query.data?.available) return "available";
  if (query.data?.reason === "invalid") return "invalid";
  return query.data?.reason === "reserved" ? "reserved" : "taken";
}

const REVIEW_KEY = "sw.username.review";
/** A social/OIDC sign-up has no form, so the server claimed a suggestion; remember to show "Your username is X, change it?". */
export function markUsernameReview() { try { window.sessionStorage.setItem(REVIEW_KEY, "1"); } catch { /* storage blocked: the step is a courtesy */ } }
export function takeUsernameReview() { try { const set = window.sessionStorage.getItem(REVIEW_KEY) === "1"; return set; } catch { return false; } }
export function clearUsernameReview() { try { window.sessionStorage.removeItem(REVIEW_KEY); } catch { /* nothing stored */ } }
