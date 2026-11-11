import { t } from "@lingui/core/macro";
import { useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { CustomFormBuilder } from "../forms/CustomFormBuilder";
import type { CustomFormSchema } from "../forms/customFormTypes";
import type { BookableSpace, BookableSpacePayload } from "./bookingsApi";
import { getBookingMachineTypes } from "./staffBookingApi";

import { FormPageLayout } from "../../components/layouts";
import { ErrorBlock, SettingsActions, PagePager } from "../../components/ui";
import { BookableSpaceFields } from "./BookableSpaceFields";
import { useStaffChargesOn } from "./useStaffChargesOn";
import { BookableSpaceMachine, useMachineTimeBookingOn } from "./BookableSpaceMachine";

type FormValues = BookableSpacePayload;

export const EMPTY_SPACE_FORM: FormValues = {
  name: "",
  kind: "other",
  description: "",
  capacity: 0,
  location: "",
  is_public: false,
  show_public_availability: false,
  show_public_booker_names: false,
  payment_amount: "0.00",
  custom_form: null,
  requester_notifications_enabled: null,
  machine_type: null,
};

export function valuesForSpace(space: BookableSpace): FormValues {
  return {
    name: space.name,
    kind: space.kind,
    description: space.description,
    capacity: space.capacity,
    location: space.location,
    is_public: space.is_public,
    show_public_availability: space.show_public_availability,
    show_public_booker_names: space.show_public_booker_names,
    payment_amount: space.payment_amount,
    custom_form: space.custom_form,
    requester_notifications_enabled: space.requester_notifications_enabled,
    machine_type: space.machine_type ?? null,
    machine: space.machine ?? null,
  };
}

export function BookableSpaceForm({ makerspaceId, initialValues = EMPTY_SPACE_FORM, onSubmit, pending, error, submitLabel, disabled = false, mode = "form", onCancel }: {
  makerspaceId: number;
  initialValues?: FormValues;
  onSubmit: (payload: BookableSpacePayload) => void;
  pending: boolean;
  error?: string;
  submitLabel: string;
  disabled?: boolean;
  mode?: "form" | "create" | "settings";
  onCancel?: () => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<FormValues>(initialValues);
  const [typePage, setTypePage] = useState(1);
  const types = useQuery({
    queryKey: ["booking-machine-types", makerspaceId, typePage],
    queryFn: () => getBookingMachineTypes(makerspaceId, typePage),
    retry: false,
  });
  const machineTypes = types.data?.results ?? [];
  const machineTimeOn = useMachineTimeBookingOn(makerspaceId);
  const chargesOn = useStaffChargesOn("bookings", makerspaceId);
  const set =<K extends keyof FormValues>(key: K, value: FormValues[K]) => setValues((current) => ({ ...current, [key]: value }));
  const submitPayload = () => {
    const payload: BookableSpacePayload = {
      ...values,
      name: values.name.trim(),
      description: values.description.trim(),
      location: values.location.trim(),
      custom_form: values.custom_form?.length ? values.custom_form : null,
    };
    // An unchanged link must survive editing while Machines is uninstalled.
    // The server validates machine_type only when the caller actually changes it.
    if (values.machine_type === initialValues.machine_type) delete payload.machine_type;
    // Only a "Machine time" resource books one machine; leaving that kind clears the link. Unchanged, it is not sent.
    const machine = values.kind === "machine" ? values.machine ?? null : null;
    if (machine === (initialValues.machine ?? null)) delete payload.machine; else payload.machine = machine;
    onSubmit(payload);
  };
  const changeAvailability = (checked: boolean) => setValues((current) => ({
    ...current,
    show_public_availability: checked,
    show_public_booker_names: checked ? current.show_public_booker_names : false,
  }));
  const submit = (event: FormEvent) => { event.preventDefault(); submitPayload(); };
  const dirty = JSON.stringify(values) !== JSON.stringify(initialValues);
  const fields = <>
    <fieldset className="min-w-0 grid gap-6" disabled={disabled || pending}>
      <BookableSpaceFields values={values} set={set} machineTypes={machineTypes} typesError={types.error?.message}
        changeAvailability={changeAvailability} chargesOn={chargesOn}
        machineTime={{ available: machineTimeOn !== false, picker: pickerId => <BookableSpaceMachine makerspaceId={makerspaceId} id={pickerId}
          value={values.machine ?? null} onChange={machine => set("machine", machine)} /> }} pagination={<PagePager page={typePage} setPage={setTypePage} next={types.data?.next} disabled={types.isFetching} />} />
    </fieldset>
    <CustomFormBuilder value={values.custom_form as CustomFormSchema} onChange={schema => set("custom_form", schema)} disabled={disabled || pending} />
    {error ? <ErrorBlock error={new Error(error)} /> : null}
  </>;
  if (mode === "create") return <FormPageLayout header={{ title: t`New space`, subtitle: t`Create a place your community can book.` }}
    state={{ status: "ready" }} back={{ label: t`Bookings`, onClick: onCancel }} form={fields}
    submit={{ label: submitLabel, onClick: submitPayload, pending, pendingLabel: t`Creating…` }}
    cancel={onCancel ? { label: t`Cancel`, onClick: onCancel } : undefined} />;
  return <form ref={formRef} className="grid gap-6" onSubmit={submit}>
    {fields}
    {!disabled ? mode === "settings" ? dirty || pending ? <SettingsActions pending={pending}
      onDiscard={() => setValues(initialValues)} onSave={() => formRef.current?.requestSubmit()} /> : null
      : <button className="desk-button-primary w-fit" type="submit" disabled={pending}>{pending ? t`Saving…` : submitLabel}</button> : null}
  </form>;
}
