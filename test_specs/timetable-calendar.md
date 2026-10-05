# Timetable and calendar (TTC)

This module covers the school holiday and event calendar (holidays belong to an academic year and are managed on a month calendar and an "All Events" list) and the weekly class timetable (one grid per section: rows are time ranges, columns are days, with subject rows, special rows such as Snacks or Lunch, and an optional Saturday). It also covers the read-only views: the mobile school calendar for every role and the mobile student and parent timetable viewer. The page is the specification for the TTC test cases and is ordered the way an admin meets the work: holidays for the year first, then the timetable (view, build and save, editing tools, delete, export), then the read-only consumers and the legacy slot endpoints. Classes, sections, subjects and class-subject mappings that the timetable depends on are in `docs/features/masters.md` (code MST); the holiday message button on the list belongs to Communication (COM).

_Last verified against code: 2026-10-02_

Module rules, gotchas and code map: `docs/modules/timetable-calendar.md`. Flows and decisions: `docs/graph/views/timetable-calendar.md`. Test conventions and IDs: `docs/testing/strategy.md`.

Unit tests (U) implemented in: `backend/tests/unit/timetable_calendar/test_ttc_*.py`, `mobile/__tests__/timetable_calendar/` (TC-TTC-06-U11). Every web and the other mobile U row is blocked because the logic lives unexported inside component files. Tests whose names end `_defect_kgN` assert today's behaviour of a Known gaps item.

## Roles

Access is decided per resource (`docs/permissions.md`). The grants below are the default seed (`ROLE_PERMISSIONS` in `backend/app/service/tenant/permission_catalog.py`) that `qa_school` is provisioned with.

| Resource | Admin | Staff | Teacher | Student | Parent |
|---|---|---|---|---|---|
| `holiday_management` | create, read, update, delete, list | read, list | read, list | none | none |
| `timetable_management` | create, read, update, delete, list | none | none | none | none |

Consequences of the default seed (see Known gaps): Student and Parent cannot read holidays or timetables through the API, so the mobile calendar and the student and parent timetable viewer receive 403 for them; Staff and Teacher can read holidays but cannot read timetables. Menu: Admin, Staff and Teacher receive every menu; Student and Parent receive only the self-service allowlist, which contains neither `/TimeTable` nor `/Calender`.

Web permission names: the web calendar checks `holidays:*` (alias names) while the backend enforces `holiday_management:*`; the web timetable editor checks `timetable_management:update` (correct); the mobile screens check `holiday_management` and `timetable_management` (correct). The default Admin grant has no `holidays` rows, so the web calendar Add Event, Edit and Delete controls stay hidden unless the tenant also holds `holidays:create`, `holidays:update` and `holidays:delete` (the Teacher and Staff web caps already include `holidays: read, list`).

## Conventions used by the test cases

- API base `/api/v1`; phase 2 tests run on `qa_school` (`docs/testing/test-environment.md`). The QA baseline holds no master data: each test creates a year, a class with sections, subjects and (for timetables) uses their ids, with names prefixed `QA-<run id>`, and removes them. Phase 3 specs seed the same through API fixtures.
- Web E specs for holidays run with the `holidays:*` alias grants added to Admin by a fixture; one case records the default (controls hidden).
- A "403" case means status 403 with `detail` starting `Permission not found in database`. Validation (422) runs before the permission check, so role-matrix tests send valid bodies.
- Returned timetable rows are not in time order: tests sort `timetable_data` by `time.from` before comparing.
- Create endpoints are rate limited per client IP (holiday create 30 per minute); the timetable endpoints are not rate limited.
- Tenant isolation pattern: data created in tenant A is invisible to tenant B (404 or empty list), and a tenant A token with a `cschema` header naming B gets 403.
- Backend unit tests (`backend/tests/unit/timetable_calendar/`) use fake sessions; web unit tests use vitest and mobile unit tests use jest. Functions that live inside a component file and are not exported (called out per feature) must be extracted or exported first.

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
1. Open Masters > Holidays (or Calendar). Card "Holidays" with the buttons "Month" and "All Events" (Week, Day and Year views are disabled in code), "<" and ">" for the previous and next month, the month and year labels (click to pick a month or a year from -10 to +10), and "+ Add Event" (create permission only).
2. Month view: a Sunday-first grid. Single-day events show as coloured chips inside the day cell (name and a shortened description); multi-day events show as bars over the week. Today is highlighted. Clicking an event opens the Edit Event dialog (F03); clicking an empty day opens Add Event for that day (F02).
3. "All Events" view: filter "Search events..." (title and description of the current page), sortable headers Title, Start Date, End Date (click toggles ascending and descending), columns S.No., Title, Description (cut at 60 characters with "..."), Start Date, End Date, Color (swatch), Actions (message button "Send Holiday Message to all parents", "Edit Event", "Delete Event"). Paging: "Prev", "Page n", "Next" with 10 events per page; "Next" is disabled when a page returns fewer than 10. Empty text "No events" or "No events match your search".
4. The month view requests `academic_year_id` only, so it receives at most 10 events (default limit); the list view requests 10 per page.

**Steps, mobile.**
1. Masters tab > Holidays (admin screen). Header "Holidays" with a back arrow, tabs "Month" and "All Events", "Add Event", month arrows ("Previous month", "Next month") and "Select month and year" (picker with Year, Month, Day columns, buttons "Cancel" and "Select").
2. All Events: "Search events...", sort chips "Title", "Start", "End" (accessibility labels "Sort by Title" and so on), cards with the title, date range (`start to end` or one date), description, message button, "Edit Event" and "Delete Event" buttons, and "Prev", "Page n", "Next" (10 per page). Failure text "Failed to load events".
3. Month view behaves like web without drag and drop; the request has no limit, so at most 10 events appear.
4. Student and Parent have no Masters tab. The read-only view for all roles is F12.

**Expected results.** Only active holidays of the working year appear; each shows its name, dates and colour; list paging, search and sort act on the loaded page only.

**API endpoints.** Prefix `/api/v1/masters/holidays`.
- `GET /` query `skip=0`, `limit=10`, `active_only=true`, `academic_year_id?` -> `{items, total_count, has_next}` (no ordering guarantee).

