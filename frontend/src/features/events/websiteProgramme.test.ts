import { describe, expect, it } from "vitest";
import { previewSessions, programmeWarnings } from "./websiteProgramme";
import type { WebsiteSession } from "./websiteTypes";

const s = (over: Partial<WebsiteSession>): WebsiteSession => ({
  slug: "a", title: "A", starts_at: "2026-05-01T10:00:00Z", ends_at: "2026-05-01T11:00:00Z", visibility: "published", track: "main", ...over,
} as WebsiteSession);
const next = { starts_at: "2026-05-01T11:00:00Z", ends_at: "2026-05-01T12:00:00Z" };

describe("previewSessions", () => {
  it("sorts by planned start, then slug", () => {
    const rows = previewSessions([s({ slug: "b" }), s({ slug: "a" }), s({ slug: "z", starts_at: "2026-05-01T09:00:00Z", ends_at: "2026-05-01T09:30:00Z" })]);
    expect(rows.map(r => r.slug)).toEqual(["z", "a", "b"]);
  });
  it("carries a published delay forward in the same track only", () => {
    const rows = previewSessions([s({ slug: "a", delay_minutes: 15 }), s({ slug: "b", ...next }), s({ slug: "c", track: "other", ...next })]);
    const by = Object.fromEntries(rows.map(r => [r.slug, r]));
    expect(by.a.effective_starts_at).toBe("2026-05-01T10:15:00.000Z");
    expect(by.b.effective_starts_at).toBe("2026-05-01T11:15:00.000Z");
    expect(by.b.delay_minutes).toBe(0);
    expect(by.c.effective_starts_at).toBe("2026-05-01T11:00:00.000Z");
  });
  it("applies a draft session's delay to itself but never shifts later sessions", () => {
    const rows = previewSessions([s({ slug: "a", visibility: "draft", delay_minutes: 30 }), s({ slug: "b", ...next })]);
    expect(rows[0].effective_ends_at).toBe("2026-05-01T11:30:00.000Z");
    expect(rows[1].effective_starts_at).toBe("2026-05-01T11:00:00.000Z");
  });
  it("keeps the original time when a timestamp cannot be parsed", () => {
    const [row] = previewSessions([s({ starts_at: "not-a-date", delay_minutes: 5 })]);
    expect(row.effective_starts_at).toBe("not-a-date");
  });
  it("treats a missing track as its own bucket", () => {
    const rows = previewSessions([s({ slug: "a", track: undefined, delay_minutes: 10 }), s({ slug: "b", track: undefined, ...next })]);
    expect(rows[1].effective_starts_at).toBe("2026-05-01T11:10:00.000Z");
  });
});

describe("programmeWarnings", () => {
  const base = { starts_at: "2026-05-01T10:00:00Z", ends_at: "2026-05-01T11:00:00Z" };
  it("is silent for separate tracks with nothing shared", () => expect(programmeWarnings([
    s({ ...base, track: "x", room: "r1", speakers: ["ann"] }), s({ ...base, slug: "b", title: "B", track: "y", room: "r2", speakers: ["bob"] })])).toEqual([]));
  it("is silent for back-to-back sessions", () => expect(programmeWarnings([s({ ...base }), s({ slug: "b", ...next })])).toEqual([]));
  it("names every shared resource of an overlap", () => expect(programmeWarnings([
    s({ ...base, room: "r1", speakers: ["ann"] }), s({ ...base, slug: "b", title: "B", room: "r1", speakers: ["ann", "bob"] })]))
    .toEqual(["A overlaps B: shared track, room, speaker."]));
  it("falls back to the slug when a title is empty", () => expect(programmeWarnings([
    s({ ...base, title: "" }), s({ ...base, slug: "b", title: "" })])).toEqual(["a overlaps b: shared track."]));
  it("does not treat two missing rooms as a shared room", () => expect(programmeWarnings([
    s({ ...base, track: "x" }), s({ ...base, slug: "b", track: "y" })])).toEqual([]));
});
