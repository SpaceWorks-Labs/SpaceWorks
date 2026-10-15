import { DetailLayout } from "../../components/layouts";
import { StatusPill } from "../../components/ui";
import type { Product } from "../../types/inventory";
import { AvailabilityBadge } from "./AvailabilityBadge";

type ProductQuickViewModalProps = { product: Product | null; open: boolean; onClose: () => void };

function trackingLabel(product: Product) {
  if (product.tracking_mode === "individual") return "Serialized";
  if (product.tracking_mode === "quantity") return "Quantity-tracked";
  return "Catalog item";
}

export function ProductQuickViewModal({ product, open, onClose }: ProductQuickViewModalProps) {
  if (!product) return null;
  return <DetailLayout presentation="drawer" open={open} onClose={onClose} drawerWidth={720}
    title={product.name} state={{ status: "ready" }} status={<AvailabilityBadge availability={product.availability} />}
    meta={[`ID: ${String(product.id).padStart(4, "0")}`, trackingLabel(product)]}
    main={<div className="grid gap-6">
      {product.image_url ? <img src={product.image_url} alt={product.name} className="aspect-[16/10] w-full rounded-xl border border-line bg-surface object-contain" />
        : <div aria-hidden="true" className="grid aspect-[16/10] place-items-center rounded-xl border border-line bg-surface font-display text-6xl text-ink">{product.name.slice(0, 2)}</div>}
      {product.category_name ? <div><StatusPill label={product.category_name} /></div> : null}
      <section aria-label="Description"><h2 className="title-panel">Description</h2>
        <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7">{product.description.trim() || "No description provided."}</p>
      </section>
    </div>}
    footer={{ secondary: [{ label: "Close", onClick: onClose }] }} />;
}
