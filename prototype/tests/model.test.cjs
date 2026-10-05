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
  assert.equal(r.state, 'Review');
  assert.equal(r.events.length, 21);
  assert.equal(r.alerts.length, 5);
  assert.equal(r.tickets.length, 5);
  for (const t of r.tickets) {
    assert.equal(new Set(t.evidenceIds).size, t.evidenceIds.length);
    assert.ok(t.evidenceIds.every(id => r.events.some(e => e.id === id && e.scenarioId === t.scenarioId)));
  }
});

test('invalid transitions and missing closing assessments are rejected without mutation', () => {
  const r = M.demoRun(); const t = r.tickets[0];
  const changes = { title: t.title, severity: t.severity, status: 'Closed', reason: 'ตรวจหลักฐานครบแล้ว', disposition: 'True Positive' };
  assert.throws(() => M.updateTicket(r, t.id, changes, 'analyst'), /ตามลำดับ/);
  assert.equal(t.status, 'Open');
  M.updateTicket(r, t.id, { ...changes, status: 'Investigating' }, 'analyst');
  assert.throws(() => M.updateTicket(r, t.id, { ...changes, status: 'Resolved', disposition: '' }, 'analyst'), /เลือกข้อสรุป/);
  assert.throws(() => M.updateTicket(r, t.id, { ...changes, status: 'Resolved', reason: ' ' }, 'analyst'), /เหตุผล/);
  M.updateTicket(r, t.id, { ...changes, status: 'Resolved' }, 'analyst');
  M.updateTicket(r, t.id, changes, 'analyst');
  assert.equal(t.status, 'Closed');
  M.updateTicket(r, t.id, { ...changes, status: 'Investigating', reason: 'พบหลักฐานใหม่' }, 'analyst');
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
  assert.throws(() => M.updateTicket(r, r.tickets[0].id, {}, 'analyst'), /ไม่พบ ticket/);
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
