import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { ArrowUpRight, Check, CircleAlert, Clock3, LoaderCircle } from 'lucide-react';

export type User = { username: string; organization: string; role: string };
export type Config = { llm_available: boolean; example_contract: string; database: string; model: string };
export type Rule = { kind: string; value: string | number | boolean; start: number | null; end: number | null; rationale: string | null; strict: boolean };
export type Issue = { id: string; code: string; message: string; start: number | null; end: number | null };
export type Policy = { id: string; title: string; status: string; method: string; created_at: number; rule_count: number; issue_count: number };
export type Agreement = Policy & { source: string; source_hash: string; rules: Rule[]; issues: Issue[]; approved_at: number | null; parent_id: string | null };
export type Runner = { id: string; name: string; device: string; vram_mib: number; zone: string | null; rate_cents: number; last_seen: number; online: boolean; ready: boolean; paused: boolean };
export type Reason = { code: string; message: string; rule: string | null };
export type Candidate = { runner_name: string; runner_id: string; start: number; reserved_until: number; quote_cents: number; envelope_cents: number; runtime_s: number; device: string; estimated_carbon_g: number | null; reasons: Reason[] };
export type Preview = { selected: Candidate | null; candidates: Candidate[]; deadline_at: number };
export type Job = { id: string; title: string; policy_id: string; status: string; mode: 'live' | 'shadow'; created_at: number; deadline_at: number; sample_count: number; cancel_requested: boolean };
export type LogEvent = { seq: number; at: number; kind: string; details: Record<string, unknown> };
export type Review = { id: string; finding_id: string; disposition: string; note: string; at: number };
export type AttemptResult = { duration_s: number; gpu_energy_kwh: number | null; device: string; power_samples: number; telemetry_coverage: number; artifact_id?: string; sha256?: string; rows?: number; model?: string; inference_seconds?: number; charged_cents: number; message?: string };
export type Finding = { id: string; rule: string; status: string; observed: unknown; expected: unknown; source_span?: [number, number]; evidence: number[] };
export type JobDetail = Job & { decision: Partial<Candidate> & { candidates: Candidate[] }; policy: Agreement; input_sha256: string | null; events: LogEvent[]; findings: Finding[]; reviews: Review[]; attempts: { id: string; status: string; result: AttemptResult | null }[] };
export type Dataset = { id: string; pods: number; gpu_pods: number; gpu_nodes: number; gpu_devices: number; runtime_proxies: number; carbon_intervals: number; carbon_range: number[]; carbon_zone: string; sources: { file: string; url: string; sha256: string }[]; origins: Record<string, string> };
export type Run = { id: string; title: string; created_at: number; status: string; progress: number; jobs: number; seeds: number };
export type Transition = { from: string; to: string; action: string; count: number; rounds: number[] };
export type Auditor = { provider: string; status: string; states: string[]; transitions: Transition[]; heldout_accuracy: number | null; heldout_coverage: number; exposures: number; matched_controls: number; summary: string; motifs: { undercut_response_round: number; recovery_round: number }[] };
export type Round = { round: number; pressure: number; capacity: number; demand: number; offers: { provider: string; price: number; gpu_model: string }[] };
export type TimelinePoint = { round: number; queued: number; started: number; forecast: number; actual: number; solver: string };
export type Placement = { job: string; provider: string; start: number; finish: number; arrival: number; status: string; violations: string[]; carbon_g: number; charge: number };
export type Metrics = Record<string, number | null>;
export type RunResult = {
  dataset: string; engine: string; summary: Record<string, Metrics>; assumptions: string[];
  paired: Record<string, { delta: number; pairs: number; interval95: [number, number] | null }>;
  audit_metrics: Metrics;
  first_episode: { seed: number; carbon_anchor: number; offers: Round[]; timeline: TimelinePoint[]; placements: Placement[]; audits: Auditor[]; mapping: Record<string, unknown> };
};
export type RunDetail = Run & { artifact_id: string | null; error: string | null; result: RunResult | null; reviews: Review[]; config: { scenario: Record<string, unknown> }; events: LogEvent[] };

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  const response = await fetch('/api/v1' + path, { ...options, headers });
  if (!response.ok) {
    const failure = await response.json().catch(() => ({}));
    throw new Error(typeof failure.detail === 'string' ? failure.detail : Array.isArray(failure.detail)
      ? failure.detail.map((entry: { msg: string }) => entry.msg).join(' · ')
      : 'Request failed (' + response.status + ').');
  }
  return response.json() as Promise<T>;
}

export function post<T>(path: string, body?: unknown, headers?: HeadersInit): Promise<T> {
  return api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body), headers });
}

export function message(error: unknown) {
  return error instanceof Error ? error.message : 'The request could not be completed.';
}

export function go(path: string) {
  location.hash = path;
}

