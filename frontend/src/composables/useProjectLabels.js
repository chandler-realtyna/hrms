import { ref } from "vue"
import { call } from "frappe-ui"

// Shared project code → "Label : CODE" map so every surface shows the
// human-readable project name beside the code (never a bare code).
export function useProjectLabels() {
	const labels = ref({})

	async function load() {
		try {
			const rows = await call("hrms.api.search_employee_projects", {
				doctype: "Project",
				txt: "",
				searchfield: "name",
				start: 0,
				page_len: 500,
				filters: {},
			})
			const map = {}
			for (const row of rows || []) {
				const name = row[0] || row.name
				const label = row[1] || row[0] || row.name
				if (!name) continue
				map[name] =
					!label || label === name || label.includes(name) ? label || name : `${label} : ${name}`
			}
			labels.value = map
		} catch {
			// fall back to project codes
		}
	}

	function displayName(code) {
		return labels.value[code] || code || ""
	}

	return { labels, load, displayName }
}
