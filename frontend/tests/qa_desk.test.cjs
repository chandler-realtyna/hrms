const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    const response = await context.request.post('http://127.0.0.1:18880/api/method/login', {
      form: { usr: 'hr@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' } })
    assert.equal(response.status(), 200)
    const page = await context.newPage()
    page.on('pageerror', error => console.log('DESK_PAGE_ERROR', error.message))
    await page.goto('http://127.0.0.1:18880/desk/admin-reviews')
    try { await page.getByText('Timesheet Reviews', { exact: true }).waitFor({ timeout: 20000 }) }
    catch (error) { console.log('DESK_DIAGNOSTIC', page.url(), await page.locator('body').innerText()); await page.screenshot({ path: '/private/tmp/hrms-qa-desk-error.png', fullPage: true }); throw error }
    await page.getByRole('button', { name: 'Log out', exact: true }).waitFor({ timeout: 10000 })
    const sidebar = await page.locator('.body-sidebar').innerText()
    console.log('QA_SIDEBAR', JSON.stringify(sidebar))
    assert.match(sidebar, /Search/); assert.match(sidebar, /Notification/); assert.match(sidebar, /Log out/)
    assert.doesNotMatch(sidebar, /Stock Entry|Manufacturing|Selling/)
    await page.screenshot({ path: '/private/tmp/hrms-qa-desk.png', fullPage: true })
    await page.getByRole('link', { name: /Team Timesheets/ }).click()
    await page.getByRole('button', { name: 'Current', exact: true }).waitFor({ timeout: 10000 })
    console.log('DESK_UI_QA_OK: utilities sidebar and native team queue route')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
