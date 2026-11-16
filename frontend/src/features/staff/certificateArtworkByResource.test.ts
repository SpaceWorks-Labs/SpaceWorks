import { beforeEach, describe, expect, it, vi } from "vitest";

const { blob } = vi.hoisted(() => ({ blob: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequestBlob: blob }));

import { certificateArtworkByResource } from "./eventsCertificateDesignerApi";

beforeEach(() => blob.mockReset());

describe("old certificate image layers", () => {
  it("read their artwork by resource id inside the event, so no session upload is needed", async () => {
    const bytes = new Blob(["x"], { type: "image/png" });
    blob.mockResolvedValue(bytes);
    await expect(certificateArtworkByResource(4, "7c9e6679-7425-40de-944b-e07fc1f90ae7")).resolves.toBe(bytes);
    expect(blob).toHaveBeenCalledWith("/admin/events/4/certificate-artwork/by-resource/7c9e6679-7425-40de-944b-e07fc1f90ae7/");
  });
});
