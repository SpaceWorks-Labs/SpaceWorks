import { t } from "@lingui/core/macro";
import { useCallback, useState } from "react";
import { staffRequest } from "../../lib/api";
import { useStaffGet } from "./StaffPanels";
import type { ContainerResponse, QrResolveResponse } from "./DirectLoansTypes";

/**
 * The optional handout container: the full list (its own cache key, so a truncated first page of
 * the shared ["containers"] entry can't leak in), the picked id, and a scan that only accepts a
 * container this list holds. Shared by the counter form and the guided handout.
 */
export function useDirectLoanContainer(makerspaceId: number) {
  const containers = useStaffGet<ContainerResponse>(["containers-all", makerspaceId],
    `/admin/makerspace/${makerspaceId}/containers?page_size=1000`);
  const [containerId, setContainerId] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState("");
  const options = Array.isArray(containers.data) ? containers.data : containers.data?.results ?? [];
  const scan = async (payload: string) => {
    try {
      const result = await staffRequest<QrResolveResponse>("/admin/qr/resolve", { method: "POST", body: JSON.stringify({ payload }) });
      const target = result.target;
      if (target.type !== "box") { setScanError(t`Scanned QR is not a container.`); return; }
      if (!options.some(container => container.id === target.id)) {
        setScanError(t`That container isn't available for handout (inactive or not found).`);
        return;
      }
      setContainerId(String(target.id));
      setScanError("");
    } catch {
      setScanError(t`Could not resolve the scanned QR.`);
    } finally {
      setScanning(false);
    }
  };
  const reset = useCallback(() => { setContainerId(""); setScanning(false); setScanError(""); }, []);
  return {
    containerId, scanning, error: containers.error, label: options.find(row => String(row.id) === containerId)?.label,
    scan, reset, closeScanner: () => setScanning(false),
    field: { containerId, onContainerIdChange: setContainerId, containerOptions: options, containersLoading: containers.isLoading,
      scanError, onScanClick: () => { setScanError(""); setScanning(true); } },
  };
}
