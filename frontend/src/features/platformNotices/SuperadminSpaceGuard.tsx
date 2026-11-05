import { useEffect } from "react";
import { Icon } from "../../components/ui";
import { toneSurfaceClasses } from "../../components/ui/tones";
import { setStaffWriteGuard } from "../../lib/api/requests";
import type { NoticeSpace } from "./platformNoticesApi";

const ACKNOWLEDGED_FOR_MS = 10 * 60_000;
const acknowledged = new Map<number, number>();

export function superadminWarning(notice: NoticeSpace) {
  const state = notice.state === "read_only" ? "read-only" : "paused";
  return `You are acting as the platform superadmin in ${notice.name}, which is ${state}. Your changes are allowed and recorded in the audit log.`;
}

/** Asks once per space every ten minutes; the platform controls themselves never ask. */
export function superadminWriteGuard(notice: NoticeSpace, confirm: (message: string) => boolean = window.confirm.bind(window)) {
  return (path: string) => {
    if (path.startsWith("/admin/platform/")) return true;
    const at = acknowledged.get(notice.id);
    if (at !== undefined && Date.now() - at < ACKNOWLEDGED_FOR_MS) return true;
    const ok = confirm(`${superadminWarning(notice)}

Continue with this change?`);
    if (ok) acknowledged.set(notice.id, Date.now());
    return ok;
  };
}

export function resetSuperadminAcknowledgements() {
  acknowledged.clear();
}

/**
 * #195 (#110/#190): nothing is switched off for the superadmin, so writes in a paused or read-only
 * space are allowed (and audited by the server). The console says so plainly and confirms first.
 */
export function SuperadminSpaceGuard({ notice }: { notice?: NoticeSpace }) {
  useEffect(() => {
    if (!notice) return undefined;
    setStaffWriteGuard(superadminWriteGuard(notice));
    return () => setStaffWriteGuard(null);
  }, [notice]);
  if (!notice) return null;
  return <div role="alert" className={`mb-4 flex min-w-0 items-start gap-3 rounded-xl border p-4 ${toneSurfaceClasses.warn}`}>
    <Icon name="TriangleAlert" />
    <p className="min-w-0 flex-1 text-sm [overflow-wrap:anywhere]"><strong>{superadminWarning(notice)}</strong> You will be asked to
      confirm before your first change.</p>
  </div>;
}
