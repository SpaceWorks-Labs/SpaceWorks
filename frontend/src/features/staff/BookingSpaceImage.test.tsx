import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { bookingImageRequest, BookingSpaceImage } from "./BookingSpaceImage";
import { uploadPublicImage } from "./ImageUploader";
import type { BookableSpace } from "./bookingsApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual("../../lib/api"), staffRequest: request,
  publicV1Request: async () => ({ public_image_max_bytes: 5 * 1024 * 1024 }) }));
beforeEach(() => { request.mockReset(); });
afterEach(() => { vi.unstubAllGlobals(); });

it("uses the existing nested presign and POST-finalize protocol without changing object keys", async () => {
  request.mockImplementation(async (path: string) => path.endsWith("presign/")
    ? { object_key: "spaces/7/3/test.png", upload: { url: "https://storage.example/upload", fields: { key: "staged/key" }, method: "POST" } }
    : { id: 3, image_url: "https://storage.example/test.png" });
  const storage = vi.fn(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", storage);
  await uploadPublicImage("/admin/spaces/3/image/", new File(["fixture"], "room.png", { type: "image/png" }), {}, bookingImageRequest);
  expect(request).toHaveBeenCalledWith("/admin/spaces/3/image/presign/",
    { method: "POST", body: JSON.stringify({ content_type: "image/png", filename: "room.png" }) }, undefined);
  expect(storage).toHaveBeenCalledWith("https://storage.example/upload", expect.objectContaining({ method: "POST" }));
  expect(request).toHaveBeenCalledWith("/admin/spaces/3/image/finalize/",
    { method: "POST", body: JSON.stringify({ object_key: "spaces/7/3/test.png" }) }, undefined);
});

it("keeps clearing on the existing DELETE endpoint and forwards explicit session context", async () => {
  request.mockResolvedValue(undefined);
  await bookingImageRequest("/admin/spaces/3/image/", { method: "DELETE" }, "platform");
  expect(request).toHaveBeenCalledWith("/admin/spaces/3/image/", { method: "DELETE" }, "platform");
});

it("shows the saved listing photo and disables replacement/removal for an inactive resource", () => {
  const space = { id: 3, image_url: "https://image.example/room.png", is_active: false } as BookableSpace;
  render(<QueryClientProvider client={new QueryClient()}><BookingSpaceImage makerspaceId={7} space={space} /></QueryClientProvider>);
  expect(screen.getByRole("img", { name: "Booking listing photo" })).toHaveAttribute("src", space.image_url);
  expect(screen.getByLabelText("Booking listing photo")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Remove" })).toBeDisabled();
});
