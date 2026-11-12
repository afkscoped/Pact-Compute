import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, CheckCircle2, Cpu, Download, GitBranch, Radio, RefreshCw } from 'lucide-react';
import { api, date, Empty, go, label, LinkButton, Loading, message, money, Notice, num, Page, Panel, post, RetryNotice, Status,
  type Candidate, type Policy, type Runner, type User } from './shared';
import { encodeImage } from './operations';
import { bookingGuidance, offerBadges, SORTS, sortOffers, type SortKey } from './offers';

type Offer = { id: string; title: string; device: string; producer: string; vram_mib: number; zone: string | null; starts_at: number;
  ends_at: number; rate_cents: number; status: string; available: boolean; available_at: number | null; fresh_at: number; own: boolean };
type Quote = { id: string | null; offer_id: string; policy_id: string; expires_at?: number; selected?: Candidate; candidates: Candidate[] };
export type Protocol = { version: string; verdict: string; state: string; labels: Record<string, string>;
  steps: { event: string; from: string; to: string; at: number; status: string; errors: string[]; evidence: string | number | null }[] };
type Booking = { id: string; offer: string; title: string; party: 'consumer' | 'producer'; status: string; accepted_at: number;
  start_at: number; deadline_at: number; rate_cents: number; maximum_charge_cents: number; usage_cents: number | null;
  duration_s: number | null; energy_kwh: number | null; artifact_sha256: string | null; job_id: string | null; protocol?: Protocol };

function useExchange<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState(false);
  const updater = useRef<() => void>(() => {});
  useEffect(() => {
    let active = true;
    let loading = false;
    let queued = false;
    const refresh = async () => {
      if (loading) { queued = true; return; }
      loading = true;
      try {
        const value = await api<T>(path);
        if (active) { setData(value); setError(''); }
      } catch (failure) {
        if (active) setError(message(failure));
      } finally {
        loading = false;
        if (active && queued) { queued = false; void refresh(); }
      }
    };
    updater.current = refresh;
    setData(null);
    void refresh();
    const stream = new EventSource('/api/v1/market/events');
    stream.onopen = () => setConnected(true);
    stream.onerror = () => setConnected(false);
    stream.addEventListener('snapshot', refresh);
    stream.addEventListener('update', refresh);
    const fallback = window.setInterval(refresh, 12000);
    return () => { active = false; window.clearInterval(fallback); stream.close(); };
  }, [path]);
  return { data, error, connected, refresh: () => updater.current() };
}

function LiveLabel({ connected }: { connected: boolean }) {
  return <span className={'feed-status ' + (connected ? 'fresh' : '')}><Radio size={15} />{connected ? 'Live updates' : 'Refreshing snapshots'}</span>;
}

