import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Ban, Check, ChevronRight, ClipboardList, Compass, FileText, Home, Lightbulb, LockKeyhole, LogOut, MapPin, MessageCircle, Plus, RefreshCw, Search, Send, ShieldCheck, Sparkles, Star, Upload, UserRound, WalletCards, X, Zap } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const client = axios.create({ baseURL: API, withCredentials: true });
const nav = [['home', 'Home', Home], ['explore', 'Explore', Compass], ['requests', 'Requests', ClipboardList], ['profile', 'Profile', UserRound], ['insights', 'Insights', Lightbulb]];
const money = n => `₹${n}`;
const initials = name => (name || 'U').split(/\s+/).map(x => x[0]).join('').slice(0, 2).toUpperCase();

const STATUS_LABEL = {
  HIRE_REQUESTED: 'Hire requested', PROVIDER_ACCEPTED: 'Provider accepted', PAYMENT_SECURED: 'Payment secured',
  PROVIDER_COMPLETED: 'Work delivered', COMPLETED: 'Completed', DECLINED: 'Declined',
  RENTAL_REQUESTED: 'Rental requested', OWNER_ACCEPTED: 'Owner accepted', PICKED_UP: 'Picked up',
  RETURNED: 'Returned', RETURN_CONFIRMED: 'Return confirmed',
};
function nextActions(tx) {
  const s = tx.status;
  if (tx.kind === 'service') {
    if (s === 'HIRE_REQUESTED') return [['accept', 'Provider accepts', 'primary'], ['decline', 'Decline', 'secondary']];
    if (s === 'PROVIDER_ACCEPTED') return [['pay', `Pay ${money(tx.amount)} via UPI`, 'primary']];
    if (s === 'PAYMENT_SECURED') return [['complete', 'Provider marks delivered', 'primary']];
    if (s === 'PROVIDER_COMPLETED') return [['confirm', 'Confirm & release payment', 'primary']];
  } else {
    if (s === 'RENTAL_REQUESTED') return [['accept', 'Owner accepts', 'primary'], ['decline', 'Decline', 'secondary']];
    if (s === 'OWNER_ACCEPTED') return [['pay', `Pay ${money(tx.amount + tx.deposit)} via UPI`, 'primary']];
    if (s === 'PAYMENT_SECURED') return [['pickup', 'Mark picked up', 'primary']];
    if (s === 'PICKED_UP') return [['return', 'Mark returned', 'primary']];
    if (s === 'RETURNED') return [['confirm_return', 'Owner confirms · refund deposit', 'primary']];
  }
  return [];
}

function Badge({ children, tone = '' }) { return <span data-testid={`badge-${String(children).toLowerCase().replaceAll(' ', '-')}`} className={`badge ${tone}`}>{children}</span> }
function Avatar({ name, small = false }) { return <div data-testid={`avatar-${(name || '').toLowerCase().replaceAll(' ', '-')}`} className={`avatar ${small ? 'small' : ''}`}>{initials(name)}</div> }

