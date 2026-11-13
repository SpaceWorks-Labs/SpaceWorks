import { describe, expect, it } from "vitest";
import { emailForm, emailPayload, emailValidation, optionalProviderFields, PROVIDER_FIELDS, type EmailForm, type EmailSettings } from "./emailSettings";

const form = (over: Partial<EmailForm> = {}): EmailForm => ({ ...emailForm(), ...over });
const saved = (over: Partial<EmailSettings> = {}): EmailSettings => ({ smtp_host: "", smtp_port: 587, smtp_username: "", smtp_password_set: false,
  smtp_use_tls: true, smtp_use_ssl: false, ...over });

describe("emailForm", () => {
  it("starts on the environment default with STARTTLS on port 587", () => expect(emailForm()).toEqual({ provider: "inherit", host: "", port: "587",
    username: "", password: "", tls: true, ssl: false, sender: "", credentials: {} }));
  it("treats a saved SMTP host with no explicit provider as smtp", () => expect(emailForm(saved({ smtp_host: "mail.x.org" })).provider).toBe("smtp"));
  it("keeps an explicit provider over a saved host", () => expect(emailForm(saved({ smtp_host: "mail.x.org", email_provider: "resend" })).provider).toBe("resend"));
  it("prefers from_email over smtp_from_email and never copies the saved password", () => {
    const out = emailForm(saved({ from_email: "a@x.org", smtp_from_email: "b@x.org", smtp_use_tls: false, smtp_use_ssl: true, smtp_port: 465, smtp_username: "u", smtp_password_set: true }));
    expect(out).toMatchObject({ sender: "a@x.org", tls: false, ssl: true, port: "465", username: "u", password: "" });
    expect(emailForm(saved({ smtp_from_email: "b@x.org" })).sender).toBe("b@x.org");
  });
});

describe("optionalProviderFields", () => {
  it("offers a webhook secret only where the provider has one", () => {
    expect(optionalProviderFields("resend")).toEqual(["account_key", "webhook_secret"]);
    expect(optionalProviderFields("mailgun")).toEqual(["account_key", "webhook_signing_key"]);
    expect(optionalProviderFields("postmark")).toEqual(["account_key"]);
  });
});

describe("emailValidation", () => {
  it("accepts the environment default with nothing filled in", () => expect(emailValidation(form())).toBeNull());
  it("requires a sender, and refuses one with a line break", () => {
    expect(emailValidation(form({ provider: "smtp", sender: "  " }))).toBe("Enter a verified sender email address.");
    expect(emailValidation(form({ provider: "smtp", sender: "a@x.org\nbcc:b@x.org", host: "h" }))).toBe("Enter a verified sender email address.");
  });
  it("requires an SMTP host", () => expect(emailValidation(form({ provider: "smtp", sender: "a@x.org", host: " " }))).toBe("Enter an SMTP host."));
  it.each(["", "abc", "0", "65536", "-1", "25.5"])("refuses SMTP port %j", (port) => expect(emailValidation(form({ provider: "smtp", sender: "a@x.org", host: "h", port })))
    .toBe("Enter an SMTP port from 1 to 65,535."));
  it.each(["1", "587", "65535"])("accepts SMTP port %s", (port) => expect(emailValidation(form({ provider: "smtp", sender: "a@x.org", host: "h", port }))).toBeNull());
  it("refuses STARTTLS and implicit SSL together", () => expect(emailValidation(form({ provider: "smtp", sender: "a@x.org", host: "h", tls: true, ssl: true })))
    .toBe("Choose STARTTLS or implicit SSL."));
  it("requires every provider field when the credentials are new", () => {
    expect(emailValidation(form({ provider: "mailgun", sender: "a@x.org", credentials: { api_key: "k", domain: "d" } })))
      .toBe("Enter all required provider fields to replace the saved configuration.");
    expect(emailValidation(form({ provider: "mailgun", sender: "a@x.org", credentials: { api_key: "k", domain: "d", region: "eu" } }))).toBeNull();
  });
  it("leaves a configured provider alone when nothing changed", () => expect(emailValidation(form({ provider: "resend", sender: "a@x.org" }),
    saved({ email_provider: "resend", email_provider_configured: true }))).toBeNull());
  it("requires credentials when the provider changed even if one was configured", () => expect(emailValidation(form({ provider: "resend", sender: "a@x.org" }),
    saved({ email_provider: "postmark", email_provider_configured: true }))).toBe("Enter all required provider fields to replace the saved configuration."));
  it("requires credentials when the saved provider was never configured", () => expect(emailValidation(form({ provider: "resend", sender: "a@x.org" }),
    saved({ email_provider: "resend", email_provider_configured: false }))).toBe("Enter all required provider fields to replace the saved configuration."));
  it("does not require the SES session token, and not the keys with workload identity", () => {
    const base = { provider: "ses" as const, sender: "a@x.org" };
    expect(emailValidation(form({ ...base, credentials: { region: "r", access_key_id: "a", secret_access_key: "s" } }))).toBeNull();
    expect(emailValidation(form({ ...base, credentials: { region: "r", workload_identity: true } }))).toBeNull();
    expect(emailValidation(form({ ...base, credentials: { region: "r" } }))).toBe("Enter all required provider fields to replace the saved configuration.");
  });
  it("declares the required fields per provider", () => expect(PROVIDER_FIELDS.postmark).toEqual(["server_token"]));
});

describe("emailPayload", () => {
  it("clears the platform provider and legacy host when set back to the environment", () => expect(emailPayload(form(), true)).toEqual({ email_provider: "", smtp_host: "" }));
  it("keeps the tenant provider key as inherit and sends nothing else", () => expect(emailPayload(form(), false)).toEqual({ email_provider: "inherit" }));
  it("sends trimmed SMTP settings under the platform sender key, with a password only when typed", () => {
    const f = form({ provider: "smtp", sender: " a@x.org ", host: " h ", port: "465", username: "u", tls: false, ssl: true });
    expect(emailPayload(f, true)).toEqual({ email_provider: "smtp", from_email: "a@x.org", smtp_host: "h", smtp_port: 465, smtp_username: "u", smtp_use_tls: false, smtp_use_ssl: true });
    expect(emailPayload({ ...f, password: "pw" }, false)).toMatchObject({ smtp_from_email: "a@x.org", smtp_password: "pw" });
    expect(emailPayload(f, false)).not.toHaveProperty("smtp_password");
  });
  it("sends provider credentials without blank values, and none when untouched", () => {
    expect(emailPayload(form({ provider: "mailgun", sender: "a@x.org", credentials: { api_key: "k", domain: "", region: "eu" } }), true))
      .toEqual({ email_provider: "mailgun", from_email: "a@x.org", email_provider_config: { api_key: "k", region: "eu" } });
    expect(emailPayload(form({ provider: "resend", sender: "a@x.org" }), true)).toEqual({ email_provider: "resend", from_email: "a@x.org" });
  });
});
