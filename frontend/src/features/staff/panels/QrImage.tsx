import { t } from "@lingui/core/macro";
import { useMemo } from "react";

import { useStaffGet } from "./shared";
import { BoxSpinner } from "../../../components/BoxSpinner";

type QrPrintPayload = {
  payload: string;
  svg: string;
};

export function QrImage({ qrId, label }: { qrId: number; label: string }) {
  const qr = useStaffGet<QrPrintPayload>(["qr-image", qrId], `/admin/qr/${qrId}/print`);
  const src = useMemo(() => {
    if (!qr.data?.svg) return "";
    return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(qr.data.svg)))}`;
  }, [qr.data?.svg]);

  if (qr.isLoading) {
    return <div className="grid aspect-square place-items-center rounded-md border border-line"><BoxSpinner label={t`Loading QR`} size={24} /></div>;
  }

  if (qr.isError || !src) {
    return <div className="grid aspect-square place-items-center rounded-md border border-danger/40 text-xs text-danger">{t`QR unavailable`}</div>;
  }

  return <img className="aspect-square w-full rounded-md border border-line bg-white p-2" src={src} alt={`${label} QR`} />;
}
