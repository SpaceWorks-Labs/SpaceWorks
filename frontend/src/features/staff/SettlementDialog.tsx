import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FlowLayout } from "../../components/layouts";

import { SETTLEMENT_METHODS, type Settlement } from "./paymentsApi";

/** Collects the receipt the API requires before a charge can be marked paid offline.
 *
 * Method and received date are mandatory server-side: the whole point of the manual
 * settlement ledger is that a settled charge can always say how and when the money
 * arrived, so a bare "mark paid" button would just 400. `reference` stays optional
 * because cash genuinely has none.
 */
export function SettlementDialog({
  count,
  pending,
  onCancel,
  onConfirm,
  title,
  error,
}: {
  count: number;
  pending: boolean;
  /** Overrides the heading, e.g. when correcting an existing receipt. */
  title?: string;
  error?: string;
  onCancel: () => void;
  onConfirm: (settlement: Settlement) => void;
}) {
  const [method, setMethod] = useState<string>(SETTLEMENT_METHODS[0][0]);
  const [reference, setReference] = useState("");
  // Defaults to now, which is the common case: staff record the money as they take it.
  const [receivedAt, setReceivedAt] = useState(() => localNow());
  // The input can be cleared. Confirming with an empty value would throw a RangeError
  // out of toISOString() before the mutation ran, leaving the operator with a blank
  // screen and no explanation.
  const receivedValid = !Number.isNaN(new Date(receivedAt).getTime());

  return (
    <FlowLayout presentation="dialog" open state={{ status: "ready" }} onCancel={() => { if (!pending) onCancel(); }}
      title={title ?? t`Record payment${count > 1 ? ` for ${count} charges` : ""}`}
      steps={[{ key: "receipt", label: t`Payment receipt`, state: "current" }]} current="receipt"
      footer={{ next: { label: title ? t`Save correction` : t`Save receipt`, pending,
        disabled: !receivedValid, onClick: () => onConfirm({ method, reference, received_at: new Date(receivedAt).toISOString() }) } }}
      work={<>
      <p className="mt-1 text-sm text-muted">
        {t`How and when the money arrived. This is kept as a permanent receipt.`}</p>
      <div className="@container mt-3"><div className="grid gap-3 @2xl:grid-cols-3">
        <label className="block text-sm">
          <span className="eyebrow">{t`Method`}</span>
          <select
            className="desk-input mt-1 w-full"
            value={method}
            onChange={(event) => setMethod(event.target.value)}
          >
            {SETTLEMENT_METHODS.map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="eyebrow">{t`Reference`}</span>
          <input
            className="desk-input mt-1 w-full"
            maxLength={64}
            onChange={(event) => setReference(event.target.value)}
            placeholder={t`Optional`}
            value={reference}
          />
        </label>
        <label className="block text-sm">
          <span className="eyebrow">{t`Received`}</span>
          <input
            className="desk-input mt-1 w-full"
            onChange={(event) => setReceivedAt(event.target.value)}
            type="datetime-local"
            value={receivedAt}
          />
        </label>
      </div></div>
      {receivedValid ? null : (
        <p className="mt-2 text-sm text-danger" role="alert">
          {t`Enter the date and time the money was received.`}</p>
      )}
      {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
      </>}
    />
  );
}

function localNow() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}
