import { useEffect, useState, type FormEvent } from 'react';
import { Check, Copy, UserPlus } from 'lucide-react';
import { api, date, message, Notice, Page, Panel, Status, type User } from './shared';

type Invitation = { id: string; role: string; status: string; created_at: number; expires_at: number };
type Membership = { org_id: string; organization: string; role: string; home: boolean; active: boolean };

export function WorkspaceSwitcher({ user }: { user: User }) {
  const [spaces, setSpaces] = useState<Membership[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { api<Membership[]>('/memberships').then(setSpaces).catch(() => setSpaces([])); }, [user.organization, user.role]);
  if (spaces.length < 2) return null;
  const active = spaces.find(space => space.active)?.org_id ?? '';
  async function change(orgId: string) {
    setError('');
    try { await api('/session/workspace', { method: 'POST', body: JSON.stringify({ org_id: orgId }) }); window.location.hash = '#/'; window.location.reload(); }
    catch (failure) { setError(message(failure)); }
  }
  return <div className="workspace-switch">
    <label>Switch workspace<select value={active} onChange={event => void change(event.target.value)}>
      {spaces.map(space => <option key={space.org_id} value={space.org_id}>{space.organization} ({space.role})</option>)}
    </select></label>
    {error && <small role="alert">{error}</small>}
  </div>;
}

export function Team({ user }: { user: User }) {
  const [items, setItems] = useState<Invitation[] | null>(null);
  const [role, setRole] = useState('reviewer');
  const [issued, setIssued] = useState('');
  const [copied, setCopied] = useState(false);
  const [joinCode, setJoinCode] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const canInvite = ['producer', 'consumer', 'admin'].includes(user.role);
  const load = () => api<Invitation[]>('/invitations').then(setItems).catch(failure => { setItems([]); setError(message(failure)); });
  useEffect(() => { if (canInvite) void load(); else setItems([]); }, [canInvite]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(''); setCopied(false);
    try {
      const created = await api<{ code: string }>('/invitations', { method: 'POST', body: JSON.stringify({ role }) });
      setIssued(created.code); await load();
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function revoke(id: string) {
    setError('');
    try { await api('/invitations/' + id, { method: 'DELETE' }); await load(); }
    catch (failure) { setError(message(failure)); }
  }
  async function join(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(''); setNotice('');
    try {
      const joined = await api<{ organization: string; role: string }>('/invitations/accept', { method: 'POST', body: JSON.stringify({ code: joinCode.trim() }) });
      setNotice('You joined ' + joined.organization + ' as ' + joined.role + '. Reloading…');
      window.setTimeout(() => { window.location.hash = '#/'; window.location.reload(); }, 900);
    } catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(issued); setCopied(true); } catch { setCopied(false); }
  }
  return <Page title="Team" subtitle="Invite people into this workspace or join another one with an invitation code.">
    {error && <Notice>{error}</Notice>}
    {notice && <Notice type="success">{notice}</Notice>}
    <div className="content-grid">
      {canInvite && <Panel title="Invite a colleague" subtitle="A reviewer approves your agreements, so consumers need one before booking">
        <form className="stack" onSubmit={create}>
          <label>Role<select value={role} onChange={event => setRole(event.target.value)}>
            <option value="reviewer">Reviewer (approves agreements)</option>
            {(user.role === 'producer' || user.role === 'consumer') && <option value={user.role}>{user.role === 'producer' ? 'Producer' : 'Consumer'} (same access as you)</option>}
          </select></label>
          <div className="button-row"><button className="button" type="submit" disabled={busy}><UserPlus size={15} />Create invitation code</button></div>
        </form>
        {issued && <Notice type="success">Send this one-time code privately. It is shown only now and expires in 7 days: <code>{issued}</code>
          <div className="button-row"><button className="button secondary" type="button" onClick={copy}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? 'Copied' : 'Copy code'}</button></div></Notice>}
      </Panel>}
      <Panel title="Join a workspace" subtitle="Already signed in? Enter a code you received. New people use “I have an invitation code” on the sign-in page.">
        <form className="stack" onSubmit={join}>
          <label>Invitation code<input value={joinCode} onChange={event => setJoinCode(event.target.value)} required minLength={20} maxLength={100} autoComplete="off" spellCheck={false} /></label>
          <div className="button-row"><button className="button secondary" type="submit" disabled={busy}>Join workspace</button></div>
        </form>
      </Panel>
    </div>
    {canInvite && <Panel title="Invitations" subtitle="Codes are never shown again after creation">
      {items === null ? <p className="muted">Loading invitations…</p> : items.length === 0 ? <p className="muted">No invitations yet. Create one above.</p> :
        <div className="stack">{items.map(item => <div key={item.id} className="form-facts">
          <span>Role <b>{item.role}</b></span><span>Status <Status value={item.status} /></span><span>Expires <b>{date(item.expires_at)}</b></span>
          {item.status === 'pending' && <button className="button secondary" type="button" onClick={() => void revoke(item.id)}>Revoke</button>}
        </div>)}</div>}
    </Panel>}
  </Page>;
}
