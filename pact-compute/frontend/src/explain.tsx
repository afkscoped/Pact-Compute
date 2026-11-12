import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, CheckCircle2, Download, GitBranch, Microscope } from 'lucide-react';
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from '@xyflow/react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, Empty, label, Loading, message, Notice, num, Page, Panel, pct, post, Status } from './shared';

type Topic = 'workspace' | 'contract' | 'pricing' | 'allocation' | 'booking' | 'job' | 'experiment';
type Step = { id: number; title: string; detail: string; link: string; evidence: string | number | null };
type Answer = { topic: Topic; title: string; status: string; source: string; steps: Step[]; focus?: number[]; provider_status?: string };
type Stats = Record<string, number | null>;
type EdgeRow = { from: string; to: string; action: string; count: number };
type PricingExample = { seed: number; regime: string; label: boolean; intervention: {
  cut_response: number[]; raise_response: number[]; cut_profit_delta: number; raise_profit_delta: number;
  rounds: number[]; trajectory: { round: number; sham: number; cut: number; raise: number; demand: number; capacity: number[] }[];
} };
type Study = {
  version: string; protocol: { comparison: Record<string, Stats>; transition_coverage: string[] };
  runtime: { comparison: Record<string, Stats>; target_coverage: number; split: Record<string, { n: number }>;
    observations: { source_id: string; actual_proxy_s: number; training_median: number; training_p90: number; calibrated_group_bound: number }[] };
  pricing: { classification: Record<string, Stats>; training: { episodes: number; visited_states: number[]; reward_history: { episode: number; profits: number[] }[];
      alpha?: number; gamma?: number; margins?: number[]; q_tables?: { state: number[]; q_values: number[] }[][] };
    fsm: { states: number; accuracy: number | null; coverage: number; log_loss: number | null; edges: EdgeRow[];
      majority_baseline?: { accuracy: number; log_loss: number } };
    examples: PricingExample[]; label_scope: string; splits: { heldout_episodes: number } };
  scheduler: Record<string, { summary: Record<string, Stats>; config: { seeds: number; jobs: number } }>;
  paired_calibrated_minus_median: Record<string, { delta: number | null; interval95: [number, number] | null; n: number }>;
  scope: string[];
};

const colors = ['#9ee8b7', '#87adf4', '#ddb67b'];
const tooltip = { background: '#17211a', border: '1px solid #385344', borderRadius: 8, color: '#e8f0eb' };
const guides: [Topic, string][] = [['workspace', 'Workspace guide'], ['contract', 'Contract to protocol'],
  ['pricing', 'Pricing and automata'], ['allocation', 'Sustainable allocation']];
const names: Record<string, string> = {
  presence_baseline: 'Event presence baseline', temporal_monitor: 'Temporal protocol monitor',
  training_median: 'Training median', training_p90: 'Training p90', calibrated_group_bound: 'Calibrated group bound',
  markup: 'Price markup baseline', effect: 'Matched intervention detector',
  on_time_rate: 'On-time completion', carbon_g: 'Estimated emissions (g CO₂)', wait_p95_min: 'Wait p95 (min)',
};

function readable(value: string) { return names[value] ?? label(value); }
function stepTitle(value: string) { return value.replace(/([a-z])([A-Z])/g, '$1 $2'); }

function ModelTable({ rows, columns }: { rows: Record<string, Stats>; columns: [string, string, boolean?][] }) {
  return <div className="table-wrap"><table><thead><tr><th>Method</th>{columns.map(([key, name]) => <th key={key}>{name}</th>)}</tr></thead>
    <tbody>{Object.entries(rows).map(([name, row]) => <tr key={name}><td><strong>{readable(name)}</strong></td>
      {columns.map(([key, , percent]) => <td key={key}>{percent ? pct(row[key]) : num(row[key], 3)}</td>)}</tr>)}</tbody></table></div>;
}

