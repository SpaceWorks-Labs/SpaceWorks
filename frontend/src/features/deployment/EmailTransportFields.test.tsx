import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { EmailTransportFields } from "./EmailTransportFields";
import { emailForm, type EmailForm, type EmailProvider } from "./emailSettings";

let latest: EmailForm;
function Harness({ initial, ...props }: { initial?: Partial<EmailForm>; platform?: boolean; disabled?: boolean; configured?: boolean; passwordSet?: boolean }) {
  const [form, setForm] = useState<EmailForm>({ ...emailForm(), ...initial });
  latest = form;
  return <EmailTransportFields form={form} onChange={setForm} platform={props.platform ?? false} disabled={props.disabled ?? false} configured={props.configured} passwordSet={props.passwordSet} />;
}
const show = (initial?: Partial<EmailForm>, props: Omit<Parameters<typeof Harness>[0], "initial"> = {}) => render(<Harness initial={initial} {...props} />);
const choose = (provider: EmailProvider) => fireEvent.change(screen.getByLabelText("Email provider"), { target: { value: provider } });

describe("provider choice", () => {
  it("labels inherit differently for the platform and a makerspace, and names each provider", () => {
    const { unmount } = show({}, { platform: true });
    const options = within(screen.getByLabelText("Email provider")).getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Use deployment environment", "SMTP", "Resend (HTTP)", "Postmark (HTTP)", "Amazon SES (HTTP)", "Brevo (HTTP)", "Mailgun (HTTP)", "Sendgrid (HTTP)"]);
    expect(screen.getByText(/Password resets and authentication mail always use platform configuration\./)).toBeInTheDocument();
    unmount();
    show();
    expect(screen.getByRole("option", { name: "Inherit platform email" })).toBeInTheDocument();
    expect(screen.getByText(/Makerspace notifications use this sender\. Platform authentication mail remains separate\./)).toBeInTheDocument();
  });
  it("inherit shows no sender or credential fields", () => {
    show({ provider: "inherit" });
    expect(screen.queryByLabelText("From email")).toBeNull();
    expect(screen.queryByLabelText("SMTP host")).toBeNull();
  });
  it("changing the provider clears credentials and the password but keeps the sender", () => {
    show({ provider: "smtp", sender: "a@x.test", password: "secret", credentials: { api_key: "k" } });
    choose("resend");
    expect(latest).toMatchObject({ provider: "resend", password: "", credentials: {}, sender: "a@x.test" });
  });
  it("disables every control while disabled", () => {
    show({ provider: "smtp" }, { disabled: true });
    expect(screen.getByLabelText("Email provider")).toBeDisabled();
    expect(screen.getByLabelText("SMTP host")).toBeDisabled();
  });
});

describe("SMTP", () => {
  it("edits sender, host, port, username and password, with the password hint following whether one is saved", () => {
    const { unmount } = show({ provider: "smtp" }, { passwordSet: true });
    expect(screen.getByText("Password set. Leave blank to keep it.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("From email"), { target: { value: "me@x.test" } });
    fireEvent.change(screen.getByLabelText("SMTP host"), { target: { value: "smtp.x.test" } });
    fireEvent.change(screen.getByLabelText("SMTP port"), { target: { value: "2525" } });
    fireEvent.change(screen.getByLabelText("SMTP username"), { target: { value: "mailer" } });
    fireEvent.change(screen.getByLabelText("SMTP password"), { target: { value: "pw" } });
    expect(latest).toMatchObject({ sender: "me@x.test", host: "smtp.x.test", port: "2525", username: "mailer", password: "pw" });
    unmount();
    show({ provider: "smtp" }, { passwordSet: false });
    expect(screen.getByText("No password saved.")).toBeInTheDocument();
  });
  it("STARTTLS and implicit SSL are mutually exclusive", () => {
    show({ provider: "smtp", tls: true, ssl: false });
    fireEvent.click(screen.getByLabelText("Use implicit SSL (465)"));
    expect(latest).toMatchObject({ tls: false, ssl: true });
    fireEvent.click(screen.getByLabelText("Use STARTTLS (587)"));
    expect(latest).toMatchObject({ tls: true, ssl: false });
    fireEvent.click(screen.getByLabelText("Use STARTTLS (587)"));
    expect(latest).toMatchObject({ tls: false, ssl: false });
    fireEvent.click(screen.getByLabelText("Use implicit SSL (465)"));
    fireEvent.click(screen.getByLabelText("Use implicit SSL (465)"));
    expect(latest).toMatchObject({ tls: false, ssl: false });
  });
});

describe("HTTP providers", () => {
  it("resend: API key plus optional alias and webhook secret, all masked", () => {
    show({ provider: "resend" });
    expect(screen.getByText(/^Enter the provider configuration./)).toBeInTheDocument();
    for (const label of ["API key", "Shared provider account alias (optional)", "Webhook secret (optional)"]) expect(screen.getByLabelText(label)).toHaveAttribute("type", "password");
    expect(screen.queryByLabelText("Webhook signing key (optional)")).toBeNull();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "re_123" } });
    expect(latest.credentials).toEqual({ api_key: "re_123" });
  });
  it("mailgun: sending domain and region are visible text, region carries the us/eu hint, and the signing key is optional", () => {
    show({ provider: "mailgun" });
    expect(screen.getByLabelText("Sending domain")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("Region")).toHaveAttribute("type", "text");
    expect(screen.getByText("Enter us or eu.")).toBeInTheDocument();
    expect(screen.getByLabelText("Webhook signing key (optional)")).toHaveAttribute("type", "password");
    expect(screen.queryByLabelText("Webhook secret (optional)")).toBeNull();
  });
  it("postmark uses a server token and no region hint", () => {
    show({ provider: "postmark" });
    expect(screen.getByLabelText("Server token")).toBeInTheDocument();
    expect(screen.queryByText("Enter us or eu.")).toBeNull();
  });
  it("a saved configuration says to leave fields blank to keep it", () => {
    show({ provider: "brevo" }, { configured: true });
    expect(screen.getByText(/Provider configuration saved\. Leave fields blank to keep it/)).toBeInTheDocument();
  });
  it("SES offers workload identity, which hides the AWS key fields but keeps the region", () => {
    show({ provider: "ses" });
    for (const label of ["Dedicated AWS access key ID", "Dedicated AWS secret access key", "AWS session token (optional)", "Region"]) expect(screen.getByLabelText(label)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Use dedicated workload identity for SES"));
    expect(latest.credentials).toEqual({ workload_identity: true });
    expect(screen.queryByLabelText("Dedicated AWS access key ID")).toBeNull();
    expect(screen.queryByLabelText("AWS session token (optional)")).toBeNull();
    expect(screen.getByLabelText("Region")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Use dedicated workload identity for SES"));
    expect(screen.getByLabelText("Dedicated AWS access key ID")).toBeInTheDocument();
  });
});
