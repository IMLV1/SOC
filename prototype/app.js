/* Interactive UI prototype. Authentication, detections and AI are local fixtures. */
(() => {
  'use strict';
  const M = window.SOC;
  const STORE = 'sentinel.prototype.v1';
  const paths = {
    shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z M9 12l2 2 4-4',
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    play: 'm8 5 11 7-11 7V5Z', pause: 'M8 5v14 M16 5v14',
    activity: 'M2 12h5l3-8 4 16 3-8h5', search: 'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
    bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4',
    ticket: 'M3 5h18v5a2 2 0 0 0 0 4v5H3v-5a2 2 0 0 0 0-4V5Z M15 5v3 M15 11v2 M15 16v3',
    chart: 'M4 3v17h17 M8 15v-4 M13 15V7 M18 15v-6', users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M13 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M17 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-4',
    settings: 'M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6',
    arrow: 'M5 12h14 M13 6l6 6-6 6', back: 'M19 12H5 M11 6l-6 6 6 6', chevron: 'm9 5 7 7-7 7',
    plus: 'M12 5v14 M5 12h14', close: 'm6 6 12 12 M6 18 18 6', check: 'm5 12 4 4L19 6',
    clock: 'M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
    spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
    database: 'M20 6c0 2-4 3-8 3S4 8 4 6s4-3 8-3 8 1 8 3Z M4 6v12c0 2 4 3 8 3s8-1 8-3V6 M4 12c0 2 4 3 8 3s8-1 8-3',
    terminal: 'm5 7 5 5-5 5 M13 17h6', globe: 'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M2 12h20 M12 2c5 6 5 14 0 20-5-6-5-14 0-20Z',
    info: 'M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
    logout: 'M9 3H4v18h5 M10 12h11 M17 8l4 4-4 4', menu: 'M4 6h16 M4 12h16 M4 18h16',
    trash: 'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
    refresh: 'M20 7v5h-5 M4 17v-5h5 M6 6a8 8 0 0 1 13 2 M18 18A8 8 0 0 1 5 16',
    download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5', book: 'M12 5C8 2 4 3 2 4v15c4-2 7-1 10 1 3-2 6-3 10-1V4c-2-1-6-2-10 1Z M12 5v15'
  };
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.shield}"/></svg>`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const badge = (text, color = 'gray') => `<span class="badge ${color}">${esc(text)}</span>`;
  const severity = value => badge(value, { Critical: 'red', High: 'red', Medium: 'yellow', Low: 'blue' }[value]);
  const status = value => badge(value, { Open: 'blue', Investigating: 'purple', Resolved: 'green', Closed: 'gray', Running: 'green', Review: 'yellow', Completed: 'purple', Paused: 'yellow' }[value]);
  const button = (label, action, ico, kind = '', attrs = '') => `<button type="button" class="btn ${kind}" data-action="${action}" ${attrs}>${ico ? icon(ico) : ''}${label}</button>`;
  const time = n => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
  const eventTime = n => '21:' + time(n);
  let persisted = {};
  try { persisted = JSON.parse(localStorage.getItem(STORE) || '{}'); } catch { /* Start clean if local storage is unavailable or invalid. */ }
  const validRuns = Array.isArray(persisted.runs) ? persisted.runs.filter(r => r && Array.isArray(r.events) && Array.isArray(r.tickets) && Array.isArray(r.alerts) && Array.isArray(r.audit) && Array.isArray(r.scenarioIds) && r.scenarioIds.every(id => M.getScenario(id))) : [];
  const state = { view: 'overview', user: null, runs: validRuns, accounts: Array.isArray(persisted.accounts) ? persisted.accounts : [], selectedRun: null, demo: M.demoRun(), selection: ['S02'], ticketId: null, search: '', filter: 'All', deleted: false, mobile: false, faults: { ai: false, quota: false }, authMode: 'login', noteDeleted: false };
  // Reloading pauses a running exercise; it never fabricates events while the page is closed.
  state.runs.forEach(r => { if (r.state === 'Running') r.state = 'Paused'; });
  function save() {
    try { localStorage.setItem(STORE, JSON.stringify({ runs: state.runs, accounts: state.accounts })); }
    catch { toast('บันทึกใน browser ไม่สำเร็จ กรุณาส่งออกรายงานก่อนปิดหน้า'); }
  }
  const run = () => state.selectedRun ? state.runs.find(r => r.id === state.selectedRun) || state.demo : state.demo;
  const editable = () => !!state.user && !run().demo && run().owner === state.user.email && !state.user.disabled;
  const currentTicket = () => run().tickets.find(t => t.id === state.ticketId);
  const pageNames = { overview: 'Overview', simulation: 'Simulation lab', events: 'Event explorer', alerts: 'Alert queue', tickets: 'Tickets', evaluation: 'Evaluation', admin: 'Instructor', help: 'Getting started' };
  let toastTimer;
  function toast(message) { const el = document.getElementById('toast'); el.textContent = message; el.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 3600); }
  function navigate(view) { state.view = view; state.ticketId = null; state.search = ''; state.filter = 'All'; state.deleted = false; state.mobile = false; render(); window.scrollTo({ top: 0, behavior: 'instant' }); }
  function requireEdit() {
    if (!state.user) { authModal(); return false; }
    if (!editable()) { toast('รอบนี้เป็นแบบอ่านอย่างเดียว เริ่มรอบของคุณใน Simulation lab'); return false; }
    return true;
  }
  function heading(title, subtitle, actions = '') { return `<div class="page-heading"><div><h1>${title}</h1><p>${subtitle}</p></div><div class="heading-actions">${actions}</div></div>`; }
  function empty(title, text, action = '') { return `<div class="empty">${icon('search')}<h3>${title}</h3><p>${text}</p>${action}</div>`; }
  function panel(title, sub, body, right = '', extra = '') { return `<section class="panel ${extra}"><div class="panel-head"><div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ''}</div>${right}</div>${body}</section>`; }
  function shell(content) {
    const r = run();
    const nav = (view, ico, text, count) => `<button class="nav-item ${state.view === view ? 'active' : ''}" data-nav="${view}" ${state.view === view ? 'aria-current="page"' : ''} title="${text}">${icon(ico)}<span>${text}</span>${count ? `<span class="nav-count">${count}</span>` : ''}</button>`;
    return `<div class="shell"><div class="mobile-scrim ${state.mobile ? 'active' : ''}" data-action="menu"></div><aside class="sidebar ${state.mobile ? 'open' : ''}"><div class="brand"><div class="brand-mark">${icon('shield')}</div><span>sentinel<span class="brand-dot">.</span></span></div><div class="workspace"><div class="workspace-symbol">${icon('globe')}</div><div><strong>SOC Simulation Lab</strong><span>DemoCorp workspace</span></div></div><div class="nav-label">WORKSPACE</div><nav aria-label="เมนูหลัก">${nav('overview', 'grid', 'Overview')}${nav('simulation', 'play', 'Simulation lab')}${nav('events', 'activity', 'Event explorer')}${nav('alerts', 'bell', 'Alert queue', r.alerts.length)}${nav('tickets', 'ticket', 'Tickets', r.tickets.filter(t => !t.deleted && t.status !== 'Closed').length)}${nav('evaluation', 'chart', 'Evaluation')}<div class="nav-divider"></div><div class="nav-label">MANAGE</div>${nav('admin', 'users', 'Instructor')}${nav('help', 'book', 'Getting started')}</nav><div class="sidebar-bottom"><div class="lab-card"><strong>${icon('spark')} Your next investigation</strong><p>ฝึกคิดแบบนักวิเคราะห์ SOC<br>จากหลักฐานสู่การตัดสินใจ</p><button data-nav="simulation">Explore scenarios &nbsp; →</button></div><div class="profile"><div class="avatar">${state.user ? esc(state.user.name.slice(0, 2).toUpperCase()) : 'G'}</div><div><div class="profile-name">${esc(state.user?.name || 'Guest analyst')}</div><div class="profile-role">${esc(state.user?.role || 'Read-only demo')}</div></div><button data-action="${state.user ? 'logout' : 'login'}" title="${state.user ? 'ออกจากระบบ' : 'เข้าสู่ระบบ'}">${icon('logout')}</button></div></div></aside><main class="main"><header class="topbar"><div class="breadcrumb"><button class="icon-button mobile-menu" data-action="menu" aria-label="เปิดเมนู">${icon('menu')}</button><span>Workspace</span><span>/</span><strong>${pageNames[state.view]}</strong></div><div class="top-actions"><span class="system-status"><i class="dot"></i> Local simulation</span><span class="top-divider"></span>${badge('PROTOTYPE', 'purple')}<button class="icon-button" data-action="faults" aria-label="เปิดสถานะทดสอบ" title="Prototype test states">${icon('settings')}</button>${button(state.user ? esc(state.user.name) : 'เข้าสู่ระบบ', state.user ? 'account' : 'login', state.user ? 'users' : 'logout', 'small')}</div></header><div class="content">${content}<footer class="page-footer"><span>Sentinel SOC Lab <span style="color:#9b84ce">/</span> AI-assisted security operations</span><span>ข้อมูลจำลอง · AI fixture v1 · ไม่มีการเชื่อมต่อระบบจริง</span></footer></div></main></div>`;
  }
  function demoBanner() {
    if (!run().demo) return '';
    return `<div class="banner">${icon('info')}<div><strong>คุณกำลังสำรวจรอบตัวอย่าง</strong> &nbsp; ดูหลักฐานและคำวิเคราะห์จำลองได้ทันที เริ่มรอบของคุณเพื่อบันทึกผลการสืบสวน</div>${button('เริ่มทดลอง', 'new-run', 'arrow', 'small ghost')}</div>`;
  }
  function stat(label, value, foot, ico) { return `<div class="stat"><div class="stat-head">${label}${icon(ico)}</div><div class="stat-value">${value}</div><div class="stat-foot">${foot}</div></div>`; }
  function activityChart() {
    const r = run(); const bins = Array.from({ length: 8 }, (_, i) => r.events.filter(e => Math.floor(e.time / 10) === i).length); const max = Math.max(5, ...bins);
    const points = bins.map((v, i) => [40 + i * 76, 155 - v / max * 125]);
    const line = points.map((p, i) => `${i ? 'L' : 'M'}${p.join(',')}`).join(' ');
    return `<div class="chart"><svg viewBox="0 0 610 195" role="img" aria-label="จำนวน events ต่อช่วง 10 วินาทีของรอบนี้"><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a58bfa" stop-opacity=".25"/><stop offset="1" stop-color="#a58bfa" stop-opacity="0"/></linearGradient></defs>${[0, 1, 2, 3].map(i => `<line x1="40" y1="${30 + i * 42}" x2="578" y2="${30 + i * 42}" stroke="#282c39" stroke-dasharray="3 5"/><text x="15" y="${34 + i * 42}">${Math.round(max * (3 - i) / 3)}</text>`).join('')}<path d="${line} L572,156 L40,156Z" fill="url(#chart-fill)"/><path d="${line}" fill="none" stroke="#af94fa" stroke-width="2.5"/>${points.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="#b89bff"/><text x="${p[0]}" y="183" text-anchor="middle">${time(i * 10)}</text>`).join('')}</svg></div>`;
  }
  function overview() {
    const r = run(); const open = r.tickets.filter(t => !t.deleted && t.status !== 'Closed').length; const high = r.tickets.filter(t => !t.deleted && ['High', 'Critical'].includes(t.severity)).length;
    const latest = [...r.tickets].filter(t => !t.deleted).reverse().slice(0, 5);
    return heading('Security overview', 'ทุกสัญญาณมีเรื่องราว เริ่มสืบสวนจากหลักฐานที่สำคัญ', button('ส่งออกรายงาน', 'export', 'download') + button('เริ่มรอบจำลอง', 'new-run', 'plus', 'primary')) + demoBanner() +
      `<div class="stats">${stat('Events ingested', r.events.length.toLocaleString(), '<span>●</span> Authentication · Web · File', 'activity')}${stat('Active tickets', open, `${r.alerts.length} correlated alerts`, 'ticket')}${stat('High priority', high, 'เคสที่ควรตรวจสอบเป็นลำดับแรก', 'shield')}${stat('AI analysis', state.faults.ai ? 'Error' : r.tickets.length, state.faults.ai ? 'ตรวจหลักฐานต่อได้ · AI ไม่พร้อม' : '<span>Fixture</span> คำวิเคราะห์ตัวอย่าง', 'spark')}</div><div class="grid-main">${panel('Event activity', 'ปริมาณเหตุการณ์ที่ปล่อยแล้วในรอบนี้', activityChart() + `<div class="chart-note">${icon('clock')} ${r.id} &nbsp;·&nbsp; <span data-clock>${time(r.elapsed)}</span> / ${time(r.duration)} &nbsp;·&nbsp; ช่วงละ 10 วินาที</div>`, '<div class="chart-legend"><span><i></i>Ingested events</span></div>')}${panel('Detection pipeline', 'จากเหตุการณ์สู่การสืบสวน', `<div class="pipeline">${[['database', 'Event ingestion', 'รับ request, response และ log', r.events.length], ['shield', 'Rules + anomaly', 'เชื่อมโยงสัญญาณที่ควรตรวจสอบ', r.alerts.length], ['spark', 'AI-assisted analysis', 'สรุปหลักฐาน · mock analysis', state.faults.ai ? 'Error' : r.tickets.length], ['ticket', 'Human investigation', 'นักวิเคราะห์เป็นผู้ตัดสินใจ', open]].map(x => `<div class="pipeline-step"><div class="step-icon">${icon(x[0])}</div><div class="step-info"><strong>${x[1]}</strong><p>${x[2]}</p></div><span class="step-number">${x[3]}</span></div>`).join('')}</div>`, badge('SIMULATED', 'purple'))}</div>` +
      panel('Investigation queue', 'เคสล่าสุดที่รอการตรวจสอบและข้อสรุปจากคุณ', latest.length ? ticketTable(latest, true) + `<div class="panel-footer"><span>${latest.length} of ${r.tickets.filter(t => !t.deleted).length} tickets</span><button class="text-link" data-nav="tickets">View all tickets &nbsp; →</button></div>` : empty('ยังไม่มี Ticket', 'เหตุการณ์จะทยอยเข้ามาเมื่อเริ่มรอบจำลอง'), button('All tickets', 'go-tickets', 'arrow', 'small ghost')) +
      `<div class="bottom-grid">${panel('Analyst’s workspace', 'AI ช่วยอธิบาย คุณเป็นผู้ตรวจสอบ', `<div class="insight"><div class="insight-icon">${icon('spark')}</div><div><p>คำวิเคราะห์ต้องมีหลักฐานรองรับเสมอ เปรียบเทียบ request, response และ timeline ก่อนสรุปว่าเกิดผลกระทบจริง</p><button class="text-link" data-nav="events">Explore the evidence &nbsp; →</button></div></div>`, badge('HUMAN IN THE LOOP', 'purple'))}${panel('Severity distribution', 'ความรุนแรงของ Ticket ที่ยังไม่ถูกลบ', `<div class="severity-bars">${['Critical', 'High', 'Medium', 'Low'].map((s, i) => { const count = r.tickets.filter(t => !t.deleted && t.severity === s).length; return `<div class="bar-row"><label>${s}</label><div class="bar-track"><div class="bar-fill" style="width:${count / Math.max(1, r.tickets.filter(t => !t.deleted).length) * 100}%;background:${['#e8869a', '#c694e8', '#a58bfa', '#719fd8'][i]}"></div></div><strong>${count}</strong></div>`; }).join('')}</div>`)}</div>`;
  }
  function ticketTable(tickets, compact = false) {
    return `<div class="table-wrap"><table><thead><tr><th>TICKET / DETECTION</th><th>SEVERITY</th><th>STATUS</th>${compact ? '<th>SOURCE</th>' : '<th>DISPOSITION</th>'}<th>CREATED</th><th></th></tr></thead><tbody>${tickets.map(t => `<tr><td><button class="text-link table-title" data-ticket="${esc(t.id)}"><span class="row-title"><i class="severity-mark ${esc(t.severity)}"></i>${esc(t.title)}</span></button><div class="table-sub mono">${esc(t.id)} · ${esc(M.getScenario(t.scenarioId)?.asset || 'Manual investigation')}</div></td><td>${severity(t.severity)}</td><td>${status(t.status)}${t.deleted ? ' ' + badge('Deleted', 'red') : ''}</td><td>${compact ? badge(M.getScenario(t.scenarioId)?.detector || 'Manual', t.scenarioId === 'S05' ? 'purple' : 'gray') : esc(t.disposition || 'Pending review')}</td><td class="mono">${eventTime(t.created)}</td><td><button class="icon-button" data-ticket="${esc(t.id)}" aria-label="เปิด ${esc(t.id)}">${icon('chevron')}</button></td></tr>`).join('')}</tbody></table></div>`;
  }
  function controlStrip() {
    const r = run();
    return `<div class="status-strip"><div><div class="run-info">${badge(r.id, 'purple')}${status(r.state)}<span class="run-clock" data-clock>${time(r.elapsed)}</span><span class="muted small">/ ${time(r.duration)}</span></div><div class="progress"><span data-progress style="width:${r.elapsed / r.duration * 100}%"></span></div><div class="status-note">${r.events.length} events · ${r.alerts.length} alerts · ${r.tickets.length} tickets</div></div><div class="control-actions">${editable() && ['Running', 'Paused'].includes(r.state) ? button(r.state === 'Running' ? 'พักรอบ' : 'ดำเนินต่อ', 'pause', r.state === 'Running' ? 'pause' : 'play') : ''}${editable() && r.state !== 'Completed' ? button('จบรอบและประเมิน', 'finish', 'check') : button('ดูผลประเมิน', 'go-evaluation', 'chart')}${button('รอบใหม่', 'start-selected', 'plus', 'primary')}</div></div>`;
  }
  function simulation() {
    const own = state.user ? state.runs.filter(r => r.owner === state.user.email) : [];
    return heading('Build your investigation', 'เลือกสถานการณ์ ฝึกอ่านสัญญาณ และทดสอบการตัดสินใจของคุณ', badge('5 SCENARIOS', 'purple')) + controlStrip() +
      `<div class="panel-head" style="padding:0 0 19px"><div><h2>Choose your scenarios</h2><p>เลือกได้หลายสถานการณ์ต่อรอบ · ระยะเวลา 75 วินาที แล้วสืบสวนต่อได้</p></div><span class="small muted">${state.selection.length} selected</span></div><div class="scenario-grid">${M.scenarios.map((s, i) => `<article class="scenario-card ${state.selection.includes(s.id) ? 'selected' : ''}"><div class="scenario-top"><div class="step-icon">${icon(['shield', 'users', 'globe', 'activity', 'spark'][i])}</div><span class="eyebrow">LAB 0${i + 1}</span></div><div><h3>${s.title}</h3><p>${s.thai}</p></div><p>${s.description}</p><div class="scenario-meta">${badge(s.category, 'purple')}${badge(s.level)}</div><label><input type="checkbox" data-scenario="${s.id}" ${state.selection.includes(s.id) ? 'checked' : ''}> เลือกสถานการณ์นี้</label></article>`).join('')}<article class="scenario-card"><div class="step-icon">${icon('book')}</div><h3>Evidence before assumptions.</h3><p>ตรวจสอบสิ่งที่เกิดขึ้นจริง แยกผลกระทบที่ยืนยันแล้วออกจากข้อสันนิษฐาน และบันทึกสิ่งที่ยังไม่ทราบ</p>${button('คู่มือการฝึก', 'help', 'arrow', 'ghost')}</article></div><div class="callout">กฎและ AI ใช้ fixture ที่เตรียมไว้ ทุก request และผลกระทบเป็นข้อมูลจำลอง ไม่มีการส่งคำขอไปยังเป้าหมายจริง ในต้นแบบนี้เฉลยอยู่ในไฟล์ JavaScript จึงไม่เหมาะใช้เป็นข้อสอบที่ต้องป้องกันการเข้าถึงเฉลย</div>` +
      (own.length ? panel('Your previous runs', 'ประวัติบน browser นี้ · เลือกกลับไปทำต่อได้', `<div class="table-wrap"><table><thead><tr><th>RUN</th><th>SCENARIOS</th><th>STATE</th><th></th></tr></thead><tbody>${own.slice().reverse().map(r => `<tr><td class="mono">${r.id}</td><td>${r.scenarioIds.length} scenarios</td><td>${status(r.state)}</td><td>${button('เปิดรอบ', 'open-run', 'arrow', 'small', `data-id="${r.id}"`)}</td></tr>`).join('')}</tbody></table></div>`) : '');
  }
  function filterTools(kind, options) {
    return `<div class="section-tools"><label class="search">${icon('search')}<input id="table-search" aria-label="ค้นหา ${kind}" placeholder="Search ${kind}..." value="${esc(state.search)}"></label><select id="table-filter" aria-label="กรอง ${kind}">${options.map(o => `<option ${state.filter === o ? 'selected' : ''}>${o}</option>`).join('')}</select>${button('ค้นหา', 'search', 'search', 'small')}</div>`;
  }
  function events() {
    const r = run(); const q = state.search.toLowerCase(); const rows = r.events.filter(e => `${JSON.stringify(e)} ${eventTime(e.time)}`.toLowerCase().includes(q) && (state.filter === 'All' || e.source === state.filter)).slice().reverse();
    return heading('Event explorer', 'ค้นหาหลักฐานจาก request, response และ log ที่ปล่อยแล้ว', button('ส่งออก JSON', 'export', 'download')) + demoBanner() + panel('Event stream', `${rows.length} events · Timezone Asia/Bangkok (fixture)`, rows.length ? `<div class="table-wrap"><table><thead><tr><th>TIME / EVENT</th><th>MESSAGE</th><th>SOURCE</th><th>ASSET / USER</th><th>RESPONSE</th><th></th></tr></thead><tbody>${rows.map(e => `<tr><td class="mono">${eventTime(e.time)}<div class="table-sub">${e.id}</div></td><td><button class="text-link table-title" data-event="${e.id}">${esc(e.message)}</button><div class="table-sub mono">${esc(e.ip)} · ${esc(e.request)}</div></td><td>${badge(e.source)}</td><td>${esc(e.asset)}<div class="table-sub">${esc(e.user)}</div></td><td>${badge(e.response, e.response >= 400 ? 'yellow' : 'green')}</td><td><button class="icon-button" data-event="${e.id}" aria-label="เปิดหลักฐาน ${e.id}">${icon('chevron')}</button></td></tr>`).join('')}</tbody></table></div>` : empty('ไม่พบเหตุการณ์', q || state.filter !== 'All' ? 'ลองเปลี่ยนคำค้นหาหรือตัวกรอง' : 'รอ event แรก หรือเริ่มรอบจาก Simulation lab'), filterTools('events', ['All', 'Auth gateway', 'Web gateway', 'File audit']));
  }
  function alerts() {
    const q = state.search.toLowerCase(); const rows = run().alerts.filter(a => `${a.id} ${a.title} ${a.detector}`.toLowerCase().includes(q) && (state.filter === 'All' || a.detector === state.filter));
    return heading('Alert queue', 'สัญญาณจากกฎและความผิดปกติ พร้อมเชื่อมต่อไปยังเคสสืบสวน') + demoBanner() + panel('Correlated alerts', `${rows.length} alerts · สัญญาณเตือนไม่เท่ากับยืนยันผลกระทบ`, rows.length ? `<div class="table-wrap"><table><thead><tr><th>ALERT</th><th>DETECTOR</th><th>INITIAL SEVERITY</th><th>EVIDENCE</th><th>LINKED TICKET</th></tr></thead><tbody>${rows.map(a => { const t = run().tickets.find(t => t.scenarioId === a.scenarioId); return `<tr><td class="table-title">${esc(a.title)}<div class="table-sub mono">${a.id} · ${eventTime(a.time)}</div></td><td>${badge(a.detector, a.detector === 'Rule' ? 'blue' : 'purple')}</td><td>${severity(a.severity)}</td><td>${run().events.filter(e => e.scenarioId === a.scenarioId).map(e => `<button class="link-chip" data-event="${e.id}">${e.id}</button>`).join('')}</td><td>${t ? `<button class="text-link" data-ticket="${t.id}">${t.id}${t.deleted ? ' · Deleted' : ''} →</button>` : '—'}</td></tr>`; }).join('')}</tbody></table></div>` : empty('คิว Alert ว่าง', 'ยังไม่มีผลตรวจจับที่ตรงกับตัวกรองนี้'), filterTools('alerts', ['All', 'Rule', 'Anomaly']));
  }
  function tickets() {
    if (state.ticketId && currentTicket()) return ticketDetail();
    const q = state.search.toLowerCase(); const rows = run().tickets.filter(t => !!t.deleted === state.deleted && `${t.id} ${t.title} ${t.reason}`.toLowerCase().includes(q) && (state.filter === 'All' || t.status === state.filter));
    return heading('Investigation tickets', 'รวบรวมหลักฐาน บันทึกข้อสรุป และติดตามทุกการตัดสินใจ', button('สร้าง Ticket', 'create-ticket', 'plus', 'primary')) + demoBanner() + panel('Ticket workspace', 'รายการที่ลบยังคงอยู่ใน audit และผลประเมิน', rows.length ? ticketTable(rows) : empty(state.deleted ? 'ไม่มี Ticket ที่ถูกลบ' : 'ไม่พบ Ticket', 'ลองเปลี่ยนตัวกรอง หรือสร้างเคสจากหลักฐานที่มี'), filterTools('tickets', ['All', ...M.statuses])) + `<div style="margin-top:15px"><label class="toggle"><input type="checkbox" id="show-deleted" ${state.deleted ? 'checked' : ''}> แสดงเฉพาะ Ticket ที่ลบแล้ว</label></div>`;
  }
  function ticketDetail() {
    const r = run(); const t = currentTicket(); const a = M.analysis(r, t); const canEdit = editable() && !t.deleted;
    const aiBody = state.faults.ai ? `<div class="panel-body"><div class="notice error">AI analysis unavailable · จำลองบริการไม่พร้อมใช้งาน<br>กฎยังเปิด Ticket ได้ และคุณตรวจสอบหลักฐานต่อได้</div>${button('ลองวิเคราะห์อีกครั้ง', 'retry-ai', 'refresh', 'small')}</div>` : `<div class="panel-body"><p class="ai-summary">${esc(a.summary)}</p><div class="fact-grid"><div><label>OBSERVED IMPACT</label><p>${esc(a.impact)}</p></div><div><label>POTENTIAL IMPACT</label><p>อาจมีการเข้าถึงข้อมูลนอกขอบเขต ต้องมีหลักฐานเพิ่มก่อนยืนยัน</p></div><div><label>CONFIDENCE</label><p>${esc(a.confidence)}</p></div><div><label>UNKNOWNS / NEXT CHECKS</label><p>${esc(a.unknown)}</p></div></div><div style="margin-top:17px">${a.evidence.map(e => `<button class="link-chip" data-event="${e.id}">${e.id}</button>`).join('')}</div><p class="status-note">Mock model · fixture-v1 / prompt-v1 · ประเมินจาก ${a.evidence.length} events ที่ปล่อยแล้ว</p></div>`;
    return heading(esc(t.title), `${t.id} / ${r.id}`, button('กลับรายการ', 'go-tickets', 'back') + button('อัปเดตหลักฐาน', 'refresh-evidence', 'refresh') + (editable() ? button(t.deleted ? 'กู้คืน Ticket' : 'ลบ Ticket', t.deleted ? 'restore-ticket' : 'delete-ticket', t.deleted ? 'refresh' : 'trash', t.deleted ? '' : 'danger') : '')) + (r.demo ? demoBanner() : '') + (t.deleted ? '<div class="notice error">Ticket นี้ถูกลบแบบ soft delete แล้ว ต้องกู้คืนก่อนแก้ไข ข้อมูลยังคงอยู่ในผลประเมิน</div>' : '') +
      `<div class="detail-meta" style="margin-bottom:22px">${severity(t.severity)}${status(t.status)}${badge(t.disposition || 'Awaiting human review', 'purple')}${badge(M.getScenario(t.scenarioId)?.asset || 'Manual case')}</div><div class="detail-grid"><div class="stack">${panel('AI investigation brief', 'คำวิเคราะห์ตัวอย่าง · ตรวจสอบกับหลักฐานก่อนตัดสินใจ', aiBody, badge('MOCK AI', 'purple'), 'ai-panel')}${panel('Evidence timeline', `${a.evidence.length} linked events · อ่านข้อมูลต้นทางได้ทุกรายการ`, `<div class="panel-body"><div class="timeline">${a.evidence.map(e => `<div class="timeline-item"><strong>${esc(e.message)}</strong><p class="mono">${eventTime(e.time)} · ${esc(e.asset)} · HTTP ${e.response}</p><button class="text-link" data-event="${e.id}">${e.id} · View request & response →</button></div>`).join('') || '<p class="muted small">ยังไม่มีหลักฐาน</p>'}</div></div>`)}${panel('Investigation notes', 'บันทึกของคนแยกจากผล AI · เก็บประวัติการแก้ไข', `<div class="panel-body">${canEdit ? `<form id="note-form"><div class="field"><label for="note-content">เพิ่มบันทึกการสืบสวน</label><textarea id="note-content" name="content" required maxlength="2000" placeholder="พบอะไร หลักฐานใดสนับสนุน และต้องตรวจอะไรต่อ..."></textarea></div><div class="field"><label for="note-evidence">หลักฐานอ้างอิง (ไม่บังคับ)</label><select id="note-evidence" name="evidence"><option value="">ไม่ระบุ</option>${a.evidence.map(e => `<option value="${e.id}">${e.id} · ${esc(e.message)}</option>`).join('')}</select></div><div class="form-error" role="alert"></div>${button('เพิ่มบันทึก', 'submit-note', 'plus', 'small primary')}</form>` : '<p class="small muted">อ่านบันทึกได้ เริ่มรอบของคุณเพื่อเพิ่มหรือแก้ไข</p>'}<div style="margin-top:17px"><label class="toggle"><input type="checkbox" id="show-deleted-notes" ${state.noteDeleted ? 'checked' : ''}> แสดงบันทึกที่ลบแล้วด้วย</label></div>${t.notes.filter(n => !n.deleted || state.noteDeleted).map(n => `<article class="note"><div class="note-meta"><span>${esc(n.author)} · ${time(n.time)} · v${n.versions.length + 1}</span>${n.deleted ? badge('Deleted', 'red') : ''}</div><p>${esc(n.content)}</p>${n.evidence ? `<button class="link-chip" data-event="${esc(n.evidence)}">${esc(n.evidence)}</button>` : ''}<div class="note-actions">${canEdit && n.author === state.user.email ? (n.deleted ? `<button class="text-link" data-note-action="restore" data-id="${n.id}">กู้คืน</button>` : `<button class="text-link" data-note-action="edit" data-id="${n.id}">แก้ไข</button><button class="text-link" data-note-action="delete" data-id="${n.id}">ลบ</button>`) : ''}<button class="text-link" data-note-action="history" data-id="${n.id}">ประวัติ (${n.versions.length})</button></div></article>`).join('') || '<p class="small muted" style="margin-top:15px">ยังไม่มีบันทึกการสืบสวน</p>'}</div>`)}</div><div class="stack">${panel('Your assessment', 'ให้เหตุผลและหลักฐานประกอบการตัดสินใจ', `<div class="panel-body"><form id="assessment-form"><fieldset ${canEdit ? '' : 'disabled'} style="border:0;padding:0;margin:0;min-width:0"><div class="field"><label for="ticket-title">ชื่อ Ticket</label><input id="ticket-title" name="title" value="${esc(t.title)}" maxlength="120" required></div><div class="form-row"><div class="field"><label for="ticket-severity">Severity</label><select id="ticket-severity" name="severity">${['Low', 'Medium', 'High', 'Critical'].map(s => `<option ${s === t.severity ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="field"><label for="ticket-status">Status</label><select id="ticket-status" name="status">${M.statuses.map(s => `<option ${s === t.status ? 'selected' : ''}>${s}</option>`).join('')}</select></div></div><div class="field"><label for="ticket-disposition">ข้อสรุปของนักวิเคราะห์</label><select id="ticket-disposition" name="disposition"><option value="">เลือกข้อสรุป...</option>${M.dispositions.map(d => `<option ${d === t.disposition ? 'selected' : ''}>${d}</option>`).join('')}</select></div><div class="field"><label for="ticket-reason">เหตุผล / ข้อมูลที่ต้องตรวจเพิ่ม</label><textarea id="ticket-reason" name="reason" maxlength="2000" required placeholder="อ้างหลักฐานและแยกสิ่งที่ยืนยันแล้วออกจากข้อสันนิษฐาน">${esc(t.reason)}</textarea><small>Open → Investigating → Resolved → Closed</small></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary" style="width:100%">${icon('check')} บันทึกการประเมิน</button></fieldset></form></div>`)}${panel('Audit trail', 'ประวัติการตัดสินใจที่แก้ไขย้อนหลังไม่ได้ผ่าน UI', `<div class="panel-body audit-list">${r.audit.filter(a => a.entity === t.id || a.entity === 'ALT-' + t.scenarioId?.slice(1)).map(a => `<div class="audit-entry"><strong>${esc(a.action)}</strong><p>${esc(a.actor)} · ${time(a.time)}</p><p>${esc(a.reason)}</p></div>`).join('') || '<p class="small muted">ยังไม่มีการเปลี่ยนแปลง</p>'}</div>`)}</div></div>`;
  }
  function evaluation() {
    const r = run();
    if (r.state !== 'Completed') return heading('Evaluation & debrief', 'ทบทวนหลักฐานและเหตุผลเมื่อคุณพร้อมจบรอบ') + panel('รอบนี้ยังไม่จบ', '', empty('ผลประเมินจะเปิดหลังจบรอบ', 'คุณยังกลับไปสืบสวนและบันทึกข้อสรุปได้ จบรอบก่อนเพื่อเปิดเฉลย', editable() ? button('จบรอบและดูผล', 'finish', 'check', 'primary') : button('เริ่มรอบของคุณ', 'new-run', 'play', 'primary')));
    const e = M.evaluate(r);
    return heading('Evaluation & debrief', 'เปรียบเทียบข้อสรุปของคุณกับเฉลยของสถานการณ์จำลอง', button('ส่งออกรายงาน', 'export', 'download') + button('ฝึกรอบใหม่', 'new-run', 'plus', 'primary')) + (r.demo ? demoBanner() : '') + `<div class="stats">${stat('Correct classifications', `${e.correct} / ${e.total}`, 'หนึ่งหน่วยต่อหนึ่งสถานการณ์', 'check')}${stat('Undetermined', e.pending, 'ยังไม่ถือว่ายืนยันว่าปลอดภัย', 'search')}${stat('Evidence collected', r.events.length, `${e.rows.filter(x => x.complete).length} scenarios มีหลักฐานครบ`, 'database')}${stat('Simulation time', time(r.elapsed), 'เวลาจำลอง ไม่รวมช่วงพัก', 'clock')}</div>` +
      panel('Scenario review', 'รายการที่ลบยังถูกนับในการประเมิน · รอบที่จบก่อนกำหนดอาจมีหลักฐานไม่ครบ', `<div class="table-wrap"><table><thead><tr><th>SCENARIO</th><th>YOUR ASSESSMENT</th><th>GROUND TRUTH</th><th>RESULT</th></tr></thead><tbody>${e.rows.map(row => `<tr><td class="table-title">${esc(row.title)}<div class="table-sub">${row.complete ? 'Evidence complete' : 'Incomplete evidence'}${row.deleted ? ' · Ticket deleted' : ''}</div></td><td>${badge(row.answer, row.answer === 'Undetermined' ? 'yellow' : 'gray')}</td><td>${badge(row.truth, 'purple')}</td><td>${badge(row.correct ? 'Correct' : row.answer === 'Undetermined' ? 'Pending / unresolved' : 'Review needed', row.correct ? 'green' : 'yellow')}</td></tr>`).join('')}</tbody></table></div>`) + `<div class="bottom-grid">${panel('What the evidence tells us', 'ใช้เป็นแนวทางทบทวน ไม่ใช่ผลประเมินโมเดลจริง', `<div class="panel-body">${e.rows.map(row => `<div class="audit-entry"><strong>${esc(row.title)}</strong><p>${esc(M.getScenario(row.id).impact)}</p></div>`).join('')}</div>`)}${panel('Detection experiment', 'A / B / C comparison', `<div class="panel-body"><div class="notice">ยังไม่มีการทดลองประมวลผล A/B/C จริงในต้นแบบ จึงไม่แสดง Precision / Recall หรือคะแนนประสิทธิภาพ AI ที่คำนวณขึ้นแทนผลทดลอง</div><div class="audit-entry"><strong>A · Rules only</strong><p>Not measured</p></div><div class="audit-entry"><strong>B · Rules + anomaly</strong><p>Not measured</p></div><div class="audit-entry"><strong>C · Rules + anomaly + AI</strong><p>Not measured · คำวิเคราะห์ใน UI เป็น fixture</p></div></div>`)}</div>`;
  }
  function admin() {
    if (state.user?.role !== 'Instructor') return heading('Instructor workspace', 'ติดตามรอบฝึกและจัดการบัญชีตัวอย่าง') + panel('Restricted workspace', '', empty('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'หน้าตัวอย่างนี้สำหรับบทบาท Instructor ใช้บัญชีเดโม Instructor เพื่อสำรวจ', button('เลือกบัญชีเดโม', 'login', 'users', 'primary')));
    return heading('Instructor workspace', 'จัดการบัญชีและโควตาตัวอย่างบน browser นี้', badge('DEMO INSTRUCTOR', 'purple')) + `<div class="notice">สิทธิ์ในต้นแบบเป็นการสาธิต UI เท่านั้น ไม่มี backend authentication หรือการป้องกันข้อมูลจริง</div>` + panel('Demo accounts', 'ปิดใช้งานหรือปรับโควตาของ Analyst · มีผลกับการเข้าสู่ระบบและเริ่มรอบในต้นแบบ', `<div class="table-wrap"><table><thead><tr><th>ACCOUNT</th><th>ROLE</th><th>STATUS</th><th>QUOTA (RUNS)</th><th>ACTIONS</th></tr></thead><tbody>${accounts().filter(a => a.role === 'Analyst').map(a => `<tr><td>${esc(a.name)}<div class="table-sub">${esc(a.email)}</div></td><td>${badge(a.role, 'purple')}</td><td>${badge(a.disabled ? 'Disabled' : 'Active', a.disabled ? 'red' : 'green')}</td><td>${state.runs.filter(r => r.owner === a.email).length} / ${a.quota ?? 10}</td><td><div class="account-actions">${button(a.disabled ? 'เปิดใช้งาน' : 'ปิดใช้งาน', 'toggle-account', 'users', 'small', `data-id="${esc(a.email)}"`)}${button('ปรับโควตา', 'quota-account', 'settings', 'small', `data-id="${esc(a.email)}"`)}</div></td></tr>`).join('')}</tbody></table></div>`) + `<div style="margin-top:22px">${panel('Learner runs', 'เปิดดูหลักฐานและเพิ่มความเห็นโดยไม่เขียนทับข้อสรุปของผู้เรียน', state.runs.length ? `<div class="table-wrap"><table><thead><tr><th>RUN</th><th>OWNER</th><th>STATUS</th><th>TICKETS</th><th></th></tr></thead><tbody>${state.runs.map(r => `<tr><td class="mono">${r.id}</td><td>${esc(r.owner)}</td><td>${status(r.state)}</td><td>${r.tickets.length}</td><td>${button('ตรวจรอบ', 'inspect-run', 'search', 'small', `data-id="${r.id}"`)}</td></tr>`).join('')}</tbody></table></div>` : empty('ยังไม่มีรอบของผู้เรียน', 'เข้าสู่บัญชี Analyst และเริ่มรอบก่อน'))}</div>`;
  }
  function help() {
    return heading('Welcome to the lab.', 'ต้นแบบที่กดใช้งานได้สำหรับ AI-Assisted SOC Simulation Platform') + panel('Your first investigation', 'จาก alert สู่ข้อสรุปใน 6 ขั้นตอน', `<div class="panel-body"><div class="help-grid">${[['01', 'เข้าสู่ระบบเดโม', 'เลือก Analyst เพื่อเริ่มฝึก หรือ Instructor เพื่อดูหน้ากำกับการฝึก'], ['02', 'เลือกสถานการณ์', 'Simulation lab มี 5 สถานการณ์ เลือกหลายสถานการณ์ร่วมกันได้'], ['03', 'ตรวจหลักฐาน', 'รอ events ทยอยเข้ามา เปิด Event explorer หรือ Alert queue เพื่อดูต้นทาง'], ['04', 'สืบสวน Ticket', 'อ่าน AI brief เทียบ request / response และเพิ่มบันทึกอ้างอิงหลักฐาน'], ['05', 'บันทึกข้อสรุป', 'เปลี่ยนสถานะตามลำดับ เลือก disposition และระบุเหตุผล'], ['06', 'จบรอบและทบทวน', 'เปิดเฉลย ดูข้อสรุปที่ยังค้าง และส่งออกรายงาน JSON']].map(x => `<div class="scenario-card"><span class="eyebrow">STEP ${x[0]}</span><h3>${x[1]}</h3><p>${x[2]}</p></div>`).join('')}</div></div>`) + `<div class="callout">Prototype scope: ใช้ localStorage เก็บรอบฝึกและชื่อบัญชีตัวอย่าง ไม่มีระบบยืนยันตัวตนจริง ไม่เก็บรหัสผ่าน ไม่เชื่อมต่อ AI หรือฐานข้อมูล ข้อมูลแยกตามบัญชีเพื่อสาธิต flow แต่ไม่ใช่ขอบเขตความปลอดภัย ผู้ใช้เครื่องเดียวกันสามารถอ่านข้อมูลทั้งหมดได้</div>` + panel('Explore edge cases', 'ใช้ปุ่ม Test states ที่มุมขวาบน', `<div class="panel-body"><p class="small muted">ทดสอบ AI error, quota เต็ม, session หมดอายุ และ empty state ได้จากแผงเดียว กรณีไม่มีสิทธิ์ดูได้จากเมนู Instructor ในบัญชี Analyst ส่วน validation ทดสอบได้จากการปิด Ticket โดยไม่ใส่ข้อสรุปหรือข้ามลำดับสถานะ</p><div style="margin-top:17px">${button('เปิด Test states', 'faults', 'settings')}${button('เริ่มรอบจำลอง', 'new-run', 'play', 'primary')}</div></div>`);
  }
  function render() { document.getElementById('app').innerHTML = shell(({ overview, simulation, events, alerts, tickets, evaluation, admin, help })[state.view]()); }
  let focusBeforeModal;
  function modal(title, body, wide = false) {
    focusBeforeModal = document.activeElement;
    document.getElementById('modal-root').innerHTML = `<dialog class="modal ${wide ? 'wide' : ''}" aria-labelledby="modal-title"><div class="modal-head"><h2 id="modal-title">${title}</h2><button class="icon-button" data-action="close-modal" aria-label="ปิดหน้าต่าง">${icon('close')}</button></div><div class="modal-body">${body}</div></dialog>`;
    const d = document.querySelector('dialog'); const returnFocus = focusBeforeModal; d.showModal(); d.addEventListener('close', () => { if (d.isConnected) { d.remove(); returnFocus?.focus(); } });
  }
  function closeModal() { document.querySelector('dialog')?.close(); }
  function accounts() {
    const base = [{ email: 'analyst@demo.test', name: 'Demo Analyst', role: 'Analyst', quota: 10, disabled: false }, { email: 'instructor@demo.test', name: 'Demo Instructor', role: 'Instructor', quota: 10, disabled: false }];
    return [...base.map(a => ({ ...a, ...state.accounts.find(x => x.email === a.email) })), ...state.accounts.filter(a => !base.some(b => b.email === a.email))];
  }
  function accountPatch(email, patch) { let a = state.accounts.find(a => a.email === email); if (!a) { a = { ...accounts().find(a => a.email === email) }; state.accounts.push(a); } Object.assign(a, patch); save(); }
  function authModal(mode = 'login', error = '') {
    state.authMode = mode;
    modal('เข้าสู่ SOC workspace', `<div class="auth-logo"><div class="brand-mark">${icon('shield')}</div><strong>sentinel<span class="brand-dot">.</span></strong></div><p>บัญชีสำหรับจำลอง flow เท่านั้น ใช้รหัส <strong style="color:var(--purple)">demo1234</strong> กับทุกบัญชีตัวอย่าง ไม่ใช้รหัสผ่านจริงของคุณ</p><div class="auth-tabs"><button class="${mode === 'login' ? 'active' : ''}" data-action="auth-login">Login</button><button class="${mode === 'register' ? 'active' : ''}" data-action="auth-register">Create demo account</button></div><form id="auth-form">${mode === 'register' ? '<div class="field"><label for="auth-name">ชื่อที่แสดง</label><input id="auth-name" name="name" required maxlength="60" autocomplete="off"></div>' : ''}<div class="field"><label for="auth-email">อีเมลบัญชีตัวอย่าง</label><input id="auth-email" name="email" type="email" required maxlength="100" autocomplete="off" value="${mode === 'login' ? 'analyst@demo.test' : ''}" placeholder="yourname@demo.test"></div><div class="field"><label for="auth-password">รหัสเดโม (demo1234)</label><input id="auth-password" name="password" type="password" required autocomplete="off" placeholder="demo1234"></div><div class="form-error" role="alert">${esc(error)}</div><button type="submit" class="btn primary" style="width:100%">${mode === 'login' ? 'เข้าสู่ระบบเดโม' : 'สร้างบัญชี Analyst จำลอง'}</button></form><div class="feature-list">${button('ใช้บัญชี Analyst', 'demo-analyst', 'users', 'small')}${button('ใช้บัญชี Instructor', 'demo-instructor', 'users', 'small')}</div><p class="status-note">ไม่เก็บรหัสผ่าน · ข้อมูลรอบฝึกเก็บเฉพาะ browser นี้ · Refresh แล้วต้องเข้าสู่ระบบใหม่</p>`);
  }
  function login(email) {
    const a = accounts().find(a => a.email === email);
    if (!a || a.disabled) throw Error('เข้าสู่ระบบไม่สำเร็จ บัญชีหรือรหัสเดโมไม่ถูกต้อง หรือบัญชีถูกปิดใช้งาน');
    if (editable() && run().state === 'Running') { run().state = 'Paused'; save(); }
    state.user = { ...a }; state.selectedRun = state.runs.filter(r => r.owner === email).at(-1)?.id || null;
    closeModal(); navigate(a.role === 'Instructor' ? 'admin' : 'simulation'); toast('เข้าสู่ระบบเดโมแล้ว');
  }
  function eventModal(id) {
    const e = run().events.find(e => e.id === id); if (!e) return toast('หลักฐานยังไม่ถูกปล่อยในรอบนี้');
    modal('Evidence / ' + esc(e.id), `<p>${esc(e.message)}</p><dl class="key-value"><dt>Timestamp</dt><dd>${eventTime(e.time)} ICT · fixture time</dd><dt>Source</dt><dd>${esc(e.source)}</dd><dt>Asset / user</dt><dd>${esc(e.asset)} / ${esc(e.user)}</dd><dt>Source IP</dt><dd>${esc(e.ip)}</dd></dl><h3>Request</h3><pre>${esc(JSON.stringify({ request: e.request, host: 'democorp.test', source_ip: e.ip, user: e.user, session: e.scenarioId === 'S02' && e.time >= 29 ? 'SES-041' : null }, null, 2))}</pre><h3>Response / log</h3><pre>${esc(JSON.stringify({ status: e.response, event_id: e.id, message: e.message, asset: e.asset, source: e.source, simulated: true }, null, 2))}</pre><p class="status-note">หลักฐานอ่านอย่างเดียว · fixture-v1 · ไม่มี password หรือ access token</p>`, true);
  }
  function faultsModal() {
    modal('Prototype test states', `<p>สลับสถานะเพื่อสาธิตเส้นทางข้อผิดพลาด โดยไม่กระทบบริการจริง</p><div class="field"><label class="toggle"><input type="checkbox" id="fault-ai" ${state.faults.ai ? 'checked' : ''}> AI unavailable · ตรวจหลักฐานต่อได้</label></div><div class="field"><label class="toggle"><input type="checkbox" id="fault-quota" ${state.faults.quota ? 'checked' : ''}> โควตาเต็ม · ไม่สามารถเริ่มรอบใหม่</label></div><div class="feature-list">${button('Session หมดอายุ', 'expire', 'clock')}${button('Empty state', 'empty-run', 'database')}${button('ไม่มีสิทธิ์', 'no-access', 'shield')}${button('ล้างสถานะทดสอบ', 'clear-faults', 'refresh')}</div><div class="callout">Login error: กรอกรหัสที่ไม่ใช่ demo1234<br>Validation error: ข้ามสถานะจาก Open ไป Closed หรือไม่เลือกข้อสรุป<br>AI error: เปิด Ticket หลังเลือก AI unavailable</div>`);
  }
  function startSelected() {
    if (!state.user) return authModal();
    if (!state.selection.length) return toast('เลือกอย่างน้อย 1 สถานการณ์');
    const a = accounts().find(a => a.email === state.user.email);
    if (a.disabled) return logout('บัญชีถูกปิดใช้งาน');
    if (state.faults.quota || state.runs.filter(r => r.owner === state.user.email).length >= (a.quota ?? 10)) return modal('Run quota reached', `<div class="notice error">โควตารอบจำลองเต็มแล้ว คุณยังตรวจรอบเดิมได้ ให้ Instructor ปรับโควตา หรือปิดสถานะจำลองโควตาเต็มใน Test states</div>${button('กลับไปตรวจ Ticket', 'close-and-tickets', 'ticket')}`);
    state.runs.filter(r => r.owner === state.user.email && r.state === 'Running').forEach(r => { r.state = 'Paused'; });
    const r = M.makeRun(state.selection); r.owner = state.user.email; r.comments = []; state.runs.push(r); state.selectedRun = r.id;
    M.audit(r, state.user.email, 'Run started', r.id, state.selection.join(', ')); save(); closeModal(); navigate('overview'); toast('เริ่มรอบแล้ว · event แรกจะเข้ามาใน 5 วินาที');
  }
  function logout(message = 'ออกจากระบบเดโมแล้ว') {
    if (editable() && run().state === 'Running') run().state = 'Paused';
    save(); state.user = null; state.selectedRun = null; closeModal(); navigate('overview'); toast(message);
  }
  function confirmForm(title, text, type, extra = '') { modal(title, `<p>${text}</p><form id="${type}">${extra}<div class="field"><label for="confirm-reason">เหตุผล</label><textarea id="confirm-reason" name="reason" required maxlength="2000" placeholder="ระบุเหตุผลเพื่อเก็บใน audit trail"></textarea></div><div class="form-error" role="alert"></div><div class="modal-actions">${button('ยกเลิก', 'close-modal', '')}<button type="submit" class="btn ${type.includes('delete') ? 'danger' : 'primary'}">ยืนยัน</button></div></form>`); }
  function createTicketModal() {
    if (!requireEdit()) return;
    if (!run().events.length) return toast('ต้องมีหลักฐานอย่างน้อย 1 event ก่อนสร้าง Ticket');
    modal('Create investigation ticket', `<p>สร้างเคสจากหลักฐานที่ปล่อยแล้วในรอบของคุณ</p><form id="create-ticket-form"><div class="field"><label for="new-title">ชื่อ Ticket</label><input id="new-title" name="title" maxlength="120" required></div><div class="field"><label for="new-evidence">หลักฐานตั้งต้น</label><select id="new-evidence" name="evidence">${run().events.map(e => `<option value="${e.id}">${e.id} · ${esc(e.message)}</option>`).join('')}</select></div><div class="field"><label for="new-severity">Severity</label><select id="new-severity" name="severity">${['Low', 'Medium', 'High', 'Critical'].map(s => `<option>${s}</option>`).join('')}</select></div><div class="field"><label for="new-reason">เหตุผลที่เปิดเคส</label><textarea id="new-reason" name="reason" required maxlength="2000"></textarea></div><div class="form-error" role="alert"></div><div class="modal-actions"><button class="btn primary" type="submit">สร้าง Ticket</button></div></form>`);
  }
  function exportReport() {
    const r = run(); const data = { prototype: true, warning: 'Simulated evidence and mock AI; not a real detector benchmark', run: r, evaluation: r.state === 'Completed' ? M.evaluate(r) : 'Locked until run completion' };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = `sentinel-${r.id}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); toast('ส่งออกรายงาน JSON แล้ว');
  }
  function inspectRun(id) {
    if (state.user?.role !== 'Instructor') return toast('ไม่มีสิทธิ์');
    const r = state.runs.find(r => r.id === id); if (!r) return;
    modal('Review / ' + r.id, `<p>${esc(r.owner)} · ${r.tickets.length} tickets · ${r.events.length} events</p>${r.tickets.map(t => `<div class="note"><strong>${esc(t.id)} · ${esc(t.title)}</strong><div class="detail-meta">${severity(t.severity)}${status(t.status)}${badge(t.disposition || 'Pending')}</div><p>${esc(t.reason || 'ยังไม่มีข้อสรุป')}</p><details><summary class="small muted">หลักฐาน (${t.evidenceIds.length})</summary><pre>${esc(JSON.stringify(r.events.filter(e => t.evidenceIds.includes(e.id)), null, 2))}</pre></details>${button('ปรับ severity / status', 'instructor-ticket', 'settings', 'small', `data-id="${r.id}" data-ticket-id="${t.id}"`)}</div>`).join('') || '<p>ยังไม่มี Ticket</p>'}<form id="instructor-comment" data-run="${r.id}" style="margin-top:20px"><div class="field"><label for="instructor-note">ความเห็นประกอบการประเมิน</label><textarea id="instructor-note" name="content" required maxlength="2000"></textarea></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">เพิ่มความเห็น</button></form>${(r.comments || []).map(c => `<div class="note"><div class="note-meta">${esc(c.author)}</div><p>${esc(c.content)}</p></div>`).join('')}`, true);
  }
  function noteAction(action, id) {
    const t = currentTicket(); const n = t?.notes.find(n => n.id === id); if (!n) return;
    if (action === 'history') return modal('Note version history', n.versions.length ? n.versions.map((v, i) => `<div class="note"><div class="note-meta">Version ${i + 1} · ${time(v.time)}</div><p>${esc(v.content)}</p></div>`).join('') : '<p>ยังไม่มีเวอร์ชันก่อนหน้า</p>');
    if (!requireEdit() || n.author !== state.user.email || t.deleted) return;
    if (action === 'edit') modal('Edit investigation note', `<form id="edit-note-form" data-note="${id}"><div class="field"><label for="edit-note">เนื้อหาบันทึก</label><textarea id="edit-note" name="content" required maxlength="2000">${esc(n.content)}</textarea></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary">บันทึกเวอร์ชันใหม่</button></form>`);
    if (action === 'delete') confirmForm('Delete note?', 'บันทึกจะถูกลบแบบ soft delete และกู้คืนได้', 'delete-note-form', `<input type="hidden" name="note" value="${id}">`);
    if (action === 'restore') { n.deleted = false; M.audit(run(), state.user.email, 'Note restored', t.id, id); save(); render(); toast('กู้คืนบันทึกแล้ว'); }
  }
  document.addEventListener('click', event => {
    const el = event.target.closest('button,[data-action]'); if (!el) return;
    if (el.dataset.nav) return navigate(el.dataset.nav);
    if (el.dataset.ticket) { state.ticketId = el.dataset.ticket; state.view = 'tickets'; state.noteDeleted = false; render(); window.scrollTo(0, 0); return; }
    if (el.dataset.event) return eventModal(el.dataset.event);
    if (el.dataset.noteAction) return noteAction(el.dataset.noteAction, el.dataset.id);
    const a = el.dataset.action; const r = run();
    switch (a) {
      case 'menu': state.mobile = !state.mobile; render(); break;
      case 'login': case 'auth-login': authModal(); break;
      case 'auth-register': authModal('register'); break;
      case 'demo-analyst': case 'demo-instructor': try { login(a === 'demo-analyst' ? 'analyst@demo.test' : 'instructor@demo.test'); } catch (e) { authModal('login', e.message); } break;
      case 'logout': logout(); break;
      case 'account': modal('Demo account', `<dl class="key-value"><dt>Name</dt><dd>${esc(state.user.name)}</dd><dt>Email</dt><dd>${esc(state.user.email)}</dd><dt>Role</dt><dd>${esc(state.user.role)}</dd></dl>${button('ออกจากระบบ', 'logout', 'logout')}`); break;
      case 'new-run': if (!state.user) authModal(); else navigate('simulation'); break;
      case 'start-selected': startSelected(); break;
      case 'pause': if (requireEdit()) { r.state = r.state === 'Running' ? 'Paused' : 'Running'; M.audit(r, state.user.email, 'Run ' + r.state, r.id, 'Simulation control'); save(); render(); } break;
      case 'finish': if (requireEdit()) modal('จบรอบจำลอง?', `<p>หลังจบรอบจะเปิดเฉลย และไม่มี event ใหม่เข้ามา คุณยังตรวจทาน Ticket ได้</p><div class="notice">มี ${r.tickets.filter(t => !t.disposition || t.disposition === 'Undetermined').length} Ticket ที่ยังไม่สรุป · หลักฐาน ${r.events.length} events</div><div class="modal-actions">${button('สืบสวนต่อ', 'close-modal', '')}${button('ยืนยันจบรอบ', 'confirm-finish', 'check', 'primary')}</div>`); break;
      case 'confirm-finish': if (requireEdit()) { r.state = 'Completed'; M.audit(r, state.user.email, 'Run completed', r.id, 'User ended exercise'); save(); closeModal(); navigate('evaluation'); } break;
      case 'go-tickets': navigate('tickets'); break;
      case 'go-evaluation': navigate('evaluation'); break;
      case 'close-and-tickets': closeModal(); navigate('tickets'); break;
      case 'help': navigate('help'); break;
      case 'close-modal': closeModal(); break;
      case 'search': state.search = document.getElementById('table-search')?.value || ''; render(); break;
      case 'refresh-evidence': {
        const drafts = ['assessment-form', 'note-form'].map(id => { const f = document.getElementById(id); return { id, values: f ? Object.fromEntries(new FormData(f)) : {} }; });
        render();
        drafts.forEach(({ id, values }) => { const f = document.getElementById(id); if (f) Object.entries(values).forEach(([name, value]) => { if (f.elements.namedItem(name)) f.elements.namedItem(name).value = value; }); });
        toast('อัปเดตหลักฐานแล้ว · เก็บข้อความที่กำลังกรอกไว้'); break;
      }
      case 'create-ticket': createTicketModal(); break;
      case 'delete-ticket': if (requireEdit()) confirmForm('Delete ticket?', 'Ticket และหลักฐานจะยังคงอยู่ในผลประเมิน สามารถกู้คืนได้จากรายการที่ลบแล้ว', 'delete-ticket-form'); break;
      case 'restore-ticket': if (requireEdit()) { currentTicket().deleted = false; M.audit(r, state.user.email, 'Ticket restored', currentTicket().id, 'Restored from trash'); save(); render(); toast('กู้คืน Ticket แล้ว'); } break;
      case 'submit-note': document.getElementById('note-form')?.requestSubmit(); break;
      case 'export': exportReport(); break;
      case 'faults': faultsModal(); break;
      case 'retry-ai': state.faults.ai = false; render(); toast('โหลดคำวิเคราะห์ fixture สำเร็จ'); break;
      case 'expire': logout('Session จำลองหมดอายุ กรุณาเข้าสู่ระบบใหม่'); authModal('login', 'Session หมดอายุ ประวัติรอบฝึกยังอยู่'); break;
      case 'no-access': closeModal(); if (state.user?.role === 'Instructor') modal('Access denied · test state', '<div class="notice error">คุณไม่มีสิทธิ์เข้าถึงรอบของบัญชีนี้ (สถานะจำลอง)</div>'); else navigate('admin'); break;
      case 'clear-faults': state.faults = { ai: false, quota: false }; closeModal(); render(); toast('ล้างสถานะทดสอบแล้ว'); break;
      case 'empty-run': if (!state.user) authModal(); else { startSelected(); if (!run().demo && run().elapsed === 0) { run().state = 'Paused'; save(); closeModal(); navigate('events'); } } break;
      case 'open-run': if (state.runs.some(x => x.id === el.dataset.id && x.owner === state.user?.email)) { state.selectedRun = el.dataset.id; navigate('overview'); } break;
      case 'toggle-account': if (state.user?.role === 'Instructor') { const ac = accounts().find(x => x.email === el.dataset.id); accountPatch(ac.email, { disabled: !ac.disabled }); render(); toast('ปรับสถานะบัญชีตัวอย่างแล้ว'); } break;
      case 'quota-account': if (state.user?.role === 'Instructor') { const ac = accounts().find(x => x.email === el.dataset.id); modal('Adjust demo quota', `<p>${esc(ac.email)}</p><form id="quota-form" data-email="${esc(ac.email)}"><div class="field"><label for="quota">จำนวนรอบสูงสุด (0–100)</label><input id="quota" name="quota" type="number" min="0" max="100" required value="${ac.quota ?? 10}"></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary">บันทึกโควตา</button></form>`); } break;
      case 'inspect-run': inspectRun(el.dataset.id); break;
      case 'instructor-ticket': if (state.user?.role === 'Instructor') { const targetRun = state.runs.find(x => x.id === el.dataset.id); const t = targetRun?.tickets.find(x => x.id === el.dataset.ticketId); if (!t || t.deleted) return toast('Ticket ถูกลบ ต้องให้เจ้าของกู้คืนก่อน'); modal('Instructor ticket review', `<p>${esc(t.id)} · ไม่แก้ข้อสรุปหรือเหตุผลของผู้เรียน</p><form id="instructor-ticket-form" data-run="${targetRun.id}" data-ticket="${t.id}"><div class="field"><label for="admin-severity">Severity</label><select id="admin-severity" name="severity">${['Low', 'Medium', 'High', 'Critical'].map(s => `<option ${s === t.severity ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="field"><label for="admin-status">Status</label><select id="admin-status" name="status">${M.statuses.map(s => `<option ${s === t.status ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="field"><label for="admin-reason">เหตุผลของ Instructor</label><textarea id="admin-reason" name="reason" required maxlength="2000"></textarea></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary">บันทึก</button></form>`); } break;
    }
  });
  document.addEventListener('change', event => {
    const el = event.target;
    if (el.dataset.scenario) { if (el.checked) state.selection.push(el.dataset.scenario); else state.selection = state.selection.filter(x => x !== el.dataset.scenario); render(); }
    if (el.id === 'table-filter') { state.filter = el.value; state.search = document.getElementById('table-search')?.value || ''; render(); }
    if (el.id === 'show-deleted') { state.deleted = el.checked; render(); }
    if (el.id === 'show-deleted-notes') { state.noteDeleted = el.checked; render(); }
    if (el.id === 'fault-ai') { state.faults.ai = el.checked; render(); }
    if (el.id === 'fault-quota') state.faults.quota = el.checked;
  });
  document.addEventListener('keydown', event => { if (event.key === 'Enter' && event.target.id === 'table-search') { event.preventDefault(); state.search = event.target.value; render(); } });
  document.addEventListener('submit', event => {
    event.preventDefault(); const form = event.target; const data = Object.fromEntries(new FormData(form));
    const error = message => { const el = form.querySelector('.form-error'); if (el) el.textContent = message; else toast(message); };
    try {
      if (form.id === 'auth-form') {
        const email = data.email.trim().toLowerCase();
        if (data.password !== 'demo1234') throw Error('เข้าสู่ระบบไม่สำเร็จ บัญชีหรือรหัสเดโมไม่ถูกต้อง หรือบัญชีถูกปิดใช้งาน');
        if (state.authMode === 'register') { if (!data.name?.trim() || data.name.length > 60) throw Error('กรอกชื่อ 1–60 ตัวอักษร'); if (!email.endsWith('@demo.test')) throw Error('ใช้บัญชีตัวอย่างลงท้าย @demo.test'); if (accounts().some(a => a.email === email)) throw Error('ไม่สามารถสร้างบัญชีนี้ได้ กรุณาใช้ชื่อใหม่'); state.accounts.push({ email, name: data.name.trim(), role: 'Analyst', quota: 10, disabled: false }); save(); }
        login(email); return;
      }
      if (form.id === 'quota-form') { if (state.user?.role !== 'Instructor') throw Error('ไม่มีสิทธิ์'); const n = Number(data.quota); if (!Number.isInteger(n) || n < 0 || n > 100) throw Error('โควตาต้องเป็นจำนวนเต็ม 0–100'); accountPatch(form.dataset.email, { quota: n }); closeModal(); render(); toast('ปรับโควตาแล้ว'); return; }
      if (form.id === 'instructor-comment') { if (state.user?.role !== 'Instructor' || !data.content.trim()) throw Error('กรอกความเห็นก่อนบันทึก'); const r = state.runs.find(r => r.id === form.dataset.run); r.comments ||= []; r.comments.push({ author: state.user.email, content: data.content.trim(), time: r.elapsed }); M.audit(r, state.user.email, 'Instructor comment', r.id, data.content.trim()); save(); inspectRun(r.id); toast('เพิ่มความเห็นแล้ว'); return; }
      if (form.id === 'instructor-ticket-form') {
        if (state.user?.role !== 'Instructor') throw Error('ไม่มีสิทธิ์'); const r = state.runs.find(r => r.id === form.dataset.run); const t = r.tickets.find(t => t.id === form.dataset.ticket); const learnerReason = t.reason;
        M.updateTicket(r, t.id, { title: t.title, severity: data.severity, status: data.status, disposition: t.disposition, reason: data.reason }, state.user.email); t.reason = learnerReason; save(); inspectRun(r.id); toast('ปรับสถานะโดย Instructor แล้ว'); return;
      }
      if (!requireEdit()) return;
      const r = run(); const t = currentTicket();
      if (form.id === 'assessment-form') { M.updateTicket(r, t.id, data, state.user.email); save(); render(); toast('บันทึกการประเมินแล้ว'); return; }
      if (form.id === 'create-ticket-form') {
        if (!data.title.trim() || data.title.length > 120 || !data.reason.trim() || data.reason.length > 2000) throw Error('กรอกชื่อและเหตุผลให้ครบตามความยาวที่กำหนด');
        if (!r.events.some(e => e.id === data.evidence)) throw Error('หลักฐานต้องอยู่ในรอบนี้');
        const ticket = { id: 'TKT-M' + (r.tickets.filter(t => !t.scenarioId).length + 1), scenarioId: null, title: data.title.trim(), severity: data.severity, status: 'Open', disposition: '', reason: data.reason.trim(), notes: [], deleted: false, created: r.elapsed, evidenceIds: [data.evidence] };
        r.tickets.push(ticket); M.audit(r, state.user.email, 'Manual ticket created', ticket.id, ticket.reason); state.ticketId = ticket.id; state.view = 'tickets';
      }
      if (form.id === 'note-form') { if (!data.content.trim() || data.content.length > 2000 || t.deleted) throw Error('ระบุข้อความ 1–2,000 ตัวอักษรใน Ticket ที่ยังไม่ถูกลบ'); if (data.evidence && !t.evidenceIds.includes(data.evidence)) throw Error('หลักฐานไม่อยู่ใน Ticket นี้'); const n = { id: 'N-' + Date.now(), content: data.content.trim(), evidence: data.evidence, author: state.user.email, time: r.elapsed, deleted: false, versions: [] }; t.notes.push(n); M.audit(r, state.user.email, 'Note created', t.id, n.id); }
      if (form.id === 'edit-note-form') { const n = t.notes.find(n => n.id === form.dataset.note); if (!n || n.deleted || n.author !== state.user.email || t.deleted) throw Error('ไม่สามารถแก้บันทึกนี้ได้'); if (!data.content.trim() || data.content.length > 2000) throw Error('ระบุข้อความ 1–2,000 ตัวอักษร'); n.versions.push({ content: n.content, time: r.elapsed }); n.content = data.content.trim(); M.audit(r, state.user.email, 'Note updated', t.id, `${n.id} · v${n.versions.length + 1}`); }
      if (form.id === 'delete-ticket-form' || form.id === 'delete-note-form') { if (!data.reason.trim()) throw Error('ระบุเหตุผลก่อนลบ'); if (form.id === 'delete-ticket-form') { t.deleted = true; M.audit(r, state.user.email, 'Ticket deleted', t.id, data.reason.trim()); } else { const n = t.notes.find(n => n.id === data.note); if (!n || n.author !== state.user.email || t.deleted) throw Error('ไม่มีสิทธิ์ลบบันทึกนี้'); n.deleted = true; M.audit(r, state.user.email, 'Note deleted', t.id, data.reason.trim()); } }
      save(); closeModal(); render(); toast('บันทึกเรียบร้อยแล้ว');
    } catch (e) { error(e.message); }
  });
  setInterval(() => {
    const r = run(); if (!editable() || r.state !== 'Running') return;
    const previous = r.events.length; M.tick(r);
    document.querySelectorAll('[data-clock]').forEach(el => { el.textContent = time(r.elapsed); });
    document.querySelectorAll('[data-progress]').forEach(el => { el.style.width = r.elapsed / r.duration * 100 + '%'; });
    if (r.elapsed % 5 === 0 || r.state === 'Review') save();
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
    if ((previous !== r.events.length || r.state === 'Review') && !state.ticketId && !document.querySelector('dialog') && !typing) render();
    if (r.state === 'Review') toast('ปล่อยเหตุการณ์ครบแล้ว สืบสวนต่อหรือจบรอบเพื่อดูเฉลยได้');
  }, 1000);
  window.addEventListener('beforeunload', save);
  render();
})();
