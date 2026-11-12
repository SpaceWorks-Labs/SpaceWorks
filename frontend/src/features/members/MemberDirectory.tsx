import { plural, t } from "@lingui/core/macro";
import { EmptyState, ListRow } from "../../components/ui";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { memberRequest } from "../../lib/api";
import { LogoLoader } from "../../components/LogoLoader";

type DirectoryEntry = {
  membership_id: number;
  display_name: string;
  headline: string;
  avatar_url: string | null;
};

type Directory = { members: DirectoryEntry[]; hidden_count: number };

/**
 * Who else is here. Fed by the global account profile, but this space-scoped list shows a name, a headline and an
 * avatar and nothing else: the full profile lives at the member's own address. Members whose profile is hidden (or whose
 * account is restricted) are only counted, so "see who else is here" is not an address harvest or a way to probe hidden profiles.
 */
export function MemberDirectory({ makerspaceId }: { makerspaceId: number }) {
  const [search, setSearch] = useState("");
  const directory = useQuery({
    queryKey: ["member", "directory", makerspaceId],
    queryFn: () => memberRequest<Directory>(`/member/makerspaces/${makerspaceId}/directory`),
    retry: false,
  });

  if (directory.isLoading) {
    return <LogoLoader label={t`Loading members…`} size={48} className="min-h-16 py-3" />;
  }
  if (directory.isError) return <section className="desk-panel p-5"><p role="alert" className="text-sm text-danger">{directory.error instanceof Error ? directory.error.message : t`Unable to load members.`}</p></section>;

  const entries = (directory.data?.members ?? []).filter(entry => `${entry.display_name} ${entry.headline}`.toLowerCase().includes(search.toLowerCase()));
  const hidden = directory.data?.hidden_count ?? 0;

  return (
    <section className="desk-panel p-5">
      <h2 className="title-panel">{t`Members`}</h2>
      <label className="mt-3 grid gap-1 text-sm sm:max-w-sm">{t`Search members`}<input className="desk-input" type="search" value={search} onChange={event => setSearch(event.target.value)} /></label>
      {entries.length === 0 ? (
        <EmptyState message={search ? t`No members match. Try another name.` : t`No members have shared a profile yet.`} />
      ) : (
        <ul className="mt-3 space-y-2">
          {entries.map(entry => <li key={entry.membership_id}><ListRow title={entry.display_name}
            identity={entry.avatar_url ? { kind: "image", src: entry.avatar_url } : { kind: "avatar", name: entry.display_name, seed: String(entry.membership_id) }}
            meta={entry.headline} /></li>)}
        </ul>
      )}
      {hidden > 0 ? (
        <p className="mt-3 text-sm text-muted">
          {plural(hidden, { one: "# more member has not published a profile.", other: "# more members have not published a profile." })}
        </p>
      ) : null}
    </section>
  );
}
