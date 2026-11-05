import { Card, DateChip, StatusPill } from "../../components/ui";
import type { EventFormValues } from "./EventFormFields";
import type { SeriesFormValues } from "./EventSeriesForm";
import { useStaffChargesOn } from "./useStaffChargesOn";

export function EventCreatePreview({ values }: { values: EventFormValues | SeriesFormValues }) {
  const chargesOn = useStaffChargesOn("events"); // #184: no price in a free domain
  const date = "starts_at" in values ? values.starts_at : values.dtstart_local_date;
  return <Card>
    <div className="flex items-start gap-4">{date ? <DateChip date={date} draft /> : null}<div className="min-w-0"><StatusPill label="Draft" tone="neutral" /><h2 className="title-panel mt-3 break-words">{values.title || "Your event title"}</h2></div></div>
    <p className="mt-4 text-sm text-muted">{values.location || "Location to be confirmed"}</p>
    {values.description ? <p className="mt-4 whitespace-pre-wrap text-sm">{values.description}</p> : null}
    <p className="mt-4 text-sm">{values.capacity ? `${values.capacity} places` : "Unlimited places"}{chargesOn ? ` · ${Number(values.payment_amount) === 0 ? "Free" : values.payment_amount}` : ""}</p>
    <p className="mt-4 text-xs text-muted">{values.is_public ? "This event will appear on your public events page after publishing." : "This event stays private after publishing."}</p>
  </Card>;
}
