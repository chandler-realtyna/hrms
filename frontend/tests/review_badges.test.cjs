const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm')
const source = fs.readFileSync(path.join(__dirname, '../../hrms/public/js/admin_reviews.js'), 'utf8')
function setup(call) {
  const ctx = { frappe: { pages: { 'admin-reviews': {} } }, __: (s, values=[]) => s.replace(/\{(\d+)\}/g, (_,i) => values[i]) }
  vm.createContext(ctx); vm.runInContext(source + '\nthis.Reviews = HRMSAdminReviews;', ctx)
  const review = Object.create(ctx.Reviews.prototype), badge = {
    text(value) { this.value = value; return this },
    toggleClass(_name, value) { this.empty = value; return this },
    attr(value) { this.attributes = value; return this },
  }
  review.version = 1; review.call = call
  review.homeBadges = new Map([['hr-timesheets', { badge, label: 'HR review' }]])
  return { review, badge }
}
test('counts show actual integer values and distinguish zero from unavailable', async () => {
  let count = 65
  const { review, badge } = setup(async () => ({ 'hr-timesheets': count }))
  await review.updateHomeCounts(1)
  assert.equal(badge.value, '65'); assert.match(badge.attributes.title, /final HR approval/)
  count = 0; await review.updateHomeCounts(1)
  assert.equal(badge.value, '0'); assert.equal(badge.empty, true)
  count = null; await review.updateHomeCounts(1)
  assert.equal(badge.value, '-'); assert.equal(badge.empty, false)
  assert.equal(badge.attributes.title, 'Review count unavailable')
})
test('count failure is not silently reported as an empty review queue', async () => {
  const { review, badge } = setup(async () => { throw new Error('Disconnected') })
  await review.updateHomeCounts(1)
  assert.equal(badge.value, '-'); assert.match(badge.attributes['aria-label'], /unavailable/)
})
test('stale responses cannot overwrite a newer count or different page', async () => {
  let resolve, calls = 0
  const { review, badge } = setup(async () => ++calls === 1 ? new Promise(r => resolve = r) : { 'hr-timesheets': 3 })
  const old = review.updateHomeCounts(1); await review.updateHomeCounts(1)
  resolve({ 'hr-timesheets': 99 }); await old
  assert.equal(badge.value, '3')
  review.version = 2; await review.updateHomeCounts(1)
  assert.equal(badge.value, '3')
})
