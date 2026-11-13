import { describe, expect, it } from "vitest";
import { emptyMakerspaceForm, makerspacePayload } from "./forms";

describe("makerspacePayload ownership", () => {
  const form = { ...emptyMakerspaceForm, name: " Community Lab " };

  it("emits only organization_id for an existing selection despite a stale new name", () => {
    const payload = makerspacePayload({ ...form, organization: { id: 42, name: "Network" }, organization_name: "Stale" });
    expect(payload).toMatchObject({ organization_id: 42 });
    expect(payload).not.toHaveProperty("organization_name");
  });

  it.each([undefined, " Custom Network "])("emits only the trimmed new name (%s)", organization_name => {
    const payload = makerspacePayload({ ...form, organization: "new", organization_name });
    expect(payload).toMatchObject({ organization_name: organization_name ? "Custom Network" : "Community Lab" });
    expect(payload).not.toHaveProperty("organization_id");
  });
});
