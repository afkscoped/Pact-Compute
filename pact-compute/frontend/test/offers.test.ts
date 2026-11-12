import assert from 'node:assert/strict';
import { test } from 'node:test';
import { bookingGuidance, offerBadges, sortOffers, type OfferLike } from '../src/offers.ts';

const offer = (id: string, rate: number, vram: number, at: number | null, available = true): OfferLike =>
  ({ id, rate_cents: rate, vram_mib: vram, available_at: at, available });
const a = offer('a', 300, 8192, 100), b = offer('b', 200, 6144, 300), c = offer('c', 250, 16384, 200), gone = offer('gone', 50, 99999, null, false);

test('sorting puts bookable offers first, then the chosen order', () => {
  assert.deepEqual(sortOffers([gone, a, b, c], 'rate').map(item => item.id), ['b', 'c', 'a', 'gone']);
  assert.deepEqual(sortOffers([gone, a, b, c], 'soonest').map(item => item.id), ['a', 'c', 'b', 'gone']);
  assert.deepEqual(sortOffers([gone, a, b, c], 'memory').map(item => item.id), ['c', 'a', 'b', 'gone']);
});
test('badges mark the best bookable offer per dimension and ignore unavailable ones', () => {
  const badges = offerBadges([gone, a, b, c]);
  assert.deepEqual(badges.b, ['Lowest rate']);
  assert.deepEqual(badges.a, ['Soonest start']);
  assert.deepEqual(badges.c, ['Most memory']);
  assert.equal(badges.gone, undefined);
});
test('ties share a badge and a single bookable offer gets none', () => {
  assert.deepEqual(offerBadges([offer('x', 100, 1, 5), offer('y', 100, 2, 6)]).y, ['Lowest rate', 'Most memory']);
  assert.deepEqual(offerBadges([a, gone]), {});
});
test('booking guidance is role-aware and flags uncertain execution', () => {
  assert.equal(bookingGuidance('execution_unknown', 'consumer').tone, 'error');
  assert.match(bookingGuidance('succeeded', 'consumer').detail, /download/i);
  assert.match(bookingGuidance('succeeded', 'producer').detail, /receipt/i);
  assert.equal(bookingGuidance('mystery_state', 'producer').headline, 'Mystery state');
});
