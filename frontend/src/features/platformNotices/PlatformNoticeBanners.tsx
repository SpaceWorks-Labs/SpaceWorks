import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Icon } from "../../components/ui";
import { toneSurfaceClasses } from "../../components/ui/tones";
import type { Tone } from "../../components/ui";
import { READ_ONLY_LEAD, spaceNotice, useDismissedAnnouncements, type NoticeAnnouncement, type PlatformNotices } from "./platformNoticesApi";

const TONES: Record<NoticeAnnouncement["severity"], Tone> = { info: "info", maintenance: "warn", policy: "info", warning: "warn" };
const LEADS: Record<NoticeAnnouncement["severity"], string> = { info: "Announcement", maintenance: "Planned maintenance", policy: "Policy change", warning: "Important" };

function Banner({ tone, children, onDismiss, dismissLabel }: { tone: Tone; children: ReactNode; onDismiss?: () => void; dismissLabel?: string }) {
  return <div role="status" className={`flex min-w-0 items-start gap-3 rounded-xl border p-4 ${toneSurfaceClasses[tone]}`}>
    <Icon name={tone === "warn" ? "TriangleAlert" : "Info"} />
    <div className="min-w-0 flex-1 text-sm [overflow-wrap:anywhere]">{children}</div>
    {onDismiss ? <button type="button" aria-label={dismissLabel} onClick={onDismiss}
      className="-m-2 inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <X aria-hidden="true" size={18} /></button> : null}
  </div>;
}

export type NoticeSurface = "staff" | "member";

/**
 * Announcements that apply here. The server already limits both id lists to the VIEWER's own spaces.
 * Staff screens: those reaching this space (an empty list is the superadmin's "every space").
 * Member screens: only those that reach the viewer as a member, of this space when one is shown.
 */
export function applicableAnnouncements(data: PlatformNotices | undefined, spaceId?: number, surface: NoticeSurface = "staff") {
  return (data?.announcements ?? []).filter(row => {
    if (surface === "member") {
      const ids = row.member_makerspace_ids ?? [];
      return ids.length > 0 && (spaceId === undefined || ids.includes(spaceId));
    }
    return spaceId === undefined || !row.makerspace_ids.length || row.makerspace_ids.includes(spaceId);
  });
}

/**
 * The platform banners above a signed-in screen: live announcements (dismissible, remembered per browser)
 * and, when this space is read-only, why nothing new can be created. Paused spaces never reach here:
 * their shells render the paused page instead.
 */
export function PlatformNoticeBanners({ data, space, surface = "staff" }: {
  data: PlatformNotices | undefined; space?: { id?: number; slug?: string }; surface?: NoticeSurface;
}) {
  const { ids, dismiss } = useDismissedAnnouncements();
  const readOnly = space ? spaceNotice(data, space) : undefined;
  const announcements = applicableAnnouncements(data, space?.id, surface).filter(row => !ids.includes(row.id));
  if (!announcements.length && readOnly?.state !== "read_only") return null;
  return <div className="mb-4 grid gap-3" aria-label={t`Platform notices`} role="region">
    {readOnly?.state === "read_only" ? <Banner tone="warn">
      <p><strong>{READ_ONLY_LEAD}</strong>{readOnly.reason ? <> {readOnly.reason}</> : null}</p>
    </Banner> : null}
    {announcements.map(row => <Banner key={row.id} tone={TONES[row.severity] ?? "info"} onDismiss={() => dismiss(row.id)} dismissLabel={`Dismiss announcement: ${row.title}`}>
      <p><span className="sr-only">{LEADS[row.severity] ?? t`Announcement`}: </span><strong>{row.title}</strong></p>
      <p className="mt-1 whitespace-pre-line">{row.body}</p>
    </Banner>)}
  </div>;
}
