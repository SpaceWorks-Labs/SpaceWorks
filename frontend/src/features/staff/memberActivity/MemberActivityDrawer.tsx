import { t } from "@lingui/core/macro";
import { useSearchParams } from "react-router-dom";

import { DetailLayout } from "../../../components/layouts/DetailLayout";
import { MemberActivitySection } from "./MemberActivitySection";

/**
 * `Members?member=<user id>`: the member 360 opened from a cross-link (an incident's involved
 * person, a booking's requester, a shop order's buyer) without first finding the roster row.
 */
export function MemberActivityDrawer({ makerspaceId, title }: { makerspaceId: number; title?: string }) {
  const [params, setParams] = useSearchParams();
  const userId = Number(params.get("member"));
  if (!Number.isInteger(userId) || userId <= 0) return null;
  const close = () => setParams(current => { const next = new URLSearchParams(current); next.delete("member"); return next; });
  return <DetailLayout presentation="drawer" open onClose={close} title={title ?? t`Member activity`}
    identity={{ kind: "icon", icon: "User", tone: "accent" }} state={{ status: "ready" }}
    main={<MemberActivitySection makerspaceId={makerspaceId} userId={userId} />} />;
}
