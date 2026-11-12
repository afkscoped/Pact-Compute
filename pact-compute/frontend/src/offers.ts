// Pure helpers for comparing offers and explaining bookings (unit-tested with `node --test`).
export type OfferLike = { id: string; rate_cents: number; vram_mib: number; available: boolean; available_at: number | null };
export type SortKey = 'soonest' | 'rate' | 'memory';

export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'soonest', label: 'Soonest start' }, { key: 'rate', label: 'Lowest hourly rate' }, { key: 'memory', label: 'Most GPU memory' },
];

const start = (offer: OfferLike) => offer.available_at ?? Number.POSITIVE_INFINITY;

export function sortOffers<T extends OfferLike>(offers: T[], key: SortKey): T[] {
  const order: Record<SortKey, (a: T, b: T) => number> = {
    soonest: (a, b) => start(a) - start(b) || a.rate_cents - b.rate_cents,
    rate: (a, b) => a.rate_cents - b.rate_cents || start(a) - start(b),
    memory: (a, b) => b.vram_mib - a.vram_mib || a.rate_cents - b.rate_cents,
  };
  // Bookable offers first, then the chosen order.
  return [...offers].sort((a, b) => Number(b.available) - Number(a.available) || order[key](a, b));
}

// Which bookable offer is best on each dimension; ties share the badge. Needs 2+ bookable offers to be meaningful.
export function offerBadges(offers: OfferLike[]): Record<string, string[]> {
  const bookable = offers.filter(item => item.available);
  const badges: Record<string, string[]> = {};
  if (bookable.length < 2) return badges;
  const award = (text: string, best: number, value: (item: OfferLike) => number) => {
    for (const item of bookable) if (value(item) === best) (badges[item.id] ??= []).push(text);
  };
  award('Lowest rate', Math.min(...bookable.map(item => item.rate_cents)), item => item.rate_cents);
  award('Soonest start', Math.min(...bookable.map(start)), start);
  award('Most memory', Math.max(...bookable.map(item => item.vram_mib)), item => item.vram_mib);
  return badges;
}

export type Guidance = { headline: string; detail: string; tone: 'info' | 'success' | 'error' };

export function bookingGuidance(status: string, party: 'consumer' | 'producer'): Guidance {
  const buyer = party === 'consumer';
  switch (status) {
    case 'reserved':
      return { headline: 'Reserved', tone: 'info', detail: buyer ? 'Capacity is held for you. The GPU will pick up your job at the reserved start time; nothing is needed from you.' : 'A consumer has reserved your capacity. Keep the runner online and its listing unchanged until it finishes.' };
    case 'dispatched': case 'running':
      return { headline: 'Running now', tone: 'info', detail: 'The runner holds an execution lease and is working. This page updates automatically.' };
    case 'succeeded':
      return { headline: 'Completed', tone: 'success', detail: buyer ? 'Your results are ready. Open the job evidence to download the embeddings; the receipt records the usage charged.' : 'The workload finished and capacity was released. Download the shared receipt for the delivered usage.' };
    case 'execution_unknown':
      return { headline: 'Needs attention', tone: 'error', detail: 'Contact with the runner was lost, so the outcome is uncertain. Capacity stays held until the runner reports back or an operator reconciles it. Open the protocol below to see the last evidence.' };
    case 'failed':
      return { headline: 'Failed', tone: 'error', detail: 'Execution did not complete. Capacity was released. Check the job evidence for the reason, then request a new quote.' };
    case 'cancelled': case 'canceled':
      return { headline: 'Cancelled', tone: 'info', detail: 'The booking was cancelled and capacity was released. Any usage before cancellation is on the receipt.' };
    case 'expired': case 'interrupted':
      return { headline: label(status), tone: 'error', detail: 'The reservation ended before the work finished. Capacity was released; request a new quote to run it again.' };
    default:
      return { headline: label(status), tone: 'info', detail: 'Follow the protocol below for the evidence behind this status.' };
  }
}

function label(value: string) {
  const text = value.replace(/_/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}
