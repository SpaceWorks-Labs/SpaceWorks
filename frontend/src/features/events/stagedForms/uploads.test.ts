import { afterEach, describe, expect, it, vi } from "vitest";
import { memberRequest } from "../../../lib/api";
import { uploadPrivateFile, type UploadAsset } from "./uploads";
vi.mock("../../../lib/api", () => ({ memberRequest: vi.fn() }));
const path = "/member/makerspaces/2/events/41/stage-forms/11/files/";
const asset: UploadAsset = { asset_id: 91, version: 1, generation: 2, sha256: "", state: "initiated",
  upload: { method: "POST", url: "https://storage.example.test/staging", fields: { key: "staging/opaque", policy: "signed" }, expires_at: "2099-12-01T10:00:00Z" } };
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });
describe("private stage and receipt upload transport", () => {
  it("binds the stage revision and question, sends credentials only to the API, and returns a scanner-ready reference", async () => {
    const storage = vi.fn().mockResolvedValue({ ok: true }); vi.stubGlobal("fetch", storage);
    vi.mocked(memberRequest).mockResolvedValueOnce(asset).mockResolvedValueOnce({ ...asset, sha256: "a".repeat(64), state: "ready" });
    const result = await uploadPrivateFile(path, new File(["evidence"], "private.pdf", { type: "application/pdf" }), {
      response_id: 111, expected_response_version: 2, form_revision_id: 72, question_id: "supporting-file",
    }, new AbortController().signal);
    expect(result).toEqual({ asset_id: 91, generation: 2, sha256: "a".repeat(64) });
    const create = vi.mocked(memberRequest).mock.calls[0][1]!;
    expect(JSON.parse(create.body as string)).toMatchObject({ expected_version: 0, response_id: 111, expected_response_version: 2,
      form_revision_id: 72, question_id: "supporting-file", original_filename: "private.pdf", declared_mime: "application/pdf", expected_bytes: 8 });
    expect(create.cache).toBe("no-store");
    const posted = storage.mock.calls[0][1];
    expect(posted.credentials).toBe("omit"); expect(posted.headers).toBeUndefined();
    expect((posted.body as FormData).get("key")).toBe("staging/opaque");
    expect(JSON.parse(vi.mocked(memberRequest).mock.calls[1][1]!.body as string)).toMatchObject({ expected_version: 1, generation: 2 });
  });
  it("never returns a reference for failed scanning or an invalid trusted hash", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    for (const terminal of [{ state: "failed", sha256: "" }, { state: "ready", sha256: "bad" }]) {
      vi.mocked(memberRequest).mockResolvedValueOnce(asset).mockResolvedValueOnce({ ...asset, ...terminal });
      await expect(uploadPrivateFile(path, new File(["x"], "x.pdf"), { claim_uuid: "claim" }, new AbortController().signal)).rejects.toThrow();
    }
  });
  it("polls scanner status before enabling attachment and aborts unfinished work", async () => {
    vi.useFakeTimers(); vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    vi.mocked(memberRequest).mockResolvedValueOnce(asset).mockResolvedValueOnce({ ...asset, state: "validating" })
      .mockResolvedValueOnce({ ...asset, state: "ready", sha256: "b".repeat(64) });
    const promise = uploadPrivateFile(path, new File(["x"], "x.pdf"), { claim_uuid: "claim" }, new AbortController().signal);
    await vi.advanceTimersByTimeAsync(1000);
    await expect(promise).resolves.toMatchObject({ generation: 2, sha256: "b".repeat(64) });
    vi.mocked(memberRequest).mockResolvedValueOnce(asset).mockResolvedValueOnce({ ...asset, state: "validating" });
    const controller = new AbortController();
    const pending = uploadPrivateFile(path, new File(["x"], "x.pdf"), { claim_uuid: "claim" }, controller.signal);
    const refused = expect(pending).rejects.toThrow(/cancelled/);
    await vi.advanceTimersByTimeAsync(0); controller.abort(); await refused;
  });
});
