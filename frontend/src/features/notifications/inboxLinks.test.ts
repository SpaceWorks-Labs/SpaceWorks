import { describe, expect, it } from "vitest";
import { inboxRoute } from "./inboxLinks";

describe("inbox navigation across frontend route modes", () => {
  it.each(["admin/payments", "admin/events?event=42", "admin/bookings?view=requests&status=pending",
    "admin/stocktake", "admin/devices", "admin/reports", "admin/members", "admin/api-access",
    "admin/settings", "admin/email-log", "member", "member/bookings", "member/events/8/ticket", "items/73"])(
    "opens saved %s notices on central, custom-domain and token-configured frontends", path => {
      expect(inboxRoute(`/m/local/${path}`, "single", "local")).toBe(`/${path}`);
      expect(inboxRoute(`/${path}`, "single", "local")).toBe(`/${path}`);
      expect(inboxRoute(`/${path}`, "central", "local")).toBe(`/m/local/${path}`);
      expect(inboxRoute(`/m/local/${path}`, "central", "local")).toBe(`/m/local/${path}`);
    },
  );

  it("never rebinds another tenant and preserves archived-payment recovery", () => {
    expect(inboxRoute("/m/other/member", "single", "local")).toBe("");
    expect(inboxRoute("/m/other/member", "central", "local")).toBe("/m/other/member");
    expect(inboxRoute("/member/archived", "central", "local")).toBe("/member/archived");
  });

  it.each(["//evil.test", "/\\evil.test", "/\t/evil.test", "https://evil.test", "/\x7fpath"])(
    "refuses unsafe links %j before normalization", value => {
      expect(inboxRoute(value, "single", "local")).toBe("");
    },
  );
});
