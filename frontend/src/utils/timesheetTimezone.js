import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import { getViewerTimezone } from './timezone.js'

dayjs.extend(utc)
dayjs.extend(timezone)

export { getViewerTimezone }
export function timezoneOptions(...preferred) {
 let zones=[]
 try { zones=Intl.supportedValuesOf('timeZone') } catch {}
 return [...new Set([...preferred, 'UTC', ...zones].filter(Boolean))]
}
export function storedInstant(value, sourceZone) {
 if (!value) return null
 const text=String(value)
 return /(?:Z|[+-]\d{2}:?\d{2})$/.test(text) ? dayjs(text) : dayjs.tz(text, sourceZone)
}
export function displayedTime(value, sourceZone, viewerZone) {
 const instant=storedInstant(value,sourceZone)
 return instant?.isValid() ? instant.tz(viewerZone).format('YYYY-MM-DD HH:mm:ss') : ''
}
export function localEntryTimes(date, time, minutes, entryZone, sourceZone, original=null) {
 const wall=`${date} ${time}:00`
 const previous=original?.from_time ? storedInstant(original.from_time,sourceZone) : null
 const sameStart=previous?.tz(entryZone).format('YYYY-MM-DD HH:mm')===`${date} ${time}`
 if (sameStart && Number(minutes)===Math.round(Number(original.hours)*60)) {
  return {from_time:original.from_time,to_time:original.to_time}
 }
 const start=sameStart ? previous : dayjs.tz(wall,entryZone)
 if (!start.isValid() || start.tz(entryZone).format('YYYY-MM-DD HH:mm:ss')!==wall && !sameStart) {
  throw new Error('This local time does not exist because the clocks change. Choose another time.')
 }
 if (!sameStart) {
  // A repeated wall time needs an explicit choice; UTC gives an unambiguous input.
  for(let delta=-180;delta<=180;delta+=15) {
   if(delta && start.add(delta,'minute').tz(entryZone).format('YYYY-MM-DD HH:mm:ss')===wall) {
    throw new Error('This local time occurs twice because the clocks change. Select UTC to enter the exact time.')
   }
  }
 }
 const end=dayjs(start.valueOf()+Number(minutes)*60000)
 return {from_time:start.tz(sourceZone).format('YYYY-MM-DD HH:mm:ss'),to_time:end.tz(sourceZone).format('YYYY-MM-DD HH:mm:ss')}
}
export function localWeekBounds(weekStart, weekEnd, sourceZone, viewerZone) {
 const start=dayjs.tz(weekStart+' 00:00:00',sourceZone)
 const endDate=dayjs(weekEnd).add(1,'day').format('YYYY-MM-DD')
 const end=dayjs.tz(endDate+' 00:00:00',sourceZone)
 return {min:start.tz(viewerZone).format('YYYY-MM-DD'),max:end.subtract(1,'second').tz(viewerZone).format('YYYY-MM-DD')}
}
