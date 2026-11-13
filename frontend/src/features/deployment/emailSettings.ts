export const EMAIL_PROVIDERS = ["inherit", "smtp", "resend", "postmark", "ses", "brevo", "mailgun", "sendgrid"] as const;
export type EmailProvider = typeof EMAIL_PROVIDERS[number];
export type EmailSettings = {
  email_provider?: EmailProvider | "";
  email_provider_configured?: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password_set: boolean;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  smtp_from_email?: string;
  from_email?: string;
};
export type EmailForm = {
  provider: EmailProvider;
  host: string;
  port: string;
  username: string;
  password: string;
  tls: boolean;
  ssl: boolean;
  sender: string;
  credentials: Record<string, string | boolean>;
};
export const PROVIDER_FIELDS: Record<EmailProvider, string[]> = {
  inherit: [], smtp: [], resend: ["api_key"], postmark: ["server_token"], brevo: ["api_key"],
  sendgrid: ["api_key"], mailgun: ["api_key", "domain", "region"],
  ses: ["region", "access_key_id", "secret_access_key", "session_token"],
};
export function optionalProviderFields(provider: EmailProvider) {
  return ["account_key", ...(provider === "resend" ? ["webhook_secret"] : provider === "mailgun" ? ["webhook_signing_key"] : [])];
}
export function emailForm(settings?: EmailSettings): EmailForm {
  return {
    provider: settings?.email_provider || (settings?.smtp_host ? "smtp" : "inherit"),
    host: settings?.smtp_host ?? "", port: String(settings?.smtp_port ?? 587),
    username: settings?.smtp_username ?? "", password: "", tls: settings?.smtp_use_tls ?? true,
    ssl: settings?.smtp_use_ssl ?? false, sender: settings?.from_email ?? settings?.smtp_from_email ?? "", credentials: {},
  };
}
export function emailValidation(form: EmailForm, saved?: EmailSettings): string | null {
  if (form.provider === "inherit") return null;
  if (!form.sender.trim() || /[\r\n]/.test(form.sender)) return "Enter a verified sender email address.";
  if (form.provider === "smtp") {
    if (!form.host.trim()) return "Enter an SMTP host.";
    if (!/^\d+$/.test(form.port) || Number(form.port) < 1 || Number(form.port) > 65535) return "Enter an SMTP port from 1 to 65,535.";
    if (form.tls && form.ssl) return "Choose STARTTLS or implicit SSL.";
    return null;
  }
  const changed = Object.keys(form.credentials).length > 0 || saved?.email_provider !== form.provider;
  if (!changed && saved?.email_provider_configured) return null;
  const required = PROVIDER_FIELDS[form.provider].filter(key => key !== "session_token"
    && !(form.provider === "ses" && form.credentials.workload_identity && ["access_key_id", "secret_access_key"].includes(key)));
  if (required.some(key => !String(form.credentials[key] ?? "").trim())) return "Enter all required provider fields to replace the saved configuration.";
  return null;
}
export function emailPayload(form: EmailForm, platform: boolean) {
  const payload: Record<string, unknown> = { email_provider: form.provider === "inherit" && platform ? "" : form.provider };
  if (form.provider === "inherit") {
    // The legacy platform fallback uses an empty host; selecting environment must clear it.
    if (platform) payload.smtp_host = "";
    return payload;
  }
  payload[platform ? "from_email" : "smtp_from_email"] = form.sender.trim();
  if (form.provider === "smtp") {
    Object.assign(payload, { smtp_host: form.host.trim(), smtp_port: Number(form.port),
      smtp_username: form.username, smtp_use_tls: form.tls, smtp_use_ssl: form.ssl });
    if (form.password) payload.smtp_password = form.password;
  } else if (Object.keys(form.credentials).length) {
    payload.email_provider_config = Object.fromEntries(Object.entries(form.credentials).filter(([, value]) => value !== ""));
  }
  return payload;
}
