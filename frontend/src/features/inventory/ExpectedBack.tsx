import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import type { Product } from "../../types/inventory";

/** "Thu, 14 Nov" for a server date-only value, read as a local calendar day (no timezone shift). */
export function formatExpectedBack(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return date.toLocaleDateString(formatLocale(), { weekday: "short", day: "numeric", month: "short" });
}

/** Shown only when the item is out and the space publishes when it should be back. */
export function ExpectedBack({ product, className = "" }: { product: Pick<Product, "availability" | "expected_back_on">; className?: string }) {
  if (!product.expected_back_on || product.availability?.label !== "Unavailable") return null;
  return <p className={`text-sm text-muted ${className}`}>{t`Back around `}<time dateTime={product.expected_back_on}>{formatExpectedBack(product.expected_back_on)}</time></p>;
}
