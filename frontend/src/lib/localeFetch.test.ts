import { beforeEach, describe, expect, it, vi } from "vitest";

const { setUserLocale, setMakerspaceLocale } = vi.hoisted(() => ({ setUserLocale: vi.fn(), setMakerspaceLocale: vi.fn() }));
vi.mock("./runtimeConfig", () => ({ configuredApiUrl: () => "https://api.example.org/api" }));
vi.mock("./i18n", () => ({
  setUserLocale, setMakerspaceLocale,
  withLocaleHeaders: (base?: HeadersInit) => { const h = new Headers(base); h.set("Accept-Language", "ml"); return h; },
}));

import { installLocaleFetch, isSpaceWorksApi } from "./localeFetch";

const json = (body: unknown, init: ResponseInit = {}) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" }, ...init });
const flush = () => new Promise(resolve => setTimeout(resolve, 0));
let original: ReturnType<typeof vi.fn>;
let target: { fetch: typeof fetch };

beforeEach(() => {
  setUserLocale.mockReset(); setMakerspaceLocale.mockReset();
  original = vi.fn().mockResolvedValue(json({}));
  target = { fetch: original as unknown as typeof fetch };
  installLocaleFetch(target);
});

describe("isSpaceWorksApi", () => {
  it("accepts the configured API, its children and this origin's /api/ only", () => {
    expect(isSpaceWorksApi(new URL("https://api.example.org/api"))).toBe(true);
    expect(isSpaceWorksApi(new URL("https://api.example.org/api/v1/x"))).toBe(true);
    expect(isSpaceWorksApi(new URL("https://api.example.org/apix"))).toBe(false);
    expect(isSpaceWorksApi(new URL("/api/v1/x", window.location.href))).toBe(true);
    expect(isSpaceWorksApi(new URL("/other", window.location.href))).toBe(false);
    expect(isSpaceWorksApi(new URL("https://s3.example.org/upload"))).toBe(false);
  });
});

describe("installLocaleFetch", () => {
  it("is idempotent: a second install does not wrap the wrapper", () => {
    const wrapped = target.fetch;
    installLocaleFetch(target);
    expect(target.fetch).toBe(wrapped);
  });
  it("does nothing when there is no fetch", () => {
    const bare = {} as { fetch: typeof fetch };
    installLocaleFetch(bare);
    expect(bare.fetch).toBeUndefined();
  });
  it("adds locale headers to API requests, keeping the caller's headers", async () => {
    await target.fetch("https://api.example.org/api/v1/things", { headers: { "X-Mine": "1" } });
    const [, init] = original.mock.calls[0];
    expect((init.headers as Headers).get("Accept-Language")).toBe("ml");
    expect((init.headers as Headers).get("X-Mine")).toBe("1");
  });
  it("takes headers from a Request object when init has none", async () => {
    await target.fetch(new Request("https://api.example.org/api/v1/things", { headers: { "X-Req": "2" } }));
    expect((original.mock.calls[0][1].headers as Headers).get("X-Req")).toBe("2");
  });
  it("accepts a URL object and a relative same-origin path", async () => {
    await target.fetch(new URL("https://api.example.org/api/v1/a"));
    await target.fetch("/api/v1/b");
    expect(original.mock.calls.every(([, init]) => (init.headers as Headers).get("Accept-Language") === "ml")).toBe(true);
  });
  it("passes storage and other URLs through untouched", async () => {
    const init = { method: "PUT" };
    await target.fetch("https://s3.example.org/upload", init);
    expect(original).toHaveBeenCalledWith("https://s3.example.org/upload", init);
  });
  it("passes through an input whose URL cannot be built", async () => {
    await target.fetch("http://[bad");
    expect(original).toHaveBeenCalledWith("http://[bad", undefined);
  });
  it("reads preferred_locale from a login or me payload, nested or flat", async () => {
    original.mockResolvedValueOnce(json({ user: { preferred_locale: "ml" } }));
    await target.fetch("https://api.example.org/api/v1/auth/login"); await flush();
    expect(setUserLocale).toHaveBeenLastCalledWith("ml");
    original.mockResolvedValueOnce(json({ preferred_locale: "hi" }));
    await target.fetch("https://api.example.org/api/v1/auth/me/"); await flush();
    expect(setUserLocale).toHaveBeenLastCalledWith("hi");
  });
  it("reads the makerspace default from the bootstrap payload", async () => {
    original.mockResolvedValueOnce(json({ default_locale: "ta" }));
    await target.fetch("https://api.example.org/api/v1/bootstrap"); await flush();
    expect(setMakerspaceLocale).toHaveBeenCalledWith("ta");
    expect(setUserLocale).not.toHaveBeenCalled();
  });
  it("clears the user locale on logout and logout-all", async () => {
    await target.fetch("https://api.example.org/api/v1/auth/logout");
    await target.fetch("https://api.example.org/api/v1/auth/logout-all/");
    expect(setUserLocale).toHaveBeenCalledTimes(2);
    expect(setUserLocale).toHaveBeenCalledWith(null);
  });
  it("ignores failed responses, non-JSON bodies, other endpoints and payloads without a locale", async () => {
    original.mockResolvedValueOnce(json({ preferred_locale: "ml" }, { status: 401 }));
    await target.fetch("https://api.example.org/api/v1/auth/me");
    original.mockResolvedValueOnce(new Response("{}", { status: 200, headers: { "Content-Type": "text/plain" } }));
    await target.fetch("https://api.example.org/api/v1/auth/me");
    original.mockResolvedValueOnce(json({ preferred_locale: "ml" }));
    await target.fetch("https://api.example.org/api/v1/other");
    original.mockResolvedValueOnce(json({ unrelated: true }));
    await target.fetch("https://api.example.org/api/v1/bootstrap");
    original.mockResolvedValueOnce(json({ user: {} }));
    await target.fetch("https://api.example.org/api/v1/auth/me");
    await flush();
    expect(setUserLocale).not.toHaveBeenCalled();
    expect(setMakerspaceLocale).not.toHaveBeenCalled();
  });
  it("survives a JSON body that cannot be parsed", async () => {
    original.mockResolvedValueOnce(new Response("{oops", { status: 200, headers: { "Content-Type": "application/json" } }));
    await expect(target.fetch("https://api.example.org/api/v1/auth/me")).resolves.toBeInstanceOf(Response);
    await flush();
    expect(setUserLocale).not.toHaveBeenCalled();
  });
});
