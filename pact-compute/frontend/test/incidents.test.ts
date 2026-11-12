import assert from 'node:assert/strict';
import { test } from 'node:test';
import { canResolve, evidenceText, noteProblem, resolveBody, safeHref, type Incident } from '../src/incidents.ts';

const base: Incident = {
  id: 'inc-1', kind: 'uncertain_attempt', title: 't', status: 'open', owner: null, subject: { type: 'job', id: 'j', label: 'J' },
  opened_at: 1, summary: 's', evidence: [], resolution: null, outcome: null, resolved_at: null,
  permitted_actions: [{ id: 'reconcile', label: 'Reconcile', executes: true }],
};
test('only app routes become evidence links', () => {
  assert.equal(safeHref('/jobs/abc123'), '#/jobs/abc123');
  assert.equal(safeHref('/bookings/x-1'), '#/bookings/x-1');
  for (const bad of ['https://evil.example/x', '//evil.example', 'javascript:alert(1)', '/jobs/../x?y=1', '', undefined]) assert.equal(safeHref(bad), null);
});
test('evidence text names the event and its sequence', () => {
  assert.equal(evidenceText({ type: 'event', seq: 42, kind: 'ExecutionUncertain' }), 'ExecutionUncertain · evidence 42');
  assert.equal(evidenceText({ type: 'link', href: '/capacity', label: 'Compute capacity' }), 'Compute capacity');
});
test('a recorded resolution needs a real note', () => {
  assert.match(noteProblem('short') ?? '', /5 so far/);
  assert.equal(noteProblem('  Process confirmed stopped.  '), null);
});
test('resolve bodies match the server contract per incident kind', () => {
  assert.deepEqual(resolveBody(base, 'reconcile', ' done and checked '), { resolution: 'done and checked', action: 'reconcile' });
  assert.deepEqual(resolveBody({ ...base, kind: 'adjustment_request' }, 'declined', 'reviewed the receipt'), { resolution: 'reviewed the receipt', outcome: 'declined' });
  assert.deepEqual(resolveBody({ ...base, kind: 'stale_runner' }, 'note', 'host rebooted ok'), { resolution: 'host rebooted ok', action: 'none' });
});
test('resolvable actions exclude waiting, links and finished incidents', () => {
  assert.deepEqual(canResolve(base), ['reconcile']);
  assert.deepEqual(canResolve({ ...base, permitted_actions: [{ id: 'wait', label: 'w' }] }), []);
  assert.deepEqual(canResolve({ ...base, kind: 'stale_runner', permitted_actions: [{ id: 'pause_dispatch', label: 'p' }, { id: 'note', label: 'n' }] }), ['note']);
  assert.deepEqual(canResolve({ ...base, status: 'resolved' }), []);
});
