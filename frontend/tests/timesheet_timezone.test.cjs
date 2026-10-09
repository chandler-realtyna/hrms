const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path')
const dayjs=require('dayjs'),utc=require('dayjs/plugin/utc'),timezone=require('dayjs/plugin/timezone')
const ctx={dayjs,utc,timezone,Intl,getViewerTimezone:()=> 'Asia/Yerevan'}
vm.createContext(ctx)
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/utils/timesheetTimezone.js'),'utf8').replace(/^import .*$/gm,'').replace(/^export \{.*\}\s*$/gm,'').replace(/export function/g,'function')+'\nthis.api={displayedTime,localEntryTimes,localWeekBounds};',ctx)
const {displayedTime,localEntryTimes,localWeekBounds}=ctx.api
const plain=x=>JSON.parse(JSON.stringify(x))
test('today timer hours display in Yerevan and a different chosen timezone',()=>{
 assert.equal(displayedTime('2026-10-06 00:03:28','EST','Asia/Yerevan'),'2026-10-06 09:03:28')
 assert.equal(displayedTime('2026-10-06 03:13:43','EST','Asia/Yerevan'),'2026-10-06 12:13:43')
 assert.equal(displayedTime('2026-10-06 03:13:43','EST','UTC'),'2026-10-06 08:13:43')
})
test('display date crosses midnight in both directions',()=>{
 assert.equal(displayedTime('2026-10-06 20:00:00','EST','Asia/Yerevan'),'2026-10-07 05:00:00')
 assert.equal(displayedTime('2026-10-06 01:00:00','EST','America/Los_Angeles'),'2026-10-05 23:00:00')
})
test('manual local entry converts back to storage, keeping elapsed duration',()=>{
 assert.deepEqual(plain(localEntryTimes('2026-10-06','09:00',60,'Asia/Yerevan','EST')),{from_time:'2026-10-06 00:00:00',to_time:'2026-10-06 01:00:00'})
 assert.deepEqual(plain(localEntryTimes('2026-10-07','01:00',60,'Asia/Yerevan','EST')),{from_time:'2026-10-06 16:00:00',to_time:'2026-10-06 17:00:00'})
})
test('metadata-only edits preserve the exact timer timestamps including seconds',()=>{
 const row={from_time:'2026-10-06 00:03:28',to_time:'2026-10-06 01:07:02',hours:1.059444}
 assert.deepEqual(plain(localEntryTimes('2026-10-06','09:03',64,'Asia/Yerevan','EST',row)),{from_time:row.from_time,to_time:row.to_time})
})
test('clock changes: nonexistent and ambiguous local inputs are rejected; valid elapsed intervals convert correctly',()=>{
 assert.throws(()=>localEntryTimes('2026-03-08','02:30',60,'America/New_York','EST'),/does not exist/)
 assert.throws(()=>localEntryTimes('2026-11-01','01:30',60,'America/New_York','EST'),/occurs twice/)
 assert.deepEqual(plain(localEntryTimes('2026-03-08','01:30',60,'America/New_York','EST')),{from_time:'2026-03-08 01:30:00',to_time:'2026-03-08 02:30:00'})
})
test('date inputs cover the local dates of the whole accounting week',()=>{
 assert.deepEqual(plain(localWeekBounds('2026-10-04','2026-10-10','EST','Asia/Yerevan')),{min:'2026-10-04',max:'2026-10-11'})
})
