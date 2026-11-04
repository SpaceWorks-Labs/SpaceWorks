import { useState } from "react";
import { Field } from "../ui";
import { LayoutGalleryExample, layoutGalleryExamples, type LayoutGalleryExampleName } from "./LayoutGalleryExamples";

/** Dev/test only. Intentionally not registered in the application router or barrel. */
export function LayoutGallery({ initialExample = "Dashboard" }: { initialExample?: LayoutGalleryExampleName }) {
  const [example, setExample] = useState(initialExample);
  if (!import.meta.env.DEV && import.meta.env.MODE !== "test") return null;
  return <div className="min-h-dvh bg-bg text-ink">
    <div className="border-b border-line bg-panel p-4">
      <Field label="Layout gallery"><select className="desk-input max-w-full" value={example}
        onChange={event => setExample(event.target.value as LayoutGalleryExampleName)}>
        {layoutGalleryExamples.map(name => <option key={name}>{name}</option>)}
      </select></Field>
    </div>
    <LayoutGalleryExample key={example} example={example} onDismiss={() => setExample("Dashboard")} />
  </div>;
}
