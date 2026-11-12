import assert from 'node:assert/strict';
import { test } from 'node:test';
import { nextAction, type BookingRow, type JourneyPolicy } from '../src/journey.ts';

const policy = (over: Partial<JourneyPolicy> = {}): JourneyPolicy => ({ id: 'p1', title: 'Batch SLA', status: 'draft', issue_count: 0, ...over });
const booking = (status: string, id = 'b1'): BookingRow => ({ id, title: 'Embedding run', offer: 'Offer', status, accepted_at: 1, usage_cents: null });

test('no agreement: create one', () => {
  assert.equal(nextAction([], []).to, '/agreements');
});
test('draft with findings: resolve them', () => {
  const next = nextAction([policy({ issue_count: 2 })], []);
  assert.equal(next.to, '/agreements/p1');
  assert.match(next.detail, /2 items/);
});
test('clean draft: invite a reviewer', () => {
  assert.equal(nextAction([policy()], []).to, '/team');
});
test('approved and no bookings: compare offers', () => {
  assert.equal(nextAction([policy({ status: 'approved' })], []).to, '/market');
});
test('active booking takes priority over everything else', () => {
  assert.equal(nextAction([], [booking('running')]).to, '/bookings/b1');
  assert.equal(nextAction([policy({ status: 'approved' })], [booking('succeeded', 'old'), booking('reserved', 'live')]).to, '/bookings/live');
});
test('uncertain execution outranks an active one', () => {
  assert.equal(nextAction([], [booking('running', 'a'), booking('execution_unknown', 'b')]).to, '/bookings/b');
});
test('finished booking: book again', () => {
  const next = nextAction([policy({ status: 'approved' })], [booking('succeeded')]);
  assert.equal(next.to, '/market');
  assert.equal(next.title, 'Book more capacity');
});
