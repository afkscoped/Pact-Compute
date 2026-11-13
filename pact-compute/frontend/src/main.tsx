import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowRight, BookOpen, CalendarCheck, Cpu, Database, FileCheck2, FlaskConical, LayoutDashboard, LifeBuoy, ListOrdered, LogOut, Menu, ShieldCheck, Store, Users, X } from 'lucide-react';
import { AgreementView, Agreements, Capacity, JobView, NewJob, Overview, Queue } from './operations';
import { DataSources, Research, ResearchResult } from './research';
import { BookingDetail, Bookings, Exchange } from './exchange';
import { ExplainConsole } from './explain';
import { Team, WorkspaceSwitcher } from './team';
import { Incidents } from './incident-queue';
import { ConsumerHome } from './home';
import { api, go, Loading, message, Notice, post, RetryNotice, type Config, type Dataset, type Job, type Policy, type Run, type Runner, type User } from './shared';
import './style.css';

const nav = [
  { path: '/', title: 'Overview', icon: LayoutDashboard },
  { path: '/market', title: 'GPU exchange', icon: Store },
  { path: '/bookings', title: 'Bookings', icon: CalendarCheck },
  { path: '/jobs', title: 'Job queue', icon: ListOrdered },
  { path: '/agreements', title: 'Agreements', icon: FileCheck2 },
  { path: '/capacity', title: 'Compute capacity', icon: Cpu },
  { path: '/research', title: 'Research Lab', icon: FlaskConical },
  { path: '/data', title: 'Data sources', icon: Database },
  { path: '/incidents', title: 'Incidents', icon: LifeBuoy },
  { path: '/team', title: 'Team', icon: Users },
  { path: '/explain', title: 'Explainable AI', icon: BookOpen },
];

function Brand() {
  return <a className="brand" href="#/" aria-label="PACT Compute home"><span className="brand-mark"><Activity size={20} strokeWidth={2.7} /></span><span>PACT<span className="brand-divider">/</span>Compute</span></a>;
}

