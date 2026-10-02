const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fs = require('node:fs')
const origin = 'http://127.0.0.1:18880'
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  const contexts = []
  try {
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, serviceWorkers: 'block' }); contexts.push(context)
      const login = await context.request.post(origin+'/api/method/login', { form: { usr: 'worker@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' } })
      assert.equal(login.status(), 200, await login.text())
    }
    async function rpc(context, method, args = {}) {
      const page = context.pages()[0]
      const csrf = page && await page.evaluate(() => window.csrf_token)
      const response = await context.request.post(origin+'/api/method/'+method, { data: args,
        headers: csrf ? { 'X-Frappe-CSRF-Token': csrf } : {} })
      const data = await response.json()
      assert.equal(response.status(), 200, JSON.stringify(data)); return data.message
    }
    const projects = await rpc(contexts[0], 'hrms.api.search_employee_projects', { doctype: 'Project', txt: '', searchfield: 'name', start: 0, page_len: 50, filters: {} })
    const alpha = projects.find(row => row[1] === 'QA Alpha')[0], beta = projects.find(row => row[1] === 'QA Beta')[0]
    for (const project of [alpha, beta]) {
      const state = await rpc(contexts[0], 'hrms.api.timer_state.get_state')
      if (!state.favorites.includes(project)) await rpc(contexts[0], 'hrms.api.timer_state.apply_action', {
        action: 'favorite', expected_revision: state.revision, operation_id: 'http_'+require('node:crypto').randomUUID(), payload: JSON.stringify({ project }) })
    }
    const pages = await Promise.all(contexts.map(context => context.newPage()))
    for (const [i,page] of pages.entries()) {
      page.on('pageerror', err => console.log('PAGE_ERROR', i, err.message))
      await page.goto(origin+'/hrms/timesheets/timer')
      await page.getByRole('heading', { name: 'Time Tracker' }).waitFor({ timeout: 30000 })
      await page.getByRole('button', { name: 'Start', exact: true }).first().waitFor({ timeout: 20000 })
    }
    const row = (page, name) => page.locator('div.flex.flex-wrap.items-center.gap-2.rounded-lg').filter({ hasText: name })
    await row(pages[0], 'QA Alpha').getByRole('button', { name: 'Start', exact: true }).click()
    await row(pages[1], 'QA Alpha').getByRole('button', { name: 'Pause', exact: true }).waitFor({ timeout: 15000 })
    await row(pages[1], 'QA Alpha').getByRole('button', { name: 'Pause', exact: true }).click()
    await row(pages[0], 'QA Alpha').getByRole('button', { name: 'Resume', exact: true }).waitFor({ timeout: 15000 })
    await row(pages[1], 'QA Alpha').getByRole('button', { name: 'Resume', exact: true }).click()
    await row(pages[1], 'QA Beta').getByRole('button', { name: 'Switch', exact: true }).click()
    const before = await rpc(contexts[0], 'hrms.api.timer_state.get_state')
    await row(pages[1], 'QA Alpha').getByRole('button', { name: 'Save', exact: true }).click()
    const after = await rpc(contexts[0], 'hrms.api.timer_state.get_state')
    assert.equal(after.timer.startTime, before.timer.startTime); assert.equal(after.timer.form.project, beta)
    await contexts[1].setOffline(true)
    assert.equal(await row(pages[1], 'QA Beta').getByRole('button', { name: 'Pause', exact: true }).isDisabled(), true)
    await contexts[1].setOffline(false)
    await row(pages[1], 'QA Beta').getByRole('button', { name: 'Pause', exact: true }).waitFor()
    for (const [i,page] of pages.entries()) await page.screenshot({ path: '/private/tmp/hrms-qa-http-'+i+'.png', fullPage: true })
    console.log('HTTP_UI_QA_OK: two authenticated browser contexts, shared favorites, start/pause/resume/switch, save inactive project, offline controls')
	const week = await rpc(contexts[0], 'hrms.api.weekly_timesheet.get_weekly_timesheet')
	assert.ok(week.name, 'Saved timer must create a weekly source record')
	for (const page of pages) {
		await page.goto(origin+'/hrms/timesheets/'+week.name)
		await page.getByRole('heading', { name: 'Weekly Timesheet', exact: true }).waitFor({ timeout: 20000 })
		const dismiss = page.getByRole('button', { name: 'Not now', exact: true })
		if (await dismiss.isVisible()) await dismiss.click()
	}
	const note = page => page.getByPlaceholder('Optional note for the week')
	await note(pages[0]).fill('Updated in desktop QA')
	await pages[0].getByText('Saved automatically', { exact: true }).waitFor({ timeout: 10000 })
	await pages[1].waitForFunction(() => document.querySelector('textarea')?.value === 'Updated in desktop QA', null, { timeout: 40000 })
	await contexts[1].setOffline(true)
	await note(pages[1]).fill('Unsaved mobile draft QA')
	await pages[1].getByText('Save failed — tap to retry', { exact: true }).waitFor({ timeout: 10000 })
	await note(pages[0]).fill('New desktop version QA')
	await pages[0].getByText('Saved automatically', { exact: true }).waitFor({ timeout: 10000 })
	await contexts[1].setOffline(false)
	await pages[1].getByRole('button', { name: 'Review latest', exact: true }).waitFor({ timeout: 15000 })
	assert.equal(await note(pages[1]).inputValue(), 'Unsaved mobile draft QA')
	console.log('HTTP_WEEK_QA_OK: automatic 30-second refresh, offline edit preservation, explicit version conflict')
  } catch (error) {
    for (const [i,context] of contexts.entries()) for (const page of context.pages()) {
      await page.screenshot({ path: '/private/tmp/hrms-qa-http-error-'+i+'.png', fullPage: true })
      fs.writeFileSync('/private/tmp/hrms-qa-http-error-'+i+'.txt', await page.locator('body').innerText())
    }
    throw error
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
