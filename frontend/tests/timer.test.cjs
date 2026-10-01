const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const dayjs = require('dayjs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/views/timesheet/Timer.vue'), 'utf8');
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '');

function timer(save = async () => 'WEEK') {
  const storage = new Map();
  const calls = [];
  const context = {
    ref: value => ({ value }), computed: getter => ({ get value() { return getter(); } }),
    inject: name => name === '$translate' ? text => text : name === '$employee' ? { data: { name: 'EMP', user_id: 'employee@example.test' } } : dayjs,
    onMounted() {}, onUnmounted() {}, console, Date,
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    setInterval: () => 1, clearInterval() {}, setTimeout: () => 1, clearTimeout() {},
    window: { confirm: () => true }, document: { title: 'HRMS', querySelector: () => null },
    STORAGE_KEY: 'timer', TIMER_NOTIFIED_KEY: 'notified',
    toast() {}, unreadNotificationsCount: { reload: async () => {} },
    call: async (method, args) => { calls.push(args); return save(args, calls.length); },
  };
  vm.createContext(context);
  vm.runInContext(script + '\nthis.state = { form, segments, startTime, isRunning, isPaused, isSaving, pickedProject, startProject, pause, saveProject, discardProject, timerProjects };', context);
  return { ...context.state, calls, storage };
}

function interval(project, from = '2026-10-01T10:00:00Z') {
  return { project, from, to: '2026-10-01T10:01:00Z', seconds: 60, description: project };
}

test('choosing another project does not reassign an active interval', () => {
  const t = timer();
  t.startProject('Alpha');
  t.pickedProject.value = 'Beta';
  assert.equal(t.form.value.project, 'Alpha');
  assert.equal(t.isRunning.value, true);
});

test('switching ends the old project interval and resets unrelated metadata', () => {
  const t = timer();
  t.startProject('Alpha');
  t.form.value.description = 'Alpha work';
  t.startTime.value = new Date(Date.now() - 5000).toISOString();
  t.startProject('Beta');
  assert.equal(t.segments.value.length, 1);
  assert.equal(t.segments.value[0].project, 'Alpha');
  assert.equal(t.form.value.project, 'Beta');
  assert.equal(t.form.value.description, '');
});

test('saving one project does not stop or save another running project', async () => {
  const t = timer();
  t.segments.value = [interval('Alpha')];
  t.startProject('Beta');
  const started = t.startTime.value;
  await t.saveProject('Alpha');
  assert.equal(t.calls.length, 1);
  assert.equal(t.calls[0].project, 'Alpha');
  assert.equal(t.isRunning.value, true);
  assert.equal(t.startTime.value, started);
});

test('partial failure preserves only unacknowledged intervals for retry', async () => {
  const t = timer(async (_, count) => { if (count === 2) throw new Error('Network'); return 'WEEK'; });
  t.segments.value = [interval('Alpha'), interval('Alpha', '2026-10-01T09:00:00Z')];
  await t.saveProject('Alpha');
  assert.equal(t.segments.value.length, 1);
  assert.equal(t.segments.value[0].from, '2026-10-01T09:00:00Z');
  assert.equal(JSON.parse(t.storage.get('timer')).segments.length, 1);
  await t.saveProject('Alpha');
  assert.equal(t.calls.length, 3);
  assert.equal(t.calls[2].from_time, dayjs('2026-10-01T09:00:00Z').format('YYYY-MM-DD HH:mm:ss'));
});

test('discard removes only the selected project', () => {
  const t = timer();
  t.segments.value = [interval('Alpha'), interval('Beta')];
  t.discardProject('Alpha');
  assert.equal(t.segments.value.length, 1);
  assert.equal(t.segments.value[0].project, 'Beta');
});
