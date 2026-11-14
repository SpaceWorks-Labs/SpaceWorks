import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, publicV1Request, staffRequest, tenantPublicRequest } from "../../lib/api";
import { uploadGalleryPhoto } from "../../components/ui/galleryUpload";
import { uploadAsset } from "../../components/card-designer/designerApi";
import { uploadCardPhoto } from "../members/memberCard/api";
import { uploadCardPhoto as uploadWalletPhoto } from "../members/wallet/api";
import { uploadJoinPhoto } from "../members/joinFields/uploadJoinPhoto";
import { stageJobFile } from "../machine-jobs/api";
import { uploadPublicImage } from "./ImageUploader";
import { uploadMachineDocument } from "./machineDocumentsApi";
import { uploadWarrantyDocument } from "./warrantyApi";
import { uploadIssuePhoto } from "./repairs/repairsApi";

vi.mock("../../lib/api", async () => ({
  ...(await vi.importActual<object>("../../lib/api")),
  memberRequest: vi.fn(), memberRequestBlob: vi.fn(), publicV1Request: vi.fn(), staffRequest: vi.fn(),
  publicRequest: vi.fn(), tenantPublicRequest: vi.fn(), staffRequestBlob: vi.fn(),
}));

const file = new File(["évidence"], "photo.png", { type: "image/png" });
const upload = { url: "https://storage.test/put", method: "PUT", fields: {},
  headers: { "Content-Type": file.type, "Content-Length": String(file.size) } };
const presigned = { ...upload, upload, object_key: "staging/photo", content_type: file.type,
  file_id: 7, asset_id: "asset", photo_token: "proof", max_bytes: 1000 };
const helpers = [
  { name: "card artwork", request: staffRequest, run: () => uploadAsset(3, "background", file) },
  { name: "public image", request: staffRequest, run: () => uploadPublicImage("/image", file) },
  { name: "machine document", request: staffRequest, run: () => uploadMachineDocument(3, file, "manual") },
  { name: "warranty document", request: staffRequest, run: () => uploadWarrantyDocument(3, file) },
  { name: "repair photo", request: staffRequest, run: () => uploadIssuePhoto(3, file) },
  { name: "member photo", request: memberRequest, run: () => uploadCardPhoto(3, file) },
  { name: "wallet photo", request: memberRequest,
    run: () => uploadWalletPhoto({ kind: "programme_card", id: 3 } as Parameters<typeof uploadWalletPhoto>[0], file) },
  { name: "join photo", request: memberRequest, run: () => uploadJoinPhoto(3, file) },
  { name: "machine job", request: tenantPublicRequest, run: () => stageJobFile("space", 3, file, "model") },
];

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(publicV1Request).mockResolvedValue({ public_image_max_bytes: 1000 });
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 200 }));
});
afterEach(() => vi.restoreAllMocks());

describe("presign declarations (540)", () => {
  it.each(helpers)("$name sends the actual byte size and honors bounded PUT", async ({ request, run }) => {
    vi.mocked(request).mockResolvedValueOnce(presigned).mockResolvedValueOnce({});
    await run();
    const call = vi.mocked(request).mock.calls[0];
    const options = call[call.length - 1] as RequestInit;
    expect(options.method).toBe("POST");
    expect(JSON.parse(String(options.body))).toMatchObject({ size: file.size });
    expect(fetch).toHaveBeenCalledExactlyOnceWith(upload.url, { method: "PUT", body: file, headers: upload.headers });
  });

  it.each(helpers)("$name stops after a typed quota refusal", async ({ request, run }) => {
    const refusal = Object.assign(new Error("upload_limit"), { code: "upload_limit", status: 400 });
    vi.mocked(request).mockRejectedValueOnce(refusal);
    await expect(run()).rejects.toBe(refusal);
    expect(request).toHaveBeenCalledTimes(1);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("gallery presign carries bytes alongside the filename and MIME type", async () => {
    const presign = vi.fn().mockResolvedValue(presigned);
    const attach = vi.fn().mockResolvedValue({ id: 5 });
    await expect(uploadGalleryPhoto(file, { presign, attach })).resolves.toEqual({ id: 5 });
    expect(presign).toHaveBeenCalledExactlyOnceWith({ filename: file.name, content_type: file.type, size: file.size });
    expect(attach).toHaveBeenCalledExactlyOnceWith(presigned.object_key);
    expect(fetch).toHaveBeenCalledExactlyOnceWith(upload.url, { method: "PUT", body: file, headers: upload.headers });
  });
});
