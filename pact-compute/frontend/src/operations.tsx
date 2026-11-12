import { useEffect, useState, type FormEvent } from 'react';
import { reasonProblem, segments, valueText } from './inbox';
import { specRows, stageRows } from './stages';
import { applyEdits, changeLines, reasonName, verdict, type Counterfactual, type Option } from './counterfactual';
import { Activity, ArrowRight, CheckCircle2, ChevronRight, ClipboardCheck, Cpu, Download, FileText, FlaskConical, Layers3, Plus, Radio, ShieldCheck, UploadCloud } from 'lucide-react';
import {
  active, api, countLabel, date, Empty, evidence, go, label, LinkButton, LoadMore, Loading, message, money, Notice, num, Page, Panel, pct, post, ReviewForm, RetryNotice, Status, useDetail, usePagedList,
  type Agreement, type Candidate, type Config, type InboxItem, type Job, type JobDetail, type Policy, type Preview, type Rule, type Run, type Runner, type User,
} from './shared';

type Lists = { jobs: Job[]; runners: Runner[]; policies: Policy[]; runs: Run[] };

export function Overview({ jobs, runners, policies, runs }: Lists) {
  const online = runners.filter(runner => runner.online).length;
  const completed = jobs.filter(job => job.status === 'succeeded').length;
  const approved = policies.filter(policy => policy.status === 'approved').length;
  return <Page title="Operations overview" subtitle="Monitor GPU work, approved agreements, and reproducible experiments."
    action={<a className="button primary" href="#/jobs/new"><Plus size={17} /> Submit job</a>}>
    <div className="metrics-grid">
      <Metric name="GPU runners online" value={String(online)} detail={runners.length + ' enrolled'} icon={<Cpu size={18} />} />
      <Metric name="Active reservations" value={String(jobs.filter(job => active.includes(job.status)).length)} detail="Queued or executing" icon={<Activity size={18} />} />
      <Metric name="GPU jobs completed" value={String(completed)} detail="Verified output artifacts" icon={<CheckCircle2 size={18} />} />
      <Metric name="Approved agreements" value={String(approved)} detail={countLabel(policies.length, 'revision')} icon={<ShieldCheck size={18} />} />
    </div>
    <div className="overview-grid">
      <Panel title="Recent jobs" subtitle="Admission, execution, and audit status" action={<LinkButton to="/jobs">Open queue</LinkButton>}>
        <JobsTable jobs={jobs.slice(0, 6)} />
      </Panel>
      <Panel title="Compute capacity" subtitle="Enrolled execution infrastructure" action={<Cpu size={19} className="muted" />}>
        {runners.length ? runners.map(runner => <div className="runner-card" key={runner.id}>
          <div className="split"><div className="runner-icon"><Cpu size={22} /></div><Status value={runner.online ? 'online' : runner.paused ? 'paused' : 'offline'} /></div>
          <h3>{runner.name}</h3><p>{runner.device}</p>
          <div className="stats-inline"><div><small>GPU memory</small><strong>{num(runner.vram_mib / 1024)} GiB</strong></div><div><small>Grid zone</small><strong>{runner.zone ?? 'Unconfigured'}</strong></div></div>
        </div>) : <Empty title="No runner enrolled" icon={<Cpu size={25} />}>Start the local GPU runner to enable dispatch.</Empty>}
        <a className="text-link" href="#/capacity">Manage capacity <ArrowRight size={15} /></a>
      </Panel>
    </div>
    <div className="overview-grid">
      <Panel title="Latest experiments" subtitle="Paired scheduler comparisons" action={<LinkButton to="/research">Research Lab</LinkButton>}>
        {runs.length ? <div className="rows">{runs.slice(0, 4).map(run => <a className="list-row" key={run.id} href={'#/research/' + run.id}>
          <div className="row-icon"><FlaskConical size={18} /></div><div className="grow"><strong>{run.title}</strong><small>{run.jobs} jobs per seed · {countLabel(run.seeds, 'seed')}</small></div><Status value={run.status} /><ChevronRight size={17} />
        </a>)}</div> : <Empty title="Run the workload replay" icon={<FlaskConical size={24} />}>Compare baseline schedulers on the imported trace and grid history.</Empty>}
      </Panel>
      <Panel title="Policy approval" subtitle="Review clauses before dispatch" action={<ClipboardCheck size={20} className="muted" />}>
        <div className="rows">{policies.slice(0, 4).map(policy => <a className="list-row" key={policy.id} href={'#/agreements/' + policy.id}>
          <div className="row-icon"><FileText size={18} /></div><div className="grow"><strong>{policy.title}</strong><small>{countLabel(policy.rule_count, 'rule')}</small></div><Status value={policy.status} />
        </a>)}</div>
        {!policies.length && <Empty title="Create an agreement" icon={<FileText size={23} />}>Extract the clauses, confirm the evidence, and approve a version.</Empty>}
        <a className="text-link" href="#/agreements">Open agreements <ArrowRight size={15} /></a>
      </Panel>
    </div>
  </Page>;
}