function EvidenceGraph({ edges }: { edges: EdgeRow[] }) {
  const [picked, setPicked] = useState<EdgeRow | null>(null);
  const most = [...edges].sort((a, b) => b.count - a.count).slice(0, 16);
  const states = Array.from(new Set(most.flatMap(row => [row.from, row.to])));
  const graphNodes: Node[] = states.map((name, index) => ({ id: name, data: { label: name },
    position: { x: index % 3 * 230, y: Math.floor(index / 3) * 110 },
    style: { width: 174, background: '#203529', color: '#def2e4', border: '1px solid #466954', borderRadius: 8 } }));
  const pairs = new Set<string>();
  const graphEdges: Edge[] = [];
  for (const row of most) {
    const key = row.from + '->' + row.to;
    if (row.from === row.to || pairs.has(key)) continue;
    pairs.add(key);
    graphEdges.push({ id: key, source: row.from, target: row.to, label: row.action + ' · ' + row.count,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#83c9a0' }, style: { stroke: '#83c9a0' },
      labelStyle: { fill: '#dbe9df' }, labelBgStyle: { fill: '#17211a' }, data: { row } });
  }
  return <div className="stack">
    <div className="flow evidence-flow"><ReactFlow nodes={graphNodes} edges={graphEdges} fitView
      nodesDraggable={false} nodesConnectable={false} colorMode="dark" onEdgeClick={(_, edge) => setPicked(edge.data?.row as EdgeRow)}>
      <Background color="#2c4134" gap={24} /><Controls showInteractive={false} />
    </ReactFlow></div>
    {picked && <div className="step-inspection"><div><small>Source context</small><strong>{picked.from}</strong></div><ArrowRight size={17} />
      <div><small>Destination context</small><strong>{picked.to}</strong></div><span>{picked.action} · {picked.count} observations</span></div>}
    <details className="assumptions"><summary>Accessible transition table</summary>
      <div className="table-wrap"><table><thead><tr><th>From</th><th>To</th><th>Action</th><th>Support</th></tr></thead>
        <tbody>{[...edges].sort((a, b) => b.count - a.count).map(row => <tr key={[row.from, row.to, row.action].join('|')}>
          <td>{row.from}</td><td>{row.to}</td><td>{row.action}</td><td>{row.count}</td></tr>)}</tbody></table></div>
    </details>
  </div>;
}

