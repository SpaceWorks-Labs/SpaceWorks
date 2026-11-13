import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StepNotifications } from "./StepNotifications";
import { context, renderWithQuery } from "./test/stepTestKit";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async importOriginal => ({ ...(await importOriginal<object>()), staffRequest }));

const none = { machine_type_ids: [], machine_ids: [], category_ids: [] };
const rule = (id: number, feature: string, event: string, role_id: number, types: number[]) => ({ id, feature, event, kind: "role", role_id, user_id: null, scope: { ...none, machine_type_ids: types } });
const data = {
  delegated: false, features: [{ key: "stock", events: ["low_stock"] }, { key: "maintenance", events: ["due_soon", "overdue"] }],
  roles: [{ id: 2, name: "Machine Manager", slug: "mm" }, { id: 3, name: "Space Manager", slug: "sm" }], members: [{ id: 5, username: "ada", email: "a@x.test" }],
  rules: [rule(1, "stock", "low_stock", 3, []), rule(2, "stock", "low_stock", 2, [9]), rule(3, "stock", "low_stock", 3, [4]), rule(4, "maintenance", "overdue", 3, [])],
  managed_policy_markers: [], scope_options: { machine_types: [], machines: [], categories: [] },
};
const puts = () => staffRequest.mock.calls.filter(([, init]) => init?.method === "PUT");

describe("StepNotifications", () => {
  beforeEach(() => { staffRequest.mockReset(); staffRequest.mockImplementation(async () => data); });

  it("lists only the rules narrowed to this type and suggests events from the template", async () => {
    renderWithQuery(<StepNotifications ctx={context()} />);
    expect(await screen.findByText("Machine Manager")).toBeVisible();
    expect(screen.queryByText("Space Manager")).toBeNull();
    expect(screen.getByText("Suggested by the template")).toBeVisible();
  });

  it("adds a type-narrowed rule and sends every other rule for the event back unchanged", async () => {
    renderWithQuery(<StepNotifications ctx={context()} />);
    await screen.findByText("Machine Manager");
    fireEvent.click(screen.getAllByRole("button", { name: "Add a recipient" })[0]);
    fireEvent.change(screen.getByLabelText("Recipient 1 role"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Add for this type" }));
    await waitFor(() => expect(puts()).toHaveLength(1));
    const [path, init] = puts()[0];
    expect(path).toBe("/admin/makerspace/1/notification-recipient-rules");
    expect(JSON.parse(init.body)).toEqual({ feature: "stock", event: "low_stock", rules: [
      { kind: "role", role_id: 3, user_id: null, scope: none },
      { kind: "role", role_id: 2, user_id: null, scope: { ...none, machine_type_ids: [9] } },
      { kind: "role", role_id: 3, user_id: null, scope: { ...none, machine_type_ids: [4] } },
      { kind: "role", role_id: 3, user_id: null, scope: { ...none, machine_type_ids: [9] } },
    ] });
  });

  it("removes only the chosen type-narrowed rule", async () => {
    renderWithQuery(<StepNotifications ctx={context()} />);
    await screen.findByText("Machine Manager");
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(puts()).toHaveLength(1));
    expect(JSON.parse(puts()[0][1].body).rules.map((item: { role_id: number }) => item.role_id)).toEqual([3, 3]);
  });
});
