# Timetable and calendar (TTC)

This module covers the school holiday and event calendar (holidays belong to an academic year and are managed on a month calendar and an "All Events" list) and the weekly class timetable (one grid per section: rows are time ranges, columns are days, with subject rows, special rows such as Snacks or Lunch, and an optional Saturday). It also covers the read-only views: the mobile school calendar for every role and the mobile student and parent timetable viewer. The page is the specification for the TTC test cases and is ordered the way an admin meets the work: holidays for the year first, then the timetable (view, build and save, editing tools, delete, export), then the read-only consumers and the legacy slot endpoints. Classes, sections, subjects and class-subject mappings that the timetable depends on are in `docs/features/masters.md` (code MST); the holiday message button on the list belongs to Communication (COM).

_Last verified against code: 2026-10-07_

Module rules, gotchas and code map: `docs/modules/timetable-calendar.md`. Flows and decisions: `docs/graph/views/timetable-calendar.md`. Test conventions and IDs: `docs/testing/strategy.md`.

Unit tests (U) implemented in: `backend/tests/unit/timetable_calendar/test_ttc_*.py`, `mobile/__tests__/timetable_calendar/` (TC-TTC-06-U11). Every web and the other mobile U row is blocked because the logic lives unexported inside component files. Tests whose names end `_defect_kgN` assert today's behaviour of a Known gaps item.

## Roles

Access is decided per resource (`docs/permissions.md`). The grants below are the default seed (`ROLE_PERMISSIONS` in `backend/app/service/tenant/permission_catalog.py`) that `qa_school` is provisioned with.

| Resource | Admin | Staff | Teacher | Student | Parent |
|---|---|---|---|---|---|
| `holiday_management` | create, read, update, delete, list | read, list | read, list | none | none |
| `timetable_management` | create, read, update, delete, list | none | none | none | none |

Consequences of the default seed (see Known gaps): Student and Parent cannot read holidays or timetables through the API, so the mobile calendar and the student and parent timetable viewer receive 403 for them; Staff and Teacher can read holidays but cannot read timetables. Menu: Admin, Staff and Teacher receive every menu (web sidebar "Masters > Holidays", "Timetable", "Calendar"; mobile Dashboard "Modules" tiles "Timetable" and "Calendar" and the Masters hub card "Holidays"); Student and Parent receive only the self-service allowlist, which contains neither `/TimeTable` nor `/Calender`. The web routes have no route guard, so a Student or Parent who types `/Calender` still sees the (empty) calendar.

Web permission names: the web calendar checks `holidays:*` (alias names) while the backend enforces `holiday_management:*`; the web timetable editor checks `timetable_management:update` (correct); the mobile screens check `holiday_management` and `timetable_management` (correct). The default Admin grant has no `holidays` rows, so the web calendar Add Event, Edit and Delete controls stay hidden unless the tenant also holds `holidays:create`, `holidays:update` and `holidays:delete` (the Teacher and Staff web caps already include `holidays: read, list`).

## Conventions used by the test cases

- API base `/api/v1`; phase 2 tests run on `qa_school` (`docs/testing/test-environment.md`). The QA baseline holds no master data: each test creates a year, a class with sections, subjects and (for timetables) uses their ids, with names prefixed `QA-<run id>`, and removes them. Phase 3 specs seed the same through API fixtures.
- Web E specs for holidays run with the `holidays:*` alias grants added to Admin by a fixture; one case records the default (controls hidden).
- A "403" case means status 403 with `detail` starting `Permission not found in database`. Validation (422) runs before the permission check, so role-matrix tests send valid bodies.
- Returned timetable rows are not in time order: tests sort `timetable_data` by `time.from` before comparing.
- Create endpoints are rate limited per client IP (holiday create 30 per minute); the timetable endpoints are not rate limited.
- Tenant isolation pattern: data created in tenant A is invisible to tenant B (404 or empty list), and a tenant A token with a `cschema` header naming B gets 403.
- Backend unit tests (`backend/tests/unit/timetable_calendar/`) use fake sessions; web unit tests use vitest and mobile unit tests use jest. Functions that live inside a component file and are not exported (called out per feature) must be extracted or exported first.
- UI (E) cases are written for manual execution on the seeded manual-test tenant `qa_manual` (organisation `qa_manual` at sign-in; `backend/scripts/qa/setup_manual_tenant.py`, data from `backend/scripts/seed_demo_data.py`) with the QA logins for Admin, Staff and Teacher. The QA Student and Parent logins are not linked to a student; cases that need a real student or parent use a seeded login (student login = admission number, parent login = email; first-login password change done). Seeded data the cases use:
  - Holidays in the working year: Independence Day (2026-08-15), Ganesh Chaturthi (2026-09-14), Gandhi Jayanti (2026-10-02), Dasara Vacation (2026-10-17 to 2026-10-24), Diwali (2026-11-08), Christmas (2026-12-25), Sankranti Break (2027-01-13 to 2027-01-16), Republic Day (2027-01-26), all active.
  - Timetables for sections 1-A, 1-B (Class 1) and 2-A, 2-B (Class 2), Monday to Friday, eight rows: subject rows 9:00-10:00, 10:00-10:45, 11:00-11:45, 11:45-12:30, 13:15-14:00, 14:00-14:45, special rows SNACKS 10:45-11:00 and LUNCH 12:30-13:15, no Saturday. Classes Nursery, LKG, UKG and Class 3 to Class 5 have no timetable.
  - Class 3 (3-A, 3-B) has 8 of the 10 subjects mapped (English, Hindi, Telugu, Mathematics, General Science, Social Studies, Computer Science, Physical Education); Environmental Studies and Art and Craft are not mapped to it.
  - Students Advik Mehta (002) and Harsha Raju (004) in Class 1; Harsha's sister Tanvi Raju (005) in Class 4; parent login venkat.raju@example.com for Harsha and Tanvi.
  - Cases that create holidays or timetables use names starting "QA " or a section without a timetable (Class 3 to Class 5), and the tester removes what they created (holidays: delete; timetables: `DELETE /students/timetable/frontend/{section_id}`, F09). Do not change the seeded holidays or timetables except where a case says to restore them.
- The web holiday "+ Add Event", "Save", "Delete", "Edit Event" and "Delete Event" controls are hidden for the default Admin (Known gaps 1). Web cases that need them are `blocked` until the `holidays:*` alias grant exists or the code is fixed; creating through a day cell and drag and drop work without it.

## Feature index

| ID | Title |
|---|---|
| F01 | Holiday calendar and event list |
| F02 | Create a holiday or event |
| F03 | Edit and reschedule a holiday |
| F04 | Delete (deactivate) and restore a holiday |
| F05 | Holiday single read and dropdown |
| F06 | Timetable: select a section and view it |
| F07 | Timetable: build and save (create and replace) |
| F08 | Timetable editing tools: Saturday, special rows, custom events, repeat |
| F09 | Delete a section timetable |
| F10 | Timetable export (PNG, CSV, Excel) |
| F11 | Student and parent timetable viewer (mobile) |
| F12 | School calendar, read-only (mobile) |
| F13 | Legacy timetable endpoints: bulk create, grouped read, slot patch, test |

---

## F01 Holiday calendar and event list

**Purpose.** Admin, Staff and Teacher see the year's holidays and events on a month calendar or as a searchable list.

**Roles and permissions.** Backend: list `holiday_management:list`, single read `holiday_management:read`. Admin, Staff and Teacher hold both; Student and Parent hold neither. Web Month and All Events views render for everyone who can open the page; the Add, Edit and Delete controls need `holidays:create`, `holidays:update`, `holidays:delete`. Menu: web Masters > Holidays (`/masters/holidays`) and the top-level "Calendar" entry (`/Calender`) open the same component; mobile Masters tab > Holidays (admin screen).

**Preconditions.** An academic year selected as the working year (MST F01 and F02). Holidays exist (F02).

**Steps, web.**
1. Open Masters > Holidays (or the sidebar entry "Calendar"; breadcrumb "Masters > Holidays" or "Calender"). Card "Holidays" with the buttons "Month" and "All Events" (Week, Day and Year views are disabled in code), "<" and ">" for the previous and next month, the month and year labels (click the month name to pick a month, the year to pick a year from -10 to +10), and "+ Add Event" (only with `holidays:create`, so hidden for the default Admin).
2. Month view: a Sunday-first grid with headers Sun to Sat. Single-day events show as coloured chips inside the day cell (name and the description cut at 40 characters); multi-day events show as bars over the week. Today is highlighted. Clicking an event opens the Edit Event dialog (F03); clicking a day opens Add Event for that day (F02), for every role.
3. "All Events" view: a "Filters" label with the box "Search events..." (title and description of the current page), sortable headers Title, Start Date, End Date (click toggles ascending and descending), columns S.No., Title, Description (cut at 60 characters with "...", "-" when empty), Start Date, End Date (`YYYY-MM-DD`), Color (swatch), Actions (message button "Send Holiday Message to all parents" with `communications:create`, "Edit Event", "Delete Event"). Clicking the title opens Edit Event. Paging: "Prev", "Page n", "Next" with 10 events per page; "Next" is disabled when a page returns fewer than 10. Empty text "No events" or "No events match your search"; failure "Failed to load events".
4. The month view requests `academic_year_id` only, so it receives at most 10 events (default limit); the list view requests 10 per page.

**Steps, mobile.**
1. Masters tab (or the Dashboard "Masters" tile) > "Holidays". Header "Holidays" with a back arrow ("Go back"), tabs "Month" and "All Events", "Add Event" (create permission only), month arrows ("Previous month", "Next month") and the label "<Month> <year>" ("Select month and year"), which opens a picker with "Previous year" and "Next year" arrows and a grid of month names Jan to Dec; tapping a month jumps there.
2. All Events: "Filters", "Search events..." (with "Clear search"), sort chips "Title", "Start", "End" (accessibility labels "Sort by Title" and so on), cards with the title, date range (`start to end` or one date), description, message button, "Edit Event" and "Delete Event" buttons, and "Prev", "Page n", "Next" (10 per page). Empty texts as web; failure text "Failed to load events".
3. Month view behaves like web without drag and drop; tapping a day opens Add Event for every role; the request has no limit, so at most 10 events appear.
4. A role without holiday read or list sees "Access Denied - You don't have permission to view holidays". Student and Parent have no Masters tab. The read-only view for all roles is F12.

**Expected results.** Only active holidays of the working year appear; each shows its name, dates and colour; list paging, search and sort act on the loaded page only.

**API endpoints.** Prefix `/api/v1/masters/holidays`.
- `GET /` query `skip=0`, `limit=10`, `active_only=true`, `academic_year_id?` -> `{items, total_count, has_next}` (no ordering guarantee).

**Rules and validations.**
1. Defaults are `limit=10` and `active_only=true`; any client that needs more must pass an explicit `limit`. There is no upper bound on `limit`; negative `skip` or `limit` returns 400 `Invalid query parameters.`
2. `has_next` is `(skip + limit) < total_count`.
3. A holiday created with `is_active=false` (the schema default) is hidden from default lists.
4. Search and sort are client-side over the loaded page.
5. Holidays are display-only: attendance, timetable and fee logic do not read them.
6. Day cells open the Add Event dialog even for users without create permission (web and mobile); the API then answers 403 and the toast "Failed to create holiday" (web) or "Create Failed" (mobile) appears.

**Error and edge cases.**
- Empty year: month grid shows no events; list shows "No events".
- List failure: "Failed to load events".
- Student and Parent receive 403 from the API.

**Unit-testable logic.**
- Backend `get_all_holidays` filter composition (`active_only`, `academic_year_id`) and `has_next` with a fake session.
- Web `getMonthDays` (Sunday-start grid covering the month), multi-day versus single-day event split, `filteredAndSortedEvents` search and sort; mobile equivalents (`buildMonthGrid`, `getHolidaysForDate`, filter, sort). These helpers live inside `Calendar.tsx` and `masters/holidays.tsx` and need extracting.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-01-U01 | [backend] `get_all_holidays(active_only=True, academic_year_id=Y)` with a fake session | Generated queries filter `is_active` and the year for both the page and the count | passing |
| TC-TTC-01-U02 | [backend] `has_next` for (skip 0, limit 10, total 11), (skip 10, limit 10, total 11), (0, 10, 10) | True, False, False | passing |
| TC-TTC-01-U03 | [web] `getMonthDays(2026-10-15)` | Starts on Sunday 27 Sep and ends on Saturday 31 Oct (35 cells) | blocked: needs getMonthDays exported from web/src/components/calendar/Calendar.tsx |
| TC-TTC-01-U04 | [web] Event 10 to 12 Oct and event 14 Oct on the same week | First is multi-day (bar), second single-day (chip) | blocked: needs the multi-day versus single-day split exported from web/src/components/calendar/Calendar.tsx |
| TC-TTC-01-U05 | [web] All Events search `diwali` over name and description, then sort Start Date descending | Case-insensitive filter; later dates first | blocked: needs filteredAndSortedEvents exported from web/src/components/calendar/Calendar.tsx |
| TC-TTC-01-U06 | [mobile] `buildMonthGrid(2026, 9)` and `getHolidaysForDate("2026-10-12")` | Weeks of 7 cells with null padding; returns holidays whose range includes that date | blocked: needs buildMonthGrid and getHolidaysForDate exported from mobile/app/masters/holidays.tsx |
| TC-TTC-01-A01 | Admin `GET /masters/holidays/` default with 12 active holidays in the year | `items` length 10, `total_count` 12, `has_next` true | passing |
| TC-TTC-01-A02 | `GET /?skip=10&limit=10` | 2 items, `has_next` false | passing |
| TC-TTC-01-A03 | `GET /?limit=100&academic_year_id=Y` | All 12 items of year Y only; none from another year | passing |
| TC-TTC-01-A04 | `GET /` with one inactive holiday; then `?active_only=false` | Inactive hidden by default; present with `active_only=false` | passing |
| TC-TTC-01-A05 | `GET /?skip=-1`; `GET /?limit=-1` | 400 `Invalid query parameters.` | passing |
| TC-TTC-01-A06 | Item shape | Each item has `id, name, description, start_date, end_date, is_active, academic_year_id, color` with dates as `YYYY-MM-DD` | passing |
| TC-TTC-01-A07 | Read matrix: `GET /` as Admin, Staff, Teacher | 200 | passing |
| TC-TTC-01-A08 | `GET /` as Student and Parent | 403 each | passing |
| TC-TTC-01-A09 | No Authorization header | 401 | passing |
| TC-TTC-01-A10 | Tenant isolation: tenant B `GET /` and `GET /?academic_year_id=<A's year>` | Empty `items`; A token with B `cschema` header gets 403 | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-01-E01 | P1 | Web | Admin | Seeded holidays (8, all active); the month shown is October 2026 (use ">" or "<" to reach it) | 1. Sign in as Admin.<br>2. Open Masters > Holidays. | Card "Holidays" with "Month" active, "All Events", "<", ">", the month and year label; headers Sun to Sat; "Gandhi Jayanti" as a green chip on 2 Oct with "National holiday" under it; "Dasara Vacation" as a yellow bar from Sat 17 Oct and from Sun 18 to Sat 24 Oct; today's cell highlighted when it is in October 2026 | planned |
| TC-TTC-01-E02 | P2 | Web | Admin | Seeded holidays (8, all active) | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click ">".<br>4. Click "<".<br>5. Click the month name and choose "December".<br>6. Click the year and choose the next year. | Label shows the next month (Diwali on 8 Nov when it is November 2026), then the start month again; then December with "Christmas" on 25 Dec 2026; then December 2027 with no events | planned |
| TC-TTC-01-E03 | P1 | Web | Admin | Seeded holidays (8, all active) | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click "All Events". | "Filters" label, "Search events..." box, columns S.No., Title, Description, Start Date, End Date, Color, Actions; one row per holiday with dates as `YYYY-MM-DD`, a colour swatch, "-" for an empty description; "Prev" disabled, "Page 1" | planned |
| TC-TTC-01-E04 | P2 | Web | Admin | Seeded holidays (8, all active) | 1. Sign in as Admin.<br>2. Open Masters > Holidays > "All Events".<br>3. Type "diwali" in "Search events...".<br>4. Replace the text with "zzz". | Step 3: only the "Diwali" row (case-insensitive). Step 4: "No events match your search" | planned |
| TC-TTC-01-E05 | P3 | Web | Admin | Seeded holidays (8, all active) | 1. Sign in as Admin.<br>2. Open Masters > Holidays > "All Events".<br>3. Click the "Title" header twice.<br>4. Click the "Start Date" header twice. | Title ascending then descending (up then down chevron); Start Date ascending then descending; only the loaded page is sorted | planned |
| TC-TTC-01-E06 | P2 | Web | Admin | Seeded holidays (8) plus 4 holidays "QA H01" to "QA H04" created on mobile as in TC-TTC-02-E07 (12 active) | 1. Sign in as Admin.<br>2. Open Masters > Holidays > "All Events".<br>3. Click "Next".<br>4. Click "Prev". | Page 1 shows 10 rows (S.No. 1 to 10) and "Next" enabled; page 2 shows "Page 2", 2 rows numbered 11 and 12 and "Next" disabled; "Prev" returns to page 1 | planned |
| TC-TTC-01-E07 | P3 | Web | Admin | TC-TTC-01-E06 preconditions (12 active holidays in the year), with "QA H01" to "QA H04" dated in October 2026 | 1. Sign in as Admin.<br>2. Open Masters > Holidays (Month view).<br>3. Go to October 2026 and to the other months that hold holidays.<br>4. Count the events drawn over all months. | Only 10 of the 12 holidays are drawn across the months (default `limit=10`); some October events can be missing. Records Known gaps 4 | planned |
| TC-TTC-01-E08 | P3 | Web | Admin | Seeded holidays (8, all active) | 1. Sign in as Admin.<br>2. Click "Calendar" in the sidebar. | URL `/Calender`, breadcrumb "Calender"; the same "Holidays" card and events as Masters > Holidays | planned |
| TC-TTC-01-E09 | P2 | Web | Teacher | Seeded holidays (8, all active) | 1. Sign in as Teacher.<br>2. Open Masters > Holidays.<br>3. Click "All Events". | Month grid and list show the events; no "+ Add Event"; no "Edit Event" or "Delete Event" icons in Actions (the default Admin sees the same, Known gaps 1) | planned |
| TC-TTC-01-E10 | P3 | Web | Teacher | Working year of `qa_manual` selected | 1. Sign in as Teacher.<br>2. Open Masters > Holidays.<br>3. Click an empty day cell. | The "Add Event" dialog opens with that date in both date pickers (no permission check, Known gaps 2) | planned |
| TC-TTC-01-E11 | P2 | Web | Student | QA Student and QA Parent logins | 1. Sign in as Student.<br>2. Look at the sidebar.<br>3. Sign out and repeat as Parent. | Sidebar shows Dashboard, Students, Fee, Exam only: no Masters, Timetable or Calendar entry; Parent: same | planned |
| TC-TTC-01-E12 | P1 | Mobile | Admin | Seeded holidays (8, all active) | 1. Sign in as Admin on mobile.<br>2. Open the Masters tab.<br>3. Tap "Holidays". | Header "Holidays" with a back arrow, tabs "Month" and "All Events", "Add Event", month label "<Month> <year>" with previous and next arrows, Sun to Sat grid with the chips and the "QA Break" bar | planned |
| TC-TTC-01-E13 | P2 | Mobile | Admin | TC-TTC-01-E06 preconditions (12 active holidays) | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap "All Events".<br>4. Type "Diwali" in "Search events...".<br>5. Tap "Clear search".<br>6. Tap the sort chip "Title" twice.<br>7. Tap "Next". | Step 4: only "Diwali". Step 6: cards ascending then descending by title. Step 7: "Page 2" with 2 cards and "Next" disabled | planned |
| TC-TTC-01-E14 | P3 | Mobile | Admin | Working year of `qa_manual` selected | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap the month label.<br>4. Tap "Next year".<br>5. Tap "Mar". | The picker shows the year with arrows and a Jan to Dec grid; after step 5 it closes and the calendar shows "March <next year>" | planned |
| TC-TTC-01-E15 | P2 | Mobile | Teacher | Seeded holidays (8, all active) | 1. Sign in as Teacher on mobile.<br>2. Open Masters > Holidays.<br>3. Tap "All Events". | Events visible; no "Add Event" button; cards show only the message button (no "Edit Event" or "Delete Event") | planned |
| TC-TTC-01-E16 | P3 | Web | Student | QA Student login | 1. Sign in as Student.<br>2. Type `/Calender` in the address bar. | The "Holidays" card renders with an empty month grid and no error message (no route guard; the list call returns 403 silently). Records the missing route guard | planned |

