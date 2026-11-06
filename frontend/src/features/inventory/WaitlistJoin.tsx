import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { getAccessToken } from "../../lib/api";
import type { Product } from "../../types/inventory";
import { waitlistApi, waitlistKeys } from "./waitlistApi";

/** "Join the waitlist" for an item that is out. Needs a signed-in member account and the `loans.waitlist` switch. */
export function WaitlistJoin({ makerspaceId, product, features }: {
  makerspaceId?: number; product: Pick<Product, "id" | "name" | "availability">; features?: readonly string[];
}) {
  const out = product.availability?.label === "Unavailable";
  if (!makerspaceId || !out || !features?.includes("loans.waitlist") || !getAccessToken("person")) return null;
  return <JoinButton makerspaceId={makerspaceId} product={product} />;
}

function JoinButton({ makerspaceId, product }: { makerspaceId: number; product: Pick<Product, "id" | "name"> }) {
  const client = useQueryClient();
  const join = useMutation({
    throwOnError: false,
    mutationFn: () => waitlistApi.join(makerspaceId, product.id),
    onSuccess: () => { void client.invalidateQueries({ queryKey: waitlistKeys.member(makerspaceId) }); },
  });
  const entry = join.data;
  return <div className="mt-4 grid gap-2">
    <button className="desk-button" type="button" disabled={join.isPending || join.isSuccess} onClick={() => join.mutate()}>
      {join.isPending ? t`Joining…` : join.isSuccess ? t`On the waitlist` : t`Join the waitlist`}
    </button>
    {entry ? <p role="status" className="text-sm text-muted">
      {entry.position ? t`You're number ${entry.position} in line for ${product.name}. ` : t`You're in line for ${product.name}. `}
      {t`When one comes back we hold it for you and let you know.`}</p> : null}
    {join.error ? <p role="alert" className="text-sm text-danger">{join.error.message}</p> : null}
  </div>;
}