**Rules and validations.**
1. Defaults are `limit=10` and `active_only=true`; any client that needs more must pass an explicit `limit`. There is no upper bound on `limit`; negative `skip` or `limit` returns 400 `Invalid query parameters.`
2. `has_next` is `(skip + limit) < total_count`.
3. A holiday created with `is_active=false` (the schema default) is hidden from default lists.
4. Search and sort are client-side over the loaded page.
5. Holidays are display-only: attendance, timetable and fee logic do not read them.
6. Day cells open the Add Event dialog even for users without create permission; the API then answers 403 and the toast "Failed to create holiday" appears.

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
| TC-TTC-01-A01 | Admin `GET /masters/holidays/` default with 12 active holidays in the year | `items` length 10, `total_count` 12, `has_next` true | planned |
| TC-TTC-01-A02 | `GET /?skip=10&limit=10` | 2 items, `has_next` false | planned |
| TC-TTC-01-A03 | `GET /?limit=100&academic_year_id=Y` | All 12 items of year Y only; none from another year | planned |
| TC-TTC-01-A04 | `GET /` with one inactive holiday; then `?active_only=false` | Inactive hidden by default; present with `active_only=false` | planned |
| TC-TTC-01-A05 | `GET /?skip=-1`; `GET /?limit=-1` | 400 `Invalid query parameters.` | planned |
| TC-TTC-01-A06 | Item shape | Each item has `id, name, description, start_date, end_date, is_active, academic_year_id, color` with dates as `YYYY-MM-DD` | planned |
| TC-TTC-01-A07 | Read matrix: `GET /` as Admin, Staff, Teacher | 200 | planned |
| TC-TTC-01-A08 | `GET /` as Student and Parent | 403 each | planned |
| TC-TTC-01-A09 | No Authorization header | 401 | planned |
| TC-TTC-01-A10 | Tenant isolation: tenant B `GET /` and `GET /?academic_year_id=<A's year>` | Empty `items`; A token with B `cschema` header gets 403 | planned |
| TC-TTC-01-E01 | [web] Admin opens Masters > Holidays with 3 holidays in the current month | Card "Holidays", Month active, chips and a multi-day bar visible | planned |
| TC-TTC-01-E02 | [web] Click ">" then "<" | Month label changes and returns; events follow the month | planned |
| TC-TTC-01-E03 | [web] Click "All Events" | Table with S.No., Title, Description, Start Date, End Date, Color, Actions | planned |
| TC-TTC-01-E04 | [web] Type a title in "Search events..." | Only matching rows; message "No events match your search" when none | planned |
| TC-TTC-01-E05 | [web] Click Title then Start Date headers twice | Ascending then descending order each time | planned |
| TC-TTC-01-E06 | [web] 12 holidays seeded; All Events | 10 rows; "Next" enabled; page 2 shows 2 rows and "Next" disabled | planned |
| TC-TTC-01-E07 | [web] Month view with 12 holidays in one month | Only 10 are drawn (default limit; records the limitation) | planned |
| TC-TTC-01-E08 | [web] Open the same page through the Calendar entry (`/Calender`) | Identical content | planned |
| TC-TTC-01-E09 | [web] Teacher opens Masters > Holidays | Month and list visible; no "+ Add Event", no Edit or Delete icons | planned |
| TC-TTC-01-E10 | [web] Teacher clicks an empty day | Add Event dialog opens (no permission check) | planned |
| TC-TTC-01-E11 | [web] Student and Parent | No Masters and no Calendar entry in the sidebar | planned |
| TC-TTC-01-E12 | [mobile] Admin opens Masters > Holidays | Header "Holidays", tabs Month and All Events, month label with arrows | planned |
| TC-TTC-01-E13 | [mobile] All Events: search, sort chip "Title", Next page | Filter, order and paging as web | planned |
| TC-TTC-01-E14 | [mobile] "Select month and year" > choose month and year > Select | Calendar jumps to that month | planned |
| TC-TTC-01-E15 | [mobile] Teacher opens the screen | Events visible; no "Add Event"; no Edit or Delete buttons | planned |

---

## F02 Create a holiday or event

**Purpose.** An admin adds a holiday or event with a title, a date range, a colour and a description.

**Roles and permissions.** API: `holiday_management:create` (Admin only). Web button: `holidays:create`. Mobile button: `holiday_management:create`.

**Preconditions.** An academic year is selected (F01; without it the web Add button does nothing).

**Steps, web.**
1. Click "+ Add Event" (dates default to today) or click a day cell (that day is prefilled).
2. Dialog "Add Event" ("Fill in the details to add a new holiday event to the calendar."): Title* (placeholder "Event title"), Date Range* (two date pickers separated by "to"), Event Color (colour input, default `#2563eb`), Description (placeholder "Event description").
3. Click "Add" ("Adding..."). Toast "Holiday created!". Missing required fields show "Please fill in all required fields." and the submit does nothing. Failure toast "Failed to create holiday".
4. The request sends `is_active:true`, the working year id and the colour.

**Steps, mobile.**
1. "Add Event" or tap a day. Modal "Add Event": "Title *" ("Event title"), "Date Range *" (start and end pickers "Select start date" and "Select end date"), "Event Color", "Description" ("Event description"), buttons "Add" and "Cancel".
2. Toasts "Holiday Created - Holiday created successfully." and "Create Failed" with the server reason. Submit is ignored while title or dates are empty.

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
| TC-TTC-02-A01 | Admin `POST /masters/holidays/` `{name:"QA-Diwali", description:"Festival", start_date:"2026-11-08", end_date:"2026-11-10", is_active:true, academic_year_id, color:"#ff8800"}` | 200 `HolidayRead` with the same values and an `id` | planned |
| TC-TTC-02-A02 | POST omitting `is_active` | 200 with `is_active:false`; absent from `GET /` default, present with `?active_only=false` | planned |
| TC-TTC-02-A03 | POST single-day holiday (`start_date` equals `end_date`) | 200 | planned |
| TC-TTC-02-A04 | POST with `end_date` before `start_date` | 422 | planned |
| TC-TTC-02-A05 | POST name of 50 and 51 characters | 50: 200. 51: 400 detail starts `Error creating holiday` | planned |
| TC-TTC-02-A06 | POST description of 100 and 101 characters | 100: 200. 101: 400 | planned |
| TC-TTC-02-A07 | POST colour `#ff8800` (7), `#ff880011` (9), `red` (3) | 200; 422; 422 | planned |
| TC-TTC-02-A08 | POST missing `name`; missing `academic_year_id`; invalid date | 422 each | planned |
| TC-TTC-02-A09 | POST with a random `academic_year_id` | 400 `Error creating holiday: ...` (foreign key) | planned |
| TC-TTC-02-A10 | Write matrix: POST as Staff, Teacher, Student, Parent | 403 each; Admin 200 | planned |
| TC-TTC-02-A11 | No Authorization header | 401 | planned |
| TC-TTC-02-A12 | Create then `GET /dropdown` immediately | New holiday in the dropdown (create invalidates the cache) | planned |
| TC-TTC-02-A13 | 31 POSTs within a minute (limiter enabled) | The 31st returns 429 | planned |
| TC-TTC-02-A14 | Tenant isolation: holiday created in tenant A | Not visible to tenant B; B can create the same name | planned |
| TC-TTC-02-E01 | [web] "+ Add Event": title `QA Sports Day`, today to tomorrow, colour red, description, Add | Toast "Holiday created!"; dialog closes; a red bar or chip appears; also listed under All Events | planned |
| TC-TTC-02-E02 | [web] Click an empty day cell | Add Event opens with that date in both date pickers | planned |
| TC-TTC-02-E03 | [web] Add with an empty title | Message "Please fill in all required fields."; nothing sent | planned |
| TC-TTC-02-E04 | [web] Close the dialog after typing | "Discard changes?" guard appears | planned |
| TC-TTC-02-E05 | [web] Teacher adds an event after clicking a day | Toast "Failed to create holiday" (API 403) | planned |
| TC-TTC-02-E06 | [web] Default Admin without `holidays:create` alias | "+ Add Event" not shown (records the permission-name mismatch) | planned |
| TC-TTC-02-E07 | [mobile] Add Event with title `QA Picnic`, pick dates, colour, Add | Toast "Holiday Created"; event on the calendar | planned |
| TC-TTC-02-E08 | [mobile] Add with empty title | Nothing sent; modal stays | planned |
| TC-TTC-02-E09 | [mobile] Teacher | No "Add Event" button | planned |

---

## F03 Edit and reschedule a holiday

**Purpose.** An admin changes a holiday's title, dates, colour or description, or moves it to another day by dragging it on the web calendar.

**Roles and permissions.** API: `holiday_management:update`. Web: `holidays:update` for "Save" and "Edit Event"; drag and drop sends the update without a client permission check. Mobile: `holiday_management:update`.

**Preconditions.** A holiday exists (F02).

**Steps, web.**
1. Click an event chip or bar, or "Edit Event" in All Events. Dialog "Edit Event" ("Edit the details of this holiday event."): Title*, Date Range*, Event Color, Description.
2. Click "Save" ("Saving..."). Toast "Holiday updated!"; failure "Failed to update holiday". Missing required fields: "Please fill in all required fields." and no request.
3. Drag: drag a chip or bar onto another day cell in the month view. The event moves so that it starts on the dropped day and keeps its length; toast "Holiday updated!".

