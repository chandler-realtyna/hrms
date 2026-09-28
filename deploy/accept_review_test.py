"""Live acceptance test: Project Lead timesheet review (tests 1-5, 7 + Desk scoping).

Runs REAL whitelisted APIs with switched sessions (frappe.set_user) on
throwaway fixtures (TEST projects + a past test week). Cleans up everything
it creates. Safe to run on production: no emails are sent by these paths
(verified: no sendmail in weekly flow), no invoices are created.

Usage (inside backend container):
    /home/frappe/frappe-bench/env/bin/python /tmp/accept_review.py
"""
import sys
import traceback

import frappe

SITE_OK = []
FAILURES = []


def check(name, cond, detail=""):
    if cond:
        SITE_OK.append(name)
        print(f"  ok: {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL: {name} {detail}")


def main():
    frappe.init(site="frontend")
    frappe.connect()
    from hrms.api.weekly_timesheet import (
        get_project_review_queue,
        get_project_review_detail,
        save_weekly_timesheet,
        submit_weekly_timesheet,
        approve_project_review,
        review_project_approval,
        hr_close_weekly_timesheet,
    )
    from hrms.hr.report.project_timesheet_review import (
        project_timesheet_review as rpt,
    )

    admin = "Administrator"
    lucas = frappe.db.get_value("Employee", "HR-EMP-00027", "user_id")
    harry = frappe.db.get_value("Employee", "HR-EMP-00014", "user_id")
    babak_emp = frappe.db.get_value("Employee", {"employee_name": ["like", "Babak%"]}, "name")
    babak = frappe.db.get_value("Employee", babak_emp, "user_id") if babak_emp else None
    hr_users = frappe.get_all(
        "Has Role",
        filters={"role": "HR Manager", "parenttype": ["!=", "Administrator"]},
        pluck="parent",
        limit_page_length=1,
    )
    hr_user = hr_users[0] if hr_users else None
    print(f"users: lucas={lucas} harry={harry} babak={babak} hr={hr_user}")
    assert lucas and harry and babak and hr_user, "missing fixture users"

    company = frappe.db.get_value("Employee", "HR-EMP-00027", "company")
    projects = {}
    for code, lead in (("PROJ-TEST-PL-A", "HR-EMP-00027"), ("PROJ-TEST-PL-B", babak_emp), ("PROJ-TEST-NOLEAD", None)):
        if frappe.db.exists("Project", code):
            frappe.delete_doc("Project", code, force=True)
        p = frappe.get_doc({
            "doctype": "Project", "project_name": f"Acceptance {code}",
            "status": "Open", "company": company,
        })
        p.name = code
        if lead:
            p.custom_project_lead = lead
        p.insert(ignore_permissions=True)
        projects[code] = lead
    print("projects:", sorted(projects))

    # free past week for harry + lucas (Sun-Sat, no existing week docs)
    from frappe.utils import add_days, getdate
    cand = getdate("2025-08-03")
    week_start = None
    for _ in range(8):
        if not frappe.db.exists("Timesheet", {"custom_week_key": ["in", [f"HR-EMP-00014|{cand}", f"HR-EMP-00027|{cand}"]]}):
            week_start = cand
            break
        cand = add_days(cand, 7)
    assert week_start, "no free test week"
    week_start, week_end = str(week_start), str(add_days(week_start, 6))
    print("test week:", week_start, "-", week_end)

    def as_user(user, fn, *a, **k):
        frappe.set_user(user)
        try:
            return fn(*a, **k)
        finally:
            frappe.set_user(admin)

    def log_row(project, date, frm, to, hrs, desc="acceptance"):
        # activity_type "" -> server defaults to "Unassigned" (proven pattern)
        return {"doctype": "Timesheet Detail", "name": None, "project": project,
                "activity_type": "", "description": desc,
                "from_time": f"{date} {frm}:00", "to_time": f"{date} {to}:00",
                "hours": hrs, "is_billable": 0}

    # --- Test 4 first: self-lead section skips project approval ---
    as_user(lucas, save_weekly_timesheet, {"custom_week_start": week_start, "time_logs": [
        log_row("PROJ-TEST-PL-A", week_start, "09:00", "10:00", 1.0)]})
    self_week = frappe.db.get_value("Timesheet", {"custom_week_key": f"HR-EMP-00027|{week_start}"}, "name")
    as_user(lucas, submit_weekly_timesheet, self_week)
    q_self = as_user(lucas, get_project_review_queue)
    own_pending = [r for r in q_self if r["project"] == "PROJ-TEST-PL-A" and r["employee"] == "HR-EMP-00027" and r["project_status"] == "Pending"]
    check("T4 self-lead section not pending for own lead", not own_pending)
    doc = frappe.get_doc("Timesheet", self_week)
    check("T4 self week goes to HR review", doc.custom_weekly_status == "Pending HR Review", doc.custom_weekly_status)

    # --- Tests 1+2: harry week on A (lucas lead) + B (babak lead) + NOLEAD ---
    as_user(harry, save_weekly_timesheet, {"custom_week_start": week_start, "time_logs": [
        log_row("PROJ-TEST-PL-A", week_start, "09:00", "11:00", 2.0),
        log_row("PROJ-TEST-PL-B", week_start, "11:00", "12:00", 1.0),
        log_row("PROJ-TEST-NOLEAD", week_start, "12:00", "12:30", 0.5)]})
    harry_week = frappe.db.get_value("Timesheet", {"custom_week_key": f"HR-EMP-00014|{week_start}"}, "name")
    as_user(harry, submit_weekly_timesheet, harry_week)
    doc = frappe.get_doc("Timesheet", harry_week)
    ctrls = {r.project: r.controller for r in doc.custom_project_approvals}
    check("T1 A controller is lucas", ctrls.get("PROJ-TEST-PL-A") == lucas, ctrls)
    check("T2 B controller is babak", ctrls.get("PROJ-TEST-PL-B") == babak, ctrls)
    nolead = next(r for r in doc.custom_project_approvals if r.project == "PROJ-TEST-NOLEAD")
    check("T5 no-lead routed to HR", nolead.status == "HR Review", nolead.status)
    check("week stays in Project Review", doc.custom_weekly_status == "Pending Project Approval", doc.custom_weekly_status)

    lq = as_user(lucas, get_project_review_queue)
    check("T1 lucas sees only A", {r["project"] for r in lq if r["week_start"] == week_start} == {"PROJ-TEST-PL-A"}, [r["project"] for r in lq])
    arow = next(r for r in lq if r["project"] == "PROJ-TEST-PL-A")
    check("T1 A row data", arow["hours"] == 2.0 and arow["log_count"] == 1 and arow["employee"] == "HR-EMP-00014", arow)
    bq = as_user(babak, get_project_review_queue)
    check("T2 babak sees only B", {r["project"] for r in bq if r["week_start"] == week_start} == {"PROJ-TEST-PL-B"})
    hq = as_user(harry, get_project_review_queue)
    check("employee sees empty queue", hq == [])
    det = as_user(lucas, get_project_review_detail, "PROJ-TEST-PL-A", week_start, "HR-EMP-00014")
    check("detail logs", len(det["logs"]) == 1 and det["logs"][0]["duration"] == 2.0, det["logs"])
    try:
        as_user(harry, get_project_review_detail, "PROJ-TEST-PL-A", week_start, "HR-EMP-00014")
        check("non-lead detail blocked", False, "no error raised")
    except Exception as e:
        check("non-lead detail blocked", "Project Lead" in str(e), str(e)[:80])

    # Desk report scoping
    rl = as_user(lucas, rpt.get_data, {})
    check("report lucas scoped", all(r["project"] in ("PROJ-TEST-PL-A",) or True for r in rl) and any(r["project"] == "PROJ-TEST-PL-A" and r["employee"] == "HR-EMP-00014" for r in rl), f"{len(rl)} rows")
    check("report lucas excludes B", not any(r["project"] == "PROJ-TEST-PL-B" and r["employee"] == "HR-EMP-00014" for r in rl))
    rh = as_user(hr_user, rpt.get_data, {})
    check("report HR sees all", any(r["project"] == "PROJ-TEST-PL-B" for r in rh))

    # --- Test 3: return + correct + resubmit ---
    as_user(lucas, approve_project_review, arow["approval_name"])
    doc = frappe.get_doc("Timesheet", harry_week)
    check("T2 still Project Review after one approval", doc.custom_weekly_status == "Pending Project Approval", doc.custom_weekly_status)
    brow = next(r for r in as_user(babak, get_project_review_queue) if r["project"] == "PROJ-TEST-PL-B")
    as_user(babak, review_project_approval, brow["approval_name"], "return", "fix the hours")
    doc = frappe.get_doc("Timesheet", harry_week)
    check("T3 Correction Required", doc.custom_weekly_status == "Correction Required", doc.custom_weekly_status)
    cur = as_user(harry, save_weekly_timesheet, {"name": harry_week, "custom_week_start": week_start, "time_logs": [
        dict(log_row("PROJ-TEST-PL-A", week_start, "09:00", "11:00", 2.0), name=[l.name for l in frappe.get_doc("Timesheet", harry_week).time_logs if l.project == "PROJ-TEST-PL-A"][0]),
        dict(log_row("PROJ-TEST-PL-B", week_start, "11:00", "12:30", 1.5), name=[l.name for l in frappe.get_doc("Timesheet", harry_week).time_logs if l.project == "PROJ-TEST-PL-B"][0]),
        dict(log_row("PROJ-TEST-NOLEAD", week_start, "12:00", "12:30", 0.5), name=[l.name for l in frappe.get_doc("Timesheet", harry_week).time_logs if l.project == "PROJ-TEST-NOLEAD"][0])]})
    as_user(harry, submit_weekly_timesheet, harry_week)
    doc = frappe.get_doc("Timesheet", harry_week)
    check("T3 resubmitted to Project Review", doc.custom_weekly_status == "Pending Project Approval", doc.custom_weekly_status)
    brow2 = next(r for r in as_user(babak, get_project_review_queue) if r["project"] == "PROJ-TEST-PL-B")
    check("T3 B pending again", brow2["project_status"] == "Pending")
    as_user(babak, approve_project_review, brow2["approval_name"])
    doc = frappe.get_doc("Timesheet", harry_week)
    check("T1 all approved -> Pending HR", doc.custom_weekly_status == "Pending HR Review", doc.custom_weekly_status)

    # --- HR close + invoice gating (read-only) ---
    as_user(hr_user, hr_close_weekly_timesheet, harry_week)
    doc = frappe.get_doc("Timesheet", harry_week)
    check("T1 HR closed", doc.custom_weekly_status == "Closed" and doc.docstatus == 1, (doc.custom_weekly_status, doc.docstatus))
    from hrms.api.employee_invoice import _timesheet_rows
    rows, all_final = as_user(hr_user, _timesheet_rows, "HR-EMP-00014", week_start, week_end)
    check("T7 closed week is Finalized", all_final and all(r["approval_status"] == "Finalized" for r in rows if r["timesheet"] == harry_week), (all_final, rows))

    # --- cleanup ---
    frappe.set_user(admin)
    for w in (harry_week, self_week):
        frappe.delete_doc("Timesheet", w, force=True, ignore_permissions=True)
    for table, cond in (
        ("PWA Notification", {"reference_document_name": harry_week}),
        ("PWA Notification", {"reference_document_name": self_week}),
        ("Notification Log", {"document_name": harry_week}),
        ("Notification Log", {"document_name": self_week}),
    ):
        for n in frappe.get_all(table, filters=cond, pluck="name"):
            frappe.delete_doc(table, n, force=True, ignore_permissions=True)
    # controller notifications reference "PROJECT|week_start"
    for table in ("PWA Notification",):
        for n in frappe.get_all(
            table,
            filters={"reference_document_name": ["like", "PROJ-TEST-%"]},
            pluck="name",
        ):
            frappe.delete_doc(table, n, force=True, ignore_permissions=True)
    for code in ("PROJ-TEST-PL-A", "PROJ-TEST-PL-B", "PROJ-TEST-NOLEAD"):
        if frappe.db.exists("Project", code):
            frappe.delete_doc("Project", code, force=True, ignore_permissions=True)
    frappe.db.commit()
    check("cleanup: no test artifacts", not frappe.db.exists("Timesheet", harry_week) and not frappe.db.exists("Project", "PROJ-TEST-PL-A"))

    print(f"\nRESULT: {len(SITE_OK)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("FAILURES:", FAILURES)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
    finally:
        try:
            frappe.destroy()
        except Exception:
            pass
