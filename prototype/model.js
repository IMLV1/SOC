(function (global) {
  'use strict';
  const scenarios = [
    { id: 'S01', title: 'Brute-force attempts', thai: 'ลองรหัสผ่านหลายครั้ง', description: 'ตรวจความพยายามเข้าใช้งาน โดยแยกให้ออกว่ามีการเข้าถึงสำเร็จหรือไม่', category: 'IDENTITY', level: 'Beginner', asset: 'AUTH-01', user: 'finance.user', ip: '198.51.100.20', severity: 'Medium', detector: 'Rule', truth: 'True Positive', impact: 'พบความพยายามเข้าสู่ระบบที่ถูกปฏิเสธ ยังไม่มีหลักฐานว่าบัญชีถูกยึด', unknown: 'ยังไม่ทราบผู้ควบคุม IP ต้นทาง ตรวจสอบ log ช่วงเวลาอื่นเพิ่มเติม', steps: [['Authentication failed', 'POST /auth/login', 401], ['Repeated authentication failures · 12 attempts', 'POST /auth/login', 401], ['Account temporarily locked', 'POST /auth/login', 423], ['No successful session observed', 'GET /auth/sessions', 200]] },
    { id: 'S02', title: 'Account compromise', thai: 'เข้าถึงบัญชีและข้อมูลสำคัญ', description: 'เชื่อมโยงการล็อกอินผิด การเข้าถึงสำเร็จ และการอ่านข้อมูลการเงิน', category: 'IDENTITY', level: 'Intermediate', asset: 'AUTH-01', user: 'finance.user', ip: '198.51.100.20', severity: 'High', detector: 'Rule', truth: 'True Positive', impact: 'พบ session ใหม่และการอ่านข้อมูลการเงินสำเร็จ เจ้าของบัญชีปฏิเสธกิจกรรม', unknown: 'ยังไม่ทราบว่าข้อมูลถูกนำไปใช้ต่อหรือไม่ และมีบัญชีอื่นได้รับผลกระทบหรือไม่', steps: [['Authentication failed', 'POST /auth/login', 401], ['Repeated authentication failures · 12 attempts', 'POST /auth/login', 401], ['New session created · SES-041', 'POST /auth/login', 200], ['Finance records accessed · 240 records', 'GET /api/finance/export', 200], ['Account owner denies activity', 'GET /support/verification/041', 200]] },
    { id: 'S03', title: 'Blocked web request', thai: 'คำขอโจมตีเว็บถูกปฏิเสธ', description: 'ตรวจหลักฐาน request และ response โดยไม่ตีความการโจมตีว่าประสบผลสำเร็จ', category: 'APPLICATION', level: 'Beginner', asset: 'WEB-01', user: 'anonymous', ip: '203.0.113.30', severity: 'Low', detector: 'Rule', truth: 'True Positive', impact: 'คำขอที่มีรูปแบบน่าสงสัยถูกปฏิเสธ ไม่มีหลักฐานว่าอ่านข้อมูลได้สำเร็จ', unknown: 'ต้องตรวจสอบเส้นทางอื่นและ log ของแอปพลิเคชันก่อนสรุปขอบเขต', steps: [['Web request received', 'GET /catalog?q=[suspicious-input]', 403], ['Request rejected by policy', 'GET /catalog?q=[suspicious-input]', 403], ['Application access denied', 'GET /admin/config', 403], ['Service health remains normal', 'GET /health', 200]] },
    { id: 'S04', title: 'Authorized security scan', thai: 'การสแกนที่ได้รับอนุญาต', description: 'ตรวจ change ticket และขอบเขตที่อนุญาตก่อนตัดสินใจกับการแจ้งเตือน', category: 'NETWORK', level: 'Intermediate', asset: 'WEB-01', user: 'scanner.service', ip: '192.0.2.10', severity: 'Medium', detector: 'Rule', truth: 'Benign Positive', impact: 'พบคำขอจำนวนมาก บริการยังทำงานปกติ และมี change ticket ที่ตรงขอบเขต', unknown: 'ต้องยืนยันว่าเวลา แหล่งที่มา และเป้าหมายตรงกับ CHG-204 ทุกเงื่อนไข', steps: [['Elevated request volume observed', 'GET /catalog', 200], ['Multiple endpoints requested · 90/min', 'GET /api/products', 404], ['Scanner inventory matched', 'GET /inventory/scanner-01', 200], ['CHG-204: source, target and time approved', 'GET /changes/CHG-204', 200]] },
    { id: 'S05', title: 'Beyond the rulebook', thai: 'พฤติกรรมนอกขอบเขตกฎ', description: 'สืบสวนการเข้าถึงที่ผิดจาก baseline โดยยังไม่มีกฎตรวจจับเฉพาะ', category: 'ANOMALY', level: 'Advanced', asset: 'FILE-01', user: 'ops.user', ip: '192.0.2.45', severity: 'High', detector: 'Anomaly', truth: 'True Positive', impact: 'พบปริมาณการอ่านไฟล์ 8 เท่าของ baseline และหลักฐานยืนยันว่าไม่ได้รับอนุญาต', unknown: 'ยังไม่ทราบช่องทางที่ผู้กระทำได้ session มา ต้องตรวจสอบต้นทางเพิ่มเติม', steps: [['Off-hours session observed', 'POST /auth/session', 200], ['File reads exceed baseline · 8×', 'GET /files/reports', 200], ['Unusual asset sequence correlated', 'GET /files/finance', 200], ['Session owner denies access', 'GET /support/verification/087', 200]] }
  ];
  const clone = value => JSON.parse(JSON.stringify(value));
  const getScenario = id => scenarios.find(s => s.id === id);
  function makeRun(ids, demo = false) {
    return { id: demo ? 'DEMO-024' : 'RUN-' + Date.now().toString(36).toUpperCase(), scenarioIds: [...ids], state: demo ? 'Completed' : 'Running', elapsed: demo ? 75 : 0, duration: 75, events: [], alerts: [], tickets: [], audit: [], ai: 'ready', demo, version: 1, lastClockAt: Date.now(), startedAt: new Date().toISOString() };
  }
  function audit(run, actor, action, entity, reason) { run.audit.unshift({ id: 'AUD-' + (run.audit.length + 1), time: run.elapsed, actor, action, entity, reason }); }
  function release(run) {
    for (const id of run.scenarioIds) {
      const s = getScenario(id);
      s.steps.forEach((step, i) => {
        const at = 5 + i * 12 + run.scenarioIds.indexOf(id) * 2;
        const eventId = id + '-EV-' + String(i + 1).padStart(3, '0');
        if (at > run.elapsed || run.events.some(e => e.id === eventId)) return;
        run.events.push({ id: eventId, scenarioId: id, time: at, source: s.category === 'IDENTITY' ? 'Auth gateway' : s.category === 'ANOMALY' ? 'File audit' : 'Web gateway', asset: s.asset, user: s.user, ip: s.ip, message: step[0], request: step[1], response: step[2] });
        if (i === 1) {
          const alert = { id: 'ALT-' + id.slice(1), scenarioId: id, title: s.title, detector: s.detector, severity: s.id === 'S02' ? 'Medium' : s.severity, time: at };
          run.alerts.push(alert);
          run.tickets.push({ id: 'TKT-' + (1040 + Number(id.slice(1))), scenarioId: id, title: s.title, severity: alert.severity, status: 'Open', disposition: '', reason: '', notes: [], assessments: [], version: 1, deleted: false, created: at, evidenceIds: run.events.filter(e => e.scenarioId === id).map(e => e.id) });
          audit(run, 'Detection engine', 'Ticket created', alert.id, s.detector + ' detection · fixture v1');
        }
        const ticket = run.tickets.find(t => t.scenarioId === id);
        if (ticket) {
          if (!ticket.evidenceIds.includes(eventId)) { ticket.evidenceIds.push(eventId); ticket.version = (ticket.version || 1) + 1; }
          if (id === 'S02' && i === 3 && !ticket.humanSeverity) ticket.severity = 'High';
        }
      });
    }
    run.events.sort((a, b) => a.time - b.time);
    return run;
  }
  function tick(run, seconds = 1) {
    if (run.state !== 'Running') return run;
    run.elapsed = Math.min(run.duration, run.elapsed + seconds);
    release(run);
    if (run.elapsed >= run.duration) { run.state = 'Reviewing'; run.version = (run.version || 1) + 1; }
    return run;
  }
  function demoRun() { const run = makeRun(scenarios.map(s => s.id), true); release(run); return run; }
  function analysis(run, ticket) {
    const s = getScenario(ticket.scenarioId);
    const evidence = run.events.filter(e => ticket.evidenceIds.includes(e.id));
    if (!s) return { summary: 'เคสที่สร้างโดยนักวิเคราะห์ โปรดตรวจสอบหลักฐานที่เลือกและบันทึกข้อสรุป', impact: 'ยังไม่มีผลวิเคราะห์สำหรับเคสที่สร้างเอง', unknown: 'ต้องตรวจสอบบริบทและขอบเขตเพิ่มเติม', confidence: 'ยังไม่ประเมิน', evidence };
    const complete = evidence.length >= s.steps.length;
    return { summary: complete ? s.impact : 'พบ ' + evidence.length + ' เหตุการณ์ที่เชื่อมโยงกับ ' + s.user + ' จาก ' + s.ip + ' ต้องรอและตรวจสอบหลักฐานเพิ่มเติมก่อนยืนยันผลกระทบ', impact: complete ? s.impact : 'ยังไม่ยืนยันขอบเขตผลกระทบจากหลักฐานที่มี', unknown: complete ? s.unknown : 'ยังไม่มีข้อมูลครบทั้งช่วงเวลา ตรวจสอบ event ที่ปล่อยแล้วและติดตามเหตุการณ์ถัดไป', confidence: complete ? 'สูง · มีหลักฐานหลายแหล่งใน fixture' : 'ปานกลาง · หลักฐานยังไม่ครบ', evidence };
  }
  const statuses = ['Open', 'Investigating', 'Resolved', 'Closed'];
  const dispositions = ['True Positive', 'Benign Positive', 'False Positive', 'Undetermined'];
  const mutableStates = ['Created', 'Running', 'Paused', 'Reviewing'];
  function isMutable(run) { return !run.demo && mutableStates.includes(run.state); }
  function assertMutable(run) { if (!isMutable(run)) throw Error('RUN_READ_ONLY: รอบนี้อ่านอย่างเดียว เริ่มรอบใหม่เพื่อฝึกต่อ'); }
  function assertVersion(resource, expected) { if (Number(expected) !== (resource.version || 1)) throw Error('VERSION_CONFLICT: ข้อมูลเปลี่ยนแล้ว กรุณาอัปเดตหลักฐานก่อนบันทึกอีกครั้ง ข้อความที่กรอกยังอยู่'); }
  function syncClock(run, now = Date.now()) {
    if (run.state === 'Completing' && now >= run.completeAt) { run.state = 'Completed'; run.version++; run.completedAt = new Date(now).toISOString(); }
    if (run.state !== 'Running') return run;
    if (!Number.isFinite(run.lastClockAt)) run.lastClockAt = now;
    const delta = Math.max(0, Math.floor((now - run.lastClockAt) / 1000));
    if (delta) { tick(run, delta); run.lastClockAt += delta * 1000; }
    return run;
  }
  function pauseRun(run, now = Date.now()) { assertMutable(run); syncClock(run, now); if (run.state !== 'Running') throw Error('INVALID_TRANSITION: พักได้เฉพาะรอบที่กำลังทำงาน'); run.state = 'Paused'; run.version++; }
  function resumeRun(run, allRuns, now = Date.now()) { assertMutable(run); if (run.state !== 'Paused') throw Error('INVALID_TRANSITION'); if (allRuns.some(r => r.id !== run.id && r.owner === run.owner && r.state === 'Running')) throw Error('มีรอบกำลังทำงานอยู่แล้ว กรุณาพักหรือจบรอบนั้นก่อน'); run.state = 'Running'; run.lastClockAt = now; run.version++; }
  function finishRun(run, now = Date.now()) {
    if (['Completing', 'Completed'].includes(run.state)) return run;
    assertMutable(run); syncClock(run, now);
    run.evaluationSnapshot = computeEvaluation(run);
    run.evaluationSnapshot.assessment_cutoff = new Date(now).toISOString();
    run.evaluationSnapshot.release_cutoff = run.events.length;
    run.evaluationSnapshot.truncated = run.elapsed < run.duration;
    run.state = 'Completing'; run.completeAt = now + 1500; run.version++;
    return run;
  }
  function dailyRunCount(runs, owner, now = new Date()) { const day = now.toISOString().slice(0, 10); return runs.filter(r => r.owner === owner && r.startedAt?.slice(0, 10) === day).length; }
  function eventDate(run, e) { return new Date(new Date(run.startedAt).getTime() + e.time * 1000).toISOString(); }
  function filterEvents(run, query = {}) {
    for (const key of ['from', 'to']) if (query[key] && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/.test(query[key])) throw Error('ช่วงเวลาไม่ถูกต้อง: ใช้ ISO UTC เช่น 2026-10-12T10:00:00Z');
    if ((query.q || '').length > 200) throw Error('คำค้นหายาวเกิน 200 ตัวอักษร');
    const from = query.from ? Date.parse(query.from) : -Infinity;
    const to = query.to ? Date.parse(query.to) : Infinity;
    if (Number.isNaN(from) || Number.isNaN(to) || from >= to) throw Error('ช่วงเวลาไม่ถูกต้อง: ใช้ ISO UTC และ from ต้องน้อยกว่า to');
    return run.events.filter(e => {
      const at = Date.parse(eventDate(run, e));
      return at >= from && at < to && (!query.source || query.source === 'All' || e.source === query.source) && (!query.asset || e.asset === query.asset) && (!query.user || e.user.toLowerCase().includes(query.user.toLowerCase())) && (!query.ip || e.ip === query.ip) && `${JSON.stringify(e)} ${eventDate(run, e)}`.toLowerCase().includes((query.q || '').toLowerCase());
    });
  }
  function updateTicket(run, id, changes, actor, instructor = false) {
    assertMutable(run);
    const t = run.tickets.find(t => t.id === id);
    if (!t || t.deleted) throw Error('ไม่พบ ticket ที่แก้ไขได้');
    assertVersion(t, changes.expected_version);
    if (!changes.title?.trim() || changes.title.length > 120) throw Error('ระบุชื่อ ticket ความยาว 1–120 ตัวอักษร');
    if (!['Low', 'Medium', 'High', 'Critical'].includes(changes.severity)) throw Error('Severity ไม่ถูกต้อง');
    if (!statuses.includes(changes.status)) throw Error('สถานะไม่ถูกต้อง');
    const next = { Open: ['Open', 'Investigating'], Investigating: ['Investigating', 'Resolved'], Resolved: ['Resolved', 'Closed', 'Investigating'], Closed: ['Closed', 'Investigating'] };
    if (!next[t.status].includes(changes.status)) throw Error('เปลี่ยนสถานะตามลำดับ Open → Investigating → Resolved → Closed');
    if (!changes.reason?.trim() || changes.reason.length > 2000) throw Error('ระบุเหตุผลการเปลี่ยนแปลง 1–2,000 ตัวอักษร');
    if (changes.disposition && !dispositions.includes(changes.disposition)) throw Error('ข้อสรุปไม่ถูกต้อง');
    if (['Resolved', 'Closed'].includes(changes.status) && !changes.disposition) throw Error('ต้องเลือกข้อสรุปก่อน resolve หรือปิด ticket');
    const before = `${t.status} / ${t.severity} / ${t.disposition || 'Pending'}`;
    if (!instructor) {
      t.assessments ||= [];
      t.assessments.push({ disposition: changes.disposition || '', reason: changes.reason.trim(), author: actor, time: run.elapsed });
    }
    t.humanSeverity = true;
    Object.assign(t, { title: changes.title.trim(), severity: changes.severity, status: changes.status, disposition: changes.disposition || '', reason: instructor ? t.reason : changes.reason.trim(), version: (t.version || 1) + 1 });
    audit(run, actor, instructor ? 'Instructor ticket review' : 'Ticket updated', id, `${before} → ${t.status} / ${t.severity} / ${t.disposition || 'Pending'} · ${changes.reason.trim()}`);
    return t;
  }
  function computeEvaluation(run) {
    const rows = run.scenarioIds.map(id => {
      const s = getScenario(id);
      const t = run.tickets.find(t => t.scenarioId === id);
      return { id, title: s.title, truth: s.truth, answer: t?.disposition || 'Undetermined', correct: t?.disposition === s.truth, deleted: t?.deleted || false, detected: run.alerts.some(a => a.scenarioId === id), complete: run.events.filter(e => e.scenarioId === id).length === s.steps.length };
    });
    return { rows, correct: rows.filter(r => r.correct).length, pending: rows.filter(r => r.answer === 'Undetermined').length, total: rows.length };
  }
  function evaluate(run) { if (run.state !== 'Completed') throw Error('EVALUATION_LOCKED: จบรอบก่อนดูผล'); return clone(run.evaluationSnapshot || computeEvaluation(run)); }
  const api = { scenarios, clone, getScenario, makeRun, release, tick, demoRun, analysis, updateTicket, audit, evaluate, statuses, dispositions, isMutable, assertMutable, assertVersion, syncClock, pauseRun, resumeRun, finishRun, dailyRunCount, eventDate, filterEvents };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.SOC = api;
})(typeof window !== 'undefined' ? window : globalThis);
