import { t } from "@lingui/core/macro";
import { useLocation } from "react-router-dom";
import { readinessHref } from "./readinessHref";
import { CheckCircle2, Clock3, CircleAlert } from "lucide-react";
import { Card } from "../../../components/ui";
import { RouteLink } from "../../../components/ui/RouteLink";
import { eventErrorText } from "../eventUi";
import { useProgrammeQuery, type Readiness } from "./api";
import { LogoLoader } from "../../../components/LogoLoader";

export function EventReadinessPanel({ eventId }: { eventId: number }) {
  const location = useLocation();
  const query = useProgrammeQuery<Readiness>(eventId, "readiness");
  const data = query.data;
  return <section className="grid gap-4" aria-label={t`Readiness and waiting for you`}><h3 className="title-section">{t`Ready for the next maker?`}</h3>
    {query.isLoading ? <LogoLoader size={48} className="min-h-32 py-3" /> : null}
    {query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    {data ? [false, true].map(waiting => <Card key={String(waiting)}><h4 className="mb-3 font-semibold">{waiting ? t`Waiting for you` : t`Event readiness`}</h4>
      <ul className="grid gap-3">{data.items.filter(item => (item.status === "action") === waiting).map(item => { const Icon = item.status === "ready" ? CheckCircle2 : item.status === "action" ? Clock3 : CircleAlert;
        return <li key={item.code} className="flex min-h-11 items-center justify-between gap-3 border-b border-line pb-2"><span className="flex items-center gap-3"><Icon size={20} aria-hidden="true" />{item.label}{item.count !== null ? <span className="rounded-full bg-surface px-2 py-1 text-sm tabular-nums">{item.count}</span> : null}</span>{readinessHref(item.href, eventId, location.pathname) ? <RouteLink className="desk-button" href={readinessHref(item.href, eventId, location.pathname) || item.href}>{t`Review`}</RouteLink> : <span className="text-sm text-muted">{item.status === "ready" ? t`Ready` : item.status === "unavailable" ? t`Unavailable` : t`Needs attention`}</span>}</li>;
      })}</ul>
      {!data.items.some(item => (item.status === "action") === waiting) ? <p className="text-sm text-muted">{waiting ? t`Nothing is waiting for your action.` : t`No readiness checks are available for your access.`}</p> : null}
    </Card>) : null}
  </section>;
}
