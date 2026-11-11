import { t } from "@lingui/core/macro";
import { ProductCard } from "../../inventory/ProductCard";
import type { Availability } from "../../../types/inventory";
import type { ItemForm } from "./InventoryPanelShared";
export function publicPreviewAvailability(form: ItemForm): Availability {
 if (!form.is_public || form.public_availability_mode === "hidden") return null;
 const available = Number(form.available_quantity), total = Number(form.total_quantity);
 // The API contract code, not display copy: AvailabilityBadge translates it.
 const label = available <= 0 || total <= 0 ? "Unavailable" : available <= Math.ceil(total * .2) ? "Limited" : "Available";
 return form.public_availability_mode === "exact_count" && form.show_public_count ? { mode: "exact_count", label, count: available } : { mode: "status_only", label };
}
export function InventoryPublicPreview({ form, category }: { form: ItemForm; category?: string }) {
 if (!form.is_public) return <p className="rounded-xl border border-dashed border-line p-6 text-sm text-muted">{t`Private item. This won't appear in the public catalogue.`}</p>;
 return <div inert><ProductCard product={{ id: 0, name: form.name || "Item name", description: form.description, category_name: category, borrowing_terms: form.borrowing_terms, availability: publicPreviewAvailability(form) }} quantity={0}
   onIncrement={() => {}} onDecrement={() => {}} onOpenDetails={() => {}} /></div>;
}
