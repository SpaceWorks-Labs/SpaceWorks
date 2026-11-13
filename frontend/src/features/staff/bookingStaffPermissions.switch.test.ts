import { describe, expect, it } from "vitest";
import { bookingPermissionLabel } from "./bookingStaffPermissions";

describe("bookingPermissionLabel", () => {
  it.each([
    ["edit_details", "Edit details"],
    ["manage_reservations", "Manage reservations"],
    ["check_in", "Check in"],
    ["publish_page", "Publish page"],
  ])("%s reads %s", (code, text) => expect(bookingPermissionLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(bookingPermissionLabel("zz_unknown_code")).toBe("zz unknown code"));
});

