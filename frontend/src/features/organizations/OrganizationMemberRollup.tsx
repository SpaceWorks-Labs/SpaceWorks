import { plural, t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { ErrorText } from "../../components/ui";
import { formatLocale } from "../../lib/format";
import { staffRequest } from "../../lib/api";
import { LogoLoader } from "../../components/LogoLoader";

// O-B5 `member-rollup`; typed locally until the staging step regenerates `generated/api.ts`.
export type MemberRollup = {
  people: { total: number; explicit: number; derived_only: number; owned_spaces: number };
  spaces: { name: string; slug: string; active: number; revoked: number }[];
  home_space_card_note: string;
};

export function useMemberRollup(id: number) {
  return useQuery({ queryKey: ["organizations", id, "member-rollup"],
    queryFn: () => staffRequest<MemberRollup>(`/admin/organizations/${id}/member-rollup/`) });
}

const count = (value: number) => value.toLocaleString(formatLocale());

/**
 * Governor roll-up (decision 293): how many people belong to the organization, split into invited
 * members and community members of the spaces it owns, with each owned space's standing counts.
 * Counts only by contract, so no row here can name or identify a person.
 */
export function OrganizationMemberRollup({ organizationId }: { organizationId: number }) {
  const rollup = useMemberRollup(organizationId);
  if (rollup.isLoading) return <LogoLoader size={48} className="min-h-32 py-3" />;
  if (rollup.isError || !rollup.data) return <ErrorText resource={t`member counts`} onRetry={() => { void rollup.refetch(); }} />;
  const { people, spaces } = rollup.data;
  const figures = [
    { label: t`People in total`, value: people.total, help: t`Each person counted once.` },
    { label: t`Invited members`, value: people.explicit, help: t`Joined the organization directly.` },
    { label: t`Through owned spaces`, value: people.derived_only, help: plural(people.owned_spaces, {
      one: "Active community members of the # space it owns.", other: "Active community members of the # spaces it owns." }) },
  ];
  return <div className="grid gap-5">
    <dl className="grid gap-3 sm:grid-cols-3">{figures.map(figure => <div key={figure.label} className="grid content-start gap-1 rounded-xl border border-line bg-panel p-4">
      <dt className="text-sm font-semibold text-ink">{figure.label}</dt>
      <dd className="order-first text-3xl font-semibold tabular-nums text-ink">{count(figure.value)}</dd>
      <dd className="text-sm text-muted">{figure.help}</dd>
    </div>)}</dl>
    {spaces.length ? <div className="overflow-x-auto rounded-xl border border-line bg-panel">
      <table className="w-full min-w-[20rem] text-sm">
        <caption className="sr-only">{t`Community members in each space the organization owns`}</caption>
        <thead><tr className="border-b border-line text-left text-muted">
          <th scope="col" className="px-4 py-2 font-semibold">{t`Space`}</th>
          <th scope="col" className="px-4 py-2 text-right font-semibold">{t`Active`}</th>
          <th scope="col" className="px-4 py-2 text-right font-semibold">{t`Revoked`}</th>
        </tr></thead>
        <tbody className="divide-y divide-line">{spaces.map(space => <tr key={space.slug}>
          <th scope="row" className="px-4 py-3 text-left font-normal text-ink [overflow-wrap:anywhere]">{space.name}</th>
          <td className="px-4 py-3 text-right tabular-nums text-ink">{count(space.active)}</td>
          <td className="px-4 py-3 text-right tabular-nums text-muted">{count(space.revoked)}</td>
        </tr>)}</tbody>
      </table>
    </div> : <p className="text-sm text-muted">{t`This organization owns no spaces yet, so only invited members are counted.`}</p>}
    <p className="max-w-[65ch] text-sm text-muted">{t`Counts only: names stay with each space. Member cards are issued by the home space; there is no separate organization card.`}</p>
  </div>;
}