function PricingEvidence({ study }: { study: Study }) {
  const [scenario, setScenario] = useState(study.pricing.examples[0]?.regime ?? '');
  const [tick, setTick] = useState(0);
  const [seller, setSeller] = useState(0);
  const selected = study.pricing.examples.find(item => item.regime === scenario);
  const trajectory = selected?.intervention.trajectory ?? [];
  const row = trajectory[tick];
  const training = study.pricing.training.reward_history.map(item => ({ episode: item.episode, sellerOne: item.profits[0], sellerTwo: item.profits[1] }));
  return <div className="stack">
    <ModelTable rows={study.pricing.classification} columns={[['precision', 'Precision', true], ['recall', 'Recall', true],
      ['f1', 'F1'], ['false_positive_rate', 'False-positive rate', true], ['fp', 'False positives']]} />
    <small>{study.pricing.label_scope}. {study.pricing.splits.heldout_episodes} held-out scenario episodes.</small>
    <div className="content-grid">
      <Panel title="Training progress" subtitle={study.pricing.training.episodes + ' episodes · realized seller margin'}>
        <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={training} margin={{ top: 8, right: 12, left: 4, bottom: 3 }}>
          <CartesianGrid stroke="#29382e" vertical={false} /><XAxis dataKey="episode" stroke="#9caea3" /><YAxis stroke="#9caea3" />
          <Tooltip contentStyle={tooltip} /><Legend /><Line dataKey="sellerOne" name="Seller 1" stroke={colors[0]} dot={false} isAnimationActive={false} />
          <Line dataKey="sellerTwo" name="Seller 2" stroke={colors[1]} dot={false} isAnimationActive={false} />
        </LineChart></ResponsiveContainer></div>
        <small>Frozen Q-table coverage · {study.pricing.training.visited_states.join(' and ')} visited states</small>
        {!!study.pricing.training.q_tables?.length && <details className="assumptions">
          <summary>Inspect the trained Q-table</summary>
          <p>States encode demand, remaining inventory, rival markup and episode time. The largest Q-value selects the markup.</p>
          <div className="form-facts"><span>Learning rate <b>{study.pricing.training.alpha}</b></span><span>Discount <b>{study.pricing.training.gamma}</b></span></div>
          <label>Seller<select value={seller} onChange={event => setSeller(Number(event.target.value))}><option value="0">Seller 1</option><option value="1">Seller 2</option></select></label>
          <div className="table-wrap q-table"><table><thead><tr><th>State bands</th>{study.pricing.training.margins?.map(value => <th key={value}>+{value}¢</th>)}</tr></thead>
            <tbody>{study.pricing.training.q_tables?.[seller]?.map(row => <tr key={row.state.join('/')}>
              <td><code>{row.state.join(' / ')}</code></td>{row.q_values.map((value, index) => <td key={index} className={value === Math.max(...row.q_values) ? 'best-value' : ''}>{num(value, 2)}</td>)}
            </tr>)}</tbody></table></div>
        </details>}
      </Panel>
      <Panel title="Matched pricing interventions" subtitle="Change only one seller's quote and inspect its rival's response.">
        <label>Test scenario<select value={scenario} onChange={event => { setScenario(event.target.value); setTick(0); }}>
          {study.pricing.examples.map(item => <option key={item.regime} value={item.regime}>{label(item.regime)}</option>)}</select></label>
        <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={trajectory} margin={{ top: 8, right: 12, left: 1, bottom: 3 }}>
          <CartesianGrid stroke="#29382e" vertical={false} /><XAxis dataKey="round" stroke="#9caea3" /><YAxis stroke="#9caea3" />
          <Tooltip contentStyle={tooltip} /><Legend /><ReferenceLine x={tick} stroke="#e4eee7" />
          {selected?.intervention.rounds.map(round => <ReferenceLine key={round} x={round} stroke="#a0b8a7" strokeDasharray="4 4" />)}
          {(['sham', 'cut', 'raise'] as const).map((name, index) => <Line key={name} dataKey={name} name={label(name)} stroke={colors[index]} dot={false} isAnimationActive={false} />)}
        </LineChart></ResponsiveContainer></div>
        {!!trajectory.length && <label>Inspect round {tick}<input type="range" value={tick} min={0} max={trajectory.length - 1} onChange={event => setTick(Number(event.target.value))} /></label>}
        {row && <div className="form-facts"><span>Demand <b>{row.demand} buyers</b></span><span>Capacity <b>{row.capacity.join(' / ')}</b></span>
          <span>Cut vs sham <b>{num(row.cut - row.sham)} credit cents</b></span><span>Raise vs sham <b>{num(row.raise - row.sham)} credit cents</b></span></div>}
      </Panel>
    </div>
    <Panel title="Learned pricing states" subtitle="State labels combine market pressure, prior rival action and prior own action.">
      <div className="form-facts"><span>Merged states <b>{num(study.pricing.fsm.states)}</b></span>
        <span>Held-out accuracy <b>{pct(study.pricing.fsm.accuracy)}</b></span><span>Coverage <b>{pct(study.pricing.fsm.coverage)}</b></span>
        <span>Log loss <b>{num(study.pricing.fsm.log_loss, 3)}</b></span>
        {study.pricing.fsm.majority_baseline && <span>Majority-action baseline <b>{pct(study.pricing.fsm.majority_baseline.accuracy)}</b></span>}</div>
      <EvidenceGraph edges={study.pricing.fsm.edges} />
    </Panel>
  </div>;
}

