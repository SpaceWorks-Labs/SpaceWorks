import { SegmentedControl } from "../../components/ui";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { RequestCartItem } from "../../types/inventory";
import { BorrowRequestCard } from "./BorrowRequestCard";
import { getAccessToken, refreshAccessToken } from "../../lib/api";
import { submitPublicRequest } from "./api";
import { invalidatePublicInventory } from "../staff/queryInvalidation";
import { PublicToolScanPanel } from "./PublicToolScanPanel";
import { useRequestDraft, newIdempotencyKey, type RequestDraft } from "./useRequestDraft";

export type ActiveTab = "borrow" | "scan";

type PublicRequestPanelProps = {
  items: RequestCartItem[];
  makerspaceSlug: string;
  onClear: () => void;
  disabled?: boolean;
  // The makerspace's policy, not the caller's state. Present only when the space opted
  // into account-less borrow requests.
  requestAccess?: "anyone";
  /** Lets the page open the panel straight on "Scan a tool" (the phone bar does). Uncontrolled when omitted. */
  activeTab?: ActiveTab;
  onActiveTabChange?: (tab: ActiveTab) => void;
  /** The page owns the draft so it survives the phone sheet unmounting this panel. Own state when omitted. */
  draft?: RequestDraft;
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
}: PublicRequestPanelProps) {
  const queryClient = useQueryClient();
  const [ownTab, setOwnTab] = useState<ActiveTab>("borrow");
  const activeTab = controlledTab ?? ownTab;
  const setActiveTab = (tab: ActiveTab) => { setOwnTab(tab); onActiveTabChange?.(tab); };
  const ownDraft = useRequestDraft();
  const {
    requestedFor, setRequestedFor, submitted, setSubmitted, contactName, setContactName,
    contactEmail, setContactEmail, contactPhone, setContactPhone, website, setWebsite,
    publicToken, setPublicToken, idempotencyKey,
  } = draftProp ?? ownDraft;
  // A signed-in member who RELOADED this page holds no in-memory access token -- it lives
  // behind the refresh cookie, and unlike `MemberArea` this page never hydrates. Without
  // the probe they would be classified as anonymous and their request filed against the
  // SHARED anonymous principal, which every per-person view excludes: it would vanish from
  // their own activity and take the unverified-contact path instead of notifying them.
  const sessionProbe = useQuery({
    queryKey: ["public-request-session", makerspaceSlug],
    queryFn: async () => (getAccessToken() ? true : refreshAccessToken()),
    enabled: requestAccess === "anyone" && !disabled,
    staleTime: Infinity,
    retry: false,
  });
  // Policy AND caller state. `tenantPublicRequest` still attaches Authorization when a
  // token is in memory, and the backend then takes the AUTHENTICATED branch and ignores
  // these contact fields -- so asking for them would promise something the stored request
  // does not honour. Until the probe settles we assume a member: claiming "no account
  // needed" and then discovering a session would be the worse way round.
  const authenticated = Boolean(getAccessToken());
  const accountLess =
    requestAccess === "anyone" && sessionProbe.isFetched && !authenticated;
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
          ...(accountLess
            ? {
                contact_name: contactName.trim(),
                contact_email: contactEmail.trim(),
                contact_phone: contactPhone.trim(),
              }
            : {}),
        },
        accountLess ? idempotencyKey.current : undefined,
      ),
    // The previous banner and token must not survive into the next attempt: if this one
    // fails, showing the error beside a stale token invites the requester to save the
    // wrong reference -- and it is their only route back to the request.
    onMutate: () => {
      setSubmitted(false);
      setPublicToken("");
    },
    onSuccess: (response) => {
      invalidatePublicInventory(queryClient, makerspaceSlug);
      // Kept before the form is cleared: this token is the account-less requester's only
      // way back to the request.
      setPublicToken(response?.public_token ?? "");
      setSubmitted(true);
      onClear();
      setContactName("");
      setContactEmail("");
      setContactPhone("");
      setRequestedFor("");
      setWebsite("");
      // Only after the server accepted it: reusing the key for the NEXT request would
      // return this one back instead of creating anything.
      idempotencyKey.current = newIdempotencyKey();
    },
  });

  const contactReady =
    !accountLess ||
    (contactName.trim().length > 0 && contactEmail.trim().length > 0);
  // While the probe is unresolved `accountLess` is still false, so `contactReady` is
  // vacuously true and the button would go live before the contact fields exist. On a
  // slow refresh a visitor could submit a member-shaped body and take a 400.
  const policyResolved = requestAccess !== "anyone" || sessionProbe.isFetched;
  const canSubmit =
    requestedFor.trim().length > 0 &&
    items.length > 0 &&
    contactReady &&
    policyResolved &&
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
            Requests
          </p>
          <h2 className="title-panel mt-2">Unavailable</h2>
          <p className="mt-2 text-sm text-muted">
            This makerspace is publishing inventory without public requests.
          </p>
        </div>
      ) : (
        <>
          <div className="shrink-0">
            <h2 className="title-panel text-brand-ink">
              {accountLess && activeTab === "borrow"
                ? "Borrow something"
                : "Member borrowing"}
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              {/* Three states, because the requirements genuinely differ. Scoped to the
                  borrow tab: scanning a tool is self-checkout, which DOES require an
                  authenticated member with active presence, so "no account needed" would
                  be false there until it 401s. And an `anyone` policy necessarily has the
                  membership module off, so the membership/waiver/presence sentence cannot
                  be true on such a space even for a signed-in visitor. */}
              {activeTab === "borrow" && accountLess
                ? "No account needed. Leave your name and email so staff can reach you about the request; they review it before anything is handed over."
                : activeTab === "borrow" && requestAccess === "anyone"
                  ? "You are signed in, so this request is filed against your account. Staff review it before anything is handed over."
                  : "Requests use your signed-in member account. An active membership, waiver acceptance, and current presence are required."}
            </p>
          </div>

          <div className="shrink-0 [&>[role=radiogroup]]:flex [&>[role=radiogroup]]:w-full [&_[role=radio]]:flex-1">
            <SegmentedControl label="Request actions" value={activeTab} options={[{ value: "borrow", label: "Borrow request" }, { value: "scan", label: "Scan a tool" }]} onChange={value => setActiveTab(value as ActiveTab)} />
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
                  accountLess={accountLess}
                  contactName={contactName}
                  contactEmail={contactEmail}
                  contactPhone={contactPhone}
                  onContactNameChange={setContactName}
                  onContactEmailChange={setContactEmail}
                  onContactPhoneChange={setContactPhone}
                  website={website}
                  onWebsiteChange={setWebsite}
                  publicToken={publicToken}
                />
              </div>
            ) : null}

            {activeTab === "scan" ? (
              <div
                aria-label="Scan a tool"
                id="public-request-scan-panel"
                role="region"
              >
                <PublicToolScanPanel
                  makerspaceSlug={makerspaceSlug}
                />
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
