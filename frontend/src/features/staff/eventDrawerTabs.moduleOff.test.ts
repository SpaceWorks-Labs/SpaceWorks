// Decision 21 (module/capability-off) and decision 14/15 surfaces in the staff event drawer:
// every yuyu-gap surface disappears with its own switch, even for a full manager, and the
// full staff-invitation "Team" management is manager-only (a co-organizer with manage_team
// reaches Team for helper invitations alone; EventDrawerMore renders EventHelperInvites there).
import { describe, expect, it } from "vitest";

import { eventCredentialTools, eventDrawerSurfaces } from "./eventDrawerTabs";
import { eventAccess } from "./eventStaffPermissions";
import type { StaffEvent } from "./eventsApi";

const ON_FEATURES = ["events.volunteering", "events.mentoring", "events.hackathons", "events.crew",
  "events.checkin_lists", "events.id_cards", "events.ticket_designs", "events.attendance_confirmation"];
const ON_EVENT = { status: "published", broadcasts_enabled: true, report_features: ["analytics"],
  ticketing_features: ["events.invites", "events.ticket_types", "events.promo_codes", "events.website", "events.certificate_designer"] };
const manager = eventAccess({ can_manage_staff: true, staff_permissions: [] });

function sections(event: Record<string, unknown> = ON_EVENT, features = ON_FEATURES, modules = ["event_reimbursements"],
  access = manager) {
  return eventDrawerSurfaces(event as unknown as StaffEvent, access, features, modules).sections;
}
const without = (list: string[], key: string) => list.filter((entry) => entry !== key);

describe("drawer surfaces follow their module and capability switches", () => {
  it("shows every surface to a full manager when everything is on", () => {
    expect(Object.entries(sections()).filter(([, shown]) => !shown).map(([key]) => key)).toEqual([]);
  });

  it.each([
    ["volunteers", "events.volunteering"], ["mentor-desk", "events.mentoring"], ["judging", "events.hackathons"],
    ["programme-teams", "events.hackathons"], ["crew", "events.crew"], ["checkin-lists", "events.checkin_lists"],
  ] as const)("hides %s when %s is off", (section, feature) => {
    expect(sections(ON_EVENT, without(ON_FEATURES, feature))[section]).toBe(false);
  });

  it("hides analytics without the event's analytics report feature", () => {
    expect(sections({ ...ON_EVENT, report_features: [] }).analytics).toBe(false);
  });

  it("hides the website (and its publishing questions) when events.website is off", () => {
    expect(sections({ ...ON_EVENT, ticketing_features: without(ON_EVENT.ticketing_features, "events.website") }).website).toBe(false);
  });

  it("hides broadcasts when the event's broadcast capability and attendance confirmation are both off", () => {
    const off = { ...ON_EVENT, broadcasts_enabled: false };
    expect(sections(off).broadcasts).toBe(true); // attendance confirmation still sends through broadcasts
    expect(sections(off, without(ON_FEATURES, "events.attendance_confirmation")).broadcasts).toBe(false);
  });

  it("hides the certificate designer without its switch, and the whole credentials section with every credential switch off", () => {
    const noDesigner = { ...ON_EVENT, ticketing_features: without(ON_EVENT.ticketing_features, "events.certificate_designer") };
    expect(eventCredentialTools(noDesigner as unknown as StaffEvent, manager, ON_FEATURES).certificates).toBe(false);
    const features = without(without(ON_FEATURES, "events.id_cards"), "events.ticket_designs");
    expect(sections(noDesigner, features).certificates).toBe(false);
  });

  it("hides travel support when the event_reimbursements module is off", () => {
    expect(sections(ON_EVENT, ON_FEATURES, []).reimbursements).toBe(false);
  });
});

describe("delegated staff see only what their grant holds", () => {
  it("a co-organizer with manage_team reaches Team (for helper invitations only) but is never a full manager", () => {
    const co = eventAccess({ can_manage_staff: false, staff_permissions: ["manage_team", "manage_volunteers", "check_in", "judge", "mentor_queue"] });
    const shown = sections(ON_EVENT, ON_FEATURES, [], co);
    expect(co.manager).toBe(false);
    expect(shown.team).toBe(true);
    expect(shown.volunteers && shown["mentor-desk"] && shown.judging && shown["programme-teams"]).toBe(true);
  });

  it("a helper grant without manage_team never sees Team", () => {
    const helper = eventAccess({ can_manage_staff: false, staff_permissions: ["check_in", "judge", "mentor_queue"] });
    expect(sections(ON_EVENT, ON_FEATURES, [], helper).team).toBe(false);
  });

  it("a volunteer-only grant still loses the Volunteers section when volunteering is off", () => {
    const volunteers = eventAccess({ can_manage_staff: false, staff_permissions: ["manage_volunteers"] });
    expect(sections(ON_EVENT, ON_FEATURES, [], volunteers).volunteers).toBe(true);
    expect(sections(ON_EVENT, without(ON_FEATURES, "events.volunteering"), [], volunteers).volunteers).toBe(false);
  });
});
