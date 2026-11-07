// "My cards": every live card of this account across spaces, programmes and events.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getAccessToken, memberRequest, memberRequestBlob, refreshAccessToken } from "../../../lib/api";
import { uploadCardPhoto as uploadMemberPhoto } from "../memberCard/api";

export type CardKind = "member_card" | "programme_card" | "event_card";
export type MyCard = {
  kind: CardKind; id: number; makerspace_id: number; issuer: string; title: string; name: string; number: string;
  label: string; valid_until: string; status: "valid" | "expired" | "revoked"; has_back: boolean; check_url: string;
  photo_request_open: boolean; wallet_platforms: string[]; email_available: boolean; qr_image: string | null;
  photo_set: boolean; photo_cleanup_available: boolean; photo_aspect: number;
};
export type EmailFormat = "pdf" | "png";
export type CardSettings = { verify_show_name: boolean; verify_show_photo: boolean; extras_opted_in: boolean;
  blood_group: string; emergency_contact_name: string; emergency_contact_phone: string; public_check_on: boolean;
  email_format: EmailFormat };

export const cardPath = (card: Pick<MyCard, "kind" | "id">) => `/member/cards/${card.kind}/${card.id}`;
export const myCardsKey = ["member", "cards"] as const;

/** Restore a session from the refresh cookie before asking who is signed in. */
export function useMemberIdentity() {
  const [restoring, setRestoring] = useState(!getAccessToken());
  useEffect(() => { if (restoring) void refreshAccessToken().finally(() => setRestoring(false)); }, [restoring]);
  const identity = useQuery({ queryKey: ["member", "cards-account"], queryFn: () => memberRequest<{ id: number }>("/auth/me"),
    enabled: !restoring, retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always" });
  return { restoring, identity };
}

export function useMyCards(enabled: boolean) {
  return useQuery({ queryKey: myCardsKey, enabled, queryFn: () => memberRequest<MyCard[]>("/member/cards") });
}

export function useCardImage(card: MyCard, side: "front" | "back", enabled: boolean) {
  return useQuery({
    queryKey: ["member", "card-image", card.kind, card.id, side], enabled, staleTime: 5 * 60_000,
    queryFn: async () => URL.createObjectURL(await memberRequestBlob(`${cardPath(card)}/download?format=png&side=${side}`)),
  });
}

export async function downloadMyCard(card: MyCard, format: "pdf" | "png") {
  const blob = await memberRequestBlob(`${cardPath(card)}/download?format=${format}`);
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: `${card.number || "card"}.${format}` }).click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function useEmailMyCard() {
  return useMutation({ mutationFn: ({ card, format }: { card: MyCard; format?: EmailFormat }) =>
    memberRequest(`${cardPath(card)}/email`, format ? { method: "POST", body: JSON.stringify({ format }) } : { method: "POST" }) });
}

export function useCardSettings(card: MyCard, enabled: boolean) {
  return useQuery({ queryKey: ["member", "card-settings", card.kind, card.id], enabled,
    queryFn: () => memberRequest<CardSettings>(`${cardPath(card)}/settings`) });
}

export function useSaveCardSettings(card: MyCard) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<CardSettings>) => memberRequest<CardSettings>(`${cardPath(card)}/settings`,
      { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: (saved) => client.setQueryData(["member", "card-settings", card.kind, card.id], saved),
  });
}

export function useRotateCheckLink(card: MyCard) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => memberRequest<{ check_url: string }>(`${cardPath(card)}/rotate-link`, { method: "POST" }),
    onSuccess: () => client.invalidateQueries({ queryKey: myCardsKey }),
  });
}

type Presign = { object_key?: string; url: string; fields?: Record<string, string>; method?: string; headers?: Record<string, string> };

/** Presign -> upload the photo to private storage -> attach it with the holder's consent. */
export async function uploadCardPhoto(card: MyCard, file: Blob) {
  if (card.kind === "member_card") {
    return uploadMemberPhoto(card.makerspace_id, new File([file], "card-photo.jpg", { type: file.type || "image/jpeg" }));
  }
  const type = file.type || "image/jpeg";
  const presign = await memberRequest<Presign>(`${cardPath(card)}/photo`, { method: "POST", body: JSON.stringify({ content_type: type }) });
  const upload = presign.method === "PUT"
    ? await fetch(presign.url, { method: "PUT", body: file, headers: presign.headers })
    : await fetch(presign.url, { method: "POST", body: (() => {
      const form = new FormData();
      Object.entries(presign.fields ?? {}).forEach(([key, value]) => form.append(key, value));
      form.append("file", file);
      return form;
    })() });
  if (!upload.ok) throw new Error(t`Upload failed (${upload.status})`);
  return memberRequest(`${cardPath(card)}/photo`, { method: "PUT",
    body: JSON.stringify({ object_key: presign.object_key, consent: true }) });
}

type PassJob = { id: number; state: string; save_url: string; download_ready: boolean };

/** A pass is made by a short server job: wait for it, then open Google's save link or the Apple pass. */
export function useWalletPass(card: MyCard) {
  return useMutation({ mutationFn: async (platform: string) => {
    let job = await memberRequest<PassJob>(`${cardPath(card)}/wallet/${platform}`, { method: "POST" });
    for (let tries = 0; tries < 30 && (job.state === "queued" || job.state === "running"); tries += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      job = await memberRequest<PassJob>(`/member/card-jobs/${job.id}`);
    }
    if (job.state !== "succeeded") throw new Error(t`The wallet pass isn't ready. Try again in a minute.`);
    const target = job.save_url || (await memberRequest<{ url: string }>(`/member/card-jobs/${job.id}/result`)).url;
    window.location.assign(target);
  } });
}

export function useAcceptInvite() {
  return useMutation({ mutationFn: (input: { card: number; invite: string }) =>
    memberRequest<{ card_id: number; status: string }>("/member/id-programme-invites/accept", { method: "POST", body: JSON.stringify(input) }) });
}
