import assert from 'node:assert/strict';
import { test } from 'node:test';
import { reasonProblem, segments, valueText } from '../src/inbox.ts';

const source = 'Jobs need 4 GiB. Charge under 2 credits.';
test('segments highlight clauses and keep the text in between', () => {
  const parts = segments(source, [{ start: 0, end: 15 }, { start: 17, end: 39 }]);
  assert.deepEqual(parts.map(part => part.clause), [0, null, 1, null]);
  assert.equal(parts.map(part => part.text).join(''), source);
});
test('unsorted spans are sorted; overlapping, empty and out-of-range spans are ignored', () => {
  const parts = segments(source, [{ start: 17, end: 39 }, { start: 0, end: 15 }, { start: 5, end: 20 }, { start: null, end: null }, { start: 3, end: 3 }, { start: 30, end: 999 }]);
  assert.deepEqual(parts.filter(part => part.clause !== null).map(part => part.clause), [1, 0]);
  assert.equal(parts.map(part => part.text).join(''), source);
});
test('no clauses yields one plain segment', () => {
  assert.deepEqual(segments(source, []), [{ text: source, clause: null }]);
  assert.deepEqual(segments('', []), []);
});
test('a decision reason needs at least 12 characters', () => {
  assert.match(reasonProblem('short') ?? '', /5 so far/);
  assert.equal(reasonProblem('  a proper reason  '), null);
});
test('values print plainly', () => {
  assert.equal(valueText(true), 'Yes');
  assert.equal(valueText(4096), '4096');
});