function AllocationEvidence({ study }: { study: Study }) {
  const [mode, setMode] = useState('calibrated');
  const summary = study.scheduler[mode]?.summary ?? {};
  const observations = study.runtime.observations.map((item, index) => ({ ...item, observation: index + 1 }));
  const trade = Object.entries(summary).map(([name, row]) => ({ arm: label(name), carbon_g: row.carbon_g, completed: row.completed }));
  return <div className="stack">
    <ModelTable rows={study.runtime.comparison} columns={[['n', 'Test rows'], ['coverage', 'Observed coverage', true], ['mae_s', 'MAE (s)'],
      ['pinball_s', 'P90 pinball loss (s)'], ['mean_prediction_s', 'Mean estimate (s)']]} />
    <small>{Object.entries(study.runtime.split).map(([name, values]) => label(name) + ' ' + values.n).join(' · ')} · Coverage target {pct(study.runtime.target_coverage)}</small>
    <div className="content-grid">
      <Panel title="Held-out runtime estimates" subtitle="Actual target is the successful-pod lifecycle proxy.">
        <div className="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={observations}>
          <CartesianGrid stroke="#29382e" vertical={false} /><XAxis dataKey="observation" stroke="#9caea3" /><YAxis stroke="#9caea3" />
          <Tooltip contentStyle={tooltip} /><Legend /><Line dataKey="actual_proxy_s" name="Observed proxy (s)" stroke={colors[0]} dot={false} isAnimationActive={false} />
          <Line dataKey="calibrated_group_bound" name="Calibrated bound (s)" stroke={colors[1]} dot={false} isAnimationActive={false} />
          <Line dataKey="training_median" name="Training median (s)" stroke={colors[2]} dot={false} isAnimationActive={false} />
        </LineChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Paired allocation comparison" subtitle="Hold arrivals, provider offers and the grid series fixed.">
        <label>Runtime planning model<select value={mode} onChange={event => setMode(event.target.value)}>
          <option value="median">Median duration</option><option value="calibrated">Calibrated upper bound</option></select></label>
        <div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={trade}>
          <CartesianGrid stroke="#29382e" vertical={false} /><XAxis dataKey="arm" stroke="#9caea3" tick={{ fontSize: 10 }} />
          <YAxis stroke="#9caea3" /><Tooltip contentStyle={tooltip} /><Bar dataKey="carbon_g" name="Estimated g CO₂" fill={colors[0]} isAnimationActive={false} />
        </BarChart></ResponsiveContainer></div>
      </Panel>
    </div>
    <ModelTable rows={summary} columns={[['completed', 'Completed'], ['on_time_rate', 'On time', true], ['overruns', 'Runtime overruns'],
      ['wait_p95_min', 'Wait p95 (min)'], ['carbon_g', 'Estimated g CO₂']]} />
    <div className="paired">{Object.entries(study.paired_calibrated_minus_median).map(([key, row]) => <div key={key}>
      <small>{readable(key)} change</small><strong>{key === 'on_time_rate' && row.delta != null ? num(row.delta * 100, 3) + ' pp' : num(row.delta, 3)}</strong>
      <small>{row.n} pairs{row.interval95 ? ' · 95% interval ' + row.interval95.map(value => num(key === 'on_time_rate' ? value * 100 : value, 3)).join(' to ') : ''}</small>
    </div>)}</div>
  </div>;
}

function ResearchEvidence({ study }: { study: Study }) {
  const [panel, setPanel] = useState('protocol');
  return <Panel title="Publication comparisons" subtitle="Held-out tests and reproducible benchmark exports" action={<Microscope size={21} className="muted" />}>
    <div className="research-controls">
      <div className="button-row">{[['protocol', 'Protocol verification'], ['pricing', 'Pricing and FSM'], ['allocation', 'Runtime and allocation']].map(([id, text]) =>
        <button key={id} className={'button ' + (panel === id ? 'primary' : 'secondary')} onClick={() => setPanel(id)} aria-pressed={panel === id}>{text}</button>)}</div>
      <a className="button secondary" href="/api/v1/explain/study/download/publication-metrics.csv"><Download size={16} /> Metrics CSV</a>
      <a className="button secondary" href="/api/v1/explain/study/download/publication-study.json"><Download size={16} /> Full evidence</a>
    </div>
    {panel === 'protocol' && <div className="stack">
      <ModelTable rows={study.protocol.comparison} columns={[['n', 'Held-out traces'], ['accuracy', 'Exact verdict', true],
        ['unsafe_accepts', 'Unsafe accepts'], ['valid_rejects', 'Valid rejects']]} />
      <small>Transitions exercised · {study.protocol.transition_coverage.join(', ')}</small>
    </div>}
    {panel === 'pricing' && <PricingEvidence study={study} />}
    {panel === 'allocation' && <AllocationEvidence study={study} />}
    <details className="assumptions"><summary>Study scope and data limits</summary><ul>{study.scope.map(item => <li key={item}>{item}</li>)}</ul></details>
  </Panel>;
}

