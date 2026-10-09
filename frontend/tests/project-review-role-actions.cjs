const fs = require("fs"),
	assert = require("assert"),
	vm = require("vm");
const root = require("path").resolve(__dirname, "..");
const Vue = require(root + "/node_modules/vue"),
	{ renderToString } = require(root + "/node_modules/@vue/server-renderer"),
	{ parse, compileScript } = require(root + "/node_modules/@vue/compiler-sfc");
const { descriptor } = parse(
	fs.readFileSync(root + "/src/views/timesheet/ProjectReview.vue", "utf8")
);
let source = compileScript(descriptor, {
	id: "RoleQA",
	inlineTemplate: true,
	genDefaultAs: "Review",
})
	.content.replace(
		/^import \{([\s\S]*?)\} from ["']vue["']\s*$/gm,
		(_, s) => `const {${s.replace(/\bas\b/g, ":")}}=Vue`
	)
	.replace(/^import[\s\S]*?from ["'][^"']+["']\s*$/gm, "");
source = source.replace(
	"return (_ctx, _cache) => {",
	`loading.value=false;sections.value=window.rows;detail.value=window.section;Object.assign(window.hooks,{approveAll,approveRow,approveDetail,approveEntry,returnEntry,exceptionalReview,exceptionReason,exceptionBusy});return (_ctx, _cache) => {`
);
source += ";globalThis.Review=Review;";
const row = (regular) => ({
	timesheet: "QA",
	project: "P",
	modified: "v1",
	employee: "E",
	employee_name: "Test",
	week_start: "2026-10-04",
	week_end: "2026-10-10",
	actionable: true,
	regular_reviewer: regular,
	project_status: "Pending",
	hours: 1,
	logs: [],
	can_review_entries: true,
	can_return_entries: true,
	hr_exception: !regular,
});
async function scenario(rows, section) {
	const calls = [];
	const stub = {
		setup(p, { slots }) {
			return () => Vue.h("div", {}, slots.default?.());
		},
	};
	const ctx = {
		Vue,
		window: { rows, section, hooks: {}, confirm: () => true },
		IonPage: stub,
		IonHeader: stub,
		IonToolbar: stub,
		IonTitle: stub,
		IonContent: stub,
		IonButtons: stub,
		IonButton: stub,
		IonBackButton: stub,
		Button: {
			setup(p, { slots }) {
				return () => Vue.h("button", {}, slots.default?.());
			},
		},
		FeatherIcon: stub,
		onIonViewWillEnter: () => {},
		formatHours: () => "1:00",
		serverTimeAgo: () => "now",
		useProjectLabels: () => ({ displayName: (s) => s, load() {} }),
		call: async (method, args) => {
			calls.push({ method, args });
			return method.includes("get_team")
				? { rows, total: rows.length }
				: method.includes("get_project_review_detail")
				? section
				: { modified: "v2" };
		},
		toast: () => {},
		console,
	};
	vm.createContext(ctx);
	vm.runInContext(source, ctx);
	const app = Vue.createSSRApp(ctx.Review);
	app.provide("$translate", (s) => s);
	app.provide("$dayjs", () => ({ format: () => "date" }));
	const html = await renderToString(app);
	return { html, hooks: ctx.window.hooks, calls };
}
(async () => {
	let q = await scenario([row(false), row(false)], null);
	assert(!q.html.includes("Approve visible"));
	assert(!q.html.includes(">Approve<"));
	await q.hooks.approveRow(row(false));
	await q.hooks.approveAll();
	assert.equal(q.calls.length, 0);
	q = await scenario([row(true), row(true), row(false)], null);
	assert(q.html.includes("Approve visible"));
	await q.hooks.approveAll();
	assert.equal(
		q.calls.filter((c) => c.method.endsWith("review_saved_project_entries"))
			.length,
		2
	);
	q = await scenario([], row(false));
	assert(q.html.includes("Exceptional HR actions"));
	assert(!q.html.includes(">Approve<"));
	await q.hooks.approveDetail();
	await q.hooks.approveEntry({ name: "L" });
	await q.hooks.returnEntry({ name: "L" });
	await q.hooks.exceptionalReview("approve");
	assert.equal(q.calls.length, 0);
	q.hooks.exceptionReason.value = " Reviewer unavailable ";
	await q.hooks.exceptionalReview("approve");
	const c = q.calls.find((c) =>
		c.method.endsWith("review_saved_project_entries")
	);
	assert.equal(c.args.reason, "Reviewer unavailable");
	assert.equal(c.args.expected_modified, "v1");
	assert.equal(c.args.action, "approve");
	q = await scenario([], row(true));
	assert(!q.html.includes("Exceptional HR actions"));
	assert(q.html.includes(">Approve<"));
	await q.hooks.approveDetail();
	assert.equal(q.calls[0].args.reason, undefined);
	assert.equal(q.calls[0].args.expected_modified, "v1");
	console.log(
		"PASS: HR ordinary/bulk/entry actions blocked; assigned lead actions preserved; exceptional HR approval requires reason and saved revision; compiled list and detail templates checked"
	);
})().catch((e) => {
	console.error(e);
	process.exitCode = 1;
});
