const { test } = require('node:test');
const assert = require('node:assert/strict');
const M = require('../model.js');

test('a fresh run exposes no future events or tickets', () => {
  const r = M.makeRun(['S02']);
  M.tick(r, 4);
  assert.equal(r.events.length, 0);
  assert.equal(r.tickets.length, 0);
  M.tick(r, 1);
  assert.equal(r.events.length, 1);
  assert.equal(r.tickets.length, 0);
});

test('exam run keeps detector titles neutral while preserving evidence', () => {
  const r = M.makeRun(['S04']);
  r.mode = 'exam';
  M.tick(r, 75);
  assert.equal(r.alerts[0].title, 'Unclassified activity');
  assert.equal(r.tickets[0].title, 'Unclassified activity');
  assert.equal(r.alerts[0].severity, 'Unrated');
  assert.equal(r.tickets[0].severity, 'Unrated');
  assert.equal(r.events.length, M.getScenario('S04').steps.length);
});

test('pause freezes simulation and releasing repeatedly never duplicates evidence', () => {
  const r = M.makeRun(['S02']);
  M.tick(r, 17);
  r.state = 'Paused';
  M.tick(r, 100);
  assert.equal(r.elapsed, 17);
  assert.equal(r.events.length, 2);
  M.release(r); M.release(r);
  assert.equal(r.tickets.length, 1);
  assert.equal(r.alerts.length, 1);
  assert.equal(new Set(r.tickets[0].evidenceIds).size, 2);
});

test('analysis cannot claim future successful access from initial login failures', () => {
  const r = M.makeRun(['S02']);
  M.tick(r, 17);
  const a = M.analysis(r, r.tickets[0]);
  assert.equal(a.evidence.length, 2);
  assert.match(a.impact, /ยังไม่ยืนยัน/);
  assert.doesNotMatch(a.summary, /เจ้าของบัญชีปฏิเสธ/);
  M.tick(r, 36);
  assert.equal(r.tickets.length, 1);
  assert.equal(M.analysis(r, r.tickets[0]).evidence.length, 5);
  assert.match(M.analysis(r, r.tickets[0]).summary, /เจ้าของบัญชีปฏิเสธ/);
});

test('all five scenarios generate one correlated ticket each, and stop in Review', () => {
  const r = M.makeRun(M.scenarios.map(s => s.id));
  M.tick(r, 999);
  assert.equal(r.elapsed, 75);
  assert.equal(r.state, 'Reviewing');
  assert.equal(r.events.length, 21);
  assert.equal(r.alerts.length, 5);
  assert.equal(r.tickets.length, 5);
  for (const t of r.tickets) {
    assert.equal(new Set(t.evidenceIds).size, t.evidenceIds.length);
    assert.ok(t.evidenceIds.every(id => r.events.some(e => e.id === id && e.scenarioId === t.scenarioId)));
  }
});

test('invalid transitions and missing closing assessments are rejected without mutation', () => {
  const r = M.makeRun(M.scenarios.map(s => s.id)); M.tick(r, 75); const t = r.tickets[0];
  const changes = { title: t.title, severity: t.severity, status: 'Closed', reason: 'ตรวจหลักฐานครบแล้ว', disposition: 'True Positive' };
  assert.throws(() => M.updateTicket(r, t.id, { ...changes, expected_version: t.version }, 'analyst'), /ตามลำดับ/);
  assert.equal(t.status, 'Open');
  M.updateTicket(r, t.id, { ...changes, expected_version: t.version, status: 'Investigating' }, 'analyst');
  assert.throws(() => M.updateTicket(r, t.id, { ...changes, expected_version: t.version, status: 'Resolved', disposition: '' }, 'analyst'), /เลือกข้อสรุป/);
  assert.throws(() => M.updateTicket(r, t.id, { ...changes, expected_version: t.version, status: 'Resolved', reason: ' ' }, 'analyst'), /เหตุผล/);
  M.updateTicket(r, t.id, { ...changes, expected_version: t.version, status: 'Resolved' }, 'analyst');
  M.updateTicket(r, t.id, { ...changes, expected_version: t.version }, 'analyst');
  assert.equal(t.status, 'Closed');
  M.updateTicket(r, t.id, { ...changes, expected_version: t.version, status: 'Investigating', reason: 'พบหลักฐานใหม่' }, 'analyst');
  assert.equal(t.status, 'Investigating');
  assert.match(r.audit[0].reason, /พบหลักฐานใหม่/);
});

