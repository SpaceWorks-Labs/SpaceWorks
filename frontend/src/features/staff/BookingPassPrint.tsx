import { usePrintBookingPass } from "./bookingPassApi";

export function BookingPassPrint({ spaceId, bookingId, disabled = false }: {
  spaceId: number; bookingId: number; disabled?: boolean;
}) {
  const print = usePrintBookingPass(spaceId, bookingId);
  return <div className="grid gap-2">
    <button type="button" className="desk-button-secondary w-fit" disabled={disabled || print.isPending} onClick={() => print.mutate()}>
      {print.isPending ? "Rendering pass..." : "Print booking pass"}
    </button>
    {print.error ? <p role="alert" className="text-danger">{print.error.message}</p> : null}
  </div>;
}
