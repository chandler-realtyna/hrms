const assert = require('node:assert/strict')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const origin = 'http://127.0.0.1:18880'
;(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' })
    const api = async (method, data = {}) => context.request.post(origin+'/api/method/'+method, { data })
    assert.equal((await api('login', { usr: 'worker@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' })).status(), 200)
    let response = await api('frappe.client.get_list', { doctype: 'User', fields: ['name'], limit_page_length: 1000 })
    assert.deepEqual((await response.json()).message.map(row => row.name), ['worker@qa.invalid'])
    assert.equal((await api('frappe.client.get', { doctype: 'User', name: 'hr@qa.invalid' })).status(), 403)
    response = await api('frappe.client.get_list', { doctype: 'Project', fields: ['name'] })
    assert.deepEqual((await response.json()).message, [])
    response = await api('frappe.desk.search.search_link', { doctype: 'Project', txt: 'QA', page_length: 20 })
    const projects = (await response.json()).message
    assert.ok(projects.length >= 2, 'Self-service project choices remain available')
    assert.equal((await api('frappe.client.get', { doctype: 'Project', name: projects[0].value })).status(), 403)
    response = await api('hrms.api.get_current_employee_info')
    const employee = (await response.json()).message
    response = await api('frappe.client.get', { doctype: 'Employee', name: employee.name })
    const doc = (await response.json()).message
    doc.leave_approver = 'worker@qa.invalid'
    assert.equal((await api('frappe.client.save', { doc: JSON.stringify(doc) })).status(), 403)
    assert.equal((await api('login', { usr: 'lead@qa.invalid', pwd: 'Synthetic-QA-Only!9842-Browser' })).status(), 200)
    const page = await context.newPage()
    await page.goto(origin+'/desk/admin-reviews', { waitUntil: 'domcontentloaded' })
    await page.getByRole('link', { name: 'Team Timesheets', exact: true }).waitFor({ timeout: 45000 })
    assert.deepEqual(await page.locator('.admin-reviews-link-label').allTextContents(), ['Team Timesheets', 'Time History'])
    await page.screenshot({ path: '/private/tmp/hrms-contractor-desk-access.png', fullPage: true })
    await page.getByRole('link', { name: 'Team Timesheets', exact: true }).click()
    await page.getByPlaceholder('Search contractor, project or activity').waitFor({ timeout: 30000 })
    console.log('MASTER_ACCESS_BROWSER_OK: denied foreign users/master project/profile save; project lookup and lead review retained')
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })
