import { Clock, MapPin } from "lucide-react";
import { ActionControl } from "../../components/ui";
import type { Action } from "../../components/ui";
import type { TenantBootstrap } from "../../lib/api";
import { safeUrl } from "./MakerspaceMoreSections";
import { summariseHours } from "./openingHours";

type Props = { name: string; bootstrap: TenantBootstrap; actions: Action[] };

/** The page's one h1: logo, name, where it is, when it is open, and the jumps a visitor most often needs. */
export function MakerspaceHeader({ name, bootstrap, actions }: Props) {
  const { makerspace, branding } = bootstrap;
  const location = makerspace.location?.trim() ?? "";
  const mapUrl = safeUrl(makerspace.map_url?.trim());
  const hours = summariseHours(makerspace.opening_hours, makerspace.timezone);
  const lede = branding.welcome_body?.trim();
  return <header className="mb-10 grid gap-5" aria-labelledby="makerspace-title">
    {makerspace.cover_image_url ? <img src={makerspace.cover_image_url} alt="" className="h-40 w-full rounded-2xl border border-line object-cover sm:h-56" /> : null}
    <div className="flex min-w-0 flex-wrap items-center gap-4">
      {makerspace.logo_url ? <img src={makerspace.logo_url} alt={`${name} logo`} className="h-16 w-16 shrink-0 rounded-xl border border-line bg-panel object-contain" /> : null}
      <div className="min-w-0 flex-1 basis-56">
        <h1 id="makerspace-title" className="break-words font-accent text-3xl leading-10 font-semibold text-ink sm:text-4xl sm:leading-[48px]">{name}</h1>
        {lede ? <p className="mt-2 max-w-2xl text-base leading-6 text-muted">{lede}</p> : null}
      </div>
    </div>
    {location || mapUrl || hours ? <dl className="grid gap-3 text-sm sm:flex sm:flex-wrap sm:gap-x-8">
      {location || mapUrl ? <div className="flex min-w-0 items-start gap-2">
        <dt><MapPin aria-hidden="true" size={18} className="mt-0.5 text-muted" /><span className="sr-only">Location</span></dt>
        <dd className="min-w-0 [overflow-wrap:anywhere]">{location}{mapUrl ? <>{location ? " · " : null}
          <a className="font-semibold text-brand-ink underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            href={mapUrl} target="_blank" rel="noopener noreferrer">Get directions</a></> : null}</dd>
      </div> : null}
      {hours ? <div className="flex min-w-0 items-start gap-2">
        <dt><Clock aria-hidden="true" size={18} className="mt-0.5 text-muted" /><span className="sr-only">Opening hours</span></dt>
        <dd className="min-w-0">
          <details>
            <summary className="cursor-pointer rounded-control font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{hours.today}</summary>
            <table className="mt-2 text-sm"><caption className="sr-only">Weekly opening hours</caption><tbody>
              {hours.week.map((row) => <tr key={row.day} className={row.isToday ? "font-semibold text-ink" : "text-muted"}>
                <th scope="row" className="py-0.5 pr-4 text-left font-[inherit]">{row.day}</th><td className="tabular-nums">{row.hours}</td>
              </tr>)}
            </tbody></table>
          </details>
        </dd>
      </div> : null}
    </dl> : null}
    {actions.length ? <nav aria-label="Quick actions" className="flex flex-wrap gap-2">
      {actions.map((action, index) => <ActionControl key={action.label} action={action} primary={index === 0} className={index === 0 ? "desk-button-brand" : undefined} />)}
    </nav> : null}
  </header>;
}