**Steps, mobile.**
1. Tap an event or "Edit Event". Modal "Edit Event" with the same fields; buttons "Save", "Delete", "Cancel". Toasts "Holiday Updated" and "Update Failed". There is no drag and drop on mobile.

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
| TC-TTC-03-A01 | Admin `PUT /{id}` `{name:"QA-Diwali-2"}` | 200; name changed; dates, colour, `is_active` unchanged | planned |
| TC-TTC-03-A02 | `PUT /{id}` `{start_date:"2026-11-12", end_date:"2026-11-14"}` | 200; new dates returned as `YYYY-MM-DD` | planned |
| TC-TTC-03-A03 | `PUT /{id}` `{color:"#00aa00", description:"New"}` | 200 with the new values | planned |
| TC-TTC-03-A04 | `PUT /{id}` with `end_date` before `start_date` | 422 (both sent) or 400 (against the stored date) | planned |
| TC-TTC-03-A05 | `PUT /{id}` with a 51-character name | 400 `Error updating holiday: ...` | planned |
| TC-TTC-03-A06 | `PUT /{id}` `{academic_year_id:<other>}` | 200 but the year is unchanged (field not accepted) | planned |
| TC-TTC-03-A07 | `PUT /{random uuid}` | 404 detail `Holiday not found` | planned |
| TC-TTC-03-A08 | Write matrix: PUT as Staff, Teacher, Student, Parent | 403 each; Admin 200 | planned |
| TC-TTC-03-A09 | No Authorization header | 401 | planned |
| TC-TTC-03-A10 | Update then `GET /dropdown` | Dropdown shows the new name (update invalidates) | planned |
| TC-TTC-03-A11 | Tenant isolation: tenant B `PUT` on tenant A's holiday id | 404; row unchanged | planned |
| TC-TTC-03-E01 | [web] Click an event, change title and colour, Save | Toast "Holiday updated!"; chip shows the new title and colour | planned |
| TC-TTC-03-E02 | [web] Edit the end date | Bar length changes | planned |
| TC-TTC-03-E03 | [web] Clear the title | "Please fill in all required fields."; Save sends nothing | planned |
| TC-TTC-03-E04 | [web] Drag a single-day chip to another day | Toast "Holiday updated!"; chip moves to the target day; list shows the new dates | planned |
| TC-TTC-03-E05 | [web] Drag a 3-day bar to a day in another week | New range keeps 3 days | planned |
| TC-TTC-03-E06 | [web] Teacher opens an event | Dialog fields visible; no "Save" or "Delete" buttons; Cancel only | planned |
| TC-TTC-03-E07 | [mobile] Tap an event, change description, Save | Toast "Holiday Updated"; card shows the new text | planned |
| TC-TTC-03-E08 | [mobile] Edit with the title cleared | Save does nothing | planned |

---

## F04 Delete (deactivate) and restore a holiday

**Purpose.** An admin removes a holiday from the calendar without losing it, and can restore it through the API.

**Roles and permissions.** Delete: `holiday_management:delete`. Restore (`PATCH .../activate`): `holiday_management:update`. Web buttons: `holidays:delete`. Mobile: `holiday_management:delete`. There is no restore button on web or mobile.

**Preconditions.** A holiday exists.

**Steps, web.**
1. In the Edit Event dialog click "Delete" ("Deleting..."), or in All Events click the trash icon ("Delete Event", no confirmation). Toast "Holiday deleted!". The holiday disappears from the calendar and list (it is deactivated).
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
| TC-TTC-04-A01 | Admin `DELETE /{id}` | 200 body has `is_active:false`; `GET /` default no longer lists it; `GET /?active_only=false` does | planned |
| TC-TTC-04-A02 | `DELETE /{id}` twice | 200 both times | planned |
| TC-TTC-04-A03 | `DELETE /{random uuid}` | 404 | planned |
| TC-TTC-04-A04 | `PATCH /{id}/activate` on a deactivated holiday | 200 `is_active:true`; listed again by default | planned |
| TC-TTC-04-A05 | `PATCH /{random uuid}/activate` | 404 | planned |
| TC-TTC-04-A06 | Deactivate then `GET /dropdown`; activate then `GET /dropdown` | Absent; present again (cache invalidated both times) | planned |
| TC-TTC-04-A07 | Write matrix: DELETE and PATCH activate as Staff, Teacher, Student, Parent | 403 each; Admin 200 | planned |
| TC-TTC-04-A08 | No Authorization header on both | 401 | planned |
| TC-TTC-04-A09 | Tenant isolation: tenant B `DELETE` and `PATCH` on tenant A's holiday | 400; row unchanged | planned |
| TC-TTC-04-E01 | [web] Open an event, click "Delete" | Toast "Holiday deleted!"; event gone from month and list | planned |
| TC-TTC-04-E02 | [web] All Events: trash icon | Toast "Holiday deleted!" with no confirmation dialog | planned |
| TC-TTC-04-E03 | [web] Teacher | No trash icon or "Delete" button | planned |
| TC-TTC-04-E04 | [mobile] Edit Event > Delete > confirm "Delete" | Toast "Holiday Deleted"; event gone | planned |
| TC-TTC-04-E05 | [mobile] Delete > cancel in the confirm | Event kept | planned |
| TC-TTC-04-E06 | [mobile] All Events trash button | Confirm "Delete Event" then toast "Holiday Deleted" | planned |

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
| TC-TTC-05-A01 | `GET /dropdown` with two active and one inactive holiday | Two items `{id,name}` ordered by name | planned |
| TC-TTC-05-A02 | `GET /dropdown?active_only=false` | Three items | planned |
| TC-TTC-05-A03 | `GET /{id}` valid | 200 `HolidayRead` | planned |
| TC-TTC-05-A04 | `GET /{random uuid}` | 404 detail `Holiday not found` | planned |
| TC-TTC-05-A05 | `GET /not-a-uuid` | 422 | planned |
| TC-TTC-05-A06 | Read matrix: both endpoints as Admin, Staff, Teacher | 200 | planned |
| TC-TTC-05-A07 | Both endpoints as Student and Parent | 403 each | planned |
| TC-TTC-05-A08 | No Authorization header | 401 | planned |
| TC-TTC-05-A09 | Tenant isolation: tenant B `GET /dropdown`; `GET /{A's id}` | Empty list; 404 | planned |
| TC-TTC-05-A10 | Rename a holiday and call `GET /dropdown` | New name immediately (update invalidates) | planned |

---

## F06 Timetable: select a section and view it

**Purpose.** An admin picks a class and a section and sees that section's weekly timetable: time ranges as rows, days as columns, subjects and special rows in the cells.

**Roles and permissions.** Read: `timetable_management:read` (`GET /students/timetable/frontend/{section_id}`). Only Admin holds it in the default seed; Staff, Teacher, Student and Parent receive 403. The class and section pickers use `classes:list` (MST F06). Edit controls need `timetable_management:update`. Menu: web top-level "Timetable" (`/TimeTable`); mobile: the drawer entry "Timetable" (the menu path `/TimeTable` maps to `/masters/timetable`) and, only when the backend Masters menu lists it or the cold-start fallback list is used, the Masters hub card "Timetable Management".

**Preconditions.** Class, sections and subjects exist (MST F03, F08). For a non-empty view a timetable was saved (F07).

