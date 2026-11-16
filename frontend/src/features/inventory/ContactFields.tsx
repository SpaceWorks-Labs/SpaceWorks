import { t } from "@lingui/core/macro";
import { BoxArt } from "../../components/BoxSpinner";
// A makerspace without member accounts has accounts for staff only (owner decision #80),
// so a public borrower asks with name, phone and email instead, and proves the email with
// a one-time code before the request is accepted. Phone and email reach staff only; the
// name is shown wherever the space shows borrower names publicly.
export type ContactDetails = {
  name: string;
  email: string;
  phone: string;
  code: string;
  onNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPhoneChange: (value: string) => void;
  onCodeChange: (value: string) => void;
  onSendCode: () => void;
  codePending: boolean;
  codeSent: boolean;
  codeError?: string;
};

type TextFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  autoComplete?: string;
  maxLength: number;
  placeholder?: string;
};

function TextField({ label, value, onChange, type = "text", autoComplete, maxLength, placeholder }: TextFieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-ink">{label}</span>
      <input
        autoComplete={autoComplete}
        className="desk-input w-full"
        maxLength={maxLength}
        placeholder={placeholder}
        required
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function ContactFields({ contact }: { contact: ContactDetails }) {
  const emailReady = contact.email.trim().length > 3 && contact.email.includes("@");
  return (
    <div className="space-y-3">
      <TextField label={t`Your name (shown publicly)`} value={contact.name} onChange={contact.onNameChange}
        autoComplete="name" maxLength={200} placeholder={t`Ada Lovelace`} />
      <TextField label={t`Phone (staff only)`} value={contact.phone} onChange={contact.onPhoneChange}
        type="tel" autoComplete="tel" maxLength={32} placeholder="+44 20 1234 5678" />
      <TextField label={t`Email (staff only)`} value={contact.email} onChange={contact.onEmailChange}
        type="email" autoComplete="email" maxLength={254} placeholder="you@example.com" />
      <button className="desk-button w-full" type="button" disabled={!emailReady || contact.codePending}
        onClick={contact.onSendCode}>
        {contact.codePending ? <><BoxArt size={16} mono />{t`Sending code...`}</> : contact.codeSent ? t`Send a new code` : t`Email me a code`}
      </button>
      {contact.codeSent ? (
        <p className="text-sm text-muted">{t`We sent a 6-digit code to that address. It expires in 10 minutes.`}</p>
      ) : null}
      {contact.codeError ? <p role="alert" className="text-sm text-danger">{contact.codeError}</p> : null}
      <TextField label={t`Email code`} value={contact.code} onChange={contact.onCodeChange}
        autoComplete="one-time-code" maxLength={6} placeholder="123456" />
    </div>
  );
}
