import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Gallery } from "./Gallery";
import { GalleryEditor } from "./GalleryEditor";
import { uploadGalleryPhoto } from "./galleryUpload";

const photos = [1, 2, 3, 4, 5, 6].map(id => ({ id, url: `https://img.test/${id}.webp`, caption: `Room view ${id}` }));

describe("Gallery", () => {
  it("renders nothing without photos unless an empty message is given", () => {
    const { container, rerender } = render(<Gallery photos={[]} label="Photos" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<Gallery photos={[]} label="Photos" emptyMessage="No photos yet." />);
    expect(screen.getByText("No photos yet.")).toBeInTheDocument();
  });

  it("shows a lead photo, four thumbnails and a +N overflow badge", () => {
    render(<Gallery photos={photos} label="Photos of Lab" />);
    expect(screen.getByRole("region", { name: "Photos of Lab" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Open / })).toHaveLength(5);
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("opens a viewer that pages with buttons and arrow keys and wraps around", () => {
    render(<Gallery photos={photos.slice(0, 3)} label="Photos of Lab" />);
    fireEvent.click(screen.getByRole("button", { name: "Open Room view 1" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Photos of Lab — 1 of 3")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /Next/ }));
    expect(within(dialog).getByText("Photos of Lab — 2 of 3")).toBeInTheDocument();
    fireEvent.keyDown(within(dialog).getByText("Room view 2"), { key: "ArrowRight" });
    fireEvent.keyDown(within(dialog).getByText("Room view 3"), { key: "ArrowRight" });
    expect(within(dialog).getByText("Photos of Lab — 1 of 3")).toBeInTheDocument();
    fireEvent.keyDown(within(dialog).getByText("Room view 1"), { key: "ArrowLeft" });
    expect(within(dialog).getByText("Photos of Lab — 3 of 3")).toBeInTheDocument();
  });
});

describe("GalleryEditor", () => {
  const handlers = () => ({
    onUpload: vi.fn().mockResolvedValue(undefined), onCaption: vi.fn().mockResolvedValue(undefined),
    onReorder: vi.fn().mockResolvedValue(undefined), onRemove: vi.fn().mockResolvedValue(undefined),
  });

  it("reorders with the move controls by sending the complete new order", async () => {
    const h = handlers();
    render(<GalleryEditor photos={photos.slice(0, 3)} maxPhotos={12} canEdit {...h} />);
    expect(screen.getByRole("button", { name: "Move photo 1 earlier" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Move photo 1 later" }));
    await waitFor(() => expect(h.onReorder).toHaveBeenCalledWith([2, 1, 3]));
  });

  it("uploads the chosen file, saves captions and confirms removal", async () => {
    const h = handlers();
    const { container } = render(<GalleryEditor photos={photos.slice(0, 2)} maxPhotos={12} canEdit {...h} />);
    const file = new File(["x"], "room.png", { type: "image/png" });
    fireEvent.change(container.querySelector("input[type=file]")!, { target: { files: [file] } });
    await waitFor(() => expect(h.onUpload).toHaveBeenCalledWith(file));
    fireEvent.change(screen.getByLabelText("Caption for photo 1"), { target: { value: "Bench row" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(h.onCaption).toHaveBeenCalledWith(1, "Bench row"));
    fireEvent.click(screen.getAllByRole("button", { name: /Remove/ })[1]);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove photo" }));
    await waitFor(() => expect(h.onRemove).toHaveBeenCalledWith(2));
  });

  it("is read-only without edit rights and blocks uploads when the gallery is full", () => {
    const { rerender } = render(<GalleryEditor photos={photos.slice(0, 2)} maxPhotos={12} canEdit={false}
      readOnlyMessage="Ask a Booking Manager." {...handlers()} />);
    expect(screen.queryByRole("button", { name: /Add photo/ })).not.toBeInTheDocument();
    expect(screen.getByText("Ask a Booking Manager.")).toBeInTheDocument();
    rerender(<GalleryEditor photos={photos.slice(0, 2)} maxPhotos={2} canEdit {...handlers()} />);
    expect(screen.getByRole("button", { name: /Gallery full/ })).toBeDisabled();
  });

  it("shows a failed change as an alert", async () => {
    const h = { ...handlers(), onReorder: vi.fn().mockRejectedValue(new Error("Order is stale.")) };
    render(<GalleryEditor photos={photos.slice(0, 2)} maxPhotos={12} canEdit {...h} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Move photo 2 earlier" })); });
    expect(await screen.findByRole("alert")).toHaveTextContent("Order is stale.");
  });
});

describe("uploadGalleryPhoto", () => {
  it("presigns, PUTs the bytes to storage and attaches the returned key", async () => {
    const transport = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    const presign = vi.fn().mockResolvedValue({ object_key: "spaces/1/2/images/a.png", upload: { url: "https://s3.test/x", method: "PUT", headers: { "Content-Type": "image/png" } } });
    const attach = vi.fn().mockResolvedValue({ id: 9 });
    const file = new File(["x"], "a.png", { type: "image/png" });
    await expect(uploadGalleryPhoto(file, { presign, attach, transport })).resolves.toEqual({ id: 9 });
    expect(presign).toHaveBeenCalledWith({ filename: "a.png", content_type: "image/png" });
    expect(transport).toHaveBeenCalledWith("https://s3.test/x", expect.objectContaining({ method: "PUT", body: file }));
    expect(attach).toHaveBeenCalledWith("spaces/1/2/images/a.png");
  });

  it("refuses non-image types before contacting the server and surfaces storage failures", async () => {
    const presign = vi.fn();
    await expect(uploadGalleryPhoto(new File(["x"], "a.gif", { type: "image/gif" }), { presign, attach: vi.fn() }))
      .rejects.toThrow("Use a JPEG, PNG or WebP photo.");
    expect(presign).not.toHaveBeenCalled();
    const failing = vi.fn().mockResolvedValue(new Response(null, { status: 403 }));
    await expect(uploadGalleryPhoto(new File(["x"], "a.png", { type: "image/png" }), {
      presign: vi.fn().mockResolvedValue({ object_key: "k", upload: { url: "https://s3.test/x", fields: { key: "k" } } }),
      attach: vi.fn(), transport: failing,
    })).rejects.toThrow("Photo upload failed (403)");
  });
});
