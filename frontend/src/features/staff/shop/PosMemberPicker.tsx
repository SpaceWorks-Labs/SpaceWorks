import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { findMembers } from "./staffShopOrdersApi";

export type TillMember = { id: number; name: string };

/** Member prices at the till: find the buyer by name or email, then the quote applies their discount. */
export function PosMemberPicker({ makerspaceId, member, onChange }: {
  makerspaceId: number; member: TillMember | null; onChange: (member: TillMember | null) => void;
}) {
  const [q, setQ] = useState("");
  const term = q.trim();
  const query = useQuery({ queryKey: ["staff-shop", makerspaceId, "members", term], queryFn: () => findMembers(makerspaceId, term),
    enabled: term.length >= 2 && !member });
  if (member) return <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3">
    <span className="min-w-0 flex-1"><span className="block text-sm text-muted">{t`Member`}</span><span className="font-semibold">{member.name}</span></span>
    <button type="button" className="desk-button min-h-11" onClick={() => { onChange(null); setQ(""); }}>{t`Remove member`}</button>
  </div>;
  return <div className="grid gap-2">
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Member (for member prices)`}<input className="desk-input min-h-11 font-normal" type="search" value={q} placeholder={t`Name or email`} onChange={event => setQ(event.target.value)} /></label>
    {term.length >= 2 && query.data ? query.data.length ? <ul className="grid gap-1" aria-label={t`Matching members`}>
      {query.data.slice(0, 6).map(row => <li key={row.id}><button type="button" className="desk-button min-h-11 w-full justify-start"
        onClick={() => onChange(row)}>{row.name}</button></li>)}
    </ul> : <p className="text-sm text-muted">{t`No member matches.`}</p> : null}
  </div>;
}