export function Metric({ name, value, detail, icon }: { name: string; value: string; detail: string; icon?: React.ReactNode }) {
  return <div className="metric"><div className="split"><span>{name}</span>{icon && <div className="metric-icon">{icon}</div>}</div><strong>{value}</strong><small>{detail}</small></div>;
}

export function JobsTable({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return <Empty icon={<Layers3 size={25} />} title="No jobs yet">Submit a batch with an approved agreement to populate the queue.</Empty>;
  return <div className="table-wrap"><table><thead><tr><th>Job</th><th>Mode</th><th>Status</th><th>Submitted</th><th aria-label="Open job" /></tr></thead>
    <tbody>{jobs.map(job => <tr key={job.id}><td><a className="table-link" href={'#/jobs/' + job.id}>{job.title}</a><small>{job.sample_count} images</small></td>
      <td>{label(job.mode)}</td><td><Status value={job.status} /></td><td>{date(job.created_at)}</td><td><a className="icon-link" href={'#/jobs/' + job.id} aria-label={'Open ' + job.title}><ChevronRight size={17} /></a></td></tr>)}</tbody></table></div>;
}

export function Queue({ exchange = false }: { exchange?: boolean }) {
  const [filter, setFilter] = useState('all');
  const list = usePagedList<Job>('/jobs', 4200);
  const jobs = list.items ?? [];
  return <Page title="Job queue" subtitle="Follow submitted workloads from admission through execution."
    action={<a className="button primary" href={exchange ? '#/market' : '#/jobs/new'}><Plus size={17} />{exchange ? 'Find GPU' : 'Submit job'}</a>}>
    <Panel title="Submissions" action={<select aria-label="Filter jobs" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All modes</option><option value="live">Live</option><option value="shadow">Shadow</option></select>}>
      {list.error && <RetryNotice onRetry={() => void list.refresh()}>{list.error}</RetryNotice>}
      {list.items === null && !list.error ? <Loading label="Loading jobs" /> : <JobsTable jobs={jobs.filter(job => filter === 'all' || job.mode === filter)} />}
      {list.items && <LoadMore shown={jobs.length} hasMore={list.hasMore} loading={list.loadingMore} onMore={() => void list.more()} noun="jobs" />}
    </Panel>
  </Page>;
}

const kinds: Record<string, string> = {
  min_vram_mib: 'Minimum GPU memory (MiB)', gpu_count: 'GPU count', gpu_model: 'GPU model', grid_zone: 'Grid zone',
  deadline_seconds: 'Completion deadline (seconds)', deadline_utc: 'Absolute deadline (UTC Unix seconds)',
  max_deferral_seconds: 'Maximum deferral (seconds)', max_charge_cents: 'Total charge cap (credit cents)',
  max_rate_cents: 'GPU-hour rate cap (credit cents)', carbon_limit_g: 'Estimated emissions cap (g CO₂)',
  prefer_low_carbon: 'Prefer lower carbon', report_required: 'Energy reporting',
};

function defaultValue(kind: string) {
  if (kind === 'gpu_model' || kind === 'grid_zone') return '';
  return ['prefer_low_carbon', 'report_required'].includes(kind) ? true : 0;
}

function InboxCard({ item, onDecided }: { item: InboxItem; onDecided: () => void }) {
  const [note, setNote] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const problem = rejecting ? reasonProblem(note) : null;
  async function decide(action: 'approve' | 'reject') {
    setBusy(true); setError('');
    try {
      await post<Agreement>('/policies/' + item.id + '/' + action, action === 'approve' ? { note: note.trim() || null } : { reason: note.trim() });
      onDecided();
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <article className="rule-card" aria-label={'Review ' + item.title}>
    <div className="split"><strong>{item.title}</strong><Status value={item.status} /></div>
    <small>{countLabel(item.rule_count, 'rule')} · {countLabel(item.issue_count, 'open finding')}{item.revision_of ? ' · revision of ' + item.revision_of.slice(0, 10) : ''}</small>
    <h4>Clause text</h4>
    <pre className="source-text">{segments(item.source, item.clauses).map((part, index) => part.clause === null
      ? <span key={index}>{part.text}</span> : <mark key={index} title={'Rule ' + (part.clause + 1)}>{part.text}</mark>)}</pre>
    <h4>Parsed values</h4>
    {item.clauses.length ? <ul>{item.clauses.map((clause, index) => <li key={index}>
      <strong>{kinds[clause.kind] ?? label(clause.kind)}</strong>: <code>{clause.strict ? '< ' : ''}{valueText(clause.value)}</code>
      {clause.text ? <small> from “{clause.text}”</small> : <small> (no source span)</small>}</li>)}</ul> : <p className="muted">No rules were extracted.</p>}
    <h4>Unresolved issues</h4>
    {item.issues.length ? item.issues.map(issue => <Notice key={issue.id} type="info"><strong>{label(issue.code)}</strong><p>{issue.message}</p>
      {evidence(item.source, issue.start, issue.end) && <blockquote>{evidence(item.source, issue.start, issue.end)}</blockquote>}</Notice>)
      : <p className="muted">None. This version can be approved.</p>}
    <h4>Affected future jobs</h4>
    {item.affected_jobs.length ? <ul>{item.affected_jobs.map(job => <li key={job.id}><a href={'#/jobs/' + job.id}>{job.title}</a> <small>{label(job.status)} · booked under an earlier version</small></li>)}</ul>
      : <p className="muted">No reserved jobs are booked under an earlier version of this agreement.</p>}
    {error && <Notice>{error}</Notice>}
    <label>{rejecting ? 'Reason for rejection (required)' : 'Approval note (optional)'}
      <input value={note} maxLength={500} onChange={event => setNote(event.target.value)} aria-invalid={!!problem} /></label>
    {problem && <small role="status">{problem}</small>}
    <div className="button-row">
      <button className="button primary" disabled={busy || !item.can_approve || rejecting} onClick={() => void decide('approve')}><ShieldCheck size={17} />Approve</button>
      {rejecting
        ? <button className="button secondary" disabled={busy || !!problem} onClick={() => void decide('reject')}>Confirm rejection</button>
        : <button className="button secondary" disabled={busy} onClick={() => { setRejecting(true); setNote(''); }}>Reject…</button>}
      {rejecting && <button className="button ghost" onClick={() => { setRejecting(false); setNote(''); }}>Cancel</button>}
      <LinkButton to={'/agreements/' + item.id}>Open</LinkButton>
    </div>
    {!item.can_approve && <small>Approval is unavailable until every finding is resolved in a revision.</small>}
  </article>;
}

function ReviewInbox({ onChange }: { onChange: () => void }) {
  const [items, setItems] = useState<InboxItem[] | null>(null);
  const [error, setError] = useState('');
  const load = () => api<InboxItem[]>('/policies/inbox').then(rows => { setItems(rows); setError(''); }).catch(failure => setError(message(failure)));
  useEffect(() => { void load(); }, []);
  return <Panel title="Review queue" subtitle="Draft agreements awaiting a decision, oldest first.">
    {error && <RetryNotice onRetry={() => void load()}>{error}</RetryNotice>}
    {items === null && !error && <Loading label="Loading review queue" />}
    {items?.length === 0 && <Empty title="Nothing to review" icon={<ClipboardCheck size={24} />}>New drafts appear here for a reviewer to approve or reject.</Empty>}
    <div className="stack">{items?.map(item => <InboxCard key={item.id} item={item} onDecided={() => { onChange(); void load(); }} />)}</div>
  </Panel>;
}

export function Agreements({ policies, config, onChange, canReview = false }: { policies: Policy[]; config: Config; onChange: () => void; canReview?: boolean }) {
  const [title, setTitle] = useState('');
  const [source, setSource] = useState('');
  const [method, setMethod] = useState('local');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function extract(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const draft = await post<Agreement>('/policies', { title, source, method });
      onChange(); go('/agreements/' + draft.id);
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <Page title="Agreements" subtitle="Turn service terms into versioned rules with source evidence.">
    {canReview && <ReviewInbox onChange={onChange} />}
    <div className="content-grid">
      <Panel title="New agreement" subtitle="Use one clause per line for the deterministic compiler.">
        <form className="stack" onSubmit={extract}>
          <label>Agreement name<input value={title} onChange={event => setTitle(event.target.value)} minLength={2} maxLength={120} required placeholder="Batch inference SLA" /></label>
          <label>Service agreement<textarea value={source} onChange={event => setSource(event.target.value)} rows={10} required maxLength={16000} placeholder="Jobs require at least 4 GiB VRAM." /></label>
          {config.llm_available && <label>Extraction method<select value={method} onChange={event => setMethod(event.target.value)}><option value="local">Local compiler</option><option value="llm">Configured model provider</option></select></label>}
          {method === 'llm' && <Notice type="info">Extraction sends this agreement to the configured provider. Submit only text you are authorized to share.</Notice>}
          {error && <Notice>{error}</Notice>}
          <div className="button-row"><button className="button primary" disabled={busy}><ClipboardCheck size={17} />{busy ? 'Extracting…' : 'Extract rules'}</button>
            <button type="button" className="button secondary" onClick={() => { setTitle('Image embedding SLA'); setSource(config.example_contract); }}>Load example</button></div>
        </form>
      </Panel>
      <Panel title="Policy versions" subtitle="Approved versions are pinned to each job.">
        {policies.length ? <div className="rows">{policies.map(policy => <a className="list-row" key={policy.id} href={'#/agreements/' + policy.id}>
          <div className="row-icon"><FileText size={18} /></div><div className="grow"><strong>{policy.title}</strong><small>{policy.rule_count} rules · {policy.issue_count} findings</small></div>
          <Status value={policy.status} /><ChevronRight size={15} />
        </a>)}</div> : <Empty title="No policy versions" icon={<ShieldCheck size={25} />}>Extract rules from a new agreement to create a draft.</Empty>}
      </Panel>
    </div>
  </Page>;
}

export function AgreementView({ id, onChange }: { id: string; onChange: () => void }) {
  const { data, error, setData } = useDetail<Agreement>('policies', id);
  const [draft, setDraft] = useState<Rule[] | null>(null);
  const [resolutions, setResolutions] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setDraft(null); setResolutions({}); setFeedback(''); }, [id]);
  if (error) return <Notice>{error}</Notice>;
  if (!data) return <Loading />;
  const policy = data;
  async function update() {
    setFeedback(''); setBusy(true);
    try {
      if (draft) {
        const version = await post<Agreement>('/policies/' + id + '/revisions', { rules: draft, resolutions });
        go('/agreements/' + version.id);
      } else setData(await post<Agreement>('/policies/' + id + '/approve'));
      onChange();
    } catch (failure) { setFeedback(message(failure)); }
    finally { setBusy(false); }
  }
  const edit = (index: number, fields: Partial<Rule>) => setDraft(current => current?.map((rule, i) => i === index ? { ...rule, ...fields } : rule) ?? null);
  return <Page title={policy.title} subtitle={'Policy ' + policy.id.slice(0, 10) + ' · ' + policy.method}
    action={<LinkButton to="/agreements">All agreements</LinkButton>}>
    <div className="content-grid">
      <Panel title="Original agreement" action={<Status value={policy.status} />}>
        <pre className="source-text">{policy.source}</pre>
        <div className="hash"><small>Source SHA-256</small><code>{policy.source_hash}</code></div>
      </Panel>
      <Panel title="Rule review" subtitle={policy.issues.length ? 'Resolve findings before approval.' : policy.rule_count + ' source-linked rules'}>
        {feedback && <Notice>{feedback}</Notice>}
        {policy.issues.map(issue => <Notice key={issue.id} type="info">
          <strong>{label(issue.code)}</strong><p>{issue.message}</p>
          {evidence(policy.source, issue.start, issue.end) && <blockquote>{evidence(policy.source, issue.start, issue.end)}</blockquote>}
          {draft && <label>Resolution or reviewer disposition<input value={resolutions[issue.id] ?? ''} onChange={event => setResolutions(old => ({ ...old, [issue.id]: event.target.value }))} /></label>}
        </Notice>)}
        <div className="stack">
          {(draft ?? policy.rules).map((rule, index) => <article className="rule-card" key={index}>
            {draft ? <div className="form-grid">
              <label>Rule type<select value={rule.kind} onChange={event => edit(index, { kind: event.target.value, value: defaultValue(event.target.value), start: null, end: null, strict: false })}>
                {Object.entries(kinds).map(([kind, name]) => <option key={kind} value={kind}>{name}</option>)}
              </select></label>
              {typeof rule.value !== 'boolean' && <label>Normalized value<input type={typeof rule.value === 'number' ? 'number' : 'text'} value={rule.value} onChange={event => edit(index, { value: typeof rule.value === 'number' ? Number(event.target.value) : event.target.value })} /></label>}
              <label className="wide">Reviewer rationale<input value={rule.rationale ?? ''} onChange={event => edit(index, { rationale: event.target.value })} /></label>
              <button className="button ghost" onClick={() => setDraft(draft.filter((_, i) => i !== index))}>Remove rule</button>
            </div> : <div className="split"><strong>{kinds[rule.kind] ?? label(rule.kind)}</strong><code>{rule.strict ? '< ' : ''}{String(rule.value)}</code></div>}
            {evidence(policy.source, rule.start, rule.end) && <blockquote>{evidence(policy.source, rule.start, rule.end)}</blockquote>}
            {rule.rationale && !draft && <p className="muted">{rule.rationale}</p>}
          </article>)}
        </div>
        <div className="button-row">
          {draft ? <>
            <button className="button primary" disabled={busy || !draft.length} onClick={update}>Save new revision</button>
            <button className="button secondary" onClick={() => setDraft([...draft, { kind: 'min_vram_mib', value: 1024, start: null, end: null, rationale: '', strict: false }])}>Add rule</button>
            <button className="button ghost" onClick={() => setDraft(null)}>Cancel edits</button>
          </> : <>
            {policy.status === 'draft' && <button className="button primary" disabled={busy || policy.issue_count > 0} onClick={update}><ShieldCheck size={17} />Approve policy</button>}
            <button className="button secondary" onClick={() => setDraft(policy.rules.map(rule => ({ ...rule })))}>Revise rules</button>
            {policy.status === 'approved' && <LinkButton to="/jobs/new">Submit a job</LinkButton>}
          </>}
        </div>
      </Panel>
    </div>
  </Page>;
}

function CandidateView({ candidate }: { candidate: Candidate }) {
  return <article className="rule-card">
    <div className="split"><strong>{candidate.runner_name}</strong><Status value={candidate.reasons.length ? 'rejected' : 'eligible'} /></div>
    <div className="form-facts"><span>Start <b>{date(candidate.start)}</b></span><span>Estimate <b>{money(candidate.quote_cents)}</b></span>
      <span>Budget envelope <b>{money(candidate.envelope_cents)}</b></span><span>Forecast <b>{candidate.estimated_carbon_g == null ? 'Unavailable' : num(candidate.estimated_carbon_g, 3) + ' g CO₂'}</b></span></div>
    {candidate.reasons.length > 0 && <ul className="reason-list">{candidate.reasons.map(reason => <li key={reason.code}><strong>{reason.rule ? kinds[reason.rule] : label(reason.code)}</strong> {reason.message}</li>)}</ul>}
  </article>;
}

export async function encodeImage(file: File) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  return { name: file.name, content: btoa(binary) };
}

function WhatIf({ spec, policyId, canRevise, onChange, auto }: { spec: object; policyId: string; canRevise: boolean; onChange: () => void; auto: boolean }) {
  const [result, setResult] = useState<Counterfactual | null>(null);
  const [chosen, setChosen] = useState<Option | null>(null);
  const [rules, setRules] = useState<Agreement['rules'] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function explore() {
    setBusy(true); setError(''); setChosen(null);
    try { setResult(await post<Counterfactual>('/jobs/preview/counterfactual', { ...spec, suggest: true })); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  useEffect(() => { setResult(null); setChosen(null); if (auto) void explore(); }, [policyId, auto, JSON.stringify(spec)]);
  async function choose(option: Option) {
    setError('');
    try { setRules((await api<Agreement>('/policies/' + policyId)).rules); setChosen(option); } catch (failure) { setError(message(failure)); }
  }
  async function accept() {
    if (!chosen || !rules) return;
    setBusy(true); setError('');
    try {
      const version = await post<Agreement>('/policies/' + policyId + '/revisions', { rules: applyEdits(rules, chosen.edits), resolutions: {} });
      onChange(); go('/agreements/' + version.id);
    } catch (failure) { setError(message(failure)); setBusy(false); }
  }
  return <Panel title="What would make this feasible?" subtitle="Checks other deadlines, budgets and regions with the same rules engine. Nothing changes until you accept.">
    <div className="button-row"><button className="button secondary" type="button" disabled={busy || !policyId} onClick={() => void explore()}>{busy ? 'Checking…' : result ? 'Check again' : 'Explore changes'}</button></div>
    {error && <Notice>{error}</Notice>}
    {result && <>
      <small role="status">{result.baseline.feasible ? 'The current terms already work.' : 'Today blocked by: ' + (result.baseline.blocking_codes.map(reasonName).join('; ') || 'nothing recorded')}</small>
      {!result.options.length && <Empty title="No alternatives to test" icon={<Cpu size={22} />}>This agreement has no deadline, charge cap or region rule to vary, or no other region is enrolled.</Empty>}
      <div className="stack">{result.options.map((option, index) => <article className="rule-card" key={index}>
        <div className="split"><strong>{option.label}</strong><Status value={option.feasible ? 'eligible' : 'rejected'} /></div>
        <p className="muted">{verdict(option)}.{option.selected ? ' Would use ' + option.selected.runner_name + ' for up to ' + money(option.selected.envelope_cents) + '.' : ''}</p>
        {!option.feasible && option.blocking_codes.length > 0 && <small>Still blocked by: {option.blocking_codes.map(reasonName).join('; ')}</small>}
        <div className="button-row"><button className="button ghost" type="button" onClick={() => void choose(option)}>Review this change</button></div>
      </article>)}</div>
      <small>{result.notice}</small>
    </>}
    {chosen && rules && <Notice type="info">
      <strong>Proposed change to the agreement</strong>
      <ul>{changeLines(rules, chosen.edits).map(line => <li key={line}>{line}</li>)}</ul>
      {canRevise
        ? <div className="button-row"><button className="button primary" disabled={busy} onClick={() => void accept()}>Accept and create a revision for review</button>
            <button className="button ghost" onClick={() => setChosen(null)}>Cancel</button></div>
        : <p>Only a reviewer can change an agreement. Share this change with one; nothing has been changed.</p>}
    </Notice>}
  </Panel>;
}

export function NewJob({ policies, config, onChange, canRevise = false }: { policies: Policy[]; config: Config; onChange: () => void; canRevise?: boolean }) {
  const approved = policies.filter(policy => policy.status === 'approved');
  const [policy, setPolicy] = useState('');
  const [title, setTitle] = useState('Nightly image embeddings');
  const [count, setCount] = useState(4);
  const [mode, setMode] = useState('live');
  const [flexible, setFlexible] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const selected = policy || approved[0]?.id || '';
  function invalidate() { setPreview(null); setKey(crypto.randomUUID()); }
  function spec() { return { policy_id: selected, title, sample_count: files.length || count, mode, flexible }; }
  async function check(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { setPreview(await post<Preview>('/jobs/preview', spec())); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true); setError('');
    try {
      if (files.length > 16 || files.some(file => file.size > 1_000_000)) throw new Error('Choose up to 16 images of at most 1 MB each.');
      const images = mode === 'live' ? await Promise.all(files.map(encodeImage)) : [];
      const job = await post<Job>('/jobs', { ...spec(), images }, { 'Idempotency-Key': key });
      onChange(); go('/jobs/' + job.id);
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <Page title="Submit GPU job" subtitle="Preview available capacity against an approved agreement." action={<LinkButton to="/jobs">Back to queue</LinkButton>}>
    {!approved.length && <Notice type="info">An approved policy is required. <a href="#/agreements">Create or approve an agreement</a>.</Notice>}
    <div className="content-grid">
      <Panel title="Workload" subtitle={config.model + ' · 960-dimensional image embeddings'}>
        <form className="stack" onSubmit={check}>
          <label>Job name<input value={title} required minLength={2} maxLength={120} onChange={event => { setTitle(event.target.value); invalidate(); }} /></label>
          <label>Approved agreement<select value={selected} onChange={event => { setPolicy(event.target.value); invalidate(); }} required>
            {!approved.length && <option value="">No approved agreements</option>}{approved.map(item => <option key={item.id} value={item.id}>{item.title} · {item.id.slice(0, 6)}</option>)}
          </select></label>
          <div className="form-grid">
            <label>Execution mode<select value={mode} onChange={event => { setMode(event.target.value); setFiles([]); invalidate(); }}>
              <option value="live">Live GPU execution</option><option value="shadow">Shadow recommendation</option>
            </select></label>
            <label>Sample images<input type="number" min={1} max={16} value={files.length || count} disabled={!!files.length} onChange={event => { setCount(Number(event.target.value)); invalidate(); }} /></label>
          </div>
          {mode === 'live' && <label className="upload-field"><UploadCloud size={20} /><span>{files.length ? files.length + ' files selected' : 'Add PNG, JPEG, or WebP images'}</span>
            <small>Optional. Otherwise, the job uses the built-in sample images.</small><input type="file" multiple accept="image/png,image/jpeg,image/webp" onChange={event => { setFiles(Array.from(event.target.files ?? [])); invalidate(); }} /></label>}
          <label className="check"><input type="checkbox" checked={flexible} onChange={event => { setFlexible(event.target.checked); invalidate(); }} />Allow deferral within the agreement</label>
          {error && <Notice>{error}</Notice>}
          <button className="button primary" disabled={busy || !approved.length}><Activity size={17} />{busy ? 'Checking…' : 'Preview placement'}</button>
        </form>
      </Panel>
      <Panel title="Admission preview" subtitle="The reservation is validated again when you submit.">
        {preview ? <>
          {preview.selected ? <Notice type="success">{mode === 'shadow' ? 'A recommendation is available. Shadow mode creates no dispatch.' : 'An eligible reservation is available.'}</Notice>
            : <Notice type="info">No runner satisfies the current policy and inventory.</Notice>}
          <div className="stack">{preview.candidates.slice(0, 12).map((candidate, index) => <CandidateView candidate={candidate} key={index} />)}</div>
          <div className="button-row"><button className="button primary" disabled={busy} onClick={submit}>{preview.selected ? (mode === 'shadow' ? 'Record recommendation' : 'Submit live job') : 'Record rejected request'}</button></div>
        </> : <Empty title="Preview a placement" icon={<Cpu size={26} />}>Review the available device, quoted charge, time window, and any blocked clauses.</Empty>}
      </Panel>
    </div>
    {approved.length > 0 && <WhatIf spec={{ ...spec(), images: [] }} policyId={selected} canRevise={canRevise} onChange={onChange} auto={!!preview && !preview.selected} />}
  </Page>;
}

function observed(value: unknown) {
  return value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);
}

export function JobView({ id, user, onChange }: { id: string; user: User; onChange: () => void }) {
  const { data, error, refresh } = useDetail<JobDetail>('jobs', id);
  const [failure, setFailure] = useState('');
  const [selectedFinding, setFinding] = useState('');
  const [note, setNote] = useState('');
  if (error) return <Notice>{error}</Notice>;
  if (!data) return <Loading />;
  const job = data;
  const result = job.attempts.at(-1)?.result;
  async function cancel() {
    try { await post('/jobs/' + id + '/cancel'); refresh(); onChange(); }
    catch (value) { setFailure(message(value)); }
  }
  async function reconcile(event: FormEvent) {
    event.preventDefault();
    try { await post('/jobs/' + id + '/reconcile', { note }); setNote(''); refresh(); onChange(); }
    catch (value) { setFailure(message(value)); }
  }
  return <Page title={job.title} subtitle={label(job.mode) + ' · ' + job.sample_count + ' images · Submitted ' + date(job.created_at)}
    action={<LinkButton to="/jobs">Back to queue</LinkButton>}>
    {failure && <Notice>{failure}</Notice>}
    <div className="metrics-grid">
      <Metric name="Job status" value={label(job.status)} detail={job.cancel_requested ? 'Cancellation requested' : 'Current execution state'} icon={<Radio size={18} />} />
      <Metric name="Execution time" value={result?.duration_s == null ? '—' : num(result.duration_s) + ' s'} detail={result?.device ?? 'Awaiting execution'} icon={<Cpu size={18} />} />
      <Metric name="Board energy" value={result?.gpu_energy_kwh == null ? '—' : num(result.gpu_energy_kwh * 1000, 3) + ' Wh'} detail={result ? pct(result.telemetry_coverage) + ' sampling coverage' : 'Measured GPU board power'} icon={<Activity size={18} />} />
      <Metric name="Internal charge" value={money(result?.charged_cents)} detail={'Reserved ' + money(job.decision.envelope_cents)} icon={<Layers3 size={18} />} />
    </div>
    <div className="content-grid">
      <Panel title="Execution evidence" subtitle={'Deadline ' + date(job.deadline_at)} action={<Status value={job.status} />}>
        {active.includes(job.status) && !job.cancel_requested && <button className="button secondary" onClick={cancel}>Cancel job</button>}
        {job.status === 'execution_unknown' && ['admin', 'operator'].includes(user.role) && <form className="review-box" onSubmit={reconcile}>
          <label>Record why the original process has stopped<input required minLength={12} maxLength={500} value={note} onChange={event => setNote(event.target.value)} /></label>
          <button className="button secondary" disabled={(job.decision.reserved_until ?? 0) * 1000 > Date.now()}>Confirm stopped and release</button>
        </form>}
        {result?.message && <Notice type="info">{result.message}</Notice>}
        {result?.artifact_id && <div className="artifact">
          <div className="runner-icon"><FileText size={22} /></div><div className="grow"><strong>image-embeddings.json</strong><small>{result.rows} verified rows · {result.model}</small>
            {result.inference_seconds != null && <small>{num(result.inference_seconds, 3)} seconds of model inference</small>}</div>
          <a className="button secondary" href={'/api/v1/artifacts/' + result.artifact_id}><Download size={16} /> Output</a>
          <div className="hash"><small>Output SHA-256</small><code>{result.sha256}</code></div>
        </div>}
        {job.input_sha256 && <div className="hash"><small>Input SHA-256</small><code>{job.input_sha256}</code></div>}
        <ol className="timeline">{job.events.map(event => <li key={event.seq}><div><strong>{event.kind.replace(/([a-z])([A-Z])/g, '$1 $2')}</strong><small>{date(event.at)} · event {event.seq}</small></div>
          <details><summary>Data</summary><pre>{JSON.stringify(event.details, null, 2)}</pre></details></li>)}</ol>
        <a className="button secondary" href={'/api/v1/jobs/' + id + '/evidence.json'}><Download size={16} /> Signed evidence</a>
      </Panel>
      {(job.workload || stageRows(result?.stage_seconds).length > 0) && <Panel title="Workload specification" subtitle="Fixed when the job was submitted; it cannot change afterwards.">
        {stageRows(result?.stage_seconds).length > 0 && <div className="stack" aria-label="Stage timing">
          <h4>Where the time went</h4>
          {stageRows(result?.stage_seconds).map(row => <div key={row.key} className="split" title={row.hint}>
            <span>{row.label}<small> {row.hint}</small></span><strong>{num(row.seconds, 3)} s <small>({pct(row.share)})</small></strong></div>)}
        </div>}
        {job.workload && <dl className="stack">{specRows(job.workload).map(([name, value]) => <div key={name} className="split"><dt>{name}</dt><dd>{value}</dd></div>)}</dl>}
        {job.workload && <div className="hash"><small>Specification SHA-256</small><code>{job.workload.spec_sha256}</code></div>}
      </Panel>}
      <Panel title="Policy audit" subtitle="Reconstructed from execution evidence" action={<div className="button-row">
        <LinkButton to={'/agreements/' + job.policy_id}>Pinned policy</LinkButton><LinkButton to={'/explain/job/' + id}>Explain</LinkButton></div>}>
        <div className="stack">{job.findings.map(finding => <article className="rule-card" key={finding.id}>
          <div className="split"><strong>{kinds[finding.rule] ?? label(finding.rule)}</strong><Status value={finding.status} /></div>
          <small>Expected {observed(finding.expected)} · observed {observed(finding.observed)}</small>
          {finding.source_span && evidence(job.policy.source, ...finding.source_span) && <blockquote>{evidence(job.policy.source, ...finding.source_span)}</blockquote>}
          {finding.evidence.length > 0 && <small>Evidence events {finding.evidence.join(', ')}</small>}
          {['admin', 'reviewer'].includes(user.role) && <button className="button ghost" onClick={() => setFinding(selectedFinding === finding.id ? '' : finding.id)}>Review finding</button>}
          {selectedFinding === finding.id && <ReviewForm type="jobs" id={id} finding={finding.id} reviews={job.reviews} refresh={refresh} />}
        </article>)}</div>
      </Panel>
    </div>
    {!!job.decision.candidates.length && <Panel title="Placement candidates"><div className="stack">{job.decision.candidates.map((item, index) => <CandidateView key={index} candidate={item} />)}</div></Panel>}
  </Page>;
}

export function Capacity({ runners, onChange, canEnroll = false }: { runners: Runner[]; onChange: () => void; canEnroll?: boolean }) {
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [zone, setZone] = useState('');
  const [issued, setIssued] = useState<{ id: string; token: string } | null>(null);
  async function enroll(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const created = await api<{ id: string; token: string }>('/runners', { method: 'POST', body: JSON.stringify({ name, zone: zone.trim() ? zone.trim().toUpperCase() : null }) });
      setIssued({ id: created.id, token: created.token }); setName(''); setZone(''); onChange();
    } catch (failure) { setError(message(failure)); }
  }
  async function toggle(runner: Runner) {
    try { await api('/runners/' + runner.id + '/dispatch', { method: 'PATCH', body: JSON.stringify({ paused: !runner.paused }) }); onChange(); }
    catch (failure) { setError(message(failure)); }
  }
  return <Page title="Compute capacity" subtitle="Check runner health and control new dispatches.">
    {error && <Notice>{error}</Notice>}
    {canEnroll && <Panel title="Enroll a GPU host" subtitle="Creates a runner in your workspace and shows its token once">
      <form className="stack" onSubmit={enroll}>
        <label>Runner name<input value={name} onChange={event => setName(event.target.value)} maxLength={100} required placeholder="Lab workstation" /></label>
        <label>Grid zone (optional, e.g. GB)<input value={zone} onChange={event => setZone(event.target.value)} maxLength={20} pattern="[A-Za-z0-9_-]{2,20}" /></label>
        <div className="button-row"><button className="button" type="submit"><Plus size={15} />Enroll runner</button></div>
      </form>
      {issued && <Notice type="success">Runner <b>{issued.id}</b> created. Copy this token now into the GPU host's runner configuration; it will not be shown again: <code>{issued.token}</code></Notice>}
    </Panel>}
    <div className="content-grid">{runners.map(runner => <Panel key={runner.id} title={runner.name} subtitle={runner.device} action={<Status value={runner.paused ? 'paused' : runner.online ? 'online' : 'offline'} />}>
      <div className="form-facts"><span>Reported VRAM <b>{num(runner.vram_mib / 1024)} GiB</b></span><span>Grid zone <b>{runner.zone ?? 'Unconfigured'}</b></span>
        <span>Last heartbeat <b>{date(runner.last_seen)}</b></span><span>Hourly rate <b>{money(runner.rate_cents)}</b></span></div>
      <div className="button-row"><button className="button secondary" onClick={() => toggle(runner)}>{runner.paused ? 'Resume dispatch' : 'Pause dispatch'}</button></div>
    </Panel>)}</div>
  </Page>;
}