function localInput(epoch: number) {
  const value = new Date(epoch * 1000);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function Exchange({ user, runners, policies }: { user: User; runners: Runner[]; policies: Policy[] }) {
  const { data, error, connected, refresh } = useExchange<Offer[]>('/market/offers');
  const producer = ['admin', 'operator', 'producer'].includes(user.role);
  const buyer = ['admin', 'consumer', 'submitter'].includes(user.role);
  const [offering, setOffering] = useState(false);
  const [runnerId, setRunnerId] = useState('');
  const [offerTitle, setOfferTitle] = useState('Image embedding capacity');
  const [start, setStart] = useState(() => localInput(Date.now() / 1000));
  const [end, setEnd] = useState(() => localInput(Date.now() / 1000 + 2 * 3600));
  const [rate, setRate] = useState('2.50');
  const [selection, select] = useState('');
  const [policyId, setPolicyId] = useState('');
  const [jobTitle, setJobTitle] = useState('Image embedding batch');
  const [count, setCount] = useState(4);
  const [files, setFiles] = useState<File[]>([]);
  const [flex, setFlex] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [now, setNow] = useState(() => Date.now() / 1000);
  const [search, setSearch] = useState('');
  const [availableOnly, setAvailableOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>('soonest');
  const [problem, setProblem] = useState('');
  const [busy, setBusy] = useState('');
  const approved = policies.filter(item => item.status === 'approved');
  const offer = data?.find(item => item.id === selection);
  const expires = quote?.expires_at ? Math.max(0, Math.ceil(quote.expires_at - now)) : 0;
  const remaining = files.length || count;
  useEffect(() => {
    if (!selection) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { select(''); setQuote(null); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [selection]);
  useEffect(() => {
    if (!quote?.expires_at) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [quote?.expires_at]);

  async function execute(name: string, operation: () => Promise<void>) {
    if (busy) return;
    setBusy(name); setProblem('');
    try { await operation(); }
    catch (failure) { setProblem(message(failure)); }
    finally { setBusy(''); }
  }
  function publish(event: FormEvent) {
    event.preventDefault();
    void execute('publish', async () => {
      await post('/market/offers', { runner_id: runnerId || runners[0]?.id, title: offerTitle,
        starts_at: new Date(start).getTime() / 1000, ends_at: new Date(end).getTime() / 1000, rate_cents: Math.round(Number(rate) * 100) });
      setOffering(false); refresh();
    });
  }
  function getQuote(event: FormEvent) {
    event.preventDefault();
    void execute('quote', async () => {
      setNow(Date.now() / 1000);
      setQuote(await post<Quote>('/market/quotes', { offer_id: selection, policy_id: policyId || approved[0]?.id,
        title: jobTitle, sample_count: remaining, flexible: flex }));
    });
  }
  function confirm() {
    if (!quote?.id) return;
    const id = quote.id;
    void execute('confirm', async () => {
      try {
        const result = await post<Booking>('/market/quotes/' + id + '/confirm', { images: await Promise.all(files.map(encodeImage)) });
        go('/bookings/' + result.id);
      } catch (error) {
        if (/expired|slot or terms changed/.test(message(error))) setQuote(null);
        throw error;
      }
    });
  }
  function toggle(item: Offer) {
    void execute(item.id, async () => {
      await api('/market/offers/' + item.id, { method: 'PATCH', body: JSON.stringify({ status: item.status === 'paused' ? 'published' : 'paused' }) });
      refresh();
    });
  }
  const badges = offerBadges(data ?? []);
  const list = sortOffers((data ?? []).filter(item => (!availableOnly || item.available)
    && [item.title, item.producer, item.device, item.zone].join(' ').toLowerCase().includes(search.toLowerCase())), sort);
  return <Page title={user.role === 'producer' ? 'Producer exchange' : 'GPU exchange'}
    subtitle={user.role === 'producer' ? 'Publish verified capacity and manage offer availability.' : 'Compare capacity, review the terms, and reserve a GPU for an approved workload.'}
    action={<div className="button-row"><LiveLabel connected={connected} />{producer && <button className="button primary" onClick={() => setOffering(!offering)}>{offering ? 'Close publisher' : 'Publish capacity'}</button>}</div>}>
    {error && <RetryNotice onRetry={refresh}>{error}</RetryNotice>}{problem && <Notice>{problem}</Notice>}
    {offering && <Panel title="Publish capacity" subtitle="A producer can pause future quotes from the listing. Existing reservations keep their terms.">
      <form className="stack" onSubmit={publish}>
        <div className="form-grid">
          <label>Offer name<input value={offerTitle} onChange={event => setOfferTitle(event.target.value)} required maxLength={120} /></label>
          <label>Producer runner<select value={runnerId || runners[0]?.id || ''} onChange={event => setRunnerId(event.target.value)} required>
            {!runners.length && <option value="">No enrolled runners</option>}{runners.map(item => <option key={item.id} value={item.id}>{item.name} · {item.device}</option>)}</select></label>
          <label>Window start<input type="datetime-local" value={start} onChange={event => setStart(event.target.value)} required /></label>
          <label>Window end<input type="datetime-local" value={end} onChange={event => setEnd(event.target.value)} required /></label>
          <label>Credits per GPU-hour<input type="number" min="0" max="1000" step=".01" value={rate} onChange={event => setRate(event.target.value)} required /></label>
        </div>
        <button className="button primary" disabled={!!busy || !runners.length}>{busy === 'publish' ? 'Publishing…' : 'Publish offer'}</button>
      </form>
    </Panel>}
    <div className={offer && buyer ? 'exchange-layout' : ''}>
      <Panel title="Capacity offers" action={<button className="button secondary" onClick={refresh}><RefreshCw size={15} />Refresh</button>}>
        <div className="market-filters"><input aria-label="Filter capacity" placeholder="Filter by GPU, producer, or region" value={search} onChange={event => setSearch(event.target.value)} />
          <label className="check"><input type="checkbox" checked={availableOnly} onChange={event => setAvailableOnly(event.target.checked)} />Available only</label>
          <label className="sort-by">Sort by<select value={sort} onChange={event => setSort(event.target.value as SortKey)}>{SORTS.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label></div>
        <p className="sr-only" role="status">{list.length} offer{list.length === 1 ? '' : 's'} shown, sorted by {SORTS.find(item => item.key === sort)?.label}.</p>
        {data === null ? <Loading /> : !list.length ? <Empty title="No matching offers" icon={<Cpu size={24} />}>Publish capacity or change the search filters.</Empty>
          : <div className="offer-grid">{list.map(item => <article className={'offer-card ' + (item.id === selection ? 'selected' : '')} key={item.id}>
            <div className="split"><div className="runner-icon"><Cpu size={18} /></div><Status value={item.status === 'paused' ? 'paused' : item.available ? 'available' : 'unavailable'} /></div>
            <h3>{item.title}</h3>{!!badges[item.id]?.length && <div className="badges" aria-label="Best on">{badges[item.id].map(text => <span className="badge" key={text}>{text}</span>)}</div>}<p>{item.producer} · {item.device}</p>
            <div className="form-facts"><span>GPU memory <b>{num(item.vram_mib / 1024)} GiB</b></span><span>Grid zone <b>{item.zone || 'Unverified'}</b></span>
              <span>Hourly rate <b>{money(item.rate_cents)}</b></span><span>First available <b>{date(item.available_at)}</b></span></div>
            <small>Window ends {date(item.ends_at)} · Verified {date(item.fresh_at)}</small>
            <div className="button-row">
              {buyer && <button className="button secondary" aria-label={'Request quote for ' + item.title} disabled={!item.available || !!busy} onClick={() => { select(item.id); setQuote(null); setProblem(''); }}>
                Request quote <ArrowRight size={15} /></button>}
              {producer && item.own && <button className="button ghost" disabled={!!busy} onClick={() => toggle(item)}>
                {busy === item.id ? 'Saving…' : item.status === 'paused' ? 'Resume offer' : 'Pause offer'}</button>}
            </div>
          </article>)}</div>}
      </Panel>
      {offer && buyer && <Panel title="Request quote" subtitle={offer.title} action={<button className="button ghost" onClick={() => { select(''); setQuote(null); }}>Close</button>}>
        {!approved.length && <Notice type="info">An approved agreement is required. <a href="#/agreements">Open Agreements</a> to review your options.</Notice>}
        <form className="stack" onSubmit={getQuote}>
          <label>Job name<input value={jobTitle} onChange={event => { setJobTitle(event.target.value); setQuote(null); }} required maxLength={120} /></label>
          <label>Agreement<select value={policyId || approved[0]?.id || ''} onChange={event => { setPolicyId(event.target.value); setQuote(null); }} required>
            {!approved.length && <option value="">Choose an approved policy</option>}{approved.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
          <label>Image count<input type="number" min={1} max={16} value={remaining} disabled={!!files.length} onChange={event => { setCount(Number(event.target.value)); setQuote(null); }} /></label>
          <label>Input images (optional)<input type="file" multiple accept="image/png,image/jpeg,image/webp" onChange={event => {
            const chosen = Array.from(event.target.files ?? []);
            if (chosen.length > 16 || chosen.some(file => file.size > 1_000_000)) { setProblem('Choose up to 16 images of at most 1 MB each.'); event.target.value = ''; setFiles([]); }
            else { setFiles(chosen); setProblem(''); }
            setQuote(null);
          }} /></label>
          <label className="check"><input type="checkbox" checked={flex} onChange={event => { setFlex(event.target.checked); setQuote(null); }} />Allow deferral within the agreement</label>
          <button className="button primary" disabled={!approved.length || !!busy}>{busy === 'quote' ? 'Checking eligibility…' : 'Get quote'}</button>
        </form>
        {quote && <div className="quote-summary">
          {quote.selected && quote.id ? <>
            <div className="split"><strong>Reservation terms</strong><Status value={expires ? 'quoted' : 'expired'} /></div>
            <div className="form-facts"><span>Estimated start <b>{date(quote.selected.start)}</b></span>
              <span>Maximum charge <b>{money(quote.selected.envelope_cents)}</b></span><span>Quoted estimate <b>{money(quote.selected.quote_cents)}</b></span>
              <span>Quote expires <b>{expires ? expires + ' seconds' : 'Expired'}</b></span></div>
            <small>Confirmation checks capacity again and pins the agreed maximum charge.</small>
            <button className="button primary" onClick={confirm} disabled={!expires || !!busy}><CheckCircle2 size={16} />{busy === 'confirm' ? 'Reserving…' : 'Confirm reservation'}</button>
          </> : <><Notice type="info">The selected capacity cannot meet these terms.</Notice><ul className="reason-list">
            {quote.candidates.flatMap(item => item.reasons).map((reason, index) => <li key={index}>{reason.message}</li>)}</ul></>}
        </div>}
      </Panel>}
    </div>
  </Page>;
}

export function Bookings() {
  const { data, error, connected, refresh } = useExchange<Booking[]>('/market/bookings');
  return <Page title="Bookings" subtitle="Shared reservations and usage from your side of the exchange." action={<LiveLabel connected={connected} />}>
    {error && <RetryNotice onRetry={refresh}>{error}</RetryNotice>}
    <Panel title="Booking history">{!data ? <Loading /> : !data.length ? <Empty title="No bookings yet">A confirmed quote creates a booking for both parties.</Empty>
      : <div className="table-wrap"><table><thead><tr><th>Workload</th><th>Offer</th><th>Role</th><th>Status</th><th>Charge</th></tr></thead><tbody>
        {data.map(item => <tr key={item.id}><td><a className="table-link" href={'#/bookings/' + item.id}>{item.title}</a></td><td>{item.offer}</td>
          <td>{label(item.party)}</td><td><Status value={item.status} /></td><td>{money(item.usage_cents)}</td></tr>)}
      </tbody></table></div>}
    </Panel>
  </Page>;
}

export function ProtocolTimeline({ protocol }: { protocol: Protocol }) {
  const [index, setIndex] = useState(0);
  const step = protocol.steps[Math.min(index, Math.max(0, protocol.steps.length - 1))];
  return <div className="protocol-timeline">
    <div className="split"><strong>{protocol.labels[protocol.state]}</strong><Status value={protocol.verdict} /></div>
    {step ? <><div className="trace-steps" aria-label="Protocol transitions">{protocol.steps.map((entry, position) => <button className={'trace-step ' + (step === entry ? 'selected' : '')}
      type="button" key={position} onClick={() => setIndex(position)} aria-pressed={step === entry}><span>{position + 1}</span>{entry.event.replace(/([a-z])([A-Z])/g, '$1 $2')}</button>)}</div>
      <div className="step-inspection"><div><small>Previous state</small><strong>{protocol.labels[step.from]}</strong></div><ArrowRight size={19} />
        <div><small>Next state</small><strong>{protocol.labels[step.to]}</strong></div><Status value={step.status} /></div>
      <small>{date(step.at)} · Evidence {step.evidence ?? '—'}</small>
      {step.errors.length > 0 && <Notice>{step.errors.map(label).join(' · ')}</Notice>}
      <div className="button-row"><button className="button secondary" onClick={() => setIndex(index - 1)} disabled={!index}>Previous step</button>
        <button className="button secondary" onClick={() => setIndex(index + 1)} disabled={index >= protocol.steps.length - 1}>Next step</button></div>
    </> : <Empty title="No execution evidence yet" />}
  </div>;
}

export function BookingDetail({ id }: { id: string }) {
  const { data, error, connected, refresh } = useExchange<Booking>('/market/bookings/' + id);
  if (error && !data) return <RetryNotice onRetry={refresh}>{error}</RetryNotice>;
  if (!data) return <Loading label="Loading booking" />;
  const guidance = bookingGuidance(data.status, data.party);
  return <Page title={data.title} subtitle={'Booking ' + data.id.slice(0, 10) + ' · ' + data.offer} action={<div className="button-row"><a className="button ghost" href="#/bookings">← All bookings</a><LiveLabel connected={connected} /></div>}>
    {error && <RetryNotice onRetry={refresh}>{error}</RetryNotice>}
    <div className="content-grid">
      <section className={'guidance ' + guidance.tone} aria-labelledby="booking-guidance">
        <small>What this means</small><h2 id="booking-guidance">{guidance.headline}</h2><p>{guidance.detail}</p>
      </section>
      <Panel title="Shared usage receipt" subtitle="Internal compute credits" action={<Status value={data.status} />}>
        <div className="form-facts"><span>Accepted <b>{date(data.accepted_at)}</b></span><span>Deadline <b>{date(data.deadline_at)}</b></span>
          <span>Reserved start <b>{date(data.start_at)}</b></span><span>Maximum charge <b>{money(data.maximum_charge_cents)}</b></span>
          <span>Recorded usage <b>{money(data.usage_cents)}</b></span><span>Execution time <b>{data.duration_s == null ? 'Awaiting usage' : num(data.duration_s) + ' s'}</b></span>
          <span>GPU board energy <b>{data.energy_kwh == null ? 'Unavailable' : num(data.energy_kwh * 1000, 4) + ' Wh'}</b></span></div>
        {data.artifact_sha256 && <div className="hash"><small>Artifact SHA-256</small><code>{data.artifact_sha256}</code></div>}
        <div className="button-row"><a className="button secondary" href={'/api/v1/market/bookings/' + id + '/receipt'}><Download size={16} />Receipt</a>
          {data.job_id && <LinkButton to={'/jobs/' + data.job_id}>Job evidence</LinkButton>}</div>
      </Panel>
      <Panel title="Executable protocol" subtitle="Inspect each observed transition and the evidence that supports it." action={<LinkButton to={'/explain/booking/' + id}>Explain</LinkButton>}>
        {data.protocol && <ProtocolTimeline protocol={data.protocol} />}
      </Panel>
    </div>
  </Page>;
}
