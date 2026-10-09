const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = 'http://127.0.0.1:18880'
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  try {
    let name
    for (const width of [390, 1280]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: 'dark', serviceWorkers: 'block', extraHTTPHeaders: { 'X-Frappe-Site-Name': 'qa.local' } })
      let csrf = ''
      const rpc = async (method, data = {}) => {
        const response = await context.request.post(origin+'/api/method/'+method, { data, headers: csrf ? { 'X-Frappe-CSRF-Token': csrf } : {} })
        assert.equal(response.status(), 200, await response.text())
        return (await response.json()).message
      }
      await rpc('login', { usr: 'worker@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' })
      const page = await context.newPage(), errors = []
      page.on('pageerror', err => errors.push(err.message))
      if (!name) {
        await page.goto(origin+'/hrms/timesheets/timer')
        await page.getByRole('heading', { name: 'Time Tracker' }).waitFor()
        csrf = await page.evaluate(() => window.csrf_token)
        const before = await rpc('hrms.api.timer_state.get_state')
        assert.equal(before.timer.segments[0].seconds, 600)
        const savedResponse = page.waitForResponse(response => response.url().includes('timer_state.apply_action') && response.request().postDataJSON()?.action === 'save')
        await page.getByRole('button', { name: 'Save', exact: true }).first().click()
        const response = await savedResponse
        assert.equal(response.status(), 200)
        const saved = (await response.json()).message
        assert.equal(saved.timer.segments.length, 0)
        assert.ok(saved.overlap_warnings.length)
        name = saved.saved_timesheets[0]
        await page.getByText('Saved with a short overlap', { exact: true }).waitFor()
        await page.screenshot({ path: '/private/tmp/hrms-short-overlap-saved.png', fullPage: true })
      }
      await page.goto(origin+'/hrms/timesheets/'+name)
      await page.getByText('Saved with short overlaps of up to 5 minutes. Your time was not changed.', { exact: true }).waitFor()
      assert.equal(await page.getByText('Overlapping entries — saving is blocked until fixed:', { exact: true }).count(), 0)
      csrf = await page.evaluate(() => window.csrf_token)
      const week = await rpc('hrms.api.weekly_timesheet.get_weekly_timesheet', { name })
      assert.equal(week.time_logs.length, 2)
      const durations = week.time_logs.map(row => (Date.parse(row.to_time)-Date.parse(row.from_time))/1000).sort((a,b) => a-b)
      assert.deepEqual(durations, [300, 600])
      await page.screenshot({ path: '/private/tmp/hrms-short-overlap-week-'+width+'.png', fullPage: true })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
      assert.deepEqual(errors, [])
      await context.close()
    }
    console.log('SHORT_OVERLAP_BROWSER_OK: actual timer save; warning in timer and weekly form; original durations preserved; mobile/desktop dark mode')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
