import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { EvidenceUpload } from "./panels/EvidenceUpload";
import { QuantityStepper } from "./QuantityStepper";
import { WalkInMemberForm } from "./WalkInMemberForm";
import type {
  ContainerOption,
  DirectLoanMember,
  LineDraft,
  ProductOption,
  ScannedPayload,
} from "./DirectLoansTypes";

/** "Guest pass until <date>" for a guest-pass borrower, or null for a member. */
export function guestPassLabel(member: DirectLoanMember): string | null {
  if (!member.is_guest_pass) return null;
  return member.pass_valid_until ? t`Guest pass until ${formatDate(member.pass_valid_until)}` : t`Guest pass`;
}

/** Picker text: a guest is marked in the option itself, since an <option> cannot hold a pill. */
export function borrowerOptionLabel(member: DirectLoanMember): string {
  const name = member.display_name || member.username;
  const guest = guestPassLabel(member);
  return guest ? `${name} · ${guest}` : name;
}

export function DirectLoanBorrowerFields({
  makerspaceId,
  borrowerId,
  onBorrowerIdChange,
  memberOptions,
  membersLoading,
  membersError,
}: {
  makerspaceId: number;
  borrowerId: string;
  onBorrowerIdChange: (value: string) => void;
  memberOptions: DirectLoanMember[];
  membersLoading: boolean;
  membersError?: string;
}) {
  return (
    <>
      <label className="block text-sm font-medium text-ink" htmlFor="direct-loan-borrower">
        {t`Borrowing member`}</label>
      <select
        id="direct-loan-borrower"
        className="desk-input mt-1 w-full"
        value={borrowerId}
        disabled={membersLoading}
        onChange={(event) => onBorrowerIdChange(event.target.value)}
      >
        <option value="">{t`Select an active member`}</option>
        {memberOptions.map((member) => (
          <option key={member.user_id} value={member.user_id}>
            {borrowerOptionLabel(member)}
          </option>
        ))}
      </select>
      {membersError ? <p className="mt-2 text-sm text-danger">{membersError}</p> : null}
      <DirectLoanBorrowerExtras key={borrowerId} makerspaceId={makerspaceId}
        member={memberOptions.find((member) => String(member.user_id) === borrowerId)} onBorrowerIdChange={onBorrowerIdChange} />
    </>
  );
}

/**
 * The counter's borrower extras: record a waiver the member accepted in person, or name a walk-in
 * so the handout can be recorded against them. Key it by borrower so a recorded waiver resets.
 */
