import { useState } from "react";
import { PassState } from "./PassState";
import { SuccessCard } from "./SuccessCard";
import { BrandLoader, MoodGlyph } from "./Artwork";
import { Companion } from "./Companion";
import { ThemeToggle } from "../ThemeToggle";
import { ConfirmationGreeting, DotMeter, EventTimeChip, SetupChecklist, StaffGreeting } from "./StatusDetails";
import { WordFeedback, type FeedbackWord } from "./WordFeedback";
import { WorkshopLogbook } from "./WorkshopLogbook";
import { SpaceWorksDemo } from "../../features/landing/SpaceWorksDemo";
import { MakerModePanel, MakerModeToggle, useMakerMode } from "./EasterEggs";
import { delightTone } from "./tone";

/** Browser acceptance fixture; G may mount this within its existing fixture harness, never a hidden route. */
export function DelightFixtures() {
  const [rating, setRating] = useState<FeedbackWord | null>(null);
  const mode = useMakerMode("/about");
  return <div className="grid gap-6 bg-surface p-6 text-ink">
    <section aria-label="1 Persistent pass"><PassState accent={false} title="Booking pass" value={{ state: "completed", label: "Checked in", completedAt: "2026-10-18T10:00:00Z" }} /></section>
    <section aria-label="2 Result card"><SuccessCard kind="success" name="Alex" message="Handover recorded." resultId="sample-result" /></section>
    <section aria-label="3 Loader and moods"><BrandLoader />{(["welcome", "success", "waiting", "empty", "error"] as const).map(mood => <MoodGlyph key={mood} mood={mood} />)}</section>
    <section aria-label="4 Companion"><Companion /><p>404 acceptance: open a known-unknown URL in G's browser harness.</p></section>
    <section aria-label="5 Theme reveal"><ThemeToggle /></section>
    <section aria-label="6 Greetings and setup"><StaffGreeting name="Alex" /><ConfirmationGreeting name="Alex" /><SetupChecklist steps={[{ key: "inventory", label: "Add inventory", done: false, available: true, href: "/admin/inventory" }]} /></section>
    <section aria-label="7 Meters and time"><DotMeter value={{ mode: "exact_count", count: 3, total: 8 }} /><EventTimeChip startsAt="2026-10-18T10:00:00Z" endsAt="2026-10-18T12:00:00Z" now={new Date("2026-10-18T11:00:00Z")} /></section>
    <section aria-label="8 Word feedback"><WordFeedback version="words_v1" value={rating} onChange={setRating} /></section>
    <section aria-label="9 Logbook"><WorkshopLogbook /></section>
    <section aria-label="10 Landing demo"><SpaceWorksDemo /></section>
    <section aria-label="11 Plain errors"><p>{delightTone.retry}</p></section>
    <section aria-label="12 Maker mode"><MakerModeToggle mode={mode} /><MakerModePanel mode={mode} version="fixture" /></section>
  </div>;
}
