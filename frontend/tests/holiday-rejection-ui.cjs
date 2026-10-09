const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict'), path = require('path')
const { test } = require('node:test')
const root = path.resolve(__dirname, '..')
const Vue = require(root + '/node_modules/vue')
const dayjs = require(root + '/node_modules/dayjs')
const { renderToString } = require(root + '/node_modules/@vue/server-renderer')
const { parse, compileScript } = require(root + '/node_modules/@vue/compiler-sfc')
const { descriptor } = parse(fs.readFileSync(root + '/src/views/holidays/MyHolidays.vue', 'utf8'))
const source = compileScript(descriptor, { id: 'HolidayQA', inlineTemplate: true, genDefaultAs: 'Holiday' }).content
 .replace(/^import\s+([\s\S]*?)\s+from\s+["']([^"']+)["']\s*$/gm, (_, names, mod) => mod === 'vue' ? `const ${names.replace(/\bas\b/g, ':')}=Vue` : '')
 .replace('return (_ctx, _cache) => {', 'holidayRecord.onSuccess(window.fixture);window.page={submission,selectedDates,isEditable,toggleDate,primaryAction};return (_ctx, _cache) => {')
 + ';globalThis.Holiday=Holiday;'
async function page(status) {
 const fixture = { name: 'Rejected-history', status, holidays: [{date: '2026-10-12'}] }
 const calls = [], enter = []
 const stub = { setup(p, {slots}) { return () => Vue.h('div', {}, slots.default?.()) } }
 const ctx = { Vue, window: {fixture}, IonPage:stub, IonHeader:stub, IonToolbar:stub, IonTitle:stub, IonButtons:stub, IonBackButton:stub, IonContent:stub, IonSpinner:stub, FeatherIcon:stub,
  onIonViewWillEnter: fn => enter.push(fn), toastController: {create: async () => ({present: async () => {}})},
  createResource: options => ({...options, loading:false, reload() {calls.push({reload:options.url})}, submit(args) {
   calls.push({url:options.url,args})
   options.onSuccess?.(options.url.endsWith('save_employee_holiday_draft')
    ? {name:'New-revision',status: status==='Approved' ? 'Approved' : 'Draft',holidays:JSON.parse(args.dates).map(date=>({date}))}
    : {name:args.name,status:'Submitted'})
  }}) }
 vm.createContext(ctx); vm.runInContext(source, ctx)
 const app = Vue.createSSRApp(ctx.Holiday); app.provide('$translate', s=>s); app.provide('$dayjs',dayjs)
 const html = await renderToString(app)
 return { ...ctx.window.page, html, calls, enter, fixture }
}
test('a rejected request exposes editable dates and submits a new request for HR review', async () => {
 const p = await page('Rejected')
 assert(p.html.includes('Submit revised request')); assert(!p.html.includes('Selected Holiday Dates'))
 assert.equal(p.isEditable.value,true)
 p.toggleDate('2026-10-12'); p.toggleDate('2026-10-13'); p.primaryAction()
 assert.equal(p.calls[0].url,'hrms.api.save_employee_holiday_draft')
 assert.equal(p.calls[0].args.dates,'["2026-10-13"]')
 assert.equal(p.calls[1].url,'hrms.api.submit_employee_holidays')
 assert.equal(p.calls[1].args.name,'New-revision')
 assert.equal(p.submission.value.status,'Submitted'); assert.equal(p.isEditable.value,false)
 assert.equal(p.fixture.status,'Rejected'); assert.equal(p.fixture.holidays[0].date,'2026-10-12')
})
test('pending HR approval remains locked and approved editing keeps its existing behavior', async () => {
 const pending = await page('Submitted')
 assert.equal(pending.isEditable.value,false); assert(!pending.html.includes('Submit revised request'))
 pending.toggleDate('2026-10-13'); assert.equal(pending.selectedDates.value.length,1)
 const approved = await page('Approved'); approved.primaryAction()
 assert(approved.html.includes('Save holiday changes'))
 assert.equal(approved.calls.length,1); assert.equal(approved.calls[0].url,'hrms.api.save_employee_holiday_draft')
})
test('returning to the cached page refreshes the current HR decision', async () => {
 const p = await page('Submitted'); assert.equal(p.enter.length,1); p.enter[0]()
 assert.equal(p.calls[0].reload,'hrms.api.get_employee_holiday_for_year')
})