test('soft deletion does not improve results by removing unresolved scenarios', () => {
  const r = M.demoRun();
  r.tickets[0].deleted = true;
  r.tickets[1].disposition = 'True Positive';
  const e = M.evaluate(r);
  assert.equal(e.total, 5);
  assert.equal(e.correct, 1);
  assert.equal(e.pending, 4);
  assert.equal(e.rows[0].deleted, true);
  assert.throws(() => M.updateTicket(r, r.tickets[0].id, {}, 'analyst'), /RUN_READ_ONLY/);
});

test('run data is isolated and incomplete evidence remains explicit in evaluation', () => {
  const a = M.makeRun(['S02']); const b = M.makeRun(['S02']);
  M.tick(a, 17);
  a.tickets[0].disposition = 'Undetermined';
  a.state = 'Completed';
  assert.equal(b.events.length, 0);
  assert.equal(b.tickets.length, 0);
  assert.equal(M.evaluate(a).rows[0].complete, false);
  assert.equal(M.evaluate(a).pending, 1);
});

test('manual tickets get no invented automated analysis', () => {
  const r = M.demoRun();
  const a = M.analysis(r, { scenarioId: null, evidenceIds: [r.events[0].id] });
  assert.equal(a.confidence, 'ยังไม่ประเมิน');
  assert.equal(a.evidence.length, 1);
});

test('finish locks mutations immediately and evaluation is a stable snapshot', () => {
  const r = M.makeRun(['S02']); M.tick(r, 30); r.lastClockAt = 1000;
  r.tickets[0].disposition = 'Undetermined';
  M.finishRun(r, 1000);
  assert.equal(r.state, 'Completing');
  assert.throws(() => M.evaluate(r), /EVALUATION_LOCKED/);
  assert.throws(() => M.updateTicket(r, r.tickets[0].id, {}, 'analyst'), /RUN_READ_ONLY/);
  const count = r.events.length;
  M.syncClock(r, 2500);
  assert.equal(r.state, 'Completed');
  assert.equal(r.events.length, count);
  r.tickets[0].disposition = 'True Positive';
  assert.equal(M.evaluate(r).pending, 1);
  assert.equal(M.evaluate(r).truncated, true);
  const result = M.evaluate(r); result.rows[0].truth = 'altered';
  assert.notEqual(M.evaluate(r).rows[0].truth, 'altered');
});

test('clock catches up without login and paused time stays frozen', () => {
  const r = M.makeRun(['S02']); r.lastClockAt = 1000;
  M.syncClock(r, 18000); assert.equal(r.elapsed, 17);
  M.pauseRun(r, 18000); M.syncClock(r, 50000); assert.equal(r.elapsed, 17);
  M.resumeRun(r, [r], 50000); M.syncClock(r, 62000); assert.equal(r.elapsed, 29);
  assert.equal(r.events.length, 3);
});

test('resume refuses a second active run belonging to the same owner', () => {
  const a = M.makeRun(['S02']), b = M.makeRun(['S01']);
  a.id = 'a'; b.id = 'b'; a.owner = b.owner = 'analyst'; a.state = 'Paused';
  assert.throws(() => M.resumeRun(a, [a,b]), /มีรอบ/);
});

