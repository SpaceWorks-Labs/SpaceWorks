import { SampleIdCard } from "./SampleIdCard";

/**
 * AuthLayout's inert decorative showcase slot (decision 306 addendum): a sample staff ID card from the
 * card designer, drawn by the real renderer. The slot itself is aria-hidden, inert and shown only from
 * the xl breakpoint, so on phones and tablets nothing sits near the form.
 */
export function AuthShowcase() {
  return <div className="justify-self-start -rotate-2 rounded-[3.18mm] shadow-[0_24px_48px_-16px_rgba(20,44,42,0.35),0_0_0_1px_rgba(20,44,42,0.08)] dark:shadow-[0_24px_56px_-16px_rgba(0,0,0,0.7),0_0_0_1px_rgba(255,255,255,0.12)]">
    <SampleIdCard width={380} />
  </div>;
}
