const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path')
const script = fs.readFileSync(path.join(__dirname, '../src/views/timesheet/WeeklyForm.vue'), 'utf8')
  .match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
function form(call) {
  const storage = new Map(), watches = []
  const props = { id: 'TS-A' }, route = { query: {} }
  const ctx = { ref: value => ({ value }), computed: get => ({ get value() { return get() } }),
    inject: key => key === '$translate' ? x => x : null, defineProps: () => props,
    useRoute: () => route, useRouter: () => ({ replace: async () => {} }),
    useProjectLabels: () => ({ displayName: x => x, load() {} }), formatHours: x => x,
    watch: (get, fn) => watches.push(fn), onMounted() {}, onUnmounted() {}, onIonViewWillEnter() {}, onIonViewWillLeave() {},
    call, toast() {}, console, Promise, Date,
    setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
    document: { visibilityState: 'visible' }, window: { prompt: () => "Correct my entries", confirm: () => true, clearTimeout() {}, setTimeout: () => 1 },
    localStorage: { getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k) },
  }
  vm.createContext(ctx)
  vm.runInContext(script+'\nthis.api={timesheet,loading,loadError,conflict,hasUnsavedChanges,lastServerModified,load,queueAutosave,scheduleAutosave,routeChanging,enter,additiveDraft,reviewLatest,isReadOnly,withdrawWeek,canWithdraw,routeWatch:()=>'+
    '0};', ctx)
  return { ...ctx.api, props, route, storage, routeWatch: watches.at(-1) }
}
function doc(name = 'TS-A', modified = 'one') {
  return { name, employee: 'EMP', custom_week_start: '2026-09-27', custom_weekly_status: 'Draft', modified, time_logs: [], note: '' }
}
test('a refresh gets the latest server version without manual reload', async () => {
  let fresh = doc(), c = form(async () => fresh)
  await c.load(); fresh = doc('TS-A', 'two'); await c.load()
  assert.equal(c.timesheet.value.modified, 'two'); assert.equal(c.loading.value, false)
})
test('failed loading becomes a retryable error', async () => {
  let fail = true, c = form(async () => { if (fail) throw new Error('Permission denied'); return doc() })
  await c.load(); assert.equal(c.loading.value, false); assert.equal(c.loadError.value, 'Permission denied')
  fail = false; await c.load(); assert.equal(c.timesheet.value.name, 'TS-A'); assert.equal(c.loadError.value, '')
})
test('refresh preserves edits and exposes a version conflict', async () => {
  let fresh = doc(), c = form(async () => fresh)
  await c.load(); c.timesheet.value.note = 'My unsaved note'; c.hasUnsavedChanges.value = true
  fresh = doc('TS-A', 'two'); await c.load()
  assert.equal(c.timesheet.value.note, 'My unsaved note'); assert.equal(c.conflict.value, true)
  assert.ok(c.storage.get('hrms_weekly_draft_EMP_2026-09-27'))
})
test('optimistic save sends its base version and retains a rejected draft', async () => {
  let sent, c = form(async (method,args) => {
    if (method.endsWith('get_weekly_timesheet')) return doc()
    sent = args; throw { exc_type: 'TimestampMismatchError', messages: ['changed elsewhere'] }
  })
  await c.load(); c.timesheet.value.note = 'Keep me'; c.hasUnsavedChanges.value = true
  await assert.rejects(c.queueAutosave())
  assert.equal(sent.expected_modified, 'one'); assert.equal(c.conflict.value, true)
  assert.equal(c.hasUnsavedChanges.value, true)
})
test('changing weeks preserves the old draft without carrying it into the new week', async () => {
  const c = form(async (_method,args) => doc(args.name, args.name === 'TS-B' ? 'new' : 'one'))
  c.enter(); await new Promise(resolve => setImmediate(resolve))
  c.timesheet.value.note = 'Old week draft'; c.hasUnsavedChanges.value = true
  c.props.id = 'TS-B'; c.routeWatch(); await new Promise(resolve => setImmediate(resolve))
  assert.equal(c.timesheet.value.name, 'TS-B'); assert.equal(c.timesheet.value.note, '')
  assert.equal(JSON.parse(c.storage.get('hrms_weekly_draft_EMP_2026-09-27')).payload.note, 'Old week draft')
})

