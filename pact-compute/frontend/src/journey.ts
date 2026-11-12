// Pure journey logic (no React) so it can be unit-tested with `node --test`.
export type JourneyPolicy = { id: string; title: string; status: string; issue_count: number };
export type BookingRow = { id: string; title: string; offer: string; status: string; accepted_at: number; usage_cents: number | null };
export type Next = { title: string; detail: string; to: string; action: string };

export const ACTIVE = ['reserved', 'dispatched', 'running'];
const words = (value: string) => value.replace(/_/g, ' ');

// Exactly one clear next action, derived from where the consumer is in the journey.
export function nextAction(policies: JourneyPolicy[], bookings: BookingRow[]): Next {
  const approved = policies.filter(item => item.status === 'approved');
  const attention = bookings.find(item => item.status === 'execution_unknown');
  const active = bookings.find(item => ACTIVE.includes(item.status));
  if (attention) return { title: 'A booking needs your attention', detail: attention.title + ' lost contact with its GPU. Review the evidence before anything is released.', to: '/bookings/' + attention.id, action: 'Open booking' };
  if (active) return { title: 'Your reservation is in progress', detail: active.title + ' is ' + words(active.status) + '. Follow it step by step.', to: '/bookings/' + active.id, action: 'Follow booking' };
  if (!policies.length) return { title: 'Write your first service agreement', detail: 'An agreement states what your workload needs (GPU memory, deadline, maximum charge). It must be approved before you can book.', to: '/agreements', action: 'Create agreement' };
  if (!approved.length) {
    const blocked = policies.find(item => item.issue_count > 0);
    if (blocked) return { title: 'Resolve the findings in “' + blocked.title + '”', detail: blocked.issue_count + ' item' + (blocked.issue_count === 1 ? '' : 's') + ' need clarification before a reviewer can approve it.', to: '/agreements/' + blocked.id, action: 'Review findings' };
    return { title: 'Get your agreement approved', detail: 'A reviewer approves the limits before you can request a quote. Invite a colleague as reviewer, then ask them to approve “' + policies[0].title + '”.', to: '/team', action: 'Invite a reviewer' };
  }
  if (!bookings.length) return { title: 'Find a GPU for your workload', detail: 'Compare offers, request a quote under “' + approved[0].title + '” and confirm to reserve capacity.', to: '/market', action: 'Compare GPU offers' };
  return { title: 'Book more capacity', detail: 'Your last booking finished. Compare current offers to run another workload.', to: '/market', action: 'Compare GPU offers' };
}
