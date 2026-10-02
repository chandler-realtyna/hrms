const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path')
const source = fs.readFileSync(path.join(__dirname, '../src/views/timesheet/ProjectReview.vue'), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1]
  .replace(/^import\s+[\s\S]*?\s+from\s+"[^"]+"\s*$/gm, '')
function queue(call) {
  const notices = []
  const ctx = { ref: value => ({ value }), reactive: value => value,
    computed: get => ({ get value() { return get() } }),
    inject: key => key === '$translate' ? x => x : null,
    useProjectLabels: () => ({ displayName: x => x, load() {} }),
    formatHours: x => x, serverTimeAgo: () => '', watch() {}, onUnmounted() {}, onIonViewWillEnter() {},
    call, toast: n => notices.push(n), setTimeout() {}, clearTimeout() {}, window: {},
  }
  vm.createContext(ctx)
  vm.runInContext(script + '\nthis.api={sections,orderedSections,load,loading,loadError,cursor,total};', ctx)
  return { ...ctx.api, notices }
}
test('team cards preserve server priority across pages, not newest modification', async () => {
  let count = 0
  const c = queue(async () => ++count === 1
    ? { rows: [{ timesheet: 'pending', modified: 'old' }], total: 2, next_cursor: 'v2' }
    : { rows: [{ timesheet: 'draft', modified: 'new' }], total: 2, next_cursor: null })
  await c.load(); await c.load(true)
  assert.deepEqual(Array.from(c.orderedSections.value, r => r.timesheet), ['pending', 'draft'])
})
test('old cursor replaces existing rows with first page and shows a notice', async () => {
  const calls = []
  const c = queue(async (_method, args) => {
    calls.push(args.cursor)
    if (args.cursor) throw { exc_type: 'TeamCursorResetRequired' }
    return { rows: [{ timesheet: 'restart' }], total: 1, next_cursor: null }
  })
  c.sections.value = [{ timesheet: 'old' }]; c.cursor.value = 'v1'
  await c.load(true)
  assert.deepEqual(calls, ['v1', null])
  assert.deepEqual(Array.from(c.sections.value, r => r.timesheet), ['restart'])
  assert.equal(c.notices.length, 1); assert.equal(c.loading.value, false)
})
test('a stale failing request cannot replace a newer successful response', async () => {
  let reject, calls = 0
  const c = queue(async () => ++calls === 1 ? new Promise((_resolve, fail) => { reject = fail })
    : { rows: [{ timesheet: 'fresh' }], total: 1, next_cursor: null })
  const old = c.load(); await c.load(); reject(new Error('stale failure')); await old
  assert.equal(c.loadError.value, ''); assert.equal(c.sections.value[0].timesheet, 'fresh')
})
test('overview has only project review, detail retains week status in both UIs', () => {
  const overview = source.slice(0, source.indexOf('<!-- Detail:'))
  assert.doesNotMatch(overview, /row\.hr_status/)
  assert.match(source, /__\("Week Status"\)/)
  const desk = fs.readFileSync(path.join(__dirname, '../../hrms/public/js/admin_reviews.js'), 'utf8')
  assert.match(desk, /"Activity Type", "Review Status", "Updated"/)
  assert.doesNotMatch(desk, /"Week status"/)
  assert.match(desk, /\["Week Status", data\.hr_status\]/)
})
