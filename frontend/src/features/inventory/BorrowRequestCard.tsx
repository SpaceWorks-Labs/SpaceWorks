import type { RequestCartItem } from "../../types/inventory";
import { ContactFields, type ContactDetails } from "./ContactFields";

type BorrowRequestCardProps = {
  canSubmit: boolean;
  items: RequestCartItem[];
  requestedFor: string;
  submitError?: string;
  submitPending: boolean;
  submitted: boolean;
  totalItems: number;
  onClear: () => void;
  onRequestedForChange: (value: string) => void;
  onSubmit: () => void;
  // Honeypot, carried by every other public form (booking, printing, events). A bot that
  // autofills it gets the server's decoy response instead of a real request.
  website?: string;
  onWebsiteChange?: (value: string) => void;
  // Present only for a makerspace without member accounts: the borrower has no account.
  contact?: ContactDetails;
};

export function BorrowRequestCard({
  canSubmit,
  items,
  requestedFor,
  submitError,
  submitPending,
  submitted,
  totalItems,
  onClear,
  onRequestedForChange,
  onSubmit,
  website = "",
  onWebsiteChange,
  contact,
}: BorrowRequestCardProps) {
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className="title-section min-w-0">
          Selected equipment
        </h3>
        <span className="shrink-0 rounded-lg border border-brand bg-brand-soft px-3 py-1 text-sm font-semibold tabular-nums text-brand-ink">
          {totalItems}
        </span>
      </div>

      {items.length === 0 ? (
        <p className="mt-4 text-sm leading-6 text-muted">
          {contact
            ? "Add public items from the inventory list, then give your name, phone and email to submit the request."
            : "Add public items from the inventory list, then submit the request with your signed-in member account."}
        </p>
      ) : (
        <div className="mt-4 space-y-2">
          <div className="max-h-40 space-y-2 overflow-y-auto">
            {items.map((item) => (
              <div
                className="flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-2"
                key={item.productId}
              >
                <span className="min-w-0 break-words text-sm font-medium text-ink">{item.name}</span>
                <span className="shrink-0 tabular-nums text-sm text-muted">x{item.quantity}</span>
              </div>
            ))}
          </div>
          <button className="desk-button w-full" type="button" onClick={onClear}>
            Clear selection
          </button>
        </div>
      )}

      <div className="mt-5 space-y-3">
        {contact ? <ContactFields contact={contact} /> : null}
        <label
          aria-hidden="true"
          className="absolute left-[-10000px] top-auto h-px w-px overflow-hidden"
        >
          Website
          <input
            autoComplete="off"
            name="website"
            tabIndex={-1}
            value={website}
            onChange={(event) => onWebsiteChange?.(event.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">
            Request purpose
          </span>
          <textarea
            className="desk-input min-h-24 w-full resize-y"
            placeholder="What do you need these items for?"
            value={requestedFor}
            onChange={(event) => onRequestedForChange(event.target.value)}
          />
        </label>
        <button
          className="desk-button-brand w-full disabled:cursor-not-allowed"
          disabled={!canSubmit}
          type="button"
          onClick={onSubmit}
        >
          {submitPending ? "Submitting..." : "Submit request"}
        </button>
        {submitError ? <Notice tone="danger" text={submitError} /> : null}
        {submitted ? (
          <div className="rounded-xl border border-success bg-success px-3 py-2 text-on-success dark:bg-success-soft dark:text-success-ink">
            <h3 className="title-section text-on-success dark:text-success-ink">Request submitted</h3>
            <p className="mt-1 text-sm">
              {contact
                ? "Staff will contact you by email or phone about the request."
                : "Check this page with your email to follow the request."}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Notice({ text, tone }: { text: string; tone: "danger" | "success" }) {
  const colors =
    tone === "success"
      ? "border-success bg-success text-on-success"
      : "border-danger/40 bg-panel text-danger";
  return <p className={`rounded-lg border px-3 py-2 text-sm ${colors}`}>{text}</p>;
}
