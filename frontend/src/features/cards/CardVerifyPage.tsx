// /verify/c/:token — the public card check. Valid, expired or revoked; the issuer and what the
// card is for; the holder's name and photo only when they opted in. Never indexed.
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { StructuredApiError, publicV1Request } from "../../lib/api";

type Verification = {
  status: "valid" | "expired" | "revoked"; valid: boolean;
  issuer: { kind: "space" | "organisation" | "event"; name: string; logo_url: string | null };
  label: string | null; number: string | null; valid_until: string | null;
  holder: { name: string | null; photo_url: string | null } | null; note: string; checked_at: string;
};

const TITLES = { valid: "This card is valid", expired: "This card has expired", revoked: "This card is not valid" } as const;
const TONES = { valid: "success", expired: "warn", revoked: "danger" } as const;

function useNoIndex() {
  useEffect(() => {
    const meta = Object.assign(document.createElement("meta"), { name: "robots", content: "noindex, nofollow, noarchive" });
    const referrer = Object.assign(document.createElement("meta"), { name: "referrer", content: "no-referrer" });
    document.head.append(meta, referrer);
    return () => { meta.remove(); referrer.remove(); };
  }, []);
}

export function CardVerifyPage() {
  const { token = "" } = useParams();
  useNoIndex();
  const check = useQuery({ queryKey: ["card-verify", token], retry: false, staleTime: 0, gcTime: 0,
    queryFn: () => publicV1Request<Verification>(`/public/card-verifications/${encodeURIComponent(token)}`) });
  const missing = check.error instanceof StructuredApiError && check.error.status === 404;
  const limited = check.error instanceof StructuredApiError && check.error.status === 429;
  const data = check.data;
  if (!data) return <CenteredCardLayout state={check.isLoading ? { status: "loading" } : { status: "ready" }}
    media={{ icon: "ShieldAlert", tone: "danger" }} title={missing ? "We can't find this card" : "The check didn't work"}
    body={missing ? "The link may be mistyped, or the card's check link was changed. Ask the holder to show their card again."
      : limited ? "Too many checks from here. Wait a minute and try again." : "Try again in a moment."}
    primary={{ label: "Try again", onClick: () => void check.refetch() }} />;

  const facts = [["Issued by", data.issuer.name], ["Card", data.label], ["Number", data.number], ["Valid until", data.valid_until]]
    .filter((row): row is [string, string] => Boolean(row[1]));
  return <CenteredCardLayout state={{ status: "ready" }} media={{ banner: TONES[data.status] }} eyebrow="Card check" title={TITLES[data.status]}
    body={data.note || (data.valid ? "Checked just now." : "Do not accept this card.")}
    content={<div className="grid gap-4">
      {data.holder?.photo_url || data.holder?.name ? <div className="flex items-center gap-3">
        {data.holder.photo_url ? <img src={data.holder.photo_url} alt="" className="h-16 w-16 rounded-control border border-line object-cover" /> : null}
        {data.holder.name ? <p className="text-lg font-semibold text-ink">{data.holder.name}</p> : null}
      </div> : null}
      <dl className="grid gap-2 text-sm sm:grid-cols-[auto_1fr] sm:gap-x-4">
        {facts.map(([label, value]) => <div key={label} className="contents"><dt className="text-muted">{label}</dt><dd className="text-ink">{value}</dd></div>)}
      </dl>
      <p className="text-xs text-muted">Checked {new Date(data.checked_at).toLocaleString()}.</p>
    </div>}
    primary={{ label: "Check again", onClick: () => void check.refetch() }} />;
}
