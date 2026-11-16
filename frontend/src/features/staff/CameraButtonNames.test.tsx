import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PublicEvidenceUpload } from "../inventory/PublicEvidenceUpload";
import { requestPublicEvidenceUpload, uploadPublicEvidenceFile } from "../inventory/selfCheckoutApi";
import { ImageUploader } from "./ImageUploader";
import { EvidenceUpload } from "./panels/EvidenceUpload";

vi.mock("../inventory/selfCheckoutApi", () => ({ requestPublicEvidenceUpload: vi.fn(), uploadPublicEvidenceFile: vi.fn() }));

const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
describe("camera button accessible names", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: vi.fn() } });
  });
  afterEach(() => {
    if (originalMediaDevices) Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
    else Reflect.deleteProperty(navigator, "mediaDevices");
  });

  it("includes the visible Camera label and field context for public images", () => {
    render(<ImageUploader endpoint="/admin/makerspaces/3/image" label="Logo" onChanged={vi.fn()} disabled />);
    expect(screen.getByRole("button", { name: "Camera for Logo" })).toHaveTextContent("Camera");
    expect(screen.getByRole("button", { name: "Camera for Logo" })).toBeDisabled();
  });

  it("includes the visible Camera label and field context for staff evidence", () => {
    render(<EvidenceUpload makerspaceId={3} evidenceType="return" label="Return evidence" onUploaded={vi.fn()} disabled />);
    expect(screen.getByRole("button", { name: "Camera for Return evidence" })).toHaveTextContent("Camera");
    expect(screen.getByRole("button", { name: "Camera for Return evidence" })).toBeDisabled();
  });

  it("keeps public camera wording aligned before and after an actual file upload", async () => {
    vi.mocked(requestPublicEvidenceUpload).mockResolvedValue({ evidence_id: 7, evidence_grant: "grant", upload_url: "https://storage.test", fields: {}, object_key: "test" });
    vi.mocked(uploadPublicEvidenceFile).mockResolvedValue(undefined);
    const uploaded = vi.fn();
    render(<PublicEvidenceUpload slug="test" evidenceType="issue" onUploaded={uploaded} />);
    expect(screen.getByRole("button", { name: "Take photo with camera for Issue photo" })).toHaveTextContent("Take photo with camera");
    fireEvent.change(screen.getByLabelText("Issue photo"), { target: { files: [new File(["photo"], "issue.png", { type: "image/png" })] } });
    await waitFor(() => expect(uploaded).toHaveBeenLastCalledWith(7, "grant"));
    expect(screen.getByRole("button", { name: "Retake with camera for Issue photo" })).toHaveTextContent("Retake with camera");
    expect(requestPublicEvidenceUpload).toHaveBeenCalledWith("test", expect.objectContaining({ evidence_type: "issue", content_type: "image/png" }));
  });
});
