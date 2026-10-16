import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest, tenantPublicRequest, StructuredApiError } from "../../lib/api";
import type { BookingWebsite, PublicBookingResource } from "./bookingWebsiteTypes";
import { websiteContent } from "./bookingWebsiteTypes";

export const bookingWebsiteKey = (tenant: number, resource: number) => ["booking-website", tenant, resource] as const;
const base = (id: number) => `/admin/spaces/${id}/website/`;

export function useBookingWebsite(tenant: number, id: number) {
  return useQuery({ queryKey: bookingWebsiteKey(tenant, id), staleTime: 0,
    queryFn: () => staffRequest<BookingWebsite>(base(id)),
  });
}
export function useBookingWebsiteMutation(tenant: number, id: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { page: BookingWebsite } | { released: boolean; revision: number } | { asset: FormData } | { remove: number }) => {
      if ("page" in input) return staffRequest(base(id), { method: "PUT", body: JSON.stringify(websiteContent(input.page)) });
      if ("asset" in input) return staffRequest(`${base(id)}assets/`, { method: "POST", body: input.asset });
      if ("remove" in input) return staffRequest(`${base(id)}assets/${input.remove}/`, { method: "DELETE" });
      return staffRequest(`${base(id)}release/`, { method: "POST", body: JSON.stringify(input) });
    },
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: bookingWebsiteKey(tenant, id) }),
      ...["public-booking-resource", "public-website-image", "booking-discover", "bookings", "booking-space", "public-spaces"].map((key) => client.invalidateQueries({ queryKey: [key] })),
    ]),
  });
}
export function usePublicBookingResource(slug: string, token: string) {
  return useQuery({ queryKey: ["public-booking-resource", slug, token], staleTime: 0, gcTime: 0,
    enabled: Boolean(slug && token),
    queryFn: () => tenantPublicRequest<PublicBookingResource>(slug, `/public/${slug}/spaces/${token}/`),
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
}
