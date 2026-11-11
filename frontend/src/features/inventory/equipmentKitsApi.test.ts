import { expect, it, vi } from "vitest";
import { createKitVersion, publishKit, staffContextKits, staffKits } from "./equipmentKitsApi";
const mock = vi.hoisted(() => ({ staff: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: mock.staff, memberRequest: vi.fn() }));

it("uses source-scoped kit discovery and revision CAS for publication and versions", async () => {
  mock.staff.mockReset(); mock.staff.mockResolvedValue({});
  await staffContextKits(4, "booking", 7, 2);
  await publishKit(4, 8, 3, true);
  await createKitVersion(4, 8, 4, "Workshop", [{ product_id: 10, quantity_per_person: 2, kind: "returnable" }]);
  expect(mock.staff.mock.calls[0][0]).toBe("/admin/makerspace/4/spaces/7/equipment-kits?page=2");
  expect(JSON.parse(mock.staff.mock.calls[1][1].body)).toEqual({ expected_revision: 3, published_for_contexts: true });
  expect(JSON.parse(mock.staff.mock.calls[2][1].body)).toMatchObject({ expected_revision: 4, name: "Workshop" });
});

it("requests archived templates only for the editor's management view", async () => {
  mock.staff.mockReset(); mock.staff.mockResolvedValue({});
  await staffKits(4, 1);
  await staffKits(4, 2, true);
  expect(mock.staff.mock.calls[0][0]).toBe("/admin/makerspace/4/equipment-kits?page=1");
  expect(mock.staff.mock.calls[1][0]).toBe("/admin/makerspace/4/equipment-kits?page=2&include_archived=true");
});
