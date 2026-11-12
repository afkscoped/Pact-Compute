// Pure paging helpers (no React) so they can be unit-tested with `node --test`.
export const PAGE_SIZE = 50;
export type Page<T> = { items: T[]; next: string | null };

export function pagePath(path: string, cursor: string | null, size = PAGE_SIZE): string {
  return path + (path.includes('?') ? '&' : '?') + 'limit=' + size + (cursor ? '&cursor=' + encodeURIComponent(cursor) : '');
}

// Re-walk `count` pages from the start. Refreshing this way never leaves a gap when new rows arrive
// and drops rows that disappeared (for example expired offers), unlike appending to stale pages.
export async function walkPages<T>(load: (cursor: string | null) => Promise<Page<T>>, count: number): Promise<Page<T> & { pages: number }> {
  const items: T[] = [];
  let cursor: string | null = null;
  let pages = 0;
  while (pages < Math.max(1, count)) {
    const page: Page<T> = await load(cursor);
    items.push(...page.items);
    pages += 1;
    cursor = page.next;
    if (!cursor) break;
  }
  return { items, next: cursor, pages };
}