---

## F02 Create a holiday or event

**Purpose.** An admin adds a holiday or event with a title, a date range, a colour and a description.

**Roles and permissions.** API: `holiday_management:create` (Admin only). Web button: `holidays:create`. Mobile button: `holiday_management:create`.

**Preconditions.** An academic year is selected (F01; without it the web Add button does nothing).

**Steps, web.**
1. Click "+ Add Event" (dates default to today; shown only with `holidays:create`) or click a day cell (that day is prefilled; works for every role).
2. Dialog "Add Event" ("Fill in the details to add a new holiday event to the calendar."): Title* (placeholder "Event title"), Date Range* (two date pickers separated by "to"), Event Color (colour input "Pick event color", default `#2563eb`, with a swatch), Description (placeholder "Event description"). Buttons "Add" and "Cancel".
3. Click "Add" ("Adding..."). Toast "Holiday created!" and the dialog closes. While a required field is empty the red text "Please fill in all required fields." shows and the browser blocks the submit (Title is a required field). Failure toast "Failed to create holiday". Closing the dialog after typing shows the "Discard changes?" guard.
4. The request sends `is_active:true`, the working year id and the colour.

**Steps, mobile.**
1. "Add Event" or tap a day. Modal "Add Event" (close "Close"): "Title *" ("Event title"), "Date Range *" (start and end buttons "Select start date" and "Select end date", each opening a date picker titled "Select Start Date" or "Select End Date" with Year, Month and Day steppers and "Cancel" and "Select"), "Event Color" (the hex value and a palette of 12 colour swatches, default `#2563eb`), "Description" ("Event description"), buttons "Add" and "Cancel".
2. "Add" is disabled and "Please fill in all required fields." shows while the title or a date is empty. Toasts "Holiday Created - Holiday created successfully." and "Create Failed" with the server reason.

**Expected results.** The holiday is stored active in the working year with the chosen colour and appears on the calendar and in All Events.

**API endpoints.**
- `POST /api/v1/masters/holidays/` `{name, description?, start_date, end_date, is_active=false, academic_year_id, color?}` -> 200 `HolidayRead`.

**Rules and validations.**
1. `name` is required, at most 50 characters; `description` at most 100; `color` must be `#rrggbb` (422 otherwise). Dates are ISO dates; `academic_year_id` must exist.
2. `is_active` defaults to false: a client must send `is_active:true` or the new holiday is hidden from default lists.
3. `end_date` before `start_date` is rejected with 422. There is no overlap or duplicate check.
4. The call returns status 200 (not 201). Creating clears the holidays dropdown cache.
5. Create is rate limited to 30 per minute per client IP.

**Error and edge cases.**
- Name over 50, description over 100 or an unknown year: 400 `Error creating holiday`. A bad colour or an end date before the start date: 422.
- Missing name, dates or year: 422.
- Roles without create: 403.

**Unit-testable logic.**
- `HolidayCreate` schema defaults (`is_active` False, `description` and `color` None) and required fields.
- `create_holiday` with a fake session: fields mapped, cache invalidated; exception becomes 400.
- Web add handler guard (empty title, dates or year does nothing) and payload (`is_active:true`, colour default `#2563eb`); mobile `handleAddEvent` payload (`description` undefined when empty).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-02-U01 | [backend] `HolidayCreate` with name, two dates and year only | `is_active` False, `description` None, `color` None | passing |
| TC-TTC-02-U02 | [backend] `HolidayCreate` missing `academic_year_id`; with `start_date="2026-31-12"` | Validation error each | passing |
| TC-TTC-02-U03 | [backend] `create_holiday` with a fake session that raises on flush | HTTPException 400 `Error creating holiday: ...` after rollback | passing |
| TC-TTC-02-U04 | [web] Add handler with empty title; with no selected year | No request sent | blocked: needs the add handler exported from web/src/components/calendar/Calendar.tsx |
| TC-TTC-02-U05 | [web] Add handler with valid input | Payload has `is_active:true`, `academic_year_id`, `color:"#2563eb"` | blocked: needs the add handler payload builder exported from web/src/components/calendar/Calendar.tsx |
| TC-TTC-02-A01 | Admin `POST /masters/holidays/` `{name:"QA-Diwali", description:"Festival", start_date:"2026-11-08", end_date:"2026-11-10", is_active:true, academic_year_id, color:"#ff8800"}` | 200 `HolidayRead` with the same values and an `id` | passing |
| TC-TTC-02-A02 | POST omitting `is_active` | 200 with `is_active:false`; absent from `GET /` default, present with `?active_only=false` | passing |
| TC-TTC-02-A03 | POST single-day holiday (`start_date` equals `end_date`) | 200 | passing |
| TC-TTC-02-A04 | POST with `end_date` before `start_date` | 422 | passing |
| TC-TTC-02-A05 | POST name of 50 and 51 characters | 50: 200. 51: 400 detail starts `Error creating holiday` | passing |
| TC-TTC-02-A06 | POST description of 100 and 101 characters | 100: 200. 101: 400 | passing |
| TC-TTC-02-A07 | POST colour `#ff8800` (7), `#ff880011` (9), `red` (3) | 200; 422; 422 | passing |
| TC-TTC-02-A08 | POST missing `name`; missing `academic_year_id`; invalid date | 422 each | passing |
| TC-TTC-02-A09 | POST with a random `academic_year_id` | 400 `Error creating holiday: ...` (foreign key) | passing |
| TC-TTC-02-A10 | Write matrix: POST as Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-TTC-02-A11 | No Authorization header | 401 | passing |
| TC-TTC-02-A12 | Create then `GET /dropdown` immediately | New holiday in the dropdown (create invalidates the cache) | passing |
| TC-TTC-02-A13 | 31 POSTs within a minute (limiter enabled) | The 31st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |
| TC-TTC-02-A14 | Tenant isolation: holiday created in tenant A | Not visible to tenant B; B can create the same name | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-02-E01 | P2 | Web | Admin | Working year of `qa_manual` selected; Admin holds the `holidays:create` alias grant | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click "+ Add Event".<br>4. Enter Title "QA Sports Day".<br>5. Set the date range today to tomorrow.<br>6. Pick a red colour in "Event Color".<br>7. Enter Description "QA annual sports".<br>8. Click "Add". | Toast "Holiday created!"; dialog closes; a red bar for "QA Sports Day" appears and the row is listed under "All Events" with today and tomorrow | blocked: "+ Add Event" is hidden without `holidays:create` (Known gaps 1) |
| TC-TTC-02-E02 | P1 | Web | Admin | Working year of `qa_manual` selected | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Go to October 2026 and click the empty day cell 28 Oct.<br>4. Check both date pickers.<br>5. Enter Title "QA Day One".<br>6. Click "Add". | Step 4: dialog "Add Event" with that date in both pickers. Step 6: toast "Holiday created!"; a blue (`#2563eb`) chip "QA Day One" in that cell; stored active in the working year | planned |
| TC-TTC-02-E03 | P2 | Web | Admin | Working year of `qa_manual` selected | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click an empty day cell.<br>4. Leave Title empty.<br>5. Click "Add". | Red text "Please fill in all required fields." is shown; the browser asks to fill in Title; no request is sent and no holiday is created | planned |
| TC-TTC-02-E04 | P3 | Web | Admin | Working year of `qa_manual` selected | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click an empty day cell.<br>4. Type "QA Draft" in Title.<br>5. Press Escape. | A "Discard changes?" confirmation appears; confirming closes the dialog without saving | planned |
| TC-TTC-02-E05 | P2 | Web | Teacher | Working year of `qa_manual` selected | 1. Sign in as Teacher.<br>2. Open Masters > Holidays.<br>3. Click an empty day cell.<br>4. Enter Title "QA Teacher Event".<br>5. Click "Add". | Toast "Failed to create holiday" (API 403); no holiday is created | planned |
| TC-TTC-02-E06 | P3 | Web | Admin | Default seed (no `holidays` alias grant) | 1. Sign in as Admin.<br>2. Open Masters > Holidays. | No "+ Add Event" button next to the month arrows (records the permission-name mismatch, Known gaps 1) | planned |
| TC-TTC-02-E07 | P1 | Mobile | Admin | Working year of `qa_manual` selected | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap "Add Event".<br>4. Enter Title "QA Picnic".<br>5. Tap "Select end date", step the day forward by 2 and tap "Select".<br>6. Tap the green swatch in "Event Color".<br>7. Enter Description "QA outing".<br>8. Tap "Add". | Toast "Holiday Created - Holiday created successfully."; modal closes; a green "QA Picnic" bar spans today to today plus 2; listed under "All Events" | planned |
| TC-TTC-02-E08 | P3 | Mobile | Admin | Working year of `qa_manual` selected | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap "Add Event".<br>4. Leave Title empty. | "Add" is disabled and "Please fill in all required fields." is shown; nothing is sent | planned |
| TC-TTC-02-E09 | P2 | Mobile | Teacher | Working year of `qa_manual` selected | 1. Sign in as Teacher on mobile.<br>2. Open Masters > Holidays. | No "Add Event" button (tapping a day still opens the modal, Known gaps 2) | planned |

---

## F03 Edit and reschedule a holiday

**Purpose.** An admin changes a holiday's title, dates, colour or description, or moves it to another day by dragging it on the web calendar.

**Roles and permissions.** API: `holiday_management:update`. Web: `holidays:update` for "Save" and "Edit Event"; drag and drop sends the update without a client permission check. Mobile: `holiday_management:update`.

**Preconditions.** A holiday exists (F02).

**Steps, web.**
1. Click an event chip or bar, the title in All Events, or "Edit Event" in All Events. Dialog "Edit Event" ("Edit the details of this holiday event."): Title*, Date Range*, Event Color, Description. Footer: "Save" (`holidays:update`), "Delete" (`holidays:delete`), "Cancel"; for the default Admin only "Cancel" shows.
2. Click "Save" ("Saving..."). Toast "Holiday updated!"; failure "Failed to update holiday". Missing required fields: "Please fill in all required fields." and no request.
3. Drag: drag a chip or bar onto another day cell in the month view. The event moves so that it starts on the dropped day and keeps its length; toast "Holiday updated!". Drag works for every role that sees the calendar (no client permission check); roles without update get "Failed to update holiday".

**Steps, mobile.**
1. Tap an event, a card in All Events, or "Edit Event". Modal "Edit Event" with the same fields; buttons "Save" (update permission), "Delete" (delete permission, asks for confirmation as in F04), "Cancel". "Save" is disabled while the title or a date is empty. Toasts "Holiday Updated - Holiday updated successfully." and "Update Failed" with the reason. There is no drag and drop on mobile.

**Expected results.** Changes are stored; the calendar and list refresh; unchanged fields are kept.

**API endpoints.**
- `PUT /api/v1/masters/holidays/{holiday_id}` partial `{name?, description?, start_date?, end_date?, is_active?, color?}` -> `HolidayRead`.

**Rules and validations.**
1. Only sent fields change. `start_date` and `end_date` are typed as date-times on update (send `YYYY-MM-DD`, which both clients do; a time part is dropped on storage).
2. `academic_year_id` cannot be changed.
3. No date-order or overlap check.
4. The web drag handler sends the whole record with new `start_date` and `end_date` (`yyyy-MM-dd`), keeping `is_active`, `name`, `description` and `color`.
5. Update clears the holidays dropdown cache.

**Error and edge cases.**
- Unknown id: 404 `Holiday not found`.
- Over-length name or description: 400 `Error updating holiday`. A bad colour: 422. An end date before the start date (including against the stored start date): 400 or 422.
- Roles without update: 403; the web dialog hides "Save" without the alias permission.
- A drag that fails shows "Failed to update holiday".

