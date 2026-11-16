import { staffRequest } from "../../lib/api";

/** A Space Manager's request to move the space to its own server (#128 C-23). Status only. */
export type SelfHostMoveRequest = {
  id: string;
  status: "requested" | "approved" | "exporting" | "exported" | "rejected" | "failed" | "cancelled";
  status_label: string;
  note: string;
  requested_at: string;
  decided_at: string | null;
  decision_note: string;
  exported_at: string | null;
};
export type SelfHostMoveStatus = { request: SelfHostMoveRequest | null };

const path = (makerspaceId: number) => `/admin/makerspace/${makerspaceId}/selfhost-move-request`;
export const getSelfHostMove = (makerspaceId: number) => staffRequest<SelfHostMoveStatus>(path(makerspaceId));
export const requestSelfHostMove = (makerspaceId: number, note: string) =>
  staffRequest<SelfHostMoveStatus>(path(makerspaceId), { method: "POST", body: JSON.stringify({ note }) });
