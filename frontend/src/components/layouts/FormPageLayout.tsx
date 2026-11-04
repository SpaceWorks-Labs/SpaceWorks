import { useRef, useState, type ReactNode } from "react";
import { ActionControl, Card, CollapsibleSection, PageHeader } from "../ui";
import type { Action, PageHeaderProps } from "../ui";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import type { LayoutProps } from "./types";
import { useLayoutMedia } from "./useLayoutMedia";

export type FormPageLayoutProps = Omit<LayoutProps, "width"> & {
  back?: Action;
  header: PageHeaderProps;
  form: ReactNode;
  preview?: { label: string; content: ReactNode };
  submit: Action & { href?: never };
  cancel?: Action;
  width?: "default" | "narrow" | "wide";
};
export function FormPageLayout({ back, header, form, preview, submit, cancel, width = "default", standalone, ...query }: FormPageLayoutProps) {
  const formRef = useRef<HTMLFormElement>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const tablet = useLayoutMedia("(min-width: 768px)");
  return <LayoutFrame standalone={standalone} width={width}>
    <PageHeader {...header} back={back} />
    <QueryContent {...query}>
      <div className={preview && width !== "narrow" ? "sw-form-columns" : "min-w-0"}>
        <form ref={formRef} className="grid min-w-0 content-start gap-6" onSubmit={event => {
          event.preventDefault();
          if (!submit.disabled && !submit.pending) submit.onClick?.();
        }}>
          <Card>{form}</Card>
          <div className="sw-sticky-footer sw-sticky-footer-mobile flex flex-wrap gap-3 border-t border-line bg-panel pt-4 md:border-0 md:bg-transparent">
            <ActionControl primary action={{ ...submit, onClick: () => formRef.current?.requestSubmit() }} />
            {cancel ? <ActionControl action={cancel} /> : null}
          </div>
        </form>
        {preview ? tablet ? <aside aria-label={preview.label} className="min-w-0 self-start xl:sticky xl:top-6">
          <h2 className="eyebrow mb-3">{preview.label}</h2>{preview.content}
        </aside> : <CollapsibleSection title={preview.label} open={previewOpen} onToggle={() => setPreviewOpen(!previewOpen)}>
          <div className="p-4">{preview.content}</div>
        </CollapsibleSection> : null}
      </div>
    </QueryContent>
  </LayoutFrame>;
}
