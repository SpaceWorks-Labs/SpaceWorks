import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { useStaffGet } from "../staff/StaffPanels";
import { emailForm, emailPayload, emailValidation, type EmailSettings } from "./emailSettings";

export function useEmailSettings(endpoint: string, queryKey: (string | number)[], platform: boolean) {
  const client = useQueryClient();
  const settings = useStaffGet<EmailSettings>(queryKey, endpoint);
  const [form, setForm] = useState(() => emailForm());
  const [saved, setSaved] = useState(form);
  useEffect(() => {
    if (!settings.data) return;
    const next = emailForm(settings.data);
    setForm(next); setSaved(next);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: async () => {
      const problem = emailValidation(form, settings.data);
      if (problem) throw new Error(problem);
      return staffRequest<EmailSettings>(endpoint, { method: "PATCH", body: JSON.stringify(emailPayload(form, platform)) });
    },
    onSuccess: () => {
      // Credentials leave component state immediately, including while refetch is pending.
      setForm(current => ({ ...current, password: "", credentials: {} }));
      void client.invalidateQueries({ queryKey, exact: true });
    },
  });
  const clearPassword = useMutation({
    mutationFn: () => staffRequest<EmailSettings>(endpoint, { method: "PATCH", body: JSON.stringify({ smtp_password: "" }) }),
    onSuccess: () => { setForm(current => ({ ...current, password: "" })); void client.invalidateQueries({ queryKey, exact: true }); },
  });
  return { settings, form, setForm, save, clearPassword,
    dirty: JSON.stringify(form) !== JSON.stringify(saved),
    validation: emailValidation(form, settings.data),
    discard: () => { setForm(saved); save.reset(); },
  };
}
