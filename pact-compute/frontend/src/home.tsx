import { useEffect, useState } from 'react';
import { ArrowRight, CalendarCheck, CheckCircle2, Circle, FileCheck2, Store } from 'lucide-react';
import { api, date, Empty, message, money, Page, Panel, RetryNotice, Status, type Policy, type User } from './shared';
import { nextAction, type BookingRow } from './journey';

export function ConsumerHome({ user, policies }: { user: User; policies: Policy[] }) {
  const [bookings, setBookings] = useState<BookingRow[] | null>(null);
  const [error, setError] = useState('');
  const load = () => api<BookingRow[]>('/market/bookings').then(rows => { setBookings(rows); setError(''); }).catch(failure => setError(message(failure)));
  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 8000);
    return () => window.clearInterval(timer);
  }, []);
  const approved = policies.filter(item => item.status === 'approved');
  const next = bookings ? nextAction(policies, bookings) : null;
  const steps = [
    { done: policies.length > 0, text: 'Write an agreement' },
    { done: approved.length > 0, text: 'Get it approved by a reviewer' },
    { done: !!bookings?.length, text: 'Reserve a GPU' },
    { done: !!bookings?.some(item => item.status === 'succeeded'), text: 'Download your results' },
  ];
  return <Page title={'Welcome, ' + user.username} subtitle={user.organization + ' · book approved GPU capacity for your workloads'}>
    {error && <RetryNotice onRetry={() => void load()}>{error}</RetryNotice>}
    {next && <section className="next-action" aria-labelledby="next-title">
      <small>Next step</small>
      <h2 id="next-title">{next.title}</h2>
      <p>{next.detail}</p>
      <a className="button primary" href={'#' + next.to}>{next.action}<ArrowRight size={16} /></a>
    </section>}
    <div className="content-grid">
      <Panel title="Your progress" subtitle="Everything happens in this order">
        <ol className="journey">{steps.map(step => <li key={step.text} className={step.done ? 'done' : ''}>
          {step.done ? <CheckCircle2 size={18} aria-hidden="true" /> : <Circle size={18} aria-hidden="true" />}
          <span>{step.text}<span className="sr-only">{step.done ? ' (done)' : ' (to do)'}</span></span></li>)}</ol>
        <div className="button-row"><a className="button secondary" href="#/agreements"><FileCheck2 size={15} />Agreements</a>
          <a className="button secondary" href="#/market"><Store size={15} />GPU exchange</a></div>
      </Panel>
      <Panel title="Recent bookings" action={<a className="button ghost" href="#/bookings"><CalendarCheck size={15} />All bookings</a>}>
        {bookings === null ? <p className="muted" role="status">Loading bookings…</p> : !bookings.length
          ? <Empty title="No bookings yet">Once you confirm a quote, your reservation appears here.</Empty>
          : <div className="table-wrap"><table><thead><tr><th>Workload</th><th>Status</th><th>Charge</th></tr></thead><tbody>
            {bookings.slice(0, 5).map(item => <tr key={item.id}><td><a className="table-link" href={'#/bookings/' + item.id}>{item.title}</a><br /><small>{date(item.accepted_at)}</small></td>
              <td><Status value={item.status} /></td><td>{money(item.usage_cents)}</td></tr>)}
          </tbody></table></div>}
      </Panel>
    </div>
  </Page>;
}
