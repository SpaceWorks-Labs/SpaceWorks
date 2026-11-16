import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { publicV1Request, staffRequest } from "../../../lib/api";
import { EventCoverUploader } from "./EventCoverUploader";

vi.mock("../../../lib/api", () => ({ publicV1Request: vi.fn(), staffRequest: vi.fn() }));
const file = new File(["prepared-cover"], "event-cover.webp", { type: "image/webp" });
vi.mock("./CoverPhotoEditor", () => ({
  CoverPhotoEditor: ({ onSave }: { onSave: (file: File) => Promise<void> }) =>
    <button onClick={() => { void onSave(file); }}>Save prepared cover</button>,
}));

beforeEach(() => { vi.clearAllMocks(); });
afterEach(() => { vi.restoreAllMocks(); });

it.each([
  ["/admin/events/12/image", "PUT"], ["/admin/event-series/12/image", "PUT"],
  ["/admin/events/12/image", "POST"], ["/admin/event-series/12/image", "POST"],
])("declares the prepared cover size at %s and honors %s", async (endpoint, method) => {
  vi.mocked(publicV1Request).mockResolvedValue({ public_image_max_bytes: 10000 });
  const headers = { "Content-Type": file.type, "Content-Length": String(file.size) };
  vi.mocked(staffRequest).mockResolvedValueOnce({ object_key: "event/3/cover.webp",
    url: "https://storage.test/upload", method, headers, fields: { key: "staging/event/3/cover.webp" },
  }).mockResolvedValueOnce({});
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 200 }));
  const changed = vi.fn();
  render(<EventCoverUploader endpoint={endpoint} currentUrl={null} label="Cover" onChanged={changed} />);
  fireEvent.click(screen.getByRole("button", { name: "Add a cover" }));
  fireEvent.click(screen.getByRole("button", { name: "Save prepared cover" }));
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  expect(staffRequest).toHaveBeenNthCalledWith(1, endpoint, { method: "POST", body: JSON.stringify({
    content_type: file.type, filename: file.name, size: file.size,
  }) });
  expect(staffRequest).toHaveBeenNthCalledWith(2, endpoint, { method: "PUT",
    body: JSON.stringify({ object_key: "event/3/cover.webp" }),
  });
  if (method === "PUT") {
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith("https://storage.test/upload", { method, body: file, headers });
  } else {
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const request = fetchMock.mock.calls[0][1];
    expect(request?.method).toBe("POST");
    const data = request?.body as FormData;
    expect(data.get("key")).toBe("staging/event/3/cover.webp");
    expect((data.get("file") as File).size).toBe(file.size);
    expect((data.get("file") as File).name).toBe(file.name);
  }
});