function Login({ signIn }: { signIn: (user: User) => void }) {
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [code, setCode] = useState('');
  const [username, setUsername] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [organization, setOrganization] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function switchMode() {
    const nextCreating = !creating && !joining;
    setJoining(false);
    setCode('');
    setCreating(nextCreating);
    setWorkspace(nextCreating ? 'consumer' : '');
    setUsername('');
    setOrganization('');
    setPassword('');
    setError('');
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (joining) {
        const user = await post<User>('/invitations/accept', { code: code.trim(), username, password });
        go('/agreements');
        signIn(user);
      } else if (creating) {
        const user = await post<User>('/accounts', { username, password, organization, role: workspace });
        go('/explain');
        signIn(user);
      } else {
        signIn(await post<User>('/session', { username, password, workspace }));
      }
    }
    catch (failure) { setError(message(failure)); }
    finally { setBusy(false); }
  }
  return <div className="login-shell">
    <div className="login-left"><Brand /><div><h1>GPU operations<br />with verifiable rules.</h1><p>Review service agreements, schedule real workloads, and inspect the evidence behind each decision.</p></div>
      <div className="login-footer"><ShieldCheck size={17} /> Policy approval · GPU execution · Independent audit</div></div>
    <main className="login-right"><form className="login-panel" onSubmit={submit} aria-labelledby="login-title">
      <div className="runner-icon"><ShieldCheck size={23} /></div>
      <h2 id="login-title">{joining ? 'Join with an invitation' : creating ? 'Create your account' : 'Sign in to your workspace'}</h2>
      <p>{joining ? 'Enter the code you were sent and choose a username and password. You will join the workspace that invited you.' : creating ? 'Create a workspace to offer GPU capacity or book it for your workloads.' : 'Choose the workspace assigned to your account.'}</p>
      {joining && <label>Invitation code<input value={code} required minLength={20} maxLength={100} autoComplete="off" spellCheck={false} onChange={event => setCode(event.target.value)} /></label>}
      {!joining && <label>{creating ? 'Account type' : 'Workspace'}<select value={workspace} required onChange={event => {
        const next = event.target.value;
        setWorkspace(next);
        setError('');
        if (!creating) { setUsername(''); setPassword(''); }
      }}>{!creating && <><option value="" disabled>Select your workspace</option><option value="operations">Operations and research</option></>}
        <option value="producer">Producer</option><option value="consumer">Consumer</option></select></label>}
      {creating && !joining && <label>Organization name<input value={organization} autoComplete="organization" required maxLength={100}
        onChange={event => setOrganization(event.target.value)} /></label>}
      <div className="login-field"><label>Username<input value={username} autoComplete="username" autoCapitalize="none" spellCheck={false}
        required maxLength={64} pattern={creating || joining ? '[a-z][a-z0-9._\\-]{1,63}' : undefined}
        aria-describedby={creating ? 'username-help' : undefined} onChange={event => setUsername(event.target.value)} /></label>
        {creating && <small id="username-help">Use 2–64 lowercase letters, numbers, dots, underscores, or hyphens. Start with a letter.</small>}</div>
      <div className="login-field"><label>Password<input key={creating ? 'new' : 'current'} value={password} type="password"
        autoComplete={creating || joining ? 'new-password' : 'current-password'} required minLength={creating || joining ? 12 : undefined} maxLength={200}
        aria-describedby={creating ? 'password-help' : undefined} onChange={event => setPassword(event.target.value)} /></label>
        {creating && <small id="password-help">Use at least 12 characters.</small>}</div>
      {error && <Notice>{error}</Notice>}
      <button className="button primary" disabled={busy}>
        {joining ? (busy ? 'Joining…' : 'Join workspace') : creating ? (busy ? 'Creating account…' : 'Create account') : (busy ? 'Signing in…' : 'Sign in')}<ArrowRight size={17} />
      </button>
      <div className="login-switch"><span>{creating ? 'Already have an account?' : 'New to PACT-Compute?'}</span>
        <button className="button secondary" type="button" disabled={busy} onClick={switchMode}>{creating || joining ? 'Back to sign in' : 'Create account'}</button>
        {!joining && <button className="button secondary" type="button" disabled={busy} onClick={() => { setJoining(true); setCreating(false); setUsername(''); setPassword(''); setError(''); }}>I have an invitation code</button>}
      </div>
    </form></main>
  </div>;
}

type WorkspaceData = { jobs: Job[]; runners: Runner[]; policies: Policy[]; runs: Run[]; datasets: Dataset[]; config: Config };

function Shell({ user, logout }: { user: User; logout: () => Promise<void> }) {
  const [route, setRoute] = useState(location.hash.slice(1) || '/');
  const [mobile, setMobile] = useState(false);
  const [data, setData] = useState<WorkspaceData | null>(null);
  const [error, setError] = useState('');
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState('');
  const [refreshAt, requestRefresh] = useState(0);
  const mainRef = useRef<HTMLElement>(null);
  const navigationRef = useRef<HTMLElement>(null);
  const navigationButtonRef = useRef<HTMLButtonElement>(null);
  const returnToNavigation = useRef(true);
  const participant = user.role === 'producer' || user.role === 'consumer';
  const links = participant ? nav.filter(item => (user.role === 'producer'
    ? ['/market', '/bookings', '/capacity', '/team', '/explain']
    : ['/', '/market', '/bookings', '/jobs', '/agreements', '/team', '/explain']).includes(item.path)).map(item => item.path === '/' && user.role === 'consumer' ? { ...item, title: 'Home' } : item) : nav.filter(item => item.path !== '/incidents' || ['admin', 'operator'].includes(user.role));
  const refresh = () => requestRefresh(value => value + 1);
  async function signOut() {
    setSigningOut(true);
    setSignOutError('');
    try { await logout(); }
    catch (failure) { setSignOutError('Could not sign out. ' + message(failure)); }
    finally { setSigningOut(false); }
  }
  useEffect(() => {
    const onHash = () => { returnToNavigation.current = false; setRoute(location.hash.slice(1) || '/'); setMobile(false); window.scrollTo(0, 0); mainRef.current?.focus({ preventScroll: true }); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  useEffect(() => {
    if (!mobile) return;
    const panel = navigationRef.current;
    panel?.querySelector<HTMLButtonElement>('button[aria-label="Close navigation"]')?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setMobile(false); return; }
      if (event.key !== 'Tab' || !panel) return;
      const targets = Array.from(panel.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), select:not(:disabled), [tabindex="0"]'))
        .filter(node => node.getClientRects().length > 0);
      const first = targets[0], last = targets.at(-1);
      if (!first || !last) return;
      if (!panel.contains(document.activeElement) || (event.shiftKey && document.activeElement === first)) {
        event.preventDefault(); (event.shiftKey ? last : first).focus();
      } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    const resize = () => { if (window.innerWidth > 825) setMobile(false); };
    document.addEventListener('keydown', keydown);
    window.addEventListener('resize', resize);
    return () => {
      document.removeEventListener('keydown', keydown);
      window.removeEventListener('resize', resize);
      if (returnToNavigation.current && navigationButtonRef.current?.getClientRects().length) navigationButtonRef.current.focus();
      else mainRef.current?.focus({ preventScroll: true });
    };
  }, [mobile]);
  useEffect(() => {
    let current = true;
    let inFlight = false;
    async function reload() {
      if (inFlight) return;
      inFlight = true;
      try {
        const [jobs, runners, policies, runs, datasets, config] = await Promise.all([
          api<Job[]>('/jobs'), api<Runner[]>('/runners'), api<Policy[]>('/policies'), api<Run[]>('/runs'),
          api<Dataset[]>('/datasets'), api<Config>('/config'),
        ]);
        if (current) { setData({ jobs, runners, policies, runs, datasets, config }); setError(''); }
      } catch (failure) { if (current) setError(message(failure)); }
      finally { inFlight = false; }
    }
    void reload();
    const timer = window.setInterval(reload, 4200);
    return () => { current = false; window.clearInterval(timer); };
  }, [refreshAt]);
  const visibleRoute = route === '/' && participant && user.role === 'producer' ? '/market' : route;
  const current = links.find(link => link.path === visibleRoute || (link.path !== '/' && visibleRoute.startsWith(link.path + '/'))) ?? links[0];
  let screen = null;
  if (data) {
    const { jobs, runners, policies, runs, datasets, config } = data;
    const id = route.split('/')[2] || '';
    if (visibleRoute === '/') screen = user.role === 'consumer' ? <ConsumerHome user={user} policies={policies} /> : <Overview {...{ jobs, runners, policies, runs }} />;
    else if (visibleRoute === '/market') screen = <Exchange {...{ user, runners, policies }} />;
    else if (route === '/bookings') screen = <Bookings />;
    else if (route.startsWith('/bookings/') && id) screen = <BookingDetail key={id} id={id} />;
    else if (route === '/explain' || route.startsWith('/explain/')) screen = <ExplainConsole key={route} context={id} reference={route.split('/')[3]} />;
    else if (route === '/jobs') screen = <Queue exchange={user.role === 'consumer'} />;
    else if (route === '/jobs/new') screen = user.role === 'consumer' ? <Exchange {...{ user, runners, policies }} /> : <NewJob policies={policies} config={config} onChange={refresh} canRevise={['admin', 'reviewer'].includes(user.role)} />;
    else if (route.startsWith('/jobs/') && id) screen = <JobView key={id} id={id} user={user} onChange={refresh} />;
    else if (route === '/agreements') screen = <Agreements policies={policies} config={config} onChange={refresh} canReview={['admin', 'reviewer'].includes(user.role)} />;
    else if (route.startsWith('/agreements/') && id) screen = <AgreementView key={id} id={id} onChange={refresh} />;
    else if (route === '/capacity') screen = <Capacity runners={runners} onChange={refresh} canEnroll={['producer', 'operator', 'admin'].includes(user.role)} />;
    else if (route === '/team') screen = <Team user={user} />;
    else if (route === '/incidents' && ['admin', 'operator'].includes(user.role)) screen = <Incidents user={user} />;
    else if (route === '/research') screen = <Research {...{ datasets, policies, runs }} onChange={refresh} />;
    else if (route.startsWith('/research/') && id) screen = <ResearchResult key={id} id={id} user={user} />;
    else if (route === '/data') screen = <DataSources datasets={datasets} onChange={refresh} />;
    else screen = <Notice>Page unavailable. <a href="#/">Open overview</a>.</Notice>;
  }
  const online = data?.runners.some(runner => runner.online);
  return <div className="shell">
    <button type="button" className="skip-link" inert={mobile} onClick={() => mainRef.current?.focus()}>Skip to main content</button>
    {mobile && <div className="scrim" aria-hidden="true" onClick={() => setMobile(false)} />}
    <aside ref={navigationRef} id="workspace-navigation" role={mobile ? 'dialog' : undefined} aria-modal={mobile || undefined}
      aria-label={mobile ? 'Navigation menu' : undefined} className={'sidebar ' + (mobile ? 'is-open' : '')}>
      <div className="sidebar-head"><Brand /><button className="icon-button mobile-only" onClick={() => setMobile(false)} aria-label="Close navigation"><X size={20} /></button></div>
      <div className="workspace"><span className="workspace-mark"><Cpu size={17} /></span><div><strong title={user.organization}>{user.organization}</strong><small>Compute workspace</small></div></div>
      <WorkspaceSwitcher user={user} />
      <nav aria-label="Primary">
        {links.map(({ path, title, icon: Icon }) => <div key={path} className={path === '/research' ? 'nav-section' : ''}>
          {path === '/research' && <span className="nav-caption">Experiments</span>}
          <a href={'#' + path} aria-current={current.path === path ? 'page' : undefined}><Icon size={18} /><span>{title}</span></a>
        </div>)}
      </nav>
      <div className="sidebar-foot">
        <div className="workspace-user"><div className="avatar">{user.username.slice(0, 2).toUpperCase()}</div>
          <div><strong>{user.username}</strong><small>{user.role}</small></div></div>
        {signOutError && <Notice>{signOutError}</Notice>}
        <button className="button secondary sign-out" type="button" disabled={signingOut} onClick={signOut}>
          <LogOut size={17} aria-hidden="true" />{signingOut ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    </aside>
    <div className="workspace-body" inert={mobile}>
      <header className="topbar"><div><button ref={navigationButtonRef} className="icon-button mobile-only" aria-label="Open navigation"
        aria-haspopup="dialog" aria-expanded={mobile} aria-controls="workspace-navigation" onClick={() => { returnToNavigation.current = true; setMobile(true); }}><Menu size={21} /></button><span>Workspace</span><span className="slash">/</span><strong>{current.title}</strong></div>
        <div className="topbar-right">{user.role !== 'consumer' && <span className="connection"><i className={online ? 'connected' : ''} />{online ? 'GPU connected' : 'GPU offline'}</span>}
          <span className="db-label">{data?.config.database ?? 'Connecting'}</span></div></header>
      <main className="main" id="main-content" tabIndex={-1} ref={mainRef}>{error && <Notice>{error}</Notice>}{screen ?? (!error && <Loading />)}</main>
    </div>
  </div>;
}

async function endSession() {
  await api('/session', { method: 'DELETE' });
  const url = new URL(location.href);
  url.searchParams.delete('start');
  url.hash = '';
  history.replaceState(history.state, '', url);
  window.scrollTo(0, 0);
}

function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [launchError, setLaunchError] = useState('');
  useEffect(() => {
    if (new URLSearchParams(location.search).get('start') === 'sign-in') {
      endSession().then(() => setUser(null)).catch(failure => setLaunchError(message(failure)));
    } else {
      api<User>('/session').then(setUser).catch(() => setUser(null));
    }
  }, []);
  async function logout() {
    await endSession();
    setUser(null);
  }
  if (launchError) return <main className="login-right"><div className="login-panel"><RetryNotice onRetry={() => location.reload()}>
    Could not open the sign-in page. {launchError}
  </RetryNotice></div></main>;
  if (user === undefined) return <Loading />;
  return user ? <Shell user={user} logout={logout} /> : <Login signIn={setUser} />;
}

createRoot(document.getElementById('root')!).render(<App />);
