import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EMPTY_SCOPE, type RecipientRulesResponse } from "../../../notificationDestinationTypes";
import { RecipientTarget } from "../../../NotificationRecipientEvent";
import { bodyWithAdded, offeredEvents } from "./typeNotificationRules";

const data = (events: string[]): RecipientRulesResponse => ({
  delegated: false, features: [{ key: "printing", events }], roles: [{ id: 3, name: "Machine Manager", slug: "mm" }],
  members: [], rules: [{ id: 9, feature: "printing", event: "completed", kind: "role", role_id: 3, user_id: null,
    scope: { ...EMPTY_SCOPE, machine_type_ids: [77] } }], managed_policy_markers: [], scope_options: undefined,
} as unknown as RecipientRulesResponse);

describe("machine-service job notices per type (decision 343)", () => {
  it("offers the printing family's staff events the endpoint lists", () => {
    const offered = offeredEvents(data(["submitted", "completed", "failed"])).filter(item => item.feature === "printing");
    expect(offered.map(item => item.event)).toEqual(["submitted", "completed", "failed"]);
    expect(offered.find(item => item.event === "completed")?.suggestedBy).toBe("job_finished");
  });

  it("keeps the event's other rules when adding one narrowed to this type", () => {
    const body = bodyWithAdded(data(["completed"]), "printing", "completed", 12, { kind: "role", role_id: 3, user_id: null });
    expect(body.rules).toHaveLength(2);
    expect(body.rules[1].scope.machine_type_ids).toEqual([12]);
  });

  it("offers roles and people only for a staff-only family", () => {
    const rule = { kind: "role" as const, role_id: null, user_id: null, scope: EMPTY_SCOPE };
    render(<RecipientTarget data={data(["completed"])} staffOnly index={0} rule={rule} rules={[rule]} update={vi.fn()} />);
    const options = Array.from(screen.getByLabelText("Recipient 1 type").querySelectorAll("option")).map(o => o.getAttribute("value"));
    expect(options).toEqual(["role", "user"]);
  });
});
