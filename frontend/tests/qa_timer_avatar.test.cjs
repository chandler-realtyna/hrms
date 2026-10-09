const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = 'http://127.0.0.1:18880'
const originalPhoto = process.env.QA_PRIVATE_PHOTO
assert.ok(originalPhoto?.startsWith('/private/files/'), 'Pass the synthetic fixture photo URL as QA_PRIVATE_PHOTO')
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  try {
    const guest = await browser.newContext({ serviceWorkers: 'block', extraHTTPHeaders: { 'X-Frappe-Site-Name': 'qa.local' } })
    assert.equal((await guest.request.get(origin+'/api/method/hrms.api.profile_photo.get_photo?employee=missing')).status(), 403)
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: 'dark', serviceWorkers: 'block', extraHTTPHeaders: { 'X-Frappe-Site-Name': 'qa.local' } })
      let csrf = ''
      const rpc = async (method, data = {}) => {
        const response = await context.request.post(origin+'/api/method/'+method, { data, headers: csrf ? { 'X-Frappe-CSRF-Token': csrf } : {} })
        assert.equal(response.status(), 200, await response.text())
        return (await response.json()).message
      }
      await rpc('login', { usr: 'worker@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' })
      const people = await rpc('hrms.api.get_all_employees')
      const lead = people.find(p => p.user_id === 'lead@qa.invalid')
      assert.match(lead.image, /hrms.api.profile_photo.get_photo/)
      const thumbnail = await context.request.get(origin+lead.image)
      assert.equal(thumbnail.status(), 200)
      assert.match(thumbnail.headers()['content-type'], /image\/webp/)
      assert.equal(thumbnail.headers()['cache-control'], 'private, no-store')
      assert.equal((await context.request.get(origin+originalPhoto)).status(), 403)
      assert.equal((await context.request.get(origin+'/api/method/hrms.api.profile_photo.get_photo?employee=missing')).status(), 404)
      assert.equal((await context.request.post(origin+'/api/method/frappe.client.get', { data: { doctype: 'Employee', name: lead.name } })).status(), 403)
      const page = await context.newPage(), errors = []
      page.on('pageerror', err => errors.push(err.message))
      await page.goto(origin+'/hrms/timesheets/timer')
      await page.getByRole('heading', { name: 'Time Tracker' }).waitFor({ timeout: 30000 })
      csrf = await page.evaluate(() => window.csrf_token)
      const dismiss = page.getByRole('button', { name: 'Not now', exact: true }).first()
      if (await dismiss.isVisible()) await dismiss.click()
      await page.getByRole('button', { name: 'Save', exact: true }).first().click()
      await page.getByText('This time overlaps existing entries. Your timer is preserved.', { exact: true }).waitFor()
      await page.getByRole('link', { name: 'Review timesheet', exact: true }).first().waitFor()
      const before = await rpc('hrms.api.timer_state.get_state')
      await page.getByRole('button', { name: 'Retry', exact: true }).click()
      await page.getByText('This time overlaps existing entries. Your timer is preserved.', { exact: true }).waitFor()
      const after = await rpc('hrms.api.timer_state.get_state')
      assert.equal(after.revision, before.revision)
      assert.deepEqual(after.timer, before.timer)
      await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent.trim() === 'Save' && !button.disabled))
      if (await dismiss.isVisible()) await dismiss.click()
      await page.screenshot({ path: '/private/tmp/hrms-save-conflict-'+width+'.png', fullPage: true })
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
      await page.goto(origin+'/hrms/availability')
      await page.locator('ion-title').filter({ hasText: 'Team Availability' }).waitFor({ timeout: 30000 })
      const photo = page.locator('img[src*="hrms.api.profile_photo.get_photo"]').first()
      await photo.waitFor()
      await photo.evaluate(img => img.complete && img.naturalWidth ? true : new Promise((resolve, reject) => {
        img.onload = () => resolve(true); img.onerror = () => reject(new Error('Thumbnail did not render'))
      }))
      assert.equal(await photo.evaluate(img => img.naturalWidth), 128)
      await page.screenshot({ path: '/private/tmp/hrms-profile-thumbnail-'+width+'.png', fullPage: true })
      await page.route('**/api/method/hrms.api.profile_photo.get_photo?**', route => route.abort())
      await page.reload()
      await page.locator('button[aria-label="Select person"]').filter({ hasText: /^l$/i }).waitFor()
      assert.equal(await page.locator('img[src*="hrms.api.profile_photo.get_photo"]').count(), 0)
      assert.deepEqual(errors, [])
      await context.close()
    }
    console.log('TIMER_AVATAR_HTTP_OK: persistent conflict/real retry; unchanged timer; authenticated thumbnail renders desktop/mobile; foreign document and Guest denied')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
