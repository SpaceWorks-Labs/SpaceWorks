import { File as NodeFile } from "node:buffer";
import { webcrypto } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest } from "../../../lib/api";
import { uploadProjectFile, clearUploadSessions } from "./upload";

vi.mock("../../../lib/api", () => ({ memberRequest: vi.fn() }));
const scope = { accountId: 18, makerspaceId: 9, eventId: 42, teamId: 7 };
const response = { asset_id: 301, event_id: 42, version: 1, generation: 1, state: "uploading",
  upload: { method: "MULTIPART", part_size: 16 * 1024 ** 2, part_count: 1 } };

beforeEach(() => { vi.clearAllMocks(); clearUploadSessions(); localStorage.clear(); vi.stubGlobal("crypto", webcrypto); });

describe("staging-only resumable uploads", () => {
  it("uses separate creation/completion receipts and no auth on storage requests", async () => {
    const file = new NodeFile(["inert maker bytes"], "project.stl", { lastModified: 1 }) as unknown as File;
    vi.mocked(memberRequest).mockResolvedValueOnce(response).mockResolvedValueOnce({ parts: [
      { part_number: 1, size_bytes: file.size, url: "https://storage.example/staging-only" },
    ] }).mockResolvedValueOnce({ ...response, state: "validating" });
    const network = vi.fn().mockResolvedValue({ ok: true }); vi.stubGlobal("fetch", network);
    await uploadProjectFile({ file, scope, spec: { group: "fab-3dprint", subtype: "binary" },
      allowedOrigins: ["https://storage.example"], signal: new AbortController().signal, progress: vi.fn() });
    const calls = vi.mocked(memberRequest).mock.calls;
    const create = calls[0][1]?.headers as Record<string, string>;
    const complete = JSON.parse(calls[2][1]?.body as string);
    expect(complete.operation_id).not.toBe(create["Idempotency-Key"]);
    expect(complete).not.toHaveProperty("ETag");
    expect(network.mock.calls[0][1]).toMatchObject({ method: "PUT", credentials: "omit", cache: "no-store", redirect: "error" });
    expect(network.mock.calls[0][1]).not.toHaveProperty("headers");
    expect(localStorage.length).toBe(0);
  });
  it("rejects an unconfigured storage origin without browser-storage persistence", async () => {
    const file = new NodeFile(["inert bytes"], "project.stl", { lastModified: 1 }) as unknown as File;
    vi.mocked(memberRequest).mockResolvedValueOnce(response).mockResolvedValueOnce({ parts: [
      { part_number: 1, size_bytes: file.size, url: "https://evil.example/write" },
    ] });
    const network = vi.fn(); vi.stubGlobal("fetch", network);
    await expect(uploadProjectFile({ file, scope, spec: { group: "fab-3dprint", subtype: "binary" },
      allowedOrigins: ["https://storage.example"], signal: new AbortController().signal, progress: vi.fn() })).rejects.toThrow("destination");
    expect(network).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
  });
});
