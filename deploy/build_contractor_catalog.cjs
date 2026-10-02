// Generate standard Frappe English translations without renaming data contracts.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const { execFileSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const requireFrontend = createRequire(path.join(root, 'frontend/package.json'));
const babel = requireFrontend('@babel/parser');
const sfc = requireFrontend('@vue/compiler-sfc');
const compiler = requireFrontend('@vue/compiler-dom');
const messages = new Set([
  'Employee', 'Employees', 'Employee Invoice', 'Employee Invoices',
  'Employee ID', 'Employee Name', 'Employee User', 'From Employee',
  'Employee Details', 'Employee Information', 'Employee Profile',
]);

function add(value) {
  if (typeof value === 'string' && /\bemployees?\b/i.test(value)) messages.add(value.trim());
}
function walk(value) {
  if (!value || typeof value !== 'object') return;
  if (value.type === 'CallExpression' && ['__', '_', '$translate'].includes(value.callee.name || value.callee.property?.name)) {
    if (value.arguments[0]?.type === 'StringLiteral') add(value.arguments[0].value);
  }
  if (value.type === 'ObjectProperty' && ['label', 'title', 'description', 'placeholder'].includes(value.key.name || value.key.value)) {
    if (value.value.type === 'StringLiteral') add(value.value.value);
  }
  for (const item of Object.values(value)) {
    if (Array.isArray(item)) item.forEach(walk);
    else if (item && typeof item === 'object') walk(item);
  }
}
function javascript(source, filename) {
  try {
    // Frappe expands these includes before parsing; included files are scanned separately.
    source = source.replace(/^\s*\{%\s*include\s+['"][^'"]+['"]\s*%\}\s*$/gm, '');
    walk(babel.parse(source, { sourceType: 'unambiguous', plugins: ['typescript'], sourceFilename: filename }));
  } catch (error) { throw new Error(`${filename}: ${error.message}`); }
}
function template(node, filename) {
  if (node.type === 5) javascript(node.content.content, filename);
  for (const prop of node.props || []) {
    if (prop.type === 6 && prop.value) add(prop.value.content);
    if (prop.type === 7 && prop.exp && prop.name !== 'for') {
      // Handler statements and bound expressions are parsed as real JS.
      javascript(prop.name === 'on' ? prop.exp.content : `(${prop.exp.content})`, filename);
    }
  }
  for (const child of node.children || []) template(child, filename);
}
function metadata(value) {
  if (!value || typeof value !== 'object') return;
  for (const key of ['label', 'title', 'description', 'report_name']) add(value[key]);
  if (['DocType', 'Report', 'Print Format'].includes(value.doctype)) add(value.name);
  if (value.fieldtype === 'Select') (value.options || '').split('\n').forEach(add);
  for (const item of Object.values(value)) {
    if (Array.isArray(item)) item.forEach(metadata);
    else if (item && typeof item === 'object') metadata(item);
  }
}
const pythonSources = [];
function scan(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['.git', 'node_modules', '__pycache__', 'frontend', 'roster', 'translations'].includes(entry.name)) continue;
    const filename = path.join(dir, entry.name);
    if (entry.isDirectory()) { scan(filename); continue; }
    const ext = path.extname(filename);
    if (!['.js', '.vue', '.json', '.py'].includes(ext)) continue;
    const source = fs.readFileSync(filename, 'utf8');
    if (ext === '.json') metadata(JSON.parse(source));
    else if (ext === '.py') pythonSources.push(source);
    else if (ext === '.js') javascript(source, filename);
    else {
      const { descriptor, errors } = sfc.parse(source);
      if (errors.length) throw errors[0];
      for (const script of [descriptor.script, descriptor.scriptSetup]) if (script) javascript(script.content, filename);
      if (descriptor.template) template(compiler.parse(descriptor.template.content), filename);
    }
  }
}
scan(path.join(root, 'hrms'));
scan(path.join(root, 'frontend/src'));
const pythonMessages = execFileSync('python3', ['-c', `
import ast, json, sys
messages = []
for source in json.load(sys.stdin):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and node.args and (isinstance(node.func, ast.Name) and node.func.id in {'_', '_lt'} or isinstance(node.func, ast.Attribute) and node.func.attr == '_'):
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                messages.append(node.args[0].value)
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in {'label', 'description', 'title'} and isinstance(value, ast.Constant):
                    messages.append(value.value)
json.dump(messages, sys.stdout)
`], { input: JSON.stringify(pythonSources), encoding: 'utf8' });
JSON.parse(pythonMessages).forEach(add);
function casing(source, target) {
  return source === source.toUpperCase() ? target.toUpperCase()
    : source[0] === source[0].toUpperCase() ? target[0].toUpperCase() + target.slice(1) : target;
}
function plainLabel(source) {
  return source.replace(/\bemployee invoices?\b/gi, text => casing(text, /s$/i.test(text) ? 'invoices' : 'invoice'))
    .replace(/\bemployees?\b/gi, text => casing(text, /s$/i.test(text) ? 'contractors' : 'contractor'))
    .replace(/\ban(?= contractor\b)/gi, text => casing(text, 'a'));
}
function label(source) {
  if (!source.includes('<')) return plainLabel(source);
  const errors = [], edits = [];
  const html = compiler.parse(source, { onError: error => errors.push(error) });
  if (errors.length) return source;
  function text(node) {
    if (node.type === 2) edits.push([node.loc.start.offset, node.loc.end.offset, plainLabel(node.loc.source)]);
    for (const child of node.children || []) text(child);
  }
  text(html);
  for (const [start, end, value] of edits.sort((a, b) => b[0] - a[0])) source = source.slice(0, start) + value + source.slice(end);
  return source;
}
const rows = [...messages].sort().map(source => [source, label(source)]).filter(([source, target]) => source !== target);
const csv = execFileSync('python3', ['-c', String.raw`
import csv, json, sys
writer = csv.writer(sys.stdout, lineterminator='\n')
writer.writerows(json.load(sys.stdin))
`], { input: JSON.stringify(rows), encoding: 'utf8' });
const output = path.join(root, 'hrms/translations/en.csv');
if (process.argv.includes('--write')) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, csv);
} else if (!fs.existsSync(output) || fs.readFileSync(output, 'utf8') !== csv) {
  throw new Error('Contractor catalog is stale; run node deploy/build_contractor_catalog.cjs --write');
}
console.log(`${rows.length} English terminology entries ${process.argv.includes('--write') ? 'generated' : 'verified'}`);
