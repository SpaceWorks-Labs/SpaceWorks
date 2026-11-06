import { t } from "@lingui/core/macro";
import type { PublicToolLoanResult } from "./selfCheckoutApi";

function formatStatus(status: string) {
  const normalized = status.replace(/_/g, " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export function ResultCard({ result }: { result: PublicToolLoanResult }) {
  return (
    <div className="rounded-xl border border-success bg-success px-3 py-3 text-on-success dark:bg-success-soft dark:text-success-ink">
      <p className="eyebrow text-on-success dark:text-success-ink">
        {formatStatus(result.status)}
      </p>
      <h2 className="title-panel mt-1 break-words text-on-success dark:text-success-ink">
        {result.items.map((item) => item.product_name).join(", ") || t`Tool loan`}
      </h2>
      <div className="mt-3 space-y-2">
        {result.items.map((item) => (
          <div
            className="flex items-center justify-between gap-3 rounded-lg border border-line bg-panel text-ink px-3 py-2 text-sm"
            key={item.product_name}
          >
            <span className="min-w-0 break-words">{item.product_name}</span>
            <span className="shrink-0 tabular-nums font-semibold">x{item.quantity}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

