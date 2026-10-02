const assert = require("node:assert/strict")
const { test } = require("node:test")
const fs = require("node:fs"), vm = require("node:vm"), { randomUUID } = require("node:crypto")
const source = fs.readFileSync(require("node:path").join(__dirname, "../src/views/timesheet/Timer.vue"), "utf8")
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, "")

function server() {
  const state = { revision: 0, initialized: false, server_now: "2026-10-02T09:00:00Z", favorites: [],
    timer: { startTime: null, form: { project: "", activity_type: "", description: "" }, segments: [], isPaused: false } }
  const receipts = new Set(), calls = []
  let saved = 0, lose = false
  const clone = () => JSON.parse(JSON.stringify(state))
  return {
    state, calls, get saved() { return saved }, loseNext() { lose = true },
    async call(method, args) {
      if (method.endsWith("get_state")) return clone()
      if (method.includes("search_employee_projects")) return [["Alpha", "Alpha"], ["Beta", "Beta"]]
      calls.push(args)
      if (receipts.has(args.operation_id)) return clone()
      if (args.expected_revision !== state.revision) throw { exc_type: "TimestampMismatchError", messages: ["The timer changed on another device."] }
      const payload = JSON.parse(args.payload), t = state.timer, action = args.action
      if (["start", "resume", "switch"].includes(action)) {
        if (t.startTime) t.segments.push({ project: t.form.project, from: t.startTime, to: state.server_now, seconds: 60 })
        t.form = { project: payload.project, activity_type: "", description: "" }
        t.startTime = state.server_now; t.isPaused = false
      } else if (action === "pause") {
        t.segments.push({ project: t.form.project, from: t.startTime, to: state.server_now, seconds: 60 })
        t.startTime = null; t.isPaused = true
      } else if (action === "save" || action === "discard") {
        t.segments = t.segments.filter(row => row.project !== payload.project)
        if (action === "save") saved++
        if (t.form.project === payload.project) t.startTime = null
      } else if (action === "favorite") {
        state.favorites = state.favorites.includes(payload.project) ? state.favorites.filter(p => p !== payload.project) : [...state.favorites, payload.project]
      }
      state.revision++; state.initialized = true; receipts.add(args.operation_id)
      if (lose) { lose = false; throw new Error("Network response lost") }
      return clone()
    }
  }
}
function client(backend, offset = 0) {
  const storage = new Map()
  class Clock extends Date { static now() { return Date.parse(backend.state.server_now) + offset } }
  const navigator = { onLine: true }
  const context = {
    ref: value => ({ value }), computed: getter => ({ get value() { return getter() } }),
    inject: name => name === "$translate" ? text => text : name === "$employee" ? { data: { name: "EMP", user_id: "worker@qa.invalid" } } : null,
    onMounted() {}, onUnmounted() {}, onIonViewWillEnter() {}, onIonViewWillLeave() {},
    console, Date: Clock, crypto: { randomUUID }, navigator,
    localStorage: { getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k) },
    setInterval: () => 1, clearInterval() {}, setTimeout: () => 1, clearTimeout() {},
    window: { confirm: () => true }, document: { title: "HRMS", querySelector: () => null, visibilityState: "visible" },
    STORAGE_KEY: "legacy", toast() {}, call: backend.call,
  }
  vm.createContext(context)
  vm.runInContext(script + "\nthis.api={form,segments,startTime,isRunning,isPaused,connected,revision,pickedProject,command,hydrate,saveProject,toggleProjectTimer,toggleFavorite,projectSeconds,refresh,migrateLegacy,legacyConflict,metadataConflict,persistState,activate:()=>{active=true},pending:()=>pending};", context)
  context.api.hydrate(JSON.parse(JSON.stringify(backend.state))); context.api.connected.value = true
  context.api.activate()
  return { ...context.api, storage, navigator }
}

test("a second browser sees the same timer and shared favorites", async () => {
  const backend = server(), a = client(backend), b = client(backend, 5 * 3600000)
  await a.toggleProjectTimer("Alpha"); await a.toggleFavorite("Alpha"); await b.refresh()
  assert.equal(b.startTime.value, a.startTime.value)
  assert.equal(b.projectSeconds("Alpha"), a.projectSeconds("Alpha"))
  await b.toggleProjectTimer("Alpha"); await a.refresh()
  assert.equal(a.isPaused.value, true)
})
test("choosing an extra project never reassigns active time", async () => {
  const backend = server(), c = client(backend)
  await c.toggleProjectTimer("Alpha"); c.pickedProject.value = "Beta"
  assert.equal(c.form.value.project, "Alpha")
})
test("saving one project leaves the other timer running", async () => {
  const backend = server(), c = client(backend)
  await c.toggleProjectTimer("Alpha"); await c.toggleProjectTimer("Beta")
  const start = c.startTime.value
  await c.saveProject("Alpha")
  assert.equal(c.form.value.project, "Beta")
  assert.equal(c.startTime.value, start)
  assert.equal(c.isRunning.value, true)
})
test("lost responses retry the exact operation without duplicate saves", async () => {
  const backend = server(), c = client(backend)
  await c.toggleProjectTimer("Alpha")
  c.navigator.onLine = false; backend.loseNext()
  await c.saveProject("Alpha")
  const operation = c.pending().operation_id
  assert.equal(backend.saved, 1)
  c.navigator.onLine = true; await c.refresh()
  assert.equal(backend.saved, 1)
  assert.equal(backend.calls.at(-1).operation_id, operation)
  assert.equal(c.pending(), null)
})
test("stale device rejects action and refreshes without replaying it", async () => {
  const backend = server(), a = client(backend), b = client(backend)
  await a.toggleProjectTimer("Alpha")
  b.navigator.onLine = false
  assert.equal(await b.command("start", { project: "Beta" }), false)
  assert.equal(b.pending(), null)
  b.navigator.onLine = true; await b.refresh()
  assert.equal(b.form.value.project, "Alpha")
})
test("offline state disables actions but preserves the running counter", async () => {
  const backend = server(), c = client(backend)
  await c.toggleProjectTimer("Alpha")
  c.connected.value = false
  assert.equal(await c.command("pause"), false)
  assert.equal(c.isRunning.value, true)
})
test("conflicting local state is retained without overwriting server timer", async () => {
  const backend = server(), c = client(backend)
  await c.toggleProjectTimer("Alpha")
  c.storage.set("legacy", JSON.stringify({ owner: "worker@qa.invalid", form: { project: "Beta" }, segments: [] }))
  await c.migrateLegacy()
  assert.equal(c.form.value.project, "Alpha")
  assert.equal(c.legacyConflict.value, true)
  assert.ok(c.storage.get("hrms_timer_recovery:worker@qa.invalid"))
})
test("remote changes never silently overwrite an unsaved timer description", async () => {
  const backend = server(), a = client(backend), b = client(backend)
  await a.toggleProjectTimer("Alpha"); await b.refresh()
  b.form.value.description = "Unsent draft"; b.persistState()
  await a.toggleProjectTimer("Beta"); await b.refresh()
  assert.equal(b.metadataConflict.value, true)
  assert.equal(b.form.value.project, "Beta")
  assert.equal(await b.command("pause"), false)
  assert.equal(JSON.parse(b.storage.get("hrms_timer_recovery:worker@qa.invalid")).metadataDraft.form.description, "Unsent draft")
})
