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

/** Announcements that apply here: every-space ones, plus those naming this space. Without a space, all of them. */
export function applicableAnnouncements(data: PlatformNotices | undefined, spaceId?: number) {
  return (data?.announcements ?? []).filter(row => spaceId === undefined || !row.makerspace_ids.length || row.makerspace_ids.includes(spaceId));
}

/**
 * The platform banners above a signed-in screen: live announcements (dismissible, remembered per browser)
 * and, when this space is read-only, why nothing new can be created. Paused spaces never reach here:
 * their shells render the paused page instead.
 */
export function PlatformNoticeBanners({ data, space }: { data: PlatformNotices | undefined; space?: { id?: number; slug?: string } }) {
  const { ids, dismiss } = useDismissedAnnouncements();
  const readOnly = space ? spaceNotice(data, space) : undefined;
  const announcements = applicableAnnouncements(data, space?.id).filter(row => !ids.includes(row.id));
  if (!announcements.length && readOnly?.state !== "read_only") return null;
  return <div className="mb-4 grid gap-3" aria-label="Platform notices" role="region">
    {readOnly?.state === "read_only" ? <Banner tone="warn">
      <p><strong>{READ_ONLY_LEAD}</strong>{readOnly.reason ? <> {readOnly.reason}</> : null}</p>
    </Banner> : null}
    {announcements.map(row => <Banner key={row.id} tone={TONES[row.severity] ?? "info"} onDismiss={() => dismiss(row.id)} dismissLabel={`Dismiss announcement: ${row.title}`}>
      <p><span className="sr-only">{LEADS[row.severity] ?? "Announcement"}: </span><strong>{row.title}</strong></p>
      <p className="mt-1 whitespace-pre-line">{row.body}</p>
    </Banner>)}
  </div>;
}
