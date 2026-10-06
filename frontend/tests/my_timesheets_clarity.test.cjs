const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path')
const dayjs = require('dayjs')
const source = fs.readFileSync(path.join(__dirname, '../src/views/timesheet/List.vue'),'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm,'')
function page(call = async () => ({})) {
 const pushed = [], context = { computed: get => ({ get value() { return get() } }), ref: value => ({ value }),
 inject: key => key === '$dayjs' ? dayjs : text => text, useRouter: () => ({push: target => pushed.push(target)}),
 onMounted() {}, onIonViewWillEnter() {}, call, formatHours: value => value }
 vm.createContext(context); vm.runInContext(script+'\nthis.api={data,currentWeek,weekGroups,closedWeeks,currentWeekAction,openCurrentWeek,load,loadError,loading};',context)
 return {...context.api,pushed}
}
const week = (name,status,date='2026-09-27') => ({name,custom_weekly_status:status,start_date:date,end_date:date,docstatus:status==='Closed'?1:0,total_hours:3})
test('old unfinished weeks remain visible while only completed weeks move to history', () => {
 const p=page(); p.currentWeek.value={...week('CURRENT','Draft'),custom_week_start:'2026-10-04'}
 p.data.value.weekly=[week('CURRENT','Draft'),week('RETURNED','Correction Required','2026-08-02'),week('OLD-DRAFT','Draft','2026-07-05'),week('PENDING','Pending HR Review'),week('CLOSED','Closed')]
 assert.deepEqual(Array.from(p.weekGroups.value.flatMap(group=>group.docs.map(doc=>doc.name))),['RETURNED','OLD-DRAFT','PENDING'])
 assert.deepEqual(Array.from(p.closedWeeks.value.map(doc=>doc.name)),['CLOSED'])
})
test('current week action follows server status and opens the exact named week', () => {
 const p=page(); p.currentWeek.value={...week('CURRENT','Draft'),custom_week_start:'2026-10-04'}
 assert.equal(p.currentWeekAction.value,'Continue this week');p.openCurrentWeek()
 assert.equal(p.pushed[0].params.id,'CURRENT')
 p.currentWeek.value.custom_weekly_status='Pending HR Review'
 assert.equal(p.currentWeekAction.value,'View this week')
 p.currentWeek.value={name:null,custom_week_start:'2026-10-04',custom_weekly_status:'Draft'};p.openCurrentWeek()
 assert.equal(p.pushed[1].query.week_start,'2026-10-04')
})
test('loading gets server current-week bounds and refreshes totals on returning', async () => {
 let hours=1
 const p=page(async method=>method.endsWith('get_my_timesheets')?{weekly:[],legacy:[]}: {name:'CURRENT',custom_week_start:'2026-10-04',total_hours:hours})
 await p.load();assert.equal(p.currentWeek.value.total_hours,1)
 hours=4;await p.load();assert.equal(p.currentWeek.value.total_hours,4)
})
test('load failure is visible and retry succeeds', async () => {
 let fail=true
 const p=page(async method=>{if(fail)throw new Error('Offline');return method.endsWith('get_my_timesheets')?{weekly:[],legacy:[]}: {name:'CURRENT'}})
 await p.load();assert.equal(p.loadError.value,'Offline');assert.equal(p.loading.value,false)
 fail=false;await p.load();assert.equal(p.loadError.value,'');assert.equal(p.currentWeek.value.name,'CURRENT')
})
