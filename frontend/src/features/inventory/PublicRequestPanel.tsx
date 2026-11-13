import { t } from "@lingui/core/macro";
import { SegmentedControl } from "../../components/ui";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { RequestCartItem } from "../../types/inventory";
import { BorrowRequestCard } from "./BorrowRequestCard";
import { submitPublicRequest } from "./api";
import { invalidatePublicInventory } from "../staff/queryInvalidation";
import { PublicToolScanPanel } from "./PublicToolScanPanel";
import { useRequestDraft, type RequestDraft } from "./useRequestDraft";
import { useContactRequest } from "./useContactRequest";
import { PricePreview } from "../payments/PricePreview";
import { PickupWindowFields, pickupWindowPayload, pickupWindowProblem } from "./PickupWindowFields";
import { ContextualRequest } from "./ContextualRequest";
import { ConsumableKitPlan } from "./ConsumableKitPlan";
import { type PendingIntake, type SelfBody, type SelfResult } from "./contextualIntake";
import { useIntakeScope } from "./useIntakeScope";
import { useRestoreMemberSession } from "./useRestoreMemberSession";
import { usePendingIntakeOwner } from "./usePendingIntakeOwner";
import { getSessionOwner, hasSessionIdentity } from "../../lib/api/sessionTokens";
import { onSessionCleared } from "../../lib/api/sessionContext";
import { memberRequest } from "../../lib/api";
import { eligibilityMessage } from "../../lib/eligibilityCopy";
import { acquireOrdinary, notifyOrdinary, ordinaryEntry } from "./ordinaryRequestFence";
import { tenantPath, useOptionalTenant } from "../../lib/tenant";
import { stashCartForSignIn } from "./publicInventory/cartHandoff";
import { formatDateTime } from "../../lib/format";
import { statusStageLabel } from "../../components/ui/StatusStepper";

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
  makerspaceId?: number;
  modules?: readonly string[];
  /** Single-item forms submit ordinary requests; contextual kits belong to the catalogue. */
  contextual?: boolean;
  pendingOwner?: PendingIntake<SelfBody>;
  contextualLocked?: boolean;
  onContextLock?: () => void;
  onContextDone?: () => void;
  onContextSuccess?: (result: SelfResult, scope: string) => void;
  planConfirmed?: boolean;
  onNewRequest?: () => void;
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
  features, contextual = true,
  makerspaceId, modules = [], pendingOwner, contextualLocked: parentLocked, onContextLock, onContextDone, onContextSuccess, planConfirmed, onNewRequest,
}: PublicRequestPanelProps) {
  const queryClient = useQueryClient();
  const tenantMode = useOptionalTenant()?.mode ?? "central";
  const session = useIntakeScope();
  useRestoreMemberSession(requestAccess !== "contact");
  // The identity query is intentionally unscoped by the candidate owner: while
  // auth notification precedes token replacement, its verified result may still
  // be the previous actor and must never admit a new actor-scoped request.
  const identity = useQuery({ queryKey: ["member", "cards-account"], queryFn: () => memberRequest<{ id: number }>("/auth/me"), enabled: hasSessionIdentity("person"), retry: false, staleTime: 0 });
  const verifiedOwner = Boolean(session.owner && identity.data && session.owner === String(identity.data.id));
  const ordinaryScope = JSON.stringify([session.context, session.owner, makerspaceSlug, makerspaceId ?? null]);
  const ordinary = ordinaryEntry(ordinaryScope);
  useSyncExternalStore(listener => { ordinary.listeners.add(listener); return () => { ordinary.listeners.delete(listener); }; }, () => ordinary.busy ? "busy" : ordinary.unknown ? "unknown" : "idle");
  const [history, setHistory] = useState<{ scope: string; rows: { id: number; status: string; created_at: string }[] }>();
  const [historyError, setHistoryError] = useState(false);
  const identityAdmitted = () => {
    const current = getSessionOwner("person");
    const verified = queryClient.getQueryData<{ id: number }>(["member", "cards-account"]);
    return Boolean(current && current === session.owner && verified && current === String(verified.id));
  };
  const admitted = () => identityAdmitted() && !ordinary.busy && !ordinary.unknown;
  const scope = ordinaryScope;
  const liveScope = useRef({ scope, live: false }); liveScope.current.scope = scope;
  useEffect(() => { const state = liveScope.current; state.live = true; return () => { state.live = false; }; }, []);
  const [lockedScope, setLockedScope] = useState<string>();
  const [planSubmittedScope, setPlanSubmitted] = useState<string>();
  useEffect(() => { setPlanSubmitted(undefined); }, [scope]);
  useEffect(() => onSessionCleared(context => {
    if (context === session.context && getSessionOwner(context) !== session.owner) setPlanSubmitted(undefined);
  }), [session.context, session.owner]);
  const localOwner = usePendingIntakeOwner(scope);
  const selectedOwner = pendingOwner ?? localOwner;
  const pendingAtRender = Boolean(selectedOwner.current(scope));
  useEffect(() => {
    let wasPending = pendingAtRender;
    const reconcile = () => {
      const pending = Boolean(selectedOwner.current(scope));
      if (wasPending && !pending && getSessionOwner("person") === session.owner) {
        setLockedScope(current => current === scope ? undefined : current);
        onContextDone?.();
      }
      wasPending = pending;
    };
    const unsubscribe = selectedOwner.subscribe(reconcile);
    reconcile();
    return unsubscribe;
  }, [selectedOwner, scope, session.owner, onContextDone, pendingAtRender]);
  const contextualLocked = parentLocked || lockedScope === scope;
  const [ownTab, setOwnTab] = useState<ActiveTab>("borrow");
  // "Scan a tool" is the self-checkout surface: without `inventory.self_checkout` every step
  // of it is refused, so the tab is not offered at all (an unknown switch list keeps it).
  const selfCheckout = !features || features.includes("inventory.self_checkout");
  const activeTab = selfCheckout ? controlledTab ?? ownTab : "borrow";
  const setActiveTab = (tab: ActiveTab) => { setOwnTab(tab); onActiveTabChange?.(tab); };
  const ownDraft = useRequestDraft();
  const draft = draftProp ?? ownDraft;
  const { requestedFor, setRequestedFor, submitted, setSubmitted, website, setWebsite, pickup, setPickup } = draft;
  const contextSuccess = (result: SelfResult, completedScope: string) => {
    if (onContextSuccess) { onContextSuccess(result, completedScope); return; }
    if (!liveScope.current.live || completedScope !== liveScope.current.scope || !identityAdmitted()) return;
    invalidatePublicInventory(queryClient, makerspaceSlug);
    setSubmitted(result.kind === "request"); setPlanSubmitted(result.kind === "consumable_plan" ? completedScope : undefined);
    onClear(); setRequestedFor(""); setWebsite(""); setPickup({ from: "", until: "" });
  };
  const reservations = Boolean(features?.includes("loans.reservations"));
  const contactMode = requestAccess === "contact";
  // `request_access` only says "contact"; members vs any-account follows the membership module.
  const membershipBorrowing = modules.includes("membership");
  const contact = useContactRequest(makerspaceSlug, draft, contactMode);
  const totalItems = useMemo(
    () => items.reduce((total, item) => total + item.quantity, 0),
    [items],
  );

  const submitMutation = useMutation({
    mutationFn: (_attempt: { owner: string; done?: (definite: boolean) => boolean }) =>
      (!contactMode && !identityAdmitted()) ? Promise.reject(new Error(t`Session changed.`)) : submitPublicRequest(
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
    onMutate: () => { setSubmitted(false); setPlanSubmitted(undefined); onNewRequest?.(); },
    onSuccess: (_result, attempt) => {
      if (attempt.done && !attempt.done(true)) return;
      if (!contactMode && (!identityAdmitted() || getSessionOwner("person") !== attempt.owner)) return;
      invalidatePublicInventory(queryClient, makerspaceSlug);
      setSubmitted(true);
      onClear();
      setRequestedFor("");
      setWebsite("");
      setPickup({ from: "", until: "" });
      contact.clear();
    },
    onError: (error, attempt) => { attempt.done?.((error as { status?: number }).status === 400); },
  });

  const canSubmit =
    requestedFor.trim().length > 0 &&
    items.length > 0 &&
    contact.ready &&
    (contactMode || verifiedOwner) &&
    !(reservations && pickupWindowProblem(pickup)) &&
    !submitMutation.isPending && !contextualLocked && !ordinary.busy && !ordinary.unknown;

  // No cards inside this panel: its host already frames it (the public "Your request" card, the
  // desk kiosk's card), and every nested card's padding took width from a ~300px desktop column.
  // At xl the host card is sticky beside the catalogue, so the tab body scrolls inside a viewport-
  // high panel instead of hiding the submit button below the fold until the page ends.
  return (
    <div data-replay-block className="grid min-w-0 gap-4 xl:flex xl:max-h-[calc(100dvh-9rem)] xl:flex-col">
      {planConfirmed || planSubmittedScope === scope ? <p role="status">{t`Consumable plan saved. No equipment was issued or stock used.`}</p> : null}
      {disabled ? (
        <div>
          <p className="eyebrow text-brand-ink">
            {t`Requests`}</p>
          <h2 className="title-panel mt-2">{t`Unavailable`}</h2>
          <p className="mt-2 text-sm text-muted">
            {t`This makerspace is publishing inventory without public requests.`}</p>
          {features?.includes("inventory.consumables") && verifiedOwner ? <ConsumableKitPlan key={scope} scope={scope} slug={makerspaceSlug} pendingOwner={pendingOwner ?? localOwner} admitted={admitted} onSuccess={contextSuccess} onLock={() => { setPlanSubmitted(undefined); onNewRequest?.(); setLockedScope(scope); onContextLock?.(); }} onDone={() => { setLockedScope(undefined); onContextDone?.(); }} /> : null}
        </div>
      ) : (
        <>
          <div className="shrink-0">
            <h2 className="title-panel text-brand-ink">{contactMode ? activeTab === "borrow" ? t`Borrow something` : t`Borrow or return a tool` : membershipBorrowing ? t`Member borrowing` : t`Borrowing`}</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              {contactMode
                ? activeTab === "borrow"
                  ? t`No account needed. Give your name, phone and email and confirm the email with the code we send; staff review every request before anything is handed over.`
                  : t`No account needed. Give your name, phone and email and confirm the email with the code we send.`
                : membershipBorrowing
                  ? t`Requests use your signed-in member account. An active membership, waiver acceptance, and current presence are required.`
                  : t`Requests use your signed-in account. Staff review every request before anything is handed over.`}
            </p>
            {/* 0.12.0 row 29: sign in, then come back to this page with the cart as it was. */}
            {!contactMode && !session.owner ? <a className="desk-button-brand mt-3 inline-flex" onClick={() => stashCartForSignIn(items)}
              href={`${tenantPath(tenantMode, makerspaceSlug, "member")}?next=${encodeURIComponent(window.location.pathname + window.location.search + window.location.hash)}`}>{t`Sign in to borrow`}</a> : null}
          </div>

          {selfCheckout ? <div className="shrink-0 [&>[role=radiogroup]]:flex [&>[role=radiogroup]]:w-full [&_[role=radio]]:flex-1">
            <SegmentedControl label={t`Request actions`} value={activeTab} options={[{ value: "borrow", label: t`Borrow request` }, { value: "scan", label: t`Scan a tool` }]} onChange={value => setActiveTab(value as ActiveTab)} />
          </div> : null}

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
                  submitError={eligibilityMessage(submitMutation.error) ?? submitMutation.error?.message}
                  submitPending={submitMutation.isPending}
                  submitted={submitted}
                  historyHref={!contactMode ? tenantPath(tenantMode, makerspaceSlug, "member/loans/history") : undefined}
                  totalItems={totalItems}
                  onClear={onClear}
                  onRequestedForChange={setRequestedFor}
                  onSubmit={() => { if (contactMode) { submitMutation.mutate({ owner: "" }); return; } if (!identityAdmitted() || (pendingOwner ?? localOwner).current(scope)) return; const done = acquireOrdinary(scope); if (!done) return; submitMutation.mutate({ owner: session.owner ?? "", done }); }}
                  website={website}
                  onWebsiteChange={setWebsite}
                  contact={contact.details}
                  extraFields={reservations ? <PickupWindowFields value={pickup} onChange={setPickup} /> : null}
                />
                {ordinary.unknown && !ordinary.busy ? <div className="mt-3 grid gap-2 text-sm" role="status"><p className="text-ink">{t`The previous request may have been submitted. Review your borrowing history before making another.`}</p><button type="button" className="desk-button w-fit" onClick={() => { if (!identityAdmitted() || !makerspaceId) return; setHistoryError(false); void memberRequest<{ results: { id: number; status: string; created_at: string }[] }>(`/member/makerspaces/${makerspaceId}/borrowing-history?period=all&page=1`).then(page => { if (identityAdmitted()) setHistory({ scope, rows: page.results }); }).catch(() => setHistoryError(true)); }}>{t`Load my borrowing history`}</button>{historyError ? <p className="text-danger" role="alert">{t`History is unavailable. Try again before starting another request.`}</p> : null}{history?.scope === scope ? <>{history.rows.length ? <ul className="grid gap-1">{history.rows.map(row => <li key={row.id}>{t`Request #${row.id}`} · {statusStageLabel(row.status)} · {formatDateTime(row.created_at)}</li>)}</ul> : <p className="text-muted">{t`No earlier requests found.`}</p>}<a className="desk-button w-fit" href={tenantPath(tenantMode, makerspaceSlug, "member/loans/history")}>{t`Open full borrowing history`}</a><button type="button" className="desk-button w-fit" onClick={() => { if (!identityAdmitted() || ordinary.busy) return; ordinary.unknown = false; setHistory(undefined); notifyOrdinary(ordinary); }}>{t`I reviewed my history; start another request`}</button></> : null}</div> : null}
                {contextualLocked && !modules.includes("events") && !modules.includes("bookings") ? <p role="status">{t`A previous request may have been submitted. Review your request history before making another.`}</p> : null}
                {contextual && !contactMode && makerspaceId && verifiedOwner ? <ContextualRequest key={`${scope}:${modules.includes("events")}:${modules.includes("bookings")}`} scope={scope} slug={makerspaceSlug} makerspaceId={makerspaceId} eventsEnabled={modules.includes("events")} bookingsEnabled={modules.includes("bookings")} fields={{ requested_for: requestedFor.trim(), items: items.map(item => ({ product_id: item.productId, quantity: item.quantity })), website, ...(reservations ? pickupWindowPayload(pickup) : {}) }} canSubmit={requestedFor.trim().length > 0 && !(reservations && pickupWindowProblem(pickup)) && !submitMutation.isPending} admitted={admitted} pendingOwner={pendingOwner ?? localOwner} onLock={() => { setLockedScope(scope); setPlanSubmitted(undefined); onNewRequest?.(); onContextLock?.(); }} onDenied={() => { setLockedScope(undefined); onContextDone?.(); }} onSuccess={contextSuccess} /> : null}
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
                  borrowOff={contactMode && Boolean(features) && !features?.includes("inventory.contact_self_checkout")}
                />
              </div>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
