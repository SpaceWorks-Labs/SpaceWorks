import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobFileUpload } from "./JobFileUpload";

const { staffRequest, uploadToStorage } = vi.hoisted(() => ({ staffRequest: vi.fn(), uploadToStorage: vi.fn() }));
vi.mock("../../../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../../../lib/api")), staffRequest }));
vi.mock("../../../../printing/publicApi", () => ({ uploadToStorage }));

const upload = { url: "https://storage.example/bucket", fields: { key: "staging/1" } };
const pick = (name = "part.stl") => fireEvent.change(screen.getByLabelText("Add a file"),
  { target: { files: [new File(["solid"], name, { type: "model/stl" })] } });

beforeEach(() => { staffRequest.mockReset(); uploadToStorage.mockReset(); });

describe("JobFileUpload", () => {
  it("presigns, uploads to storage, then finalizes the file on the job", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/presign") ? { file_id: 31, upload } : { file_id: 31 }));
    uploadToStorage.mockResolvedValue(undefined);
    const onUploaded = vi.fn();
    render(<JobFileUpload requestId={90} onUploaded={onUploaded} />);
    pick();
    await waitFor(() => expect(onUploaded).toHaveBeenCalled());
    expect(staffRequest).toHaveBeenNthCalledWith(1, "/admin/machine-service/requests/90/files/presign",
      { method: "POST", body: JSON.stringify({ filename: "part.stl", content_type: "model/stl" }) });
    expect(uploadToStorage).toHaveBeenCalledWith(upload, expect.any(File));
    expect(staffRequest).toHaveBeenNthCalledWith(2, "/admin/machine-service/requests/90/files/finalize",
      { method: "POST", body: JSON.stringify({ file_id: 31 }) });
    expect(screen.getByRole("status")).toHaveTextContent("part.stl added.");
  });

  it("deletes the staged file when the upload fails", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(path.endsWith("/presign") ? { file_id: 32, upload } : undefined));
    uploadToStorage.mockRejectedValue(new Error("Upload failed (403)"));
    const onUploaded = vi.fn();
    render(<JobFileUpload requestId={90} onUploaded={onUploaded} />);
    pick("big.stl");
    expect(await screen.findByText("Upload failed (403)")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/files/32", { method: "DELETE" });
    expect(onUploaded).not.toHaveBeenCalled();
  });
});