export function ExplainConsole({ context, reference }: { context?: string; reference?: string }) {
  const topics = ['workspace', 'contract', 'pricing', 'allocation', 'booking', 'job', 'experiment'];
  const initial = topics.includes(context ?? '') ? context as Topic : 'workspace';
  const [topic, setTopic] = useState<Topic>(initial);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [study, setStudy] = useState<Study | null>(null);
  const [model, setModel] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState(0);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    api<{ model_assistance: boolean; study_ready: boolean }>('/explain/options').then(options => {
      setModel(options.model_assistance);
      if (options.study_ready) return api<Study>('/explain/study').then(setStudy);
    }).catch(failure => setError(message(failure))).finally(() => setLoaded(true));
  }, []);
  useEffect(() => {
    let live = true;
    const ref = topic === initial ? reference : undefined;
    const refresh = () => post<Answer>('/explain/answer', { topic, ref }).then(value => {
      if (live) setAnswer(value);
    }).catch(failure => { if (live) setError(message(failure)); });
    setAnswer(null); setError(''); setStep(0);
    void refresh();
    const timer = ref ? window.setInterval(refresh, 4500) : undefined;
    return () => { live = false; if (timer) window.clearInterval(timer); };
  }, [topic, initial, reference]);
  async function ask(event: FormEvent, enhance: boolean) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const response = await post<Answer>('/explain/answer', { topic, question, enhance, ref: topic === initial ? reference : undefined });
      setAnswer(response); setStep(response.focus?.[0] ? response.focus[0] - 1 : 0);
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  const selected = answer?.steps[Math.min(step, Math.max(0, answer.steps.length - 1))];
  return <Page title="Explainable AI" subtitle="Understand the next action, trace decisions, and inspect the measured research evidence."
    action={<div className="feed-status fresh"><GitBranch size={16} />Evidence-linked guidance</div>}>
    <Panel title="Guides and decision trace" action={<BookOpen size={20} className="muted" />}>
      <div className="button-row">{guides.map(([id, text]) => <button key={id} className={'button ' + (topic === id ? 'primary' : 'secondary')}
        aria-pressed={topic === id} onClick={() => setTopic(id)}>{text}</button>)}
        {reference && <button className={'button ' + (topic === initial ? 'primary' : 'secondary')} onClick={() => setTopic(initial)}>Selected record</button>}
      </div>
      {error && <Notice>{error}</Notice>}
      {!answer ? <Loading /> : <div className="guide-layout">
        <div className="stack"><div className="split"><h3>{answer.title}</h3><Status value={answer.status} /></div>
          <div className="guide-steps">{answer.steps.map((row, index) => <button type="button" key={row.id}
            className={'guide-step ' + (selected === row ? 'selected' : '')} aria-pressed={selected === row} onClick={() => setStep(index)}>
            <span>{index + 1}</span>{stepTitle(row.title)}{answer.focus?.includes(row.id) && <CheckCircle2 size={15} />}</button>)}</div>
        </div>
        {selected && <div className="guide-content"><small>Step {selected.id} of {answer.steps.length}</small><h3>{stepTitle(selected.title)}</h3><p>{selected.detail}</p>
          {selected.evidence != null && <div className="hash"><small>Evidence reference</small><code>{selected.evidence}</code></div>}
          <div className="button-row"><a className="button primary" href={'#' + selected.link}>Open related screen <ArrowRight size={16} /></a>
            <button className="button secondary" disabled={step >= answer.steps.length - 1} onClick={() => setStep(step + 1)}>Next step</button></div>
        </div>}
      </div>}
      {(!reference || topic !== initial) && <form className="guide-question" onSubmit={event => { void ask(event, false); }}>
        <label>Find a relevant step<input value={question} maxLength={360} onChange={event => setQuestion(event.target.value)} placeholder="How do I handle an expired quote?" /></label>
        <div className="button-row"><button className="button secondary" disabled={busy}>Find guidance</button>
          {model && <button className="button secondary" type="button" disabled={busy || !question.trim()} onClick={event => { void ask(event, true); }}>
            {busy ? 'Reviewing…' : 'Ask Groq to rank guidance'}</button>}</div>
        <small>{answer?.source ?? 'Deterministic evidence'}{answer?.provider_status ? ' · Local guidance used' : ''}</small>
        {model && <small>Groq receives your question and public guide titles. Keep private details out of the question.</small>}
      </form>}
    </Panel>
    {study ? <ResearchEvidence study={study} /> : loaded && <Panel title="Publication comparisons"><Empty title="Study report unavailable">Run the publication study to populate the metrics and model views.</Empty></Panel>}
  </Page>;
}
