import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest, type StaffAuthUser } from "../../../lib/api";
import { StructuredApiError, isSurfaceOff } from "../../../lib/api/errors";
import { type Makerspace, type Product, useStaffGet } from "./shared";
import { invalidateInventoryViews, invalidateQrViews } from "../queryInvalidation";
import { rows, type BoxContents, type ListResponse, type Rebound, type Resolved } from "./ScannerPanelTypes";

// The staff scanner page existed as an orphan route with dead action badges. This wires
// the staff-reachable allowed_actions the backend returns: revoke (MANAGE_QR) and box
// contents. checkout/return/direct_handout need a borrower identifier, so we point staff
// to the Direct handout / self-checkout flows instead of faking them here.
export function useStaffScanner({ makerspace, isSuperadmin, makerspaces }: {
  makerspace: Makerspace;
  isSuperadmin: boolean;
  makerspaces: Makerspace[];
}) {
  const queryClient = useQueryClient();
  const [scanNote, setScanNote] = useState("");
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [recent, setRecent] = useState<{ key: string; label: string; meta: string }[]>([]);
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [contents, setContents] = useState<BoxContents | null>(null);
  const [showRebind, setShowRebind] = useState(false);
  const [showMove, setShowMove] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [destMakerspaceId, setDestMakerspaceId] = useState("");
  const [destProductId, setDestProductId] = useState("");
  const [newName, setNewName] = useState("");
  const [moveTag, setMoveTag] = useState("");
  const [successNote, setSuccessNote] = useState<string | null>(null);
  // A scanned value nothing resolves to: offered to QR managers as a label to register.
  const [unknownValue, setUnknownValue] = useState<string | null>(null);
  const resolvedQrMakerspaceId = resolved?.qr.makerspace_id ?? resolved?.qr.makerspace;
  const rebindMakerspaceId = resolvedQrMakerspaceId ?? makerspace.id;
  const rebindMakerspace = makerspaces.find((space) => space.id === rebindMakerspaceId) ?? (
    makerspace.id === rebindMakerspaceId ? makerspace : undefined
  );

  const products = useStaffGet<ListResponse<Product>>(
    ["inventory-all", rebindMakerspaceId],
    `/admin/makerspace/${rebindMakerspaceId}/inventory?page_size=1000`,
    showRebind && Boolean(resolvedQrMakerspaceId),
  );
  const destinationProducts = useStaffGet<ListResponse<Product>>(
    ["inventory-all", destMakerspaceId],
    `/admin/makerspace/${destMakerspaceId}/inventory?page_size=1000`,
    Boolean(destMakerspaceId),
  );
  const currentUser = useStaffGet<StaffAuthUser>(["staff", "me"], "/auth/me");
  const productRows = useMemo(() => rows(products.data), [products.data]);
  const destinationProductRows = useMemo(
    () => rows(destinationProducts.data).filter((product) => product.tracking_mode === "individual"),
    [destinationProducts.data],
  );

  const resolve = useMutation({
    mutationFn: (value: string) =>
      // makerspace_id: labels printed outside SpaceWorks are unique only per makerspace.
      staffRequest<Resolved>("/admin/qr/resolve", { method: "POST", body: JSON.stringify({ payload: value.trim(), makerspace_id: makerspace.id }) }),
    onSuccess: (data) => {
      setResolved(data);
      setUnknownValue(null);
      setRecent(current => [{ key: String(Date.now()), label: data.target.type === "box" ? data.target.label : data.target.type === "product" ? data.target.name : data.target.asset_tag, meta: data.target.type }, ...current].slice(0, 8));
      setContents(null);
      setScanNote("");
      setShowRebind(false);
      setShowMove(false);
      setSelectedProductId("");
      setDestMakerspaceId("");
      setDestProductId("");
      setNewName("");
      setMoveTag("");
      setSuccessNote(null);
    },
  });
  const revoke = useMutation({
    mutationFn: (qrId: number) => staffRequest(`/admin/qr/${qrId}/revoke`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      setConfirmRevoke(false);
      if (resolvedQrMakerspaceId) invalidateQrViews(queryClient, resolvedQrMakerspaceId, resolved?.qr.id);
      if (resolved) resolve.mutate(resolved.qr.payload);
    },
  });
  const loadContents = useMutation({
    mutationFn: (boxId: number) => staffRequest<BoxContents>(`/admin/containers/${boxId}/contents`),
    onSuccess: setContents,
  });
  const rebind = useMutation({
    mutationFn: () =>
      staffRequest<Rebound>(`/admin/qr/${resolved?.qr.id}/rebind-target`, {
        method: "POST",
        body: JSON.stringify({
          target_type: "product",
          target_id: Number(selectedProductId),
          new_name: newName.trim() || undefined,
        }),
      }),
    onSuccess: (data) => {
      if (resolvedQrMakerspaceId) invalidateInventoryViews(queryClient, resolvedQrMakerspaceId);
      invalidateQrViews(queryClient, data.qr.makerspace_id ?? data.qr.makerspace, data.qr.id);
      setShowRebind(false);
      setNewName("");
      setSuccessNote("Rebound.");
      resolve.mutate(data.qr.payload, {
        onError: () => {
          setResolved(null);
          setContents(null);
          setSuccessNote("Rebound. Re-scan in the destination makerspace to view.");
        },
      });
    },
  });
  const moveAsset = useMutation({
    mutationFn: () => {
      if (!resolved) throw new Error(t`No QR resolved.`);
      return staffRequest<Rebound>(`/admin/qr/${resolved.qr.id}/rebind-target`, {
        method: "POST",
        body: JSON.stringify({
          target_type: "asset",
          target_id: resolved.target.id,
          destination_makerspace_id: Number(destMakerspaceId),
          destination_product_id: destProductId ? Number(destProductId) : undefined,
          new_name: moveTag.trim() || undefined,
        }),
      });
    },
    onSuccess: (data) => {
      if (resolvedQrMakerspaceId) invalidateInventoryViews(queryClient, resolvedQrMakerspaceId);
      if (destMakerspaceId) invalidateInventoryViews(queryClient, Number(destMakerspaceId));
      invalidateQrViews(queryClient, data.qr.makerspace_id ?? data.qr.makerspace, data.qr.id);
      setShowMove(false);
      setDestMakerspaceId("");
      setDestProductId("");
      setMoveTag("");
      setSuccessNote("Moved.");
      resolve.mutate(data.qr.payload, {
        onError: () => {
          setResolved(null);
          setContents(null);
          setSuccessNote("Moved. Re-scan in the destination makerspace to view.");
        },
      });
    },
  });

  useEffect(() => {
    if (!productRows.length) {
      setSelectedProductId("");
      return;
    }
    if (!productRows.some((product) => String(product.id) === selectedProductId)) {
      setSelectedProductId(String(productRows[0].id));
    }
  }, [productRows, selectedProductId]);

  const resolveScanned = (value: string) => {
    setUnknownValue(null);
    setResolved(null);
    resolve.mutate(value, {
      onError: (error) => {
        if (error instanceof StructuredApiError && error.status === 404 && !isSurfaceOff(error)) setUnknownValue(value.trim());
      },
    });
  };
  const doResolve = (value: string) => {
    setScanNote("");
    if (value.trim()) resolveScanned(value);
  };
  // Camera scans resolve the opaque token WITHOUT echoing it into the visible
  // input (the payload is a physical-possession token, not something to display).
  const resolveFromScan = (value: string) => {
    if (!value.trim()) return;
    setScanNote("Scanned - resolving...");
    resolveScanned(value);
  };
  const spaceActions = currentUser.data?.makerspaces.find((item) => item.id === makerspace.id)?.actions ?? [];
  const canLinkExternal = isSuperadmin || spaceActions.includes("manage_qr");
  const canCreateExternal = canLinkExternal && (isSuperadmin || spaceActions.includes("edit_inventory"));
  const onExternalLinked = (data: Rebound) => {
    invalidateInventoryViews(queryClient, makerspace.id);
    invalidateQrViews(queryClient, data.qr.makerspace_id ?? data.qr.makerspace, data.qr.id);
    const value = unknownValue;
    setUnknownValue(null);
    if (value) resolve.mutate(value, { onSuccess: () => setSuccessNote(t`Code linked.`) });
  };
  const target = resolved?.target;
  const actions = resolved?.allowed_actions ?? [];
  const resolveError = unknownValue && canLinkExternal ? undefined : resolve.error instanceof Error ? resolve.error.message : undefined;
  const revokeError = revoke.error instanceof Error ? revoke.error.message : undefined;
  const rebindError = rebind.error instanceof Error ? rebind.error.message : undefined;
  const moveError = moveAsset.error instanceof Error ? moveAsset.error.message : undefined;
  const productError = products.error instanceof Error ? products.error.message : undefined;
  const destinationProductError = destinationProducts.error instanceof Error ? destinationProducts.error.message : undefined;
  const rebindActions = currentUser.data?.makerspaces.find(
    (item) => item.id === resolvedQrMakerspaceId,
  )?.actions ?? [];
  const hasRebindPermissions = isSuperadmin || (rebindActions.includes("manage_qr") && rebindActions.includes("edit_inventory"));
  // Rebind UI only targets PRODUCT QRs (the cross-makerspace quantity-product
  // transfer scenario). The form always submits target_type "product", so offering
  // it for an asset QR would silently convert that QR's type - disallow it here.
  const canRebind = Boolean(resolved && target && target.type === "product" && hasRebindPermissions);
  const canMoveAsset = Boolean(resolved && target && target.type === "asset" && isSuperadmin);
  const destinationMakerspaces = makerspaces.filter((space) => space.id !== resolvedQrMakerspaceId);

  return {
    doResolve, resolveFromScan, resolve, recent, scanNote, resolveError,
    revokeError, loadContents, successNote, resolved, target, actions,
    showRebind, setShowRebind, canRebind, canMoveAsset, setShowMove, showMove,
    setConfirmRevoke, confirmRevoke, revoke, rebindMakerspace, rebindMakerspaceId, productRows,
    products, selectedProductId, setSelectedProductId, newName, setNewName, rebind,
    productError, rebindError, destinationMakerspaces, destMakerspaceId, setDestMakerspaceId, destProductId,
    setDestProductId, destinationProductRows, destinationProducts, moveTag, setMoveTag, moveAsset,
    destinationProductError, moveError, contents,
    unknownValue, setUnknownValue, canLinkExternal, canCreateExternal, onExternalLinked,
};
}
