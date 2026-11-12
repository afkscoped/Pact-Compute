import assert from 'node:assert/strict';
import { test } from 'node:test';
import { applyEdits, changeLines, reasonName, verdict, type Option } from '../src/counterfactual.ts';

const rules = [{ kind: 'deadline_seconds', value: 20, start: 5, end: 30, rationale: null, strict: true },
               { kind: 'min_vram_mib', value: 4096, start: 0, end: 4, rationale: null, strict: false }];
test('applying edits copies rules, replaces existing values and adds missing ones', () => {
  const next = applyEdits(rules, [{ kind: 'deadline_seconds', value: 80 }, { kind: 'grid_zone', value: 'GB' }]);
  assert.equal(next.find(r => r.kind === 'deadline_seconds')?.value, 80);
  assert.equal(next.find(r => r.kind === 'deadline_seconds')?.strict, false);
  assert.equal(next.find(r => r.kind === 'grid_zone')?.value, 'GB');
  assert.equal(rules[0].value, 20);
  assert.equal(rules.length, 2);
});
test('change lines show before and after', () => {
  assert.deepEqual(changeLines(rules, [{ kind: 'deadline_seconds', value: 80 }, { kind: 'grid_zone', value: 'GB' }]),
    ['Completion deadline: 20 → 80', 'Grid region: not set → GB']);
});
test('reason codes get plain wording and unknown codes degrade gracefully', () => {
  assert.match(reasonName('time_window'), /deadline/);
  assert.equal(reasonName('new_code_x'), 'new code x');
});
test('verdicts distinguish feasible, partial and useless options', () => {
  const base: Option = { edits: [], label: '', feasible: false, blocking_codes: ['time_window'], resolved_codes: [], new_codes: [], selected: null };
  assert.equal(verdict({ ...base, feasible: true }), 'Makes the job feasible');
  assert.match(verdict({ ...base, resolved_codes: ['grid_zone'] }), /not enough/);
  assert.equal(verdict(base), 'Does not make the job feasible');
});
