import { t } from "@lingui/core/macro";
import { SettingsSection } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { ImageUploader } from "./ImageUploader";
import { useSpaceInvalidation, type BookableSpace } from "./bookingsApi";

type Presign = { object_key: string; upload: { url: string; fields?: Record<string, string>; method?: string; headers?: Record<string, string> } };

/** The existing booking image API uses separate presign/finalize routes and a nested upload. */
export const bookingImageRequest: typeof staffRequest = async <T,>(path: string, options: RequestInit = {}, context?: Parameters<typeof staffRequest>[2]) => {
  if (options.method === "POST") {
    const result = await staffRequest<Presign>(`${path}presign/`, options, context);
    return { object_key: result.object_key, ...result.upload } as T;
  }
  if (options.method === "PUT") return staffRequest<T>(`${path}finalize/`, { ...options, method: "POST" }, context);
  return staffRequest<T>(path, options, context);
};

export function BookingSpaceImage({ makerspaceId, space }: { makerspaceId: number; space: BookableSpace }) {
  const invalidate = useSpaceInvalidation(makerspaceId, space.id);
  return <SettingsSection title={t`Listing photo`} description={t`Shown on the booking listing and the space details. Add extra photos in the Photos tab.`}>
    <ImageUploader endpoint={`/admin/spaces/${space.id}/image/`} request={bookingImageRequest} currentUrl={space.image_url}
      label={t`Booking listing photo`} shape="wide" disabled={!space.is_active} onChanged={() => { void invalidate(); }} />
  </SettingsSection>;
}
