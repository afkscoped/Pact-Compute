import { useEffect, useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, date, label, money, num, pct, Status } from './shared';

export type RuntimePlan = { method: 'fixed' | 'measured_p90'; baseline_s: number; runtime_s: number;
  sample_count: number; minimum_samples: number; observed_median_s: number | null;
  backtest?: { n: number; fixed_mae_s: number; quote_mae_s: number; fixed_coverage: number; quote_coverage: number } };
type Slot = { historical_start: number; delay_s: number; predicted_g: number | null; scored_g: number | null };
export type GridReplay = { snapshot_id: string; power_w: number; alternatives: number; earliest: Slot; selected: Slot };
export type QuoteEvidence = {
  policy_title: string; policy_sha256: string;
  clauses: { kind: string; source: string | null; observed: string | number | null; status: string; reasons: string[] }[];
  runtime: RuntimePlan;
  prices: { at: number; rate_cents: number; action: string }[];
  price_cases: { name: string; rate_cents: number; eligible: boolean; estimated_charge_cents: number | null;
    maximum_charge_cents: number | null; reason: string | null }[];
  live_runtime_carbon_g: number | null;
  replay: GridReplay | null;
};

type Stats = Record<string, number | null>;
type Study = {
  protocol: { comparison: Record<string, Stats> };
  pricing: { classification: Record<string, Stats>; fsm: { accuracy: number; majority_baseline?: { accuracy: number } };
    examples: { regime: string; intervention: { rounds: number[]; cut_response: number[];
      trajectory: { round: number; sham: number; cut: number }[] } }[] };
  scheduler: Record<string, { summary: Record<string, Stats>; config: { seeds: number; jobs: number };
    paired_carbon_vs_policy: Record<string, { interval95: [number, number] | null }> }>;
};

const series = ['#87adf4', '#9ee8b7'];
const tooltip = { background: '#17211a', border: '1px solid #385344', color: '#e8f0eb' };

function Comparison({ title, rows, format }: {
  title: string; rows: { name: string; value: number | null | undefined }[]; format: (value: number) => string;
}) {
  const max = Math.max(0, ...rows.map(row => row.value ?? 0));
  return <figure className="comparison-bars">
    <figcaption>{title}</figcaption>
    {rows.map(({ name, value }, index) => <div className="comparison-row" key={name}>
      <span>{name}</span><strong>{value == null ? 'Unavailable' : format(value)}</strong>
      <div className="comparison-track" aria-hidden="true"><span style={{ width: max ? 100 * (value ?? 0) / max + '%' : 0, background: series[index % 2] }} /></div>
    </div>)}
  </figure>;
}

export function RuntimeEvidence({ plan, actual }: { plan: RuntimePlan; actual?: number | null }) {
  return <div className="stack">
    <Comparison title="Runtime used to price and reserve this job" format={value => num(value, 2) + ' s'}
      rows={[{ name: 'Fixed image-count estimate', value: plan.baseline_s }, { name: 'Quote estimate', value: plan.runtime_s },
        ...(actual == null ? [] : [{ name: 'Recorded execution time', value: actual }])]} />
    <small>{plan.method === 'measured_p90'
      ? `Used the 90th percentile of ${plan.sample_count} completed matching jobs plus a startup margin.`
      : `Fixed estimate used. ${plan.sample_count} of ${plan.minimum_samples} matching completed jobs available.`}
      {' '}Matching uses this workspace, GPU, workload and image count.</small>
    {actual != null && <div className="form-facts">
      <span>Fixed estimate error<b>{num(Math.abs(plan.baseline_s - actual), 2)} s</b></span>
      <span>Quote estimate error<b>{num(Math.abs(plan.runtime_s - actual), 2)} s</b></span>
    </div>}
    {plan.backtest && <>
      <Comparison title={`Runtime estimate error across ${plan.backtest.n} later completed jobs`} format={value => num(value, 2) + ' s MAE'}
        rows={[{ name: 'Fixed estimate', value: plan.backtest.fixed_mae_s }, { name: 'Measured estimate', value: plan.backtest.quote_mae_s }]} />
      <small>Each estimate uses only earlier jobs. Actual runtime stayed within the estimate on {pct(plan.backtest.fixed_coverage)} of jobs with the fixed estimate and {pct(plan.backtest.quote_coverage)} with the measured estimate.</small>
    </>}
  </div>;
}

