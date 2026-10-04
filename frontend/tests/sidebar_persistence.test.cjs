const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm')
const { createRouter, createMemoryHistory } = require('vue-router')
const root = path.resolve(__dirname, '../src')
function routeDefinitions(file) {
  let source = fs.readFileSync(file, 'utf8'), context = {}
  for (const match of source.matchAll(/import (\w+) from "(\.\/[^\"]+)"/g)) {
    context[match[1]] = routeDefinitions(path.resolve(path.dirname(file), match[2] + '.js'))
  }
  source = source.replace(/^import .*$/gm, '')
  if (file.endsWith('/index.js')) source = source.split('const router = createRouter')[0] + '\nthis.result = routes'
  else source = source.replace(/export default /, 'this.result = ')
  context.TabbedView = {}
  vm.createContext(context); vm.runInContext(source, context)
  return context.result
}
const routes = routeDefinitions(path.join(root, 'router/index.js'))
const router = createRouter({ history: createMemoryHistory(), routes })
const route = { name: 'Home', meta: {} }
const script = fs.readFileSync(path.join(root, 'App.vue'), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const context = { useRoute: () => route, computed: get => ({ get value() { return get() } }), useDarkMode() {}, useTimerReminder() {}, onMounted() {} }
vm.createContext(context); vm.runInContext(script + '\nthis.visible = showSidebar', context)
function visible(name) {
  const target = router.resolve({ name, params: name === 'TimesheetDetailView' ? { id: 'synthetic' } : ['BookingPage', 'BookingShort'].includes(name) ? { slug: 'synthetic' } : {} })
  route.name = target.name; route.meta = target.meta
  return context.visible.value
}
test('every desktop sidebar destination retains navigation', () => {
  const sidebar = fs.readFileSync(path.join(root, 'components/DesktopSidebar.vue'), 'utf8')
  const names = [...sidebar.matchAll(/(?:route:\s*|name:\s*)["']([^"']+)["']/g)].map(match => match[1])
  assert.ok(names.includes('ProjectTimesheets'))
  for (const name of names) assert.equal(visible(name), true, name)
})
test('internal approvals and details retain navigation through route changes', () => {
  for (const name of ['Home', 'ProjectTimesheets', 'TimesheetProjectApprovals', 'HolidayApprovals', 'ScheduleApprovals', 'AdminLeaveRequests', 'AdminExpenseRequests', 'AdminTimesheets', 'TimesheetDetailView', 'Home']) {
    assert.equal(visible(name), true, name)
  }
})
test('login, recovery and public booking pages keep their independent layouts', () => {
  for (const name of ['Login', 'ForgotPassword', 'InvalidEmployee', 'BookingPage', 'BookingShort']) assert.equal(visible(name), false, name)
})
