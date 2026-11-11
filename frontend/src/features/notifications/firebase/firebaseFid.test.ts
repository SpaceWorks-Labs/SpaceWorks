import { expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ register: vi.fn(), unsubscribe: vi.fn() }));
vi.mock("firebase/app", () => ({ getApps: () => [], initializeApp: () => ({}) }));
vi.mock("firebase/messaging", () => ({ isSupported: async () => true, getMessaging: () => ({}), onRegistered: () => mocks.unsubscribe, register: mocks.register }));
import { currentFirebaseFid } from "./firebaseFid";
it("times out a pending SDK registration and releases its FID listener even if registration rejects later", async () => {
  vi.useFakeTimers(); mocks.unsubscribe.mockReset(); let rejectRegistration!: (reason: Error) => void;
  mocks.register.mockReturnValue(new Promise<void>((_resolve, reject) => { rejectRegistration = reject; }));
  try {
    const pending = currentFirebaseFid({ apiKey: "x", authDomain: "x", projectId: "x", appId: "x", messagingSenderId: "x" }, "vapid", {} as ServiceWorkerRegistration);
    const observed = expect(pending).rejects.toThrow("Registration timed out");
    await vi.waitFor(() => expect(mocks.register).toHaveBeenCalled()); await vi.advanceTimersByTimeAsync(15000); await observed;
    expect(mocks.unsubscribe).toHaveBeenCalledOnce(); expect(vi.getTimerCount()).toBe(0);
    rejectRegistration(new Error("late failure")); await Promise.resolve(); await Promise.resolve();
  } finally { vi.useRealTimers(); }
});
