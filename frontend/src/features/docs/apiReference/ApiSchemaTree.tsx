import { t } from "@lingui/core/macro";
import { useState } from "react";
import type { SchemaNode } from "./apiReferenceModel";
import { childrenOf, enumValues, isExpandable, isNullable, resolveSchema, typeLabel, type SchemaField, type Schemas } from "./apiSchema";

type TreeProps = { schema: SchemaNode; schemas: Schemas; seen?: readonly string[]; depth?: number };

function FieldMeta({ field, schemas }: { field: SchemaField; schemas: Schemas }) {
  const resolved = resolveSchema(field.schema, schemas).schema;
  const values = enumValues(field.schema, schemas);
  const description = (field.schema.description ?? resolved.description) as string | undefined;
  return <>
    <span className="code-text font-semibold text-ink">{field.name}</span>
    <span className="code-text text-sm text-muted">{typeLabel(field.schema, schemas)}</span>
    {field.required ? <span className="rounded-full bg-warn px-2 text-xs font-semibold text-on-warn">{t`required`}</span> : null}
    {isNullable(resolved) || isNullable(field.schema) ? <span className="text-xs text-muted">{t`nullable`}</span> : null}
    {resolved.readOnly || field.schema.readOnly ? <span className="text-xs text-muted">{t`read-only`}</span> : null}
    {description ? <span className="basis-full text-sm text-muted [overflow-wrap:anywhere]">{description}</span> : null}
    {values.length ? <span className="basis-full text-sm text-muted">{t`One of:`}{" "}
      {values.slice(0, 24).map((value, index) => <span key={value}>{index ? ", " : ""}<code className="code-text text-ink">{value}</code></span>)}
      {values.length > 24 ? ` … (${values.length})` : null}</span> : null}
  </>;
}

/** One property. Nested shapes stay unrendered until opened, so a deep schema costs nothing up front. */
function FieldRow({ field, schemas, seen, depth }: { field: SchemaField; schemas: Schemas; seen: readonly string[]; depth: number }) {
  const [open, setOpen] = useState(false);
  // An array of a schema already open above it is the same cycle as a direct reference.
  const items = childrenOf(field.schema, schemas).items;
  const name = resolveSchema(field.schema, schemas).name ?? (items ? resolveSchema(items, schemas).name : null);
  const cyclic = Boolean(name && seen.includes(name));
  const expandable = !cyclic && isExpandable(field.schema, schemas);
  const meta = <FieldMeta field={field} schemas={schemas} />;
  if (!expandable) {
    return <li className="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-t border-line py-2 first:border-t-0">
      {meta}{cyclic ? <span className="text-xs text-muted">{t`(same shape as above)`}</span> : null}
    </li>;
  }
  return <li className="border-t border-line py-2 first:border-t-0">
    <details open={open} onToggle={event => setOpen(event.currentTarget.open)}>
      <summary className="flex cursor-pointer flex-wrap items-baseline gap-x-2 gap-y-1 rounded-control focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">{meta}</summary>
      {open ? <div className="mt-2 border-l border-line pl-3 sm:pl-4">
        <SchemaTree schema={field.schema} schemas={schemas} seen={name ? [...seen, name] : seen} depth={depth + 1} />
      </div> : null}
    </details>
  </li>;
}

/** The fields of an object, the items of an array, or the variants of a union; cycle-safe. */
export function SchemaTree({ schema, schemas, seen = [], depth = 0 }: TreeProps) {
  const { name } = resolveSchema(schema, schemas);
  const trail = name && !seen.includes(name) ? [...seen, name] : seen;
  const { fields, variants, items } = childrenOf(schema, schemas);
  if (fields.length) {
    return <ul className="grid">{fields.map(field => <FieldRow key={field.name} field={field} schemas={schemas} seen={trail} depth={depth} />)}</ul>;
  }
  if (variants.length) {
    return <div className="grid gap-2">
      <p className="text-sm text-muted">{t`One of these shapes:`}</p>
      {variants.map((variant, index) => <div key={index} className="rounded-xl border border-line p-3">
        <p className="code-text mb-1 text-sm font-semibold text-ink">{typeLabel(variant, schemas)}</p>
        {isExpandable(variant, schemas) && depth < 8 ? <SchemaTree schema={variant} schemas={schemas} seen={trail} depth={depth + 1} /> : null}
      </div>)}
    </div>;
  }
  if (items && isExpandable(items, schemas) && depth < 8) {
    return <div className="grid gap-1">
      <p className="text-sm text-muted">{t`Each item:`} <span className="code-text text-ink">{typeLabel(items, schemas)}</span></p>
      <SchemaTree schema={items} schemas={schemas} seen={trail} depth={depth + 1} />
    </div>;
  }
  return <p className="code-text text-sm text-muted">{typeLabel(schema, schemas)}</p>;
}

/** A body or response: its type line, then its fields shown one level deep. */
export function SchemaBlock({ schema, schemas, mediaType }: { schema: SchemaNode | null; schemas: Schemas; mediaType: string }) {
  if (!schema) return <p className="text-sm text-muted">{t`No schema (${mediaType}).`}</p>;
  return <div className="grid gap-2">
    <p className="flex flex-wrap items-baseline gap-2 text-sm">
      <span className="code-text font-semibold text-ink">{typeLabel(schema, schemas)}</span>
      <span className="text-muted">{mediaType}</span>
    </p>
    {isExpandable(schema, schemas) ? <div className="rounded-xl border border-line bg-panel px-3 py-1 sm:px-4">
      <SchemaTree schema={schema} schemas={schemas} />
    </div> : null}
  </div>;
}
