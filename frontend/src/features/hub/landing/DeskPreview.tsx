import { t } from "@lingui/core/macro";
import { CalendarDays, Camera, Check, DoorOpen, Inbox, LayoutDashboard, Package, Printer, QrCode, ShoppingBag, Users } from "lucide-react";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { requestStatusLabel } from "../../../components/ui/StatusStepper";

type Row = { initials: string; name: string; item: string; meta: string; status: string; selected?: boolean };

function rows(): Row[] {
  return [
    { initials: "AN", name: t`Asha N.`, item: t`Soldering station SS-03`, meta: t`Requested today, 10:12`, status: "pending_approval" },
    { initials: "TR", name: t`Tom R.`, item: t`Cordless drill kit`, meta: t`Pickup today, 14:00`, status: "accepted", selected: true },
    { initials: "ML", name: t`Mei L.`, item: t`Oscilloscope`, meta: t`Due back Friday`, status: "issued" },
    { initials: "DP", name: t`Diego P.`, item: t`Multimeter × 3`, meta: t`2 of 3 back`, status: "partially_returned" },
    { initials: "SK", name: t`Sam K.`, item: t`Hot air station`, meta: t`Return photo and remark`, status: "returned" },
  ];
}

function nav() {
  return [
    { icon: LayoutDashboard, label: t`Dashboard` }, { icon: Inbox, label: t`Requests`, active: true },
    { icon: Package, label: t`Inventory` }, { icon: Printer, label: t`Machines` }, { icon: CalendarDays, label: t`Events` },
    { icon: DoorOpen, label: t`Bookings` }, { icon: ShoppingBag, label: t`Shop` }, { icon: Users, label: t`Members` },
  ];
}

/**
 * A still glimpse of the staff console's request queue, drawn with the console's own tokens, status
 * pills and request wording (requestStatusLabel), so it recolours with the theme like the real screen.
 * Sample data, no controls: nothing in it is focusable, and the caption says what it is. In the hero
 * sequence the request list (`data-seq="content"`) is the surface the view zooms through.
 */
export function DeskPreview() {
  const list = rows();
  return <figure className="sw-hub-desk" aria-labelledby="desk-preview-caption" data-seq="figure">
    <div className="sw-hub-desk-bar" aria-hidden="true">
      <span className="whitespace-nowrap font-semibold text-ink">{t`Staff console`}</span>
      <span className="code-text hidden truncate text-muted sm:inline">{t`your-space.example/admin/requests`}</span>
    </div>
    <div className="sw-hub-desk-body">
      <ul className="sw-hub-desk-nav" aria-label={t`Console areas`}>
        {nav().map(({ icon: Icon, label, active }) => <li key={label} className={active ? "sw-hub-desk-nav-active" : undefined}>
          <Icon size={18} aria-hidden="true" />{label}</li>)}
      </ul>
      <div className="min-w-0" data-seq="content">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-5">
          <p className="font-display text-xl font-extrabold text-ink">{t`Requests`}</p>
          <p className="text-sm text-muted">{t`1 waiting for review · 1 ready for pickup`}</p>
        </div>
        <ul className="mt-4 border-t border-line">
          {list.map(row => <li key={row.initials} className="sw-hub-desk-row" data-selected={row.selected || undefined}>
            <span className="sw-hub-desk-avatar" aria-hidden="true">{row.initials}</span>
            <span className="grid min-w-0">
              <span className="truncate font-semibold text-ink">{row.item}</span>
              <span className="truncate text-sm text-muted">{row.name} · {row.meta}</span>
            </span>
            <StatusBadge status={row.status} label={requestStatusLabel(row.status)} />
          </li>)}
        </ul>
      </div>
      <div className="sw-hub-desk-detail">
        <p className="text-sm text-muted">{t`Tom R. · pickup today, 14:00`}</p>
        <p className="mt-1 font-display text-lg font-extrabold text-ink">{t`Cordless drill kit`}</p>
        <p className="mt-5 text-sm font-semibold text-ink">{t`Before it leaves the desk`}</p>
        <ul className="mt-2 grid gap-2 text-sm">
          <li className="sw-hub-desk-check" data-done><QrCode size={16} aria-hidden="true" />{t`Box QR scanned`}<Check size={16} className="ml-auto text-success-ink" aria-hidden="true" /></li>
          <li className="sw-hub-desk-check"><Camera size={16} aria-hidden="true" />{t`Issue photo`}<span className="ml-auto text-muted">{t`Needed`}</span></li>
        </ul>
        <span className="sw-hub-desk-issue" aria-hidden="true">{t`Issue`}</span>
        <p className="mt-2 text-xs text-muted">{t`Issuing needs both the box scan and the photo.`}</p>
      </div>
    </div>
    <figcaption id="desk-preview-caption" className="sw-hub-desk-caption">{t`Sample data: the staff console’s request queue, in this theme.`}</figcaption>
  </figure>;
}
