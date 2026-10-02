const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { parse } = require('@vue/compiler-sfc');

function form(call) {
  const source = fs.readFileSync('src/views/timesheet/Form.vue', 'utf8');
  const script = parse(source).descriptor.scriptSetup.content.replace(/^import .*$/gm, '');
  const props = { id: 'SHEET' }, timers = [];
  const context = { ref: value => ({ value }), inject: () => text => text,
    defineProps: () => props, watch: () => {}, onIonViewWillEnter: () => {}, call,
    setTimeout: callback => { timers.push(callback); return timers.length; }, clearTimeout: () => {}, };
  vm.createContext(context);
  vm.runInContext(script + '\nthis.api={loadMode,mode,loadError};', context);
  return { ...context.api, props, timers };
}

test('mode permission failure becomes a retryable error, not endless loading', async () => {
  const page = form(async () => { throw { messages: ['Permission denied'] }; });
  await page.loadMode();
  assert.equal(page.mode.value, null);
  assert.equal(page.loadError.value, 'Permission denied');
});
test('retry loads the correct mode', async () => {
  const page = form(async () => ({ is_weekly: true }));
  await page.loadMode();
  assert.equal(page.mode.value, 'weekly');
  assert.equal(page.loadError.value, '');
});
test('a hung request times out with an error', async () => {
  const page = form(() => new Promise(() => {}));
  const request = page.loadMode();
  page.timers[0]();
  await request;
  assert.match(page.loadError.value, /retry/i);
});
test('a stale result cannot replace a different route', async () => {
  let resolve;
  const page = form(() => new Promise(done => { resolve = done; }));
  const first = page.loadMode();
  page.props.id = undefined;
  await page.loadMode();
  resolve({ is_weekly: false });
  await first;
  assert.equal(page.mode.value, 'weekly');
});