function PricingEvidence({ evidence, study }: { evidence: QuoteEvidence; study: Study | null }) {
  const [regime, setRegime] = useState('configured_response');
  const scenario = study?.pricing.examples.find(example => example.regime === regime);
  const pricing = study?.pricing.classification;
  return <div className="stack">
    <h4>How price changes affect this quote</h4>
    <small>Each case checks the same agreement, workload and availability at a different hourly rate.</small>
    <div className="table-wrap"><table><thead><tr><th>Case</th><th>Rate / h</th><th>Estimated charge</th><th>Check</th></tr></thead>
      <tbody>{evidence.price_cases.map(row => <tr key={row.name}><td>{row.name}</td><td>{money(row.rate_cents)}</td>
        <td>{money(row.estimated_charge_cents)}{row.maximum_charge_cents != null && <small> Max {money(row.maximum_charge_cents)}</small>}</td>
        <td>{row.eligible ? 'Eligible' : row.reason ?? 'Blocked'}</td></tr>)}</tbody></table></div>
    <h4>Posted prices on this GPU</h4>
    <div className="market-price-steps">{evidence.prices.map((row, index) => <div className="rule-card" key={index}>
      <strong>{money(row.rate_cents)}/h</strong><small>{label(row.action)} · {date(row.at)}</small>
    </div>)}</div>
    <small>These are published offers. The controlled experiment below holds demand and capacity fixed to test a rival’s response.</small>
    {study && <label>Controlled pricing case<select value={regime} onChange={event => setRegime(event.target.value)}>
      <option value="configured_response">Configured response</option><option value="expensive_control">High price, fixed response</option>
      <option value="scarcity_control">Scarcity control</option>
    </select></label>}
    {scenario && <>
      <div className="chart market-chart" role="img" aria-label="Rival price over time with a controlled undercut and with no undercut">
        <ResponsiveContainer width="100%" height="100%"><LineChart data={scenario.intervention.trajectory}>
          <CartesianGrid vertical={false} stroke="#29382e" /><XAxis dataKey="round" stroke="#b7c7be" />
          <YAxis width={48} stroke="#b7c7be" /><Tooltip contentStyle={tooltip} /><Legend />
          {scenario.intervention.rounds.map(round => <ReferenceLine key={round} x={round} stroke="#a0b8a7" strokeDasharray="4 4" />)}
          <Line dataKey="sham" name="No undercut" stroke={series[0]} dot={false} isAnimationActive={false} />
          <Line dataKey="cut" name="Controlled undercut" stroke={series[1]} dot={false} isAnimationActive={false} />
        </LineChart></ResponsiveContainer>
      </div>
      <div className="form-facts"><span>Rival price change after a cut<b>{num(scenario.intervention.cut_response[0], 0)} credit cents</b></span>
        <span>Price state model accuracy<b>{pct(study?.pricing.fsm.accuracy)}</b></span>
        <span>Most-common-action baseline<b>{pct(study?.pricing.fsm.majority_baseline?.accuracy)}</b></span></div>
      <a className="text-link" href="#/explain/pricing">Inspect the learned states and transitions</a>
    </>}
    {pricing && <Comparison title={`False alerts across ${(pricing.effect.fp ?? 0) + (pricing.effect.tn ?? 0)} held-out controls`} format={String}
      rows={[{ name: 'High-markup rule', value: pricing.markup.fp }, { name: 'Matched response test', value: pricing.effect.fp }]} />}
    {pricing && <small>Across the labelled test scenarios, F1 was {num(pricing.markup.f1, 3)} for high markup and {num(pricing.effect.f1, 3)} for the matched response test. These results come from controlled scenarios.</small>}
  </div>;
}

