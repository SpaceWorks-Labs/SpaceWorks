import { afterEach, expect, it } from "vitest";
import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { clearJobs, getJobSession, jobStore, trackJob, updateJob } from "./jobStore";
import { clearToasts, toast, toastStore } from "./toastStore";

afterEach(() => { for (const context of ["person", "platform"] as const) { clearJobs(context); clearToasts(context); } setRouteSessionContext("person"); });
it("isolates private jobs and toasts by context, including late callbacks and cleanup", () => {
  setRouteSessionContext("person"); toast("Member message");
  trackJob({ key: "export", label: "Member export", makerspaceId: 1, endpoint: "/member/export", status: "running" });
  const memberSession = getJobSession();
  setRouteSessionContext("platform");
  expect(jobStore.snapshot()).toEqual([]); expect(toastStore.snapshot()).toEqual([]);
  toast("Staff message"); trackJob({ key: "export", label: "Staff export", makerspaceId: 1, endpoint: "/staff/export", status: "running" });
  updateJob("export", "completed", memberSession);
  expect(jobStore.snapshot()[0].status).toBe("running");
  clearJobs("platform"); clearToasts("platform");
  setRouteSessionContext("person");
  expect(jobStore.snapshot()[0].label).toBe("Member export"); expect(toastStore.snapshot()[0].message).toBe("Member message");
});
