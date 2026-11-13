import { describe, expect, it } from "vitest";

import { lifecycleTabs } from "./MembershipLifecycleTabs";

describe("release-2 membership tabs follow their switches (#95)", () => {
  it("shows nothing while every switch or the module is off", () => {
    expect(lifecycleTabs([], true)).toEqual([]);
    expect(lifecycleTabs(["membership.import"], false)).toEqual([]);
  });

  it("shows exactly the tabs whose switch is on", () => {
    const keys = lifecycleTabs(["membership.import", "membership.renewal_desk", "membership.erasure"], true).map((tab) => tab.key);
    expect(keys).toEqual(["renewals", "import", "tools"]);
    expect(lifecycleTabs(["membership.register_tools", "membership.insights"], true).map((tab) => tab.key))
      .toEqual(["register", "insights"]);
  });
});
