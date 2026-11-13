/** Date-only arithmetic: the event supplies its own local start date. Never persist this result. */
export function ageAtEvent(dateOfBirth: string, asOfDate: string): number | null {
  const valid = (date: string) => /^\d{4}-\d{2}-\d{2}$/.test(date) && !Number.isNaN(Date.parse(`${date}T00:00:00Z`)) && new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) === date;
  if (!valid(dateOfBirth) || !valid(asOfDate) || dateOfBirth > asOfDate) return null;
  const [birthYear, birthMonth, birthDay] = dateOfBirth.split("-").map(Number);
  const [year, month, day] = asOfDate.split("-").map(Number);
  return year - birthYear - (month < birthMonth || month === birthMonth && day < birthDay ? 1 : 0);
}
