import { useEffect, useState, type FormEvent } from 'react';
import { Database, Download, FlaskConical, GitBranch, Play, RefreshCw } from 'lucide-react';
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from '@xyflow/react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import '@xyflow/react/dist/style.css';
import {
  countLabel, date, Empty, go, label, LinkButton, Loading, message, money, Notice, num, Page, Panel, pct, post, ReviewForm, Status, useDetail,
  type Auditor, type Dataset, type Policy, type Run, type RunDetail, type User,
} from './shared';
import { Metric } from './operations';

const palette = ['#8be2b0', '#82a7f4', '#dfb773', '#c392ec'];
const chartStyle = { background: '#171e1a', border: '1px solid #34423a', borderRadius: 8, color: '#e3ebe6' };
const strategies = [
  ['cost_plus', 'Cost plus'],
  ['scarcity', 'Scarcity responsive'],
  ['scripted_response', 'Scripted response'],
  ['q_learning', 'Q-learning'],
];

export function Research({ datasets, policies, runs, onChange }: { datasets: Dataset[]; policies: Policy[]; runs: Run[]; onChange: () => void }) {
  const [title, setTitle] = useState('Carbon-aware scheduling comparison');
  const [dataset, setDataset] = useState('');
  const [policy, setPolicy] = useState('');
  const [jobs, setJobs] = useState(100);
  const [seeds, setSeeds] = useState(3);
  const [seed, setSeed] = useState(2026);
  const [carbon, setCarbon] = useState(4);
  const [scarcity, setScarcity] = useState(1);
  const [cohort, setCohort] = useState('modeled');
  const [runtimeModel, setRuntimeModel] = useState('median');
  const [signal, setSignal] = useState('lagged');
  const [shock, setShock] = useState(true);
  const [exactModel, setExactModel] = useState(false);
  const [agents, setAgents] = useState(['cost_plus', 'scarcity', 'scripted_response']);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const run = await post<Run>('/runs', { title, dataset_id: dataset || datasets[0]?.id, policy_id: policy || null, jobs, seeds, seed,
        strategies: agents, carbon_weight: carbon, scarcity, controlled_undercut: shock, respect_gpu_models: exactModel, carbon_mode: signal,
        cohort, runtime_model: runtimeModel });
      onChange(); go('/research/' + run.id);
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <Page title="Research Lab" subtitle="Replay real workload patterns with controlled market and scheduling conditions." action={<LinkButton to="/data">Data sources</LinkButton>}>
    <div className="content-grid">
      <Panel title="Experiment setup" subtitle="All scheduler arms share the same arrivals, carbon signal, and offer tape.">
        <form className="stack" onSubmit={submit}>
          <label>Run name<input value={title} onChange={event => setTitle(event.target.value)} required minLength={2} maxLength={120} /></label>
          <label>Dataset snapshot<select value={dataset || datasets[0]?.id || ''} onChange={event => setDataset(event.target.value)}>
            {!datasets.length && <option value="">Import a dataset first</option>}
            {datasets.map(card => <option key={card.id} value={card.id}>Alibaba v2023 + NESO GB · {card.id.slice(0, 8)}</option>)}
          </select></label>
          <label>Policy override<select value={policy} onChange={event => setPolicy(event.target.value)}>
            <option value="">Scenario deadlines and budgets</option>
            {policies.filter(row => row.status === 'approved').map(row => <option key={row.id} value={row.id}>{row.title}</option>)}
          </select></label>
          <div className="form-grid">
            <label>GPU jobs per seed<input type="number" value={jobs} min={30} max={1200} onChange={event => setJobs(Number(event.target.value))} /></label>
            <label>Paired seeds<input type="number" value={seeds} min={1} max={30} onChange={event => setSeeds(Number(event.target.value))} /></label>
            <label>Starting seed<input type="number" value={seed} min={0} max={2147483617} onChange={event => setSeed(Number(event.target.value))} /></label>
            <label>Carbon weight<input type="number" value={carbon} min={0} max={25} onChange={event => setCarbon(Number(event.target.value))} /></label>
            <label>Supply pressure<select value={scarcity} onChange={event => setScarcity(Number(event.target.value))}><option value={0}>Low</option><option value={1}>Normal</option><option value={2}>High with provider outage</option></select></label>
            <label>Runtime cohort<select value={cohort} onChange={event => setCohort(event.target.value)}><option value="modeled">Modeled runtimes</option><option value="successful_proxy">Successful lifecycle proxy</option></select></label>
          </div>
          <label>Planning carbon signal<select value={signal} onChange={event => setSignal(event.target.value)}><option value="lagged">Lagged history</option><option value="oracle">Hindsight oracle</option></select></label>
          <label>Runtime planning model<select value={runtimeModel} onChange={event => setRuntimeModel(event.target.value)}>
            <option value="median">Training median</option><option value="calibrated">Calibrated upper bound</option></select></label>
          <fieldset><legend>Provider agents</legend><div className="form-grid">{strategies.map(([key, name]) => <label className="check" key={key}>
            <input type="checkbox" checked={agents.includes(key)} onChange={() => setAgents(agents.includes(key) ? agents.filter(x => x !== key) : [...agents, key])} />{name}
          </label>)}</div></fieldset>
          <label className="check"><input type="checkbox" checked={shock} onChange={event => setShock(event.target.checked)} />Inject controlled price undercuts</label>
          <label className="check"><input type="checkbox" checked={exactModel} onChange={event => setExactModel(event.target.checked)} />Use the trace's GPU model constraints</label>
          {error && <Notice>{error}</Notice>}
          <button className="button primary" disabled={busy || !datasets.length || agents.length < 2}><Play size={17} />{busy ? 'Queueing…' : 'Run experiment'}</button>
        </form>
      </Panel>
      <Panel title="Run history" subtitle="Open a result to inspect placements and audit transitions.">
        {runs.length ? <div className="rows">{runs.map(run => <a className="list-row" href={'#/research/' + run.id} key={run.id}>
          <div className="row-icon"><FlaskConical size={18} /></div><div className="grow"><strong>{run.title}</strong><small>{run.jobs} jobs · {countLabel(run.seeds, 'seed')} · {date(run.created_at)}</small></div><Status value={run.status} />
        </a>)}</div> : <Empty title="No experiment runs" icon={<FlaskConical size={24} />}>Run a paired experiment to populate the comparison.</Empty>}
      </Panel>
    </div>
  </Page>;
}

