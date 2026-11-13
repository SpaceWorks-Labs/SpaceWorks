import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";

/**
 * Parity C20: is this space charging through TEST credentials? The server derives it from the public half of
 * the key pair (`pk_test_` / `rzp_test_`); `null` means no credentials or a key of an unknown shape. Read from
 * the payment settings, which only people who may open them can read: for anyone else this answers `false`
 * and nothing is shown, so the badge never claims a mode it could not check.
 */
export function usePaymentTestMode(makerspaceId: number | undefined) {
  const query = useQuery({
    queryKey: ["payment-settings", makerspaceId],
    queryFn: () => staffRequest<{ test_mode?: boolean | null }>(`/admin/makerspace/${makerspaceId}/payment-settings`),
    enabled: Boolean(makerspaceId), retry: false, staleTime: 60_000,
  });
  return query.data?.test_mode === true;
}

export function TestModeBadge() {
  return <StatusPill label={t`Test mode`} tone="warn" icon="TriangleAlert" />;
}

/** One line under a payment screen's heading: test money moved nothing and stays out of live totals. */
export function TestModeNotice({ makerspaceId }: { makerspaceId: number | undefined }) {
  const testMode = usePaymentTestMode(makerspaceId);
  if (!testMode) return null;
  return <p className="flex flex-wrap items-center gap-2 text-sm text-ink" role="note">
    <TestModeBadge />{t`Payments use test keys: no real money moves, and test payments are kept out of live totals.`}</p>;
}
