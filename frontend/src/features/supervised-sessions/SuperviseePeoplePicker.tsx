import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { AsyncSearchPicker, type PickerOption } from "../staff/AsyncSearchPicker";
import { supervisedErrorMessage, useSupervisedPeople } from "./api";

/** The instructor's supervisee search. The server only searches people checked in at the space or
 *  registered for the session's event, and only for the open session's instructor: anyone else (a
 *  machine manager looking after the session) is answered 404 and types the account number instead. */
export function SuperviseePeoplePicker({ sessionId, value, onChange }: {
  sessionId: number; value: string; onChange: (value: string) => void;
}) {
  const [term, setTerm] = useState("");
  const [chosen, setChosen] = useState<PickerOption | null>(null);
  const people = useSupervisedPeople(sessionId, term);
  if (people.error instanceof StructuredApiError && people.error.status === 404) return <AccountNumberField value={value} onChange={onChange} />;
  const selected = chosen && value === String(chosen.id) ? [chosen] : [];
  return <AsyncSearchPicker label={t`Supervisee`}
    helper={t`Search people checked in at the space or registered for this session's event. Type at least two letters.`}
    selected={selected} options={term.length >= 2 ? (people.data?.results ?? []).map(row => ({ id: row.id, label: row.display_name })) : []}
    loading={people.isFetching} error={people.error ? supervisedErrorMessage(people.error) : null}
    emptyText={term.length < 2 ? t`Type at least two letters.` : t`Nobody checked in or registered matches.`}
    onSearch={setTerm} onChange={next => {
      const row = next.at(-1) ?? null;
      setChosen(row);
      onChange(row ? String(row.id) : "");
    }} />;
}

function AccountNumberField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <Field label={t`Supervisee's account number`}
    hint={t`Only the session's instructor can search people. Ask the person or a staff member for their account number.`}>
    <input className="desk-input" inputMode="numeric" pattern="[0-9]*" value={value}
      onChange={event => onChange(event.target.value.replace(/\D/g, ""))} />
  </Field>;
}