function AuditGraph({ audit, pickRound }: { audit: Auditor; pickRound: (round: number) => void }) {
  const nodes: Node[] = audit.states.map((state, index) => ({ id: state, position: { x: 65 + index % 2 * 210, y: 50 + Math.floor(index / 2) * 115 },
    data: { label: label(state) }, style: { background: '#1e3027', color: '#d4f6df', border: '1px solid #416952', borderRadius: 8, width: 150 } }));
  const pairs = new Map<string, Edge>();
  audit.transitions.filter(edge => edge.from !== edge.to).forEach(edge => {
    const key = edge.from + '-' + edge.to;
    if (!pairs.has(key)) pairs.set(key, { id: key, source: edge.from, target: edge.to, label: edge.action, data: { round: edge.rounds[0] },
      markerEnd: { type: MarkerType.ArrowClosed, color: '#82cda1' }, style: { stroke: '#82cda1' },
      labelStyle: { fill: '#b7c9bf' }, labelBgStyle: { fill: '#171e1a' } });
  });
  return <div className="flow">
    <ReactFlow nodes={nodes} edges={Array.from(pairs.values())} nodesDraggable={false} nodesConnectable={false}
      onEdgeClick={(_, edge) => pickRound(Number(edge.data?.round ?? 0))} fitView fitViewOptions={{ padding: .28 }} colorMode="dark" minZoom={.35}>
      <Background gap={22} color="#33443a" /><Controls showInteractive={false} />
    </ReactFlow>
  </div>;
}

