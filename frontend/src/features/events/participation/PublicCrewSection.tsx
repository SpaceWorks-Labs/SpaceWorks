import { useQuery } from "@tanstack/react-query";
import { publicV1Request } from "../../../lib/api";

type CrewCard = { handle: string; display_name: string; crew_role: string };

/**
 * The event's public crew section (opt-in per event): only crew who chose to be shown AND
 * hold a public profile appear (#25). Nothing renders when the list is empty.
 */
export function PublicCrewSection({ publicToken, profileHref }: { publicToken: string; profileHref: (handle: string) => string }) {
  const crew = useQuery({ queryKey: ["public-event-crew", publicToken], retry: false,
    queryFn: () => publicV1Request<CrewCard[]>(`/public/event-programmes/${publicToken}/crew/`) });
  if (!crew.data?.length) return null;
  return <ul className="grid gap-2 sm:grid-cols-2" aria-label="Event crew">
    {crew.data.map(card => <li key={card.handle} className="rounded-lg border border-line p-3">
      <a className="font-semibold text-ink hover:underline" href={profileHref(card.handle)}>{card.display_name}</a>
      {card.crew_role ? <p className="text-sm text-muted">{card.crew_role}</p> : null}
    </li>)}
  </ul>;
}
