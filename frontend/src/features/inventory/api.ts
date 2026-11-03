import { apiGet, tenantPublicRequest } from "../../lib/api";
import type { ContactHandover } from "./selfCheckoutApi";
import type {
  Makerspace,
  PaginatedResponse,
  Product,
  PublicCategory,
  PublicToolLoan,
  RequestSubmitResponse,
} from "../../types/inventory";

export const publicMakerspacesKey = ["public-makerspaces"] as const;

export const publicCategoriesKey = (slug: string) =>
  ["public-categories", slug] as const;
export const publicInventoryKey = (
  slug: string,
  page: number,
  query: string,
  category?: string,
  sort?: string,
) =>
  [
    "public-inventory",
    slug,
    page,
    query,
    category ?? "",
    sort ?? "name",
  ] as const;

export async function fetchPublicMakerspaces(): Promise<Makerspace[]> {
  return apiGet<Makerspace[]>("/public/makerspaces/");
}

export async function fetchPublicCategories(
  slug: string,
): Promise<PublicCategory[]> {
  return apiGet<PublicCategory[]>(`/public/${slug}/inventory/categories/`);
}

export async function fetchPublicInventory(
  slug: string,
  page: number,
  query: string,
  category?: string,
  sort?: string,
): Promise<PaginatedResponse<Product>> {
  const params = new URLSearchParams();
  if (page > 1) {
    params.set("page", String(page));
  }
  if (query.trim()) {
    params.set("q", query.trim());
  }
  if (category) {
    params.set("category", category);
  }
  if (sort && sort !== "name") {
    params.set("sort", sort);
  }

  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<PaginatedResponse<Product>>(
    `/public/${slug}/inventory/${suffix}`,
  );
}


export async function submitPublicRequest(
  slug: string,
  payload: {
    requested_for: string;
    items: { product_id: number; quantity: number }[];
    // Honeypot. The serializer pops it and a filled value gets the decoy response.
    website?: string;
    // Required where the makerspace has no member accounts (#80); ignored otherwise.
    contact_name?: string;
    contact_phone?: string;
    contact_email?: string;
    email_code?: string;
    // Lane L12: optional collection window (ISO datetimes) and a claimed waitlist offer.
    pickup_from?: string;
    pickup_until?: string;
    waitlist_entry_id?: number;
  },
): Promise<RequestSubmitResponse> {
  return tenantPublicRequest<RequestSubmitResponse>(
    slug,
    `/public/${slug}/requests`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

/** Mail the one-time code an account-less borrow request needs (202, no delivery detail). */
export async function requestContactCode(slug: string, email: string): Promise<void> {
  await tenantPublicRequest<void>(slug, `/public/${slug}/requests/email-code`, {
    method: "POST", body: JSON.stringify({ email }),
  });
}

export async function publicToolCheckout(
  slug: string,
  payload: {
    payload: string;
    evidence_id: number;
    remark?: string;
  } & ContactHandover,
): Promise<PublicToolLoan> {
  return tenantPublicRequest<PublicToolLoan>(
    slug,
    `/public/${slug}/tools/checkout`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function publicToolReturn(
  slug: string,
  payload: {
    payload: string;
    evidence_id: number;
    remark: string;
    report_problem?: boolean;
    problem_note?: string;
  } & ContactHandover,
): Promise<PublicToolLoan> {
  return tenantPublicRequest<PublicToolLoan>(
    slug,
    `/public/${slug}/tools/return`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