export function ResearchResult({ id, user }: { id: string; user: User }) {
  const { data, error, refresh } = useDetail<RunDetail>('runs', id);
  const [round, setRound] = useState(0);
  const [provider, setProvider] = useState('');
  const [showReview, setShowReview] = useState(false);
  useEffect(() => { setRound(0); setProvider(''); setShowReview(false); }, [id]);
  if (error) return <Notice>{error}</Notice>;
  if (!data) return <Loading />;
  const run = data;
  const result = run.result;
  const episode = result?.first_episode;
  const frame = episode?.offers[round];
  const auditor = episode?.audits.find(audit => audit.provider === provider) ?? episode?.audits[0];
  const paired = result?.paired;
  const main = result?.summary.carbon_aware;
  const chart = Object.entries(result?.summary ?? {}).map(([arm, m]) => ({ arm: label(arm), completed: m.completed, carbon: m.carbon_g, wait: m.wait_p95_min }));
  const priceLines = episode?.offers.map(item => ({ round: item.round, ...Object.fromEntries(item.offers.map(o => [o.provider, o.price / 100])) }));
  return <Page title={run.title} subtitle={'Run ' + id.slice(0, 10) + ' · ' + run.jobs + ' jobs per seed · ' + countLabel(run.seeds, 'seed')}
    action={<div className="button-row"><LinkButton to="/research">All runs</LinkButton><LinkButton to={'/explain/experiment/' + id}>Explain</LinkButton></div>}>
    {run.error && <Notice>{run.error}</Notice>}
    {!result && <Panel title="Run progress" action={<Status value={run.status} />}><progress value={run.progress} max={100} /><p className="muted">{run.progress}% · Research worker status</p></Panel>}
    {result && episode && main && <>
      <div className="metrics-grid">
        <Metric name="Completed jobs" value={num(main.completed)} detail="Carbon-aware average" />
        <Metric name="On-time completion" value={pct(main.on_time_rate)} detail="All submitted jobs" />
        <Metric name="Estimated emissions" value={num(main.carbon_g) + ' g'} detail="GPU model × historical grid intensity" />
        <Metric name="Policy violations" value={num(main.policy_violations)} detail="Per carbon-aware run" />
      </div>
      <Panel title="Scheduler comparison" subtitle="Per-seed averages across the same workload and market inputs"
        action={<div className="button-row"><a className="button secondary" href={'/api/v1/runs/' + id + '/metrics.csv'}><Download size={15} /> CSV</a>
          {run.artifact_id && <a className="button secondary" href={'/api/v1/artifacts/' + run.artifact_id}><Download size={15} /> Evidence</a>}</div>}>
        <div className="result-grid">
          <div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{ top: 10, right: 10, left: -15, bottom: 10 }}>
            <CartesianGrid vertical={false} stroke="#29372f" /><XAxis dataKey="arm" stroke="#9caca2" tick={{ fontSize: 11 }} interval={0} /><YAxis stroke="#9caca2" tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={chartStyle} cursor={{ fill: '#222f28' }} /><Bar dataKey="completed" name="Completed jobs" fill={palette[0]} radius={[5, 5, 0, 0]} isAnimationActive={false} />
          </BarChart></ResponsiveContainer></div>
          <div className="table-wrap"><table><thead><tr><th>Scheduler</th><th>On time</th><th>Wait p95</th><th>g CO₂</th><th>Violations</th></tr></thead>
            <tbody>{Object.entries(result.summary).map(([arm, metrics]) => <tr key={arm}><td>{label(arm)}</td><td>{pct(metrics.on_time_rate)}</td>
              <td>{num(metrics.wait_p95_min)} min</td><td>{num(metrics.carbon_g)}</td><td>{num(metrics.policy_violations)}</td></tr>)}</tbody>
          </table></div>
        </div>
        {paired && <div className="paired">{Object.entries(paired).map(([key, row]) => <div key={key}><small>{label(key)} Δ vs. policy only</small><strong>{num(row.delta, 3)}</strong>
          <small>{row.interval95 ? '95% interval ' + row.interval95.map(x => num(x, 3)).join(' to ') : 'Interval needs at least three pairs'}</small></div>)}</div>}
      </Panel>
      <div className="overview-grid">
        <Panel title="Grid signal and schedule" subtitle={'First seed ' + episode.seed + ' · GB historical replay'}>
          <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={episode.timeline} margin={{ top: 10, right: 12, left: -10, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#29372f" /><XAxis dataKey="round" stroke="#9caca2" tick={{ fontSize: 11 }} /><YAxis stroke="#9caca2" tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={chartStyle} /><Legend /><Line dataKey="actual" stroke={palette[0]} dot={false} name="Published actual g CO₂/kWh" isAnimationActive={false} />
            <Line dataKey="forecast" stroke={palette[1]} dot={false} name="Planning signal" isAnimationActive={false} />
          </LineChart></ResponsiveContainer></div>
          <div className="range-control"><label>Market round <b>{round}</b><input type="range" min={0} max={episode.offers.length - 1} value={round} onChange={event => setRound(Number(event.target.value))} /></label></div>
          {frame && <div className="form-facts"><span>Available GPUs <b>{frame.capacity}</b></span><span>Demand pressure <b>{num(frame.pressure, 3)}</b></span>
            <span>Queued <b>{episode.timeline[round]?.queued}</b></span><span>Started <b>{episode.timeline[round]?.started}</b></span></div>}
        </Panel>
        <Panel title="Market offers" subtitle={'Posted at round ' + round + ' · credits per GPU-hour'}>
          <div className="chart price-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={priceLines} margin={{ top: 8, right: 12, left: -12, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="#29372f" /><XAxis dataKey="round" stroke="#9caca2" tick={{ fontSize: 10 }} /><YAxis stroke="#9caca2" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={chartStyle} />{episode.audits.map((item, index) => <Line key={item.provider} dataKey={item.provider}
              name={label(item.provider)} stroke={palette[index % palette.length]} dot={false} isAnimationActive={false} />)}
          </LineChart></ResponsiveContainer></div>
          <div className="stack">{frame?.offers.map(offer => <div className="rule-card split" key={offer.provider}><div><strong>{label(offer.provider)}</strong><small>{offer.gpu_model}</small></div><code>{money(offer.price)}</code></div>)}</div>
          {!frame?.offers.length && <Empty title="No offers in this round" />}
          <div className="hash"><small>Dataset snapshot</small><code>{result.dataset}</code></div>
        </Panel>
      </div>
      <Panel title="Provider strategy audit" subtitle="Observed price responses and transition support" action={<GitBranch size={20} className="muted" />}>
        {auditor && <div className="result-grid">
          <AuditGraph audit={auditor} pickRound={setRound} />
          <div className="stack">
            <label>Provider<select value={auditor.provider} onChange={event => { setProvider(event.target.value); setShowReview(false); }}>{episode.audits.map(item => <option key={item.provider} value={item.provider}>{label(item.provider)}</option>)}</select></label>
            <div className="split"><Status value={auditor.status} /><small>Held-out action fidelity {pct(auditor.heldout_accuracy)}</small></div>
            <p>{auditor.summary}</p>
            <div className="form-facts"><span>Exposures <b>{auditor.exposures}</b></span><span>Normal controls <b>{auditor.matched_controls}</b></span><span>Coverage <b>{pct(auditor.heldout_coverage)}</b></span></div>
            <div className="transition-list">{auditor.transitions.map(item => <button key={item.from + item.to + item.action} className="button ghost" onClick={() => setRound(item.rounds[0])}>
              {label(item.from)} → {label(item.to)} · {label(item.action)} × {item.count}
            </button>)}</div>
            {['admin', 'reviewer'].includes(user.role) && <button className="button secondary" onClick={() => setShowReview(!showReview)}>Review provider finding</button>}
            {showReview && <ReviewForm type="runs" id={id} finding={auditor.provider} reviews={run.reviews} refresh={refresh} />}
          </div>
        </div>}
        <div className="form-facts"><span>Precision <b>{pct(result.audit_metrics.precision)}</b></span><span>Recall <b>{pct(result.audit_metrics.recall)}</b></span>
          <span>False positive rate <b>{pct(result.audit_metrics.false_positive_rate)}</b></span><span>Abstentions <b>{num(result.audit_metrics.abstentions)}</b></span></div>
      </Panel>
      <Panel title="Schedule and allocation evidence" subtitle="First seed · selected carbon-aware placements">
        <div className="table-wrap"><table><thead><tr><th>Source pod</th><th>Pool</th><th>Round interval</th><th>Status</th><th>g CO₂</th><th>Charge</th></tr></thead>
          <tbody>{episode.placements.filter(item => item.start <= round && item.finish > round).slice(0, 40).map(item => <tr key={item.job}><td><code>{item.job}</code></td>
            <td>{label(item.provider)}</td><td>{item.start}–{item.finish}</td><td><Status value={item.status} /></td><td>{num(item.carbon_g, 3)}</td><td>{money(item.charge)}</td></tr>)}</tbody>
        </table></div>
        {!episode.placements.some(item => item.start <= round && item.finish > round) && <Empty title="No active placements in this round">Move the round slider to inspect the schedule.</Empty>}
        <details className="assumptions"><summary>Data origins and assumptions</summary><ul>{result.assumptions.map(text => <li key={text}>{text}</li>)}</ul><pre>{JSON.stringify(episode.mapping, null, 2)}</pre></details>
      </Panel>
    </>}
  </Page>;
}

