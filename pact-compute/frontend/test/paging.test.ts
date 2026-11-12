import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pagePath, walkPages, type Page } from '../src/paging.ts';

// A fake server: 7 rows, page size taken from the request, cursor = index of the next row.
const server = (rows: number[], seen: (string | null)[] = []) => async (cursor: string | null, size = 3): Promise<Page<number>> => {
  seen.push(cursor);
  const start = cursor ? Number(cursor) : 0;
  const items = rows.slice(start, start + size);
  return { items, next: start + size < rows.length ? String(start + size) : null };
};

test('pagePath adds limit and an encoded cursor, respecting existing queries', () => {
  assert.equal(pagePath('/jobs', null), '/jobs?limit=50');
  assert.equal(pagePath('/jobs', 'a b+c=='), '/jobs?limit=50&cursor=a%20b%2Bc%3D%3D');
  assert.equal(pagePath('/jobs?mode=live', null, 10), '/jobs?mode=live&limit=10');
});
test('walkPages stops at the requested page count and reports the next cursor', async () => {
  const result = await walkPages(server([1, 2, 3, 4, 5, 6, 7]), 2);
  assert.deepEqual(result.items, [1, 2, 3, 4, 5, 6]);
  assert.equal(result.next, '6');
  assert.equal(result.pages, 2);
});
test('walkPages stops early on the last page and always loads at least one', async () => {
  const result = await walkPages(server([1, 2, 3, 4]), 9);
  assert.deepEqual(result.items, [1, 2, 3, 4]);
  assert.equal(result.next, null);
  assert.equal(result.pages, 2);
  assert.equal((await walkPages(server([1, 2]), 0)).pages, 1);
});
test('a refresh re-walks from the start: dropped rows vanish and new rows appear without gaps', async () => {
  const seen: (string | null)[] = [];
  const before = await walkPages(server([10, 9, 8, 7, 6], seen), 2);
  assert.deepEqual(before.items, [10, 9, 8, 7, 6]);
  const after = await walkPages(server([11, 10, 9, 8, 7, 6], seen), 2); // one row arrived on top
  assert.deepEqual(after.items, [11, 10, 9, 8, 7, 6]);
  assert.deepEqual(seen.slice(2), [null, '3']);
});
test('errors propagate so callers can show a retry notice', async () => {
  await assert.rejects(walkPages(async () => { throw new Error('Request failed (502).'); }, 2), /502/);
});
