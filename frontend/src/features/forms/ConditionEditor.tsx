import type { Condition, Question } from "./types";

export function ConditionEditor({ value, earlier, onChange }: { value?: Condition; earlier: Question[]; onChange: (value?: Condition) => void }) {
  const eligible = earlier.filter(q => !q.sensitive && !["age_at_event", "date_of_birth"].includes(q.type));
  return <fieldset className="grid gap-2 rounded-xl border border-line p-3"><legend className="text-sm font-semibold">Show this question when</legend>
    {value ? <ConditionNode value={value} earlier={eligible} depth={1} total={countClauses(value)} onChange={onChange} /> : <button className="desk-button justify-self-start" type="button" disabled={!eligible.length} onClick={() => onChange({ all: [{ field_id: eligible[0].id, op: "is_set" }] })}>Add condition</button>}
    {value ? <button className="desk-button justify-self-start" type="button" onClick={() => onChange(undefined)}>Always show</button> : null}
  </fieldset>;
}
function countClauses(value: Condition): number { return "field_id" in value ? 1 : ("all" in value ? value.all : value.any).reduce((sum, child) => sum + countClauses(child), 0); }
function ConditionNode({ value, earlier, depth, total, onChange }: { value: Condition; earlier: Question[]; depth: number; total: number; onChange: (value?: Condition) => void }) {
  if ("field_id" in value) {
    const type = earlier.find(q => q.id === value.field_id)?.type;
    const parse = (input: string) => type === "number" && input !== "" ? Number(input) : type === "yes_no" ? input === "true" : input;
    return <div className="grid gap-2 rounded-lg border border-line p-2 sm:grid-cols-3">
      <label className="grid gap-1 text-sm">Earlier question<select className="desk-input" value={value.field_id} onChange={e => onChange({ field_id: e.target.value, op: "is_set" })}>{earlier.map(q => <option key={q.id} value={q.id}>{q.label}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Comparison<select className="desk-input" value={value.op} onChange={e => onChange({ ...value, op: e.target.value as typeof value.op, value: e.target.value === "is_set" ? true : e.target.value === "in" ? [] : "" })}>{["eq", "ne", "in", "contains", "is_set"].map(op => <option key={op}>{op}</option>)}</select></label>
      {value.op === "is_set" ? <label className="grid gap-1 text-sm">Answer state<select className="desk-input" value={value.value === false ? "false" : "true"} onChange={e => onChange({ ...value, value: e.target.value === "true" })}><option value="true">Answered</option><option value="false">Not answered</option></select></label> : <label className="grid gap-1 text-sm">{value.op === "in" ? "Values (comma separated)" : "Value"}<input className="desk-input" value={Array.isArray(value.value) ? value.value.join(",") : String(value.value ?? "")} onChange={e => onChange({ ...value, value: value.op === "in" ? e.target.value.split(",").map(item => parse(item.trim())) : parse(e.target.value) })} /></label>}
      <button className="desk-button justify-self-start" type="button" onClick={() => onChange(undefined)}>Remove condition</button>
    </div>;
  }
  const group = "all" in value ? "all" : "any";
  const children = "all" in value ? value.all : value.any;
  const commit = (next: Condition[]) => onChange(next.length ? group === "all" ? { all: next } : { any: next } : undefined);
  return <fieldset className="grid gap-2 rounded-lg border border-line p-2"><legend className="text-xs">Condition group · level {depth}</legend>
    <label className="grid gap-1 text-sm">Match<select className="desk-input" value={group} onChange={e => onChange(e.target.value === "all" ? { all: children } : { any: children })}><option value="all">All conditions</option><option value="any">Any condition</option></select></label>
    {children.map((child, index) => <ConditionNode key={index} value={child} earlier={earlier} depth={depth + 1} total={total} onChange={next => commit(next ? children.map((item, i) => i === index ? next : item) : children.filter((_, i) => i !== index))} />)}
    <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" disabled={total >= 20 || !earlier.length || depth >= 3} onClick={() => commit([...children, { field_id: earlier[0].id, op: "is_set" }])}>Add comparison</button>{depth < 2 ? <button className="desk-button" type="button" disabled={total >= 20 || !earlier.length} onClick={() => commit([...children, { any: [{ field_id: earlier[0].id, op: "is_set" }] }])}>Add nested group</button> : null}</div>
  </fieldset>;
}
