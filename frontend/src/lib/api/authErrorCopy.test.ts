import { describe, expect, it } from "vitest";

import { authErrorMessage, captchaChallenge } from "./authErrorCopy";
import { apiError } from "./errors";

const coded = (code: string, status = 400, headers?: Headers) => apiError(status, { detail: `raw ${code}`, code }, headers);
const CODES = ["captcha_required", "captcha_failed", "password_breached", "login_code_required", "login_code_invalid",
  "native_app_update_required", "passkey_failed", "rp_id_unavailable", "last_factor", "security_alert_used",
  "staff_network_refused", "staff_session_expired", "mfa_enrollment_required", "ip_blocked"];

describe("authErrorMessage", () => {
  it("never shows a raw code or the server text for a known code", () => {
    for (const code of CODES) {
      const message = authErrorMessage(coded(code));
      expect(message).not.toContain(code);
      expect(message).not.toContain("raw ");
    }
  });

  it("names the Retry-After wait for an IP block", () => {
    expect(authErrorMessage(coded("ip_blocked", 429, new Headers({ "Retry-After": "45" })))).toBe(
      "Too many failed sign-ins from your network. Try again in about a minute.");
    expect(authErrorMessage(coded("ip_blocked", 429, new Headers({ "Retry-After": "900" })))).toContain("in about 15 minutes");
    expect(authErrorMessage(coded("ip_blocked", 429))).toContain("Try again later");
  });

  it("never calls a breached password hacked", () => {
    const message = authErrorMessage(coded("password_breached"));
    expect(message).toMatch(/known data breach/);
    expect(message).toMatch(/Choose a different one/);
    expect(message.toLowerCase()).not.toContain("hack");
  });

  it("covers the CAPTCHA, code and app-update refusals", () => {
    expect(authErrorMessage(coded("captcha_failed"))).toBe("That check didn't go through. Try it again.");
    expect(authErrorMessage(coded("login_code_invalid"))).toMatch(/send a new code/);
    expect(authErrorMessage(coded("native_app_update_required"))).toMatch(/Update the Space Works app/);
  });

  it("falls back to the server text, then to the fallback", () => {
    expect(authErrorMessage(apiError(400, { detail: "Plain words." }))).toBe("Plain words.");
    expect(authErrorMessage(apiError(500, {}), "Try later.")).toBe("Try later.");
    expect(authErrorMessage("nope", "Try later.")).toBe("Try later.");
  });
});

describe("captchaChallenge", () => {
  it("reads the site key and action from a CAPTCHA refusal only", () => {
    expect(captchaChallenge(apiError(400, { code: "captcha_required", turnstile_site_key: "k", turnstile_action: "code" })))
      .toEqual({ siteKey: "k", action: "code" });
    expect(captchaChallenge(apiError(400, { code: "captcha_failed" }))).toEqual({ siteKey: "", action: "login" });
    expect(captchaChallenge(coded("ip_blocked", 429))).toBeNull();
  });
});
