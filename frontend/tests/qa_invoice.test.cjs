const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = 'http://127.0.0.1:18880'

;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } })
      try {
        const login = await context.request.post(`${origin}/api/method/login`, {
          form: { usr: 'worker@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' },
        })
        assert.equal(login.status(), 200)
        const page = await context.newPage()
        const errors = []
        page.on('pageerror', error => errors.push(error.message))
        await page.goto(`${origin}/hrms/invoices/new`)
        await page.getByRole('heading', { name: 'Create invoice', exact: true }).waitFor({ timeout: 20000 })
        const dismiss = page.getByRole('button', { name: 'Not now', exact: true })
        if (await dismiss.isVisible()) await dismiss.click()
        const main = page.locator('main.max-w-4xl')
        const dates = main.locator('input[type=date]')
        assert.equal(await dates.count(), 2)
        const issue = await dates.nth(0).inputValue()
        const due = await dates.nth(1).inputValue()
        assert.equal((Date.parse(due) - Date.parse(issue)) / 86400000, 15)
        assert.equal(await dates.nth(0).getAttribute('readonly'), '')
        assert.equal(await dates.nth(1).getAttribute('readonly'), '')
        await page.screenshot({ path: `/private/tmp/hrms-qa-invoice-new-${width}.png`, fullPage: true })
        await page.getByRole('button', { name: 'Create and calculate', exact: true }).click()
        try { await page.getByRole('heading', { name: 'Payee and payment', exact: true }).waitFor({ timeout: 20000 }) }
        catch (error) { console.log('QA_INVOICE_DIAGNOSTIC', page.url(), await main.innerText(), errors); throw error }
        const body = await main.innerText()
        assert.match(body, /Contractor notes/)
        assert.doesNotMatch(body, /Employee notes|Employee Invoice/)
        assert.equal(await dates.nth(0).inputValue(), issue)
        assert.equal(await dates.nth(1).inputValue(), due)
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
        await page.screenshot({ path: `/private/tmp/hrms-qa-invoice-created-${width}.png`, fullPage: true })
        await page.evaluate(() => document.documentElement.classList.add('dark'))
        const colors = await dates.nth(0).evaluate(el => ({
          background: getComputedStyle(el).backgroundColor, color: getComputedStyle(el).color,
        }))
        assert.notEqual(colors.background, colors.color)
        assert.notEqual(colors.background, 'rgb(255, 255, 255)')
        await page.screenshot({ path: `/private/tmp/hrms-qa-invoice-dark-${width}.png`, fullPage: true })
        assert.deepEqual(errors, [])
        console.log(`QA_INVOICE_OK width=${width} dates=${issue}/${due}`)
      } finally { await context.close() }
    }
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    try {
      const login = await context.request.post(`${origin}/api/method/login`, {
        form: { usr: 'hr@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' },
      })
      assert.equal(login.status(), 200)
      const page = await context.newPage()
      await page.goto(`${origin}/desk/admin-reviews`)
      await page.getByRole('link', { name: 'Invoices', exact: true }).waitFor({ timeout: 20000 })
      await page.getByRole('link', { name: 'Contractors', exact: true }).waitFor({ timeout: 10000 })
      await page.getByRole('link', { name: 'Invoices', exact: true }).click()
      await page.waitForFunction(() => window.frappe?.get_route()?.[1] === 'Employee Invoice', null, { timeout: 10000 })
      await page.locator('.page-title:visible').filter({ hasText: 'Invoice' }).first().waitFor({ timeout: 10000 })
      assert.doesNotMatch(await page.locator('body').innerText(), /Employee Invoice|\bEmployee\b/)
      await page.screenshot({ path: '/private/tmp/hrms-qa-invoice-desk.png', fullPage: true })
      console.log('QA_INVOICE_DESK_OK')
    } finally { await context.close() }
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
