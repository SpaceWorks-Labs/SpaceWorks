import { useState } from "react";
import { Field } from "../../../components/ui/Field";

/** Keep partially typed separators in memory while marking every edit dirty. */
export function CommaListField({ label, hint, values, onChange, pattern }: { label: string; hint: string;
  values: (string | number)[]; onChange: (parts: string[]) => void; pattern?: string;
}) {
  const [raw, setRaw] = useState(values.join(", "));
  return <Field label={label} hint={hint}><input className="desk-input" value={raw} pattern={pattern} onChange={event => {
    setRaw(event.target.value); onChange(event.target.value.split(",").map(part => part.trim()).filter(Boolean));
  }} /></Field>;
}
