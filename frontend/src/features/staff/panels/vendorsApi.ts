import { staffRequest } from "../../../lib/api";

/** A saved supplier (`inventory.vendors`). Archived vendors keep every purchase link; nothing is deleted. */
export type Vendor = {
  id: number;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  website: string;
  notes: string;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type VendorDraft = Pick<Vendor, "name" | "contact_name" | "email" | "phone" | "website" | "notes">;

export const emptyVendorDraft: VendorDraft = { name: "", contact_name: "", email: "", phone: "", website: "", notes: "" };

export const vendorKeys = {
  all: (makerspaceId: number) => ["procurement-vendors", makerspaceId] as const,
  list: (makerspaceId: number, archived: boolean) => ["procurement-vendors", makerspaceId, archived] as const,
};

const base = (makerspaceId: number) => `/procurement/makerspace/${makerspaceId}/vendors`;

export const vendorsApi = {
  list: (makerspaceId: number, archived = false) => staffRequest<Vendor[]>(`${base(makerspaceId)}${archived ? "?archived=1" : ""}`),
  create: (makerspaceId: number, draft: VendorDraft) =>
    staffRequest<Vendor>(base(makerspaceId), { method: "POST", body: JSON.stringify(draft) }),
  update: (makerspaceId: number, id: number, patch: Partial<VendorDraft> & { is_archived?: boolean }) =>
    staffRequest<Vendor>(`${base(makerspaceId)}/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
};

export function draftFromVendor(vendor: Vendor): VendorDraft {
  return { name: vendor.name, contact_name: vendor.contact_name, email: vendor.email, phone: vendor.phone,
    website: vendor.website, notes: vendor.notes };
}
