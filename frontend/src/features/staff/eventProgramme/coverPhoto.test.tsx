import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StructuredApiError } from "../../../lib/api";
import { CoverPhotoEditor } from "./CoverPhotoEditor";
import { renderCover } from "./coverImage";
vi.mock("./coverImage", async importOriginal => ({ ...await importOriginal<typeof import("./coverImage")>(), renderCover: vi.fn() }));
afterEach(() => { vi.unstubAllGlobals(); });

function stubImage() {
  const revoke = vi.fn(); const NativeURL = URL;
  vi.stubGlobal("URL", class extends NativeURL { static createObjectURL = vi.fn(() => "blob:private-cover"); static revokeObjectURL = revoke; });
  vi.stubGlobal("Image", class {
    naturalWidth = 3000; naturalHeight = 2000; onload: (() => void) | null = null; onerror: (() => void) | null = null;
    set src(_value: string) { setTimeout(() => this.onload?.(), 0); }
  });
  return revoke;
}
const pick = () => fireEvent.change(screen.getByLabelText("Image"), { target: { files: [new File(["input"], "cover.png", { type: "image/png" })] } });

it("offers crop, flip, looks and colour controls once an image opens", async () => {
  stubImage();
  render(<CoverPhotoEditor onSave={vi.fn()} />);
  pick();
  expect(await screen.findByRole("group", { name: /Cover crop, 16:7/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Flip horizontally" }));
  expect(screen.getByRole("button", { name: "Flip horizontally" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("radio", { name: /Square/ }));
  expect(screen.getByRole("group", { name: /Cover crop, 1:1/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("radio", { name: "Mono" }));
  expect(screen.getByRole("radio", { name: "Mono" })).toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(screen.getByRole("radio", { name: "Original" })).toBeChecked();
});

it("saves a WebP file named for its type and hides the description for covers", async () => {
  stubImage();
  vi.mocked(renderCover).mockResolvedValue(new Blob(["cover"], { type: "image/webp" }));
  const onSave = vi.fn().mockResolvedValue(undefined);
  render(<CoverPhotoEditor onSave={onSave} describe={false} />);
  pick(); await screen.findByRole("group", { name: /Cover crop/ });
  expect(screen.queryByLabelText("Image description")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Save cover" }));
  await waitFor(() => expect(onSave).toHaveBeenCalled());
  expect(onSave.mock.calls[0][0]).toMatchObject({ name: "event-cover.webp", type: "image/webp" });
});

it("clears cover bytes, preview URLs and alt text on denied save", async () => {
  const revoke = stubImage();
  vi.mocked(renderCover).mockResolvedValue(new Blob(["cover"], { type: "image/jpeg" }));
  render(<CoverPhotoEditor onSave={async () => { throw new StructuredApiError(403, { detail: "Access withdrawn" }); }} />);
  pick(); await screen.findByRole("group", { name: /Cover crop/ });
  fireEvent.change(screen.getByLabelText("Image description"), { target: { value: "Private cover description" } });
  fireEvent.click(screen.getByRole("button", { name: "Save cover" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Access withdrawn");
  expect(screen.queryByRole("group", { name: /Cover crop/ })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Image description")).not.toBeInTheDocument();
  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:private-cover"));
});
