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
  const status = value => badge(value, { Open: 'blue', Investigating: 'purple', Resolved: 'green', Closed: 'gray', Running: 'green', Reviewing: 'yellow', Completing: 'yellow', Failed: 'red', Completed: 'purple', Paused: 'yellow' }[value]);
  const button = (label, action, ico, kind = '', attrs = '') => `<button type="button" class="btn ${kind}" data-action="${action}" ${attrs}>${ico ? icon(ico) : ''}${label}</button>`;
  const time = n => `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
  const eventTime = n => new Date(Date.parse(run().startedAt) + n * 1000).toLocaleTimeString('en-GB', { timeZone: 'Asia/Bangkok', hour12: false });
  const lessonData = {
    beginner: { example: 'ตัวอย่างฝึก: มีผู้ลองเข้าสู่ระบบ แต่เซิร์ฟเวอร์ปฏิเสธ', method: 'POST', path: '/auth/login', status: '401 Unauthorized', actor: 'finance.user · 198.51.100.20', context: 'ลอง 12 ครั้ง · ไม่พบ session สำเร็จ', steps: [
      { target: 'method', title: 'อ่าน Method ก่อน', instruction: 'กด POST ในตัวอย่าง', explanation: 'POST คือการส่งข้อมูลไปยังเซิร์ฟเวอร์ เช่นส่งข้อมูลเพื่อขอเข้าสู่ระบบ Method บอกว่า request ต้องการทำอะไร' },
      { target: 'path', title: 'ดู Path ว่าขออะไร', instruction: 'กด /auth/login', explanation: '/auth/login คือปลายทางที่ถูกเรียก เมื่อรวมกับ POST จึงรู้ว่าเป็นความพยายามเข้าสู่ระบบ ไม่ใช่การอ่านไฟล์' },
      { target: 'status', title: 'ดูผลตอบกลับ', instruction: 'กด 401 Unauthorized', explanation: '401 แปลว่าการยืนยันตัวตนของ request นี้ไม่สำเร็จ; 403 คือถูกปฏิเสธสิทธิ์; 200 หมายถึง request สำเร็จ แต่ต้องดูว่าเป็น request อะไรด้วย' },
      { target: 'actor', title: 'ดูว่าใครและจากไหน', instruction: 'กดบัญชีและ IP', explanation: 'บัญชีคือเป้าหมายของการเข้าสู่ระบบ ส่วน Source IP คือที่มาของ request ใช้เชื่อมเหตุการณ์ที่เกี่ยวข้องกัน ไม่ใช่หลักฐานว่าผู้ใช้คนนั้นเป็นผู้โจมตี' },
      { target: 'context', title: 'แยกความพยายามจากผลกระทบ', instruction: 'กดข้อมูลเหตุการณ์ต่อเนื่อง', explanation: 'ลอง 12 ครั้งจึงควรตรวจสอบ แต่ถ้าไม่พบ session สำเร็จ ยังสรุปว่าบัญชีถูกยึดไม่ได้ ต้องแยก “พยายาม” กับ “สำเร็จ”' }
    ] },
    intermediate: { example: 'ตัวอย่างฝึก: request สำเร็จ แต่ต้องตรวจบริบทก่อนสรุป', method: 'GET', path: '/api/finance/export', status: '200 OK', actor: 'finance.user · 198.51.100.20', context: 'session ใหม่ · อ่าน 240 รายการ · เจ้าของบัญชีปฏิเสธ', steps: [
      { target: 'method', title: 'อ่าน Method', instruction: 'กด GET', explanation: 'GET ใช้ขออ่านข้อมูล แต่ไม่บอกเองว่าเป็นการอ่านที่ได้รับอนุญาตหรือไม่' },
      { target: 'path', title: 'ดูทรัพยากรที่ถูกขอ', instruction: 'กด /api/finance/export', explanation: 'Path นี้ชี้ไปยังข้อมูลการเงินและการส่งออก จึงมีผลกระทบต่างจากการขอหน้าเว็บทั่วไป' },
      { target: 'status', title: 'ยืนยันผลลัพธ์', instruction: 'กด 200 OK', explanation: '200 หมายถึง request นี้สำเร็จ ต่างจาก 401/403 แต่ต้องเชื่อมกับ session และผู้ใช้ก่อนสรุปว่าเป็นภัย' },
      { target: 'actor', title: 'เชื่อมตัวตนและแหล่งที่มา', instruction: 'กดบัญชีและ IP', explanation: 'เทียบบัญชี IP และเวลาในหลาย event; หากเป็นการสแกนที่ได้รับอนุญาต ต้องตรวจ change ticket ให้ตรงแหล่งที่มา เวลา และเป้าหมาย' },
      { target: 'context', title: 'สรุปด้วยหลายหลักฐาน', instruction: 'กดข้อมูลเหตุการณ์ต่อเนื่อง', explanation: 'session ใหม่ + การอ่านข้อมูลสำเร็จ + เจ้าของบัญชีปฏิเสธ เป็นหลักฐานหนักกว่าการล็อกอินผิดเพียงอย่างเดียว' }
    ] },
    advanced: { example: 'ตัวอย่างฝึก: พฤติกรรมผิดจากค่าปกติ แม้ไม่ตรงกฎเดิม', method: 'GET', path: '/files/reports', status: '200 OK', actor: 'ops.user · 192.0.2.45', context: 'อ่านไฟล์ 8 เท่าของ baseline · นอกเวลางาน · เจ้าของ session ปฏิเสธ', steps: [
      { target: 'method', title: 'อ่าน Method', instruction: 'กด GET', explanation: 'GET เป็นคำขออ่านข้อมูล ในเคสนี้ต้องดูปริมาณและเวลา ไม่ใช่ดู Method อย่างเดียว' },
      { target: 'path', title: 'ดูทรัพยากรที่ถูกอ่าน', instruction: 'กด /files/reports', explanation: 'Path บอกว่ามีการขอไฟล์รายงาน ต้องตรวจว่าเป็นไฟล์สำคัญและมีการอ่านสำเร็จหรือไม่' },
      { target: 'status', title: 'ตรวจผลตอบกลับ', instruction: 'กด 200 OK', explanation: 'คำขออ่านสำเร็จ แต่อย่าเพิ่งสรุปว่าเป็นภัยชนิดใหม่เพียงเพราะไม่มี rule เดิมตรวจพบ' },
      { target: 'actor', title: 'เทียบผู้ใช้และต้นทาง', instruction: 'กดบัญชีและ IP', explanation: 'ดูว่า session ของใคร มาจากไหน และตรงกับพฤติกรรมปกติหรือไม่ จากนั้นหาหลักฐานอื่นยืนยัน' },
      { target: 'context', title: 'แยก anomaly จากภัยจริง', instruction: 'กดข้อมูลเหตุการณ์ต่อเนื่อง', explanation: '8 เท่าของ baseline คือสัญญาณผิดปกติ ส่วนการปฏิเสธของเจ้าของ session เป็นอีกหลักฐานที่ทำให้ต้องเร่งสืบสวน' }
    ] }
  };
  let persisted = {};
  try { persisted = JSON.parse(localStorage.getItem(STORE) || '{}'); } catch { /* Start clean if local storage is unavailable or invalid. */ }
  const validRuns = Array.isArray(persisted.runs) ? persisted.runs.filter(r => r && Array.isArray(r.events) && Array.isArray(r.tickets) && Array.isArray(r.alerts) && Array.isArray(r.audit) && Array.isArray(r.scenarioIds) && r.scenarioIds.every(id => M.getScenario(id))) : [];
  const state = { view: 'learning', user: null, runs: validRuns, accounts: Array.isArray(persisted.accounts) ? persisted.accounts : [], tours: persisted.tours || {}, learned: persisted.learned || {}, lessonLevel: 'beginner', lessonStep: 0, lessonTouched: false, selectedRun: null, demo: M.demoRun(), selection: ['S01'], ticketId: null, search: '', filter: 'All', deleted: false, mobile: false, faults: { ai: false, quota: false }, authMode: 'login', noteDeleted: false, eventFilters: {}, filterError: '', page: 1 };
  // Local wall-clock catch-up simulates the planned server runner; no real worker is connected.
  state.runs.forEach(r => { r.version ||= 1; if (r.state === 'Review') r.state = 'Reviewing'; r.tickets.forEach(t => { t.version ||= 1; t.assessments ||= []; t.notes.forEach(n => n.version ||= n.versions.length + 1); }); M.syncClock(r); if (r.state === 'Completed' && !r.evaluationSnapshot) r.evaluationSnapshot = M.evaluate(r); });
  function save() {
    try { localStorage.setItem(STORE, JSON.stringify({ runs: state.runs, accounts: state.accounts, tours: state.tours, learned: state.learned })); }
    catch { toast('บันทึกใน browser ไม่สำเร็จ กรุณาส่งออกรายงานก่อนปิดหน้า'); }
  }
  const run = () => state.selectedRun ? state.runs.find(r => r.id === state.selectedRun) || state.demo : state.demo;
  const editable = () => !!state.user && !run().demo && run().owner === state.user.email && !state.user.disabled && M.isMutable(run());
  const currentTicket = () => run().tickets.find(t => t.id === state.ticketId);
  const pageNames = { learning: 'เส้นทางเรียนรู้', lesson: 'บทเรียน', overview: 'Overview', simulation: 'Simulation lab', events: 'Event explorer', alerts: 'Alert queue', tickets: 'Tickets', evaluation: 'Evaluation', admin: 'Instructor', help: 'Getting started' };
  let toastTimer;
  function toast(message) { const el = document.getElementById('toast'); el.textContent = message; el.classList.add('visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 3600); }
  function navigate(view) { state.view = view; state.ticketId = null; state.search = ''; state.filter = 'All'; state.eventFilters = {}; state.filterError = ''; state.page = 1; state.deleted = false; state.mobile = false; render(); window.scrollTo({ top: 0, behavior: 'instant' }); }
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
    return `<div class="shell"><div class="mobile-scrim ${state.mobile ? 'active' : ''}" data-action="menu"></div><aside class="sidebar ${state.mobile ? 'open' : ''}"><div class="brand"><div class="brand-mark">${icon('shield')}</div><span>sentinel<span class="brand-dot">.</span></span></div><div class="workspace"><div class="workspace-symbol">${icon('globe')}</div><div><strong>SOC Learning Lab</strong><span>เรียนจากเคสจำลอง</span></div></div><div class="nav-label">เรียนรู้</div><nav aria-label="เมนูหลัก">${nav('learning', 'book', 'เส้นทางเรียนรู้')}${nav('overview', 'grid', 'Overview')}${nav('simulation', 'play', 'Simulation lab')}${nav('events', 'activity', 'Event explorer')}${nav('alerts', 'bell', 'Alert queue', r.alerts.length)}${nav('tickets', 'ticket', 'Tickets', r.tickets.filter(t => !t.deleted && t.status !== 'Closed').length)}${nav('evaluation', 'chart', 'Evaluation')}<div class="nav-divider"></div><div class="nav-label">MANAGE</div>${nav('admin', 'users', 'Instructor')}${nav('help', 'book', 'Getting started')}</nav><div class="sidebar-bottom"><div class="lab-card"><strong>${icon('spark')} เริ่มเรียนทีละขั้น</strong><p>ดูหลักฐาน → ตอบพร้อมเหตุผล<br>ผ่านแล้วจึงไปบทถัดไป</p><button data-nav="learning">ดูเส้นทางเรียนรู้ &nbsp; →</button></div><div class="profile"><div class="avatar">${state.user ? esc(state.user.name.slice(0, 2).toUpperCase()) : 'G'}</div><div><div class="profile-name">${esc(state.user?.name || 'ผู้เยี่ยมชม')}</div><div class="profile-role">${esc(state.user?.role || 'ดูตัวอย่างได้')}</div></div><button data-action="${state.user ? 'logout' : 'login'}" title="${state.user ? 'ออกจากระบบ' : 'เข้าสู่ระบบ'}">${icon('logout')}</button></div></div></aside><main class="main"><header class="topbar"><div class="breadcrumb"><button class="icon-button mobile-menu" data-action="menu" aria-label="เปิดเมนู">${icon('menu')}</button><span>Workspace</span><span>/</span><strong>${pageNames[state.view]}</strong></div><div class="top-actions"><span class="system-status"><i class="dot"></i> Local simulation</span><span class="top-divider"></span>${badge('PROTOTYPE', 'purple')}<button class="icon-button" data-action="faults" aria-label="เปิดสถานะทดสอบ" title="Prototype test states">${icon('settings')}</button>${button(state.user ? esc(state.user.name) : 'เข้าสู่ระบบ', state.user ? 'account' : 'login', state.user ? 'users' : 'logout', 'small')}</div></header><div class="content">${content}<footer class="page-footer"><span>Sentinel SOC Lab <span style="color:#9b84ce">/</span> Learning path</span><span>ข้อมูลจำลอง · AI/RAG coach แบบ rubric · ไม่มีการเชื่อมต่อระบบจริง</span></footer></div></main></div>`;
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
  const lessonDone = level => !!state.user && (state.learned[`${state.user.email}:${level.id}`] || M.learningProgress(state.runs, state.user.email).passed.some(id => level.scenarioIds.includes(id)));
  const examining = () => !!state.user && !run().demo && run().owner === state.user.email && run().mode === 'exam';
  function lesson() {
    const level = M.levels.find(item => item.id === state.lessonLevel) || M.levels[0];
    const data = lessonData[level.id];
    const step = data.steps[state.lessonStep];
    const field = (target, label, value) => `<button class="request-field ${step.target === target ? 'request-target' : ''} ${state.lessonTouched && step.target === target ? 'request-found' : ''}" data-action="lesson-field" data-field="${target}"><span>${label}</span><strong>${esc(value)}</strong></button>`;
    const [account, sourceIp] = data.actor.split(' · ');
    const rawRequest = `${data.method} ${data.path} HTTP/1.1\nHost: democorp.test${data.method === 'POST' ? '\nContent-Type: application/json\n\n{"username":"' + account + '","password":"[REDACTED]"}' : ''}`;
    return heading(`บทเรียน: ${level.title}`, 'ช่วงเรียนมีคำอธิบายและตัวอย่างฝึก · ช่วงทดสอบจะซ่อนคำใบ้', button('กลับเส้นทางเรียนรู้', 'go-learning', 'back')) +
      `<div class="lesson-layout"><section class="lesson-instruction"><div class="lesson-progress">ขั้น ${state.lessonStep + 1} / ${data.steps.length}<div class="learning-meter"><span style="width:${(state.lessonStep + 1) / data.steps.length * 100}%"></span></div></div><h2>${esc(step.title)}</h2><p>${esc(step.instruction)}</p>${state.lessonTouched ? `<div class="lesson-explanation"><strong>จุดที่ต้องจำ</strong><p>${esc(step.explanation)}</p></div>` : '<div class="lesson-prompt">กดข้อมูลที่กำลังเรียนในตัวอย่างด้านขวา แล้วอ่านคำอธิบาย</div>'}<div class="lesson-controls">${button('ก่อนหน้า', 'lesson-prev', 'back', '', state.lessonStep === 0 ? 'disabled' : '')}${button(state.lessonStep === data.steps.length - 1 ? 'จบบทเรียนและเปิดทดสอบ' : 'ขั้นถัดไป', 'lesson-next', 'arrow', 'primary', state.lessonTouched ? '' : 'disabled')}</div></section><section class="lesson-request"><div class="lesson-request-head"><strong>Request / Response</strong><span>ตัวอย่างฝึก · ไม่ใช่โจทย์ทดสอบ</span></div><p>${esc(data.example)}</p><div class="request-fields">${field('method', 'METHOD', data.method)}${field('path', 'PATH', data.path)}${field('status', 'RESPONSE', data.status)}${field('actor', 'ACCOUNT / SOURCE IP', data.actor)}${field('context', 'RELATED EVENTS', data.context)}</div><div class="lesson-raw"><strong>ตัวอย่างข้อความใน log</strong><pre>${esc(rawRequest)}</pre><pre>${esc(`HTTP/1.1 ${data.status}\nContent-Type: application/json\n\n{"simulated":true}`)}</pre><p>Source IP: ${esc(sourceIp)} · บัญชี: ${esc(account)} — สองค่านี้มักอยู่ใน metadata ของ log ไม่ใช่บรรทัด request เสมอ</p></div><div class="lesson-glossary"><strong>อ่าน request อย่างไร</strong><p>เริ่มจาก Method + Path ว่าขอทำอะไร แล้วดู Response ว่าสำเร็จหรือถูกปฏิเสธ สุดท้ายดูบัญชี IP เวลา และเหตุการณ์อื่นก่อนสรุปผลกระทบ</p></div></section></div>`;
  }
  function learning() {
    const progress = M.learningProgress(state.runs, state.user?.email);
    const current = M.levels[progress.unlockedIndex];
    const intro = state.user ? `กำลังเรียน: ${current.title} · ผ่าน ${progress.passed.length}/${M.scenarios.length} เคส` : 'ดูเส้นทางได้ทันที · เข้าสู่ระบบเพื่อบันทึกความก้าวหน้า';
    return `<section class="learning-hero"><div class="learning-hero-copy"><p class="learning-kicker">เส้นทางเรียนรู้ SOC</p><h1>เรียนวิธีดู request<br>ก่อนลงมือทดสอบ</h1><p>เริ่มจากตัวอย่างที่มีคำอธิบายทุกจุด แล้วจึงเข้าสู่เคสทดสอบเลื่อนขั้นที่ต้องวิเคราะห์ด้วยตัวเอง</p><div class="learning-hero-actions">${button(state.user ? lessonDone(current) ? 'ไปทดสอบระดับที่เปิดอยู่' : 'เริ่มบทเรียนที่เปิดอยู่' : 'เข้าสู่ระบบเพื่อเริ่มเรียน', state.user ? 'start-current-lesson' : 'login', 'play', 'primary')}${button('ดูวิธีใช้หน้าต่าง ๆ', 'tour-current', 'book', 'ghost')}</div><span class="learning-progress-label">${esc(intro)}</span></div><div class="learning-orbit" aria-hidden="true"><span>01<br>เรียน</span><span>02<br>ลอง</span><span>03<br>สอบ</span></div></section>` +
      `<div class="learning-section-heading"><h2>เรียนทีละระดับ</h2><p>ผ่านทุกเคสในระดับปัจจุบันก่อน จึงปลดล็อกระดับถัดไป</p></div><div class="learning-levels">${M.levels.map((level, index) => {
        const locked = index > progress.unlockedIndex;
        const count = level.scenarioIds.filter(id => progress.passed.includes(id)).length;
        return `<section class="learning-level ${locked ? 'locked' : index === progress.unlockedIndex ? 'current' : 'complete'}"><div class="learning-level-head"><span>LEVEL ${String(index + 1).padStart(2, '0')}</span>${badge(locked ? 'ยังไม่ปลดล็อก' : count === level.scenarioIds.length ? 'ผ่านแล้ว' : lessonDone(level) ? 'พร้อมทดสอบ' : 'เริ่มบทเรียน', locked ? 'gray' : count === level.scenarioIds.length ? 'green' : 'purple')}</div><h3>${level.title}</h3><p>${level.description}</p><div class="learning-meter"><span style="width:${count / level.scenarioIds.length * 100}%"></span></div><small>${count}/${level.scenarioIds.length} เคสทดสอบผ่าน</small><div class="learning-level-action">${button(lessonDone(level) ? 'ทบทวนบทเรียน' : 'เรียนวิธีอ่าน request', 'open-lesson', 'book', 'small', `data-level="${level.id}" ${locked || !state.user ? 'disabled' : ''}`)}</div><div class="learning-lessons">${level.scenarioIds.map(id => {
          const scenario = M.getScenario(id);
          const passed = progress.passed.includes(id);
          return `<div class="learning-lesson"><div><strong>เคสทดสอบ ${level.scenarioIds.indexOf(id) + 1} · ${esc(scenario.category)}</strong><span>${passed ? 'ผ่านแล้ว · ทดสอบซ้ำได้' : locked ? 'ผ่านระดับก่อนหน้าเพื่อเปิด' : lessonDone(level) ? 'ทดสอบโดยไม่มีคำใบ้' : 'เรียนบทนี้ก่อนสอบ'}</span></div>${button(passed ? 'สอบซ้ำ' : locked ? 'ล็อก' : lessonDone(level) ? 'เริ่มทดสอบ' : 'ยังไม่เปิด', 'launch-lesson', '', 'small', `data-id="${id}" ${locked || !lessonDone(level) ? 'disabled' : ''}`)}</div>`;
        }).join('')}</div></section>`;
      }).join('')}</div><div class="learning-method"><strong>บทเรียนกับการทดสอบต่างกันอย่างไร</strong><p>บทเรียนมีตัวอย่างและเฉลยทีละจุด ส่วนเคสทดสอบซ่อนคำใบ้ระหว่างทำ คุณต้องตรวจ request/response เลือกหลักฐาน และส่งเหตุผลเอง หลังส่งจึงเห็นผลตรวจ 4 ด้าน ระบบตรวจด้วย rubric จำลอง ไม่ใช่ AI หรือ RAG ที่เรียกโมเดลจริง</p></div>`;
  }
  function overview() {
    const r = run(); const open = r.tickets.filter(t => !t.deleted && t.status !== 'Closed').length; const high = r.tickets.filter(t => !t.deleted && ['High', 'Critical'].includes(t.severity)).length;
    const latest = [...r.tickets].filter(t => !t.deleted).reverse().slice(0, 5);
    return heading('Security overview', 'ทุกสัญญาณมีเรื่องราว เริ่มสืบสวนจากหลักฐานที่สำคัญ', button('ส่งออกรายงาน', 'export', 'download') + button('ไปเส้นทางเรียนรู้', 'go-learning', 'book', 'primary')) + demoBanner() +
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
    const progress = M.learningProgress(state.runs, state.user?.email);
    return heading('เคสทดสอบเลื่อนขั้น', 'อ่าน request/response และส่งข้อสรุปเอง · ไม่มีคำใบ้ระหว่างทดสอบ', button('ดูเส้นทางเรียนรู้', 'go-learning', 'book')) + controlStrip() +
      `<div class="learning-method"><strong>วิธีทำข้อสอบ</strong><p>เลือกเคสที่เปิดแล้ว → เริ่มรอบ → รอหลักฐานทยอยเข้ามา → เปิด Event explorer และ Ticket เพื่อตรวจ request/response → เลือกหลักฐาน ตั้ง severity จัดประเภท และเขียนเหตุผล ผลตรวจจะแสดงหลังส่งคำตอบ</p></div><div class="scenario-grid">${M.scenarios.map((s, i) => {
        const level = M.levelForScenario(s.id);
        const locked = !state.user || M.levels.indexOf(level) > progress.unlockedIndex || !lessonDone(level);
        return `<article class="scenario-card ${state.selection.includes(s.id) ? 'selected' : ''} ${locked ? 'lesson-locked' : ''}"><div class="scenario-top"><div class="step-icon">${icon(['shield', 'users', 'globe', 'activity', 'spark'][i])}</div>${badge(level.title, locked ? 'gray' : 'purple')}</div><div><h3>เคสทดสอบ ${level.scenarioIds.indexOf(s.id) + 1}</h3><p>${s.category} · ${s.asset}</p></div><p>รายละเอียดและผลกระทบต้องสืบสวนจากหลักฐานในรอบทดสอบ</p><div class="scenario-meta">${badge(s.category, 'purple')}${progress.passed.includes(s.id) ? badge('ผ่านแล้ว', 'green') : ''}</div><label><input type="radio" name="selected-scenario" data-scenario="${s.id}" ${state.selection.includes(s.id) ? 'checked' : ''} ${locked ? 'disabled' : ''}> ${locked ? 'เรียนบทนี้และผ่านระดับก่อนหน้าเพื่อเปิด' : 'เลือกเคสนี้'}</label></article>`;
      }).join('')}</div><div class="callout">ระบบนี้สร้าง request และผลกระทบจำลอง ไม่มีการโจมตีเป้าหมายจริง คำแนะนำ AI/RAG ในต้นแบบเป็นคู่มือและ rubric ที่เตรียมไว้ ไม่ใช่โมเดลจริง</div>` +
      (own.length ? panel('Your previous runs', 'ประวัติบน browser นี้ · เลือกกลับไปทำต่อได้', `<div class="table-wrap"><table><thead><tr><th>RUN</th><th>SCENARIOS</th><th>STATE</th><th></th></tr></thead><tbody>${own.slice().reverse().map(r => `<tr><td class="mono">${r.id}</td><td>${r.scenarioIds.length} scenarios</td><td>${status(r.state)}</td><td>${button('เปิดรอบ', 'open-run', 'arrow', 'small', `data-id="${r.id}"`)}</td></tr>`).join('')}</tbody></table></div>`) : '');
  }
  function filterTools(kind, options) {
    return `<div class="section-tools"><label class="search">${icon('search')}<input id="table-search" aria-label="ค้นหา ${kind}" placeholder="Search ${kind}..." value="${esc(state.search)}"></label><select id="table-filter" aria-label="กรอง ${kind}">${options.map(o => `<option ${state.filter === o ? 'selected' : ''}>${o}</option>`).join('')}</select>${button('ค้นหา', 'search', 'search', 'small')}</div>`;
  }
  function eventFilterForm() { return `<form id="event-filter-form" class="panel panel-body" style="padding-top:18px;margin-bottom:18px"><div class="form-row">${[['from','จากเวลา UTC (รวม)'],['to','ถึงเวลา UTC (ไม่รวม)'],['asset','Asset ตรงตัว'],['user','บัญชีผู้ใช้'],['ip','Source IP ตรงตัว']].map(([key,label]) => `<div class="field"><label for="event-${key}">${label}</label><input id="event-${key}" name="${key}" value="${esc(state.eventFilters[key] || '')}" placeholder="${['from','to'].includes(key) ? '2026-10-12T10:00:00Z' : ''}"></div>`).join('')}</div><div class="form-error" role="alert">${esc(state.filterError)}</div><button type="submit" class="btn">ใช้ตัวกรอง</button> ${button('ล้างตัวกรอง','clear-event-filters','refresh','small')}</form>`; }
  function events() {
    const r = run(); const q = state.search.toLowerCase(); let matches = []; state.filterError = ''; try { matches = M.filterEvents(r, { ...state.eventFilters, q, source: state.filter }).reverse(); } catch (e) { state.filterError = e.message; } const pages = Math.max(1, Math.ceil(matches.length / 10)); state.page = Math.min(state.page, pages); const rows = matches.slice((state.page - 1) * 10, state.page * 10);
    return heading('Event explorer', 'ค้นหาหลักฐานจาก request, response และ log ที่ปล่อยแล้ว', button('ส่งออก JSON', 'export', 'download')) + demoBanner() + (examining() ? '<div class="exam-banner">โหมดทดสอบ · ไม่มีคำใบ้ระหว่างทำ เปิด event เพื่ออ่านหลักฐานต้นทาง</div>' : `<div class="learning-method"><strong>ต้องดูตรงไหน?</strong><p>กดชื่อ event เพื่อเปิด request และ response ดูสถานะ HTTP, เวลา, บัญชี และอุปกรณ์ หากเห็น 401 หรือ 403 แปลว่าคำขอนั้นถูกปฏิเสธ แต่ยังต้องดูเหตุการณ์อื่นในเคสเดียวกันก่อนสรุปผล</p></div>`) + eventFilterForm() + panel('Event stream', `${matches.length} events · หน้า ${state.page}/${pages} · UTC`, rows.length ? `<div class="table-wrap"><table><thead><tr><th>TIME / EVENT</th><th>MESSAGE</th><th>SOURCE</th><th>ASSET / USER</th><th>RESPONSE</th><th></th></tr></thead><tbody>${rows.map(e => `<tr><td class="mono">${M.eventDate(r, e)}<div class="table-sub">${e.id}</div></td><td><button class="text-link table-title" data-event="${e.id}">${esc(e.message)}</button><div class="table-sub mono">${esc(e.ip)} · ${esc(e.request)}</div></td><td>${badge(e.source)}</td><td>${esc(e.asset)}<div class="table-sub">${esc(e.user)}</div></td><td>${badge(e.response, e.response >= 400 ? 'yellow' : 'green')}</td><td><button class="icon-button" data-event="${e.id}" aria-label="เปิดหลักฐาน ${e.id}">${icon('chevron')}</button></td></tr>`).join('')}</tbody></table></div>` : empty('ไม่พบเหตุการณ์', q || state.filter !== 'All' ? 'ลองเปลี่ยนคำค้นหาหรือตัวกรอง' : 'รอ event แรก หรือเริ่มรอบจาก Simulation lab'), filterTools('events', ['All', 'Auth gateway', 'Web gateway', 'File audit'])) + `<div class="panel-footer"><span>แสดง ${rows.length} / ${matches.length}</span><div>${button('ก่อนหน้า', 'prev-events', '', 'small', state.page <= 1 ? 'disabled' : '')} ${button('ถัดไป', 'next-events', '', 'small', state.page >= pages ? 'disabled' : '')}</div></div>`;
  }
  function alerts() {
    const q = state.search.toLowerCase(); const rows = run().alerts.filter(a => `${a.id} ${a.title} ${a.detector}`.toLowerCase().includes(q) && (state.filter === 'All' || a.detector === state.filter));
    return heading('Alert queue', 'สัญญาณจากกฎและความผิดปกติ พร้อมเชื่อมต่อไปยังเคสสืบสวน') + demoBanner() + (examining() ? '<div class="exam-banner">โหมดทดสอบ · ใช้ Alert เป็นทางไปดูหลักฐาน ไม่ใช่คำยืนยันผลกระทบ</div>' : `<div class="learning-method"><strong>ทำไมต้องดู Alert?</strong><p>Alert บอกว่าระบบสะดุดกับพฤติกรรมใด กดรหัสหลักฐานเพื่อดูต้นทาง แล้วกด Ticket เพื่อสืบสวนต่อ คำว่า Rule คือกฎที่รู้จัก; Anomaly คือผิดจากค่าปกติ ทั้งคู่ยังไม่ยืนยันว่ามีภัยจริง</p></div>`) + panel('Correlated alerts', `${rows.length} alerts · สัญญาณเตือนไม่เท่ากับยืนยันผลกระทบ`, rows.length ? `<div class="table-wrap"><table><thead><tr><th>ALERT</th><th>DETECTOR</th><th>INITIAL SEVERITY</th><th>EVIDENCE</th><th>LINKED TICKET</th></tr></thead><tbody>${rows.map(a => { const t = run().tickets.find(t => t.scenarioId === a.scenarioId); return `<tr><td class="table-title">${esc(a.title)}<div class="table-sub mono">${a.id} · ${eventTime(a.time)}</div></td><td>${badge(a.detector, a.detector === 'Rule' ? 'blue' : 'purple')}</td><td>${severity(a.severity)}</td><td>${run().events.filter(e => e.scenarioId === a.scenarioId).map(e => `<button class="link-chip" data-event="${e.id}">${e.id}</button>`).join('')}</td><td>${t ? `<button class="text-link" data-ticket="${t.id}">${t.id}${t.deleted ? ' · Deleted' : ''} →</button>` : '—'}</td></tr>`; }).join('')}</tbody></table></div>` : empty('คิว Alert ว่าง', 'ยังไม่มีผลตรวจจับที่ตรงกับตัวกรองนี้'), filterTools('alerts', ['All', 'Rule', 'Anomaly']));
  }
  function tickets() {
    if (state.ticketId && currentTicket()) return ticketDetail();
    const q = state.search.toLowerCase(); const rows = run().tickets.filter(t => !!t.deleted === state.deleted && `${t.id} ${t.title} ${t.reason}`.toLowerCase().includes(q) && (state.filter === 'All' || t.status === state.filter));
    return heading('Investigation tickets', 'รวบรวมหลักฐาน บันทึกข้อสรุป และติดตามทุกการตัดสินใจ', button('สร้าง Ticket', 'create-ticket', 'plus', 'primary')) + demoBanner() + panel('Ticket workspace', 'รายการที่ลบยังคงอยู่ใน audit และผลประเมิน', rows.length ? ticketTable(rows) : empty(state.deleted ? 'ไม่มี Ticket ที่ถูกลบ' : 'ไม่พบ Ticket', 'ลองเปลี่ยนตัวกรอง หรือสร้างเคสจากหลักฐานที่มี'), filterTools('tickets', ['All', ...M.statuses])) + `<div style="margin-top:15px"><label class="toggle"><input type="checkbox" id="show-deleted" ${state.deleted ? 'checked' : ''}> แสดงเฉพาะ Ticket ที่ลบแล้ว</label></div>`;
  }
  function ticketDetail() {
    const r = run(); const t = currentTicket(); const a = M.analysis(r, t); const canEdit = editable() && !t.deleted;
    const aiBody = examining() ? '<div class="panel-body"><div class="exam-banner">คำวิเคราะห์และคำใบ้ถูกซ่อนระหว่างทดสอบ อ่านหลักฐานใน timeline แล้วตอบด้วยตัวเอง</div></div>' : state.faults.ai ? `<div class="panel-body"><div class="notice error">AI analysis unavailable · จำลองบริการไม่พร้อมใช้งาน<br>กฎยังเปิด Ticket ได้ และคุณตรวจสอบหลักฐานต่อได้</div>${button('ลองวิเคราะห์อีกครั้ง', 'retry-ai', 'refresh', 'small', canEdit ? '' : 'disabled')}</div>` : `<div class="panel-body"><p class="ai-summary">${esc(a.summary)}</p><div class="fact-grid"><div><label>OBSERVED IMPACT</label><p>${esc(a.impact)}</p></div><div><label>POTENTIAL IMPACT</label><p>อาจมีการเข้าถึงข้อมูลนอกขอบเขต ต้องมีหลักฐานเพิ่มก่อนยืนยัน</p></div><div><label>CONFIDENCE</label><p>${esc(a.confidence)}</p></div><div><label>UNKNOWNS / NEXT CHECKS</label><p>${esc(a.unknown)}</p></div></div><div style="margin-top:17px">${a.evidence.map(e => `<button class="link-chip" data-event="${e.id}">${e.id}</button>`).join('')}</div><p class="status-note">Mock model · fixture-v1 / prompt-v1 · ประเมินจาก ${a.evidence.length} events ที่ปล่อยแล้ว</p></div>`;
    return (['Completing','Completed','Failed'].includes(r.state) ? '<div class="notice">รอบนี้อ่านอย่างเดียว · คำตอบถูกล็อกไว้สำหรับผลประเมินแล้ว เริ่มรอบใหม่เพื่อฝึกต่อ</div>' : '') + heading(esc(t.title), `${t.id} / ${r.id}`, button('กลับรายการ', 'go-tickets', 'back') + button('อัปเดตหลักฐาน', 'refresh-evidence', 'refresh') + button('ประวัติคำตอบ', 'assessment-history', 'clock') + (editable() ? button(t.deleted ? 'กู้คืน Ticket' : 'ลบ Ticket', t.deleted ? 'restore-ticket' : 'delete-ticket', t.deleted ? 'refresh' : 'trash', t.deleted ? '' : 'danger') : '')) + (r.demo ? demoBanner() : '') + (t.deleted ? '<div class="notice error">Ticket นี้ถูกลบแบบ soft delete แล้ว ต้องกู้คืนก่อนแก้ไข ข้อมูลยังคงอยู่ในผลประเมิน</div>' : '') +
      `<div class="detail-meta" style="margin-bottom:22px">${severity(t.severity)}${status(t.status)}${badge(t.disposition || 'Awaiting human review', 'purple')}${badge(M.getScenario(t.scenarioId)?.asset || 'Manual case')}</div><div class="detail-grid"><div class="stack">${panel('AI investigation brief', 'คำวิเคราะห์ตัวอย่าง · ตรวจสอบกับหลักฐานก่อนตัดสินใจ', aiBody, badge('MOCK AI', 'purple'), 'ai-panel')}${panel('Evidence timeline', `${a.evidence.length} linked events · อ่านข้อมูลต้นทางได้ทุกรายการ`, `<div class="panel-body"><div class="timeline">${a.evidence.map(e => `<div class="timeline-item"><strong>${esc(e.message)}</strong><p class="mono">${eventTime(e.time)} · ${esc(e.asset)} · HTTP ${e.response}</p><button class="text-link" data-event="${e.id}">${e.id} · View request & response →</button></div>`).join('') || '<p class="muted small">ยังไม่มีหลักฐาน</p>'}</div></div>`)}${panel('Investigation notes', 'บันทึกของคนแยกจากผล AI · เก็บประวัติการแก้ไข', `<div class="panel-body">${canEdit ? `<form id="note-form"><div class="field"><label for="note-content">เพิ่มบันทึกการสืบสวน</label><textarea id="note-content" name="content" required maxlength="2000" placeholder="พบอะไร หลักฐานใดสนับสนุน และต้องตรวจอะไรต่อ..."></textarea></div><div class="field"><label for="note-evidence">หลักฐานอ้างอิง (ไม่บังคับ)</label><select id="note-evidence" name="evidence"><option value="">ไม่ระบุ</option>${a.evidence.map(e => `<option value="${e.id}">${e.id} · ${esc(e.message)}</option>`).join('')}</select></div><div class="form-error" role="alert"></div>${button('เพิ่มบันทึก', 'submit-note', 'plus', 'small primary')}</form>` : '<p class="small muted">อ่านบันทึกได้ เริ่มรอบของคุณเพื่อเพิ่มหรือแก้ไข</p>'}<div style="margin-top:17px"><label class="toggle"><input type="checkbox" id="show-deleted-notes" ${state.noteDeleted ? 'checked' : ''}> แสดงบันทึกที่ลบแล้วด้วย</label></div>${t.notes.filter(n => !n.deleted || state.noteDeleted).map(n => `<article class="note"><div class="note-meta"><span>${esc(n.author)} · ${time(n.time)} · v${n.versions.length + 1}</span>${n.deleted ? badge('Deleted', 'red') : ''}</div><p>${esc(n.content)}</p>${n.evidence ? `<button class="link-chip" data-event="${esc(n.evidence)}">${esc(n.evidence)}</button>` : ''}<div class="note-actions">${canEdit && n.author === state.user.email ? (n.deleted ? `<button class="text-link" data-note-action="restore" data-id="${n.id}">กู้คืน</button>` : `<button class="text-link" data-note-action="edit" data-id="${n.id}">แก้ไข</button><button class="text-link" data-note-action="delete" data-id="${n.id}">ลบ</button>`) : ''}<button class="text-link" data-note-action="history" data-id="${n.id}">ประวัติ (${n.versions.length})</button></div></article>`).join('') || '<p class="small muted" style="margin-top:15px">ยังไม่มีบันทึกการสืบสวน</p>'}</div>`)}</div><div class="stack">${panel('Your assessment', 'ให้เหตุผลและหลักฐานประกอบการตัดสินใจ', `<div class="panel-body"><form id="assessment-form"><input type="hidden" name="expected_version" value="${t.version || 1}"><fieldset ${canEdit ? '' : 'disabled'} style="border:0;padding:0;margin:0;min-width:0"><div class="field"><label for="ticket-title">ชื่อ Ticket</label><input id="ticket-title" name="title" value="${esc(t.title)}" maxlength="120" required></div><div class="form-row"><div class="field"><label for="ticket-severity">Severity</label><select id="ticket-severity" name="severity">${['Low', 'Medium', 'High', 'Critical'].map(s => `<option ${s === t.severity ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="field"><label for="ticket-status">Status</label><select id="ticket-status" name="status">${M.statuses.map(s => `<option ${s === t.status ? 'selected' : ''}>${s}</option>`).join('')}</select></div></div><div class="field"><label for="ticket-disposition">ข้อสรุปของนักวิเคราะห์</label><select id="ticket-disposition" name="disposition"><option value="">เลือกข้อสรุป...</option>${M.dispositions.map(d => `<option ${d === t.disposition ? 'selected' : ''}>${d}</option>`).join('')}</select></div><div class="field"><label for="ticket-reason">เหตุผล / ข้อมูลที่ต้องตรวจเพิ่ม</label><textarea id="ticket-reason" name="reason" maxlength="2000" required placeholder="อ้างหลักฐานและแยกสิ่งที่ยืนยันแล้วออกจากข้อสันนิษฐาน">${esc(t.reason)}</textarea><small>Open → Investigating → Resolved → Closed</small></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary" style="width:100%">${icon('check')} บันทึกการประเมิน</button></fieldset></form></div>`)}${panel('Audit trail', 'ประวัติการตัดสินใจที่แก้ไขย้อนหลังไม่ได้ผ่าน UI', `<div class="panel-body audit-list">${r.audit.filter(a => a.entity === t.id || a.entity === 'ALT-' + t.scenarioId?.slice(1)).map(a => `<div class="audit-entry"><strong>${esc(a.action)}</strong><p>${esc(a.actor)} · ${time(a.time)}</p><p>${esc(a.reason)}</p></div>`).join('') || '<p class="small muted">ยังไม่มีการเปลี่ยนแปลง</p>'}</div>`)}</div></div>`;
  }
  function evaluation() {
    const r = run();
    if (r.state === 'Completing') return heading('Evaluation & debrief', 'กำลังจัดทำ snapshot') + panel('Completing', 'จำลองผลตอบกลับ 202 / pending', empty('กำลังสรุปรอบ', 'ล็อกคำตอบแล้ว ยังไม่แสดงคะแนนหรือเฉลยจนกว่าจะ Completed'));
    if (r.state !== 'Completed') return heading('Evaluation & debrief', 'ทบทวนหลักฐานและเหตุผลเมื่อคุณพร้อมจบรอบ') + panel('รอบนี้ยังไม่จบ', '', empty('ผลประเมินจะเปิดหลังจบรอบ', 'คุณยังกลับไปสืบสวนและบันทึกข้อสรุปได้ จบรอบก่อนเพื่อเปิดเฉลย', editable() ? button('จบรอบและดูผล', 'finish', 'check', 'primary') : button('เริ่มรอบของคุณ', 'new-run', 'play', 'primary')));
    const e = M.evaluate(r);
    return (e.truncated ? '<div class="notice">รอบจบก่อนครบเวลา · Truncated dataset — อย่าเปรียบเทียบผลนี้กับรอบเต็มโดยตรง</div>' : '') + heading('Evaluation & debrief', 'เปรียบเทียบข้อสรุปของคุณกับเฉลยของสถานการณ์จำลอง', button('ส่งออกรายงาน', 'export', 'download') + button('ฝึกรอบใหม่', 'new-run', 'plus', 'primary')) + (r.demo ? demoBanner() : '') + `<div class="stats">${stat('Correct classifications', `${e.correct} / ${e.total}`, 'หนึ่งหน่วยต่อหนึ่งสถานการณ์', 'check')}${stat('Undetermined', e.pending, 'ยังไม่ถือว่ายืนยันว่าปลอดภัย', 'search')}${stat('Evidence collected', r.events.length, `${e.rows.filter(x => x.complete).length} scenarios มีหลักฐานครบ`, 'database')}${stat('Simulation time', time(r.elapsed), 'เวลาจำลอง ไม่รวมช่วงพัก', 'clock')}</div>` +
      panel('Scenario review', 'รายการที่ลบยังถูกนับในการประเมิน · รอบที่จบก่อนกำหนดอาจมีหลักฐานไม่ครบ', `<div class="table-wrap"><table><thead><tr><th>SCENARIO</th><th>YOUR ASSESSMENT</th><th>GROUND TRUTH</th><th>RESULT</th></tr></thead><tbody>${e.rows.map(row => `<tr><td class="table-title">${esc(row.title)}<div class="table-sub">${row.complete ? 'Evidence complete' : 'Incomplete evidence'}${row.deleted ? ' · Ticket deleted' : ''}</div></td><td>${badge(row.answer, row.answer === 'Undetermined' ? 'yellow' : 'gray')}</td><td>${badge(row.truth, 'purple')}</td><td>${badge(row.correct ? 'Correct' : row.answer === 'Undetermined' ? 'Pending / unresolved' : 'Review needed', row.correct ? 'green' : 'yellow')}</td></tr>`).join('')}</tbody></table></div>`) + `<div class="bottom-grid">${panel('What the evidence tells us', 'ใช้เป็นแนวทางทบทวน ไม่ใช่ผลประเมินโมเดลจริง', `<div class="panel-body">${e.rows.map(row => `<div class="audit-entry"><strong>${esc(row.title)}</strong><p>${esc(M.getScenario(row.id).impact)}</p></div>`).join('')}</div>`)}${panel('Detection experiment', 'A / B / C comparison', `<div class="panel-body"><div class="notice">ยังไม่มีการทดลองประมวลผล A/B/C จริงในต้นแบบ จึงไม่แสดง Precision / Recall หรือคะแนนประสิทธิภาพ AI ที่คำนวณขึ้นแทนผลทดลอง</div><div class="audit-entry"><strong>A · Rules only</strong><p>Not measured</p></div><div class="audit-entry"><strong>B · Rules + anomaly</strong><p>Not measured</p></div><div class="audit-entry"><strong>C · Rules + anomaly + AI</strong><p>Not measured · คำวิเคราะห์ใน UI เป็น fixture</p></div></div>`)}</div>`;
  }
  function admin() {
    if (state.user?.role !== 'Instructor') return heading('Instructor workspace', 'ติดตามรอบฝึกและจัดการบัญชีตัวอย่าง') + panel('Restricted workspace', '', empty('คุณไม่มีสิทธิ์เข้าถึงหน้านี้', 'หน้าตัวอย่างนี้สำหรับบทบาท Instructor ใช้บัญชีเดโม Instructor เพื่อสำรวจ', button('เลือกบัญชีเดโม', 'login', 'users', 'primary')));
    return heading('Instructor workspace', 'จัดการบัญชีและโควตาตัวอย่างบน browser นี้', badge('DEMO INSTRUCTOR', 'purple')) + `<div class="notice">สิทธิ์ในต้นแบบเป็นการสาธิต UI เท่านั้น ไม่มี backend authentication หรือการป้องกันข้อมูลจริง</div>` + panel('Demo accounts', 'ปิดใช้งานหรือปรับโควตาของ Analyst · มีผลกับการเข้าสู่ระบบและเริ่มรอบในต้นแบบ', `<div class="table-wrap"><table><thead><tr><th>ACCOUNT</th><th>ROLE</th><th>STATUS</th><th>QUOTA / UTC DAY</th><th>ACTIONS</th></tr></thead><tbody>${accounts().filter(a => a.role === 'Analyst').map(a => `<tr><td>${esc(a.name)}<div class="table-sub">${esc(a.email)}</div></td><td>${badge(a.role, 'purple')}</td><td>${badge(a.disabled ? 'Disabled' : 'Active', a.disabled ? 'red' : 'green')}</td><td>${M.dailyRunCount(state.runs, a.email)} / ${a.quota ?? 10}</td><td><div class="account-actions">${button(a.disabled ? 'เปิดใช้งาน' : 'ปิดใช้งาน', 'toggle-account', 'users', 'small', `data-id="${esc(a.email)}"`)}${button('ปรับโควตา', 'quota-account', 'settings', 'small', `data-id="${esc(a.email)}"`)}</div></td></tr>`).join('')}</tbody></table></div>`) + `<div style="margin-top:22px">${panel('Learner runs', 'เปิดดูหลักฐานและเพิ่มความเห็นโดยไม่เขียนทับข้อสรุปของผู้เรียน', state.runs.length ? `<div class="table-wrap"><table><thead><tr><th>RUN</th><th>OWNER</th><th>STATUS</th><th>TICKETS</th><th></th></tr></thead><tbody>${state.runs.map(r => `<tr><td class="mono">${r.id}</td><td>${esc(r.owner)}</td><td>${status(r.state)}</td><td>${r.tickets.length}</td><td>${button('ตรวจรอบ', 'inspect-run', 'search', 'small', `data-id="${r.id}"`)}</td></tr>`).join('')}</tbody></table></div>` : empty('ยังไม่มีรอบของผู้เรียน', 'เข้าสู่บัญชี Analyst และเริ่มรอบก่อน'))}</div>`;
  }
  function help() {
    return heading('คู่มือเริ่มเรียน', 'รู้หน้าที่ของแต่ละปุ่มก่อนลงมือสืบสวน') + panel('จากเคสแรกสู่ระดับถัดไป', 'เรียนตามหลักฐานจริงในสถานการณ์จำลอง', `<div class="panel-body"><div class="help-grid">${[['01', 'เข้าสู่ระบบ', 'เลือกบัญชี Analyst แล้วอ่านคำแนะนำระดับเริ่มต้นก่อน'], ['02', 'เลือกเคส', 'เปิดเส้นทางเรียนรู้ เลือกหนึ่งเคสที่ปลดล็อก แล้วกดรอบใหม่'], ['03', 'อ่าน Event', 'กด Event explorer เพื่อดู request, response, เวลา บัญชี และอุปกรณ์'], ['04', 'ดู Alert', 'อ่านว่าระบบตรวจด้วย Rule หรือ Anomaly แล้วตามไปที่ Ticket'], ['05', 'ตอบใน Ticket', 'อ่านคำใบ้ เลือกหลักฐาน ตั้งระดับความรุนแรง จัดประเภท และเขียนเหตุผล'], ['06', 'รับคำแนะนำ', 'กดบันทึกการประเมิน ดูผล rubric ถ้ายังไม่ผ่านให้ตรวจหลักฐานและตอบใหม่'], ['07', 'ปลดล็อก', 'ผ่านทุกเคสของระดับปัจจุบัน แล้วดูคำสอนระดับใหม่'], ['08', 'จบรอบ', 'กดจบรอบเพื่อดูเฉลยและส่งออกรายงาน JSON']].map(x => `<div class="scenario-card"><span class="eyebrow">STEP ${x[0]}</span><h3>${x[1]}</h3><p>${x[2]}</p></div>`).join('')}</div></div>`) + `<div class="callout">AI และ RAG coach ในต้นแบบเป็นคู่มือและ rubric ที่เตรียมไว้ ไม่ได้เชื่อมโมเดลจริง ข้อมูลเก็บใน localStorage ของ browser ไม่มีระบบยืนยันตัวตนหรือฐานข้อมูลจริง</div>` + panel('ลองสถานะพิเศษ', 'เปิดแผง Test states มุมขวาบน', `<div class="panel-body"><p>ลอง AI error, โควตาเต็ม, session หมดอายุ และหน้าที่ไม่มีข้อมูลได้โดยไม่กระทบระบบจริง</p><div style="margin-top:17px">${button('เปิด Test states', 'faults', 'settings')}${button('ดูเส้นทางเรียนรู้', 'go-learning', 'book', 'primary')}</div></div>`);
  }
  function render() {
    document.getElementById('app').innerHTML = shell(({ learning, lesson, overview, simulation, events, alerts, tickets, evaluation, admin, help })[state.view]());
    if (state.view === 'tickets' && examining()) {
      const head = document.querySelector('.ai-panel .panel-head');
      if (head) { head.querySelector('h2').textContent = 'คำวิเคราะห์ปิดระหว่างสอบ'; head.querySelector('p').textContent = 'อ่านหลักฐานและให้ข้อสรุปด้วยตัวเอง'; head.querySelector('.badge').textContent = 'EXAM'; }
    }
    const ticket = state.view === 'tickets' && state.ticketId ? currentTicket() : null;
    if (!ticket?.scenarioId || run().demo) return;
    const guide = M.guides[ticket.scenarioId];
    const latest = ticket.coachReviews?.at(-1);
    const review = latest ? `<div class="learning-review ${latest.passed ? 'passed' : ''}"><strong>${latest.passed ? 'ผ่านเคสนี้แล้ว' : 'ลองปรับคำตอบแล้วส่งใหม่ได้'}</strong><p>${latest.checks.filter(check => !check.passed).map(check => check.hint).join(' ') || 'คุณตรวจหลักฐานครบและอธิบายเหตุผลได้ตามเกณฑ์ตัวอย่าง'}</p></div>` : '';
    const guideHtml = `<section class="learning-method ticket-coach"><strong>ครูช่วยดูเคสนี้</strong><p>${esc(guide.focus)}</p><p><b>ทำไมเคสนี้ต้องดู:</b> ${esc(guide.risk)}</p><p><b>คู่มือประกอบ:</b> ${esc(guide.source)}</p><p>กดหลักฐานใน timeline แล้วเลือก event ที่ชี้ขาดในแบบฟอร์มคำตอบ ระบบจะตรวจจากหลักฐานและเหตุผลของคุณ</p>${review}<small>AI + RAG coach ใน prototype เป็นคู่มือและ rubric จำลอง ยังไม่ใช่โมเดลจริง</small></section>`;
    if (!examining()) document.querySelector('.detail-grid')?.insertAdjacentHTML('beforebegin', guideHtml);
    const form = document.getElementById('assessment-form');
    const severitySelect = form?.querySelector('#ticket-severity');
    if (examining() && severitySelect && ticket.severity === 'Unrated') {
      severitySelect.insertAdjacentHTML('afterbegin', '<option value="" selected disabled>เลือกระดับความรุนแรง...</option>');
      severitySelect.required = true;
    }
    const submit = form?.querySelector('button[type="submit"]');
    if (submit) submit.insertAdjacentHTML('beforebegin', `<div class="field"><label for="coach-evidence">หลักฐานใดชี้ขาดสำหรับคำตอบนี้?</label><select id="coach-evidence" name="coach_evidence" ${editable() && !ticket.deleted ? 'required' : 'disabled'}><option value="">เลือก event หลังตรวจ request/response</option>${run().events.filter(event => ticket.evidenceIds.includes(event.id)).map(event => `<option value="${esc(event.id)}" ${latest?.evidenceId === event.id ? 'selected' : ''}>${esc(event.id)} · ${esc(event.message)}</option>`).join('')}</select></div>`);
  }
  function showLevelTour(levelId, force = false) {
    if (!state.user) return authModal();
    const level = M.levels.find(item => item.id === levelId);
    if (!level) return;
    const key = `${state.user.email}:${level.id}`;
    if (state.tours[key] && !force) return;
    state.tours[key] = true; save();
    const emphasis = {
      beginner: 'เริ่มจากแยกคำขอที่ถูกปฏิเสธออกจากการเข้าถึงสำเร็จ เปิด request/response แล้วดูรหัส 401 หรือ 403',
      intermediate: 'ระดับนี้มีทั้งการสแกนที่ได้รับอนุญาตและการเข้าถึงข้อมูลสำคัญ ตรวจ change ticket และเชื่อม event หลายรายการ',
      advanced: 'ระดับนี้ไม่มีกฎเฉพาะ ให้เทียบกับ baseline และหาหลักฐานยืนยันผลกระทบก่อนสรุป'
    }[level.id];
    modal(`คำแนะนำระดับ ${level.title}`, `<div class="lesson-tour"><p>${emphasis}</p><ol><li><b>บทเรียน:</b> กด “เรียนวิธีอ่าน request” แล้วกดจุดที่ระบบชี้ทีละขั้น</li><li><b>เริ่มทดสอบ:</b> เมื่อเรียนจบจึงเลือกเคสทดสอบที่เปิดอยู่</li><li><b>Event explorer:</b> กด event เพื่อดู request, response, เวลาและบัญชี</li><li><b>Alert queue:</b> ดูสัญญาณ แล้วตามไปที่ Ticket</li><li><b>Ticket:</b> เปิด timeline เลือกหลักฐาน ตั้ง severity จัดประเภท และเขียนเหตุผลด้วยตัวเอง</li><li><b>ส่งคำตอบ:</b> หลังส่งจึงเห็นผล rubric จำลอง หากยังไม่ผ่านให้กลับไปทบทวนแล้วสอบใหม่</li></ol><p>ผ่าน ${level.scenarioIds.length} เคสทดสอบของระดับนี้เพื่อเปิดระดับถัดไป</p></div>${button('เข้าใจแล้ว', 'close-modal', 'check', 'primary')}`, true);
  }
  function showLessonFeedback(review, nextLevel) {
    const rows = review.checks.map(check => `<li class="${check.passed ? 'check-pass' : 'check-fail'}"><strong>${check.passed ? 'ผ่าน' : 'ดูเพิ่ม'} · ${esc(check.label)}</strong>${check.passed ? '' : `<p>${esc(check.hint)}</p>`}</li>`).join('');
    modal(review.passed ? 'ผ่านเคสทดสอบแล้ว' : 'ผลทดสอบ: ยังไม่ผ่าน', `<p>ผลจาก rubric จำลอง 4 ข้อ · แสดงหลังส่งคำตอบ ไม่ใช่ AI/RAG จริง</p><ul class="lesson-feedback">${rows}</ul>${nextLevel ? `<div class="learning-review passed"><strong>ปลดล็อก${esc(nextLevel.title)}แล้ว</strong><p>${esc(nextLevel.description)} เริ่มบทเรียนของระดับใหม่ก่อนสอบ</p></div>` : ''}<div class="modal-actions">${button('ปิดผล', 'close-modal', '')}${button('ดูเส้นทางเรียนรู้', 'feedback-to-learning', 'arrow', 'primary')}</div>`, true);
  }
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
    modal('เข้าสู่ SOC workspace', `<div class="auth-logo"><div class="brand-mark">${icon('shield')}</div><strong>sentinel<span class="brand-dot">.</span></strong></div><p>บัญชีสำหรับจำลอง flow เท่านั้น ใช้รหัส <strong style="color:var(--purple)">DemoSOC1234!</strong> กับทุกบัญชีตัวอย่าง ไม่ใช้รหัสผ่านจริงของคุณ</p><div class="auth-tabs"><button class="${mode === 'login' ? 'active' : ''}" data-action="auth-login">Login</button><button class="${mode === 'register' ? 'active' : ''}" data-action="auth-register">Create demo account</button></div><form id="auth-form">${mode === 'register' ? '<div class="field"><label for="auth-name">ชื่อที่แสดง</label><input id="auth-name" name="name" required maxlength="60" autocomplete="off"></div>' : ''}<div class="field"><label for="auth-email">อีเมลบัญชีตัวอย่าง</label><input id="auth-email" name="email" type="email" required maxlength="254" autocomplete="off" value="${mode === 'login' ? 'analyst@demo.test' : ''}" placeholder="yourname@demo.test"></div><div class="field"><label for="auth-password">รหัสเดโม (DemoSOC1234!)</label><input id="auth-password" name="password" type="password" required autocomplete="off" placeholder="DemoSOC1234!"></div><div class="form-error" role="alert">${esc(error)}</div><button type="submit" class="btn primary" style="width:100%">${mode === 'login' ? 'เข้าสู่ระบบเดโม' : 'สร้างบัญชี Analyst จำลอง'}</button></form><div class="feature-list">${button('ใช้บัญชี Analyst', 'demo-analyst', 'users', 'small')}${button('ใช้บัญชี Instructor', 'demo-instructor', 'users', 'small')}</div><p class="status-note">ไม่เก็บรหัสผ่าน · ข้อมูลรอบฝึกเก็บเฉพาะ browser นี้ · Refresh แล้วต้องเข้าสู่ระบบใหม่</p>`);
  }
  function login(email) {
    const a = accounts().find(a => a.email === email);
    if (!a || a.disabled) throw Error('เข้าสู่ระบบไม่สำเร็จ บัญชีหรือรหัสเดโมไม่ถูกต้อง หรือบัญชีถูกปิดใช้งาน');
    state.runs.forEach(r => M.syncClock(r)); save();
    state.user = { ...a }; state.selectedRun = state.runs.filter(r => r.owner === email).at(-1)?.id || null;
    closeModal(); navigate(a.role === 'Instructor' ? 'admin' : 'learning'); toast('เข้าสู่ระบบเดโมแล้ว');
    if (a.role === 'Analyst') showLevelTour(M.levels[M.learningProgress(state.runs, email).unlockedIndex].id, !state.runs.some(r => r.owner === email));
  }
  function eventModal(id) {
    const e = run().events.find(e => e.id === id); if (!e) return toast('หลักฐานยังไม่ถูกปล่อยในรอบนี้');
    modal('Evidence / ' + esc(e.id), `<p>${esc(e.message)}</p><dl class="key-value"><dt>Timestamp</dt><dd>${eventTime(e.time)} ICT · fixture time</dd><dt>Source</dt><dd>${esc(e.source)}</dd><dt>Asset / user</dt><dd>${esc(e.asset)} / ${esc(e.user)}</dd><dt>Source IP</dt><dd>${esc(e.ip)}</dd></dl><h3>Request</h3><pre>${esc(JSON.stringify({ request: e.request, host: 'democorp.test', source_ip: e.ip, user: e.user, session: e.scenarioId === 'S02' && e.time >= 29 ? 'SES-041' : null }, null, 2))}</pre><h3>Response / log</h3><pre>${esc(JSON.stringify({ status: e.response, event_id: e.id, message: e.message, asset: e.asset, source: e.source, simulated: true }, null, 2))}</pre><p class="status-note">หลักฐานอ่านอย่างเดียว · fixture-v1 · ไม่มี password หรือ access token</p>`, true);
  }
  function faultsModal() {
    modal('Prototype test states', `<p>สลับสถานะเพื่อสาธิตเส้นทางข้อผิดพลาด โดยไม่กระทบบริการจริง</p><div class="field"><label class="toggle"><input type="checkbox" id="fault-ai" ${state.faults.ai ? 'checked' : ''}> AI unavailable · ตรวจหลักฐานต่อได้</label></div><div class="field"><label class="toggle"><input type="checkbox" id="fault-quota" ${state.faults.quota ? 'checked' : ''}> โควตาเต็ม · ไม่สามารถเริ่มรอบใหม่</label></div><div class="feature-list">${button('Session หมดอายุ', 'expire', 'clock')}${button('Empty state', 'empty-run', 'database')}${button('ไม่มีสิทธิ์', 'no-access', 'shield')}${button('ล้างสถานะทดสอบ', 'clear-faults', 'refresh')}</div><div class="callout">Login error: กรอกรหัสที่ไม่ใช่ DemoSOC1234!<br>Validation error: ข้ามสถานะจาก Open ไป Closed หรือไม่เลือกข้อสรุป<br>AI error: เปิด Ticket หลังเลือก AI unavailable</div>`);
  }
  function startSelected() {
    if (!state.user) return authModal();
    if (state.selection.length !== 1) return toast('เลือกหนึ่งเคสเพื่อเรียนทีละขั้น');
    const level = M.levelForScenario(state.selection[0]);
    if (M.levels.indexOf(level) > M.learningProgress(state.runs, state.user.email).unlockedIndex || !lessonDone(level)) return toast('เรียนบทของระดับนี้ก่อนเริ่มทดสอบ');
    const a = accounts().find(a => a.email === state.user.email);
    if (a.disabled) return logout('บัญชีถูกปิดใช้งาน');
    if (state.faults.quota || M.dailyRunCount(state.runs, state.user.email) >= (a.quota ?? 10)) return modal('Run quota reached', `<div class="notice error">โควตารอบจำลองเต็มแล้ว คุณยังตรวจรอบเดิมได้ ให้ Instructor ปรับโควตา หรือปิดสถานะจำลองโควตาเต็มใน Test states</div>${button('กลับไปตรวจ Ticket', 'close-and-tickets', 'ticket')}`);
    state.runs.forEach(r => M.syncClock(r));
    if (state.runs.some(r => r.owner === state.user.email && r.state === 'Running')) return toast('มีรอบกำลังทำงานอยู่แล้ว กรุณาพักหรือจบรอบนั้นก่อน');
    const r = M.makeRun(state.selection); r.owner = state.user.email; r.mode = 'exam'; r.comments = []; state.runs.push(r); state.selectedRun = r.id;
    M.audit(r, state.user.email, 'Exam started', r.id, state.selection.join(', ')); save(); closeModal(); navigate('events'); toast('เริ่มทดสอบแล้ว · event แรกจะเข้ามาใน 5 วินาที');
  }
  function logout(message = 'ออกจากระบบเดโมแล้ว') {
    state.runs.forEach(r => M.syncClock(r));
    save(); state.user = null; state.selectedRun = null; closeModal(); navigate('learning'); toast(message);
  }
  function confirmForm(title, text, type, extra = '') { modal(title, `<p>${text}</p><form id="${type}">${extra}<div class="field"><label for="confirm-reason">เหตุผล</label><textarea id="confirm-reason" name="reason" required maxlength="2000" placeholder="ระบุเหตุผลเพื่อเก็บใน audit trail"></textarea></div><div class="form-error" role="alert"></div><div class="modal-actions">${button('ยกเลิก', 'close-modal', '')}<button type="submit" class="btn ${type.includes('delete') ? 'danger' : 'primary'}">ยืนยัน</button></div></form>`); }
  function createTicketModal() {
    if (!requireEdit()) return;
    if (!run().events.length) return toast('ต้องมีหลักฐานอย่างน้อย 1 event ก่อนสร้าง Ticket');
    modal('Create investigation ticket', `<p>สร้างเคสจากหลักฐานที่ปล่อยแล้วในรอบของคุณ</p><form id="create-ticket-form"><div class="field"><label for="new-title">ชื่อ Ticket</label><input id="new-title" name="title" maxlength="120" required></div><div class="field"><label for="new-evidence">หลักฐานตั้งต้น</label><select id="new-evidence" name="evidence">${run().events.map(e => `<option value="${e.id}">${e.id} · ${esc(e.message)}</option>`).join('')}</select></div><div class="field"><label for="new-severity">Severity</label><select id="new-severity" name="severity">${['Low', 'Medium', 'High', 'Critical'].map(s => `<option>${s}</option>`).join('')}</select></div><div class="field"><label for="new-reason">เหตุผลที่เปิดเคส</label><textarea id="new-reason" name="reason" required maxlength="2000"></textarea></div><div class="form-error" role="alert"></div><div class="modal-actions"><button class="btn primary" type="submit">สร้าง Ticket</button></div></form>`);
  }
  function exportReport() {
    const r = run(); if (r.state !== 'Completed') return toast('EXPORT_LOCKED: ส่งออกรายงานได้หลังจบรอบเท่านั้น'); const data = { prototype: true, warning: 'Simulated evidence and mock AI; not a real detector benchmark', run: r, evaluation: r.state === 'Completed' ? M.evaluate(r) : 'Locked until run completion' };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = `sentinel-${r.id}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); toast('ส่งออกรายงาน JSON แล้ว');
  }
  function inspectRun(id) {
    if (state.user?.role !== 'Instructor') return toast('ไม่มีสิทธิ์');
    const r = state.runs.find(r => r.id === id); if (!r) return;
    modal('Review / ' + r.id, `<p>${esc(r.owner)} · ${r.tickets.length} tickets · ${r.events.length} events</p>${r.tickets.map(t => `<div class="note"><strong>${esc(t.id)} · ${esc(t.title)}</strong><div class="detail-meta">${severity(t.severity)}${status(t.status)}${badge(t.disposition || 'Pending')}</div><p>${esc(t.reason || 'ยังไม่มีข้อสรุป')}</p><details><summary class="small muted">หลักฐาน (${t.evidenceIds.length})</summary><pre>${esc(JSON.stringify(r.events.filter(e => t.evidenceIds.includes(e.id)), null, 2))}</pre></details>${button('ปรับ severity / status', 'instructor-ticket', 'settings', 'small', `data-id="${r.id}" data-ticket-id="${t.id}" ${M.isMutable(r) && !t.deleted ? '' : 'disabled'}`)}</div>`).join('') || '<p>ยังไม่มี Ticket</p>'}<form id="instructor-comment" data-run="${r.id}" style="margin-top:20px"><div class="field"><label for="instructor-note">ความเห็นประกอบการประเมิน</label><textarea id="instructor-note" name="content" required maxlength="2000"></textarea></div><div class="form-error" role="alert"></div><button class="btn primary" type="submit">เพิ่มความเห็น</button></form>${(r.comments || []).map(c => `<div class="note"><div class="note-meta">${esc(c.author)}</div><p>${esc(c.content)}</p></div>`).join('')}`, true);
  }
  function noteAction(action, id) {
    const t = currentTicket(); const n = t?.notes.find(n => n.id === id); if (!n) return;
    if (action === 'history') return modal('Note version history', n.versions.length ? n.versions.map((v, i) => `<div class="note"><div class="note-meta">Version ${i + 1} · ${time(v.time)}</div><p>${esc(v.content)}</p></div>`).join('') : '<p>ยังไม่มีเวอร์ชันก่อนหน้า</p>');
    if (!requireEdit() || n.author !== state.user.email || t.deleted) return;
    if (action === 'edit') modal('Edit investigation note', `<form id="edit-note-form" data-note="${id}"><input type="hidden" name="expected_version" value="${n.version || 1}"><div class="field"><label for="edit-note">เนื้อหาบันทึก</label><textarea id="edit-note" name="content" required maxlength="2000">${esc(n.content)}</textarea></div><div class="field"><label for="edit-note-reason">เหตุผลการแก้ไข</label><input id="edit-note-reason" name="reason" maxlength="2000" required></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary">บันทึกเวอร์ชันใหม่</button></form>`);
    if (action === 'delete') confirmForm('Delete note?', 'บันทึกจะถูกลบแบบ soft delete และกู้คืนได้', 'delete-note-form', `<input type="hidden" name="note" value="${id}"><input type="hidden" name="expected_version" value="${n.version || 1}">`);
    if (action === 'restore') confirmForm('Restore note?', 'ระบุเหตุผลในการกู้คืนบันทึก', 'restore-note-form', `<input type="hidden" name="note" value="${id}"><input type="hidden" name="expected_version" value="${n.version || 1}">`);
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
      case 'go-learning': closeModal(); navigate('learning'); break;
      case 'feedback-to-learning': closeModal(); navigate('learning'); if (state.user) showLevelTour(M.levels[M.learningProgress(state.runs, state.user.email).unlockedIndex].id); break;
      case 'tour-current': if (!state.user) authModal(); else showLevelTour(M.levels[M.learningProgress(state.runs, state.user.email).unlockedIndex].id, true); break;
      case 'open-lesson': if (!state.user) authModal(); else {
        const level = M.levels.find(item => item.id === el.dataset.level);
        if (!level || M.levels.indexOf(level) > M.learningProgress(state.runs, state.user.email).unlockedIndex) return toast('ระดับนี้ยังไม่เปิด');
        state.lessonLevel = level.id; state.lessonStep = 0; state.lessonTouched = false; navigate('lesson');
      } break;
      case 'lesson-field': if (state.view === 'lesson' && el.dataset.field === lessonData[state.lessonLevel].steps[state.lessonStep].target) { state.lessonTouched = true; render(); } break;
      case 'lesson-prev': if (state.view === 'lesson' && state.lessonStep > 0) { state.lessonStep--; state.lessonTouched = false; render(); } break;
      case 'lesson-next': if (state.view === 'lesson' && state.lessonTouched) {
        if (state.lessonStep < lessonData[state.lessonLevel].steps.length - 1) { state.lessonStep++; state.lessonTouched = false; render(); }
        else { state.learned[`${state.user.email}:${state.lessonLevel}`] = true; save(); navigate('learning'); toast('จบบทเรียนแล้ว · เปิดเคสทดสอบระดับนี้ได้'); }
      } break;
      case 'start-current-lesson': if (!state.user) authModal(); else {
        const progress = M.learningProgress(state.runs, state.user.email);
        const level = M.levels[progress.unlockedIndex];
        if (!lessonDone(level)) { state.lessonLevel = level.id; state.lessonStep = 0; state.lessonTouched = false; navigate('lesson'); }
        else { state.selection = [level.scenarioIds.find(id => !progress.passed.includes(id)) || level.scenarioIds[0]]; navigate('simulation'); }
      } break;
      case 'launch-lesson': if (!state.user) authModal(); else {
        const level = M.levelForScenario(el.dataset.id);
        if (M.levels.indexOf(level) > M.learningProgress(state.runs, state.user.email).unlockedIndex || !lessonDone(level)) return toast('เรียนบทนี้และผ่านระดับก่อนหน้าเพื่อปลดล็อก');
        state.selection = [el.dataset.id]; navigate('simulation');
      } break;
      case 'start-selected': startSelected(); break;
      case 'pause': if (requireEdit()) { try { if (r.state === 'Running') M.pauseRun(r); else M.resumeRun(r, state.runs); } catch (e) { toast(e.message); break; } M.audit(r, state.user.email, 'Run ' + r.state, r.id, 'Simulation control'); save(); render(); } break;
      case 'finish': if (requireEdit()) modal('จบรอบจำลอง?', `<p>ยืนยันแล้วจะล็อกคำตอบและหยุด event ใหม่ ผ่านสถานะ Completing ก่อนเปิดเฉลย อ่านย้อนหลังได้แต่แก้ไขไม่ได้</p><div class="notice">มี ${r.tickets.filter(t => !t.disposition || t.disposition === 'Undetermined').length} Ticket ที่ยังไม่สรุป · หลักฐาน ${r.events.length} events</div><div class="modal-actions">${button('สืบสวนต่อ', 'close-modal', '')}${button('ยืนยันจบรอบ', 'confirm-finish', 'check', 'primary')}</div>`); break;
      case 'confirm-finish': if (requireEdit()) { M.finishRun(r); M.audit(r, state.user.email, 'Run completing', r.id, 'User ended exercise'); save(); closeModal(); navigate('evaluation'); } break;
      case 'go-tickets': navigate('tickets'); break;
      case 'go-evaluation': navigate('evaluation'); break;
      case 'close-and-tickets': closeModal(); navigate('tickets'); break;
      case 'help': navigate('help'); break;
      case 'close-modal': closeModal(); break;
      case 'prev-events': state.page = Math.max(1, state.page - 1); render(); break;
      case 'next-events': state.page++; render(); break;
      case 'clear-event-filters': state.eventFilters = {}; state.filterError = ''; state.search = ''; state.filter = 'All'; state.page = 1; render(); break;
      case 'search': state.page = 1; state.search = document.getElementById('table-search')?.value || ''; render(); break;
      case 'assessment-history': modal('Assessment revisions', (currentTicket().assessments || []).map((a,i) => `<div class="note"><strong>Revision ${i+1} · ${esc(a.disposition || 'Pending')}</strong><p>${esc(a.reason)}</p><span class="small muted">${esc(a.author)} · ${time(a.time)}</span></div>`).join('') || '<p>ยังไม่มีประวัติคำตอบ</p>'); break;
      case 'refresh-evidence': {
        const drafts = ['assessment-form', 'note-form'].map(id => { const f = document.getElementById(id); return { id, values: f ? Object.fromEntries(new FormData(f)) : {} }; });
        render();
        drafts.forEach(({ id, values }) => { const f = document.getElementById(id); if (f) Object.entries(values).forEach(([name, value]) => { if (name === 'expected_version') return; if (f.elements.namedItem(name)) f.elements.namedItem(name).value = value; }); });
        toast('อัปเดตหลักฐานแล้ว · เก็บข้อความที่กำลังกรอกไว้'); break;
      }
      case 'create-ticket': createTicketModal(); break;
      case 'delete-ticket': if (requireEdit()) confirmForm('Delete ticket?', 'Ticket และหลักฐานจะยังคงอยู่ในผลประเมิน สามารถกู้คืนได้จากรายการที่ลบแล้ว', 'delete-ticket-form', `<input type="hidden" name="expected_version" value="${currentTicket().version || 1}">`); break;
      case 'restore-ticket': if (requireEdit()) confirmForm('Restore ticket?', 'ระบุเหตุผลในการกู้คืน Ticket', 'restore-ticket-form', `<input type="hidden" name="expected_version" value="${currentTicket().version || 1}">`); break;
      case 'submit-note': document.getElementById('note-form')?.requestSubmit(); break;
      case 'export': exportReport(); break;
      case 'faults': faultsModal(); break;
      case 'retry-ai': if (requireEdit()) { state.faults.ai = false; M.audit(r, state.user.email, 'Mock analysis retry', currentTicket().id, 'Reload fixture; no provider request'); save(); render(); toast('โหลดคำวิเคราะห์ fixture สำเร็จ'); } break;
      case 'expire': logout('Session จำลองหมดอายุ กรุณาเข้าสู่ระบบใหม่'); authModal('login', 'Session หมดอายุ ประวัติรอบฝึกยังอยู่'); break;
      case 'no-access': closeModal(); if (state.user?.role === 'Instructor') modal('Access denied · test state', '<div class="notice error">คุณไม่มีสิทธิ์เข้าถึงรอบของบัญชีนี้ (สถานะจำลอง)</div>'); else navigate('admin'); break;
      case 'clear-faults': state.faults = { ai: false, quota: false }; closeModal(); render(); toast('ล้างสถานะทดสอบแล้ว'); break;
      case 'empty-run': if (!state.user) authModal(); else { startSelected(); if (!run().demo && run().elapsed === 0) { M.pauseRun(run()); save(); closeModal(); navigate('events'); } } break;
      case 'open-run': if (state.runs.some(x => x.id === el.dataset.id && x.owner === state.user?.email)) { state.selectedRun = el.dataset.id; navigate('overview'); } break;
      case 'toggle-account': if (state.user?.role === 'Instructor') { const ac = accounts().find(x => x.email === el.dataset.id); accountPatch(ac.email, { disabled: !ac.disabled }); render(); toast('ปรับสถานะบัญชีตัวอย่างแล้ว'); } break;
      case 'quota-account': if (state.user?.role === 'Instructor') { const ac = accounts().find(x => x.email === el.dataset.id); modal('Adjust demo quota', `<p>${esc(ac.email)}</p><form id="quota-form" data-email="${esc(ac.email)}"><div class="field"><label for="quota">จำนวนรอบต่อวัน UTC (0–100)</label><input id="quota" name="quota" type="number" min="0" max="100" required value="${ac.quota ?? 10}"></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary">บันทึกโควตา</button></form>`); } break;
      case 'inspect-run': inspectRun(el.dataset.id); break;
      case 'instructor-ticket': if (state.user?.role === 'Instructor') { const targetRun = state.runs.find(x => x.id === el.dataset.id); const t = targetRun?.tickets.find(x => x.id === el.dataset.ticketId); if (!t || t.deleted || !M.isMutable(targetRun)) return toast('รอบอ่านอย่างเดียวหรือ Ticket ถูกลบ ไม่สามารถแก้ไขได้'); modal('Instructor ticket review', `<p>${esc(t.id)} · ไม่แก้ข้อสรุปหรือเหตุผลของผู้เรียน</p><form id="instructor-ticket-form" data-run="${targetRun.id}" data-ticket="${t.id}"><input type="hidden" name="expected_version" value="${t.version || 1}"><div class="field"><label for="admin-severity">Severity</label><select id="admin-severity" name="severity">${['Low', 'Medium', 'High', 'Critical'].map(s => `<option ${s === t.severity ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="field"><label for="admin-status">Status</label><select id="admin-status" name="status">${M.statuses.map(s => `<option ${s === t.status ? 'selected' : ''}>${s}</option>`).join('')}</select></div><div class="field"><label for="admin-reason">เหตุผลของ Instructor</label><textarea id="admin-reason" name="reason" required maxlength="2000"></textarea></div><div class="form-error" role="alert"></div><button type="submit" class="btn primary">บันทึก</button></form>`); } break;
    }
  });
  document.addEventListener('change', event => {
    const el = event.target;
    if (el.dataset.scenario) { state.selection = [el.dataset.scenario]; render(); }
    if (el.id === 'table-filter') { state.page = 1; state.filter = el.value; state.search = document.getElementById('table-search')?.value || ''; render(); }
    if (el.id === 'show-deleted') { state.deleted = el.checked; render(); }
    if (el.id === 'show-deleted-notes') { state.noteDeleted = el.checked; render(); }
    if (el.id === 'fault-ai') { state.faults.ai = el.checked; render(); }
    if (el.id === 'fault-quota') state.faults.quota = el.checked;
  });
  document.addEventListener('keydown', event => { if (event.key === 'Enter' && event.target.id === 'table-search') { event.preventDefault(); state.search = event.target.value; state.page = 1; render(); } });
  document.addEventListener('submit', event => {
    event.preventDefault(); const form = event.target; const data = Object.fromEntries(new FormData(form));
    const error = message => { const el = form.querySelector('.form-error'); if (el) el.textContent = message; else toast(message); };
    try {
      if (form.id === 'event-filter-form') { M.filterEvents(run(), data); state.eventFilters = data; state.page = 1; render(); return; }
      if (form.id === 'auth-form') {
        const email = data.email.trim().toLowerCase();
        if (data.password !== 'DemoSOC1234!') throw Error('เข้าสู่ระบบไม่สำเร็จ บัญชีหรือรหัสเดโมไม่ถูกต้อง หรือบัญชีถูกปิดใช้งาน');
        if (state.authMode === 'register') { if (!data.name?.trim() || data.name.length > 60) throw Error('กรอกชื่อ 1–60 ตัวอักษร'); if (!email.endsWith('@demo.test')) throw Error('ใช้บัญชีตัวอย่างลงท้าย @demo.test'); if (accounts().some(a => a.email === email)) throw Error('ไม่สามารถสร้างบัญชีนี้ได้ กรุณาใช้ชื่อใหม่'); state.accounts.push({ email, name: data.name.trim(), role: 'Analyst', quota: 10, disabled: false }); save(); authModal('login', 'สร้างบัญชี Analyst จำลองแล้ว กรุณาเข้าสู่ระบบ'); document.getElementById('auth-email').value = email; return; }
        login(email); return;
      }
      if (form.id === 'quota-form') { if (state.user?.role !== 'Instructor') throw Error('ไม่มีสิทธิ์'); const n = Number(data.quota); if (!Number.isInteger(n) || n < 0 || n > 100) throw Error('โควตาต้องเป็นจำนวนเต็ม 0–100'); accountPatch(form.dataset.email, { quota: n }); closeModal(); render(); toast('ปรับโควตาแล้ว'); return; }
      if (form.id === 'instructor-comment') { if (state.user?.role !== 'Instructor' || !data.content.trim()) throw Error('กรอกความเห็นก่อนบันทึก'); const r = state.runs.find(r => r.id === form.dataset.run); r.comments ||= []; r.comments.push({ author: state.user.email, content: data.content.trim(), time: r.elapsed }); M.audit(r, state.user.email, 'Instructor comment', r.id, data.content.trim()); save(); inspectRun(r.id); toast('เพิ่มความเห็นแล้ว'); return; }
      if (form.id === 'instructor-ticket-form') {
        if (state.user?.role !== 'Instructor') throw Error('ไม่มีสิทธิ์'); const r = state.runs.find(r => r.id === form.dataset.run); const t = r.tickets.find(t => t.id === form.dataset.ticket); M.assertMutable(r);
        M.updateTicket(r, t.id, { title: t.title, severity: data.severity, status: data.status, disposition: t.disposition, reason: data.reason, expected_version: data.expected_version }, state.user.email, true); save(); inspectRun(r.id); toast('ปรับสถานะโดย Instructor แล้ว'); return;
      }
      if (!requireEdit()) return;
      const r = run(); const t = currentTicket();
      if (form.id === 'assessment-form') {
        const before = M.learningProgress(state.runs, state.user.email).unlockedIndex;
        M.updateTicket(r, t.id, data, state.user.email);
        let review;
        if (t.scenarioId) {
          review = M.reviewLesson(r, t, data.coach_evidence);
          t.coachReviews ||= [];
          t.coachReviews.push(review);
          M.audit(r, 'Prototype coach', review.passed ? 'Exam passed' : 'Exam feedback', t.id, `mock rubric ${review.checks.filter(check => check.passed).length}/4`);
          if (review.checks[0].passed && r.scenarioIds.length === 1) {
            M.finishRun(r);
            M.audit(r, 'Prototype coach', 'Run completing', r.id, 'Exam submitted; freeze answer before next attempt');
          }
        }
        save(); render();
        if (review) {
          const after = M.learningProgress(state.runs, state.user.email).unlockedIndex;
          const nextLevel = after > before ? M.levels[after] : null;
          showLessonFeedback(review, nextLevel);
        } else toast('บันทึกการประเมินแล้ว');
        return;
      }
      if (form.id === 'create-ticket-form') {
        if (!data.title.trim() || data.title.length > 120 || !data.reason.trim() || data.reason.length > 2000) throw Error('กรอกชื่อและเหตุผลให้ครบตามความยาวที่กำหนด');
        if (!r.events.some(e => e.id === data.evidence)) throw Error('หลักฐานต้องอยู่ในรอบนี้');
        const ticket = { id: 'TKT-M' + (r.tickets.filter(t => !t.scenarioId).length + 1), scenarioId: null, title: data.title.trim(), severity: data.severity, status: 'Open', disposition: '', reason: data.reason.trim(), notes: [], version: 1, assessments: [], deleted: false, created: r.elapsed, evidenceIds: [data.evidence] };
        r.tickets.push(ticket); M.audit(r, state.user.email, 'Manual ticket created', ticket.id, ticket.reason); state.ticketId = ticket.id; state.view = 'tickets';
      }
      if (form.id === 'note-form') { if (!data.content.trim() || data.content.length > 2000 || t.deleted) throw Error('ระบุข้อความ 1–2,000 ตัวอักษรใน Ticket ที่ยังไม่ถูกลบ'); if (data.evidence && !t.evidenceIds.includes(data.evidence)) throw Error('หลักฐานไม่อยู่ใน Ticket นี้'); const n = { id: 'N-' + Date.now(), content: data.content.trim(), evidence: data.evidence, author: state.user.email, time: r.elapsed, deleted: false, version: 1, versions: [] }; t.notes.push(n); M.audit(r, state.user.email, 'Note created', t.id, n.id); }
      if (form.id === 'edit-note-form') { const n = t.notes.find(n => n.id === form.dataset.note); if (!n || n.deleted || n.author !== state.user.email || t.deleted) throw Error('ไม่สามารถแก้บันทึกนี้ได้'); if (!data.content.trim() || data.content.length > 2000) throw Error('ระบุข้อความ 1–2,000 ตัวอักษร'); M.assertVersion(n, data.expected_version); if (!data.reason?.trim()) throw Error('ระบุเหตุผลการแก้ไข'); n.versions.push({ content: n.content, time: r.elapsed, reason: data.reason.trim() }); n.version = (n.version || 1) + 1; n.content = data.content.trim(); M.audit(r, state.user.email, 'Note updated', t.id, `${n.id} · v${n.version} · ${data.reason.trim()}`); }
      if (form.id === 'delete-ticket-form' || form.id === 'delete-note-form') { if (!data.reason.trim()) throw Error('ระบุเหตุผลก่อนลบ'); if (form.id === 'delete-ticket-form') { M.assertVersion(t, data.expected_version); t.deleted = true; t.version++; M.audit(r, state.user.email, 'Ticket deleted', t.id, data.reason.trim()); } else { const n = t.notes.find(n => n.id === data.note); if (!n || n.author !== state.user.email || t.deleted) throw Error('ไม่มีสิทธิ์ลบบันทึกนี้'); M.assertVersion(n, data.expected_version); n.deleted = true; n.version = (n.version || 1) + 1; M.audit(r, state.user.email, 'Note deleted', t.id, data.reason.trim()); } }
      if (form.id === 'restore-ticket-form' || form.id === 'restore-note-form') { if (!data.reason?.trim()) throw Error('ระบุเหตุผลในการกู้คืน'); const target = form.id === 'restore-ticket-form' ? t : t.notes.find(n => n.id === data.note && n.author === state.user.email); if (!target || (target !== t && t.deleted)) throw Error('ไม่สามารถกู้คืนได้'); M.assertVersion(target, data.expected_version); target.deleted = false; target.version = (target.version || 1) + 1; M.audit(r, state.user.email, target === t ? 'Ticket restored' : 'Note restored', t.id, data.reason.trim()); }
      save(); closeModal(); render(); toast('บันทึกเรียบร้อยแล้ว');
    } catch (e) { error(e.message); }
  });
  setInterval(() => {
    const r = run(); const previous = r.events.length; const priorState = r.state;
    let changed = false;
    state.runs.forEach(item => { const before = `${item.state}:${item.elapsed}`; M.syncClock(item); changed ||= before !== `${item.state}:${item.elapsed}`; });
    if (changed) save();
    document.querySelectorAll('[data-clock]').forEach(el => { el.textContent = time(r.elapsed); });
    document.querySelectorAll('[data-progress]').forEach(el => { el.style.width = r.elapsed / r.duration * 100 + '%'; });
    const typing = ['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);
    if ((previous !== r.events.length || priorState !== r.state) && !state.ticketId && !document.querySelector('dialog') && !typing) render();
    if (priorState !== r.state && r.state === 'Reviewing') toast('ปล่อยเหตุการณ์ครบแล้ว สืบสวนต่อหรือจบรอบเพื่อดูเฉลยได้');
  }, 1000);
  window.addEventListener('beforeunload', save);
  render();
})();
