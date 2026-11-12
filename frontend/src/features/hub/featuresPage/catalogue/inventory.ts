import { t } from "@lingui/core/macro";
import { Boxes, Camera, ClipboardList, HandHelping, LayoutDashboard, QrCode, ScanLine } from "lucide-react";
import type { CataloguePart } from "./types";

/** Inventory group, part 1: the loan spine (catalogue, requests, handover, evidence, QR). */
export const inventorySpine = (): CataloguePart => ({
  public_inventory: { icon: Boxes, value: t`A public catalogue anyone can browse.`,
    what: t`Your hardware, listed for the community with availability shown the way you choose: exact count, a status label or hidden. Visitors never see where things are stored, box IDs or who borrowed what.`,
    roles: [t`Visitors`, t`Members`, t`Space managers`],
    
    
    integrations: [t`Embeddable page`, t`Custom domain`], newIn: [t`Kiosk checkout at a shelf station`, t`Shelf pointer: light the shelf for an item`] },
  request_workflow: { icon: ClipboardList, value: t`Borrow requests staff review, then hand over.`,
    what: t`Members ask for hardware, staff accept or reject, and the request moves through issued and returned with an audit entry at every step. Nothing is issued without a box scan and a photo.`,
    roles: [t`Members`, t`Space managers`, t`Inventory managers`],
    
    
    integrations: [t`Telegram and email alerts`] },
  staff_admin: { icon: LayoutDashboard, value: t`The staff console: inventory, requests and settings.`,
    what: t`Where staff run the space: inventory and requests, roles and staff, colour and branding, and the module switches that turn areas on or off. Every action is scoped to the space and audited.`,
    roles: [t`Space managers`, t`Inventory managers`, t`Custom roles`],
    
    integrations: [t`Signed API clients`],
    newIn: [t`Colour settings with a live preview`, t`Module switches grouped like these pages`, t`Motion and loading polish across the console`] },
  guest_handover: { icon: HandHelping, value: t`A front-desk view for issue and return.`,
    what: t`Volunteers at the desk issue accepted requests, create direct handouts and process returns, with the same evidence rules as staff and nothing else on screen. Handover is a custom role, so each space decides who gets it.`,
    roles: [t`Front-desk staff`, t`Volunteers`], 
    integrations: [t`Scanner and photo capture`] },
  scanner: { icon: ScanLine, value: t`Scan a box and see what is in it.`,
    what: t`Phone or tablet scanning for boxes, assets and containers, with container lookup and a kiosk station for self-checkout where a space allows it.`,
    roles: [t`Staff`, t`Members at a kiosk`], 
    integrations: [t`Camera scanning`, t`Kiosk checkout`], newIn: [t`Kiosk checkout at the shelf`] },
  evidence_uploads: { icon: Camera, value: t`A photo and a remark for every handover.`,
    what: t`Issue and return photos are uploaded straight to private storage and attached once, never replaced. Photo files can expire on your retention schedule while the record of who, when and what stays for good.`,
    roles: [t`Staff`, t`Members at self-checkout`], 
    integrations: [t`S3-compatible private storage`] },
  qr_management: { icon: QrCode, value: t`Generate, print and revoke QR codes.`,
    what: t`Each box and asset gets its own code. Revoking a code stops it working immediately and keeps its scan history.`,
    roles: [t`Inventory managers`], 
    integrations: [t`Label and sheet printers`] },
});