function replayTime(slot: Slot) {
  return new Date(slot.historical_start * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
}

export function GridComparison({ replay }: { replay: GridReplay }) {
  const delta = replay.earliest.scored_g != null && replay.selected.scored_g != null
    ? replay.selected.scored_g - replay.earliest.scored_g : null;
  return <div className="stack">
    <h4>Replay this quote against the GB grid</h4>
    <small>The current offer, workload and agreement use a fixed historical window with a day-ago planning signal and a {replay.power_w} W power assumption. This preview leaves the real reservation time unchanged.</small>
    <Comparison title="Historical emissions for the estimated runtime" format={value => num(value, 4) + ' g CO₂'}
      rows={[{ name: 'Earliest feasible start', value: replay.earliest.scored_g }, { name: 'Carbon-aware placement', value: replay.selected.scored_g }]} />
    <div className="table-wrap"><table><thead><tr><th>Placement</th><th>Replay start</th><th>Wait</th><th>Forecast g CO₂</th></tr></thead>
      <tbody>{[{ name: 'Earliest', slot: replay.earliest }, { name: 'Carbon aware', slot: replay.selected }].map(({ name, slot }) =>
        <tr key={name}><td>{name}</td><td>{replayTime(slot)}</td><td>{slot.delay_s} s</td><td>{num(slot.predicted_g, 4)}</td></tr>)}</tbody></table></div>
    {delta != null && <small>{num(delta, 4)} g CO₂ change for {replay.selected.delay_s - replay.earliest.delay_s} s additional wait.</small>}
    {replay.alternatives === 1 && <small>One feasible slot. To test a later start, enable deferral and use an agreement that permits it and prefers lower carbon.</small>}
    <small>NESO snapshot {replay.snapshot_id.slice(0, 12)} · Observed historical readings score the two placements.</small>
  </div>;
}

function AllocationEvidence({ evidence, study }: { evidence: QuoteEvidence; study: Study | null }) {
  const replay = evidence.replay;
  const benchmark = study?.scheduler.calibrated;
  const baseline = benchmark?.summary.policy_only;
  const fcfs = benchmark?.summary.fcfs;
  const proposed = benchmark?.summary.carbon_aware;
  const interval = benchmark?.paired_carbon_vs_policy.carbon_g?.interval95;
  return <div className="stack">
    <RuntimeEvidence plan={evidence.runtime} />
    <div className="rule-card"><strong>Live carbon estimate</strong><small>{evidence.live_runtime_carbon_g == null
      ? 'Unavailable for this quote. Requires a verified grid signal and power bound for the GPU.'
      : num(evidence.live_runtime_carbon_g, 4) + ' g CO₂ at the quote runtime and configured power bound'}</small></div>
    {replay ? <GridComparison replay={replay} /> : <small>A historical comparison needs an imported grid snapshot and at least one feasible slot.</small>}
    {benchmark && baseline && proposed && <div className="stack">
      <h4>Scheduler benchmark · {benchmark.config.seeds} paired runs</h4>
      <Comparison title="Modeled emissions per run" format={value => num(value, 0) + ' g CO₂'}
        rows={[{ name: 'First come, first served', value: fcfs?.carbon_g },
          { name: 'Policy only', value: baseline.carbon_g }, { name: 'Carbon aware', value: proposed.carbon_g }]} />
      <div className="table-wrap"><table><thead><tr><th>Scheduler</th><th>Completed / {benchmark.config.jobs}</th><th>P95 wait</th></tr></thead>
        <tbody>{fcfs && <tr><td>First come, first served</td><td>{num(fcfs.completed, 2)}</td><td>{num(fcfs.wait_p95_min)} min</td></tr>}
          <tr><td>Policy only</td><td>{num(baseline.completed, 2)}</td><td>{num(baseline.wait_p95_min)} min</td></tr>
          <tr><td>Carbon aware</td><td>{num(proposed.completed, 2)}</td><td>{num(proposed.wait_p95_min)} min</td></tr></tbody></table></div>
      {interval && <small>Paired change in modeled emissions, 95% interval {num(interval[0], 0)} to {num(interval[1], 0)} g CO₂ per run.</small>}
    </div>}
  </div>;
}

export function QuoteInspector({ evidence, policyId }: { evidence: QuoteEvidence; policyId: string }) {
  const [tab, setTab] = useState('agreement');
  const [study, setStudy] = useState<Study | null>(null);
  useEffect(() => {
    let active = true;
    void api<Study>('/explain/study').then(data => { if (active) setStudy(data); }).catch(() => {});
    return () => { active = false; };
  }, []);
  return <section className="quote-inspector stack" aria-label="Quote evidence">
    <div className="button-row">{[['agreement', 'Contract checks'], ['pricing', 'Provider pricing'], ['allocation', 'Scheduling comparison']].map(([id, name]) =>
      <button key={id} type="button" className={'button ' + (tab === id ? 'primary' : 'secondary')} aria-pressed={tab === id} onClick={() => setTab(id)}>{name}</button>)}</div>
    {tab === 'agreement' && <>
      <a className="text-link" href={'#/agreements/' + policyId}>{evidence.policy_title} · {evidence.policy_sha256.slice(0, 12)}</a>
      <div className="stack">{evidence.clauses.map((row, index) => <div className="rule-card" key={index}>
        <div className="split"><strong>{row.source ?? label(row.kind)}</strong><Status value={row.status} /></div>
        {row.observed != null && row.status !== 'not_requested' && <small>{clauseObservation(row.kind, row.observed)}</small>}
        {row.reasons.length > 0 && <small>{row.reasons.join(' · ')}</small>}
      </div>)}</div>
      {study && <Comparison title={`Unsafe approvals across ${study.protocol.comparison.temporal_monitor.n} held-out traces`} format={String}
        rows={[{ name: 'Event checklist', value: study.protocol.comparison.presence_baseline.unsafe_accepts },
          { name: 'Ordered protocol monitor', value: study.protocol.comparison.temporal_monitor.unsafe_accepts }]} />}
    </>}
    {tab === 'pricing' && <PricingEvidence evidence={evidence} study={study} />}
    {tab === 'allocation' && <AllocationEvidence evidence={evidence} study={study} />}
  </section>;
}

function clauseObservation(kind: string, observed: string | number) {
  if (typeof observed === 'string') return 'Runner reports ' + observed;
  switch (kind) {
    case 'min_vram_mib': return num(observed, 0) + ' MiB available on the runner';
    case 'gpu_count': return observed + ' GPU available for this slot';
    case 'max_charge_cents': return 'Maximum charge for this slot is ' + money(observed);
    case 'max_rate_cents': return 'Posted rate is ' + money(observed) + ' per GPU-hour';
    case 'carbon_limit_g': return 'Estimated reservation envelope is ' + num(observed, 4) + ' g CO₂';
    case 'deadline_seconds': return 'Planned finish within ' + num(observed, 0) + ' seconds of the quote';
    case 'deadline_utc': return 'Planned finish at ' + date(observed);
    case 'max_deferral_seconds': return 'Planned wait is ' + num(observed, 0) + ' seconds';
    default: return String(observed);
  }
}
