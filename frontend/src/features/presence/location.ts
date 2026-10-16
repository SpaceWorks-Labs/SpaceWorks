// Browser location for self check-in. The reading is sent once and discarded by the server;
// GPS is a convenience control (spoofable), never an identity proof.
export type LocationReading = { latitude: number; longitude: number; accuracy: number };
export type LocationFailure = "denied" | "unavailable" | "timeout" | "unsupported";
export type LocationOutcome = { ok: true; reading: LocationReading } | { ok: false; reason: LocationFailure };
type BrowserLike = { geolocation?: Geolocation; permissions?: Permissions };

const browser = (): BrowserLike | undefined => (typeof navigator === "undefined" ? undefined : navigator);

export function readLocation(source: BrowserLike | undefined = browser()): Promise<LocationOutcome> {
  if (!source?.geolocation) return Promise.resolve({ ok: false, reason: "unsupported" });
  return new Promise((resolve) => {
    source.geolocation!.getCurrentPosition(
      (position) => resolve({ ok: true, reading: { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy } }),
      (error) => resolve({ ok: false, reason: error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable" }),
      { enableHighAccuracy: true, timeout: 15_000, maximumAge: 0 },
    );
  });
}

/** "denied" up front lets the sheet explain before the person presses anything. */
export async function locationPermission(source: BrowserLike | undefined = browser()): Promise<PermissionState | "unknown"> {
  if (!source?.geolocation) return "unknown";
  try {
    return (await source.permissions?.query({ name: "geolocation" }))?.state ?? "unknown";
  } catch {
    return "unknown";
  }
}

export const LOCATION_FAILURE_TEXT: Record<LocationFailure, string> = {
  denied: "Location access is blocked for this site. Allow location in your browser settings, then retry.",
  unavailable: "Your device couldn't find your location. Check that location services are on, then retry.",
  timeout: "Finding your location took too long. Retry, ideally near a window.",
  unsupported: "This browser can't share a location.",
};
