import { t } from "@lingui/core/macro";

import { joinPhotoPresign, type JoinFieldModes, type JoinFieldsInput } from "../membershipAdmissionApi";
import { e164, type JoinExtrasDraft } from "./joinFieldsModel";

/**
 * Parity O-B2: put the join-form photo in the bucket's staging area. Presign, then upload straight to
 * storage (no auth header; a multipart POST lets the browser set its own boundary). Nothing is attached
 * here: the key travels with the join request, which the server checks and applies on activation.
 */
export async function uploadJoinPhoto(makerspaceId: number, file: File, planId?: number | null) {
  const presigned = await joinPhotoPresign(makerspaceId, file.type || "image/jpeg", planId);
  const response = presigned.method === "PUT"
    ? await fetch(presigned.url, { method: "PUT", body: file, headers: presigned.headers })
    : await fetch(presigned.url, { method: "POST", body: (() => {
      const form = new FormData();
      Object.entries(presigned.fields ?? {}).forEach(([key, value]) => form.append(key, value));
      form.append("file", file);
      return form;
    })() });
  if (!response.ok) throw new Error(t`The photo did not upload (storage answered ${response.status}). Try again.`);
  return { object_key: presigned.object_key, content_type: presigned.content_type, consent: true as const };
}

/** The `join_fields` payload for a draft: uploads the photo first when one was chosen. Undefined = send nothing. */
export async function joinFieldsInput(makerspaceId: number, modes: JoinFieldModes, draft: JoinExtrasDraft, planId?: number | null): Promise<JoinFieldsInput | undefined> {
  const input: JoinFieldsInput = {};
  const phone = e164(draft);
  if (modes.phone !== "hidden" && phone) input.phone = phone;
  if (modes.state !== "hidden" && draft.state_code) input.state_code = draft.state_code;
  if (modes.photo !== "off" && draft.photo && draft.consent) input.photo = await uploadJoinPhoto(makerspaceId, draft.photo, planId);
  return Object.keys(input).length ? input : undefined;
}
