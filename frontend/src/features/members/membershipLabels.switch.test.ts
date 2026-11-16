import { describe, expect, it } from "vitest";
import { admissionStateLabel, membershipRoleLabel } from "./membershipLabels";

describe("admissionStateLabel", () => {
  it.each([
    ["requested", "Requested"],
    ["invited", "Invited"],
    ["awaiting_vouches", "Awaiting vouches"],
    ["awaiting_payment", "Awaiting payment"],
    ["changes_requested", "Changes requested"],
    ["expired", "Expired"],
    ["canceled", "Cancelled"],
    ["active", "Active"],
    ["revoked", "Revoked"],
  ])("%s reads %s", (code, text) => expect(admissionStateLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(admissionStateLabel("zz_unknown_code")).toBe("zz unknown code"));
});

describe("membershipRoleLabel", () => {
  it.each([
    ["member", "Member"],
    ["space_manager", "Space Manager"],
    ["inventory_manager", "Inventory Manager"],
    ["machine_manager", "Machine Manager"],
    ["event_manager", "Event Manager"],
    ["booking_manager", "Booking Manager"],
    ["shop_manager", "Shop Manager"],
    ["fundraising", "Fundraising"],
    ["print_manager", "Print Manager"],
    ["handover", "Handover"],
    ["technician", "Technician"],
  ])("%s reads %s", (code, text) => expect(membershipRoleLabel(code)).toBe(text));
  it("spells an unknown code with spaces instead of showing it raw", () => expect(membershipRoleLabel("zz_unknown_code")).toBe("zz unknown code"));
});

