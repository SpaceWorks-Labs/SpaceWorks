import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { usePaginatedQuery } from "../../../lib/usePaginatedQuery";
import { type Makerspace, type Product, useStaffGet } from "./shared";
import { invalidateContainerViews, invalidateInventoryViews } from "../queryInvalidation";

type ListResponse<T> = { count?: number; results: T[] };
type Container = { id: number; code?: string; label: string; location?: string };
type TransferLine = { id: number; product: number | null; asset: number | null; quantity: number };
export type Transfer = {
  id: number;
  makerspace: number;
  source_container: number | null;
  destination_container: number | null;
  source_makerspace: number | null;
  destination_makerspace: number | null;
  reason: string;
  status: string;
  created_at: string;
  lines: TransferLine[];
};
type LineDraft = { key: number; productId: string; quantity: string };

export function useStockTransfer({
  makerspace,
  makerspaces,
  isSuperadmin,
  canEditInventory = false,
}: {
  makerspace: Makerspace;
  makerspaces: Makerspace[];
  isSuperadmin: boolean;
  canEditInventory?: boolean;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState("from");
  // EDIT_INVENTORY holders can run INTRA-makerspace relocations; only a superadmin gets the
  // source/destination makerspace selectors (cross-makerspace moves are superadmin-only).
  const canCreate = isSuperadmin || canEditInventory;
  const spaceOptions = makerspaces.length ? makerspaces : [makerspace];
  const [sourceMakerspaceId, setSourceMakerspaceId] = useState(makerspace.id);
  const [destinationMakerspaceId, setDestinationMakerspaceId] = useState(makerspace.id);
  const [sourceContainerId, setSourceContainerId] = useState("");
  const [destinationContainerId, setDestinationContainerId] = useState("");
  const [reason, setReason] = useState("");
  const [lineRows, setLineRows] = useState<LineDraft[]>([{ key: 1, productId: "", quantity: "1" }]);
  const [nextLineKey, setNextLineKey] = useState(2);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    setSourceMakerspaceId(makerspace.id);
    setDestinationMakerspaceId(makerspace.id);
    setSourceContainerId("");
    setDestinationContainerId("");
    setLineRows([{ key: 1, productId: "", quantity: "1" }]);
    setNextLineKey(2);
    setValidationError("");
  }, [makerspace.id]);

  const products = useStaffGet<ListResponse<Product>>(
    ["inventory", sourceMakerspaceId],
    `/admin/makerspace/${sourceMakerspaceId}/inventory?page_size=1000`,
    canCreate,
  );
  const transfers = usePaginatedQuery<Transfer>({
    key: ["transfers", sourceMakerspaceId],
    path: `/admin/makerspace/${sourceMakerspaceId}/stock-transfers`,
    resetKey: String(sourceMakerspaceId),
  });
  const sourceContainers = useStaffGet<ListResponse<Container>>(
    ["containers", sourceMakerspaceId],
    `/admin/makerspace/${sourceMakerspaceId}/containers?page_size=1000`,
    canCreate,
  );
  const destinationContainers = useStaffGet<ListResponse<Container>>(
    ["containers", destinationMakerspaceId],
    `/admin/makerspace/${destinationMakerspaceId}/containers?page_size=1000`,
    canCreate,
  );

  const makerspaceNames = useMemo(
    () => new Map(spaceOptions.map((space) => [space.id, space.name])),
    [spaceOptions],
  );
  const sourceContainerNames = useMemo(
    () => new Map((sourceContainers.data?.results ?? []).map((box) => [box.id, labelForContainer(box)])),
    [sourceContainers.data?.results],
  );
  const destinationContainerNames = useMemo(
    () => new Map((destinationContainers.data?.results ?? []).map((box) => [box.id, labelForContainer(box)])),
    [destinationContainers.data?.results],
  );

  const isCrossMakerspace = destinationMakerspaceId !== sourceMakerspaceId;

  const create = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${sourceMakerspaceId}/stock-transfers`, {
        method: "POST",
        body: JSON.stringify({
          // Cross-makerspace transfers ignore the source container (and the control is
          // disabled), so never send a stale value the backend would otherwise record.
          source_container_id:
            isCrossMakerspace || !sourceContainerId ? null : Number(sourceContainerId),
          // destination_container_id is resolved within the destination makerspace
          // (same makerspace for intra-transfers), so it is valid in both modes.
          destination_container_id: destinationContainerId ? Number(destinationContainerId) : null,
          destination_makerspace_id: isCrossMakerspace ? destinationMakerspaceId : null,
          reason: reason.trim(),
          lines: lineRows.map((line) => ({
            product_id: Number(line.productId),
            quantity: Number(line.quantity),
          })),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transfers", sourceMakerspaceId] });
      invalidateInventoryViews(queryClient, sourceMakerspaceId);
      invalidateContainerViews(queryClient, sourceMakerspaceId, sourceContainerId ? Number(sourceContainerId) : undefined);
      if (destinationMakerspaceId !== sourceMakerspaceId) {
        queryClient.invalidateQueries({ queryKey: ["transfers", destinationMakerspaceId] });
        invalidateInventoryViews(queryClient, destinationMakerspaceId);
      }
      invalidateContainerViews(queryClient, destinationMakerspaceId, destinationContainerId ? Number(destinationContainerId) : undefined);
      setSourceContainerId("");
      setDestinationContainerId("");
      setReason("");
      setLineRows([{ key: 1, productId: "", quantity: "1" }]);
      setNextLineKey(2);
      setValidationError("");
      setOpen(false);
      setStep("from");
    },
  });

  const changeSource = (nextId: number) => {
    setSourceMakerspaceId(nextId);
    setDestinationMakerspaceId(nextId);
    setSourceContainerId("");
    setDestinationContainerId("");
    setLineRows([{ key: 1, productId: "", quantity: "1" }]);
    setNextLineKey(2);
    setValidationError("");
  };

  const addLine = () => {
    setLineRows((rows) => [...rows, { key: nextLineKey, productId: "", quantity: "1" }]);
    setNextLineKey((key) => key + 1);
  };

  const updateLine = (key: number, patch: Partial<LineDraft>) => {
    setLineRows((rows) => rows.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  };

  const removeLine = (key: number) => {
    setLineRows((rows) => rows.filter((line) => line.key !== key));
  };

  const submit = () => {
    const invalidQuantity = lineRows.some((line) => !Number.isInteger(Number(line.quantity)) || Number(line.quantity) < 1);
    if (!reason.trim()) setValidationError(t`Reason is required.`);
    else if (!lineRows.length) setValidationError(t`Add at least one transfer line.`);
    else if (lineRows.some((line) => !line.productId)) setValidationError(t`Choose a product for every line.`);
    else if (invalidQuantity) setValidationError(t`Quantities must be whole numbers of at least 1.`);
    else {
      setValidationError("");
      create.mutate();
    }
  };

  return {
    canCreate, spaceOptions, sourceMakerspaceId, changeSource, destinationMakerspaceId,
    setDestinationMakerspaceId, sourceContainerId, setSourceContainerId, destinationContainerId, setDestinationContainerId,
    sourceContainers, destinationContainers, isCrossMakerspace, step, setStep,
    open, setOpen, reason, setReason, lineRows,
    updateLine, removeLine, addLine, products, create,
    validationError, submit, transfers, makerspaceNames, sourceContainerNames,
    destinationContainerNames,
  };
}

export function labelForContainer(container: Container) {
  return [container.code, container.label, container.location].filter(Boolean).join(" · ");
}
