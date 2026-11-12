// /verify/c/:token — the public card check (SPEC §7, the public-verify-card screens). Valid,
// expired or revoked in a status band; the issuer and what the card is for; the holder's name
// and photo only when they opted in. Never indexed, never sends a referrer.
import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CalendarX, SearchX, ShieldOff, type LucideIcon } from "lucide-react";
import { useParams } from "react-router-dom";

import { useDelight, useReducedMotion } from "../../components/delight/DelightProvider";
import { AnimatedLogoMark } from "../../components/brand/AnimatedLogoMark";
import { StructuredApiError, publicV1Request } from "../../lib/api";
import { spaceNounTitle, type SpaceKind } from "../../lib/spaceNoun";
import { VerifyStaffPanel } from "./VerifyStaffPanel";
import "./cardVerify.css";
import { LogoLoader } from "../../components/LogoLoader";

type Verification = {
  status: "valid" | "expired" | "revoked"; valid: boolean;
  // `space_noun` (decision 295) says whether a space issuer is a makerspace or an organization
  // workspace; typed here until the verify serializer sends it (absent = no kind line).
  issuer: { kind: "space" | "organisation" | "event"; name: string; logo_url: string | null; space_noun?: SpaceKind };
  label: string | null; number: string | null; valid_until: string | null;
  holder: { name: string | null; photo_url: string | null } | null; note: string; checked_at: string; timezone?: string;
};

const BANDS: Record<Verification["status"], { icon: LucideIcon; title: string; body: string; className: string }> = {
  valid: { icon: BadgeCheck, title: t`Valid card`, body: t`This card is genuine and in date.`, className: "bg-success text-on-success" },
  expired: { icon: CalendarX, title: t`Expired card`, body: t`This card was genuine but is no longer in date.`, className: "bg-warn-soft text-warn-ink" },
  revoked: { icon: ShieldOff, title: t`Revoked card`, body: t`This card has been cancelled by its issuer.`, className: "border-b border-danger-line bg-panel text-danger" },
};
const LABELS = { space: t`Plan`, organisation: t`Programme`, event: t`Event` } as const;

function useNoIndex() {
  useEffect(() => {
    const meta = Object.assign(document.createElement("meta"), { name: "robots", content: "noindex, nofollow, noarchive" });
    const referrer = Object.assign(document.createElement("meta"), { name: "referrer", content: "no-referrer" });
    document.head.append(meta, referrer);
    return () => { meta.remove(); referrer.remove(); };
  }, []);
}

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]?.toUpperCase() ?? "").join("");
}

export function checkedLine(data: Pick<Verification, "checked_at" | "timezone">) {
  const zone = data.timezone || "UTC";
  let time: string;
  try {
    time = new Intl.DateTimeFormat(formatLocale(), { dateStyle: "medium", timeStyle: "short", timeZone: zone }).format(new Date(data.checked_at));
  } catch {
    time = new Date(data.checked_at).toLocaleString(formatLocale());
  }
  return `Checked ${time} (${zone}).`;
}

function Shell({ children }: { children: ReactNode }) {
  return <main className="min-h-dvh bg-bg px-4 py-6 text-ink sm:px-8">
    <AnimatedLogoMark variant="horizontal" size={180} />
    <div className="mx-auto mt-10 w-full max-w-[420px]">{children}</div>
  </main>;
}

export function CardVerifyPage() {
  const { token = "" } = useParams();
  useNoIndex();
  const delight = useDelight();
  const reduced = useReducedMotion();
  const check = useQuery({ queryKey: ["card-verify", token], retry: false, staleTime: 0, gcTime: 0,
    queryFn: () => publicV1Request<Verification>(`/public/card-verifications/${encodeURIComponent(token)}`) });
  const limited = check.error instanceof StructuredApiError && check.error.status === 429;
  const data = check.data;

  if (check.isLoading) return <Shell><LogoLoader label={t`Checking the card…`} size={48} className="min-h-16 py-3" /></Shell>;
  if (!data) return <Shell><section className="grid justify-items-center gap-3 rounded-card border border-line bg-panel p-8 text-center">
    <SearchX size={56} aria-hidden="true" className="text-muted" />
    <h1 className="text-xl font-semibold">{limited ? t`Too many checks` : t`Card not found`}</h1>
    <p className="text-sm text-muted">{limited ? t`Too many checks. Try again in a minute.`
      : t`We couldn't match this code to a card. Check the whole code was scanned, or ask to see the card again.`}</p>
    <button type="button" className="desk-button min-h-11" onClick={() => void check.refetch()}>{t`Check again`}</button>
  </section></Shell>;

  const band = BANDS[data.status];
  const Icon = band.icon;
  const stamp = data.valid && delight.enabled && !reduced;
  const holderName = data.status === "revoked" ? null : data.holder?.name ?? null;
  // A revoked card shows its issuer alone (SPEC §7), whatever else arrives.
  const facts = data.status === "revoked" ? [] : [[LABELS[data.issuer.kind], data.label], [t`Number`, data.number],
    [t`Valid until`, data.valid_until]].filter((row): row is [string, string] => Boolean(row[1]));
  return <Shell><section className="overflow-hidden rounded-card border border-line bg-panel" aria-labelledby="card-check-title">
    <div className={`grid justify-items-center gap-2 px-6 py-6 text-center ${band.className}`}>
      <Icon size={56} aria-hidden="true" className={stamp ? "sw-verify-stamp" : undefined} />
      <h1 id="card-check-title" className="text-xl font-semibold">{band.title}</h1>
      <p className="text-sm">{band.body}</p>
    </div>
    <div className="grid gap-4 p-6">
      <div className="flex items-center gap-3">
        {data.status === "valid" && data.holder?.photo_url ? <img src={data.holder.photo_url} alt="" className="h-14 w-14 rounded-full border border-line object-cover" />
          : holderName ? <span aria-hidden="true" className="grid h-14 w-14 place-items-center rounded-full bg-surface text-lg font-semibold">{initials(holderName)}</span>
            : data.issuer.logo_url ? <img src={data.issuer.logo_url} alt="" className="h-14 w-14 rounded-control border border-line bg-white object-contain p-1" />
              : null}
        <div className="grid">
          {holderName ? <p className="text-lg font-semibold">{holderName}</p> : null}
          <p className={holderName ? "text-sm text-muted" : "text-lg font-semibold"}>{data.issuer.name}</p>
          {data.issuer.kind === "space" && data.issuer.space_noun ? <p className="text-xs text-muted">{spaceNounTitle(data.issuer.space_noun)}</p> : null}
        </div>
      </div>
      {data.note ? <p className="text-sm text-muted">{data.note}</p> : null}
      {facts.length ? <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {facts.map(([label, value]) => <div key={label} className="grid gap-0.5"><dt className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">{label}</dt>
          <dd className="font-medium tabular-nums">{value}</dd></div>)}
      </dl> : null}
      <p className="border-t border-line pt-4 text-xs text-muted">{t`Space Works checks this card against ${data.issuer.name}'s records and shows only what is needed to confirm it. ${checkedLine(data)}`}</p>
    </div>
  </section>
    <VerifyStaffPanel token={token} onChanged={() => void check.refetch()} />
  </Shell>;
}