test('stale ticket version rejects the draft without changing assessment', () => {
  const r = M.makeRun(['S02']); M.tick(r, 17); const t = r.tickets[0]; const old = t.version;
  M.tick(r, 12);
  const change = { expected_version: old, title:t.title, severity:'Medium', status:'Investigating', reason:'investigating', disposition:'' };
  assert.throws(() => M.updateTicket(r,t.id,change,'analyst'), /VERSION_CONFLICT/);
  assert.equal(t.status,'Open');
  M.updateTicket(r,t.id,{...change,expected_version:t.version},'analyst');
  assert.equal(t.assessments.length,1);
});

test('instructor status review never overwrites a learner assessment', () => {
  const r = M.makeRun(['S02']); M.tick(r, 17); const t = r.tickets[0]; t.reason = 'learner reason';
  M.updateTicket(r,t.id,{expected_version:t.version,title:t.title,severity:'High',status:'Investigating',disposition:'',reason:'instructor review'},'instructor',true);
  assert.equal(t.reason,'learner reason'); assert.equal(t.assessments.length,0);
});

test('daily quota resets at UTC midnight and remains scoped to the account', () => {
  const runs = [{owner:'a',startedAt:'2026-10-11T23:59:59Z'},{owner:'a',startedAt:'2026-10-12T00:00:00Z'},{owner:'b',startedAt:'2026-10-12T00:00:01Z'}];
  assert.equal(M.dailyRunCount(runs,'a',new Date('2026-10-12T03:00:00Z')),1);
});

test('event filtering uses inclusive from and exclusive to with asset and user', () => {
  const r = M.demoRun(); r.startedAt='2026-10-12T00:00:00Z';
  const e = M.filterEvents(r,{from:'2026-10-12T00:00:05Z',to:'2026-10-12T00:00:17Z',asset:'AUTH-01',user:'finance',ip:'198.51.100.20'});
  assert.ok(e.length > 0); assert.ok(e.every(x=>x.time>=5 && x.time<17));
  assert.throws(()=>M.filterEvents(r,{from:'bad date'}),/ช่วงเวลา/);
  assert.throws(()=>M.filterEvents(r,{from:'2026-10-12T00:01:00Z',to:'2026-10-12T00:00:00Z'}),/ช่วงเวลา/);
});

test('learning path unlocks a level only after every case in the current level passes', () => {
  const owner = 'learner@demo.test';
  const runs = ['S01', 'S03', 'S04', 'S02', 'S05'].map(id => {
    const run = M.makeRun([id]); run.owner = owner; M.tick(run, 75);
    run.tickets[0].coachReviews = [{ passed: true }];
    return run;
  });
  assert.equal(M.learningProgress([], owner).unlockedIndex, 0);
  assert.equal(M.learningProgress(runs.slice(0, 1), owner).unlockedIndex, 0);
  assert.equal(M.learningProgress(runs.slice(0, 2), owner).unlockedIndex, 1);
  assert.equal(M.learningProgress(runs.slice(0, 4), owner).unlockedIndex, 2);
  assert.equal(M.learningProgress(runs, owner).completed, true);
  assert.equal(M.learningProgress(runs, 'another@demo.test').unlockedIndex, 0);
});

test('lesson review requires complete evidence, decisive reference, classification and reason', () => {
  const run = M.makeRun(['S01']); M.tick(run, 17);
  const ticket = run.tickets[0];
  ticket.disposition = 'True Positive'; ticket.reason = 'มีความพยายามเข้าสู่ระบบ แต่ยังไม่มี session ที่สำเร็จ';
  assert.equal(M.reviewLesson(run, ticket, 'S01-EV-004').passed, false);
  M.tick(run, 75);
  assert.equal(M.reviewLesson(run, ticket, 'S01-EV-001').passed, false);
  const review = M.reviewLesson(run, ticket, 'S01-EV-004');
  assert.equal(review.passed, true);
  assert.equal(review.mode, 'mock-rubric');
  ticket.disposition = 'False Positive';
  assert.equal(M.reviewLesson(run, ticket, 'S01-EV-004').passed, false);
});
