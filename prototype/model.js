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
    return { id: demo ? 'DEMO-024' : 'RUN-' + Date.now().toString(36).toUpperCase(), scenarioIds: [...ids], state: demo ? 'Completed' : 'Running', elapsed: demo ? 75 : 0, duration: 75, events: [], alerts: [], tickets: [], audit: [], ai: 'ready', demo, startedAt: new Date().toISOString() };
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
          run.tickets.push({ id: 'TKT-' + (1040 + Number(id.slice(1))), scenarioId: id, title: s.title, severity: alert.severity, status: 'Open', disposition: '', reason: '', notes: [], deleted: false, created: at, evidenceIds: run.events.filter(e => e.scenarioId === id).map(e => e.id) });
          audit(run, 'Detection engine', 'Ticket created', alert.id, s.detector + ' detection · fixture v1');
        }
        const ticket = run.tickets.find(t => t.scenarioId === id);
        if (ticket) {
          if (!ticket.evidenceIds.includes(eventId)) ticket.evidenceIds.push(eventId);
          if (id === 'S02' && i === 3 && !ticket.reason) ticket.severity = 'High';
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
    if (run.elapsed >= run.duration) run.state = 'Review';
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
  function updateTicket(run, id, changes, actor) {
    const t = run.tickets.find(t => t.id === id);
    if (!t || t.deleted) throw Error('ไม่พบ ticket ที่แก้ไขได้');
    if (!changes.title?.trim() || changes.title.length > 120) throw Error('ระบุชื่อ ticket ความยาว 1–120 ตัวอักษร');
    if (!['Low', 'Medium', 'High', 'Critical'].includes(changes.severity)) throw Error('Severity ไม่ถูกต้อง');
    if (!statuses.includes(changes.status)) throw Error('สถานะไม่ถูกต้อง');
    const next = { Open: ['Open', 'Investigating'], Investigating: ['Investigating', 'Resolved'], Resolved: ['Resolved', 'Closed', 'Investigating'], Closed: ['Closed', 'Investigating'] };
    if (!next[t.status].includes(changes.status)) throw Error('เปลี่ยนสถานะตามลำดับ Open → Investigating → Resolved → Closed');
    if (!changes.reason?.trim() || changes.reason.length > 2000) throw Error('ระบุเหตุผลการเปลี่ยนแปลง 1–2,000 ตัวอักษร');
    if (changes.disposition && !dispositions.includes(changes.disposition)) throw Error('ข้อสรุปไม่ถูกต้อง');
    if (['Resolved', 'Closed'].includes(changes.status) && !changes.disposition) throw Error('ต้องเลือกข้อสรุปก่อน resolve หรือปิด ticket');
    const before = `${t.status} / ${t.severity} / ${t.disposition || 'Pending'}`;
    Object.assign(t, { title: changes.title.trim(), severity: changes.severity, status: changes.status, disposition: changes.disposition || '', reason: changes.reason.trim() });
    audit(run, actor, 'Ticket updated', id, `${before} → ${t.status} / ${t.severity} / ${t.disposition || 'Pending'} · ${t.reason}`);
    return t;
  }
  function evaluate(run) {
    const rows = run.scenarioIds.map(id => {
      const s = getScenario(id);
      const t = run.tickets.find(t => t.scenarioId === id);
      return { id, title: s.title, truth: s.truth, answer: t?.disposition || 'Undetermined', correct: t?.disposition === s.truth, deleted: t?.deleted || false, detected: run.alerts.some(a => a.scenarioId === id), complete: run.events.filter(e => e.scenarioId === id).length === s.steps.length };
    });
    return { rows, correct: rows.filter(r => r.correct).length, pending: rows.filter(r => r.answer === 'Undetermined').length, total: rows.length };
  }
  const api = { scenarios, clone, getScenario, makeRun, release, tick, demoRun, analysis, updateTicket, audit, evaluate, statuses, dispositions };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.SOC = api;
})(typeof window !== 'undefined' ? window : globalThis);