export function DataSources({ datasets, onChange }: { datasets: Dataset[]; onChange: () => void }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState('');
  async function load() {
    setBusy(true); setError(''); setSuccess('');
    try {
      const card = await post<Dataset>('/datasets/import');
      setSuccess('Verified and imported ' + num(card.gpu_pods, 0) + ' GPU pod records.');
      onChange();
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <Page title="Data sources" subtitle="Check the raw inputs, normalized snapshots, and runtime assumptions."
    action={<button className="button primary" disabled={busy} onClick={load}><RefreshCw size={16} className={busy ? 'spin' : ''} />{busy ? 'Importing…' : 'Import verified sources'}</button>}>
    {error && <Notice>{error}</Notice>}{success && <Notice type="success">{success}</Notice>}
    {!datasets.length && <Panel title="Local source preflight"><Empty icon={<Database size={27} />} title="No normalized snapshots">Import the supplied dataset folder to create a checksummed Parquet snapshot.</Empty></Panel>}
    {datasets.map(card => <div className="stack" key={card.id}>
      <div className="metrics-grid"><Metric name="GPU pod records" value={num(card.gpu_pods, 0)} detail={num(card.pods, 0) + ' total pod records'} />
        <Metric name="GPU devices" value={num(card.gpu_devices, 0)} detail={num(card.gpu_nodes, 0) + ' source nodes'} />
        <Metric name="Successful runtime proxies" value={num(card.runtime_proxies, 0)} detail="Ordered lifecycle timestamps" />
        <Metric name="Carbon intervals" value={num(card.carbon_intervals, 0)} detail="30 minutes per interval" /></div>
      <Panel title="Snapshot provenance" subtitle={'Alibaba GPU v2023 · NESO ' + card.carbon_zone}>
        <div className="hash"><small>Snapshot SHA-256</small><code>{card.id}</code></div>
        <div className="table-wrap"><table><thead><tr><th>Source file</th><th>SHA-256</th></tr></thead><tbody>
          {card.sources.map(source => <tr key={source.file}><td><a className="table-link" href={source.url} target="_blank" rel="noreferrer">{source.file}</a></td><td><code>{source.sha256}</code></td></tr>)}
        </tbody></table></div>
        <div className="form-facts">{Object.entries(card.origins).map(([key, value]) => <span key={key}>{label(key)} <b>{value}</b></span>)}</div>
      </Panel>
    </div>)}
  </Page>;
}
