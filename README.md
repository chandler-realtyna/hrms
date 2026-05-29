# Realtyna HRMS

A customised fork of [Frappe HRMS](https://github.com/frappe/hrms) built for Realtyna's internal team.  
Base version: **HRMS 16** on the `version-16` branch.

---

## What's different from the original HRMS?

The original Frappe HRMS is a full-featured HR platform with dozens of modules (Recruitment, Performance, Payroll, Attendance, Shifts, and more). This fork strips that back to the workflows Realtyna actually uses and adds tools that make the day-to-day faster.

---

### 1. Clockify-style Time Tracker

The original HRMS requires you to open a Timesheet form, add rows manually, fill in start/end times, and save. This fork replaces that with a **live timer**:

- Hit **Start** and describe what you're working on (Activity Type, Project, optional note)
- Hit **Stop** — a submitted Timesheet is created automatically
- **Discard** cancels the session without saving anything
- The timer survives page navigation (stored in `localStorage`)
- Lives at **Quick Links → Start Timer** on the Home screen and in the sidebar

All time logs are marked **billable by default**. A new `save_timer_log` API endpoint in `hrms/api/__init__.py` finds or creates the right Timesheet for the day and appends the log to it.

---

### 2. Desktop Layout with Sidebar

The original HRMS is a mobile-first PWA — on desktop it renders a narrow column centred on screen. This fork adds a **full desktop layout**:

- A **256 px sidebar** (`DesktopSidebar.vue`) appears at the `md:` breakpoint and above
- The sidebar contains branding, user info, notification bell, and a sectioned nav with **collapsible sections** (state persisted in `localStorage`)
- The main content area fills the remaining width
- Mobile view is unchanged — the sidebar hides and the bottom tab bar appears as before

---

### 3. Simplified Timesheet Form

The original Timesheet form has ~20 fields (billing rate, exchange rate, company, employee, currency…). This fork trims it to what an employee actually needs:

| Field | Notes |
|---|---|
| **Time Logs** | Table of individual work sessions — duration + description only |
| **Note** | Free-text description or summary |
| **Attachment** | File upload |

Everything else (employee, company, dates, totals) is auto-filled by the system on save. Each time log row is **editable after the fact** — click the pencil icon to open the edit modal pre-filled with that row's values.

---

### 4. Home Screen Dashboard

The original home screen is a grid of links. This fork adds a **Working Hours Dashboard** directly on the home page:

- **Period selector** — Week (7 days), 2 Weeks (14 days), Month (30 days)
- **Total hours** for the period, displayed prominently
- **Bar chart** of hours per day — today highlighted in blue, zero-days in light grey
- **My Projects** section — top projects ranked by hours logged, with a proportional bar

Data comes from `get_working_hours_summary` and `get_employee_project_summary` API endpoints.

---

### 5. Employee Schedule

A new **Employee Schedule** doctype lets employees define their typical weekly working hours — multiple time slots per day (e.g. 9–12 and 13–17 on Monday). The mobile UI lets employees:

- Add/remove time slots per day of the week
- Submit for HR Manager approval
- Receive an **email notification** when their schedule is approved or rejected

The schedule feeds directly into the Team Availability view and the public booking page.

Backend: `hrms/doctype/employee_schedule/` · Frontend: `frontend/src/views/schedule/`

---

### 6. Employee Holiday

A new **Employee Holiday** doctype lets employees select their personal holidays (from a pool defined by HR). The mobile UI shows a calendar picker with available dates. Selections are submitted for HR Manager approval, and employees receive an **email notification** on the outcome.

Backend: `hrms/doctype/employee_holiday/` · Frontend: `frontend/src/views/holiday/`

---

### 7. Team Availability

A dedicated **Team Availability** screen shows when your colleagues are free across three display modes:

| Mode | Description |
|---|---|
| **Timezone view** | Each team member shown in their local timezone |
| **Working-hours view** | Grid of who is working at each hour of the day |
| **Calendar view** | Week-at-a-glance heat map of team availability |

Availability is derived from each employee's approved schedule and holidays. The view is accessible from the Home screen and the desktop sidebar.

---

### 8. Google Calendar Integration & Meeting Booking

A full Google Calendar integration lets employees connect their Google account and enables two booking workflows:

#### Public Booking Page
Each employee gets a **public booking page** (`/hrms/book/:slug`) where external visitors can:
- Browse available time slots (pulled live from Google Calendar's freebusy API, respecting the employee's working hours and holidays)
- Pick a slot and fill in their name, email, and meeting details
- Receive a Google Meet link via a calendar invite on both sides

Employees configure their page from **Settings → Booking**, where they set a custom slug, meeting duration, buffer time, and toggle the page on/off.

#### Meeting Finder (internal)
The **Find Meeting Slots** tool lets any employee find a time that works for the whole team:
- Select a set of team members and a date range
- The tool queries each member's Google Calendar and finds overlapping free slots
- Results show timezone-aware times and can be booked directly

#### Google Calendar Connect
Employees link their Google account from **Settings → Calendar** (or the dedicated **Connect Google Calendar** page). The OAuth popup closes automatically after authorisation and the app shows a success state without needing a page reload.

**Backend:** `hrms/api/calendar.py` — `get_google_calendar_authorize_url`, `get_calendar_connection_status`, `create_booking`, `find_meeting_slots`, `send_meeting_invitation`

**Frontend:** `frontend/src/views/calendar/` and `frontend/src/views/booking/`

---

### 9. Dark Mode

The app detects the user's system preference and switches between light and dark themes automatically. A **manual toggle** in Settings lets the user override the system default. The chosen preference is persisted in `localStorage`.

All views, modals, and form inputs have been updated for dark-mode compatibility, including proper text contrast, background colours, and icon colours for Ionic components.

---

### 10. Timezone-Aware Features

All time-related features use the **viewer's local timezone**:

- Booking slots on public booking pages are displayed in the visitor's browser timezone
- Google Calendar events are created using the employee's/organiser's timezone
- The Meeting Finder shows results in each participant's local time
- Slot cutoff logic (hiding past slots) is UTC-based to avoid edge cases at midnight

---

### 11. Attendance & Shift Features Removed

Realtyna tracks time through Timesheets, not attendance punches. The following have been removed from the UI:

- Bottom tab bar (mobile)
- Desktop sidebar navigation
- Home screen Quick Links
- Request Panel (pending items widget)

The underlying doctypes still exist in Frappe — only the frontend entry points are removed.

---

### 12. Permission & Settings Patches

Applied automatically on `bench migrate`:

| Change | Why |
|---|---|
| `Employee` role gets `submit=1` on Timesheet | Without this, employees can save but not submit their own timesheets |
| `Projects Settings.ignore_employee_time_overlap = 1` | Prevents a 417 error when two time logs touch the same minute |
| HR Setup workspace shortcuts for Employee Schedule and Employee Holiday | Makes the new doctypes reachable from the HR manager's workspace |

---

### 13. Navigation Direction Fix

Ionic Vue's `ion-router-outlet` maintains a navigation stack. Every sidebar link and tab button uses `routerDirection="root"` to ensure navigation always loads the target page fresh instead of triggering a back-animation.

---

### 14. CI/CD Pipeline

A GitHub Actions workflow (`.github/workflows/deploy.yml`) automates production deployments:

1. **Build** — checks out the HRMS repo, fetches `frappe/frappe_docker`, encodes `apps-production.json`, and builds a Docker image using the layered Containerfile. The image is pushed to GitHub Container Registry tagged `:production` and `:<git-sha>`.
2. **Deploy** — SSHes into the production server, pulls the new image, recreates app containers (DB and Redis are left running for zero data-layer downtime), waits for the backend to start, runs `bench migrate`, and clears the cache.

Triggers on every push to `version-16` and can also be run manually from the GitHub Actions UI.

Required secrets: `PROD_SSH_HOST`, `PROD_SSH_USER`, `PROD_SSH_KEY`, `PROD_SSH_PORT`, `PROD_SITE_NAME`, `PROD_COMPOSE_PATH`, `GHCR_TOKEN`.

---

## Screens at a glance

| Screen | Path | Notes |
|---|---|---|
| Home | `/home` | Working hours dashboard + quick links + request panel |
| Timer | `/timesheets/timer` | Live Clockify-style timer |
| My Timesheets | `/timesheets` | List of your timesheets |
| Timesheet Detail | `/timesheets/:id` | Simplified form (Time Logs, Note, Attachment) |
| Employee Schedule | `/schedule` | Define weekly working hours, submit for approval |
| Employee Holiday | `/holiday` | Select personal holidays, submit for approval |
| Team Availability | `/availability` | Timezone / working-hours / calendar views |
| Connect Calendar | `/calendar/connect` | OAuth flow to link Google Calendar |
| Booking Settings | `/settings` | Manage slug, duration, buffer, toggle booking page |
| Public Booking | `/book/:slug` | External-facing booking page (unauthenticated) |
| Leaves | `/dashboard/leaves` | Leave application and balance |
| Expenses | `/dashboard/expense-claims` | Expense claims |
| Salary Slips | `/dashboard/salary-slips` | View payslips |
| Profile / Settings | `/profile` | User profile and dark mode toggle |

---

## Key files changed vs upstream

```
frontend/src/
├── views/
│   ├── Home.vue                          # Working hours dashboard + updated quick links
│   ├── timesheet/
│   │   ├── Timer.vue                     # NEW — live Clockify-style timer
│   │   └── Form.vue                      # Simplified to duration + description
│   ├── schedule/                         # NEW — Employee Schedule mobile UI
│   ├── holiday/                          # NEW — Employee Holiday mobile UI
│   ├── availability/                     # NEW — Team Availability (3 display modes)
│   ├── calendar/
│   │   ├── CalendarConnect.vue           # NEW — Google OAuth connect + popup close detection
│   │   └── CalendarSettings.vue         # NEW — booking slug, duration, buffer settings
│   └── booking/                         # NEW — public booking page (unauthenticated)
├── components/
│   ├── DesktopSidebar.vue                # NEW — desktop nav sidebar with collapsible sections
│   ├── WorkingHoursDashboard.vue         # NEW — hours bar chart + projects
│   ├── BottomTabs.vue                    # Removed attendance; fixed routerDirection
│   ├── BaseLayout.vue                    # Responsive width; header hidden on desktop
│   ├── RequestPanel.vue                  # Removed shift/attendance requests
│   ├── TimeLogsTable.vue                 # Added edit (pencil) button per row
│   ├── FormView.vue                      # Removed narrow mobile constraints
│   └── ListView.vue                      # Removed narrow mobile constraints
├── router/
│   ├── index.js                          # Removed attendance route; added schedule/holiday/booking
│   └── timesheets.js                     # Added /timesheets/timer route
└── App.vue                               # Added sidebar slot; showSidebar guard

hrms/
├── api/
│   ├── __init__.py                       # save_timer_log, get_working_hours_summary,
│   │                                     #   get_employee_project_summary
│   └── calendar.py                       # get_google_calendar_authorize_url,
│                                         #   get_calendar_connection_status,
│                                         #   create_booking, find_meeting_slots,
│                                         #   send_meeting_invitation, get_booking_settings
├── doctype/
│   ├── employee_schedule/                # NEW — schedule doctype + controller
│   └── employee_holiday/                 # NEW — holiday doctype + controller
├── overrides/
│   └── whitelisted_methods.py            # google_callback override (popup redirect fix)
│                                         # get_single_value override (permission fix)
├── hooks.py                              # Registers override_whitelisted_methods
├── www/
│   └── google-calendar-success.html      # NEW — self-closing OAuth popup success page
├── patches/v16_0/
│   └── configure_timesheet_for_mobile_timer.py   # submit permission + overlap setting
└── demo_setup.py                         # Demo data script (leave types, users, salary slips)

.github/
├── workflows/
│   └── deploy.yml                        # NEW — build Docker image + SSH deploy to production
└── helper/
    └── apps-production.json              # NEW — app list for frappe_docker image build
```

---

## Setup

See [SETUP.md](../../SETUP.md) in the bench root for the full setup guide (bench install, site creation, first run).

A demo data script is included to pre-populate leave types, users, and salary slips:

```bash
bench --site hr.localhost execute hrms.demo_setup.execute
```

This creates:

- **8 leave types** — Annual, Sick, Casual, Maternity, Paternity, Bereavement, Study, Unpaid
- **HR Manager** — `sarah.johnson@realtyna.net` (password: `Realtyna@2024!`)
- **Employee** — `james.wilson@realtyna.net` (password: `Realtyna@2024!`)
- **3 months of Salary Slips** for the primary employee

---

## Original HRMS

Full documentation for the upstream project: https://docs.frappe.io/hrms

Source: https://github.com/frappe/hrms