export function DirectLoanBorrowerExtras({ makerspaceId, member, onBorrowerIdChange }: {
  makerspaceId: number; member?: DirectLoanMember; onBorrowerIdChange: (value: string) => void;
}) {
  const queryClient = useQueryClient();
  const guest = member ? guestPassLabel(member) : null;
  const witnessWaiver = useMutation({
    mutationFn: () => {
      if (!member || member.membership_id === null) throw new Error(t`Select a member first.`);
      return staffRequest(`/admin/memberships/${member.membership_id}/waiver/witness`, { method: "POST", body: JSON.stringify({}) });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members", makerspaceId] }),
  });
  return (
    <>
      {guest ? <div className="mt-2"><StatusPill tone="info" label={guest} /></div> : null}
      {member && member.membership_id !== null ? (
        <button className="desk-button mt-2" type="button" disabled={witnessWaiver.isPending} onClick={() => witnessWaiver.mutate()}>
          {t`Record witnessed waiver acceptance`}</button>
      ) : null}
      {witnessWaiver.isSuccess ? <p className="mt-2 text-sm text-success-ink">{t`Waiver acceptance recorded.`}</p> : null}
      {witnessWaiver.error ? <p className="mt-2 text-sm text-danger">{witnessWaiver.error.message}</p> : null}
      <WalkInMemberForm makerspaceId={makerspaceId} onCreated={(userId) => onBorrowerIdChange(String(userId))} />
    </>
  );
}

export function DirectLoanContainerField({
  containerId,
  onContainerIdChange,
  containerOptions,
  containersLoading,
  scanError,
  onScanClick,
}: {
  containerId: string;
  onContainerIdChange: (value: string) => void;
  containerOptions: ContainerOption[];
  containersLoading: boolean;
  scanError: string;
  onScanClick: () => void;
}) {
  return (
    <>
      <label className="mt-4 block text-sm font-medium text-ink" htmlFor="direct-loan-container">{t`Container (optional)`}</label>
      <div className="mt-1 flex flex-col gap-2 md:flex-row">
        <select
          id="direct-loan-container"
          className="desk-input w-full"
          value={containerId}
          disabled={containersLoading}
          onChange={(e) => onContainerIdChange(e.target.value)}
        >
          <option value="">{t`No container`}</option>
          {containerOptions.map((container) => (
            <option key={container.id} value={container.id}>{container.label}</option>
          ))}
        </select>
        <button
          type="button"
          className="desk-button"
          onClick={onScanClick}
        >
          {t`Scan container`}</button>
      </div>
      {scanError ? <p className="mt-1 text-sm text-danger">{scanError}</p> : null}
    </>
  );
}

export function DirectLoanItemLines({
  lineRows,
  activeProducts,
  productById,
  productsLoading,
  onAdd,
  onUpdate,
  onRemove,
}: {
  lineRows: LineDraft[];
  activeProducts: ProductOption[];
  productById: Map<number, ProductOption>;
  productsLoading: boolean;
  onAdd: () => void;
  onUpdate: (key: number, patch: Partial<LineDraft>) => void;
  onRemove: (key: number) => void;
}) {
  return (
    <div className="@container mt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h3 className="title-section">{t`Items`}</h3>
        <button className="desk-button" type="button" onClick={onAdd}>{t`Add item`}</button>
      </div>
      <div className="grid gap-2">
        {lineRows.map((line) => {
          const selectedLineProduct = productById.get(Number(line.productId));
          const selectedIndividual = selectedLineProduct?.tracking_mode === "individual";
          return (
            <div key={line.key} className="grid gap-2 @xl:grid-cols-[minmax(0,1fr)_auto_auto] @xl:items-center">
              <select aria-label={t`Product`} className="desk-input" value={line.productId} disabled={productsLoading} onChange={(e) => onUpdate(line.key, { productId: e.target.value })}>
                <option value="">{t`Inventory item`}</option>
                {activeProducts.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} | {product.tracking_mode} | {product.available_quantity} available
                    {product.storage_location ? t` - Shelf: ${product.storage_location}` : ""}
                  </option>
                ))}
              </select>
              <QuantityStepper aria-label={t`Quantity`} label="quantity" min={1} value={line.quantity} disabled={selectedIndividual} onValueChange={(value) => onUpdate(line.key, { quantity: value })} />
              <button className="desk-button" type="button" onClick={() => onRemove(line.key)}>{t`Remove`}</button>
              {selectedLineProduct ? <p className="text-xs text-muted @xl:col-span-3">{selectedLineProduct.tracking_mode}{selectedIndividual ? t` | scan unit QR` : ""}</p> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function DirectLoanQrSection({
  scanned,
  qrPayloads,
  onOpenScanner,
  onRemoveScanned,
  onQrPayloadsChange,
}: {
  scanned: ScannedPayload[];
  qrPayloads: string;
  onOpenScanner: () => void;
  onRemoveScanned: (payload: string) => void;
  onQrPayloadsChange: (value: string) => void;
}) {
  return (
    <>
      <div className="mt-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
          <h3 className="title-section">{t`QR payloads`}</h3>
          <button className="desk-button" type="button" onClick={onOpenScanner}>{t`Scan QR`}</button>
        </div>
        {scanned.length ? (
          <div className="mb-3 flex flex-wrap gap-2">
            {scanned.map((item) => (
              <span key={item.payload} className="inline-flex min-w-0 max-w-full items-center gap-2 rounded-md border border-line bg-surface px-3 py-1 text-sm text-ink [overflow-wrap:anywhere]">
                {item.label}
                <button className="desk-button-ghost px-2 text-danger" type="button" onClick={() => onRemoveScanned(item.payload)}>{t`Remove`}</button>
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <textarea
        aria-label={t`QR payloads`}
        className="desk-input mt-3 h-24 w-full"
        placeholder={t`Optional QR payloads, one per line`}
        value={qrPayloads}
        onChange={(e) => onQrPayloadsChange(e.target.value)}
      />
    </>
  );
}

export function DirectLoanIssueEvidence({
  uploadKey,
  makerspaceId,
  disabled,
  onUploaded,
  remark,
  onRemarkChange,
}: {
  uploadKey: number;
  makerspaceId: number;
  disabled: boolean;
  onUploaded: (evidenceId: number | null) => void;
  remark: string;
  onRemarkChange: (value: string) => void;
}) {
  return (
    <div className="@container mt-4"><div className="grid gap-3 @2xl:grid-cols-2">
      <EvidenceUpload
        key={uploadKey}
        makerspaceId={makerspaceId}
        evidenceType="issue"
        disabled={disabled}
        onUploaded={onUploaded}
      />
      <label className="block">
        <span className="eyebrow mb-1 block">
          {t`Issue remark`}</span>
        <textarea
          className="desk-input min-h-20 w-full"
          value={remark}
          onChange={(event) => onRemarkChange(event.target.value)}
        />
      </label>
    </div></div>
  );
}