**Unit-testable logic.**
- `HolidayUpdate` schema (all optional, dates accept `YYYY-MM-DD`).
- `update_holiday` with a fake session: only `exclude_unset` fields set; unknown id is 404; end before start is 400; cache invalidated.
- Web drop handler: new end date equals new start plus the original duration for a 3-day and a single-day event; payload date format. Mobile edit payload (`is_active` defaults to true when undefined).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-03-U01 | [backend] `HolidayUpdate(start_date="2026-11-08")` | Valid; value parsed as a datetime at midnight | passing |
| TC-TTC-03-U02 | [backend] `update_holiday` with `{name:"X"}` on a fake holiday | Only `name` changes | passing |
| TC-TTC-03-U03 | [backend] `update_holiday` for an id the fake session cannot find | HTTPException 400 detail contains `Database error retrieving holiday` | passing |
| TC-TTC-03-U04 | [web] Drop a 3-day event (10 to 12 Oct) on 20 Oct; drop a single-day event on 5 Nov | New range 20 to 22 Oct; 5 Nov to 5 Nov; strings formatted `yyyy-MM-dd` | blocked: needs the drop handler date calculation exported from web/src/components/calendar/Calendar.tsx |
| TC-TTC-03-U05 | [mobile] Edit payload for an event with `is_active` undefined | Sends `is_active:true` | blocked: needs the edit payload builder exported from mobile/app/masters/holidays.tsx |
| TC-TTC-03-A01 | Admin `PUT /{id}` `{name:"QA-Diwali-2"}` | 200; name changed; dates, colour, `is_active` unchanged | passing |
| TC-TTC-03-A02 | `PUT /{id}` `{start_date:"2026-11-12", end_date:"2026-11-14"}` | 200; new dates returned as `YYYY-MM-DD` | passing |
| TC-TTC-03-A03 | `PUT /{id}` `{color:"#00aa00", description:"New"}` | 200 with the new values | passing |
| TC-TTC-03-A04 | `PUT /{id}` with `end_date` before `start_date` | 422 (both sent) or 400 (against the stored date) | passing |
| TC-TTC-03-A05 | `PUT /{id}` with a 51-character name | 400 `Error updating holiday: ...` | passing |
| TC-TTC-03-A06 | `PUT /{id}` `{academic_year_id:<other>}` | 200 but the year is unchanged (field not accepted) | passing |
| TC-TTC-03-A07 | `PUT /{random uuid}` | 404 detail `Holiday not found` | passing |
| TC-TTC-03-A08 | Write matrix: PUT as Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-TTC-03-A09 | No Authorization header | 401 | passing |
| TC-TTC-03-A10 | Update then `GET /dropdown` | Dropdown shows the new name (update invalidates) | passing |
| TC-TTC-03-A11 | Tenant isolation: tenant B `PUT` on tenant A's holiday id | 404; row unchanged | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-03-E01 | P2 | Web | Admin | "QA Day One" exists (TC-TTC-02-E02 done); Admin holds the `holidays:update` alias grant | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click the "QA Day One" chip.<br>4. Change Title to "QA Day One Edited".<br>5. Pick a green colour.<br>6. Click "Save". | Toast "Holiday updated!"; dialog closes; the chip shows "QA Day One Edited" in green | blocked: "Save" is hidden without `holidays:update` (Known gaps 1) |
| TC-TTC-03-E02 | P3 | Web | Admin | "QA Break" (3 days, 2026-10-27 to 2026-10-29) created on mobile as in TC-TTC-02-E07; Admin holds the `holidays:update` alias grant | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click the "QA Break" bar.<br>4. Move the end date one day later.<br>5. Click "Save". | Toast "Holiday updated!"; the bar now covers 4 days | blocked: "Save" is hidden without `holidays:update` (Known gaps 1) |
| TC-TTC-03-E03 | P3 | Web | Admin | "QA Day One" exists | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click the "QA Day One" chip.<br>4. Clear the Title field. | Red text "Please fill in all required fields." appears; no request is sent; the stored name is unchanged after "Cancel" | planned |
| TC-TTC-03-E04 | P1 | Web | Admin | "QA Day One" on 28 Oct 2026 (TC-TTC-02-E02 done) | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Go to October 2026.<br>4. Drag the "QA Day One" chip onto 30 Oct. | Toast "Holiday updated!"; the chip moves to 30 Oct; "All Events" shows 2026-10-30 as start and end date | planned |
| TC-TTC-03-E05 | P2 | Web | Admin | "QA Break" (3 days, 2026-10-27 to 2026-10-29) exists | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Go to October 2026.<br>4. Drag the "QA Break" bar onto Sun 18 Oct. | Toast "Holiday updated!"; the bar now covers 18 to 20 Oct (3 days) | planned |
| TC-TTC-03-E06 | P2 | Web | Teacher | "QA Day One" exists | 1. Sign in as Teacher.<br>2. Open Masters > Holidays.<br>3. Click the "QA Day One" chip. | Dialog "Edit Event" with the fields filled; footer shows only "Cancel" (no "Save" or "Delete") | planned |
| TC-TTC-03-E07 | P1 | Mobile | Admin | "QA Picnic" exists (TC-TTC-02-E07) | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap the "QA Picnic" bar.<br>4. Change Description to "QA outing updated".<br>5. Tap "Save". | Toast "Holiday Updated - Holiday updated successfully."; the All Events card shows the new description | planned |
| TC-TTC-03-E08 | P3 | Mobile | Admin | "QA Picnic" exists | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap the "QA Picnic" bar.<br>4. Clear the Title. | "Save" is disabled and "Please fill in all required fields." is shown | planned |

---

## F04 Delete (deactivate) and restore a holiday

**Purpose.** An admin removes a holiday from the calendar without losing it, and can restore it through the API.

**Roles and permissions.** Delete: `holiday_management:delete`. Restore (`PATCH .../activate`): `holiday_management:update`. Web buttons: `holidays:delete`. Mobile: `holiday_management:delete`. There is no restore button on web or mobile.

**Preconditions.** A holiday exists.

**Steps, web.**
1. In the Edit Event dialog click "Delete" ("Deleting..."), or in All Events click the trash icon ("Delete Event", no confirmation). Both need `holidays:delete`, so they are hidden for the default Admin. Toast "Holiday deleted!". The holiday disappears from the calendar and list (it is deactivated).
2. Failure toast "Failed to deactivate holiday".

**Steps, mobile.**
1. In the Edit Event modal press "Delete" or the trash button on a card; confirm "Delete Event" ("Are you sure you want to delete "<name>"?", "Delete"). Toast "Holiday Deleted - Holiday deleted successfully." Failure toast "Delete Failed".

**Expected results.** The row stays in the database with `is_active=false`; default lists and the dropdown hide it; `PATCH /{id}/activate` makes it visible again.

**API endpoints.**
- `DELETE /api/v1/masters/holidays/{holiday_id}` -> 200 `HolidayRead` with `is_active:false`.
- `PATCH /api/v1/masters/holidays/{holiday_id}/activate` -> 200 `HolidayRead` with `is_active:true`.

**Rules and validations.**
1. Delete is a soft deactivate and idempotent; activate is idempotent.
2. Both clear the holidays dropdown cache.
3. Inactive holidays can be seen only with `active_only=false` (no client does this), so the UI offers no restore.

**Error and edge cases.**
- Unknown id on either call: 404 `Holiday not found`.
- Web All Events deletes without a confirmation dialog; mobile asks for confirmation.
- Roles without delete or update: 403.

**Unit-testable logic.**
- `deactivate_holiday` and `activate_holiday` with a fake session: flag toggled, cache invalidated, unknown id is 404.
- Web `useDeactivateHoliday` toast texts; mobile confirm copy.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-04-U01 | [backend] `deactivate_holiday` on an active fake holiday, twice | `is_active` False both times; no error | passing |
| TC-TTC-04-U02 | [backend] `activate_holiday` on an inactive fake holiday | `is_active` True; cache invalidated | passing |
| TC-TTC-04-U03 | [backend] `activate_holiday` for an unknown id | HTTPException 404 `Holiday not found` | passing |
| TC-TTC-04-A01 | Admin `DELETE /{id}` | 200 body has `is_active:false`; `GET /` default no longer lists it; `GET /?active_only=false` does | passing |
| TC-TTC-04-A02 | `DELETE /{id}` twice | 200 both times | passing |
| TC-TTC-04-A03 | `DELETE /{random uuid}` | 404 | passing |
| TC-TTC-04-A04 | `PATCH /{id}/activate` on a deactivated holiday | 200 `is_active:true`; listed again by default | passing |
| TC-TTC-04-A05 | `PATCH /{random uuid}/activate` | 404 | passing |
| TC-TTC-04-A06 | Deactivate then `GET /dropdown`; activate then `GET /dropdown` | Absent; present again (cache invalidated both times) | passing |
| TC-TTC-04-A07 | Write matrix: DELETE and PATCH activate as Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-TTC-04-A08 | No Authorization header on both | 401 | passing |
| TC-TTC-04-A09 | Tenant isolation: tenant B `DELETE` and `PATCH` on tenant A's holiday | 404 for both; the holiday stays active | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-04-E01 | P2 | Web | Admin | "QA Day One" exists; Admin holds the `holidays:delete` alias grant | 1. Sign in as Admin.<br>2. Open Masters > Holidays.<br>3. Click the "QA Day One" chip.<br>4. Click "Delete". | Toast "Holiday deleted!"; the chip disappears from the month and from "All Events"; the row is stored inactive | blocked: "Delete" is hidden without `holidays:delete` (Known gaps 1) |
| TC-TTC-04-E02 | P2 | Web | Admin | "QA Break" exists; Admin holds the `holidays:delete` alias grant | 1. Sign in as Admin.<br>2. Open Masters > Holidays > "All Events".<br>3. Click the trash icon "Delete Event" on "QA Break". | Toast "Holiday deleted!" immediately, with no confirmation dialog; the row disappears | blocked: "Delete Event" is hidden without `holidays:delete` (Known gaps 1) |
| TC-TTC-04-E03 | P3 | Web | Teacher | "QA Day One" exists | 1. Sign in as Teacher.<br>2. Open Masters > Holidays > "All Events".<br>3. Click the "QA Day One" title. | No trash icon in Actions; the Edit Event dialog has no "Delete" button | planned |
| TC-TTC-04-E04 | P1 | Mobile | Admin | "QA Picnic" exists | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays.<br>3. Tap the "QA Picnic" bar.<br>4. Tap "Delete".<br>5. Tap "Delete" in the confirmation. | Confirmation "Delete Event" with "Are you sure you want to delete "QA Picnic"?"; then toast "Holiday Deleted - Holiday deleted successfully."; the event is gone from month and list | planned |
| TC-TTC-04-E05 | P3 | Mobile | Admin | An active holiday "QA Keep" created as in TC-TTC-02-E07 | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays > "All Events".<br>3. Tap "Delete Event" on "QA Keep".<br>4. Tap "Cancel" in the confirmation. | The confirmation closes; "QA Keep" stays in the list and no request is sent | planned |
| TC-TTC-04-E06 | P2 | Mobile | Admin | TC-TTC-04-E05 done ("QA Keep" exists) | 1. Sign in as Admin on mobile.<br>2. Open Masters > Holidays > "All Events".<br>3. Tap "Delete Event" on "QA Keep".<br>4. Tap "Delete". | Confirmation "Delete Event"; toast "Holiday Deleted - Holiday deleted successfully."; the card disappears | planned |

---

## F05 Holiday single read and dropdown

**Purpose.** Other screens and integrations read one holiday or a compact holiday list.

**Roles and permissions.** Single read: `holiday_management:read`. Dropdown: `holiday_management:list`. Admin, Staff and Teacher hold both; Student and Parent hold neither. No screen uses these endpoints directly today (the hooks `useHoliday` and `useHolidaysDropdown` exist).

**Preconditions.** Holidays exist.

**Steps, web.** No screen; the hooks `useHoliday(id)` and `useHolidaysDropdown(activeOnly)` call the endpoints.

**Steps, mobile.** No screen; `holidaysApi.getHoliday` and `getHolidaysDropdown` exist and no screen uses them (the mobile type for the dropdown says `label`, but the API returns `name`).

**Expected results.** The dropdown returns active holidays ordered by name as `{id, name}`; the single read returns the full record.

**API endpoints.**
- `GET /api/v1/masters/holidays/dropdown` query `active_only=true` -> `[{id, name}]` ordered by name.
- `GET /api/v1/masters/holidays/{holiday_id}` -> `HolidayRead`.

**Rules and validations.**
1. The dropdown is cached for 5 minutes per tenant and arguments; create, update, activate and deactivate clear it.
2. The dropdown is not filtered by year.
3. `GET /{id}` for an unknown id returns 404 `Holiday not found`.

**Error and edge cases.**
- Student and Parent: 403 on both endpoints.
- `GET /dropdown` is declared before `/{holiday_id}`, so `dropdown` is never parsed as an id.

