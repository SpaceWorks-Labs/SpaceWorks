import { t } from "@lingui/core/macro";
import { ArrowLeftRight, ClipboardCheck, Container, Printer, Tag, Upload } from "lucide-react";
import type { CataloguePart } from "./types";

/** Inventory group, part 2: stock movement, units and stocktake. */
export const inventoryStock = (): CataloguePart => ({
  bulk_import: { icon: Upload, value: t`Bring a spreadsheet of stock in.`,
    what: t`Import products and assets from CSV, check the rows before anything is created, and fix what is flagged.`,
    roles: [t`Inventory managers`], 
    noLimits: t`It creates products and assets, which their own limits already cap.`, integrations: [t`CSV and XLSX files`] },
  containers: { icon: Container, value: t`Boxes and kits that hold other things.`,
    what: t`Group items into containers and kits, move them between locations and check a kit list on return.`,
    roles: [t`Inventory managers`, t`Staff`], 
    noLimits: t`Containers are QR boxes and are counted by the boxes limit.`, integrations: [t`QR codes`] },
  stock_transfers: { icon: ArrowLeftRight, value: t`Move stock between locations on the record.`,
    what: t`Transfers between shelves, rooms or sites are recorded with who moved what and when, so counts stay true.`,
    roles: [t`Inventory managers`], 
    integrations: [] },
  qr_print_batches: { icon: Printer, value: t`Print labels for many boxes at once.`,
    what: t`Choose boxes, lay them out on a sheet or a label roll and print. Sheets are made from existing boxes and are not kept.`,
    roles: [t`Inventory managers`], 
    noLimits: t`Label sheets are made from existing boxes and are not stored.`, integrations: [t`Label printers`, t`PDF sheets`] },
  asset_units: { icon: Tag, value: t`Track each individual unit.`,
    what: t`Serialised tools get a status, history and QR of their own, so a missing drill is a specific drill.`,
    roles: [t`Inventory managers`], 
    integrations: [t`QR codes`, t`Warranty tracking`] },
  stocktake: { icon: ClipboardCheck, value: t`Scan-first stock counts.`,
    what: t`Count by scanning, see variance against the book as you go and close the count with an audit trail.`,
    roles: [t`Inventory managers`], 
    integrations: [t`Camera scanning`] },
});
