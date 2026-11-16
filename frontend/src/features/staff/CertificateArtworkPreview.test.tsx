import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { blob } = vi.hoisted(() => ({ blob: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequestBlob: blob }));

import { CertificateArtworkPreview } from "./CertificateArtworkPreview";

const created: string[] = [];
const revoked: string[] = [];
beforeEach(() => {
  blob.mockReset(); created.length = 0; revoked.length = 0;
  blob.mockImplementation((path: string) => Promise.resolve(new Blob([path], { type: "image/png" })));
  URL.createObjectURL = vi.fn(() => { const url = `blob:artwork-${created.length + 1}`; created.push(url); return url; });
  URL.revokeObjectURL = vi.fn((url: string) => { revoked.push(url); });
});
afterEach(() => vi.restoreAllMocks());

describe("certificate artwork preview", () => {
  it("fetches the private artwork with the staff session and revokes its URL on change and unmount", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><CertificateArtworkPreview eventId={4} artworkId={11} /></QueryClientProvider>);
    expect(await screen.findByRole("img", { name: "Certificate artwork" })).toHaveAttribute("src", "blob:artwork-1");
    expect(blob).toHaveBeenCalledWith("/admin/events/4/certificate-artwork/11/");
    view.rerender(<QueryClientProvider client={client}><CertificateArtworkPreview eventId={4} artworkId={12} /></QueryClientProvider>);
    await waitFor(() => expect(screen.getByRole("img", { name: "Certificate artwork" })).toHaveAttribute("src", "blob:artwork-2"));
    expect(revoked).toContain("blob:artwork-1");
    view.unmount();
    expect(revoked).toContain("blob:artwork-2");
  });

  it("says so when the artwork can't be read", async () => {
    blob.mockRejectedValue(new Error("Forbidden"));
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><CertificateArtworkPreview eventId={4} artworkId={11} /></QueryClientProvider>);
    expect(await screen.findByText(/artwork preview is unavailable/)).toBeVisible();
  });
});
