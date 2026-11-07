import { t } from "@lingui/core/macro";
import { SegmentedControl } from "../../components/ui";
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { RequestCartItem } from "../../types/inventory";
import { BorrowRequestCard } from "./BorrowRequestCard";
import { submitPublicRequest } from "./api";
import { invalidatePublicInventory } from "../staff/queryInvalidation";
import { PublicToolScanPanel } from "./PublicToolScanPanel";
import { useRequestDraft, type RequestDraft } from "./useRequestDraft";
import { useContactRequest } from "./useContactRequest";
import { PricePreview } from "../payments/PricePreview";
import { PickupWindowFields, pickupWindowPayload, pickupWindowProblem } from "./PickupWindowFields";

export type ActiveTab = "borrow" | "scan";

type PublicRequestPanelProps = {
  items: RequestCartItem[];
  makerspaceSlug: string;
  onClear: () => void;
  disabled?: boolean;
  // The makerspace's policy: "contact" only where it has no member accounts (#80).
  requestAccess?: "contact";
  /** Lets the page open the panel straight on "Scan a tool" (the phone bar does). Uncontrolled when omitted. */
  activeTab?: ActiveTab;
  onActiveTabChange?: (tab: ActiveTab) => void;
  /** The page owns the draft so it survives the phone sheet unmounting this panel. Own state when omitted. */
  draft?: RequestDraft;
  /** The space's effective switches (bootstrap `features`); `loans.reservations` adds the collection window. */
  features?: readonly string[];
};

export function PublicRequestPanel({
  items,
  makerspaceSlug,
  onClear,
  disabled = false,
  requestAccess,
  activeTab: controlledTab,
  onActiveTabChange,
  draft: draftProp,
  features,
}: PublicRequestPanelProps) {
  const queryClient = useQueryClient();
  const [ownTab, setOwnTab] = useState<ActiveTab>("borrow");
  const activeTab = controlledTab ?? ownTab;
  const setActiveTab = (tab: ActiveTab) => { setOwnTab(tab); onActiveTabChange?.(tab); };
  const ownDraft = useRequestDraft();
  const draft = draftProp ?? ownDraft;
  const { requestedFor, setRequestedFor, submitted, setSubmitted, website, setWebsite, pickup, setPickup } = draft;
  const reservations = Boolean(features?.includes("loans.reservations"));
  const contactMode = requestAccess === "contact";
  const contact = useContactRequest(makerspaceSlug, draft, contactMode);
  const totalItems = useMemo(
    () => items.reduce((total, item) => total + item.quantity, 0),
    [items],
  );

  const submitMutation = useMutation({
    mutationFn: () =>
      submitPublicRequest(
        makerspaceSlug,
        {
          requested_for: requestedFor.trim(),
          items: items.map((item) => ({
            product_id: item.productId,
            quantity: item.quantity,
          })),
          website,
          ...(reservations ? pickupWindowPayload(pickup) : {}),
          ...contact.payload,
        },
      ),
    // The previous banner must not survive into the next attempt.
    onMutate: () => setSubmitted(false),
    onSuccess: () => {
      invalidatePublicInventory(queryClient, makerspaceSlug);
      setSubmitted(true);
      onClear();
      setRequestedFor("");
      setWebsite("");
      setPickup({ from: "", until: "" });
      contact.clear();
    },
  });

  const canSubmit =
    requestedFor.trim().length > 0 &&
    items.length > 0 &&
    contact.ready &&
    !(reservations && pickupWindowProblem(pickup)) &&
    !submitMutation.isPending;

  // No cards inside this panel: its host already frames it (the public "Your request" card, the
  // desk kiosk's card), and every nested card's padding took width from a ~300px desktop column.
  // At xl the host card is sticky beside the catalogue, so the tab body scrolls inside a viewport-
  // high panel instead of hiding the submit button below the fold until the page ends.
  return (
    <div className="grid min-w-0 gap-4 xl:flex xl:max-h-[calc(100dvh-9rem)] xl:flex-col">
      {disabled ? (
        <div>
          <p className="eyebrow text-brand-ink">
            {t`Requests`}</p>
          <h2 className="title-panel mt-2">{t`Unavailable`}</h2>
          <p className="mt-2 text-sm text-muted">
            {t`This makerspace is publishing inventory without public requests.`}</p>
        </div>
      ) : (
        <>
          <div className="shrink-0">
            <h2 className="title-panel text-brand-ink">{contactMode && activeTab === "borrow" ? t`Borrow something` : t`Member borrowing`}</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              {contactMode && activeTab === "borrow"
                ? t`No account needed. Give your name, phone and email and confirm the email with the code we send; staff review every request before anything is handed over.`
                : t`Requests use your signed-in member account. An active membership, waiver acceptance, and current presence are required.`}
            </p>
          </div>

          <div className="shrink-0 [&>[role=radiogroup]]:flex [&>[role=radiogroup]]:w-full [&_[role=radio]]:flex-1">
            <SegmentedControl label={t`Request actions`} value={activeTab} options={[{ value: "borrow", label: t`Borrow request` }, { value: "scan", label: t`Scan a tool` }]} onChange={value => setActiveTab(value as ActiveTab)} />
          </div>

          {/* p-1/-m-1 keeps focus outlines inside the scroll box from being clipped. */}
          <div className="min-h-0 min-w-0 xl:-m-1 xl:flex-1 xl:overflow-y-auto xl:p-1">
            {activeTab === "borrow" ? (
              <div
                id="public-request-borrow-panel"
              >
                <BorrowRequestCard
                  canSubmit={canSubmit}
                  items={items}
                  requestedFor={requestedFor}
                  submitError={submitMutation.error?.message}
                  submitPending={submitMutation.isPending}
                  submitted={submitted}
                  totalItems={totalItems}
                  onClear={onClear}
                  onRequestedForChange={setRequestedFor}
                  onSubmit={() => submitMutation.mutate()}
                  website={website}
                  onWebsiteChange={setWebsite}
                  contact={contact.details}
                  extraFields={reservations ? <PickupWindowFields value={pickup} onChange={setPickup} /> : null}
                />
                <PricePreview className="mt-4" makerspaceSlug={makerspaceSlug} request={{ domain: "loans", items: items.map(item => ({ product_id: item.productId, quantity: item.quantity })) }} />
              </div>
            ) : null}

            {activeTab === "scan" ? (
              <div
                aria-label={t`Scan a tool`}
                id="public-request-scan-panel"
                role="region"
              >
                <PublicToolScanPanel
                  makerspaceSlug={makerspaceSlug}
                  requestAccess={requestAccess}
                />
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