**Unit-testable logic.**
- `get_holidays_dropdown` shape and ordering with a fake session; the 404 in `get_holiday_by_id`.
- Mobile option mapper must use `name` (not `label`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-05-U01 | [backend] `get_holidays_dropdown(active_only=True)` with fake rows B (active), A (active), C (inactive) | `[{id,name:A},{id,name:B}]` ordered by name | passing |
| TC-TTC-05-U02 | [backend] `get_holiday_by_id` for an unknown id | HTTPException 404 `Holiday not found` | passing |
| TC-TTC-05-A01 | `GET /dropdown` with two active and one inactive holiday | Two items `{id,name}` ordered by name | passing |
| TC-TTC-05-A02 | `GET /dropdown?active_only=false` | Three items | passing |
| TC-TTC-05-A03 | `GET /{id}` valid | 200 `HolidayRead` | passing |
| TC-TTC-05-A04 | `GET /{random uuid}` | 404 detail `Holiday not found` | passing |
| TC-TTC-05-A05 | `GET /not-a-uuid` | 422 | passing |
| TC-TTC-05-A06 | Read matrix: both endpoints as Admin, Staff, Teacher | 200 | passing |
| TC-TTC-05-A07 | Both endpoints as Student and Parent | 403 each | passing |
| TC-TTC-05-A08 | No Authorization header | 401 | passing |
| TC-TTC-05-A09 | Tenant isolation: tenant B `GET /dropdown`; `GET /{A's id}` | Empty list; 404 | passing |
| TC-TTC-05-A10 | Rename a holiday and call `GET /dropdown` | New name immediately (update invalidates) | passing |

---

## F06 Timetable: select a section and view it

**Purpose.** An admin picks a class and a section and sees that section's weekly timetable: time ranges as rows, days as columns, subjects and special rows in the cells.

**Roles and permissions.** Read: `timetable_management:read` (`GET /students/timetable/frontend/{section_id}`). Only Admin holds it in the default seed; Staff, Teacher, Student and Parent receive 403. The class and section pickers use `classes:list` (MST F06). Edit controls need `timetable_management:update`. Menu: web top-level "Timetable" (`/TimeTable`); mobile: the Dashboard "Modules" tile and drawer entry "Timetable" (the menu path `/TimeTable` maps to `/masters/timetable`) and, only when the backend Masters menu lists it or the cold-start fallback list is used, the Masters hub card "Timetable Management" (absent on `qa_school`).

**Preconditions.** Class, sections and subjects exist (MST F03, F08). For a non-empty view a timetable was saved (F07).

**Steps, web.**
1. Open "Timetable". Header "Time Table Management". Pickers "Select Class" (active classes) and "Select Section" (disabled until a class is chosen; lists the class's active sections), on the right of the card.
2. Before both are chosen: "Please select a class and section to view or create a timetable" with the hint "Start by selecting a class" or "Now select a section".
3. After choosing a section: "Loading timetable data..." then the grid. Columns: "Time" (for example "9:00 AM - 9:45 AM"), "Monday" to "Friday", and "Saturday" when any saved subject row has a Saturday value. A day with no entry shows "--"; an all-empty Saturday column shows "(Holiday)" in its header and "Holiday" in cells. Special rows span all day columns with their label (Snacks, Lunch, Dispersal or the custom name).
4. View mode buttons: "Edit" (update permission) and "Export" (F10). If no timetable exists (404) the grid is empty and, for a user who can update, the page opens in edit mode (F07). If the request fails otherwise the page retries three times (about 10 seconds) and then shows "Error loading timetable: <reason>".
5. The page does not remember the selection, and saved rows come back in no particular time order.

**Steps, mobile.**
1. Open the Dashboard tile or drawer entry "Timetable" (or the Masters hub card "Timetable Management" where present). Screen "Timetable" with "Select Class" (one card per class from the class list) then a screen titled with the class name, subtitle "Select Section" and one card per section, then the grid screen titled "<class> - <section>" with the subtitle "Timetable". Each screen has a back arrow ("Go back").
2. View mode shows "Export", "Edit", day tabs (Mon to Fri, plus Sat when Saturday was saved; accessibility labels Monday to Saturday) and one card per row for the selected day: the 12-hour time range ("9:00 AM - 9:45 AM") and either the subject name, "Free period" for an empty cell, or the special label as stored (for example "LUNCH"). Pull down to refresh. Empty: "No timetable data".
3. Without a saved timetable the screen opens in edit mode with one default subject row at 9:00 AM to 9:45 AM (F07). Without any read or list permission on timetables the first screen shows "Access Denied - You don't have permission to view timetables".

**Expected results.** The grid shows exactly the saved rows and cells; Saturday appears only when saved; custom event names are restored from the saved labels (underscores become spaces and words are capitalised on web).

**API endpoints.**
- `GET /api/v1/students/timetable/frontend/{section_id}` -> `{section_id, section_name, class_name, timetable_data:[{time:{from,to}, type, subjects?, label?}]}`.

**Rules and validations.**
1. A section has at most one timetable (unique `section_id`). A missing timetable or an unknown section is 404 `Timetable not found for section`.
2. Rows are built by grouping slots by `slot_time_id`; groups come back in database order, not by time. Clients must sort by `time.from`.
3. A group is `special` only if every slot of the group is a break (its `label` is the first slot's label); otherwise it is a `subject` row built from non-break slots with only the first subject option per day.
4. Times are returned as `HH:MM` strings.
5. Class and section names are included for display.
6. Web uses `placeholderData: keepPreviousData` and ignores background refetches so the grid is not reset after a save; it does not retry a 404.

**Error and edge cases.**
- A non-Admin role: 403; the web retries three times then shows "Error loading timetable: Permission denied: timetables:read".
- A section with a timetable that has zero slots returns `timetable_data:[]`.
- Mobile class list is not limited to the working year.

**Unit-testable logic.**
- Backend `transform_slots_to_frontend_format` with fake slots: all breaks gives `special` with the first label; mixed gives `subject`; breaks inside a subject group are skipped; only `subject_options[0]` is read; times formatted `%H:%M`.
- `get_frontend_timetable_by_section`: 404 when no timetable, names filled, groups by slot time.
- Web `transformFrontendTimetableToRows`, Saturday auto-detect, custom-event extraction (`ASSEMBLY` becomes "Assembly", `MORNING_PRAYER` becomes "Morning Prayer"), `formatTime12hr` (`00:00` is 12:00 AM, `12:30` is 12:30 PM, `13:05` is 1:05 PM) and `getSaturdayCellDisplay`; mobile `formatTime12h` and the day filter used by the editor. These helpers live inside `TimeTableEditor.tsx` and `masters/timetable.tsx` and need exporting.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-06-U01 | [backend] `transform_slots_to_frontend_format` for 5 break slots labelled `LUNCH` at 12:00 to 12:45 | `{time:{from:"12:00",to:"12:45"}, type:"special", label:"LUNCH"}` | passing |
| TC-TTC-06-U02 | [backend] Same function for Monday and Tuesday subject slots with one option each | `type:"subject"`, `subjects` has Monday and Tuesday ids | passing |
| TC-TTC-06-U03 | [backend] A group with 4 subject slots and 1 break slot | Treated as `subject`; the break day is absent from `subjects` | passing |
| TC-TTC-06-U04 | [backend] A slot with two subject options | Only the first option's subject id returned | passing |
| TC-TTC-06-U05 | [backend] `get_frontend_timetable_by_section` with no timetable | HTTPException 404 `Timetable not found for section` | passing |
| TC-TTC-06-U06 | [web] `transformFrontendTimetableToRows` for a subject row and a special row | Rows keep `time`, `type`, and `subjects` or `label` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-06-U07 | [web] Saturday auto-detect with a row containing a `Saturday` key; and without | `includeSaturday` true; false | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-06-U08 | [web] Custom-event extraction from labels `SNACKS`, `ASSEMBLY`, `MORNING_PRAYER` | Defaults ignored; custom list `Assembly`, `Morning Prayer` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-06-U09 | [web] `formatTime12hr` for `00:00`, `09:00`, `12:30`, `13:05`, empty | `12:00 AM`, `9:00 AM`, `12:30 PM`, `1:05 PM`, empty string | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-06-U10 | [web] `getSaturdayCellDisplay` for empty, a subject id, `LUNCH`, free text `Sports` | `Holiday`, the subject name, `Lunch`, `Sports` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-06-U11 | [mobile] `formatTime12h("09:45")` and `formatTime12h("00:05")` | `9:45 AM` and `12:05 AM` | passing |
| TC-TTC-06-A01 | Admin `GET /frontend/{section}` after F07 saved 2 subject rows and a LUNCH row | 200 with `section_name`, `class_name`; 3 items (after sorting by `time.from`) with times as `HH:MM` | passing |
| TC-TTC-06-A02 | `GET /frontend/{section}` for a section without a timetable | 404 `Timetable not found for section` | passing |
| TC-TTC-06-A03 | `GET /frontend/{random uuid}`; `GET /frontend/not-a-uuid` | 404; 422 | passing |
| TC-TTC-06-A04 | A timetable created with an empty `timetable_data` | 200 with `timetable_data:[]` | passing |
| TC-TTC-06-A05 | Special row saved through PUT | Returned as `type:"special"`, `label` as saved, no `subjects` key | passing |
| TC-TTC-06-A06 | Two rows with the same time range saved through PUT | Single merged row returned (same slot time) | passing |
| TC-TTC-06-A07 | Read matrix: Admin 200 | 200 for Admin | passing |
| TC-TTC-06-A08 | `GET /frontend/{section}` as Staff, Teacher, Student, Parent | 403 `Permission not found in database` each (default seed) | passing |
| TC-TTC-06-A09 | No Authorization header | 401 | passing |
| TC-TTC-06-A10 | Tenant isolation: tenant B `GET` for tenant A's section id | 404 | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-06-E01 | P2 | Web | Admin | Seeded classes | 1. Sign in as Admin.<br>2. Click "Timetable" in the sidebar. | Header "Time Table Management"; pickers "Select Class" and "Select Section" (disabled); message "Please select a class and section to view or create a timetable" with "Start by selecting a class" | planned |
| TC-TTC-06-E02 | P3 | Web | Admin | Seeded classes | 1. Sign in as Admin.<br>2. Open "Timetable".<br>3. Choose "Class 1" in "Select Class". | Hint becomes "Now select a section"; "Select Section" is enabled and lists 1-A and 1-B | planned |
| TC-TTC-06-E03 | P1 | Web | Admin | Seeded timetable of 1-A | 1. Sign in as Admin.<br>2. Open "Timetable".<br>3. Choose "Class 1" and section "1-A". | "Loading timetable data..." then the grid with "Time" and Monday to Friday (no Saturday); 8 rows with 12-hour times such as "9:00 AM - 10:00 AM"; a subject name in each subject cell; "Snacks" (10:45 AM - 11:00 AM) and "Lunch" (12:30 PM - 1:15 PM) span all day columns; buttons "Edit" and "Export". Rows may not be in time order (Known gaps 10) | planned |
| TC-TTC-06-E04 | P2 | Web | Admin | TC-TTC-07-E08 done (section 3-A saved with a Saturday value in the 9:00 AM row only) | 1. Sign in as Admin.<br>2. Open "Timetable".<br>3. Choose "Class 3" and "3-A". | "Saturday" column visible; the 9:00 AM row shows the saved subject on Saturday; Saturday cells of other subject rows show "Holiday" in italics; the header has no "(Holiday)" suffix because one Saturday value exists | planned |
| TC-TTC-06-E05 | P1 | Web | Admin | Section 3-B has no timetable (seeded state) | 1. Sign in as Admin.<br>2. Open "Timetable".<br>3. Choose "Class 3" and "3-B". | Empty grid in edit mode: "Save", "Include Saturday", headers Time, Monday to Friday, Actions; buttons "+ Add Subject Row", "+ Add Special Row", and "Repeat All for Week" and "Repeat One Subject" disabled; no "Export" | planned |
| TC-TTC-06-E06 | P2 | Web | Teacher | Seeded timetable of 1-A | 1. Sign in as Teacher.<br>2. Open "Timetable".<br>3. Choose "Class 1" and "1-A".<br>4. Wait about 15 seconds. | "Loading timetable data..." during the retries, then "Error loading timetable: Permission denied: timetables:read"; no "Edit", "Save" or "Export" | planned |
| TC-TTC-06-E07 | P3 | Web | Admin | Seeded timetable of 1-A | 1. Sign in as Admin.<br>2. Open "Timetable".<br>3. Choose "Class 1" and "1-A".<br>4. Choose "Class 2" in "Select Class". | Section clears to "Select Section"; the grid is replaced by "Please select a class and section to view or create a timetable" and "Now select a section" | planned |
| TC-TTC-06-E08 | P2 | Web | Student | Seeded student Advik Mehta (002) login | 1. Sign in as Advik Mehta (login 002).<br>2. Look at the sidebar. | No "Timetable" entry (self-service menu only) | planned |
| TC-TTC-06-E09 | P1 | Mobile | Admin | Seeded timetable of 1-A | 1. Sign in as Admin on mobile.<br>2. Tap the Dashboard tile "Timetable".<br>3. Tap "Class 1".<br>4. Tap "1-A". | Screen titled "Class 1 - 1-A" with subtitle "Timetable", buttons "Export" and "Edit", day tabs Mon to Fri (no Sat), cards with times such as "9:00 AM - 10:00 AM" and subject names | planned |
| TC-TTC-06-E10 | P2 | Mobile | Admin | Seeded timetable of 1-A | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 1" > "1-A".<br>3. Tap the day tabs Tue and Fri in turn. | Cards change per day; the special rows show "SNACKS" and "LUNCH" on every day; no Sat tab | planned |
| TC-TTC-06-E11 | P2 | Mobile | Admin | Section 3-B has no timetable | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 3" > "3-B". | Edit mode: "Save", "Include Saturday", one row with "9:00 AM" to "9:45 AM" and "Select Subject" for Mon to Fri, "Add Subject", "Add Special", "Repeat All for Week", "Repeat One Subject", "Save Timetable" | planned |
| TC-TTC-06-E12 | P2 | Mobile | Teacher | Default role grants | 1. Sign in as Teacher on mobile.<br>2. Open the route `/masters/timetable`. | "Access Denied" with "You don't have permission to view timetables" | planned |

---

## F07 Timetable: build and save (create and replace)

**Purpose.** An admin builds a section's timetable (rows of times with a subject per day, plus special rows) and saves it. The first save creates it; later saves replace it wholesale.

**Roles and permissions.** Create (`POST /frontend`): `timetable_management:create`. Replace (`PUT /frontend/{section_id}`): `timetable_management:update`. Admin only. Web: the Edit and Save buttons and row controls need `timetable_management:update`; mobile: the Edit and Save button needs `timetable_management` update while editing.

**Preconditions.** A class and section exist; subjects exist and normally are mapped to the class (MST F10); the section view (F06) is open.

**Steps, web.**
1. Choose class and section. With no saved timetable the grid is empty and in edit mode; with a saved timetable click "Edit".
2. Click "+ Add Subject Row": a row with two time buttons "Select time" separated by "-" (each opens a picker with the columns "Hour" 01 to 12 and "Min" 00 to 59, the buttons "AM" and "PM", and "Done"; the button then shows "09:00 AM" and the value is stored as 24-hour `HH:MM`) and a "Select..." dropdown per day (Monday to Friday, and Saturday when "Include Saturday" is ticked). Click "+ Add Special Row": a row with one dropdown "Select or create event..." (default Snacks) spanning all days. The trash button ("Delete row") in the "Actions" column removes a row.
3. Click "Save". The button shows "Saving...". On success: toast "Timetable saved successfully", the grid returns to view mode and reloads. Failure toasts: the server message for 400 and 409 (for example "A timetable already exists for this section" or "Subject or section not found"), "Permission denied: timetables:create" or "Permission denied: timetables:update", "Invalid data provided" (422), "Timetable not found for this section" (PUT 404), or "Failed to save timetable".
4. Rows without both times and subject rows with no subject chosen are dropped before sending; empty day values are not sent.
5. If a timetable already exists the save is a replace (PUT), otherwise a create (POST).

**Steps, mobile.**
1. Select class and section (F06); on a saved timetable tap "Edit". In edit mode each row is a card with two time boxes ("9:00 AM" "to" "9:45 AM"; tapping one opens the "Select Time" picker with Hour and Minute arrows, "AM" and "PM", preset times, "Cancel" and "Done"), a "Select Subject" dropdown per day labelled Mon to Fri (and Sat), a trash button ("Delete"), and a "Select Special Activity" dropdown on special rows.
2. Buttons "Add Subject" and "Add Special" add rows (default 9:00 AM to 9:45 AM; special default Snacks). "Save" in the header or "Save Timetable" at the bottom saves ("Saving..."). Toasts "Timetable Created - Timetable created successfully.", "Timetable Updated - Timetable updated successfully.", "Create Failed" and "Update Failed" with the reason.
3. Mobile sends every row as is: an untouched subject row has an empty `subjects` object and a cleared dropdown sends an empty string, both rejected with 422.

**Expected results.** Rows and cells are stored under the section; reloading shows the same data (order may differ); a replace discards everything not sent.

**API endpoints.** Prefix `/api/v1/students/timetable`.
- `POST /frontend` `{section_id, timetable_data:[{time:{from,to}, type:"subject"|"special", subjects?:{Day:uuid}, label?}]}` -> 200 `{message:"Timetable created successfully", timetable_id, created_slots, created_slot_times}`.
- `PUT /frontend/{section_id}` same body -> 200 `{message:"Timetable updated successfully", ...}`.

**Rules and validations.**
1. Row validation (422): `type` must be `subject` or `special`; a subject row needs a non-empty `subjects` object of day name to UUID and no `label`; a special row needs a `label` and no `subjects`; `time.from` and `time.to` are required strings.
2. Times are parsed as `HH:MM` (`strptime("%H:%M")`). Any other format or an impossible time (`9am`, `25:00`, `09:00:00`) fails with 422 `Invalid time, use HH:MM`. `9:00` is accepted.
3. `POST` creates the timetable row; a second `POST` for the same section returns 409 `A timetable already exists for this section`. An unknown `section_id` returns 404 `Section not found`; an unknown subject id returns 400 `Subject or section not found` (module doc rule 2).
4. `POST` keeps only Monday to Friday: Saturday (and any other day) subject values are silently dropped, and special rows are written for Monday to Friday. A subject row whose days are all dropped still creates its time range but no slots, so it does not come back.
5. `PUT` replaces the whole timetable: all slots, options and every slot time of the section are deleted and recreated. Any day key is kept, and special rows are written for Monday to Sunday. Rows with the same `from-to` share one slot time and therefore merge into a single row on read (a special row and a subject row at the same time read back as a subject row). `PUT` returns 404 `Timetable not found for section` when none exists and uses the path `section_id` (the body value is ignored).
6. `created_slots` counts subject slots (day and subject) and break slots (5 per special row on create, 7 on replace); `created_slot_times` counts time ranges (on create one per row; on replace one per distinct range).
7. The API does not check `from` before `to`, overlaps, that a subject is mapped to the class, or that the subject belongs to the year.
8. Subject values must be UUIDs. The web Saturday cell also accepts free text or an event name; saving those fails with 422.
9. Slot ids change on every replace (nothing else references them).

**Error and edge cases.**
- Web guards the save with the permission; a Teacher never reaches it. Without `timetable_management:create` the first save returns 403 and the toast reads "Permission denied: timetables:create".
- After the first save of a table that included Saturday, Saturday is gone (POST drops it); a second save (PUT) keeps whatever Saturday value is entered.
- Duplicate `POST` from a stale screen returns 409 and the web toast reads "A timetable already exists for this section".

**Unit-testable logic.**
- `FrontendTimetableSlot` validator: all four rule branches and the unknown type; `FrontendTimeRange` accepts `from` as the field name.
- `create_frontend_timetable` with a fake session: counts for subject rows Monday to Friday, Saturday dropped, special row 5 slots, bad time raises 500; `update_frontend_timetable`: 404 when absent, deletion order, special row 7 slots, same-range merge, `subject_id` truthiness.
- Web `transformRowsToFrontendTimetableCreate`: skips rows without times, drops empty day values and empty subject rows, keeps special rows with the label. Mobile `handleSave` mapping (rows sent as is).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-07-U01 | [backend] `FrontendTimetableSlot(type="subject", subjects={})` | Validation error `subjects field is required when type is 'subject'` | passing |
| TC-TTC-07-U02 | [backend] `type="subject"` with subjects and `label="X"` | Validation error `label field should not be provided` | passing |
| TC-TTC-07-U03 | [backend] `type="special"` with no label; with label and subjects | Validation errors `label field is required...`; `subjects field should not be provided...` | passing |
| TC-TTC-07-U04 | [backend] `type="break"` | Validation error `type must be either 'subject' or 'special'` | passing |
| TC-TTC-07-U05 | [backend] Slot built from `{"time":{"from":"09:00","to":"09:45"},...}` | `time.from_time` "09:00" and `time.to` "09:45" | passing |
| TC-TTC-07-U06 | [backend] `subjects={"Monday":"not-a-uuid"}` | Validation error (UUID) | passing |
| TC-TTC-07-U07 | [backend] `create_frontend_timetable` with 2 subject rows (Monday to Friday) and 1 special row, fake session | `created_slots` 15, `created_slot_times` 3 | passing |
| TC-TTC-07-U08 | [backend] `create_frontend_timetable` with a Saturday subject key | Saturday dropped; counts exclude it | passing |
| TC-TTC-07-U09 | [backend] `create_frontend_timetable` with time `"25:00"` | HTTPException 500 `Error creating timetable from frontend data`; rollback | passing |
| TC-TTC-07-U10 | [backend] `update_frontend_timetable` when no timetable exists | HTTPException 404 `Timetable not found for section` | passing |
| TC-TTC-07-U11 | [backend] `update_frontend_timetable` with a special row | 7 break slots (Monday to Sunday); `created_slots` 7 | passing |
| TC-TTC-07-U12 | [backend] `update_frontend_timetable` with two rows at `09:00-09:45` | One slot time (`created_slot_times` 1) shared by both rows' slots | passing |
| TC-TTC-07-U13 | [web] `transformRowsToFrontendTimetableCreate` with a row without `to`, a subject row with all empty days, a row with `Monday` set | Only the third row is kept; empty values dropped | blocked: needs transformRowsToFrontendTimetableCreate exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-07-U14 | [web] Same function for a special row with label `LUNCH` | Item `{time, type:"special", label:"LUNCH"}` | blocked: needs transformRowsToFrontendTimetableCreate exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-07-U15 | [mobile] `handleSave` mapping for a default untouched subject row | Item with `subjects:{}` (documents the 422 cause) | blocked: needs the save mapping exported from mobile/app/masters/timetable.tsx |
| TC-TTC-07-A01 | Admin `POST /frontend` with rows 09:00-09:45 and 09:45-10:30 (Monday to Friday, three subjects) and a LUNCH row 12:00-12:45 | 200 `message "Timetable created successfully"`, `created_slots` 15, `created_slot_times` 3, `timetable_id` set | passing |
| TC-TTC-07-A02 | `GET /frontend/{section}` after A01 | 3 rows; the subject rows list Monday to Friday; the LUNCH row is `special` | passing |
| TC-TTC-07-A03 | POST a subject row that includes `Saturday` | 200; the returned timetable has no Saturday key; `created_slots` excludes it | passing |
| TC-TTC-07-A04 | POST a subject row with only `Saturday` | 200 with `created_slot_times` counting it; the row is absent from `GET` | passing |
| TC-TTC-07-A05 | POST a second time for the same section | First 200; second 409 `A timetable already exists for this section` | passing |
| TC-TTC-07-A06 | POST with a random `section_id`; with a random subject uuid | 404 for the unknown section; 400 for the unknown subject, and no timetable is stored (GET 404) | passing |
| TC-TTC-07-A07 | POST bodies: `type:"break"`; subject without `subjects`; subject with `label`; special without `label`; special with `subjects` | 422 each | passing |
| TC-TTC-07-A08 | POST subject value `"Holiday"` for Saturday | 422 | passing |
| TC-TTC-07-A09 | POST time `"9am"`, `"25:00"`, `"09:00:00"`; time `"9:00"` | 422 `Invalid time, use HH:MM` for the first three; 200 for `9:00` (stored as 09:00) | passing |
| TC-TTC-07-A10 | POST `from` later than `to` and two overlapping rows | 200 (no check; Known gaps) | passing |
| TC-TTC-07-A11 | POST with `timetable_data:[]` | 200 `created_slots` 0, `created_slot_times` 0 | passing |
| TC-TTC-07-A12 | POST subject not mapped to the class | 200 (mapping not checked) | passing |
| TC-TTC-07-A13 | POST missing `section_id`; missing `time.to` | 422 each | passing |
| TC-TTC-07-A14 | `PUT /frontend/{section}` replacing with a single row 08:00-08:45 | 200 `message "Timetable updated successfully"`; `GET` returns only that row | passing |
| TC-TTC-07-A15 | PUT with a Saturday subject | 200; `GET` returns the Saturday key | passing |
| TC-TTC-07-A16 | PUT with a special row | `created_slots` 7; `GET` returns `special` | passing |
| TC-TTC-07-A17 | PUT with a non-day key `Funday` | 200; key returned by `GET` (no day validation) | passing |
| TC-TTC-07-A18 | PUT with two rows at the same time range | `created_slot_times` 1; `GET` returns one merged row | passing |
| TC-TTC-07-A19 | PUT a special row and a subject row at the same range | `GET` returns a subject row (special label lost) | passing |
| TC-TTC-07-A20 | PUT for a section without a timetable | 404 `Timetable not found for section` | passing |
| TC-TTC-07-A21 | PUT with a body `section_id` of another section | 200; data stored under the path section; the other section unchanged | passing |
| TC-TTC-07-A22 | Slot ids before and after a PUT (via `GET /section/{section}`) | All slot ids differ after the replace | passing |
| TC-TTC-07-A23 | Round trip: PUT three rows then `GET` | Same set of times and subjects after sorting by `time.from` | passing |
| TC-TTC-07-A24 | Write matrix: POST and PUT with valid bodies as Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-TTC-07-A25 | No Authorization header on POST and PUT | 401 | passing |
| TC-TTC-07-A26 | Tenant isolation: tenant B `POST` for tenant A's section; `PUT` for it | 404 for both; tenant A's timetable keeps its one row | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-07-E01 | P1 | Web | Admin | Section 3-A has no timetable; English and Mathematics mapped to Class 3 (seeded) | 1. Sign in as Admin.<br>2. Open "Timetable".<br>3. Choose "Class 3" and "3-A".<br>4. Click "+ Add Subject Row".<br>5. Click the first "Select time", choose Hour 09, Min 00, "AM", "Done".<br>6. Click the second "Select time", choose Hour 09, Min 45, "AM", "Done".<br>7. Choose "Mathematics" in the Monday to Friday cells.<br>8. Click "Save". | Toast "Timetable saved successfully"; view mode with one row "9:00 AM - 9:45 AM" and Mathematics on five days; "Edit" and "Export" shown. Clean up after the F07 to F10 cases with TC-TTC-09-A01 | planned |
| TC-TTC-07-E02 | P2 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Click "+ Add Special Row".<br>5. Choose "Lunch" in "Select or create event...".<br>6. Set the times 12:00 PM and 12:45 PM.<br>7. Click "Save".<br>8. Reload the page and choose "Class 3" and "3-A" again. | Toast "Timetable saved successfully"; after reload a row "12:00 PM - 12:45 PM" spans all day columns with "Lunch" | planned |
| TC-TTC-07-E03 | P1 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Change the Wednesday cell of the 9:00 AM row to "English".<br>5. Click "Save".<br>6. Reload and reselect the section. | Toast "Timetable saved successfully"; Wednesday shows English after reload (saved by replace) | planned |
| TC-TTC-07-E04 | P2 | Web | Admin | TC-TTC-07-E02 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Click "Delete row" on the Lunch row.<br>5. Click "Save".<br>6. Reload and reselect the section. | The Lunch row is gone after reload; the other rows remain | planned |
| TC-TTC-07-E05 | P3 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Click "+ Add Subject Row" and set 10:00 AM to 10:45 AM without choosing subjects.<br>5. Click "Save". | Toast "Timetable saved successfully"; the empty row is not shown after saving; the other rows are kept | planned |
| TC-TTC-07-E06 | P3 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Click "+ Add Subject Row", set only the first time (11:00 AM) and choose "English" on Monday.<br>5. Click "Save". | The row without an end time is dropped on save; it is absent after the reload | planned |
| TC-TTC-07-E07 | P2 | Web | Admin | Section 3-B has no timetable | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-B".<br>3. Tick "Include Saturday".<br>4. Click "+ Add Subject Row", set 9:00 AM to 9:45 AM.<br>5. Choose "English" Monday to Friday and "Mathematics" on Saturday.<br>6. Click "Save".<br>7. Reload and reselect the section. | Toast "Timetable saved successfully", but after reload there is no Saturday column: the first save is a create, which drops Saturday (Known gaps 8) | planned |
| TC-TTC-07-E08 | P2 | Web | Admin | TC-TTC-07-E01 done (3-A saved without Saturday) | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Tick "Include Saturday".<br>5. Choose "Mathematics" in the Saturday cell of the 9:00 AM row.<br>6. Click "Save".<br>7. Reload and reselect the section. | Saturday column shows Mathematics in the 9:00 AM row (replace keeps Saturday) | planned |
| TC-TTC-07-E09 | P3 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Tick "Include Saturday".<br>5. Type "Sports" in the Saturday cell and choose `Use "Sports"`.<br>6. Click "Save". | Toast "Invalid data provided"; the page stays in edit mode; nothing is stored | planned |
| TC-TTC-07-E10 | P3 | Web | Admin | Section 3-B has no timetable; two browser windows signed in as Admin | 1. In window 1 open "Timetable", choose "Class 3" and "3-B" (edit mode).<br>2. In window 2 do the same, add a row 9:00 AM to 9:45 AM with English on Monday and click "Save".<br>3. In window 1 add a row 10:00 AM to 10:45 AM with Mathematics on Monday and click "Save".<br>4. In window 1 reselect "3-B". | Step 3: toast "A timetable already exists for this section" (409). Step 4: the timetable saved in window 2 is shown. Remove the 3-B timetable afterwards (TC-TTC-09-A01) | planned |
| TC-TTC-07-E11 | P2 | Web | Teacher | Seeded timetable of 1-A | 1. Sign in as Teacher.<br>2. Open "Timetable".<br>3. Choose "Class 1" and "1-A". | No "Edit" or "Save" button; the grid does not load ("Error loading timetable: Permission denied: timetables:read") | planned |
| TC-TTC-07-E12 | P1 | Mobile | Admin | Section 4-A has no timetable; English mapped to Class 4 (seeded) | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-A".<br>3. Keep the default row 9:00 AM to 9:45 AM (or tap "9:00 AM", set the time in "Select Time" and tap "Done").<br>4. Choose "English" in the Mon to Fri dropdowns.<br>5. Tap "Save Timetable". | Toast "Timetable Created - Timetable created successfully."; view mode with day tabs Mon to Fri and a card "9:00 AM - 9:45 AM" "English". Clean up with TC-TTC-09-A01 afterwards | planned |
| TC-TTC-07-E13 | P2 | Mobile | Admin | Section 4-B has no timetable | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-B".<br>3. Tap "Save Timetable" without choosing any subject. | Toast "Create Failed" with the validation reason (empty `subjects`, 422); stays in edit mode. Records Known gaps 11 | planned |
| TC-TTC-07-E14 | P1 | Mobile | Admin | TC-TTC-07-E12 done | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-A".<br>3. Tap "Edit".<br>4. Change the Wed dropdown to "Mathematics".<br>5. Tap "Save". | Toast "Timetable Updated - Timetable updated successfully."; the Wed tab shows Mathematics | planned |
| TC-TTC-07-E15 | P3 | Mobile | Admin | TC-TTC-07-E12 done | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-A".<br>3. Tap "Edit".<br>4. Tap "Add Special" and choose "Lunch" in "Select Special Activity".<br>5. Tap "Save Timetable". | Toast "Timetable Updated - Timetable updated successfully."; view mode shows a card with "LUNCH" on every day | planned |
| TC-TTC-07-E16 | P3 | Mobile | Admin | TC-TTC-07-E15 done | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-A".<br>3. Tap "Edit".<br>4. Tap "Delete" on the LUNCH row.<br>5. Tap "Save Timetable".<br>6. Go back and reopen "4-A". | The LUNCH row is gone after reopening | planned |

---

## F08 Timetable editing tools: Saturday, special rows, custom events, repeat

**Purpose.** The editor offers shortcuts so an admin fills a week quickly: an optional Saturday column, special rows with reusable event names, a subject picker limited to the class's subjects, and two repeat tools.

**Roles and permissions.** Same as F07 (`timetable_management:update` to edit). The subject picker data needs `class_subject_mappings:read` (`by-class`) and `subjects:list`, which Admin holds.

**Preconditions.** The editor is in edit mode (F07).

**Steps, web.**
1. Saturday: tick "Include Saturday" (visible in edit mode). Each subject row gains a Saturday cell, a creatable dropdown "Subject / Event / Holiday..." with groups "Subjects" and "Events" and the option `Use "<text>"` for free text. Unticking removes the Saturday values.
2. Special rows: in a special row choose Snacks, Lunch or Dispersal, or type a new name and choose `Create "<name>"`. A new name is valid with 1 to 50 letters, digits or spaces (toast "Created custom event: <Name>"; otherwise "Event name must be 1-50 alphanumeric characters", or "This event already exists"). It is stored upper-cased with underscores (`MORNING_PRAYER`) and exists only for this editing session and the sections where it was saved.
3. Subject picker: each day's dropdown lists only active subjects mapped to the selected class: mappings with no section or the selected section. If the class has no mappings the dropdown lists no subjects (all subjects show only while the mappings are still loading).
4. "Repeat All for Week" (enabled when some day has a subject): dialog "Repeat All Subjects for Week", "Copy from day" (days that hold data), buttons "Cancel" and "Apply to All Days". Toast "<Day>'s schedule applied to all days". Every subject row's other days get the source day's subject (an empty source empties the others).
5. "Repeat One Subject" (enabled when rows contain a subject): dialog "Repeat One Subject for Week", "Subject" (subjects present in the rows), "Cancel" and "Apply to All Days". For every subject row that already holds that subject on any day, all active days are set to it. Toast "<Subject> applied to all days".

**Steps, mobile.**
1. "Include Saturday" checkbox in edit mode (tap the box; the label text is not tappable) adds Saturday to the day cells and, after saving, the Sat day tab.
2. Special rows use "Select Special Activity" with the defaults Snacks, Lunch, Dispersal and a create option `Create "<name>"`; a new name is accepted with 1 to 50 letters, digits or spaces, stored upper-cased with underscores, label shown with only the first letter capitalised ("Morning prayer"). An invalid name is ignored without a message; a duplicate reuses the existing option. Custom names are not rebuilt from saved labels on mobile.
3. The subject picker is limited to the class's mapped subjects in the same way (the dropdown shows "Select Subject" first).
4. "Repeat All for Week" and "Repeat One Subject" show only while at least one subject row exists. "Repeat All for Week" opens a modal "Repeat All for Week" ("Copy this day's subjects to all other days") listing the active days: choose the source day to copy its subject to every other day in every subject row. "Repeat One Subject" first asks "Select Period to Repeat" ("Pick which period's assignments to repeat", one entry per subject row with its time range), then "Select Source Day"; the row's other days take that day's subject. Both modals have "Cancel"; there is no toast.

**Expected results.** The grid reflects each tool immediately; nothing is saved until Save (F07).

**API endpoints.** None of its own. The saved result goes through `POST /api/v1/students/timetable/frontend` and `PUT /api/v1/students/timetable/frontend/{section_id}` (F07); mapped subjects come from `GET /api/v1/masters/class-subject-mappings/by-class/{class_id}` (MST F09).

**Rules and validations.**
1. Saturday values reach the server only through `PUT` (F07 rule 4); the Saturday cell value may be a subject UUID, an event value or free text, and only UUIDs are accepted by the API.
2. Custom event names: 1 to 50 characters of letters, digits and spaces; duplicates (after upper-casing and underscoring) are rejected; defaults cannot be recreated.
3. A custom event survives only as `break_label` on saved special rows; there is no shared list across sections, and loading a section rebuilds its list from the saved labels.
4. Web Repeat One acts on all rows that contain the subject; mobile Repeat One acts on one selected row. Mobile Repeat All can copy an empty source cell as `""`, which then fails UUID validation on save.
5. The mapped-subject filter is advisory: the API accepts any subject id.

**Error and edge cases.**
- Repeat buttons are disabled when there is nothing to repeat.
- Unticking Saturday on web deletes the Saturday values; on mobile the Saturday cells are only hidden.
- A class with no subject mappings offers no subjects, so no subject row can be filled.

**Unit-testable logic.**
- Web (extract from `TimeTableEditor.tsx`): `isValidEventName` (empty, 50, 51, `Assembly!`), `addCustomEvent` value and label transformation, duplicate rejection, `handleSaturdayToggle`, `handleRepeatAll`, `handleRepeatOneSubject`, `classSubjectIds` filter (null section means class-wide), `subjectsInRows`, `daysWithData`.
- Mobile (extract from `masters/timetable.tsx`): `addCustomEvent` (label `Morning prayer` from `morning prayer`), `handleRepeatAllForWeek`, `handleRepeatOneSubject`, mapped-subject filter.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-08-U01 | [web] `isValidEventName` for `""`, `"Assembly"`, 50 characters, 51 characters, `"Prayer!"` | false, true, true, false, false | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U02 | [web] `addCustomEvent("morning prayer")` | value `MORNING_PRAYER`, label `Morning Prayer`; second call returns null with "This event already exists" | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U03 | [web] `addCustomEvent("Lunch")` | Rejected as duplicate of the default | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U04 | [web] `handleSaturdayToggle(true)` then `(false)` on rows with and without Saturday | Saturday key added as `""` then removed from every subject row | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U05 | [web] `handleRepeatAll` with source Monday and two rows | Every other active day equals Monday's value in each row; special rows untouched | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U06 | [web] `handleRepeatOneSubject` for subject S; row A has S on Tuesday, row B has no S | Row A all days S; row B unchanged | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U07 | [web] `classSubjectIds` with mappings `{section null, subject1}`, `{sectionA, subject2}`, `{sectionB, subject3}` and section A selected | Set contains subject1 and subject2 only | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U08 | [web] `daysWithData` and `subjectsInRows` for rows holding Monday and Wednesday subjects | `[Monday, Wednesday]` and only the subjects used | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-08-U09 | [mobile] `addCustomEvent("morning prayer")` | value `MORNING_PRAYER`, label `Morning prayer` | blocked: needs the helper exported from mobile/app/masters/timetable.tsx |
| TC-TTC-08-U10 | [mobile] `handleRepeatOneSubject("Tuesday")` on the selected row | The row's other days take Tuesday's value; other rows untouched | blocked: needs the helper exported from mobile/app/masters/timetable.tsx |
| TC-TTC-08-U11 | [mobile] `handleRepeatAllForWeek` with an empty source cell | Other days become `""` (documents the 422 cause) | blocked: needs the helper exported from mobile/app/masters/timetable.tsx |
| TC-TTC-08-A01 | PUT a special row labelled `MORNING_PRAYER`, then `GET` | Row returned with `label:"MORNING_PRAYER"` | passing |
| TC-TTC-08-A02 | POST a table that has a Saturday value, then PUT the same table | POST drops Saturday; PUT keeps it (compare the two `GET` results) | passing |
| TC-TTC-08-A03 | PUT a Saturday cell with free text `Sports` | 422 | passing |
| TC-TTC-08-A04 | PUT subject rows using a subject not mapped to the class | 200 (not checked) | passing |
| TC-TTC-08-A05 | `GET /masters/class-subject-mappings/by-class/{class}` as Admin after bulk mapping with `section_id` null and one section-specific mapping | Rows for the class (class-level and section-level) used to build the picker; subject ids repeat per section | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-08-E01 | P2 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Tick "Include Saturday".<br>5. Open the Saturday cell of a subject row. | Saturday column appears; the cell placeholder is "Subject / Event / Holiday..."; the menu has groups "Subjects" and "Events" (Snacks, Lunch, Dispersal) | planned |
| TC-TTC-08-E02 | P3 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A", click "Edit".<br>3. Tick "Include Saturday".<br>4. Choose "Lunch" under "Events" in a Saturday cell.<br>5. Click "Save".<br>6. Replace the Saturday value with "English" and click "Save". | Step 5: toast "Invalid data provided"; stays in edit mode. Step 6: toast "Timetable saved successfully" | planned |
| TC-TTC-08-E03 | P3 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A", click "Edit".<br>3. Tick "Include Saturday" and choose "English" in a Saturday cell.<br>4. Untick "Include Saturday". | The Saturday column and its values disappear; ticking again shows empty Saturday cells | planned |
| TC-TTC-08-E04 | P2 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A", click "Edit".<br>3. Click "+ Add Special Row".<br>4. Type "Assembly" in "Select or create event..." and choose `Create "Assembly"`. | Toast "Created custom event: Assembly"; the row label shows "Assembly" | planned |
| TC-TTC-08-E05 | P3 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A", click "Edit".<br>3. Click "+ Add Special Row".<br>4. Type "Assembly!" and choose `Create "Assembly!"`. | Toast "Event name must be 1-50 alphanumeric characters"; the label stays "Snacks" | planned |
| TC-TTC-08-E06 | P3 | Web | Admin | TC-TTC-08-E04 done in the same editing session | 1. On the special row type "assembly" and choose `Create "assembly"`. | Toast "This event already exists" | planned |
| TC-TTC-08-E07 | P3 | Web | Admin | TC-TTC-08-E04 done | 1. Set the Assembly row times 8:30 AM to 8:45 AM.<br>2. Click "Save".<br>3. Choose section "3-B", then "3-A" again. | The row shows "Assembly" (rebuilt from the saved label `ASSEMBLY`); in edit mode "Assembly" is offered in the special-row menu | planned |
| TC-TTC-08-E08 | P2 | Web | Admin | Class 3 mappings as seeded (8 subjects; Environmental Studies and Art and Craft not mapped) | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-B" (edit mode).<br>3. Click "+ Add Subject Row".<br>4. Open the Monday "Select..." dropdown. | Only the 8 mapped subjects are listed; Environmental Studies and Art and Craft are absent | planned |
| TC-TTC-08-E09 | P1 | Web | Admin | TC-TTC-07-E01 done | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A", click "Edit".<br>3. Add two more subject rows (10:00 AM to 10:45 AM, 11:00 AM to 11:45 AM) with "English" and "Hindi" on Monday only.<br>4. Click "Repeat All for Week".<br>5. Choose "Monday" in "Copy from day".<br>6. Click "Apply to All Days". | Toast "Monday's schedule applied to all days"; Tuesday to Friday of every subject row equal Monday's subject; special rows unchanged | planned |
| TC-TTC-08-E10 | P2 | Web | Admin | TC-TTC-08-E09 steps 1 to 3 done | 1. Change the Tuesday cell of the 10:00 AM row to "Mathematics".<br>2. Click "Repeat One Subject".<br>3. Choose "Mathematics" in "Subject".<br>4. Click "Apply to All Days". | Toast "Mathematics applied to all days"; every row that held Mathematics on any day (9:00 AM and 10:00 AM rows) now has Mathematics on all days; the 11:00 AM row is unchanged | planned |
| TC-TTC-08-E11 | P3 | Web | Admin | Section 3-B has no timetable | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-B". | "Repeat All for Week" and "Repeat One Subject" are disabled | planned |
| TC-TTC-08-E12 | P2 | Mobile | Admin | TC-TTC-07-E12 done | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-A".<br>3. Tap "Edit".<br>4. Tap the checkbox next to "Include Saturday". | Each subject row gains a "Sat" dropdown "Select Subject" (tapping the label text does nothing) | planned |
| TC-TTC-08-E13 | P2 | Mobile | Admin | TC-TTC-07-E12 done | 1. Open "Timetable" > "Class 4" > "4-A" and tap "Edit".<br>2. Tap "Add Subject" and choose "Hindi" on Mon only.<br>3. Tap "Repeat All for Week".<br>4. Tap "Monday". | Modal "Repeat All for Week" with "Copy this day's subjects to all other days" and Monday to Friday; after the tap every subject row copies Monday to the other days; no toast | planned |
| TC-TTC-08-E14 | P2 | Mobile | Admin | TC-TTC-07-E12 done | 1. Open "Timetable" > "Class 4" > "4-A" and tap "Edit".<br>2. Set the Tue dropdown of the 9:00 AM row to "Mathematics".<br>3. Tap "Repeat One Subject".<br>4. Tap the 9:00 AM to 9:45 AM entry.<br>5. Tap "Tuesday". | Titles "Select Period to Repeat" then "Select Source Day"; only that row's other days become Mathematics; other rows unchanged | planned |
| TC-TTC-08-E15 | P3 | Mobile | Admin | TC-TTC-07-E12 done | 1. Open "Timetable" > "Class 4" > "4-A" and tap "Edit".<br>2. Tap "Add Special".<br>3. Type "assembly" in "Select Special Activity" and choose `Create "assembly"`.<br>4. Tap "Save Timetable". | The option is added with label "Assembly"; after saving, view mode shows the label "ASSEMBLY" | planned |
| TC-TTC-08-E16 | P3 | Mobile | Admin | TC-TTC-07-E12 done | 1. Open "Timetable" > "Class 4" > "4-A" and tap "Edit".<br>2. Tap "Add Special".<br>3. Type "Assembly!" in "Select Special Activity" and choose the create option. | No option is added and no message appears; the row keeps "Snacks" (mobile ignores invalid names silently) | planned |

---

## F09 Delete a section timetable

**Purpose.** Remove a section's timetable entirely, for example before deleting the section's class, or to start over. There is no button for it on either client; it is an API-only action.

**Roles and permissions.** `timetable_management:delete`. Admin only.

**Preconditions.** The section has a timetable (F07).

**Steps, web.** No UI.

**Steps, mobile.** No UI. The class delete flow in `docs/features/masters.md` (MST F04) requires clearing a section timetable first and refers to this endpoint.

**Expected results.** The timetable row, its slots, subject options and the section's slot times are removed; reading the section returns 404; the class or section can then be deleted if nothing else references it.

**API endpoints.**
- `DELETE /api/v1/students/timetable/frontend/{section_id}` -> 200 `{message:"Timetable deleted successfully for section <id>"}`.

**Rules and validations.**
1. Deletion order: subject options, slots, slot times of the section, then the timetable.
2. A section without a timetable: 404 `Timetable not found for section`.
3. A timetable counts as a dependency when deleting a class (MST F04 rule 4); this endpoint clears that dependency.

**Error and edge cases.**
- Second delete: 404.
- Roles without delete: 403. Failure inside the transaction: 500 `Error deleting timetable: ...` with rollback.

**Unit-testable logic.**
- `delete_frontend_timetable` with a fake session: statements issued in the stated order; 404 when absent; rollback and 500 on failure.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-09-U01 | [backend] `delete_frontend_timetable` with a fake timetable and 2 slots | Deletes options, then slots, then slot times, then the timetable; one commit | passing |
| TC-TTC-09-U02 | [backend] `delete_frontend_timetable` with no timetable | HTTPException 404 `Timetable not found for section` | passing |
| TC-TTC-09-U03 | [backend] A delete statement raises | Rollback and HTTPException 500 `Error deleting timetable` | passing |
| TC-TTC-09-A01 | Admin `DELETE /frontend/{section}` after F07 | 200 `{message:"Timetable deleted successfully for section <id>"}` | passing |
| TC-TTC-09-A02 | `GET /frontend/{section}` after the delete | 404 | passing |
| TC-TTC-09-A03 | `DELETE` again; `DELETE` for a section that never had one | 404 `Timetable not found for section` each | passing |
| TC-TTC-09-A04 | After deleting, `POST /frontend` for the same section | 200 (a new timetable can be created) | passing |
| TC-TTC-09-A05 | Class delete (`DELETE /masters/class_sections/{class}`) before and after clearing a section's timetable | 400 `section-related record(s)` before; 204 after | passing |
| TC-TTC-09-A06 | Write matrix: DELETE as Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-TTC-09-A07 | No Authorization header | 401 | passing |
| TC-TTC-09-A08 | Tenant isolation: tenant B `DELETE` for tenant A's section | 404; tenant A's timetable intact | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-09-E01 | P2 | Web | Admin | TC-TTC-07-E01 done, then TC-TTC-09-A01 run for section 3-A | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A". | Empty grid in edit mode ("Save", "+ Add Subject Row", "+ Add Special Row") | planned |
| TC-TTC-09-E02 | P3 | Web | Admin | Seeded timetable of 1-A | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 1" and "1-A".<br>3. Look for a control that deletes the whole timetable in view and edit mode. | None exists (delete is API only) | planned |
| TC-TTC-09-E03 | P2 | Mobile | Admin | TC-TTC-07-E12 done, then TC-TTC-09-A01 run for section 4-A | 1. Sign in as Admin on mobile.<br>2. Open "Timetable" > "Class 4" > "4-A". | Edit mode with the single default row 9:00 AM to 9:45 AM | planned |

---

## F10 Timetable export (PNG, CSV, Excel)

**Purpose.** An admin (or any user who can view the grid) saves the displayed timetable as an image or a spreadsheet. Export happens entirely in the client.

**Roles and permissions.** No API call. Available to whoever sees the grid in view mode (in practice Admin, because the data needs `timetable_management:read`).

**Preconditions.** A section with at least one row is displayed in view mode (F06).

**Steps, web.**
1. "Export" (visible only in view mode with rows) > "Save as PNG", "Save as CSV" or "Save as Excel". Files are named `Timetable - <class> - <section>.png`, `.csv` and `.xls`.
2. CSV and Excel contain a header row "Time" plus the active day names, and one row per timetable row: a 12-hour range `h:mm AM - h:mm PM` (or `--` when a time is missing), the subject name per day (`--` when empty; Saturday uses "Holiday" for empty, the subject name, the event label or the free text), and for special rows the label repeated in every day column. Excel is an HTML table saved with the `.xls` extension. PNG is an image of the grid without the action buttons.
3. Failure toasts "Failed to export PNG", "Failed to export CSV", "Failed to export Excel".

**Steps, mobile.**
1. In view mode "Export" > "Export As": "Export CSV", and on the web build also "Export Excel" and "Export PNG". On the web build files download with the same names. On a device only "Export CSV" is listed and it opens the share sheet with the text (the info toasts "Excel export is only available on web." and "PNG export is only available on web." exist in code but cannot be reached). Failure toasts "Error - Failed to export CSV", "Failed to export Excel", "Failed to export PNG".
2. Mobile CSV content differs from web: times as stored (`09:00-09:45`), day headers Monday to Friday (and Saturday), the subject name or an empty cell, and a special row's label as stored (`LUNCH`) in the first day column only.

**Expected results.** The exported content matches the displayed grid exactly.

**API endpoints.** None.

**Rules and validations.**
1. Web CSV quotes every cell and doubles double quotes; mobile CSV quotes only cells that contain a comma or a double quote.
2. Excel output is HTML, not a true workbook.
3. Export is disabled while editing.

**Error and edge cases.**
- No rows: the Export button is not shown.
- Mobile CSV rows for special rows have the label in the first day column and empty cells after it.

**Unit-testable logic.**
- Web `generateTableData` and `getFileName`; CSV quoting; Excel HTML builder. Mobile `generateCSVData`. These live in the editor files and need extracting.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-10-U01 | [web] `generateTableData` for 1 subject row and 1 special row with 5 active days | Header `Time,Monday..Friday`; subject row has names or `--`; special row repeats the label 5 times | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U02 | [web] Same with Saturday active and an empty Saturday cell | Saturday column header present; empty cell text `Holiday` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U03 | [web] `getFileName("csv")` for class `QA-C1` section `A` | `Timetable - QA-C1 - A.csv` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U04 | [web] CSV builder with a cell containing a double quote | The quote is doubled inside quoted cells | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U05 | [mobile] `generateCSVData` header and row shape for the same input | Header `Time` plus the capitalised day names; one row per timetable row; the time cell is `from-to` as stored (24-hour `HH:MM`); a special row has its label in the first day column and empty remaining cells | blocked: needs generateCSVData exported from mobile/app/masters/timetable.tsx |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-10-E01 | P1 | Web | Admin | Seeded timetable of 1-A | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 1" and "1-A".<br>3. Click "Export".<br>4. Click "Save as CSV". | File `Timetable - Class 1 - 1-A.csv` downloads; first row `"Time","Monday",...,"Friday"`; one row per grid row with the 12-hour range, the subject names, and "Snacks" or "Lunch" repeated in all five day columns; every cell quoted | planned |
| TC-TTC-10-E02 | P2 | Web | Admin | Seeded timetable of 1-A | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 1" and "1-A".<br>3. Click "Export" > "Save as Excel". | File `Timetable - Class 1 - 1-A.xls` downloads; it opens as a table with the same cells as the CSV | planned |
| TC-TTC-10-E03 | P2 | Web | Admin | Seeded timetable of 1-A | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 1" and "1-A".<br>3. Click "Export" > "Save as PNG". | File `Timetable - Class 1 - 1-A.png` downloads showing the whole grid (all day columns) without edit controls | planned |
| TC-TTC-10-E04 | P3 | Web | Admin | TC-TTC-07-E01 done (3-A has a saved timetable) | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit".<br>4. Click "Save" without changes. | Step 3: "Export" disappears. Step 4: toast "Timetable saved successfully" and "Export" returns | planned |
| TC-TTC-10-E05 | P3 | Web | Admin | Section 3-B has no timetable | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-B". | No "Export" button | planned |
| TC-TTC-10-E06 | P2 | Mobile | Admin | Seeded timetable of 1-A; Expo web build | 1. Sign in as Admin on mobile (Expo web).<br>2. Open "Timetable" > "Class 1" > "1-A".<br>3. Tap "Export".<br>4. Tap "Export CSV". | "Export As" lists "Export CSV", "Export Excel", "Export PNG"; `Timetable - Class 1 - 1-A.csv` downloads with times like `09:00-10:00` and SNACKS or LUNCH in the Monday column only | planned |
| TC-TTC-10-E07 | P3 | Mobile | Admin | Seeded timetable of 1-A; native Android or iOS build | 1. Sign in as Admin in the native app.<br>2. Open "Timetable" > "Class 1" > "1-A".<br>3. Tap "Export". | "Export As" lists only "Export CSV"; tapping it opens the share sheet with the CSV text | planned |

---

## F11 Student and parent timetable viewer (mobile)

**Purpose.** A student sees their own section's weekly timetable and a parent sees the selected child's, one day at a time. Web has no equivalent viewer.

**Roles and permissions.** The screen resolves the section and then calls `GET /students/timetable/frontend/{section_id}` (`timetable_management:read`) and `GET /masters/subjects` (`subjects:list`) to turn subject ids into names. Student and Parent hold `subjects:list` but, in the default seed, no `timetable_management:read`, so the timetable call returns 403 and the screen shows an error (see Known gaps). Staff and Admin see an information message instead of a timetable.

**Preconditions.** A saved timetable for the child's section (F07). For a Student the admission record gives the section; for a Parent a student is selected in the header selector.

**Steps, web.** Not available. The web editor route `/TimeTable` does not select the user's own section and Student and Parent have no menu entry for it.

**Steps, mobile.**
1. The screen route is `/timetable` with the title "My Timetable". No menu entry, hub card or tab links to it in the current app (the Student and Parent Dashboard shows only Students, Exam Management and Fee Management), so it opens only by route (for example on the Expo web build).
2. Banner "Class Timetable" with the line "Your weekly class schedule" (student) or "<first name>'s schedule" (parent selected) or "Weekly class schedule".
3. Admin, Staff and Teacher see "Timetable viewer is available for students and parents only. Staff timetable is available in the Masters section."
4. A parent with no selected child: "No student selected. Use the selector in the header." No section: "No class section assigned yet." Failed load: "Failed to load timetable". Empty: "No timetable has been set up yet. Contact your class teacher."
5. Day chips Mon to Sat (the current weekday has a dot; Sunday opens on Monday). The heading shows the day name. One card per period for that day: the start and end time as stored (`HH:MM`), then the subject name with a "SUBJECT" badge, or the label with a "SPECIAL" badge, and the period number "P1", "P2". A day with no periods shows "No periods scheduled".

**Expected results.** Special rows appear on every day; a subject row appears only on days that have a subject; subject names replace ids.

**API endpoints.**
- `GET /api/v1/students/admission/my-admission` (Students module) for a student's section (`current_section_id`, else `admitted_section_id`).
- `GET /api/v1/students/timetable/frontend/{section_id}` (F06).
- `GET /api/v1/masters/subjects/?active_only=true` (MST F08).

**Rules and validations.**
1. A parent's section comes from `selectedStudent.section_id`; a student's from the admission record.
2. The special-row filter shows a special row on every day; a subject row shows only when the selected day has a subject.
3. Period numbers follow the order the API returns rows, which is not chronological (F06 rule 2), so "P1" may not be the earliest period.
4. Times are shown as stored, in 24-hour form.
5. The subject name map only holds active subjects; a deactivated subject shows its raw id.

**Error and edge cases.**
- Student or Parent without `timetable_management:read`: the timetable call returns 403 and the screen shows "Failed to load timetable".
- A deactivated subject shows its UUID instead of a name.

**Unit-testable logic.**
- Mobile (extract from `app/timetable.tsx`): `periodsForDay` filter (special visible on every day; subject rows only when the day key exists), `TODAY_IDX` clamp (Sunday maps to Monday), section resolution by role, subject-name map fallback to id.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-11-U01 | [mobile] `periodsForDay` for rows `[special LUNCH, subject {Monday:S1}, subject {Tuesday:S2}]` on Monday | LUNCH and the Monday subject row; the Tuesday row excluded | blocked: needs the helper exported from mobile/app/timetable.tsx |
| TC-TTC-11-U02 | [mobile] Initial selected day when today is Sunday, Wednesday, Saturday | Monday, Wednesday, Saturday | blocked: needs the helper exported from mobile/app/timetable.tsx |
| TC-TTC-11-U03 | [mobile] Section resolution: student with `current_section_id=null` and `admitted_section_id=X`; parent with `selectedStudent.section_id=Y` | X; Y | blocked: needs the helper exported from mobile/app/timetable.tsx |
| TC-TTC-11-U04 | [mobile] Subject name map missing an id | The card shows the raw id | blocked: needs the helper exported from mobile/app/timetable.tsx |
| TC-TTC-11-A01 | Student `GET /students/timetable/frontend/{own section}` (default seed) | 403 `Permission not found in database` | passing |
| TC-TTC-11-A02 | Parent `GET /students/timetable/frontend/{child's section}` (default seed) | 403 | passing |
| TC-TTC-11-A03 | After a fixture grants `timetable_management:read` to Student and Parent, repeat A01 and A02 | 200 with the section's `timetable_data` | skipped: Needs a fixture that grants timetable_management:read to Student and Parent; |
| TC-TTC-11-A04 | Student `GET /masters/subjects/?active_only=true` | 200 plain array including the subjects used by the timetable | passing |
| TC-TTC-11-A05 | Student `GET /students/admission/my-admission` | 200 with `current_section_id` or `admitted_section_id` (Students module contract used here) | skipped: The QA Student login has no linked student record, so my-admission has no section to return; |
| TC-TTC-11-A06 | Student requests another section's timetable (with the read grant fixture) | 200 (the API does not restrict by own section; recorded as a scope gap) | skipped: Depends on the timetable_management:read grant fixture for Student, which the QA rules forbid |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-11-E01 | P1 | Mobile | Student | Seeded student Harsha Raju (004) in Class 1 with a seeded section timetable; Student role granted `timetable_management:read` | 1. Sign in as Harsha Raju (login 004) on mobile.<br>2. Open the route `/timetable`. | "My Timetable" with banner "Class Timetable" and "Your weekly class schedule"; day chips Mon to Sat with a dot on today; cards with stored times (`09:00` `10:00`), subject names with "SUBJECT" badges and P1, P2 numbers | blocked: Student has no `timetable_management:read` in the default seed, so the call returns 403 (Known gaps 5) |
| TC-TTC-11-E02 | P2 | Mobile | Student | TC-TTC-11-E01 preconditions | 1. Sign in as Harsha Raju (004).<br>2. Open `/timetable`.<br>3. Tap "Sat". | "No periods scheduled" (the seeded timetable has no Saturday), except the special rows | blocked: Student has no `timetable_management:read` in the default seed (Known gaps 5) |
| TC-TTC-11-E03 | P2 | Mobile | Student | TC-TTC-11-E01 preconditions | 1. Sign in as Harsha Raju (004).<br>2. Open `/timetable`.<br>3. Tap each day chip. | "SNACKS" and "LUNCH" appear on every day with a "SPECIAL" badge | blocked: Student has no `timetable_management:read` in the default seed (Known gaps 5) |
| TC-TTC-11-E04 | P2 | Mobile | Parent | Seeded parent venkat.raju@example.com (Harsha and Tanvi Raju); Parent role granted `timetable_management:read` | 1. Sign in as venkat.raju@example.com on mobile.<br>2. Select Harsha in the header student selector.<br>3. Open `/timetable`. | Banner shows "Harsha's schedule" and Harsha's Class 1 section timetable | blocked: Parent has no `timetable_management:read` in the default seed (Known gaps 5) |
| TC-TTC-11-E05 | P2 | Mobile | Parent | QA Parent login (no linked student) | 1. Sign in as the QA Parent on mobile.<br>2. Open the route `/timetable`. | Banner "Class Timetable" with "Weekly class schedule" and the text "No student selected. Use the selector in the header." | planned |
| TC-TTC-11-E06 | P3 | Mobile | Parent | Seeded parent venkat.raju@example.com; Tanvi Raju (005) is in Class 4, whose sections have no timetable; read grant as in TC-TTC-11-E04 | 1. Sign in as venkat.raju@example.com.<br>2. Select Tanvi.<br>3. Open `/timetable`. | "Failed to load timetable" (a 404 is treated as an error); "No timetable has been set up yet. Contact your class teacher." appears only for a timetable saved with no rows | blocked: Parent has no `timetable_management:read` in the default seed (Known gaps 5) |
| TC-TTC-11-E07 | P2 | Mobile | Student | Seeded student Harsha Raju (004); default role grants | 1. Sign in as Harsha Raju (004) on mobile.<br>2. Open the route `/timetable`. | "Failed to load timetable" (API 403; records Known gaps 5) | planned |
| TC-TTC-11-E08 | P2 | Mobile | Admin | Admin login | 1. Sign in as Admin on mobile.<br>2. Open the route `/timetable`. | "Timetable viewer is available for students and parents only. Staff timetable is available in the Masters section." | planned |
| TC-TTC-11-E09 | P3 | Mobile | Student | Seeded student Harsha Raju (004) | 1. Sign in as Harsha Raju (004) on mobile.<br>2. Look at the Dashboard modules, tabs and drawer. | Dashboard modules are Students, Exam Management, Fee Management; no entry opens `/timetable` (records Known gaps 5) | planned |
| TC-TTC-11-E10 | P3 | Mobile | Student | QA Student login (no linked student) | 1. Sign in as the QA Student on mobile.<br>2. Open the route `/timetable`. | Banner "Class Timetable" with "Your weekly class schedule" and the text "No class section assigned yet." | planned |

---

## F12 School calendar, read-only (mobile)

**Purpose.** Every mobile user can see upcoming and past school holidays and events, as a list grouped by month or as a month grid.

**Roles and permissions.** `holiday_management:list` on `GET /masters/holidays/`. Admin, Staff and Teacher hold it; Student and Parent do not in the default seed, so they receive 403 and the screen shows an error. The screen has no in-app guard.

**Preconditions.** Holidays exist for the working year (F02) and are active.

**Steps, web.** Not applicable; the web Calendar entry shows the editable calendar of F01.

**Steps, mobile.**
1. Route `/calendar`, title "School Calendar". No tab, hub or drawer entry opens it today (reachable by route): the Dashboard tile and drawer entry "Calendar" carry the web path `/Calender`, which has no mobile mapping, so tapping it stays on the Dashboard. A banner shows "School Calendar" and "Next holiday: <name> on <date>" or "No upcoming holidays".
2. Stat cards "Total", "Upcoming", "Past". Filter chips "Upcoming" (default), "All", "Past". View toggle: list icon or grid icon.
3. List: month headers in capitals (for example "NOVEMBER 2026"), cards with a colour bar, the name, a duration badge such as "3d" for multi-day events, the date range, the description (two lines), past events dimmed, an upcoming dot on upcoming events. Empty texts "No upcoming holidays", "No past holidays", "No holidays found".
4. Grid: month title with back and next arrows ("Go back", "Next"); Su to Sa headers; today highlighted; up to three coloured dots per day; tapping a day with holidays shows a panel with the date and the event names.
5. Pull down to refresh. Failure: "Failed to load holidays" with a "Retry" button.

**Expected results.** Only active holidays of the working year, up to 100, sorted by start date; upcoming means the end date is today or later.

**API endpoints.**
- `GET /api/v1/masters/holidays/?academic_year_id=<id>&active_only=true&limit=100`.

**Rules and validations.**
1. The request passes `limit=100`, so up to 100 holidays are shown (the admin month views show 10).
2. Event colour is the stored colour; if empty the app derives one of seven colours from a hash of the name (deterministic).
3. Upcoming and past are decided on the device's current date at the time the app loaded.
4. Dates are shown with the device locale month names (English); grid cells compare `YYYY-MM-DD` strings.

**Error and edge cases.**
- A holiday that starts before today but ends today or later is Upcoming.
- Student and Parent: 403 gives the error state with "Retry".
- More than 100 active holidays in a year are not all shown.

**Unit-testable logic.**
- Mobile (extract from `app/calendar.tsx`): `holidayColor` determinism and fallback, `formatDateRange` (single day, same month, across months), `getDuration`, `isUpcoming` and `isPast` around the boundary (end date equal to today), filter and sort, month grouping, `buildMonthGrid`, `getHolidaysForDate`, stats counts and the next-holiday banner text.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-12-U01 | [mobile] `holidayColor` for a holiday with `color:"#ff0000"` and for two calls with the same name and no colour | `#ff0000`; the same colour from the palette both times | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U02 | [mobile] `formatDateRange` for `2026-11-08` to `2026-11-08`, `2026-11-08` to `2026-11-10`, `2026-11-30` to `2026-12-02` | Single date `8 Nov 2026`; day range within the month; both months shown | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U03 | [mobile] `getDuration("2026-11-08","2026-11-10")` and for one day | 3 and 1 | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U04 | [mobile] `isUpcoming` with end date today, yesterday, tomorrow | true, false, true; `isPast` the complement | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U05 | [mobile] Filter "Past" and sorting with three holidays out of order | Past ones only, ascending by start date | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U06 | [mobile] Month grouping of holidays in Nov and Dec | Two groups keyed `November 2026` and `December 2026` | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U07 | [mobile] `buildMonthGrid(2026, 10)` and `getHolidaysForDate("2026-11-09")` for a holiday 8 to 10 Nov | Padded weeks of 7; the holiday returned | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-U08 | [mobile] Stats and banner with 4 holidays (3 upcoming) | Total 4, Upcoming 3, Past 1; banner names the earliest upcoming holiday | blocked: needs the helper exported from mobile/app/calendar.tsx |
| TC-TTC-12-A01 | Teacher `GET /masters/holidays/?academic_year_id=Y&active_only=true&limit=100` | 200 `{items,total_count,has_next}`; up to 100 items | passing |
| TC-TTC-12-A02 | 101 active holidays in the year and `limit=100` | 100 items, `has_next` true | skipped: Needs 101 active holidays in one year; |
| TC-TTC-12-A03 | `limit=1000` | 200 (no upper bound on the API) | passing |
| TC-TTC-12-A04 | Staff `GET` the same | 200 | passing |
| TC-TTC-12-A05 | Student and Parent `GET` the same | 403 each (default seed) | passing |
| TC-TTC-12-A06 | Without an Authorization header | 401 | passing |
| TC-TTC-12-A07 | Tenant isolation: tenant B with tenant A's `academic_year_id` | Empty `items` | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-12-E01 | P1 | Mobile | Teacher | Seeded holidays; counts below are for a test date of 2026-10-07 (recompute for later dates) | 1. Sign in as Teacher on mobile.<br>2. Open the route `/calendar`. | "School Calendar" banner "Next holiday: Dasara Vacation on" and the date 17 Oct 2026; stats Total 8, Upcoming 5, Past 3; chip "Upcoming" active; month headers "OCTOBER 2026", "NOVEMBER 2026" and so on with 5 cards | planned |
| TC-TTC-12-E02 | P2 | Mobile | Teacher | Seeded holidays | 1. Sign in as Teacher on mobile.<br>2. Open `/calendar`.<br>3. Tap "Past".<br>4. Tap "All". | "Past": Independence Day, Ganesh Chaturthi, Gandhi Jayanti, dimmed, under "AUGUST 2026", "SEPTEMBER 2026", "OCTOBER 2026". "All": 8 cards sorted by start date | planned |
| TC-TTC-12-E03 | P3 | Mobile | Teacher | Seeded holiday Dasara Vacation (8 days) | 1. Sign in as Teacher on mobile.<br>2. Open `/calendar`.<br>3. Find the "Dasara Vacation" card. | Yellow colour bar, badge "8d", the date range 17 to 24 Oct 2026, description "Dasara festival break", upcoming dot | planned |
| TC-TTC-12-E04 | P2 | Mobile | Teacher | Seeded holidays | 1. Sign in as Teacher on mobile.<br>2. Open `/calendar`.<br>3. Tap the grid icon.<br>4. Go to October 2026 with the arrows.<br>5. Tap 20 Oct.<br>6. Tap 5 Oct. | Headers Su to Sa; dots on 2 Oct and 17 to 24 Oct; step 5 shows a panel with the date and "Dasara Vacation"; step 6 shows no panel | planned |
| TC-TTC-12-E05 | P2 | Mobile | Teacher | A working year with no active holidays (switch the academic year at sign-in to a year without holidays, if one exists) | 1. Sign in as Teacher on mobile with that year.<br>2. Open `/calendar`. | Banner "No upcoming holidays"; stats 0, 0, 0; list text "No upcoming holidays" | planned |
| TC-TTC-12-E06 | P3 | Mobile | Teacher | Seeded holidays; "QA Picnic" added by Admin after the Teacher opened the screen (TC-TTC-02-E07) | 1. Sign in as Teacher on mobile and open `/calendar`.<br>2. As Admin create "QA Picnic".<br>3. Pull the list down to refresh. | "QA Picnic" appears and Total increases by 1 | planned |
| TC-TTC-12-E07 | P2 | Mobile | Student | Seeded student Harsha Raju (004); default role grants | 1. Sign in as Harsha Raju (004) on mobile.<br>2. Open the route `/calendar`. | "Failed to load holidays" with a "Retry" button; stats 0 (records Known gaps 5) | planned |
| TC-TTC-12-E08 | P3 | Mobile | Admin | Admin login | 1. Sign in as Admin on mobile.<br>2. Tap the Dashboard module tile "Calendar". | The app stays on the Dashboard; "School Calendar" does not open (the `/Calender` menu path has no mobile mapping; records Known gaps 5) | planned |

---

## F13 Legacy timetable endpoints: bulk create, grouped read, slot patch, test

**Purpose.** These endpoints predate the row-by-day editor API. They are not used by the web or mobile editors but remain mounted and must keep their documented behaviour until removed.

**Roles and permissions.** `POST /bulk`: `timetable_management:create`. `GET /section/{section_id}`: `timetable_management:read`. `PATCH /timetable/slots/bulk`: `timetable_management:update`. `GET /test`: none (no authentication). Only Admin holds the three permissions in the default seed.

**Preconditions.** For `POST /bulk` the `slot_time_id` values must already exist (created by saving another section's timetable through F07). For the others a timetable exists.

**Steps, web.** No screen. `src/api/timetable.ts` still exports `createFullTimetable`, `getTimetableBySection` and `bulkUpdateTimetableSlots` (the last calls a path that does not exist), and `src/api/hooks/masters/timetable.ts` targets routes that do not exist; no page uses them.

**Steps, mobile.** No screen. `timetableApi` in `mobile/src/api/students.ts` exports `bulkCreateTimetable`, `getTimetableBySection` and `bulkUpdateTimetableSlots`; no screen calls them.

**Expected results.** Bulk create stores a timetable from normalised slots; the grouped read returns slots grouped by slot time with names; the patch changes individual slots.

**API endpoints.** Prefix `/api/v1/students/timetable`.
- `POST /bulk` `{section_id, slot_time_data:[{slot_time_id, slots:[{day, is_break=false, break_label?, subject_options:[{subject_id}]}]}]}` -> 200, the new timetable object (`id` and `section_id`; `created_at` may be absent because the raw model is returned).
- `GET /section/{section_id}` -> `{section_id, section_name, class_name, slot_time_data:[{slot_time_id, slots:[{id, day, is_break, break_label, subject_options:[{id, subject_id, subject_name}]}]}]}`.
- `PATCH /timetable/slots/bulk` (full path `/students/timetable/timetable/slots/bulk`) `{slots:[{id, day?, is_break?, break_label?, subject_options?}]}` -> `[TimetableSlotOut]`.
- `GET /test` -> `{message:"Test endpoint working"}`.

**Rules and validations.**
1. Slot validation (create and patch): a break (`is_break:true`) needs a `break_label` and no `subject_options`; a non-break slot must not carry a `break_label` and must carry at least one `subject_options` item. A patch item that is not a break therefore always needs `subject_options`.
2. `POST /bulk` creates one timetable per section (unique `section_id`; a second call returns a server error) and does not validate that slot times belong to the section.
3. `GET /section/{id}` returns 404 `Timetable not found for section` when none exists; groups are in database order.
4. `PATCH` replaces a slot's subject options when `subject_options` is sent; sending `is_break:true` with a label sets the flag and label but leaves existing options attached; an unknown slot id is 404 `Slot with id <id> not found`. The branch returning 400 for options on a break cannot be reached because the schema rejects that combination first.
5. The web helper that patches `/students/timetable/slots/bulk` (without the doubled segment) hits a path that does not exist.
6. `GET /test` is registered without authentication and returns a fixed message.

**Error and edge cases.**
- A bad `slot_time_id` on bulk create fails with a server error (foreign key).
- Non-admin roles get 403 on the three authenticated endpoints.

**Unit-testable logic.**
- `TimetableSlotCreate` and `TimetableSlotBulkUpdateItem` validators (all branches).
- `add_full_timetable` and `bulk_update_timetable_slots` with fake sessions: not found raises 404; subject options replaced; break flags set.
- `get_timetable_by_section` grouping with fake slots.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-13-U01 | [backend] `TimetableSlotCreate(is_break=True, break_label="LUNCH")`; with `subject_options` also set; without a label | Valid; error `must not be provided when is_break is True`; error `break_label is required` | passing |
| TC-TTC-13-U02 | [backend] `TimetableSlotCreate(is_break=False)` with no options; with a label | Errors `subject_options must be provided...` and `break_label must not be provided...` | passing |
| TC-TTC-13-U03 | [backend] `TimetableSlotBulkUpdateItem(id=..., day="Monday")` with no `subject_options` | Validation error (non-break needs options) | passing |
| TC-TTC-13-U04 | [backend] `bulk_update_timetable_slots` with an unknown slot id | HTTPException 404 `Slot with id <id> not found` | passing |
| TC-TTC-13-U05 | [backend] `bulk_update_timetable_slots` with new options for a slot that had two | Old options deleted, new ones added | passing |
| TC-TTC-13-U06 | [backend] `get_timetable_by_section` with 3 fake slots over 2 slot times | `slot_time_data` has 2 groups with 2 and 1 slots | passing |
| TC-TTC-13-A01 | `GET /section/{section}` after F07 saved 2 rows and a special row | 200; `slot_time_data` groups with slots carrying `id`, `day`, `is_break`, `break_label`, `subject_options[].subject_name` | passing |
| TC-TTC-13-A02 | `GET /section/{section}` without a timetable | 404 `Timetable not found for section` | passing |
| TC-TTC-13-A03 | Admin `POST /bulk` for a new section reusing a `slot_time_id` from another section's saved timetable, one subject slot and one break slot | 200 with `id` and `section_id`; `GET /section/{new}` returns the slots | passing |
| TC-TTC-13-A04 | `POST /bulk` for the same section again | First 200; second 400 | passing |
| TC-TTC-13-A05 | `POST /bulk` with a break slot lacking a label; a subject slot without options | 422 each | passing |
| TC-TTC-13-A06 | `POST /bulk` with a random `slot_time_id` | 400; no timetable is stored (`GET /section/{id}` 404) | passing |
| TC-TTC-13-A07 | Admin `PATCH /timetable/slots/bulk` `{slots:[{id:<slot>, subject_options:[{subject_id:<other>}]}]}` | 200 list with the slot now holding only the new subject option | passing |
| TC-TTC-13-A08 | PATCH `{slots:[{id:<slot>, is_break:true, break_label:"LUNCH"}]}` | 200; slot `is_break` true, `break_label` "LUNCH"; existing options unchanged | passing |
| TC-TTC-13-A09 | PATCH an item without `subject_options` and without `is_break` | 422 | passing |
| TC-TTC-13-A10 | PATCH `is_break:true` together with `subject_options` | 422 | passing |
| TC-TTC-13-A11 | PATCH with a random slot id | 404 `Slot with id ... not found` | passing |
| TC-TTC-13-A12 | PATCH `/students/timetable/slots/bulk` (path without the doubled segment) | 404 or 405 | passing |
| TC-TTC-13-A13 | `GET /test` with no Authorization header | 404, 405 or 422 with a token; without one 401, 404, 405 or 422 (route removed) | passing |
| TC-TTC-13-A14 | Role matrix: `POST /bulk`, `GET /section/{id}`, `PATCH` as Staff, Teacher, Student, Parent | 403 each; Admin 2xx | passing |
| TC-TTC-13-A15 | No Authorization header on the three authenticated endpoints | 401 | passing |
| TC-TTC-13-A16 | Tenant isolation: tenant B `GET /section/{A's section}` and `PATCH` with A's slot id | 404 each | passing |

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TTC-13-E01 | P3 | Web | Admin | TC-TTC-07-E01 and TC-TTC-07-E12 done; browser developer tools open on the Network tab | 1. Sign in as Admin.<br>2. Open "Timetable", choose "Class 3" and "3-A".<br>3. Click "Edit", then "Save".<br>4. Repeat on mobile (Expo web) with "Timetable" > "Class 4" > "4-A" > "Edit" > "Save". | Only `/students/timetable/frontend` requests are sent; no request to `/bulk`, `/section/` or `/timetable/slots/bulk` | planned |

---

## Known gaps

Defects and doc/code mismatches found while writing this page (the code behaviour is what the test cases above assert). Track them in `docs/modules/timetable-calendar.md` when fixed or accepted.

1. **Web calendar permission names.** `Calendar.tsx` gates "+ Add Event", "Save", "Delete", "Edit Event" on `holidays:*` while the backend and seed use `holiday_management:*`. A default-seeded Admin has no `holidays` grants, so those controls are hidden (observed on `qa_school` 2026-10-07). Mobile uses `holiday_management` and `timetable_management` and is not affected.
2. **Day cells ignore permission.** Clicking a day opens the Add Event dialog for users without create permission, on web and on mobile; the submit then fails with 403. The web "Add" button inside that dialog is not gated either, so the default Admin can create holidays only through a day cell.
3. **No restore in the UI.** `PATCH /{id}/activate` exists and web and mobile have hooks for it, but no screen calls it, and default lists hide inactive holidays, so a deactivated holiday cannot be restored from either app.
4. **Month views show at most 10 holidays.** The web calendar and the mobile admin holidays screen request the list without a limit (default 10). The mobile read-only calendar uses 100.
5. **Student and Parent cannot use the read-only views.** The default seed gives them no `holiday_management` or `timetable_management` grants, so the mobile calendar and the student and parent timetable viewer receive 403. Neither screen (`/calendar`, `/timetable`) is linked from any tab, hub or drawer entry (the mobile "Calendar" tile and drawer entry map `/Calender` to the Dashboard), and the web self-service menu allowlist omits `/TimeTable` and `/Calender`. A comment in `mobile/app/(tabs)/students.tsx` still says no student or parent timetable view exists.
6. **Holiday validation gaps.** Fixed (2026-10-02): end before start is rejected (422 on create, 400 or 422 on update) and `color` must be `#rrggbb`. `is_active` still defaults to false on create.
7. **Holiday not-found handling.** Fixed (2026-10-02): `GET`, `PUT`, `DELETE` and `PATCH activate` return 404 for an unknown id.
8. **Timetable create versus replace.** `POST /frontend` drops Saturday and writes special rows for Monday to Friday only; `PUT` keeps any day and writes special rows for Monday to Sunday. A duplicate `POST` returns 409, an unknown section 404, an unknown subject 400 and a bad time string 422 (module doc rule 2); the A rows of F07 that still expect 500 for these (TC-TTC-07-A05, A06, A09, A26) predate that change.
9. **No timetable sanity checks.** No `from` before `to`, no overlap, no check that a subject is mapped to the section or class, and the PUT merge of rows with the same time range loses a special row that shares a range with a subject row.
10. **Row order.** Rows are returned grouped by `slot_time_id` (a random UUID), not in time order, so the mobile viewer's period numbers can be out of order unless clients sort.
11. **Mobile editor.** An untouched subject row has an empty `subjects` object and Repeat All can copy an empty cell as `""`; both fail the UUID validation (422). Mobile Repeat One acts on a single row while web acts on every row containing the subject.
12. **Free-text Saturday on web.** The Saturday cell accepts free text and event names, which the API rejects (422), and the first save of a new timetable drops Saturday anyway.
13. **Viewer scope.** With the read grant, a Student can read any section's timetable (no own-section restriction), and Student or Parent default grants make the viewer unusable.
14. **Legacy and dead code.** `POST /bulk` needs pre-existing slot times and is unused; the PATCH bulk path is doubled (`/timetable/timetable/slots/bulk`) while a web helper calls the single-segment path; `GET /students/timetable/test` was unauthenticated (removed 2026-10-02, Fixed); web `api/hooks/masters/timetable.ts` targets non-existent routes.
15. **Auto-generation is not implemented.** Level timing templates, class-teacher first period, staff workload limits, publish and draft states and copying from the previous year described in the local spec have no tables or endpoints (the slot model has no staff column).
