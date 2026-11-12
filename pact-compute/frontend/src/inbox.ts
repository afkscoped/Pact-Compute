// Pure helpers for the reviewer inbox (unit-tested with `node --test`).
export type Span = { start: number | null; end: number | null };
export type Segment = { text: string; clause: number | null };

// Split `source` into plain and highlighted segments. Spans may be unsorted or overlap; overlaps and
// out-of-range spans are ignored so malformed model output can never break the page.
export function segments(source: string, clauses: Span[]): Segment[] {
  const usable = clauses
    .map((clause, index) => ({ index, start: clause.start, end: clause.end }))
    .filter((clause): clause is { index: number; start: number; end: number } =>
      clause.start !== null && clause.end !== null && clause.start >= 0 && clause.end > clause.start && clause.end <= source.length)
    .sort((a, b) => a.start - b.start || a.end - b.end);
  const out: Segment[] = [];
  let cursor = 0;
  for (const clause of usable) {
    if (clause.start < cursor) continue;
    if (clause.start > cursor) out.push({ text: source.slice(cursor, clause.start), clause: null });
    out.push({ text: source.slice(clause.start, clause.end), clause: clause.index });
    cursor = clause.end;
  }
  if (cursor < source.length) out.push({ text: source.slice(cursor), clause: null });
  return out;
}

export const MIN_REASON = 12;
export function reasonProblem(reason: string): string | null {
  const length = reason.trim().length;
  return length >= MIN_REASON ? null : `Explain the decision in at least ${MIN_REASON} characters (${length} so far).`;
}

export function valueText(value: string | number | boolean): string {
  return typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value);
}
