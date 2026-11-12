// Pure helpers for the counterfactual preview (unit-tested with `node --test`).
export type EditKind = 'deadline_seconds' | 'max_charge_cents' | 'grid_zone';
export type Edit = { kind: EditKind; value: number | string };
export type Option = {
  edits: Edit[]; label: string; feasible: boolean; blocking_codes: string[]; resolved_codes: string[]; new_codes: string[];
  selected: { runner_name: string; quote_cents: number; envelope_cents: number; zone: string | null } | null;
};
export type Counterfactual = {
  policy_id: string; notice: string; suggested: boolean; options: Option[];
  baseline: { feasible: boolean; blocking_codes: string[] };
};
type RuleLike = { kind: string; value: string | number | boolean; start: number | null; end: number | null; rationale: string | null; strict: boolean };

export const KIND_NAMES: Record<EditKind, string> = {
  deadline_seconds: 'Completion deadline', max_charge_cents: 'Charge cap', grid_zone: 'Grid region',
};

const REASONS: Record<string, string> = {
  time_window: 'The deadline or deferral window is too short', budget: 'The charge cap is too small for the predicted runtime',
  grid_zone: 'The runner is in a different grid region', vram: 'The GPU has too little memory', runner_offline: 'The runner is offline or paused',
  gpu_count: 'The agreement asks for a GPU count the runner cannot offer', gpu_model: 'The GPU model does not match', rate: 'The GPU rate is above the approved limit',
  offer_paused: 'The producer paused this offer', offer_window: 'The offer window is too short', carbon_unknown: 'No current grid forecast is available for the emissions cap',
  carbon_limit: 'Estimated emissions exceed the cap', execution_unknown: 'An earlier attempt on this runner needs reconciliation',
};
export const reasonName = (code: string) => REASONS[code] ?? code.replace(/_/g, ' ');

// Mirrors the server: returns a copy with each edit applied (or added when the agreement has no such rule).
export function applyEdits(rules: RuleLike[], edits: Edit[]): RuleLike[] {
  const out = rules.map(rule => ({ ...rule }));
  for (const edit of edits) {
    const found = out.find(rule => rule.kind === edit.kind);
    if (found) { found.value = edit.value; found.strict = false; found.start = null; found.end = null; }
    else out.push({ kind: edit.kind, value: edit.value, start: null, end: null, rationale: 'Counterfactual edit.', strict: false });
  }
  return out;
}

export function changeLines(rules: RuleLike[], edits: Edit[]): string[] {
  return edits.map(edit => {
    const before = rules.find(rule => rule.kind === edit.kind)?.value;
    return `${KIND_NAMES[edit.kind]}: ${before === undefined ? 'not set' : String(before)} → ${String(edit.value)}`;
  });
}

export function verdict(option: Option): string {
  if (option.feasible) return 'Makes the job feasible';
  if (option.resolved_codes.length) return 'Fixes ' + option.resolved_codes.map(reasonName).join('; ').toLowerCase() + ', but is not enough';
  return 'Does not make the job feasible';
}
