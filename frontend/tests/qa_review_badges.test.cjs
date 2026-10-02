const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = 'http://127.0.0.1:18880'
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, serviceWorkers: 'block' })
    assert.equal((await context.request.post(origin+'/api/method/login', {
      form: { usr: 'hr@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' } })).status(), 200)
    const page = await context.newPage(), errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(origin+'/desk/admin-reviews', { waitUntil: 'domcontentloaded' })
    for (const [label, count] of [['HR Weekly Timesheet Review', 12], ['Leave Requests', 64],
      ['Expense Requests', 3], ['Holiday Approvals', 65], ['Schedule Approvals', 4], ['Invoices', 5]]) {
      const card = page.getByRole('link', { name: label, exact: true })
      await card.locator('.admin-reviews-count-badge').getByText(String(count), { exact: true }).waitFor({ timeout: 45000 })
    }
    assert.equal(await page.locator('.admin-reviews-count-badge').count(), 6)
    const cards = page.locator('.admin-reviews-link')
    assert.equal(await cards.locator('.admin-reviews-card-icon svg use').count(), await cards.count())
    assert.equal(await cards.locator('.admin-reviews-card-icon svg').evaluateAll(icons => icons.every(icon => {
      const box = icon.getBBox(); return box.width > 0 && box.height > 0
    })), true, 'All icon symbols must actually render')
    await page.screenshot({ path: '/private/tmp/hrms-review-badges-desktop.png', fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    if (await page.locator('.body-sidebar-container.expanded').count()) {
      const overlay = page.locator('.body-sidebar-container .overlay')
      const box = await overlay.boundingBox()
      await overlay.click({ position: { x: box.width - 8, y: 100 } })
      await page.waitForFunction(() => !document.querySelector('.body-sidebar-container.expanded'))
    }
    await page.screenshot({ path: '/private/tmp/hrms-review-badges-mobile.png', fullPage: true })
    for (const card of await cards.all()) {
      await card.scrollIntoViewIfNeeded()
      assert.equal(await card.evaluate(card => {
        const box = card.getBoundingClientRect()
        return card.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2))
      }), true, 'Every mobile card is unobscured and reachable')
    }
    await page.screenshot({ path: '/private/tmp/hrms-review-badges-mobile-bottom.png', fullPage: true })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    const overlaps = await cards.evaluateAll(cards => cards.some(card => {
      const label = card.querySelector('.admin-reviews-link-label').getBoundingClientRect()
      const badge = card.querySelector('.admin-reviews-count-badge')?.getBoundingClientRect()
      return badge && label.right > badge.left
    }))
    assert.equal(overlaps, false)
    assert.deepEqual(errors, [])
    console.log('REVIEW_BADGES_BROWSER_OK: six complete counts, all icons rendered, accessible links, mobile without overlap')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
