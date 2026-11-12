import { useEffect, useState } from 'react';
import { LifeBuoy } from 'lucide-react';
import { api, date, Empty, Loading, message, Notice, Page, Panel, post, RetryNotice, Status } from './shared';
import { canResolve, evidenceText, noteProblem, resolveBody, safeHref, type Incident } from './incidents';

function IncidentCard({ incident, me, onChange }: { incident: Incident; me: string; onChange: () => void }) {
  const [action, setAction] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const choices = canResolve(incident);
  const mine = !incident.owner || incident.owner === me;
  const chosen = action || choices[0] || '';
  async function call(path: string, body?: unknown) {
    setBusy(true); setError('');
    try { await post('/incidents/' + incident.id + '/' + path, body); setNote(''); onChange(); }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <article className="rule-card" aria-label={incident.title}>
    <div className="split"><strong>{incident.title}</strong><Status value={incident.status === 'open' ? 'pending' : incident.status} /></div>
    <small>{incident.subject.label} · opened {date(incident.opened_at)} · owner {incident.owner ?? 'unassigned'}</small>
    <p>{incident.summary}</p>
    <h4>Evidence</h4>
    <ul>{incident.evidence.length ? incident.evidence.map((item, index) => {
      const href = safeHref(item.href);
      return <li key={index}>{item.type === 'link' ? (href ? <a href={href}>{evidenceText(item)}</a> : <span>{evidenceText(item)}</span>) : evidenceText(item)}</li>;
    }) : <li className="muted">No linked evidence.</li>}</ul>
    {incident.status === 'resolved'
      ? <Notice type="success"><strong>Resolved{incident.outcome ? ' · ' + incident.outcome : ''}</strong><p>{incident.resolution}</p></Notice>
      : <>
        <h4>Permitted actions</h4>
        <ul>{incident.permitted_actions.map(item => <li key={item.id}>{item.label}{item.api && <small> ({item.api})</small>}</li>)}</ul>
        {error && <Notice>{error}</Notice>}
        {!mine && <small>Owned by {incident.owner}. Only the owner can resolve it.</small>}
        {mine && !incident.owner && <div className="button-row"><button className="button secondary" disabled={busy} onClick={() => void call('claim')}>Take ownership</button></div>}
        {mine && choices.length > 0 && <>
          {choices.length > 1 && <label>Decision<select value={chosen} onChange={event => setAction(event.target.value)}>
            {incident.permitted_actions.filter(item => choices.includes(item.id)).map(item => <option key={item.id} value={item.id}>{item.id === 'accepted' ? 'Accept' : item.id === 'declined' ? 'Decline' : item.id}</option>)}</select></label>}
          <label>Resolution note (recorded)<input value={note} maxLength={500} onChange={event => setNote(event.target.value)} aria-invalid={!!note && !!noteProblem(note)} /></label>
          {!!note && noteProblem(note) && <small role="status">{noteProblem(note)}</small>}
          <div className="button-row"><button className="button primary" disabled={busy || !!noteProblem(note) || !chosen}
            onClick={() => void call('resolve', resolveBody(incident, chosen, note))}>{chosen === 'reconcile' ? 'Reconcile and resolve' : 'Record resolution'}</button></div>
        </>}
      </>}
  </article>;
}

export function Incidents({ user }: { user: { username: string } }) {
  const [view, setView] = useState<'active' | 'resolved'>('active');
  const [items, setItems] = useState<Incident[] | null>(null);
  const [error, setError] = useState('');
  const load = () => api<Incident[]>('/incidents?status=' + view).then(rows => { setItems(rows); setError(''); }).catch(failure => setError(message(failure)));
  useEffect(() => { setItems(null); void load(); const timer = window.setInterval(() => void load(), 6000); return () => window.clearInterval(timer); }, [view]);
  return <Page title="Incident queue" subtitle="Runners that went quiet, uncertain executions, rejected outputs and adjustment requests.">
    <Panel title={view === 'active' ? 'Needs attention' : 'Resolved'} action={<select aria-label="Show incidents" value={view} onChange={event => setView(event.target.value as 'active' | 'resolved')}>
      <option value="active">Active</option><option value="resolved">Resolved</option></select>}>
      {error && <RetryNotice onRetry={() => void load()}>{error}</RetryNotice>}
      {items === null && !error && <Loading label="Loading incidents" />}
      {items?.length === 0 && <Empty title={view === 'active' ? 'No open incidents' : 'No resolved incidents'} icon={<LifeBuoy size={24} />}>
        {view === 'active' ? 'Stale runners, uncertain attempts and rejected outputs appear here automatically.' : 'Resolutions are kept with who decided and why.'}</Empty>}
      <div className="stack">{items?.map(item => <IncidentCard key={item.id} incident={item} me={user.username} onChange={() => void load()} />)}</div>
    </Panel>
  </Page>;
}
