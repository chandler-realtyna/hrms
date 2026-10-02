const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm')
const source = fs.readFileSync(path.join(__dirname, '../../hrms/public/js/admin_reviews.js'), 'utf8')

class Element {
  constructor(html) { this.html = html; this.children = []; this.value = ''; this.handlers = {} }
  appendTo(parent) { parent.children.push(this); return this }
  text(value) { this.label = value; return this }
  val(value) { if (value === undefined) return this.value; this.value = value; return this }
  attr() { return this }
  addClass() { return this }
  removeClass() { return this }
  toggleClass() { return this }
  prop() { return this }
  on(event, action) { this.handlers[event] = action; return this }
  empty() { this.children = []; return this }
}
function setup() {
  const alerts = [], dialogs = [], confirmations = [], buttons = [], headings = []
  const ctx = { __: value => value, $: html => new Element(html), moment: () => ({ format: () => 'Week' }),
    frappe: { pages: { 'admin-reviews': {} }, show_alert: value => alerts.push(value),
      confirm: (message, action) => confirmations.push({ message, action }),
      ui: { Dialog: class {
        constructor() { this.fields_dict = { entries: { $wrapper: new Element('dialog') } }; dialogs.push(this) }
        show() { this.visible = true }
        hide() { this.visible = false }
      } },
    },
  }
  vm.createContext(ctx); vm.runInContext(source + '\nthis.Reviews = HRMSAdminReviews;', ctx)
  const review = Object.create(ctx.Reviews.prototype)
  review.content = new Element('content')
  review.table = (parent, labels) => { headings.push(labels); return new Element('tbody').appendTo(parent) }
  review.button = (parent, label, action) => {
    const button = new Element('button').text(label).appendTo(parent)
    buttons.push({ label, action }); return button
  }
  review.show = async () => { review.reloaded = true }
  return { review, alerts, dialogs, confirmations, buttons, headings }
}
function text(element) { return [element.label || '', ...element.children.map(text)].join(' ') }

test('week labels distinguish final approval from project approval and legacy submission', () => {
  const { review } = setup()
  const expected = { Draft: 'Not submitted', 'Pending Project Approval': 'Awaiting project review',
    'Pending HR Review': 'Awaiting HR approval', 'Correction Required': 'Needs correction',
    Closed: 'Finalized', Submitted: 'Legacy submitted' }
  for (const [state, label] of Object.entries(expected)) assert.equal(review.weekStatusLabel(state), label)
  assert.equal(review.statusLabel('Approved'), 'Approved')
  assert.notEqual(review.statusLabel('Approved'), review.weekStatusLabel('Closed'))
})

test('HR queue readiness labels and filter follow the server flag, not approval guesses', () => {
  const { review, headings } = setup()
  review.queue([
    { employee_name: 'Ready worker', ready_for_hr_close: true },
    { employee_name: 'Blocked worker', ready_for_hr_close: false },
  ], 'hr-timesheets')
  assert.equal(headings[0][3], 'Final approval')
  assert.match(text(review.content), /Ready to finalize/)
  assert.match(text(review.content), /Awaiting project review/)
  const toolbar = review.content.children[0], filter = toolbar.children[1]
  filter.val('ready'); filter.handlers.change()
  const body = review.content.children.at(-1)
  assert.match(text(body), /Ready worker/); assert.doesNotMatch(text(body), /Blocked worker/)
  filter.val('waiting'); filter.handlers.change()
  assert.match(text(body), /Blocked worker/); assert.doesNotMatch(text(body), /Ready worker/)
})

test('finalization confirms the lock and only reports success after server acceptance', async () => {
  const { review, buttons, confirmations, dialogs, alerts } = setup()
  const calls = []
  review.call = async (method, args) => {
    calls.push([method, args])
    return { name: 'QA-week', employee_name: 'Synthetic', docstatus: 0,
      custom_weekly_status: 'Pending HR Review', ready_for_hr_close: true, time_logs: [] }
  }
  await review.detail({ name: 'QA-week' }, true)
  assert.match(text(dialogs[0].fields_dict.entries.$wrapper), /HR approval is still required/)
  await buttons.find(b => b.label === 'Finalize week').action()
  assert.equal(calls.length, 1); assert.equal(alerts.length, 0)
  assert.match(confirmations[0].message, /locks the entire week.*history.*notified/)
  await confirmations[0].action()
  assert.equal(calls[1][0], 'weekly_timesheet.hr_close_weekly_timesheet')
  assert.equal(calls[1][1].name, 'QA-week')
  assert.equal(dialogs[0].visible, false); assert.equal(review.reloaded, true)
  assert.match(alerts[0].message, /Week finalized.*Locked.*history/)
})

test('blocked finalization has no final action; server rejection is never displayed as success', async () => {
  for (const ready of [false, true]) {
    const { review, buttons, confirmations, dialogs, alerts } = setup()
    review.call = async method => {
      if (method.endsWith('hr_close_weekly_timesheet')) throw new Error('Concurrent project return')
      return { name: 'QA-week', employee_name: 'Synthetic', docstatus: 0,
        custom_weekly_status: 'Pending HR Review', ready_for_hr_close: ready, time_logs: [] }
    }
    await review.detail({ name: 'QA-week' }, true)
    const finalize = buttons.find(b => b.label === 'Finalize week')
    if (ready) {
      await finalize.action()
      await assert.rejects(confirmations[0].action(), /Concurrent project return/)
      assert.equal(dialogs[0].visible, true); assert.equal(alerts.length, 0)
    } else {
      assert.equal(finalize, undefined)
      assert.match(text(dialogs[0].fields_dict.entries.$wrapper), /Project and team reviews must be complete/)
    }
  }
})

test('history keeps every hour in its original bucket and explains whole-week and legacy stages', () => {
  const { review, headings } = setup(), output = new Element('report')
  const status_hours = { Draft: 1, 'Pending Project Approval': 2, 'Pending HR Review': 3,
    'Correction Required': 4, Closed: 5, Submitted: 6 }
  review.historyResults(output, { group_by: 'project', totals: { hours: 21, entries: 6,
    employees: 1, projects: 1, status_hours }, rows: [{ label: 'QA Project', key: 'QA',
    entries: 6, hours: 21, status_hours }] })
  assert.deepEqual(Array.from(headings[0]).slice(3), ['Not submitted', 'Awaiting project review',
    'Awaiting HR approval', 'Needs correction', 'Finalized', 'Legacy submitted'])
  const metric = output.children[0].children[1]
  assert.equal(metric.children[0].label, 'Finalized hours'); assert.equal(metric.children[1].label, '5')
  const body = output.children.find(e => e.html === 'tbody')
  assert.deepEqual(body.children[0].children.slice(1).map(e => e.label), [6, '21', '1', '2', '3', '4', '5', '6'])
  assert.match(text(output), /whole-week stages, not individual project approvals/)
  assert.match(text(output), /submitted outside the weekly HR approval workflow/)
  assert.match(source, /this\.weekStatusLabel\(row\.status\), row\.timesheet/)
})
