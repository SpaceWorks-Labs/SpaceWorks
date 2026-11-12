// Decision 345: a member-card photo over the server's 8 MB card-photo ceiling is refused before anything is sent.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), ...api }));

import { MEMBER_PHOTO_MAX_BYTES, uploadCardPhoto } from "./api";
import { CardPhotoUpload } from "./CardPhotoUpload";

const big = () => new File([new Uint8Array(MEMBER_PHOTO_MAX_BYTES + 1)], "huge.jpg", { type: "image/jpeg" });

it("refuses an over-8 MB photo before asking for an upload link", async () => {
  await expect(uploadCardPhoto(3, big())).rejects.toThrow(/larger than 8 MB/);
  expect(api.memberRequest).not.toHaveBeenCalled();
});

it("says the limit up front and rejects a too-large choice", () => {
  render(<QueryClientProvider client={new QueryClient()}><CardPhotoUpload makerspaceId={3} photoSet={false} consentAt={null} /></QueryClientProvider>);
  expect(screen.getByText("PNG, JPEG or WebP, up to 8 MB.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Choose a photo"), { target: { files: [big()] } });
  expect(screen.getByRole("status")).toHaveTextContent("larger than 8 MB");
});
