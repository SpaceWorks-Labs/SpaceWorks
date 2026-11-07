import { t } from "@lingui/core/macro";
import { usePrintBookingPass } from "./bookingPassApi";

export function BookingPassPrint({ spaceId, bookingId, disabled = false }: {
  spaceId: number; bookingId: number; disabled?: boolean;
}) {
  const print = usePrintBookingPass(spaceId, bookingId);
  return <div className="grid gap-2">
    <button type="button" className="desk-button w-fit" disabled={disabled || print.isPending} onClick={() => print.mutate()}>
      {print.isPending ? t`Rendering pass...` : t`Print booking pass`}
    </button>
    {print.error ? <p role="alert" className="text-danger">{print.error.message}</p> : null}
  </div>;
}