function entry(name = 'ROW-1') {
  return { name, project: 'P', activity_type: 'Support', description: 'Task',
    from_time: '2026-09-28 09:30:00', to_time: '2026-09-28 09:42:00', hours: 0.2, is_billable: 0 }
}
test('legacy additive draft restores with current token and saves without losing entries', async () => {
  const fresh = { ...doc(), time_logs: [entry()] }
  let sent
  const c = form(async (method, args) => {
    if (method.endsWith('get_weekly_timesheet')) return fresh
    sent = args
    return { ...JSON.parse(args.payload), modified: 'two' }
  })
  const legacy = { ...fresh, modified: undefined, time_logs: [entry(), entry(undefined)] }
  delete legacy.time_logs[1].name
  c.storage.set('hrms_weekly_draft_EMP_2026-09-27', JSON.stringify({ baseModified: '', payload: legacy }))
  await c.load()
  assert.equal(c.conflict.value, false)
  assert.equal(c.timesheet.value.time_logs.length, 2)
  await c.queueAutosave()
  assert.equal(sent.expected_modified, 'one')
  assert.equal(c.timesheet.value.modified, 'two')
  assert.equal(c.storage.size, 0)
})
test('already saved legacy draft does not lock editing', async () => {
  const fresh = { ...doc(), time_logs: [entry()] }, c = form(async () => fresh)
  c.storage.set('hrms_weekly_draft_EMP_2026-09-27', JSON.stringify({ baseModified: '', payload: fresh }))
  await c.load()
  assert.equal(c.conflict.value, false)
  assert.equal(c.isReadOnly.value, false)
  assert.equal(c.hasUnsavedChanges.value, false)
  assert.equal(c.storage.size, 0)
})
test('changed, deleted, duplicate and unknown persisted rows still require review', () => {
  const c = form(async () => doc()), fresh = { ...doc(), time_logs: [entry()] }
  const drafts = [
    { ...fresh, note: 'changed' },
    { ...fresh, time_logs: [] },
    { ...fresh, time_logs: [{ ...entry(), description: 'changed' }] },
    { ...fresh, time_logs: [entry(), entry()] },
    { ...fresh, time_logs: [entry(), entry('deleted-on-server')] },
  ]
  for (const draft of drafts) assert.equal(c.additiveDraft(draft, fresh), null)
})
test('refresh started before our own successful save cannot produce a false conflict', async () => {
  let resolveRefresh, fetches = 0
  const c = form(async (method, args) => {
    if (method.endsWith('get_weekly_timesheet')) {
      if (++fetches === 1) return doc()
      return new Promise(resolve => { resolveRefresh = resolve })
    }
    return { ...JSON.parse(args.payload), modified: 'two' }
  })
  await c.load()
  const refresh = c.load()
  c.timesheet.value.note = 'New note'
  c.scheduleAutosave()
  await c.queueAutosave()
  resolveRefresh(doc())
  await refresh
  assert.equal(c.timesheet.value.modified, 'two')
  assert.equal(c.timesheet.value.note, 'New note')
  assert.equal(c.conflict.value, false)
})

test('withdrawing a pending submission keeps entries and advances the save version', async () => {
  const pending = { ...doc(), custom_weekly_status: 'Pending Project Approval', docstatus: 0, time_logs: [entry()] }
  let sent
  const c = form(async (method,args) => {
    if (method.endsWith('get_weekly_timesheet')) return pending
    sent=args
    return { ...pending, custom_weekly_status: 'Draft', modified: 'reopened' }
  })
  await c.load(); assert.equal(c.canWithdraw.value,true)
  await c.withdrawWeek()
  assert.equal(sent.name,'TS-A');assert.equal(sent.expected_modified,'one')
  assert.equal(c.isReadOnly.value,false);assert.equal(c.lastServerModified.value,'reopened')
  assert.equal(c.timesheet.value.time_logs.length,1);assert.equal(c.hasUnsavedChanges.value,false)
})
test('closed weeks and conflicting drafts cannot withdraw a submission', async () => {
  let count=0
  const c=form(async ()=>{count++;return {...doc(),custom_weekly_status:'Closed',docstatus:1}})
  await c.load();await c.withdrawWeek();assert.equal(count,1)
  c.timesheet.value.custom_weekly_status='Pending HR Review';c.timesheet.value.docstatus=0;c.conflict.value=true
  await c.withdrawWeek();assert.equal(count,1)
})
