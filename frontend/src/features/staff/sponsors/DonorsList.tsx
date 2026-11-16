import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { EmptyState, ListRow } from "../../../components/ui";
import { formatMoney } from "../../../lib/money";
import { financeError } from "../../finance/financeApi";
import { donationStaffApi, donationStaffKeys } from "./staffDonationsApi";

/** Who gave, how much and how often. Never a PAN or address; masked for a superadmin without a PII window. */
export function DonorsList({ makerspaceId }: { makerspaceId: number }) {
  const donors = useQuery({ queryKey: donationStaffKeys.donors(makerspaceId), queryFn: () => donationStaffApi.donors(makerspaceId) });
  if (donors.isLoading) return <LogoLoader label={t`Loading donors…`} size={48} className="min-h-16 py-3" />;
  if (donors.error) return <p role="alert" className="text-sm text-danger">{financeError(donors.error)}</p>;
  if (!donors.data?.length) return <EmptyState message={t`No donors yet.`} />;
  return <div className="grid gap-2">
    <p className="text-sm text-muted">{t`Donor details are private. Only givers who chose to be named appear on public pages.`}</p>
    {donors.data.map(donor => <ListRow key={donor.key} title={donor.name || t`Anonymous`}
      identity={{ kind: "icon", icon: "Info", tone: "neutral" }}
      meta={[donor.email, donor.is_guest ? t`Guest` : t`Member`,
        donor.gift_count === 1 ? t`1 gift` : t`${donor.gift_count} gifts`,
        Object.entries(donor.totals).map(([currency, total]) => formatMoney(total, currency)).join(", "),
        donor.recurring ? t`Gives every period` : "", donor.recognize_publicly ? t`Named publicly` : ""]
        .filter(Boolean).join(" · ")} />)}
  </div>;
}
