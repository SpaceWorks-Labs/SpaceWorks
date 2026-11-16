import { t } from "@lingui/core/macro";
import { Avatar } from "../../components/ui/Avatar";
import { RouteLink } from "../../components/ui/RouteLink";
import { statusLabel } from "../profile/view/profileCopy";
import type { StatusPreset } from "../profile/accountProfileTypes";
import type { PersonCard as Card } from "./api";

/** What the person is doing, as a short readable line (preset first, then their own note). */
export function cardStatusLine(card: Card): string {
  if (!card.status) return "";
  const preset = statusLabel(card.status.preset as StatusPreset);
  return [preset, card.status.note].filter(Boolean).join(" · ");
}

/** One checked-in person. `tv` makes it larger and non-interactive for the display screen. */
export function PersonCard({ card, tv = false }: { card: Card; tv?: boolean }) {
  const line = cardStatusLine(card);
  const body = <>
    {card.avatar_url
      ? <img src={card.avatar_url} alt="" className={`${tv ? "h-20 w-20" : "h-11 w-11"} shrink-0 rounded-full object-cover`} loading="lazy" />
      : <Avatar name={card.display_name} size={tv ? "lg" : "md"} />}
    <span className="min-w-0">
      <span className={`block break-words font-semibold text-ink ${tv ? "text-3xl" : "text-base"}`}>{card.display_name}</span>
      {card.headline ? <span className={`block break-words text-muted ${tv ? "text-xl" : "text-sm"}`}>{card.headline}</span> : null}
      {line ? <span className={`block break-words text-ink ${tv ? "text-lg" : "text-sm"}`}>{line}</span> : null}
      {card.skills.length ? <span className="mt-1 flex flex-wrap gap-1" aria-label={t`Skills`}>
        {card.skills.map((skill) => <span key={skill} className={`rounded-full border border-line px-2 py-0.5 text-muted ${tv ? "text-base" : "text-xs"}`}>{skill}</span>)}
      </span> : null}
    </span>
  </>;
  const shell = `flex items-start gap-3 rounded-xl border border-line bg-panel ${tv ? "p-6" : "p-4"}`;
  return !tv && card.handle
    ? <RouteLink href={`/${encodeURIComponent(card.handle)}`} className={`${shell} hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus`}>{body}</RouteLink>
    : <div className={shell}>{body}</div>;
}

/** "+ 7 makers in": the people who are here but not named to this audience. */
export function othersLabel(count: number, namedAny: boolean): string {
  if (count <= 0) return "";
  return namedAny ? t`+ ${count} more here` : t`${count} here now`;
}