**Steps, web.**
1. Open "Timetable". Header "Time Table Management". Pickers "Select Class" (active classes) and "Select Section" (disabled until a class is chosen; lists the class's active sections).
2. Before both are chosen: "Please select a class and section to view or create a timetable" with the hint "Start by selecting a class" or "Now select a section".
3. After choosing a section: "Loading timetable data..." then the grid. Columns: "Time" (for example "9:00 AM - 9:45 AM"), "Monday" to "Friday", and "Saturday" when any saved subject row has a Saturday value. A day with no entry shows "--"; an all-empty Saturday column shows "(Holiday)" in its header and "Holiday" in cells. Special rows span all day columns with their label (Snacks, Lunch, Dispersal or the custom name).
4. If no timetable exists (404) the grid is empty and, for a user who can update, the page opens in edit mode (F07). If the request fails otherwise the page shows "Error loading timetable: <reason>".
5. The page does not remember the selection, and saved rows come back in no particular time order.

**Steps, mobile.**
1. Open the drawer entry "Timetable" (or the Masters hub card "Timetable Management" where present). Screen "Timetable" with "Select Class" (one card per class from the class list) then "Select Section" (header shows the class name), then the grid screen titled "<class> - <section>" with the subtitle "Timetable".
2. View mode shows day tabs (Mon to Sat, accessibility labels Monday to Saturday) and one card per row for the selected day: the 12-hour time range and either the subject name, "Free period" for an empty cell, or the special label. Pull down to refresh. Empty: "No timetable data".
3. Without a saved timetable the screen opens in edit mode with one default subject row at 9:00 AM to 9:45 AM (F07). Without any read permission on the class step the screen shows "Access Denied - You don't have permission to view timetables".

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
- A non-Admin role: 403; the web retries then shows "Error loading timetable: Permission denied: timetables:read".
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
| TC-TTC-06-A01 | Admin `GET /frontend/{section}` after F07 saved 2 subject rows and a LUNCH row | 200 with `section_name`, `class_name`; 3 items (after sorting by `time.from`) with times as `HH:MM` | planned |
| TC-TTC-06-A02 | `GET /frontend/{section}` for a section without a timetable | 404 `Timetable not found for section` | planned |
| TC-TTC-06-A03 | `GET /frontend/{random uuid}`; `GET /frontend/not-a-uuid` | 404; 422 | planned |
| TC-TTC-06-A04 | A timetable created with an empty `timetable_data` | 200 with `timetable_data:[]` | planned |
| TC-TTC-06-A05 | Special row saved through PUT | Returned as `type:"special"`, `label` as saved, no `subjects` key | planned |
| TC-TTC-06-A06 | Two rows with the same time range saved through PUT | Single merged row returned (same slot time) | planned |
| TC-TTC-06-A07 | Read matrix: Admin 200 | 200 for Admin | planned |
| TC-TTC-06-A08 | `GET /frontend/{section}` as Staff, Teacher, Student, Parent | 403 `Permission not found in database` each (default seed) | planned |
| TC-TTC-06-A09 | No Authorization header | 401 | planned |
| TC-TTC-06-A10 | Tenant isolation: tenant B `GET` for tenant A's section id | 404 | planned |
| TC-TTC-06-E01 | [web] Admin opens Timetable with nothing selected | Message "Please select a class and section to view or create a timetable" and "Start by selecting a class" | planned |
| TC-TTC-06-E02 | [web] Choose the class | Hint becomes "Now select a section"; "Select Section" enabled | planned |
| TC-TTC-06-E03 | [web] Choose class and a section with a saved timetable | Grid with "Time" and Monday to Friday; times in 12-hour format; special row spans all days | planned |
| TC-TTC-06-E04 | [web] Section with a saved Saturday value | "Saturday" column visible with the subject; empty Saturday cells say "Holiday" | planned |
| TC-TTC-06-E05 | [web] Section with no timetable | Empty grid in edit mode ("Save" button, "+ Add Subject Row", "+ Add Special Row") | planned |
| TC-TTC-06-E06 | [web] Teacher chooses a class and section | After retries the page shows "Error loading timetable: Permission denied: timetables:read"; no Edit button | planned |
| TC-TTC-06-E07 | [web] Change the class after viewing a section | Section clears and the grid is replaced by the select-section hint | planned |
| TC-TTC-06-E08 | [web] Student and Parent | No Timetable entry in the sidebar | planned |
| TC-TTC-06-E09 | [mobile] Admin: drawer "Timetable" > class card > section card | Screen "<class> - <section>" with day tabs and period cards | planned |
| TC-TTC-06-E10 | [mobile] Switch day tabs including Saturday (when saved) | Cards change per day; empty cells "Free period"; special rows show the label | planned |
| TC-TTC-06-E11 | [mobile] Section without a timetable | Opens in edit mode with one row 9:00 AM to 9:45 AM | planned |
| TC-TTC-06-E12 | [mobile] Teacher opens the screen | "Access Denied - You don't have permission to view timetables" | planned |

---

## F07 Timetable: build and save (create and replace)

**Purpose.** An admin builds a section's timetable (rows of times with a subject per day, plus special rows) and saves it. The first save creates it; later saves replace it wholesale.

**Roles and permissions.** Create (`POST /frontend`): `timetable_management:create`. Replace (`PUT /frontend/{section_id}`): `timetable_management:update`. Admin only. Web: the Edit and Save buttons and row controls need `timetable_management:update`; mobile: the Edit and Save button needs `timetable_management` update while editing.

**Preconditions.** A class and section exist; subjects exist and normally are mapped to the class (MST F10); the section view (F06) is open.

**Steps, web.**
1. Choose class and section. With no saved timetable the grid is empty and in edit mode; with a saved timetable click "Edit".
2. Click "+ Add Subject Row": a row with From and To time pickers (24-hour `HH:MM`, shown side by side) and a "Select..." dropdown per day (Monday to Friday, and Saturday when "Include Saturday" is ticked). Click "+ Add Special Row": a row with one dropdown "Select or create event..." (default Snacks) spanning all days. The trash button ("Delete row") removes a row.
3. Click "Save". The button shows "Saving...". On success: toast "Timetable saved successfully", the grid returns to view mode and reloads. Failure toasts: the server message, "Permission denied: timetables:create" or "Permission denied: timetables:update", "Invalid data provided", or "Failed to save timetable".
4. Rows without both times and subject rows with no subject chosen are dropped before sending; empty day values are not sent.
5. If a timetable already exists the save is a replace (PUT), otherwise a create (POST).

**Steps, mobile.**
1. Select class and section (F06). In edit mode each row is a card with "9:00 AM" to "9:45 AM" time boxes (time picker modal), a day dropdown "Select Subject" per day, a trash button, and a "Select Special Activity" dropdown on special rows.
2. Buttons "Add Subject" and "Add Special" add rows (default 9:00 AM to 9:45 AM; special default Snacks). "Save" in the header or "Save Timetable" at the bottom saves ("Saving..."). Toasts "Timetable Created - Timetable created successfully.", "Timetable Updated - Timetable updated successfully.", "Create Failed" and "Update Failed" with the reason.
3. Mobile sends every row as is: an untouched subject row has an empty `subjects` object and a cleared dropdown sends an empty string, both rejected with 422.

**Expected results.** Rows and cells are stored under the section; reloading shows the same data (order may differ); a replace discards everything not sent.

**API endpoints.** Prefix `/api/v1/students/timetable`.
- `POST /frontend` `{section_id, timetable_data:[{time:{from,to}, type:"subject"|"special", subjects?:{Day:uuid}, label?}]}` -> 200 `{message:"Timetable created successfully", timetable_id, created_slots, created_slot_times}`.
- `PUT /frontend/{section_id}` same body -> 200 `{message:"Timetable updated successfully", ...}`.

**Rules and validations.**
1. Row validation (422): `type` must be `subject` or `special`; a subject row needs a non-empty `subjects` object of day name to UUID and no `label`; a special row needs a `label` and no `subjects`; `time.from` and `time.to` are required strings.
2. Times are parsed as `HH:MM` (`strptime("%H:%M")`). Any other format or an impossible time (`9am`, `25:00`, `09:00:00`) fails with 500 `Error creating timetable from frontend data: ...` (or `Error updating timetable: ...`). `9:00` is accepted.
3. `POST` creates the timetable row; a second `POST` for the same section violates the unique section constraint and returns 500. An unknown `section_id` or unknown subject id returns 500 (foreign key).
4. `POST` keeps only Monday to Friday: Saturday (and any other day) subject values are silently dropped, and special rows are written for Monday to Friday. A subject row whose days are all dropped still creates its time range but no slots, so it does not come back.
5. `PUT` replaces the whole timetable: all slots, options and every slot time of the section are deleted and recreated. Any day key is kept, and special rows are written for Monday to Sunday. Rows with the same `from-to` share one slot time and therefore merge into a single row on read (a special row and a subject row at the same time read back as a subject row). `PUT` returns 404 `Timetable not found for section` when none exists and uses the path `section_id` (the body value is ignored).
6. `created_slots` counts subject slots (day and subject) and break slots (5 per special row on create, 7 on replace); `created_slot_times` counts time ranges (on create one per row; on replace one per distinct range).
7. The API does not check `from` before `to`, overlaps, that a subject is mapped to the class, or that the subject belongs to the year.
8. Subject values must be UUIDs. The web Saturday cell also accepts free text or an event name; saving those fails with 422.
9. Slot ids change on every replace (nothing else references them).

**Error and edge cases.**
- Web guards the save with the permission; a Teacher never reaches it. Without `timetable_management:create` the first save returns 403 and the toast reads "Permission denied: timetables:create".
- After the first save of a table that included Saturday, Saturday is gone (POST drops it); a second save (PUT) keeps whatever Saturday value is entered.
- Duplicate `POST` from a stale screen returns 500.

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
| TC-TTC-07-A01 | Admin `POST /frontend` with rows 09:00-09:45 and 09:45-10:30 (Monday to Friday, three subjects) and a LUNCH row 12:00-12:45 | 200 `message "Timetable created successfully"`, `created_slots` 15, `created_slot_times` 3, `timetable_id` set | planned |
| TC-TTC-07-A02 | `GET /frontend/{section}` after A01 | 3 rows; the subject rows list Monday to Friday; the LUNCH row is `special` | planned |
| TC-TTC-07-A03 | POST a subject row that includes `Saturday` | 200; the returned timetable has no Saturday key; `created_slots` excludes it | planned |
| TC-TTC-07-A04 | POST a subject row with only `Saturday` | 200 with `created_slot_times` counting it; the row is absent from `GET` | planned |
| TC-TTC-07-A05 | POST a second time for the same section | 500 detail starts `Error creating timetable from frontend data` | planned |
| TC-TTC-07-A06 | POST with a random `section_id`; with a random subject uuid | 500 each (foreign key) | planned |
| TC-TTC-07-A07 | POST bodies: `type:"break"`; subject without `subjects`; subject with `label`; special without `label`; special with `subjects` | 422 each | planned |
| TC-TTC-07-A08 | POST subject value `"Holiday"` for Saturday | 422 | planned |
| TC-TTC-07-A09 | POST time `"9am"`, `"25:00"`, `"09:00:00"`; time `"9:00"` | 500 for the first three; 200 for `9:00` (stored as 09:00) | planned |
| TC-TTC-07-A10 | POST `from` later than `to` and two overlapping rows | 200 (no check; Known gaps) | planned |
| TC-TTC-07-A11 | POST with `timetable_data:[]` | 200 `created_slots` 0, `created_slot_times` 0 | planned |
| TC-TTC-07-A12 | POST subject not mapped to the class | 200 (mapping not checked) | planned |
| TC-TTC-07-A13 | POST missing `section_id`; missing `time.to` | 422 each | planned |
| TC-TTC-07-A14 | `PUT /frontend/{section}` replacing with a single row 08:00-08:45 | 200 `message "Timetable updated successfully"`; `GET` returns only that row | planned |
| TC-TTC-07-A15 | PUT with a Saturday subject | 200; `GET` returns the Saturday key | planned |
| TC-TTC-07-A16 | PUT with a special row | `created_slots` 7; `GET` returns `special` | planned |
| TC-TTC-07-A17 | PUT with a non-day key `Funday` | 200; key returned by `GET` (no day validation) | planned |
| TC-TTC-07-A18 | PUT with two rows at the same time range | `created_slot_times` 1; `GET` returns one merged row | planned |
| TC-TTC-07-A19 | PUT a special row and a subject row at the same range | `GET` returns a subject row (special label lost) | planned |
| TC-TTC-07-A20 | PUT for a section without a timetable | 404 `Timetable not found for section` | planned |
| TC-TTC-07-A21 | PUT with a body `section_id` of another section | 200; data stored under the path section; the other section unchanged | planned |
| TC-TTC-07-A22 | Slot ids before and after a PUT (via `GET /section/{section}`) | All slot ids differ after the replace | planned |
| TC-TTC-07-A23 | Round trip: PUT three rows then `GET` | Same set of times and subjects after sorting by `time.from` | planned |
| TC-TTC-07-A24 | Write matrix: POST and PUT with valid bodies as Staff, Teacher, Student, Parent | 403 each; Admin 200 | planned |
| TC-TTC-07-A25 | No Authorization header on POST and PUT | 401 | planned |
| TC-TTC-07-A26 | Tenant isolation: tenant B `POST` for tenant A's section; `PUT` for it | 500 (section not visible); 404 | planned |
| TC-TTC-07-E01 | [web] Admin selects class and section without a timetable; "+ Add Subject Row"; From 09:00, To 09:45; Monday to Friday Mathematics; Save | Toast "Timetable saved successfully"; view mode shows `9:00 AM - 9:45 AM` with Mathematics on five days | planned |
| TC-TTC-07-E02 | [web] "+ Add Special Row", choose Lunch, set 12:00 to 12:45, Save | Row spans all days with "Lunch" after reload | planned |
| TC-TTC-07-E03 | [web] Click "Edit" on a saved timetable, change one cell, Save | Toast "Timetable saved successfully"; change persists (PUT) | planned |
| TC-TTC-07-E04 | [web] Delete a row with the trash button and Save | The row is gone after reload | planned |
| TC-TTC-07-E05 | [web] Add a subject row and leave all subjects empty, Save | The empty row is dropped; the rest saves | planned |
| TC-TTC-07-E06 | [web] Add a row with only the From time set | The row is dropped on save | planned |
| TC-TTC-07-E07 | [web] Tick "Include Saturday", set a Saturday subject, Save on a new timetable, reload | Saturday value is missing (first save is a create) | planned |
| TC-TTC-07-E08 | [web] Repeat E07 on the existing timetable (Edit, set Saturday, Save) | Saturday value persists (replace) | planned |
| TC-TTC-07-E09 | [web] Type free text "Sports" in the Saturday cell, Save | Toast "Invalid data provided"; stays in edit mode | planned |
| TC-TTC-07-E10 | [web] Save while editing a section another admin has just created a timetable for | Toast shows a server message (create 500); reload shows the existing timetable | planned |
| TC-TTC-07-E11 | [web] Teacher and Staff | No Edit or Save button; the grid does not load (403) | planned |
| TC-TTC-07-E12 | [mobile] Add Subject, set 9:00 AM to 9:45 AM through the time picker, pick Mathematics for each day, Save Timetable | Toast "Timetable Created - Timetable created successfully."; view mode shows the periods | planned |
| TC-TTC-07-E13 | [mobile] Save a new timetable with the untouched default row | Toast "Create Failed" (empty `subjects`, 422; documents the defect) | planned |
| TC-TTC-07-E14 | [mobile] Edit an existing timetable, change a cell, Save | Toast "Timetable Updated - Timetable updated successfully." | planned |
| TC-TTC-07-E15 | [mobile] Add Special, choose Lunch, Save | Special row saved; shows "LUNCH" label in view mode | planned |
| TC-TTC-07-E16 | [mobile] Delete a row with the trash button, Save | Row removed after reload | planned |

---

## F08 Timetable editing tools: Saturday, special rows, custom events, repeat

**Purpose.** The editor offers shortcuts so an admin fills a week quickly: an optional Saturday column, special rows with reusable event names, a subject picker limited to the class's subjects, and two repeat tools.

**Roles and permissions.** Same as F07 (`timetable_management:update` to edit). The subject picker data needs `class_subject_mappings:read` (`by-class`) and `subjects:list`, which Admin holds.

**Preconditions.** The editor is in edit mode (F07).

**Steps, web.**
1. Saturday: tick "Include Saturday" (visible in edit mode). Each subject row gains a Saturday cell, a creatable dropdown "Subject / Event / Holiday..." with groups "Subjects" and "Events" and the option `Use "<text>"` for free text. Unticking removes the Saturday values.
2. Special rows: in a special row choose Snacks, Lunch or Dispersal, or type a new name and choose `Create "<name>"`. A new name is valid with 1 to 50 letters, digits or spaces (toast "Created custom event: <Name>"; otherwise "Event name must be 1-50 alphanumeric characters", or "This event already exists"). It is stored upper-cased with underscores (`MORNING_PRAYER`) and exists only for this editing session and the sections where it was saved.
3. Subject picker: each day's dropdown lists only subjects mapped to the selected class: mappings with no section or the selected section. If the class has no mappings the dropdown lists all subjects.
4. "Repeat All for Week" (enabled when some day has a subject): dialog "Repeat All Subjects for Week", "Copy from day" (days that hold data), button "Apply to All Days". Toast "<Day>'s schedule applied to all days". Every subject row's other days get the source day's subject (an empty source empties the others).
5. "Repeat One Subject" (enabled when rows contain a subject): dialog "Repeat One Subject for Week", "Subject" (subjects present in the rows), "Apply to All Days". For every subject row that already holds that subject on any day, all active days are set to it. Toast "<Subject> applied to all days".

**Steps, mobile.**
1. "Include Saturday" checkbox in edit mode adds Saturday to the day tabs and cells.
2. Special rows use "Select Special Activity" with the defaults Snacks, Lunch, Dispersal and a create-your-own option; a new name is accepted with 1 to 50 letters, digits or spaces, stored upper-cased with underscores, label shown with only the first letter capitalised.
3. The subject picker is limited to the class's mapped subjects in the same way (the dropdown shows "Select Subject" first).
4. "Repeat All for Week" opens a modal listing the active days: choose the source day to copy its subject to every other day in every subject row. "Repeat One Subject" first asks "Select Period to Repeat" (a row), then "Select Source Day"; the row's other days take that day's subject. Both modals have "Cancel".

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
- A section with no class mappings shows every subject.

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
| TC-TTC-08-A01 | PUT a special row labelled `MORNING_PRAYER`, then `GET` | Row returned with `label:"MORNING_PRAYER"` | planned |
| TC-TTC-08-A02 | POST a table that has a Saturday value, then PUT the same table | POST drops Saturday; PUT keeps it (compare the two `GET` results) | planned |
| TC-TTC-08-A03 | PUT a Saturday cell with free text `Sports` | 422 | planned |
| TC-TTC-08-A04 | PUT subject rows using a subject not mapped to the class | 200 (not checked) | planned |
| TC-TTC-08-A05 | `GET /masters/class-subject-mappings/by-class/{class}` as Admin after bulk mapping with `section_id` null and one section-specific mapping | Rows for the class (class-level and section-level) used to build the picker; subject ids repeat per section | planned |
| TC-TTC-08-E01 | [web] Edit mode: tick "Include Saturday" | Saturday column and a creatable cell "Subject / Event / Holiday..." appear | planned |
| TC-TTC-08-E02 | [web] Saturday cell: choose Lunch under "Events" and Save | Toast "Invalid data provided" (the non-UUID value is rejected); stays in edit mode. Replacing it with a subject and saving succeeds on an existing timetable | planned |
| TC-TTC-08-E03 | [web] Untick "Include Saturday" | Saturday column and values disappear | planned |
| TC-TTC-08-E04 | [web] Special row: type `Assembly` and choose `Create "Assembly"` | Toast "Created custom event: Assembly"; row label becomes Assembly | planned |
| TC-TTC-08-E05 | [web] Create an event named `Assembly!` | Toast "Event name must be 1-50 alphanumeric characters" | planned |
| TC-TTC-08-E06 | [web] Create `assembly` again | Toast "This event already exists" | planned |
| TC-TTC-08-E07 | [web] Save a table with the Assembly row (replace), switch section and back | The Assembly option is rebuilt from the saved label | planned |
| TC-TTC-08-E08 | [web] Open a subject dropdown for a class with 2 of 5 subjects mapped | Only the 2 mapped subjects are offered | planned |
| TC-TTC-08-E09 | [web] Fill Monday for 3 rows; "Repeat All for Week", "Copy from day" Monday, Apply | Toast "Monday's schedule applied to all days"; Tuesday to Friday equal Monday | planned |
| TC-TTC-08-E10 | [web] "Repeat One Subject" with Mathematics | Toast "Mathematics applied to all days"; rows containing Mathematics fill all days | planned |
| TC-TTC-08-E11 | [web] Repeat buttons on an empty grid | Both disabled | planned |
| TC-TTC-08-E12 | [mobile] Tick "Include Saturday" | Saturday day tab and cells appear | planned |
| TC-TTC-08-E13 | [mobile] "Repeat All for Week" and choose Monday | Other days copy Monday for every subject row | planned |
| TC-TTC-08-E14 | [mobile] "Repeat One Subject": choose the 9:00 AM row, then Tuesday | Only that row's other days copy Tuesday | planned |
| TC-TTC-08-E15 | [mobile] Special row: create `Assembly` through the creatable dropdown | Option added with label "Assembly"; saved row label `ASSEMBLY` | planned |

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
| TC-TTC-09-A01 | Admin `DELETE /frontend/{section}` after F07 | 200 `{message:"Timetable deleted successfully for section <id>"}` | planned |
| TC-TTC-09-A02 | `GET /frontend/{section}` after the delete | 404 | planned |
| TC-TTC-09-A03 | `DELETE` again; `DELETE` for a section that never had one | 404 `Timetable not found for section` each | planned |
| TC-TTC-09-A04 | After deleting, `POST /frontend` for the same section | 200 (a new timetable can be created) | planned |
| TC-TTC-09-A05 | Class delete (`DELETE /masters/class_sections/{class}`) before and after clearing a section's timetable | 400 `section-related record(s)` before; 204 after | planned |
| TC-TTC-09-A06 | Write matrix: DELETE as Staff, Teacher, Student, Parent | 403 each; Admin 200 | planned |
| TC-TTC-09-A07 | No Authorization header | 401 | planned |
| TC-TTC-09-A08 | Tenant isolation: tenant B `DELETE` for tenant A's section | 404; tenant A's timetable intact | planned |
| TC-TTC-09-E01 | [web] After the API delete, open the section in the editor | Empty grid in edit mode | planned |
| TC-TTC-09-E02 | [web] Admin searches for a delete button in the editor | None exists (documents API-only) | planned |
| TC-TTC-09-E03 | [mobile] After the API delete, open the section | Edit mode with the one default row | planned |

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
1. In view mode "Export" > "Export As": "Export CSV", "Export Excel", "Export PNG". On the web build files download with the same names. On a device CSV opens the share sheet with the text; Excel and PNG show the info toasts "Excel export is only available on web." and "PNG export is only available on web.". Failure toasts "Error - Failed to export CSV", "Failed to export Excel", "Failed to export PNG".

**Expected results.** The exported content matches the displayed grid exactly.

**API endpoints.** None.

**Rules and validations.**
1. Cell text is quoted and double quotes escaped in web CSV; the mobile CSV joins cells with commas without quoting.
2. Excel output is HTML, not a true workbook.
3. Export is disabled while editing.

**Error and edge cases.**
- No rows: the Export button is not shown.
- Names containing commas can break the mobile CSV columns.

**Unit-testable logic.**
- Web `generateTableData` and `getFileName`; CSV quoting; Excel HTML builder. Mobile `generateCSVData`. These live in the editor files and need extracting.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TTC-10-U01 | [web] `generateTableData` for 1 subject row and 1 special row with 5 active days | Header `Time,Monday..Friday`; subject row has names or `--`; special row repeats the label 5 times | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U02 | [web] Same with Saturday active and an empty Saturday cell | Saturday column header present; empty cell text `Holiday` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U03 | [web] `getFileName("csv")` for class `QA-C1` section `A` | `Timetable - QA-C1 - A.csv` | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U04 | [web] CSV builder with a cell containing a double quote | The quote is doubled inside quoted cells | blocked: needs the helper exported from web/src/pages/masters/TimeTableEditor.tsx |
| TC-TTC-10-U05 | [mobile] `generateCSVData` header and row shape for the same input | Header row plus one row per timetable row; times in 12-hour format | blocked: needs generateCSVData exported from mobile/app/masters/timetable.tsx |
| TC-TTC-10-E01 | [web] View mode with rows: Export > Save as CSV | File `Timetable - <class> - <section>.csv` downloads; content matches the grid | planned |
| TC-TTC-10-E02 | [web] Export > Save as Excel | File `.xls` downloads containing an HTML table with the same cells | planned |
| TC-TTC-10-E03 | [web] Export > Save as PNG | A `.png` downloads without the edit buttons; image width covers all day columns | planned |
| TC-TTC-10-E04 | [web] Enter edit mode | Export button disappears | planned |
| TC-TTC-10-E05 | [web] Section without rows | No Export button | planned |
| TC-TTC-10-E06 | [mobile] Web build: Export > Export CSV | Download `Timetable - <class> - <section>.csv` | planned |
| TC-TTC-10-E07 | [mobile] Native build: Export Excel and Export PNG | Info toasts "Excel export is only available on web." and "PNG export is only available on web." | planned |

---

## F11 Student and parent timetable viewer (mobile)

**Purpose.** A student sees their own section's weekly timetable and a parent sees the selected child's, one day at a time. Web has no equivalent viewer.

**Roles and permissions.** The screen resolves the section and then calls `GET /students/timetable/frontend/{section_id}` (`timetable_management:read`) and `GET /masters/subjects` (`subjects:list`) to turn subject ids into names. Student and Parent hold `subjects:list` but, in the default seed, no `timetable_management:read`, so the timetable call returns 403 and the screen shows an error (see Known gaps). Staff and Admin see an information message instead of a timetable.

**Preconditions.** A saved timetable for the child's section (F07). For a Student the admission record gives the section; for a Parent a student is selected in the header selector.

**Steps, web.** Not available. The web editor route `/TimeTable` does not select the user's own section and Student and Parent have no menu entry for it.

**Steps, mobile.**
1. The screen route is `/timetable` with the title "My Timetable". No menu entry, hub card or tab links to it in the current app, so it opens only by route (for example on the Expo web build).
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
| TC-TTC-11-A01 | Student `GET /students/timetable/frontend/{own section}` (default seed) | 403 `Permission not found in database` | planned |
| TC-TTC-11-A02 | Parent `GET /students/timetable/frontend/{child's section}` (default seed) | 403 | planned |
| TC-TTC-11-A03 | After a fixture grants `timetable_management:read` to Student and Parent, repeat A01 and A02 | 200 with the section's `timetable_data` | planned |
| TC-TTC-11-A04 | Student `GET /masters/subjects/?active_only=true` | 200 plain array including the subjects used by the timetable | planned |
| TC-TTC-11-A05 | Student `GET /students/admission/my-admission` | 200 with `current_section_id` or `admitted_section_id` (Students module contract used here) | planned |
| TC-TTC-11-A06 | Student requests another section's timetable (with the read grant fixture) | 200 (the API does not restrict by own section; recorded as a scope gap) | planned |
| TC-TTC-11-E01 | [mobile] Student opens `/timetable` with the read-grant fixture and a saved timetable | Banner "Class Timetable", "Your weekly class schedule", today's chip with a dot, cards with subject names and "SUBJECT" badges | planned |
| TC-TTC-11-E02 | [mobile] Tap Saturday | Periods for Saturday only when a Saturday value was saved; otherwise "No periods scheduled" | planned |
| TC-TTC-11-E03 | [mobile] Special row (Lunch) | Appears on every day with a "SPECIAL" badge | planned |
| TC-TTC-11-E04 | [mobile] Parent with a selected child | Banner shows "<first name>'s schedule" and that child's section timetable | planned |
| TC-TTC-11-E05 | [mobile] Parent with no selected child | "No student selected. Use the selector in the header." | planned |
| TC-TTC-11-E06 | [mobile] Section without a timetable (API 404) | "Failed to load timetable" (a 404 is treated as an error); "No timetable has been set up yet. Contact your class teacher." appears only for a timetable saved with no rows | planned |
| TC-TTC-11-E07 | [mobile] Student on the default seed (no read grant) | "Failed to load timetable" | planned |
| TC-TTC-11-E08 | [mobile] Admin and Teacher open `/timetable` | Message "Timetable viewer is available for students and parents only." | planned |
| TC-TTC-11-E09 | [mobile] Look for a navigation entry to `/timetable` as Student | None in the tabs, hub or drawer (documents the gap) | planned |

---

## F12 School calendar, read-only (mobile)

**Purpose.** Every mobile user can see upcoming and past school holidays and events, as a list grouped by month or as a month grid.

**Roles and permissions.** `holiday_management:list` on `GET /masters/holidays/`. Admin, Staff and Teacher hold it; Student and Parent do not in the default seed, so they receive 403 and the screen shows an error. The screen has no in-app guard.

**Preconditions.** Holidays exist for the working year (F02) and are active.

**Steps, web.** Not applicable; the web Calendar entry shows the editable calendar of F01.

**Steps, mobile.**
1. Route `/calendar`, title "School Calendar". No tab, hub or drawer entry links to it today (reachable by route). A banner shows "School Calendar" and "Next holiday: <name> on <date>" or "No upcoming holidays".
2. Stat cards "Total", "Upcoming", "Past". Filter chips "Upcoming" (default), "All", "Past". View toggle: list or grid.
3. List: month headers in capitals (for example "NOVEMBER 2026"), cards with a colour bar, the name, a duration badge such as "3d" for multi-day events, the date range, the description (two lines), past events dimmed, an upcoming dot on upcoming events. Empty texts "No upcoming holidays", "No past holidays", "No holidays found".
4. Grid: month title with back and next arrows; Su to Sa headers; today highlighted; up to three coloured dots per day; tapping a day with holidays shows a panel with the date and the event names.
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
| TC-TTC-12-A01 | Teacher `GET /masters/holidays/?academic_year_id=Y&active_only=true&limit=100` | 200 `{items,total_count,has_next}`; up to 100 items | planned |
| TC-TTC-12-A02 | 101 active holidays in the year and `limit=100` | 100 items, `has_next` true | planned |
| TC-TTC-12-A03 | `limit=1000` | 200 (no upper bound on the API) | planned |
| TC-TTC-12-A04 | Staff `GET` the same | 200 | planned |
| TC-TTC-12-A05 | Student and Parent `GET` the same | 403 each (default seed) | planned |
| TC-TTC-12-A06 | Without an Authorization header | 401 | planned |
| TC-TTC-12-A07 | Tenant isolation: tenant B with tenant A's `academic_year_id` | Empty `items` | planned |
| TC-TTC-12-E01 | [mobile] Teacher opens `/calendar` with 3 holidays (1 past) | Banner "Next holiday: ...", stats Total 3, Upcoming 2, Past 1; default chip "Upcoming" lists 2 cards | planned |
| TC-TTC-12-E02 | [mobile] Tap "Past" then "All" | List changes to past only then all, grouped by uppercase month headers | planned |
| TC-TTC-12-E03 | [mobile] Multi-day holiday card | Colour bar, badge "3d", date range text | planned |
| TC-TTC-12-E04 | [mobile] Switch to grid; navigate months; tap a day with a holiday | Dots appear on holiday days; tooltip lists the names; tapping a day without holidays shows nothing | planned |
| TC-TTC-12-E05 | [mobile] No holidays in the year | "No upcoming holidays" in the list; banner "No upcoming holidays" | planned |
| TC-TTC-12-E06 | [mobile] Pull to refresh after an admin adds a holiday | New holiday appears | planned |
| TC-TTC-12-E07 | [mobile] Student opens `/calendar` (default seed) | "Failed to load holidays" with "Retry" | planned |
| TC-TTC-12-E08 | [mobile] Look for a navigation entry to `/calendar` | None in tabs, hub or drawer (documents the gap) | planned |

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
| TC-TTC-13-A01 | `GET /section/{section}` after F07 saved 2 rows and a special row | 200; `slot_time_data` groups with slots carrying `id`, `day`, `is_break`, `break_label`, `subject_options[].subject_name` | planned |
| TC-TTC-13-A02 | `GET /section/{section}` without a timetable | 404 `Timetable not found for section` | planned |
| TC-TTC-13-A03 | Admin `POST /bulk` for a new section reusing a `slot_time_id` from another section's saved timetable, one subject slot and one break slot | 200 with `id` and `section_id`; `GET /section/{new}` returns the slots | planned |
| TC-TTC-13-A04 | `POST /bulk` for the same section again | 500 (unique section constraint) | planned |
| TC-TTC-13-A05 | `POST /bulk` with a break slot lacking a label; a subject slot without options | 422 each | planned |
| TC-TTC-13-A06 | `POST /bulk` with a random `slot_time_id` | 500 (foreign key) | planned |
| TC-TTC-13-A07 | Admin `PATCH /timetable/slots/bulk` `{slots:[{id:<slot>, subject_options:[{subject_id:<other>}]}]}` | 200 list with the slot now holding only the new subject option | planned |
| TC-TTC-13-A08 | PATCH `{slots:[{id:<slot>, is_break:true, break_label:"LUNCH"}]}` | 200; slot `is_break` true, `break_label` "LUNCH"; existing options unchanged | planned |
| TC-TTC-13-A09 | PATCH an item without `subject_options` and without `is_break` | 422 | planned |
| TC-TTC-13-A10 | PATCH `is_break:true` together with `subject_options` | 422 | planned |
| TC-TTC-13-A11 | PATCH with a random slot id | 404 `Slot with id ... not found` | planned |
| TC-TTC-13-A12 | PATCH `/students/timetable/slots/bulk` (path without the doubled segment) | 404 or 405 | planned |
| TC-TTC-13-A13 | `GET /test` with no Authorization header | 200 `{message:"Test endpoint working"}` | planned |
| TC-TTC-13-A14 | Role matrix: `POST /bulk`, `GET /section/{id}`, `PATCH` as Staff, Teacher, Student, Parent | 403 each; Admin 2xx | planned |
| TC-TTC-13-A15 | No Authorization header on the three authenticated endpoints | 401 | planned |
| TC-TTC-13-A16 | Tenant isolation: tenant B `GET /section/{A's section}` and `PATCH` with A's slot id | 404 each | planned |
| TC-TTC-13-E01 | [web] and [mobile] Search the editors for any control that calls the legacy endpoints | None found (these endpoints have no UI) | planned |

---

## Known gaps

Defects and doc/code mismatches found while writing this page (the code behaviour is what the test cases above assert). Track them in `docs/modules/timetable-calendar.md` when fixed or accepted.

1. **Web calendar permission names.** `Calendar.tsx` gates "+ Add Event", "Save", "Delete", "Edit Event" on `holidays:*` while the backend and seed use `holiday_management:*`. A default-seeded Admin has no `holidays` grants, so those controls are hidden. The module doc's statement about the mobile holiday screen and the mobile timetable editor gating on `holidays` and `timetables` is out of date: the mobile code uses `holiday_management` and `timetable_management`.
2. **Day cells ignore permission.** Clicking a day opens the Add Event dialog for users without create permission; the submit then fails with 403.
3. **No restore in the UI.** `PATCH /{id}/activate` exists and web and mobile have hooks for it, but no screen calls it, and default lists hide inactive holidays, so a deactivated holiday cannot be restored from either app.
4. **Month views show at most 10 holidays.** The web calendar and the mobile admin holidays screen request the list without a limit (default 10). The mobile read-only calendar uses 100.
5. **Student and Parent cannot use the read-only views.** The default seed gives them no `holiday_management` or `timetable_management` grants, so the mobile calendar and the student and parent timetable viewer receive 403. Neither screen (`/calendar`, `/timetable`) is linked from any tab, hub or drawer entry, and the web self-service menu allowlist omits `/TimeTable` and `/Calender`. A comment in `mobile/app/(tabs)/students.tsx` still says no student or parent timetable view exists.
6. **Holiday validation gaps.** Fixed (2026-10-02): end before start is rejected (422 on create, 400 or 422 on update) and `color` must be `#rrggbb`. `is_active` still defaults to false on create.
7. **Holiday not-found handling.** Fixed (2026-10-02): `GET`, `PUT`, `DELETE` and `PATCH activate` return 404 for an unknown id.
8. **Timetable create versus replace.** `POST /frontend` drops Saturday and writes special rows for Monday to Friday only; `PUT` keeps any day and writes special rows for Monday to Sunday. A duplicate `POST`, an unknown section or subject, or a bad time string returns 500 with the exception text.
9. **No timetable sanity checks.** No `from` before `to`, no overlap, no check that a subject is mapped to the section or class, and the PUT merge of rows with the same time range loses a special row that shares a range with a subject row.
10. **Row order.** Rows are returned grouped by `slot_time_id` (a random UUID), not in time order, so the mobile viewer's period numbers can be out of order unless clients sort.
11. **Mobile editor.** An untouched subject row has an empty `subjects` object and Repeat All can copy an empty cell as `""`; both fail the UUID validation (422). Mobile Repeat One acts on a single row while web acts on every row containing the subject.
12. **Free-text Saturday on web.** The Saturday cell accepts free text and event names, which the API rejects (422), and the first save of a new timetable drops Saturday anyway.
13. **Viewer scope.** With the read grant, a Student can read any section's timetable (no own-section restriction), and Student or Parent default grants make the viewer unusable.
14. **Legacy and dead code.** `POST /bulk` needs pre-existing slot times and is unused; the PATCH bulk path is doubled (`/timetable/timetable/slots/bulk`) while a web helper calls the single-segment path; `GET /students/timetable/test` was unauthenticated (removed 2026-10-02, Fixed); web `api/hooks/masters/timetable.ts` targets non-existent routes.
15. **Auto-generation is not implemented.** Level timing templates, class-teacher first period, staff workload limits, publish and draft states and copying from the previous year described in the local spec have no tables or endpoints (the slot model has no staff column).
