// Pure helpers for the operator incident queue (unit-tested with `node --test`).
export type Evidence = { type: 'event' | 'link'; seq?: number; kind?: string; href?: string; label?: string; at?: number };
export type Action = { id: string; label: string; executes?: boolean; api?: string };
export type Incident = {
  id: string; kind: string; title: string; status: 'open' | 'claimed' | 'resolved'; owner: string | null;
  subject: { type: string; id: string; label: string }; opened_at: number; summary: string;
  evidence: Evidence[]; permitted_actions: Action[]; resolution: string | null; outcome: string | null; resolved_at: number | null;
};

// Evidence links are app routes only. Anything else (for example from a future server bug) is dropped, never rendered as a link.
export function safeHref(href: string | undefined): string | null {
  return href && /^\/[A-Za-z0-9/_-]*$/.test(href) ? '#' + href : null;
}

export function evidenceText(item: Evidence): string {
  if (item.type === 'event') return `${item.kind ?? 'Event'} · evidence ${item.seq}`;
  return item.label ?? 'Open';
}

export const MIN_NOTE = 12;
export function noteProblem(note: string): string | null {
  const length = note.trim().length;
  return length >= MIN_NOTE ? null : `Record what you found and did in at least ${MIN_NOTE} characters (${length} so far).`;
}

// What the resolve button sends for an incident, from the action the operator chose.
export function resolveBody(incident: Incident, action: string, note: string) {
  const resolution = note.trim();
  if (incident.kind === 'adjustment_request') return { resolution, outcome: action };
  if (action === 'reconcile') return { resolution, action: 'reconcile' };
  return { resolution, action: 'none' };
}

export function canResolve(incident: Incident): string[] {
  return incident.status === 'resolved' ? [] : incident.permitted_actions
    .filter(action => action.id !== 'wait' && action.id !== 'pause_dispatch').map(action => action.id);
}
