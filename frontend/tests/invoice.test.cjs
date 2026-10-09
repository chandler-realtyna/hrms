const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { parse } = require('@vue/compiler-sfc');
const { execFileSync } = require('node:child_process');

const catalog = JSON.parse(execFileSync('python3', ['-c',
  'import csv,json; print(json.dumps(dict(csv.reader(open("../hrms/translations/en.csv")))))'
], {encoding: 'utf8'}));

test('English labels use Contractor and Invoice without changing records or roles', () => {
  assert.equal(catalog.Employee, 'Contractor');
  assert.equal(catalog.Employees, 'Contractors');
  assert.equal(catalog['Employee Invoice'], 'Invoice');
  assert.equal(catalog['Employee Invoices'], 'Invoices');
  assert.equal(catalog['Pending Employee Confirmation'], 'Pending Contractor Confirmation');
  assert.equal(catalog['Employee notes'], 'Contractor notes');
  assert.equal(catalog['/employee-advances'], undefined);
  assert.equal(catalog['$employee'], undefined);
  const metadata = JSON.parse(fs.readFileSync('../hrms/hr/doctype/employee_invoice/employee_invoice.json'));
  assert.equal(metadata.name, 'Employee Invoice');
  assert.equal(metadata.fields.find(f => f.fieldname === 'employee').options, 'Employee');
  assert.ok(metadata.permissions.some(p => p.role === 'Employee'));
});

function invoiceForm(id, response) {
  const source = parse(fs.readFileSync('src/views/invoice/Form.vue', 'utf8')).descriptor;
  const calls = [], mounted = [];
  const context = {
    ref: value => ({value}), reactive: value => value, computed: fn => ({get value() {return fn();}}),
    defineProps: () => ({id}), inject: name => name === '$user' ? {data: {roles: []}} : text => catalog[text] || text,
    useRouter: () => ({replace() {}}), h() {}, onMounted: fn => mounted.push(fn),
    call: async (method, args) => {calls.push({method, args}); return response;},
    window: {}, console,
  };
  vm.createContext(context);
  vm.runInContext(source.scriptSetup.content.replace(/^import .*$/gm, '') +
    '\nthis.api = {createInvoice, defaults, doc, loading, editableFields};', context);
  return {...context.api, calls, mounted};
}
test('new invoice displays server dates and never submits a caller-controlled due date', async () => {
  const page = invoiceForm(undefined, {invoice_date: '2026-10-02', due_date: '2026-10-17'});
  await page.mounted[0]();
  assert.equal(page.defaults.value.due_date, '2026-10-17');
  assert.equal(page.loading.value, false);
  assert.equal(page.calls[0].method, 'hrms.api.employee_invoice.get_invoice_defaults');
  await page.createInvoice();
  assert.equal(page.calls[1].args, undefined);
  assert.ok(!page.editableFields.includes('due_date'));
});
test('invoice terminology translations preserve replacement values', async () => {
  const source = fs.readFileSync('src/plugins/translationsPlugin.js', 'utf8').replace('export const', 'const');
  const context = {window: {frappe: {boot: {__messages: catalog}}}};
  vm.createContext(context);
  vm.runInContext(source + '\nthis.api = {translate,load};', context);
  await context.api.load();
  assert.equal(context.api.translate('Employee Invoice'), 'Invoice');
  assert.equal(context.api.translate('Employee {0} : {1}', ['Employee Services Ltd', 'Employee Relations']),
    'Contractor Employee Services Ltd : Employee Relations');
});