/* ---------------- Auth (welcome + email + OTP) ---------------- */
function Auth({ onDone, initialError = '' }) {
  const [step, setStep] = useState('welcome');
  const [email, setEmail] = useState('harvey@student.nitandhra.ac.in');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState(initialError);
  const boxes = useRef([]);
  const role = email.toLowerCase().endsWith('@student.nitandhra.ac.in') ? 'Student' : email.toLowerCase().endsWith('@nitandhra.ac.in') ? 'Faculty' : null;
  const send = async () => { try { await client.post('/auth/send-otp', { email }); setError(''); setStep('otp'); } catch (e) { setError(e.response?.data?.detail || 'Use a valid NIT AP email'); } };
  const setDigit = (i, v) => { const d = v.replace(/\D/g, '').slice(-1); const n = [...otp]; n[i] = d; setOtp(n); if (d && boxes.current[i + 1]) boxes.current[i + 1].focus(); };
  const onKey = (i, e) => { if (e.key === 'Backspace' && !otp[i] && boxes.current[i - 1]) boxes.current[i - 1].focus(); };
  const verify = async () => { const code = otp.join(''); if (code.length < 6) { setError('Enter all 6 digits.'); return; } try { const r = await client.post('/auth/verify-otp', { email, otp: code }); onDone(r.data.user, r.data.token); } catch (e) { setError(e.response?.data?.detail || 'Invalid code'); } };
  const google = () => { /* REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH */ const redirectUrl = window.location.origin + '/'; window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`; };
  return (
    <main className="onboard-page">
      <div className="onboard-shell">
        <aside className="onboard-brand">
          <div><div className="logo"><span>↻</span> loop</div><p className="kicker">NIT AP · PILOT</p>
            <h1 className="brand-hero">Need it?<br />Find it.<br />Have it?<br /><em>Loop it.</em></h1>
            <p className="brand-copy">A campus marketplace for one-time skills and underused resources.</p>
            <div className="brand-quote">"Don't buy it. Don't learn it. Find someone who already can."</div>
          </div>
          <p className="tiny">Institutional email establishes campus affiliation. Student ID verification is required before student transactions.</p>
        </aside>
        <section className="onboard-panel">
          <div className="onboard-progress"><span className="on" /><span className={step === 'otp' ? 'on' : ''} /><span /><span /><span /></div>
          {step === 'welcome' && <div className="ob-step" data-testid="onboarding-welcome">
            <p className="eyebrow">WELCOME</p><h2>Welcome to Loop</h2><p className="muted">Your campus. Your skills. Your resources.</p>
            <label>Institutional email<input data-testid="institutional-email-input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="harvey@student.nitandhra.ac.in" /></label>
            <p className="tiny">Student: <b>name@student.nitandhra.ac.in</b> · Faculty: <b>name@nitandhra.ac.in</b></p>
            {role && <span className="role-pill" data-testid="detected-role-pill">{role} detected</span>}
            <button data-testid="send-otp-button" className="button primary wide" onClick={send}>Continue <ChevronRight size={17} /></button>
            <div className="or-line"><span>or</span></div>
            <button data-testid="google-sign-in-button" className="button google wide" onClick={google}>Continue with Google</button>
            <p className="tiny center">No password. We'll send a one-time code.</p>
          </div>}
          {step === 'otp' && <div className="ob-step" data-testid="onboarding-otp">
            <p className="eyebrow">EMAIL VERIFICATION</p><h2>Enter your code</h2><p className="muted">We sent a 6-digit OTP to <b>{email}</b>.</p>
            <div className="otp-row">{otp.map((d, i) => <input key={i} data-testid={`otp-box-${i}`} ref={el => boxes.current[i] = el} inputMode="numeric" maxLength="1" value={d} onChange={e => setDigit(i, e.target.value)} onKeyDown={e => onKey(i, e)} />)}</div>
            <p className="demo-note" data-testid="demo-otp-note"><Sparkles size={14} /> Demo code: <b>123456</b></p>
            <button data-testid="verify-otp-button" className="button primary wide" onClick={verify}>Verify email <Check size={17} /></button>
            <button data-testid="change-email-button" className="button secondary wide" onClick={() => { setStep('welcome'); setError(''); }}>Change email</button>
          </div>}
          {error && <p className="error" data-testid="auth-error"><X size={14} />{error}</p>}
        </section>
      </div>
    </main>
  );
}

function AuthCallback({ onDone, onError }) {
  const location = useLocation(); const navigate = useNavigate(); const processed = useRef(false);
  useEffect(() => {
    if (processed.current) return; processed.current = true;
    const sessionId = new URLSearchParams(location.hash.replace(/^#/, '')).get('session_id');
    if (!sessionId) { onError('Google sign-in did not return a valid session.'); navigate('/', { replace: true }); return; }
    client.post('/auth/google/session', { session_id: sessionId }).then(r => { onDone(r.data.user, r.data.token); navigate('/', { replace: true }); }).catch(e => { onError(e.response?.data?.detail || 'Google sign-in could not be completed.'); navigate('/', { replace: true }); });
  }, [location.hash, navigate, onDone, onError]);
  return <div className="auth-callback" data-testid="google-auth-callback" role="status">Signing you into Loop…</div>;
}

/* ---------------- Onboarding continuation (profile → ID → personalize) ---------------- */
const BRANCHES = ['Civil Engineering', 'Computer Science & Engineering', 'Electronics & Communication Engineering', 'Electrical & Electronics Engineering', 'Mechanical Engineering', 'Chemical Engineering', 'Metallurgical & Materials Engineering', 'Biotechnology', 'M.Tech'];
const YEARS = ['1st Year', '2nd Year', '3rd Year', '4th Year'];
const CHOICES = [['need', 'I need things', 'Find students who can help me.'], ['skill', 'I have skills to offer', 'Turn what I know into gigs.'], ['resource', 'I have useful resources', 'Lend or rent things I rarely use.']];

function Onboarding({ user, onDone }) {
  const faculty = user.role === 'faculty';
  const [step, setStep] = useState('profile');
  const [name, setName] = useState(user.name || '');
  const [branch, setBranch] = useState(user.branch || BRANCHES[0]);
  const [year, setYear] = useState(user.year || YEARS[2]);
  const [idStatus, setIdStatus] = useState(user.verification_status || 'Pending');
  const [choices, setChoices] = useState(new Set(user.personalization || []));
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();
  const stepIndex = { profile: 3, verify: 4, personalize: 5 }[step];
  const saveProfile = async () => { setBusy(true); await client.put('/profile', { name, branch: faculty ? '' : branch, year: faculty ? '' : year }); setBusy(false); setStep(faculty ? 'personalize' : 'verify'); };
  const upload = async e => { const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); setBusy(true); try { const r = await client.post('/verification/upload', fd); setIdStatus(r.data.status); } catch { setIdStatus('Upload failed'); } setBusy(false); };
  const toggle = c => { const n = new Set(choices); n.has(c) ? n.delete(c) : n.add(c); setChoices(n); };
  const all = () => setChoices(new Set(['need', 'skill', 'resource']));
  const finish = async () => { if (choices.size === 0) return; setBusy(true); const r = await client.put('/profile/personalization', { choices: [...choices] }); onDone(r.data); };
  return (
    <main className="onboard-page">
      <div className="onboard-shell">
        <aside className="onboard-brand">
          <div><div className="logo"><span>↻</span> loop</div><p className="kicker">NIT AP · PILOT</p><h1 className="brand-hero">Almost<br /><em>in the Loop.</em></h1><p className="brand-copy">A few details so campus can find you and you can find campus.</p></div>
          <p className="tiny">Verification is a transaction gate, not an entrance gate. Explore freely while it is pending.</p>
        </aside>
        <section className="onboard-panel">
          <div className="onboard-progress">{[1, 2, 3, 4, 5].map(i => <span key={i} className={i <= stepIndex ? 'on' : ''} />)}</div>
          {step === 'profile' && <div className="ob-step" data-testid="onboarding-profile">
            <p className="eyebrow">PROFILE</p><h2>Tell us about yourself</h2><p className="muted">Account type is detected from your institutional email.</p>
            <label>Full name<input data-testid="profile-name-input" value={name} onChange={e => setName(e.target.value)} /></label>
            <label>Account type<input data-testid="profile-role-input" value={faculty ? 'Faculty' : 'Student'} disabled /></label>
            {!faculty && <><label>Branch / program<select data-testid="profile-branch-select" value={branch} onChange={e => setBranch(e.target.value)}>{BRANCHES.map(b => <option key={b}>{b}</option>)}</select></label>
              <label>Year<select data-testid="profile-year-select" value={year} onChange={e => setYear(e.target.value)}>{YEARS.map(y => <option key={y}>{y}</option>)}</select></label></>}
            <button data-testid="profile-continue-button" className="button primary wide" disabled={busy} onClick={saveProfile}>Continue <ChevronRight size={17} /></button>
          </div>}
          {step === 'verify' && <div className="ob-step" data-testid="onboarding-verify">
            <p className="eyebrow">STUDENT VERIFICATION</p><h2>Verify your student identity</h2><p className="muted">Upload your college ID. You can explore Loop while verification is pending.</p>
            <button type="button" className="upload-zone" data-testid="id-upload-zone" onClick={() => fileRef.current?.click()}><Upload size={26} /><b>Upload college ID card</b><span className="tiny">JPG, PNG or PDF</span></button>
            <input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.pdf" hidden onChange={upload} data-testid="id-file-input" />
            <div className="verify-status"><span>Verification status</span><Badge tone={idStatus === 'Under review' ? 'orange' : ''}>{busy ? 'Uploading…' : idStatus}</Badge></div>
            <p className="tiny">Verification is a transaction gate, not an entrance gate.</p>
            <button data-testid="verify-continue-button" className="button primary wide" disabled={busy} onClick={() => setStep('personalize')}>Continue <ChevronRight size={17} /></button>
          </div>}
          {step === 'personalize' && <div className="ob-step" data-testid="onboarding-personalize">
            <p className="eyebrow">PERSONALIZE</p><h2>What brings you to Loop?</h2><p className="muted">Pick everything that applies.</p>
            <div className="choice-grid">{CHOICES.map(([c, t, s]) => <button key={c} data-testid={`choice-${c}`} className={`choice ${choices.has(c) ? 'sel' : ''}`} onClick={() => toggle(c)}><b>{t}</b><span>{s}</span></button>)}
              <button data-testid="choice-all" className={`choice full ${['need', 'skill', 'resource'].every(x => choices.has(x)) ? 'sel' : ''}`} onClick={all}><b>All three</b><span>Need things + offer skills + share resources.</span></button></div>
            <button data-testid="enter-loop-button" className="button primary wide" disabled={busy || choices.size === 0} onClick={finish}>Enter Loop <ChevronRight size={17} /></button>
          </div>}
        </section>
      </div>
    </main>
  );
}

/* ---------------- Shell ---------------- */
function Shell({ page, setPage, children, user, onLogout, reqCount }) {
  return <div className="app-shell">
    <aside><div className="logo"><span>↻</span> loop</div><p className="campus-label">NIT AP · 01</p>
      <nav>{nav.map(([id, label, Icon]) => <button data-testid={`nav-${id}`} className={page === id ? 'active' : ''} onClick={() => setPage(id)} key={id}><Icon size={18} />{label}{id === 'requests' && reqCount > 0 && <i>{reqCount}</i>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="mini-profile"><Avatar name={user.name} small /><span><b>{user.name}</b><small>{user.student_verified ? 'Verified' : user.role === 'faculty' ? 'Faculty' : 'Verification pending'}</small></span></div>
        <button data-testid="logout-button" className="icon-button" onClick={onLogout}><LogOut size={17} /></button>
      </div>
    </aside>
    <main className="content"><header><div className="mobile-brand">↻ <span>loop</span></div><button data-testid="mobile-logout-button" className="notification-button" onClick={onLogout}><LogOut size={18} /></button></header>{children}</main>
    <div className="mobile-nav">{nav.map(([id, label, Icon]) => <button data-testid={`mobile-nav-${id}`} className={page === id ? 'active' : ''} onClick={() => setPage(id)} key={id}><Icon size={19} /><span>{label}</span></button>)}</div>
  </div>;
}

function SearchBox({ value, setValue, onSearch }) { return <div className="search-wrap"><Search size={20} /><input data-testid="marketplace-search-input" value={value} onChange={e => setValue(e.target.value)} onKeyDown={e => e.key === 'Enter' && onSearch()} placeholder="Try 'LinkedIn photo', 'PPT', 'drafter', or 'laptop repair'" /><button data-testid="search-submit-button" className="button primary" onClick={onSearch}>Search</button></div> }

function HomePage({ user, resources, onSearch, setPage, onHire, notify, openMsg }) {
  const [needResult, setNeedResult] = useState(null);
  const [opps, setOpps] = useState([]); const [hasSignal, setHasSignal] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const loadDiscovery = () => { client.get('/opportunities').then(r => { setOpps(r.data.opportunities); setHasSignal(r.data.has_signal); }); client.get('/suggestions').then(r => setSuggestions(r.data.resources)); };
  useEffect(() => { loadDiscovery(); /* eslint-disable-next-line */ }, []);
  const offer = async opp => { try { await client.post(`/requests/${opp.id}/apply`); notify('Offer sent · first-come-first-served'); loadDiscovery(); } catch (e) { notify(e.response?.data?.detail || 'Could not offer'); } };
  const noLoc = !(user.learned?.locations?.length);
  return <>
    <section className="home-hero composer-hero"><div>
      <p className="eyebrow accent">TWO WAYS TO LOOP</p><h1>Need it, or <em>provide it.</em></h1><p className="hero-sub">Describe it in one line. We infer the rest.</p>
      <SmartComposer notify={notify} onNeedPosted={r => { setNeedResult(r); loadDiscovery(); }} onProvidePosted={r => { setNeedResult(null); loadDiscovery(); notify(`Listed · ${r.notified} matching need${r.notified === 1 ? '' : 's'}`); }} />
      <button data-testid="home-search-everything" className="text-button" onClick={() => setPage('explore')}>or search everything on campus <ChevronRight size={15} /></button>
    </div>
      <div className="hero-stat"><span className="live-dot" /><small>LIVE ON CAMPUS</small><strong>1,284</strong><span>students helping each other</span></div>
    </section>
    {(noLoc || opps.length > 0) && <div className="prompt-banner" data-testid="context-prompt">{opps.length > 0 ? <><Zap size={16} /><span>You have <b>{opps.length}</b> strong match{opps.length > 1 ? 'es' : ''} to provide.</span><button data-testid="prompt-view-matches" className="button light" onClick={() => document.getElementById('reverse-discovery')?.scrollIntoView({ behavior: 'smooth' })}>View matches</button></> : <><MapPin size={16} /><span>Add a location to improve your matches.</span></>}</div>}
    {needResult && <MatchResults result={needResult} onHire={onHire} onSearch={onSearch} />}
    <section className="section-block" id="reverse-discovery"><div className="section-heading"><div><p className="eyebrow">REVERSE DISCOVERY</p><h2>People who need what you provide</h2></div></div>
      {opps.length > 0 ? <div className="match-grid">{opps.map(o => <OpportunityCard key={o.id} opp={o} onOffer={offer} onMessage={openMsg} />)}</div> : <p className="muted empty-line" data-testid="opportunities-empty">{hasSignal ? 'No open needs match your skills right now.' : 'Tell campus what you can provide (use "I Can Provide Something" above) to get matched to needs.'}</p>}
    </section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">BORROW, DON'T BUY</p><h2>Resources you may need</h2></div><button className="text-button" data-testid="home-explore-link" onClick={() => setPage('explore')}>View all <ChevronRight size={16} /></button></div>
      <div className="resource-strip">{(suggestions.length ? suggestions : resources).slice(0, 3).map(r => <div className="resource-card" key={r.id} data-testid={`suggested-resource-${r.id}`} onClick={() => onSearch(r.name)}><div className="resource-emoji">{r.emoji}</div><div><h3>{r.name}</h3><p>{money(r.price)} / day · {r.condition}</p><small>{r.location}</small></div><ChevronRight size={17} /></div>)}</div>
    </section>
  </>;
}

function ProviderCard({ provider, onClick }) {
  return <button data-testid={`provider-card-${provider.id}`} className="provider-card" onClick={onClick}>
    <div className="provider-top"><Avatar name={provider.name} /><span className="match-score">{provider.match ?? provider.base_match}% <small>match</small></span></div>
    <div className="provider-info"><h3>{provider.name}</h3><p>{provider.skill}</p><div className="provider-meta"><span><Star size={14} fill="currentColor" /> {provider.rating}</span><span>{provider.gigs} gigs</span><span>{money(provider.price)}</span></div></div>
    <div className="why"><ShieldCheck size={15} /><span>{provider.why}</span></div>
  </button>;
}
function ResourceCard({ resource, onClick }) { return <button data-testid={`resource-card-${resource.id}`} className="resource-card" onClick={onClick}><div className="resource-emoji">{resource.emoji}</div><div><h3>{resource.name}</h3><p>{money(resource.price)} / day · {resource.condition}</p><small>{resource.owner} · ★{resource.rating}</small></div><ChevronRight size={17} /></button> }

function Explore({ initialQuery, onSelectProvider, onSelectResource, onPostRequest }) {
  const [q, setQ] = useState(initialQuery || '');
  const [results, setResults] = useState({ services: [], resources: [], no_match: false });
  const [loading, setLoading] = useState(true);
  const run = async (term = q) => { setQ(term); setLoading(true); const r = await client.get('/search', { params: { q: term } }); setResults(r.data); setLoading(false); };
  useEffect(() => { run(initialQuery || ''); /* eslint-disable-next-line */ }, [initialQuery]);
  return <section>
    <div className="page-title"><p className="eyebrow accent">EXPLORE THE LOOP</p><h1>{q ? <>Results for <em>"{q}"</em></> : <>Find your <em>fit.</em></>}</h1><p className="hero-sub">Search once. We look across skills and resources.</p><SearchBox value={q} setValue={setQ} onSearch={() => run()} /></div>
    <div className="result-tabs"><span data-testid="services-results-tab" className="selected">Services <b>{results.services.length}</b></span><span data-testid="resources-results-tab">Resources <b>{results.resources.length}</b></span><span className="sort">Best match ▾</span></div>
    {results.no_match ? <EmptySearch onRequest={onPostRequest} /> :
      <div className="results-layout">
        <div><p className="result-context" data-testid="search-result-context">{q ? `Best matches for "${q}"` : 'Popular services'}</p>{results.services.map((p, i) => <ProviderCard key={p.id} provider={i === 0 && q ? { ...p } : p} onClick={() => onSelectProvider(p)} />)}</div>
        <div><p className="result-context">Physical resources · {results.resources.length}</p>{results.resources.map(r => <ResourceCard key={r.id} resource={r} onClick={() => onSelectResource(r)} />)}</div>
      </div>}
    {!results.no_match && <div className="section banner-inline">Can't find the right person?<button data-testid="explore-post-request-button" className="button secondary" onClick={onPostRequest}>Post a request</button></div>}
  </section>;
}
function EmptySearch({ onRequest }) { return <div className="empty-state" data-testid="no-match-empty-state"><div className="empty-icon">⌁</div><h2>Nobody currently offers this.</h2><p>Loop turns the missing need into a request. Providers with at least a 50% match get notified.</p><button data-testid="post-request-empty-button" className="button primary" onClick={onRequest}>Post a request <Plus size={17} /></button></div> }

function ProviderDetail({ provider, onBack, onHire }) {
  return <section><button data-testid="provider-back-button" className="back-button" onClick={onBack}>← Back to results</button>
    <div className="profile-hero"><Avatar name={provider.name} /><div><Badge tone="green">{provider.match ?? provider.base_match}% match</Badge><h1>{provider.name}</h1><p>{provider.branch} · {provider.year} · NIT Andhra Pradesh</p><div className="trust-row">{(provider.verified || []).map(v => <Badge key={v}>{v}</Badge>)}</div></div></div>
    <div className="detail-columns"><div>
      <div className="detail-section"><p className="eyebrow">WHY LOOP RECOMMENDED THEM</p><div className="recommendation"><ShieldCheck /><p>{provider.why}</p></div></div>
      <div className="detail-section"><p className="eyebrow">SKILLS & WORK</p><h2>{provider.skill}</h2><p className="muted">{provider.bio}</p></div>
      <div className="detail-section"><p className="eyebrow">REPUTATION</p><div className="reputation"><strong><Star size={19} fill="currentColor" /> {provider.rating}</strong><span>{provider.gigs} gigs completed</span><span>{provider.similar} similar gigs</span></div></div>
    </div>
      <aside className="hire-panel"><p className="eyebrow accent">SOLVE YOUR PROBLEM</p><h2>Hire {provider.name.split(' ')[0]}.</h2><p>{provider.availability} · UPI held until completion</p><div className="price-line"><span>One-time task</span><b>{money(provider.price)}</b></div><div className="secure-line"><LockKeyhole size={16} /> Provider accepts first · then you pay</div><button data-testid="hire-provider-button" className="button primary wide" onClick={onHire}>Send hire request <ChevronRight size={17} /></button><small>Contact details reveal only after payment.</small></aside>
    </div>
  </section>;
}

function ResourceDetail({ resource, onBack, onRent }) {
  const [days, setDays] = useState(1); const total = resource.price * days + resource.deposit;
  return <section><button data-testid="resource-back-button" className="back-button" onClick={onBack}>← Back to resources</button>
    <div className="resource-detail"><div className="resource-large">{resource.emoji}</div><p className="eyebrow accent">RESOURCE LISTING</p><h1>{resource.name}</h1><p className="hero-sub">Owned by {resource.owner} · <Star size={15} fill="currentColor" /> {resource.rating}</p>
      <div className="resource-facts"><span><b>{money(resource.price)}</b><small>per day</small></span><span><b>{resource.condition}</b><small>condition</small></span><span><b>{resource.location}</b><small>pickup</small></span></div>
      <div className="rent-box"><h2>Rent this resource</h2><label>Duration<select data-testid="rental-duration-select" value={days} onChange={e => setDays(Number(e.target.value))}><option value="1">1 day</option><option value="2">2 days</option><option value="3">3 days</option><option value="4">4 days</option></select></label>
        <div className="breakdown"><span>{money(resource.price)} × {days} day{days > 1 ? 's' : ''}<b>{money(resource.price * days)}</b></span>{resource.deposit > 0 && <span>Refundable deposit<b>{money(resource.deposit)}</b></span>}<hr /><span>Total upfront<b>{money(total)}</b></span></div>
        <button data-testid="rent-resource-button" className="button primary wide" onClick={() => onRent(days)}>Reserve · owner accepts first <WalletCards size={17} /></button><small>Deposit is refunded after the owner confirms return.</small></div>
    </div>
  </section>;
}

/* ---------------- Transaction card + messaging + composer ---------------- */
function TransactionCard({ tx, onAction, onMessage, onQuickReview }) {
  const actions = nextActions(tx);
  return <div className="tx-card" data-testid={`transaction-${tx.id}`}>
    <div className="tx-head"><div><span className="eyebrow">{tx.kind === 'service' ? 'HIRE' : 'RENTAL'}</span><h3>{tx.title}</h3><p className="muted">{money(tx.amount)}{tx.deposit ? ` + ${money(tx.deposit)} deposit` : ''}</p></div><Badge tone={tx.status === 'COMPLETED' ? 'green' : 'orange'}>{STATUS_LABEL[tx.status] || tx.status}</Badge></div>
    {tx.contact_revealed && tx.contacts && <div className="tx-contacts" data-testid={`tx-contacts-${tx.id}`}><LockKeyhole size={14} /> Contact revealed: {tx.kind === 'service' ? tx.contacts.provider : `${tx.contacts.provider} · pickup ${tx.contacts.pickup || ''}`}</div>}
    {tx.deposit_refunded && <div className="tx-contacts" data-testid={`tx-refund-${tx.id}`}><Check size={14} /> Deposit of {money(tx.deposit)} refunded.</div>}
    <div className="tx-actions">
      {actions.map(([a, label, cls]) => <button key={a} data-testid={`tx-action-${tx.id}-${a}`} className={`button ${cls}`} onClick={() => onAction(tx, a)}>{label}</button>)}
      <button data-testid={`tx-message-${tx.id}`} className="button ghost" onClick={() => onMessage(tx.id, tx.title)}><MessageCircle size={15} /> Message</button>
      {tx.status === 'COMPLETED' && !tx.reviewed && <span className="inline-rate" data-testid={`tx-rate-${tx.id}`}>How did it go?{[1, 2, 3, 4, 5].map(n => <button key={n} data-testid={`tx-rate-${tx.id}-${n}`} onClick={() => onQuickReview(tx, n)}><Star size={17} /></button>)}</span>}
      {tx.reviewed && <span className="tiny">✓ Reviewed</span>}
    </div>
  </div>;
}

function MessageDrawer({ refId, title, me, onClose }) {
  const [msgs, setMsgs] = useState([]); const [text, setText] = useState(''); const endRef = useRef();
  const load = () => client.get(`/threads/${refId}`).then(r => setMsgs(r.data.messages));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [refId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);
  const send = async () => { if (!text.trim()) return; const r = await client.post(`/threads/${refId}`, { text }); setMsgs(r.data.messages); setText(''); };
  return <div className="modal-backdrop" onClick={onClose}><div className="msg-drawer" onClick={e => e.stopPropagation()} data-testid="message-drawer">
    <div className="msg-head"><div><p className="eyebrow accent">MESSAGES</p><h3>{title}</h3></div><button data-testid="close-message-drawer" className="close-button" onClick={onClose}><X /></button></div>
    <div className="msg-body">{msgs.length === 0 && <p className="muted tiny">Start the conversation — kept attached to this {refId.startsWith('tx-') ? 'transaction' : 'request'}.</p>}
      {msgs.map(m => <div key={m.id} className={`msg ${m.from_user === me ? 'mine' : ''}`} data-testid={`message-${m.id}`}><b>{m.from_name}</b><span>{m.text}</span></div>)}<div ref={endRef} /></div>
    <div className="msg-input"><input data-testid="message-input" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Type a message…" /><button data-testid="send-message-button" className="button primary" onClick={send}><Send size={16} /></button></div>
  </div></div>;
}

const CATS = ['Presentation', 'Photography / Video', 'Tech Help', 'Academics', 'Design', 'Physical Resource', 'General'];
function SmartComposer({ notify, onNeedPosted, onProvidePosted }) {
  const [mode, setMode] = useState('need'); const [text, setText] = useState('');
  const [parsed, setParsed] = useState(null); const [busy, setBusy] = useState(false);
  const parse = async () => { if (!text.trim()) { notify('Describe what you need or can provide.'); return; } const r = await client.post('/intent/parse', { text }); setParsed({ ...r.data, intent: mode, budget: 300, price: 200 }); };
  const post = async () => {
    setBusy(true);
    try {
      if (parsed.intent === 'need') { const r = await client.post('/requests', { title: text, category: parsed.category, location: parsed.location, days: parsed.days, budget: Number(parsed.budget) || 0, description: '' }); onNeedPosted(r.data); notify(`Posted · ${r.data.notified} providers notified`); }
      else { const r = await client.post('/provides', { kind: parsed.kind, category: parsed.category, name: text, price: Number(parsed.price) || 0, location: parsed.location, text }); onProvidePosted(r.data); }
      setText(''); setParsed(null);
    } catch (e) { notify(e.response?.data?.detail || 'Could not post'); }
    setBusy(false);
  };
  return <div className="composer" data-testid="smart-composer">
    <div className="intent-toggle"><button data-testid="intent-need" className={mode === 'need' ? 'on' : ''} onClick={() => { setMode('need'); setParsed(null); }}>I Need Something</button><button data-testid="intent-provide" className={mode === 'provide' ? 'on' : ''} onClick={() => { setMode('provide'); setParsed(null); }}>I Can Provide Something</button></div>
    <div className="composer-input"><Sparkles size={18} /><input data-testid="composer-input" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && parse()} placeholder={mode === 'need' ? "e.g. Need a drafter for 3 days near Civil Block" : "e.g. I can do PPT design and LinkedIn photos"} /><button data-testid="composer-parse-button" className="button primary" onClick={parse}>Continue</button></div>
    {parsed && <div className="confirm-card" data-testid="confirm-card">
      <p className="eyebrow accent">CONFIRM & POST</p><p className="confirm-line" data-testid="confirm-line">{parsed.intent === 'need' ? 'Need' : 'Provide'} · {parsed.confirm.replace(/^(Need|Provide) · /, '')}</p>
      <div className="confirm-chips">
        <label>Category<select data-testid="confirm-category" value={parsed.category} onChange={e => setParsed({ ...parsed, category: e.target.value })}>{CATS.map(c => <option key={c}>{c}</option>)}</select></label>
        {parsed.intent === 'need' && parsed.kind === 'resource' && <label>Days<input data-testid="confirm-days" type="number" value={parsed.days || 1} onChange={e => setParsed({ ...parsed, days: Number(e.target.value) })} /></label>}
        <label>Location<input data-testid="confirm-location" value={parsed.location || ''} onChange={e => setParsed({ ...parsed, location: e.target.value })} placeholder="Add location" /></label>
        {parsed.intent === 'need' ? <label>Budget ₹<input data-testid="confirm-budget" type="number" value={parsed.budget} onChange={e => setParsed({ ...parsed, budget: e.target.value })} /></label> : <label>Price ₹<input data-testid="confirm-price" type="number" value={parsed.price} onChange={e => setParsed({ ...parsed, price: e.target.value })} /></label>}
      </div>
      <button data-testid="composer-post-button" className="button primary wide" disabled={busy} onClick={post}>{parsed.intent === 'need' ? 'Post & see matches' : 'List & notify campus'} <ChevronRight size={16} /></button>
    </div>}
  </div>;
}

function MatchResults({ result, onHire, onSearch }) {
  const s = result.matches?.services || []; const r = result.matches?.resources || [];
  return <section className="section-block" data-testid="need-match-results"><div className="section-heading"><div><p className="eyebrow accent">INSTANT MATCHES</p><h2>{s.length + r.length} matches for "{result.title}"</h2></div></div>
    <div className="match-grid">
      {s.map(p => <div className="match-card" data-testid={`match-${p.id}`} key={p.id}><div className="match-top"><span className="match-score">{p.match}% match</span>{(p.verified || []).length ? <span className="tiny">✓ Verified</span> : null}</div><h3>{p.name}</h3><p className="muted">{p.skill} · ★{p.rating} · {money(p.price)}</p><div className="match-actions"><button data-testid={`match-hire-${p.id}`} className="button primary" onClick={() => onHire(p)}>Hire {money(p.price)}</button><button data-testid={`match-view-${p.id}`} className="button ghost" onClick={() => onSearch(p.skill)}>View</button></div></div>)}
      {r.map(res => <div className="match-card" data-testid={`match-${res.id}`} key={res.id}><div className="match-top"><span className="resource-emoji small">{res.emoji}</span></div><h3>{res.name}</h3><p className="muted">{money(res.price)}/day · {res.condition}</p><div className="match-actions"><button data-testid={`match-view-${res.id}`} className="button ghost" onClick={() => onSearch(res.name)}>View resource</button></div></div>)}
    </div>
    {s.length + r.length === 0 && <p className="muted">No instant matches — providers have been notified and can apply first-come-first-served.</p>}
  </section>;
}

function OpportunityCard({ opp, onOffer, onMessage }) {
  return <div className="match-card" data-testid={`opportunity-${opp.id}`}><div className="match-top"><span className="match-score">{opp.match}% match</span><span className="tiny">{opp.location || 'NIT AP'}</span></div><h3>{opp.title}</h3><p className="muted">{opp.category} · {money(opp.budget)} · {opp.needer_name}</p><div className="match-actions">{opp.applied ? <span className="tiny">✓ Offered</span> : <button data-testid={`offer-${opp.id}`} className="button primary" onClick={() => onOffer(opp)}>Offer to Provide</button>}<button data-testid={`opp-message-${opp.id}`} className="button ghost" onClick={() => onMessage(opp.id, opp.title)}><MessageCircle size={15} /> Message</button></div></div>;
}

/* ---------------- Requests (create + FCFS + activity) ---------------- */
function Requests({ user, notify, refreshHome, onMessage }) {
  const [tab, setTab] = useState('mine');
  const [mine, setMine] = useState([]); const [campus, setCampus] = useState([]); const [txs, setTxs] = useState([]);
  const [show, setShow] = useState(false); const [mode, setMode] = useState('one');
  const [form, setForm] = useState({ title: '', category: 'Presentation', deadline: '', budget: 500, description: '', frequency: 'Weekly', location: '' });
  const load = async () => { const [r, t] = await Promise.all([client.get('/requests'), client.get('/transactions')]); setMine(r.data.mine); setCampus(r.data.campus); setTxs(t.data); };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);
  const create = async () => { if (!form.title.trim()) { notify('Add what you need first.'); return; } try { await client.post('/requests', { ...form, recurring: mode === 'recurring', budget: Number(form.budget) || 0 }); setShow(false); setForm({ ...form, title: '', description: '' }); notify('Request posted. Matching providers notified.'); load(); } catch (e) { notify(e.response?.data?.detail || 'Could not post'); } };
  const apply = async id => { try { const r = await client.post(`/requests/${id}/apply`); notify(`Applied · position #${r.data.position}`); load(); } catch (e) { notify(e.response?.data?.detail || 'Could not apply'); } };
  const select = async (reqId, appId) => { try { await client.post(`/requests/${reqId}/select/${appId}`); notify('Provider selected · hire started'); load(); refreshHome(); } catch (e) { notify(e.response?.data?.detail || 'Could not select'); } };
  const doAction = async (tx, action) => { try { const r = await client.post(`/transactions/${tx.id}/action`, { action }); notify(action === 'pay' ? 'Payment secured · contact revealed' : STATUS_LABEL[r.data.status] || 'Updated'); load(); refreshHome(); } catch (e) { notify(e.response?.data?.detail || 'Action failed'); } };
  const quickReview = async (tx, rating) => { try { await client.post('/reviews', { transaction_id: tx.id, rating, text: '' }); notify('Thanks · rating saved'); load(); refreshHome(); } catch (e) { notify(e.response?.data?.detail || 'Could not rate'); } };
  const cancelReq = async id => { try { await client.post(`/requests/${id}/cancel`); notify('Request cancelled'); load(); } catch (e) { notify('Could not cancel'); } };
  const renewReq = async id => { try { await client.post(`/requests/${id}/renew`); notify('Request renewed for 14 days'); load(); } catch (e) { notify('Could not renew'); } };
  const lifeTone = l => l === 'Completed' ? 'green' : (l === 'Cancelled' || l === 'Expired') ? '' : 'orange';
  return <section>
    <div className="page-title inline-title"><div><p className="eyebrow accent">YOUR DEMAND</p><h1>Requests & <em>activity.</em></h1><p className="hero-sub">Search first. Ask campus when you need to.</p></div><button data-testid="create-request-button" className="button primary" onClick={() => setShow(true)}><Plus size={17} /> Post a request</button></div>
    <div className="result-tabs"><span data-testid="tab-mine" className={tab === 'mine' ? 'selected' : ''} onClick={() => setTab('mine')}>My requests <b>{mine.length}</b></span><span data-testid="tab-campus" className={tab === 'campus' ? 'selected' : ''} onClick={() => setTab('campus')}>Campus <b>{campus.length}</b></span><span data-testid="tab-activity" className={tab === 'activity' ? 'selected' : ''} onClick={() => setTab('activity')}>Activity <b>{txs.length}</b></span></div>

    {tab === 'mine' && <div className="request-list">{mine.length === 0 ? <p className="muted empty-line">No requests yet. Post one when search comes up short.</p> : mine.map(r => <div className="request-row col" data-testid={`request-row-${r.id}`} key={r.id}>
      <div className="request-row-top"><div className="request-icon"><FileText size={19} /></div><div className="request-content"><h3>{r.title}</h3><p>{money(r.budget)} · {r.deadline || 'flexible'} · {r.location || 'campus'} · {r.notified} notified</p></div><Badge tone={lifeTone(r.lifecycle)} data-testid={`request-lifecycle-${r.id}`}>{r.lifecycle || r.status}</Badge></div>
      {r.applications?.length > 0 && r.status === 'open' && <div className="applicants"><p className="eyebrow">APPLICANTS · FCFS ORDER</p>{r.applications.map(a => <div className="applicant-row" key={a.id} data-testid={`applicant-${a.id}`}><span>#{a.order} {a.provider_name} · {a.match}% match</span><div className="row-actions"><button data-testid={`msg-applicant-${a.id}`} className="button ghost" onClick={() => onMessage(r.id, r.title)}><MessageCircle size={14} /></button><button data-testid={`select-applicant-${a.id}`} className="button primary" onClick={() => select(r.id, a.id)}>Select</button></div></div>)}</div>}
      {r.status === 'matched' && <p className="tiny">✓ Provider selected — see Activity to complete the transaction.</p>}
      <div className="row-actions end">{r.status === 'open' && <button data-testid={`cancel-request-${r.id}`} className="button ghost" onClick={() => cancelReq(r.id)}><Ban size={14} /> Cancel</button>}{(r.lifecycle === 'Expired' || r.status === 'cancelled') && <button data-testid={`renew-request-${r.id}`} className="button secondary" onClick={() => renewReq(r.id)}><RefreshCw size={14} /> Renew</button>}</div>
    </div>)}</div>}

    {tab === 'campus' && <div className="request-list">{campus.map(r => <div className="request-row" data-testid={`campus-request-${r.id}`} key={r.id}><div className="request-icon"><FileText size={19} /></div><div className="request-content"><h3>{r.title}</h3><p>{money(r.budget)} · {r.deadline} · {r.needer_name} · {r.applications?.length || 0} applied</p></div><div className="row-actions"><button data-testid={`msg-campus-${r.id}`} className="button ghost" onClick={() => onMessage(r.id, r.title)}><MessageCircle size={14} /></button>{r.status === 'open' ? <button data-testid={`apply-request-${r.id}`} className="button primary" onClick={() => apply(r.id)}>Offer (FCFS)</button> : <Badge tone="green">matched</Badge>}</div></div>)}</div>}

    {tab === 'activity' && <div className="request-list">{txs.length === 0 ? <p className="muted empty-line">No transactions yet. Hire a provider or rent a resource to start.</p> : txs.map(tx => <TransactionCard key={tx.id} tx={tx} onAction={doAction} onMessage={onMessage} onQuickReview={quickReview} />)}</div>}

    {show && <div className="modal-backdrop"><div className="modal"><button data-testid="close-request-modal-button" className="close-button" onClick={() => setShow(false)}><X /></button>
      <p className="eyebrow accent">NEW DEMAND</p><h2>What do you need?</h2>
      <div className="choice-grid two"><button data-testid="req-mode-one" className={`choice ${mode === 'one' ? 'sel' : ''}`} onClick={() => setMode('one')}><b>One-time task</b><span>Solve one problem, then you're done.</span></button><button data-testid="req-mode-recurring" className={`choice ${mode === 'recurring' ? 'sel' : ''}`} onClick={() => setMode('recurring')}><b>Recurring</b><span>Need the same help repeatedly.</span></button></div>
      <label>What do you need?<input data-testid="request-title-input" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="e.g. Drone photography for department event" /></label>
      <label>Category<select data-testid="request-category-select" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>{['Presentation', 'Photography / Video', 'Tech Help', 'Academics', 'Design', 'Physical Resource'].map(c => <option key={c}>{c}</option>)}</select></label>
      <div className="two-col"><label>Deadline<input data-testid="request-deadline-input" value={form.deadline} onChange={e => setForm({ ...form, deadline: e.target.value })} placeholder="Due Friday" /></label><label>Budget<input data-testid="request-budget-input" type="number" value={form.budget} onChange={e => setForm({ ...form, budget: e.target.value })} /></label></div>
      <label>Location<input data-testid="request-location-input" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} placeholder="e.g. Civil Block, Hostel C, Library" /></label>
      {mode === 'recurring' && <label>Frequency<select data-testid="request-frequency-select" value={form.frequency} onChange={e => setForm({ ...form, frequency: e.target.value })}>{['Weekly', 'Monthly', 'Custom'].map(f => <option key={f}>{f}</option>)}</select></label>}
      <label>Details<textarea data-testid="request-description-input" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Describe the task, deadline, quantity or constraints." /></label>
      <button data-testid="submit-request-button" className="button primary wide" onClick={create}>Post request <ChevronRight size={17} /></button>
    </div></div>}
  </section>;
}

function Insights() {
  const [data, setData] = useState(null);
  useEffect(() => { client.get('/insights').then(r => setData(r.data)); }, []);
  return <section><div className="page-title"><p className="eyebrow accent">CAMPUS INSIGHTS</p><h1>What is happening <em>on campus?</em></h1><p className="hero-sub">Marketplace activity translated into decisions.</p></div>
    {data && <><div className="metric-grid">{data.metrics.map(m => <div className="metric" data-testid={`metric-${m.label.toLowerCase().replaceAll(' ', '-')}`} key={m.label}><span>{m.label}</span><strong>{m.value}</strong></div>)}</div>
      <div className="banner-inline full">Resource marketplace gets them in. Skill marketplace keeps them there.</div>
      <div className="insight-grid"><div className="chart-panel"><div className="section-heading"><div><p className="eyebrow">THIS WEEK</p><h2>Popular services</h2></div><Badge tone="orange">Demand rising</Badge></div>{data.demand.map(([label, value]) => <div className="bar-row" key={label}><span>{label}</span><div><i style={{ width: `${value * 2}%` }} /></div><b>{value}</b></div>)}</div>
        <div className="supply-gap"><p className="eyebrow">UNDER-SUPPLIED</p><h2>Supply gaps worth closing.</h2>{data.undersupplied.map(([t, s]) => <div className="gap-row" key={t}><b>{t}</b><span>{s}</span></div>)}</div></div>
    </>}
  </section>;
}

function Profile({ user, onVerify, onUploaded }) {
  const fileRef = useRef(); const [busy, setBusy] = useState(false);
  const upload = async e => { const f = e.target.files?.[0]; if (!f) return; const fd = new FormData(); fd.append('file', f); setBusy(true); try { await client.post('/verification/upload', fd); onUploaded('Under review'); } catch { onUploaded('Pending'); } setBusy(false); };
  const verified = user.student_verified; const faculty = user.role === 'faculty';
  return <section><div className="page-title"><p className="eyebrow accent">YOUR LOOP</p><h1>Hi, <em>{user.name.split(' ')[0]}.</em></h1><p className="hero-sub">Your reputation grows every time you show up.</p></div>
    <div className="profile-card"><Avatar name={user.name} /><div><h2>{user.name}</h2><p>{faculty ? 'Faculty' : `${user.branch || '—'} · ${user.year || ''}`} · NIT Andhra Pradesh</p><div className="trust-row"><Badge>Email Verified</Badge>{!faculty && <Badge tone={verified ? 'green' : 'orange'}>{verified ? 'Student Verified' : `Student ${user.verification_status}`}</Badge>}{(user.personalization || []).length === 3 && <Badge>All three</Badge>}</div></div></div>
    {!faculty && !verified && <div className="verification-callout"><div><ShieldCheck /><div><h3>Student verification: {user.verification_status}</h3><p>Browse freely. Verification is required before your first transaction.</p></div></div>
      <div className="callout-actions"><input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.pdf" hidden onChange={upload} data-testid="profile-id-file-input" /><button data-testid="upload-student-id-button" className="button secondary" disabled={busy} onClick={() => fileRef.current?.click()}>{busy ? 'Uploading…' : 'Upload ID'}</button><button data-testid="approve-verification-button" className="button primary" onClick={onVerify}>Approve (demo)</button></div></div>}
    <div className="tile trust-tile"><p className="eyebrow">TRUST AT A GLANCE</p><div className="trust">{[['Identity', 'Institutional email verified'], ['Capability', 'Portfolio verified'], ['Reputation', `${user.reputation?.rating || 0}★ reviews`], ['Track record', `${user.reputation?.gigs_completed || 0} gigs`]].map(([t, s]) => <div className="tile" key={t}><strong>{t}</strong><p className="muted">{s}</p></div>)}</div></div>
    <div className="profile-stats"><div><strong>{user.reputation?.gigs_completed || 0}</strong><span>Completed gigs</span></div><div><strong>{user.reputation?.rating || '—'}</strong><span>Your rating</span></div><div><strong>{(user.personalization || []).length === 3 ? 'All three' : (user.personalization || []).join(', ') || '—'}</strong><span>Your Loop mode</span></div></div>
  </section>;
}

/* ---------------- App ---------------- */
function App() {
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [authError, setAuthError] = useState('');
  const [page, setPage] = useState('home');
  const [data, setData] = useState({ providers: [], resources: [], requests: [], transactions: [] });
  const [selected, setSelected] = useState(null); const [resource, setResource] = useState(null);
  const [msg, setMsg] = useState(null);
  const [toast, setToast] = useState(''); const [query, setQuery] = useState('');
  const hasGoogleSession = location.hash?.includes('session_id=');

  useEffect(() => { if (hasGoogleSession) return; let active = true; client.get('/auth/me').then(r => active && setUser(r.data)).catch(() => active && setUser(null)).finally(() => active && setAuthChecking(false)); return () => { active = false; }; }, [hasGoogleSession]);
  const loadHome = () => { client.get('/home').then(r => setData(r.data)); };
  useEffect(() => { if (user?.onboarded) loadHome(); }, [user]);

  const notify = msg => { setToast(msg); setTimeout(() => setToast(''), 2800); };
  const finishAuth = (u, token) => { if (token) client.defaults.headers.common.Authorization = `Bearer ${token}`; setAuthError(''); setUser(u); setAuthChecking(false); };
  const failGoogleAuth = m => { setAuthError(m); setAuthChecking(false); };
  const search = q => { setQuery(q || ''); setSelected(null); setResource(null); setPage('explore'); };
  const logout = async () => { await client.post('/auth/logout').catch(() => { }); delete client.defaults.headers.common.Authorization; setUser(null); setPage('home'); };
  const refreshUser = () => client.get('/auth/me').then(r => setUser(r.data));

  const hire = async p => { try { await client.post('/transactions/hire', { provider_id: p.id, amount: p.price }); notify(`Hire request sent to ${p.name}`); setSelected(null); loadHome(); setPage('requests'); } catch (e) { notify(e.response?.data?.detail || 'Could not hire'); } };
  const rent = async (r, days) => { try { await client.post('/transactions/rent', { resource_id: r.id, days }); notify(`Reservation created for ${r.name}`); setResource(null); loadHome(); setPage('requests'); } catch (e) { notify(e.response?.data?.detail || 'Could not reserve'); } };
  const openMsg = (ref, title) => setMsg({ ref, title });

  if (hasGoogleSession) return <AuthCallback onDone={finishAuth} onError={failGoogleAuth} />;
  if (authChecking) return <main className="onboard-page"><div className="auth-status" data-testid="auth-session-loading" role="status">Opening your Loop…</div></main>;
  if (!user) return <Auth initialError={authError} onDone={finishAuth} />;
  if (!user.onboarded) return <Onboarding user={user} onDone={u => { setUser(u); notify(`Welcome to Loop, ${u.name}.`); }} />;

  const openReqCount = data.requests.filter(r => r.status === 'open').length;
  let content;
  if (page === 'home') content = <HomePage user={user} resources={data.resources} onSearch={search} setPage={setPage} onHire={hire} notify={notify} openMsg={openMsg} />;
  else if (page === 'explore') content = selected ? <ProviderDetail provider={selected} onBack={() => setSelected(null)} onHire={() => hire(selected)} /> : resource ? <ResourceDetail resource={resource} onBack={() => setResource(null)} onRent={days => rent(resource, days)} /> : <Explore initialQuery={query} onSelectProvider={setSelected} onSelectResource={setResource} onPostRequest={() => setPage('requests')} />;
  else if (page === 'requests') content = <Requests user={user} notify={notify} refreshHome={loadHome} onMessage={openMsg} />;
  else if (page === 'insights') content = <Insights />;
  else content = <Profile user={user} onVerify={async () => { await client.post('/verification/approve'); await refreshUser(); notify('Student verification approved · you can transact now'); }} onUploaded={s => { refreshUser(); notify(`ID uploaded · status ${s}`); }} />;

  return <Shell page={page} setPage={p => { setSelected(null); setResource(null); setPage(p); }} user={user} onLogout={logout} reqCount={openReqCount}>
    {content}
    {msg && <MessageDrawer refId={msg.ref} title={msg.title} me={user.user_id} onClose={() => setMsg(null)} />}
    {toast && <div data-testid="loop-toast" className="loop-toast" role="status">{toast}</div>}
  </Shell>;
}
export default App;