export const statusLabels: Record<string, string> = {
  succeeded: 'Succeeded', recommended: 'Shadow recommendation', rejected: 'Rejected',
  execution_unknown: 'Needs reconciliation', insufficient_evidence: 'Insufficient evidence',
  policy_only: 'Policy only', carbon_aware: 'Carbon-aware', unconstrained: 'Policy ablation',
  fcfs: 'First come', edf: 'Earliest deadline',
};
export function label(value: string) {
  return statusLabels[value] ?? value.replaceAll('_', ' ').replace(/^./, character => character.toUpperCase());
}

export function date(value: number | null | undefined) {
  return value ? new Date(value * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
}

export function num(value: number | null | undefined, digits = 1) {
  return value == null ? '—' : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

export function pct(value: number | null | undefined) {
  return value == null ? '—' : num(value * 100, 1) + '%';
}

export function countLabel(count: number, item: string) {
  return count + ' ' + item + (count === 1 ? '' : 's');
}

export function money(value: number | null | undefined) {
  return value == null ? '—' : (value / 100).toFixed(2) + ' cr';
}

export function evidence(source: string, start: number | null | undefined, end: number | null | undefined) {
  return start == null || end == null ? '' : Array.from(source).slice(start, end).join('');
}

export const active = ['reserved', 'dispatched', 'running', 'execution_unknown', 'queued'];

export function Status({ value }: { value: string }) {
  const tone = ['succeeded', 'completed', 'pass', 'approved', 'online', 'clear', 'available', 'ready'].includes(value) ? 'green'
    : ['failed', 'rejected', 'expired', 'fail'].includes(value) ? 'red'
    : ['running', 'reserved', 'review', 'execution_unknown', 'draft', 'queued', 'incomplete', 'quoted'].includes(value) ? 'gold' : 'slate';
  return <span className={'status ' + tone}><span />{label(value)}</span>;
}

export function Notice({ children, type = 'error' }: { children: ReactNode; type?: 'error' | 'info' | 'success' }) {
  const Icon = type === 'success' ? Check : type === 'info' ? Clock3 : CircleAlert;
  return <div role={type === 'error' ? 'alert' : 'status'} className={'notice ' + type}><Icon size={17} /><div>{children}</div></div>;
}

export function Loading() {
  return <div className="empty"><LoaderCircle className="spin" size={22} /> Loading workspace</div>;
}

export function Empty({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty">{icon}<strong>{title}</strong>{children && <p>{children}</p>}{action}</div>;
}

export function Panel({ title, subtitle, action, children, className = '' }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={'panel ' + className}>
    <div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
    {children}
  </section>;
}

export function Page({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode }) {
  return <><div className="page-title"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</>;
}

export function LinkButton({ to, children }: { to: string; children: ReactNode }) {
  return <a className="button secondary" href={'#' + to}>{children}<ArrowUpRight size={15} /></a>;
}

export function useDetail<T>(type: 'jobs' | 'runs' | 'policies', id: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const refresh = () => api<T>('/' + type + '/' + id).then(setData).catch(value => setError(message(value)));
  useEffect(() => {
    let current = true;
    const fetchDetail = () => api<T>('/' + type + '/' + id).then(value => {
      if (current) { setData(value); setError(''); }
    }).catch(value => { if (current) setError(message(value)); });
    setData(null);
    setError('');
    void fetchDetail();
    const timer = type === 'policies' ? undefined : window.setInterval(fetchDetail, 2200);
    return () => { current = false; if (timer) window.clearInterval(timer); };
  }, [type, id]);
  return { data, error, refresh, setData };
}

export function ReviewForm({ type, id, finding, reviews, refresh }: { type: 'jobs' | 'runs'; id: string; finding: string; reviews: Review[]; refresh: () => void }) {
  const [note, setNote] = useState('');
  const [disposition, setDisposition] = useState('needs_evidence');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await post('/' + type + '/' + id + '/reviews', { finding_id: finding, disposition, note });
      setNote('');
      refresh();
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <div className="review-box">
    {reviews.filter(row => row.finding_id === finding).map(row => <div className="review-entry" key={row.id}><Status value={row.disposition} /> <span>{row.note}</span><small>{date(row.at)}</small></div>)}
    <form className="form-grid" onSubmit={submit}>
      <label>Disposition<select value={disposition} onChange={event => setDisposition(event.target.value)}><option value="needs_evidence">Needs evidence</option><option value="confirmed">Confirmed</option><option value="dismissed">Dismissed</option></select></label>
      <label>Reviewer note<input value={note} onChange={event => setNote(event.target.value)} required minLength={5} maxLength={1200} /></label>
      <button className="button secondary" disabled={busy}>Record review</button>
    </form>
    {error && <Notice>{error}</Notice>}
  </div>;
}
