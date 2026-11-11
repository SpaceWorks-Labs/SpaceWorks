import { describe, expect, it } from "vitest";
import { requestTabHref, resolveRequestTab, visibleRequestTabs, type RequestTab } from "./requestTabs";
const all: RequestTab[] = ["pending", "accepted", "active", "history"];
describe("request URL compatibility", () => {
  it.each([
    [{ queue: "pending" }, "pending"], [{ queue: "accepted" }, "accepted"], [{ queue: "active" }, "active"],
    [{ queue: "history" }, "history"], [{ history: "true" }, "history"], [{ activePage: "3" }, "active"],
    [{ queue: "bogus" }, "pending"], [{ id: "42", history: "true", activePage: "3" }, "resolve-id"],
  ])("resolves %j as %s", (values, expected) => expect(resolveRequestTab(values, all)).toBe(expected));
  it("mirrors endpoint authority and keeps the handout narrowing", () => {
    expect(visibleRequestTabs(false, ["accept_request"])).toEqual(["pending"]);
    expect(visibleRequestTabs(false, ["issue_request"])).toEqual(["accepted", "active", "history"]);
    const handout = visibleRequestTabs(true, ["issue_request", "accept_request"]);
    expect(handout).toEqual(["accepted", "active", "history"]);
    expect(resolveRequestTab({ queue: "active" }, handout)).toBe("active");
    expect(resolveRequestTab({ queue: "pending" }, handout)).toBe("accepted");
    expect(visibleRequestTabs(false)).toEqual([]);
  });
  it("opens the combined view only for ?queue=all and only with more than one visible queue", () => {
    expect(resolveRequestTab({ queue: "all" }, all)).toBe("all");
    expect(resolveRequestTab({ queue: "all" }, ["pending"])).toBe("pending");
    expect(resolveRequestTab({}, all)).toBe("pending");
    expect(requestTabHref("/admin/requests", "?queue=pending&search=ada", "all")).toBe("/admin/requests?queue=all&search=ada");
  });
  it("canonicalises only a tab click, keeping filters and resetting every page", () => {
    const url = requestTabHref("/admin/requests", "?pendingPage=2&activePage=3&history=true&search=ada&ordering=created_at", "accepted");
    const params = new URL(url, "https://space.test").searchParams;
    expect(Object.fromEntries(params)).toEqual({ search: "ada", ordering: "created_at", queue: "accepted" });
  });
});
