import { describe, expect, it, vi } from "vitest";

import { geolocationErrorMessage, requestGeolocation } from "./geolocation";

describe("presence geolocation", () => {
  it("returns browser coordinates for an enabled geofence", async () => {
    const getCurrentPosition = vi.fn((success) => success({ coords: { latitude: 12.9, longitude: 77.5, accuracy: 8 } }));
    await expect(requestGeolocation({ geolocation: { getCurrentPosition } } as unknown as Navigator)).resolves.toEqual({ latitude: 12.9, longitude: 77.5, accuracy: 8 });
    expect(getCurrentPosition).toHaveBeenCalledOnce();
  });

  it.each([[1, "denied"], [2, "unavailable"], [3, "timed out"]])("explains geolocation error %s", (code, wording) => {
    expect(geolocationErrorMessage(code)).toContain(wording);
  });

  it("explains a browser without geolocation", async () => {
    await expect(requestGeolocation(undefined)).rejects.toThrow("unavailable");
  });
});
