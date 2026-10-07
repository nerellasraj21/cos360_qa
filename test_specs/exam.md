# Exam (EXM)

Feature documentation and test specification for the Exam module. Conventions, phases and test case IDs: `docs/testing/strategy.md`. Page layout: `docs/features/README.md`. Module rules and code map: `docs/modules/exam.md`.

_Last verified against code: 2026-10-07_

## Module overview

The Exam module lets a school define grading rules once (exam grade schemes, subject grade schemes, remark sets, board patterns, exam settings), create exams for one or more class-sections in a single call (subjects, mark components with max marks, exam dates), control who may enter marks, collect marks per student and component (online grid, bulk save, Excel), decide hall-ticket eligibility from attendance and fees and produce PDF hall tickets, compute subject and overall results (total, percentage, grade, GPA, pass/fail, rank), publish them, and let students and parents see raw marks and published results. Every endpoint lives under `/api/v1` and checks `resource:action` pairs on the caller's role. Web admin screens are additionally gated by the role names `admin`, `superadmin` and `principal`. Web is a React app (menu "Exam", routes `/exam/*`), mobile is an Expo app (tab "Exam", screens `app/exam/*`). Where this document and `docs/modules/exam.md` disagree, this document follows the code; see "Known gaps" at the end.

## Roles

| Role | Seeded exam permissions (`permission_catalog.py`) | What that allows |
|---|---|---|
| Admin | `exams`: create, read, update, delete, list. `exam_marks`: create, read, list | Everything except the SMS endpoints: `exams:send_sms` is not seeded for any role |
| Principal / superadmin (UI only) | Whatever the role record grants | Web and mobile treat them like Admin for the management screens (role-name check, not a permission) |
| Teacher | `exams`: read, list. `exam_marks`: create, read, list | Read all exam data, enter marks. Cannot create, edit, compute, publish, override or delete (needs `exams:create/update/delete`) |
| Staff | `exams`: read, list. `exam_marks`: read, list | Read-only; can load the mark grid but cannot save marks |
| Student | `exams`: read, list. `exam_marks`: read_own, list_own. `exam_results`: read_own, list_own. `exam_hall_tickets`: read_own, list_own | Own marks (`my-marks`), own published result (`my-result`, unreachable: DEF-EXM-6). The result list, hall ticket eligible and ineligible lists, download-all and the audit log return 403 for the role names Student and Parent; single-student result and hall ticket download are limited to the own record. Other `exams:read` endpoints (class-sections, subject configs, dates, enrolled students) stay readable (KG-3). Cannot call the mark grid (`exam_marks:read` is not granted) |
| Parent | `exams`: read, list. `exam_marks`: read_related, list_related. `exam_hall_tickets`: read_related, list_related | Linked child's marks and published result (`child-marks`, `child-result`). Same 403 blocks as Student; single-student endpoints are limited to linked children |

`exam_hall_tickets:*_own` and `*_related` are seeded but no endpoint checks them. Tenants created before a permission was added need `POST /auth/seed/all-role-permissions`.

Test personas used in the API tables: ADMIN, TEACHER, STAFF, STUDENT, PARENT (as above), ADMIN+SMS (Admin with `exams:send_sms` granted by the test setup), NOAUTH (no Authorization header), TENANT-B (a token for another tenant).

## Feature index

| ID | Title |
|---|---|
| F01 | Exam settings |
| F02 | Board patterns |
| F03 | Exam grade schemes and grade lookup |
| F04 | Subject grade schemes |
| F05 | Remark grade sets |
| F06 | Create exam, list and view exams |
| F07 | Class-sections, subject configs and config templates |
| F08 | Exam dates |
| F09 | Edit, clone, activate, deactivate, delete and unlock (status rules) |
| F10 | Mark entry permissions |
| F11 | Mark entry (per student, bulk save, Excel) |
| F12 | Marks summary |
| F13 | Hall ticket eligibility |
| F14 | Hall ticket publish and download |
| F15 | Result computation |
| F16 | Result publish, view and export |
| F17 | Student and parent views (my marks, my results) |
| F18 | Audit log |
| F19 | Notifications |

## Cross-feature reference

### Navigation

- Web sidebar (menu "Exam", demo catalog `scripts/seed_demo_catalog.py`): Exams (`/exam/exams`), Marks (`/exam/marks`), Hall Tickets (`/exam/hall-tickets`), Results (`/exam/results`), Grading (`/exam/grading`), Board Patterns (`/exam/board-patterns`), Exam Audit (`/exam/audit`), Exam Settings (`/exam/settings`). `/exam` is the "Exam Management" dashboard (quick links All Exams, Mark Entry, Results, Hall Tickets, and Settings for admin roles; "New Exam" button for admin roles). Student and Parent roles see only Exams, Marks, Hall Tickets, Results in the seeded role-menu allowlist.
- Mobile: bottom tab "Exam" opens the "Exam Management" hub. Tiles (each filtered by permission or admin role): Exams, Create Exam, Board Patterns, Grading, Mark Entry, Hall Tickets, Results, Exam Settings, Audit Log. Student and Parent also get a "My Marks" card.

### Exam status values and what each status allows

Statuses: `draft`, `active`, `locked`, `published`, `finalized` (`schemas/exam/enums.py`). Transitions that exist in code:

| From | Action (endpoint) | To | Notes |
|---|---|---|---|
| (new) | Create exam `POST /exams` | `active` | The exam is created active, not draft |
| (new) | Clone `POST /exams/{id}/clone` | `draft` | Header copy only |
| `draft` | Activate `POST /exams/{id}/activate` | `active` | Any other status: 409 |
| `active` | Deactivate `POST /exams/{id}/deactivate` | `draft` | Any other status: 409 |
| `active`, `locked`, `finalized` | Publish `POST /exams/{id}/publish` | `published` | `draft` and `published`: 409 |
| `locked`, `published`, `finalized` | Unlock `POST /exams/{id}/unlock` (reason required) | `active` | `draft` and `active`: 409 |
| any except `published` | Delete `DELETE /exams/{id}` | (removed) | `published`: 409 |

No endpoint ever sets `locked` or `finalized`; they can only exist from data loaded outside the API.

Which actions each status allows (as enforced by the backend; "yes" means no status check exists):

| Action | draft | active | locked | published | finalized |
|---|---|---|---|---|---|
| Edit header `PUT /exams/{id}` | yes | yes | yes | yes | yes |
| Add class-section | yes | yes | 409 | 409 | 409 |
| Edit subject config, dates, mark permissions | yes | yes | yes | yes | yes |
| Save marks, Excel upload | yes | yes | yes | yes | yes |
| Compute hall-ticket eligibility, override, publish hall tickets | yes | yes | yes | yes | yes |
| Compute results | yes | yes | yes | yes | yes |
| Publish results | 409 | yes | yes | 409 | yes |
| Student `my-result` / `child-result` | 403 | 403 | 403 | yes | yes |
| Student `my-marks` / `child-marks` | yes | yes | yes | yes | yes |
| Delete | yes | yes | yes | 409 | yes |

Client-side gating differs (web and mobile hide actions by status); each feature section lists it.

### Grading primitives used by several features

Grade lookup (`grading_service.lookup_grade`), compute rules (`aggregate_service`), hall ticket rules (`hall_ticket_service`) are documented with worked examples in F03, F15 and F13.

### Standard fixtures used in the test cases

- Fixture GS1 "QA Standard" exam grade scheme: A+ 90.00-100.00 gpa 4.00 pass; A 80.00-89.99 gpa 3.50 pass; B 70.00-79.99 gpa 3.00 pass; C 60.00-69.99 gpa 2.00 pass; D 35.00-59.99 gpa 1.00 pass; F 0.00-34.99 gpa 0.00 fail.
- Fixture EX1: exam "QA FA1" for class "QA Class 5" section "A", scheme GS1, subjects Math (components Written max 80, Oral max 20), Science (Written max 100), English (Written max 100), four enrolled students S1..S4.
- API tests run on the QA tenant `qa_school` (local database `cos360_test`, never a real tenant); it holds only the role logins and API test data.
- UI test cases (the 8-column tables) run on the seeded manual-test tenant `qa_manual` (`backend/scripts/qa/setup_manual_tenant.py`). Exam data seeded there: exam grade scheme "Standard Percentage Grading" (bands A+ 90-100 down to E 0-34.99 fail), subject scheme "Subject Grading", remark set "Co-Scholastic Grading" (A to D), board patterns State / Primary and State / Pre-Primary, exam settings (Default Board State, Minimum Attendance % 60, no fee minimum), and three exams in 2026-2027: "Unit Test 1 - Class 1B" (published; Class 1 / 1-B; English, Hindi, Telugu, Mathematics, Environmental Studies, Written 25 each; computed results Advik Mehta 78.00 rank 1, Harsha Raju 72.80 rank 2, Nikhil Krishnan 68.00 rank 3; 5 dates in Room 1B), "Unit Test 1 - Class 2A" (published; Arjun Yadav, Rahul Menon) and "Half Yearly Examination 2026" (active; Class 1 to Class 5, sections A and B; Written 80 plus Internal Assessment 20; no marks; hall tickets computed and published, 21 eligible, for example Karthik Reddy 001 HT-2025-0005).
- UI fixture QA FA1 is created by TC-EXM-06-E01 in `qa_manual`: Class 1 / 1-B, scheme "Standard Percentage Grading", Mathematics (Written 80, Oral 20), English (Written 100), Environmental Studies (Written 100), students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007). Names of UI-created data start with "QA "; clean up after the case.
- Student and parent UI cases use seeded logins (student login = admission number, for example Advik Mehta 002; parent login = the parent's email). Seeded accounts force a password change at first sign-in. The QA Student and Parent logins are not linked to any student.
- Quoted UI texts use ASCII: where the UI shows a typographic dash or apostrophe, this page writes a hyphen or a straight quote.

---

## F01 Exam settings

**Purpose.** Admin stores school-wide exam defaults: default board, hall-ticket minimum attendance, minimum fee-paid percentage, grace and re-conduct values.

**Roles and permissions.**
- Read: `exams:read`. Write: `exams:update`.
- Menu: Exam > Exam Settings. Web route and mobile screen are restricted to role names admin, superadmin, principal (non-admins are redirected to `/exam` on web and to `/exam/list` on mobile). The mobile hub tile "Exam Settings" is shown only to admin roles.

**Preconditions.**
- None for the write. The settings row does not exist until the first `PUT` (nothing seeds it).

**Steps, web.**
1. Sidebar: Exam > Exam Settings (`/exam/settings`). Page title "Exam Settings", subtitle "Configure school-wide exam defaults".
2. Card "Board Configuration": select "Default Board" (CBSE, ICSE, State Board, BTech, Custom). When Custom is chosen, a "Custom Board Name" input appears.
3. Card "Hall Ticket Settings": "Minimum Attendance %" (0-100, default 75, help text "Students below this threshold are ineligible").
4. Card "Fee Payment Policy": "Minimum Fee Paid %" (0-100, help text "Students below this fee payment % cannot appear for exam").
5. Click "Save Settings". Toast "Exam settings saved successfully".
6. The page also submits hidden values grace_max_per_subject (default 2), grace_max_subjects (default 3), grace_auto_apply (false), reconduct_max_failed_subjects (default 2).

**Steps, mobile.**
1. Exam tab > tile "Exam Settings" (admin roles only). Opening this or any other admin-only exam screen by URL on a cold load (Expo web address bar, refresh) crashes with "Something went wrong" (KG-20); open it from the hub. Cards "Board Configuration" (Default Board, Custom Board Name), "Hall Ticket Settings" (Minimum Attendance %), "Fee Payment Policy" (Minimum Fee Paid %).
2. Edit and tap "Save Settings". Toast "Saved" / "Exam settings updated.". Only four fields are sent (default_board, custom_board_name, hall_ticket_min_attendance, hall_ticket_min_fee_paid_pct), so grace and re-conduct values are reset by the full overwrite (see rules).

**Expected results.**
- Row created or overwritten in `exam_settings` (singleton). `GET` returns the same values; decimals arrive as strings (`"75.00"`).
- Hall ticket compute (F13) reads `hall_ticket_min_attendance` and `hall_ticket_min_fee_paid_pct` from this row.

**API endpoints.**
- `GET /exam-settings`: returns `ExamSettingsRead` (id plus the fields below). 404 `"Exam settings not configured yet."` until the first PUT.
- `PUT /exam-settings`: body `ExamSettingsUpdate`: `default_board` (string, not validated against the enum), `custom_board_name`, `hall_ticket_min_attendance` (0-100), `hall_ticket_min_fee_paid_pct` (0-100), `exam_fee_type_id` (uuid), `grace_max_per_subject` (0-100), `grace_max_subjects` (0-50), `grace_auto_apply` (bool, default false), `reconduct_max_failed_subjects` (int >= 0, default 2). Creates the row on first call, otherwise overwrites every field.

**Rules and validations.**
- Singleton: the first row found is used. `PUT` overwrites all nine fields; omitted fields become null (or false, or 2 for `reconduct_max_failed_subjects`). Always send the full object.
- Only `hall_ticket_min_attendance` and `hall_ticket_min_fee_paid_pct` change behaviour (hall tickets). `default_board`, `custom_board_name`, `exam_fee_type_id`, `grace_*` and `reconduct_max_failed_subjects` are stored and never read by any logic.
- Hall ticket default: if the row is missing or `hall_ticket_min_attendance` is null or 0, 75.00 is used. A `hall_ticket_min_fee_paid_pct` of null disables the fee check; 0 enables the check but every student passes it.

**Error and edge cases.**
- Web on a tenant with no settings row: GET returns 404, the page shows the load error text instead of the form, so the first save cannot be done from web (KG-9). Mobile shows the form with defaults and can create the row.
- `hall_ticket_min_attendance` 100.01 or -1: 422. Non-admin web user typing `/exam/settings`: redirected to `/exam`.
- Student or Parent calling PUT: 403. Student calling GET: 200 (they hold `exams:read`).

**Unit-testable logic.**
- `ExamSettingsBase` field bounds (pydantic).
- `upsert_settings` overwrite semantics with a fake session (create vs update, omitted fields reset).
- Web `settingsSchema` (zod) bounds; web `isAdminRoleName`; mobile `isAdminRole`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-01-U01 | `ExamSettingsUpdate(hall_ticket_min_attendance=100)` and `=0` | Valid; `100.01` and `-0.01` raise validation error | passing |
| TC-EXM-01-U02 | `ExamSettingsUpdate(grace_max_per_subject=101)` and `grace_max_subjects=51` | Both raise validation error; `100` and `50` valid | passing |
| TC-EXM-01-U03 | `ExamSettingsUpdate()` with no fields | `grace_auto_apply=False`, `reconduct_max_failed_subjects=2`, all others None | passing |
| TC-EXM-01-U04 | `upsert_settings` with fake session, no existing row, payload hall 80 fee 50 | New `ExamSettings` added with those values and a generated id | passing |
| TC-EXM-01-U05 | `upsert_settings` with existing row (hall 80, grace 2) and payload hall 70 only | Row hall 70, grace_max_per_subject None, reconduct 2 (full overwrite) | passing |
| TC-EXM-01-U06 | Web `isAdminRoleName` for `Admin`, `PRINCIPAL`, `superadmin`, `Teacher`, `null` | true, true, true, false, false | passing |
| TC-EXM-01-U07 | Mobile `isAdminRole` same inputs | Same results as U06 | passing |
| TC-EXM-01-U08 | Web `settingsSchema` with attendance 101 or -1 | Validation fails; 0 and 100 pass | blocked: settingsSchema is a non-exported const inside web/src/pages/exam/ExamSettings.tsx; needs it exported |
| TC-EXM-01-A01 | GET `/exam-settings` on a tenant with no settings row (ADMIN) | 404 `"Exam settings not configured yet."` | passing |
| TC-EXM-01-A02 | PUT `/exam-settings` with full valid body (ADMIN), then GET | PUT 200 with id; GET returns same values, decimals as strings (`"75.00"`) | passing |
| TC-EXM-01-A03 | PUT twice: first with all fields, second with only `hall_ticket_min_attendance` | Second GET shows other fields null, `grace_auto_apply` false, `reconduct_max_failed_subjects` 2; still one row | passing |
| TC-EXM-01-A04 | PUT with `hall_ticket_min_attendance` 101, `-1`; `hall_ticket_min_fee_paid_pct` 101 | 422 each | passing |
| TC-EXM-01-A05 | PUT with `grace_max_per_subject` 101 and `grace_max_subjects` 51 and `reconduct_max_failed_subjects` -1 | 422 each | passing |
| TC-EXM-01-A06 | PUT boundary values 0 and 100 for both percentages | 200, stored `"0.00"` and `"100.00"` | passing |
| TC-EXM-01-A07 | PUT `default_board` `"Anything"` (not in enum) | 200 (not validated) | passing |
| TC-EXM-01-A08 | GET as ADMIN, TEACHER, STAFF, STUDENT, PARENT (parametrised) | 200 for all (all hold `exams:read`) | passing |
| TC-EXM-01-A09 | PUT as TEACHER, STAFF, STUDENT, PARENT (parametrised) | 403 each | passing |
| TC-EXM-01-A10 | GET and PUT with NOAUTH | 401 each | passing |
| TC-EXM-01-A11 | Tenant isolation: ADMIN of tenant A saves settings; ADMIN of tenant B GET | Tenant B gets 404 (or its own values); tenant A row never returned | passing |
| TC-EXM-01-A12 | Token for tenant A with `cschema` header of tenant B on GET and PUT | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-01-E01 | P1 | Web | Admin | Seeded exam settings: Default Board State, Minimum Attendance % 60, Minimum Fee Paid % empty. | 1. Sign in as Admin.<br>2. Open Exam > Exam Settings.<br>3. Enter "Minimum Attendance %" 80.<br>4. Enter "Minimum Fee Paid %" 50.<br>5. Click "Save Settings".<br>6. Reload the page. | Toast "Exam settings saved successfully". After reload the fields show 80 and 50; GET /exam-settings returns "80.00" and "50.00". Clean-up: set 60, clear the fee value and save. | planned |
| TC-EXM-01-E02 | P2 | Web | Admin | Seeded exam settings (Default Board State). | 1. Sign in as Admin.<br>2. Open Exam > Exam Settings.<br>3. Open "Default Board" and choose "Custom".<br>4. Enter "Custom Board Name" "QA Board".<br>5. Click "Save Settings".<br>6. Reload the page. | "Custom Board Name" appears only while Custom is selected. Toast "Exam settings saved successfully"; after reload Default Board is Custom and the name is "QA Board". Clean-up: choose "State Board" again and save. | planned |
| TC-EXM-01-E03 | P3 | Web | Admin | A tenant whose exam settings were never saved (qa_manual has a seeded row, so use a freshly provisioned tenant). | 1. Sign in as Admin.<br>2. Open Exam > Exam Settings. | The page shows the load error "Exam settings not configured yet." instead of the form, so the first save cannot be made from web (KG-9). Update to the form once fixed. | planned |
| TC-EXM-01-E04 | P2 | Web | Teacher | None. | 1. Sign in as Teacher.<br>2. Open /exam/settings in the address bar. | Redirected to /exam. The dashboard has no "Settings" quick link and no "New Exam" button. (The sidebar still lists Exam Settings because it comes from the menu.) | planned |
| TC-EXM-01-E05 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Exam Settings.<br>3. Enter "Minimum Attendance %" 150.<br>4. Click "Save Settings". | Inline error under the field ("Number must be less than or equal to 100"); no request is sent and no toast appears. | planned |
| TC-EXM-01-E06 | P1 | Mobile | Admin | Seeded exam settings (Minimum Attendance % 60). Open the screen from the Exam tab, not by URL (KG-20). | 1. Sign in as Admin.<br>2. Open the Exam tab.<br>3. Tap "Exam Settings".<br>4. Change "Minimum Attendance %" to 80.<br>5. Tap "Save Settings".<br>6. Go back and open "Exam Settings" again. | Toast "Saved" "Exam settings updated."; the screen shows 80 after reopening. Only four fields are sent, so the seeded grace values (2 and 1) are reset to empty (KG-11). Clean-up: set 60 again. | planned |
| TC-EXM-01-E07 | P3 | Mobile | Teacher | None. | 1. Sign in as Teacher.<br>2. Open the Exam tab. | Tiles shown: Exams, Mark Entry, Hall Tickets, Results. No "Exam Settings" tile. In-app navigation to /exam/settings redirects to /exam/list. | planned |
| TC-EXM-01-E08 | P3 | Mobile | Admin | Expo web. | 1. Sign in as Admin.<br>2. Type /exam/settings in the browser address bar and press Enter (cold load). | Exam Settings screen loads. Currently the app shows "Something went wrong" with "Attempted to navigate before mounting the Root Layout component" (KG-20). | blocked: KG-20 admin-only exam screens crash on a cold URL load |

API tests implemented in: `backend/tests/api/exam/test_f01_settings.py`

Implemented in: backend/tests/unit/exam/test_settings_boards_grading.py (U01-U05); web/src/__tests__/exam/examSchemas.test.ts (U06); mobile/__tests__/exam/roles.test.ts (U07). U08 blocked.

---

## F02 Board patterns

**Purpose.** Admin records, per board and education level, the list of exam types a school runs (for example FA1, SA1) with nature, weightage and count per year.

**Roles and permissions.**
- Create: `exams:create`. Read: `exams:read`. Update: `exams:update`. Delete: `exams:delete`.
- Menu: Exam > Board Patterns (the sidebar lists it for Teacher and Staff too). The web route has no role guard and shows "New Pattern" and "Create First Pattern" to every role, the API then answers 403 (KG-22); the mobile screen and tile are admin-role only (mobile redirects non-admins to `/exam/list`).

**Preconditions.**
- None.

**Steps, web.**
1. Exam > Board Patterns (`/exam/board-patterns`). Title "Board Patterns", subtitle "Define exam type patterns per board and education level". Empty state "No board patterns yet" with "Create First Pattern".
2. Click "New Pattern". Dialog "Create Board Pattern": select "Board" (CBSE, ICSE, State, BTech, Custom), select "Level" (Pre-Primary, Primary, Upper Primary, Secondary, Intermediate, Diploma, BTech, MTech, IIT, Others), "Custom Board Name" (only for Custom).
3. In "Exam Types" table fill "Type Name", "Nature" (formative, summative, cumulative, custom), "Weightage %", "Count/Yr"; "Add Type" adds a row, the X button removes one. At least one type with a name is required.
4. Click "Save Pattern". Toast "Board pattern created successfully".
5. Search box "Search board or level...", sortable columns Board, Level, Status; click a row to expand its exam types (Type Name, Nature, Weightage %, Count/Year, Order).
6. Edit icon opens "Edit Board Pattern"; saving sends the whole exam type list (toast "Board pattern updated successfully"). Trash icon opens "Delete Board Pattern?"; confirm toast "Board pattern deleted".

**Steps, mobile.**
1. Exam tab > "Board Patterns" (admin only). "New Pattern" opens the modal "New Board Pattern" with Board, Level, Custom Board Name (Custom only), Exam Types (Type Name, Nature, Weightage %, Count/Year, "Add Type").
2. Save. Validation toast "At least one exam type is required." Toasts "Created", "Updated", "Deleted". Delete asks "Delete Pattern" with the board and level.

**Expected results.**
- Row in `board_exam_patterns` with child rows in `board_pattern_exam_types`, unique per (board, level) within the tenant.
- Patterns are informational: exam creation does not read them (exam `board`, `level`, `exam_type` are plain strings).

**API endpoints.**
- `POST /board-patterns`: `board` (enum CBSE, ICSE, State, BTech, Custom), `custom_board_name` (max 100), `level` (enum), `is_active` (default true), `exam_types[]` (`exam_type_name` max 50, `nature` enum, `weightage_percent`, `count_per_year`, `sort_order`). 201.
- `GET /board-patterns`: list with exam types. `GET /board-patterns/{pattern_id}`: one. 404 if unknown.
- `PUT /board-patterns/{pattern_id}`: partial; when `exam_types` is present, all existing types are deleted and re-created.
- `DELETE /board-patterns/{pattern_id}`: 204.

**Rules and validations.**
- Unique (board, level): second create gives 409. Update to an existing pair gives 409.
- Delete blocked with 409 when any exam has the same `board` and `level` strings.
- Update: `board`, `custom_board_name`, `level`, `is_active` change only when provided (null is ignored); `exam_types` replaces the whole list; an empty list removes all types.
- No range check on `weightage_percent` or `count_per_year` in the backend (web restricts 0-100 and count >= 1).
- This service commits internally.

**Error and edge cases.**
- Unknown `board` or `level` value: 422. Missing `exam_type_name`: 422.
- Pattern for board `Custom` with no `custom_board_name`: accepted.
- Deleting a pattern whose board and level match an existing exam: 409 `... is referenced by one or more exams and cannot be deleted.`

**Unit-testable logic.**
- `BoardPatternCreate` validation (enums, defaults).
- `update_board_pattern` replace-all semantics with a fake session; `_check_board_pattern_not_in_use`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-02-U01 | `BoardPatternCreate(board="CBSE", level="primary")` | Valid; `is_active=True`, `exam_types=[]` | passing |
| TC-EXM-02-U02 | `BoardPatternCreate(board="Other", level="primary")` and `level="kg"` | Both raise validation error | passing |
| TC-EXM-02-U03 | `BoardPatternExamTypeCreate` with name of 50 and 51 characters | 50 valid, 51 invalid | passing |
| TC-EXM-02-U04 | `update_board_pattern` with `exam_types=[]` on a pattern with 3 types (fake session) | All 3 deleted, none re-added | passing |
| TC-EXM-02-U05 | `update_board_pattern` with `exam_types=None` | Existing types untouched | passing |
| TC-EXM-02-U06 | `_check_board_pattern_not_in_use` with a fake exam row matching board and level | Raises 409; no match returns None | passing |
| TC-EXM-02-A01 | POST valid pattern CBSE/primary with two exam types (ADMIN) | 201; response has id and two types with ids and `pattern_id` | passing |
| TC-EXM-02-A02 | POST second CBSE/primary | 409 | passing |
| TC-EXM-02-A03 | POST with `board="X"`, `level="kg"`, missing `exam_types[0].exam_type_name`, nature `"daily"` (parametrised) | 422 each | passing |
| TC-EXM-02-A04 | POST with 51-character `exam_type_name` | 422 | passing |
| TC-EXM-02-A05 | GET list after creating two patterns | 200; both present with nested types | passing |
| TC-EXM-02-A06 | GET one existing / random uuid | 200 / 404 | passing |
| TC-EXM-02-A07 | PUT `{"is_active": false}` only | 200; `is_active` false; types unchanged | passing |
| TC-EXM-02-A08 | PUT with new `exam_types` list of one item | 200; old types gone, one type returned | known defect: DEF-EXM-1: PUT /board-patterns/{id} response returns the stale exam_types (old rows) instead of the replaced list |
| TC-EXM-02-A09 | PUT changing board/level to an existing pair | 409 | passing |
| TC-EXM-02-A10 | PUT to unknown id | 404 | passing |
| TC-EXM-02-A11 | DELETE unused pattern then GET | 204 then 404 | passing |
| TC-EXM-02-A12 | DELETE pattern whose board and level equal an existing exam's | 409 | passing |
| TC-EXM-02-A13 | DELETE unknown id | 404 | passing |
| TC-EXM-02-A14 | Create, update, delete as TEACHER, STAFF, STUDENT, PARENT (parametrised) | 403 each | passing |
| TC-EXM-02-A15 | List and GET one as ADMIN, TEACHER, STAFF, STUDENT, PARENT | 200 for all | passing |
| TC-EXM-02-A16 | All five endpoints with NOAUTH | 401 each | passing |
| TC-EXM-02-A17 | Tenant isolation: pattern created in tenant A; tenant B list and GET by id | List excludes it; GET returns 404 | passing |
| TC-EXM-02-A18 | Same board and level created in tenant A and tenant B | Both succeed (uniqueness is per tenant) | passing |
| TC-EXM-02-A19 | Token A with `cschema` of tenant B on POST | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-02-E01 | P1 | Web | Admin | Seeded patterns State / Primary and State / Pre-Primary exist; no CBSE / Primary pattern. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click "New Pattern".<br>4. Keep "Board" CBSE and "Level" Primary.<br>5. In the first type row enter "Type Name" "QA FA1", "Nature" formative, "Weightage %" 10, "Count/Yr" 2.<br>6. Click "Save Pattern". | Toast "Board pattern created successfully". Row CBSE, Primary appears with badge "1 types". | planned |
| TC-EXM-02-E02 | P2 | Web | Admin | TC-EXM-02-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click the CBSE / Primary row. | Expanded table with columns Type Name, Nature, Weightage %, Count/Year, Order showing QA FA1, formative, 10, 2, 0. The seeded State / Primary row expands to Unit Test, Half Yearly Examination, Annual Examination. | planned |
| TC-EXM-02-E03 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click "New Pattern".<br>4. Leave "Type Name" empty.<br>5. Click "Save Pattern". | Inline "Name required" on the type row; dialog stays open; nothing saved. | planned |
| TC-EXM-02-E04 | P3 | Web | Admin | Seeded State / Primary pattern exists. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click "New Pattern".<br>4. Choose "Board" State and "Level" Primary; enter "Type Name" "QA FA2".<br>5. Click "Save Pattern". | Error toast "A BoardExamPattern for board='State' / level='primary' already exists."; no new row. | planned |
| TC-EXM-02-E05 | P2 | Web | Admin | TC-EXM-02-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click the Edit icon on CBSE / Primary.<br>4. Click "Add Type" and enter "QA SA1", summative, 20, 1.<br>5. Click "Save Pattern". | Toast "Board pattern updated successfully"; the row shows "2 types" and the expanded table lists QA FA1 and QA SA1. | planned |
| TC-EXM-02-E06 | P2 | Web | Admin | TC-EXM-02-E01 done; no exam uses board CBSE with level primary. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click the trash icon on CBSE / Primary.<br>4. Click "Delete" in "Delete Board Pattern?". | Toast "Board pattern deleted"; the row disappears (empty state "No board patterns yet" if it was the only one). | planned |
| TC-EXM-02-E07 | P3 | Web | Admin | Seeded State / Primary pattern; the seeded exams use board State and level primary. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Click the trash icon on State / Primary.<br>4. Click "Delete" in "Delete Board Pattern?". | Error toast ending "is referenced by one or more exams and cannot be deleted."; the pattern remains. | planned |
| TC-EXM-02-E08 | P3 | Web | Admin | Seeded patterns. | 1. Sign in as Admin.<br>2. Open Exam > Board Patterns.<br>3. Type "State" in "Search board or level...".<br>4. Replace the text with "zzz". | "State" keeps both seeded rows; "zzz" shows "No patterns match your search." | planned |
| TC-EXM-02-E09 | P2 | Mobile | Admin | No CBSE / Primary pattern exists. | 1. Sign in as Admin.<br>2. Open the Exam tab.<br>3. Tap "Board Patterns".<br>4. Tap "New Pattern".<br>5. Keep Board CBSE, Level Primary; enter Type Name "QA FA1", Weightage % 10, Count/Year 2.<br>6. Tap "Save Pattern". | Toast "Created"; a card for CBSE / Primary is listed. | planned |
| TC-EXM-02-E10 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Board Patterns".<br>3. Tap "New Pattern".<br>4. Leave Type Name empty.<br>5. Tap "Save Pattern". | Toast "At least one exam type is required."; nothing saved. | planned |
| TC-EXM-02-E11 | P2 | Mobile | Admin | TC-EXM-02-E09 done. | 1. Sign in as Admin.<br>2. Open Exam tab > "Board Patterns".<br>3. Tap delete on the CBSE / Primary card.<br>4. Confirm "Delete Pattern". | Toast "Deleted"; the card disappears. | planned |
| TC-EXM-02-E12 | P3 | Mobile | Teacher | None. | 1. Sign in as Teacher.<br>2. Open the Exam tab. | No "Board Patterns" tile. In-app navigation to /exam/board-patterns redirects to /exam/list. | planned |
| TC-EXM-02-E13 | P3 | Web | Teacher | None. | 1. Sign in as Teacher.<br>2. Open Exam > Board Patterns.<br>3. Click "New Pattern", enter type "QA FA1", click "Save Pattern". | Target: the create controls are hidden for roles without exams:create. Currently "New Pattern" and "Create First Pattern" are shown and saving fails with a permission error toast (KG-22). | blocked: KG-22 create buttons shown to roles without exams:create |

API tests implemented in: `backend/tests/api/exam/test_f02_board_patterns.py`

Implemented in: backend/tests/unit/exam/test_settings_boards_grading.py.

---

## F03 Exam grade schemes and grade lookup

**Purpose.** Admin defines percentage bands (grade label, GPA, pass or fail) used to grade a student's overall exam total, and as the fallback for subjects that have no subject grade scheme. This feature also documents the grade lookup used by every result calculation.

**Roles and permissions.**
- Create: `exams:create`. Read: `exams:read`. Update: `exams:update`. Delete: `exams:delete`.
- Menu: Exam > Grading > "Exam Grade Schemes". The "Grading" dashboard page lists three cards (Exam Grade Schemes, Subject Grade Schemes, Remark Grade Sets, each with an "Open" button) and counts. Mobile: Exam tab > "Grading" (admin only) lists the same three entries, and the "Exam Grade Schemes" screen is admin only.

**Preconditions.**
- None. An exam grade scheme must exist before the web "Create Exam" button is enabled (it is disabled with tooltip "Set up grading schemes before creating an exam").

**Steps, web.**
1. Exam > Grading, click "Exam Grade Schemes" (`/exam/grading/exam-schemes`). Title "Exam Grade Schemes". Subtitle "Map total percentage ranges to grades (A+, A, B...) with GPA and pass/fail", search "Search schemes...", columns S.No., Name, Default, Bands, Actions. Empty state "No grade schemes yet" with "Create First Scheme".
2. Click "New Scheme". Dialog "Create Exam Grade Scheme": "Scheme Name *", "Description", checkbox "Set as default scheme", and the band editor with columns "From %", "To %", "Grade", "GPA", "Remarks", "Pass?" (checkbox Pass or Fail). The editor starts empty ("No grade bands defined. Click "Add Band" to get started."). "Add Band" adds a row (default 0 to 100), the grip handle reorders by drag, the trash button removes a band.
3. Click "Save Scheme". Toast "Exam grade scheme created successfully".
4. Click a row to expand a read-only band table. Edit icon opens "Edit Exam Grade Scheme" (all bands are replaced on save, toast "Exam grade scheme updated successfully"). Trash opens "Delete Grade Scheme?" (text: deletion is blocked if the scheme is in use by an exam); toast "Grade scheme deleted".
5. Client rules: name 1-100 characters, at least one band, grade label 1-10 characters, From % <= To %, GPA 0-10, description up to 300.

**Steps, mobile.**
1. Exam tab > "Grading" > "Exam Grade Schemes" (title "Exam Grade Schemes"). "New Scheme" modal: "Name *", "Description", toggle "Set as default scheme", band rows with "Grade Label", "From %", "To %", "GPA", "Remarks" and a PASS or FAIL toggle, "Add Band".
2. Validation toasts "Name is required." and "At least one grade band required.". Toasts "Created", "Updated", "Deleted"; delete confirm "Delete Scheme".

**Expected results.**
- Rows in `exam_grade_schemes` and `exam_grade_bands`. `is_default` is stored but nothing reads it and several schemes may be default.
- Exams reference a scheme through `exam_grade_scheme_id` chosen at creation (F06).

**API endpoints.**
- `POST /grade-schemes/exam`: `name` (max 100), `description`, `is_default`, `bands[]`. 201.
- `GET /grade-schemes/exam`, `GET /grade-schemes/exam/{scheme_id}`.
- `PUT /grade-schemes/exam/{scheme_id}`: same body as create; replaces name, description, is_default and all bands.
- `DELETE /grade-schemes/exam/{scheme_id}`: 204.
- Band fields: `from_percent`, `to_percent` (0-100, from <= to), `from_marks`, `to_marks`, `grade_label` (max 10), `gpa` (>= 0, default 0.00), `remarks` (max 100), `is_pass` (default true), `sort_order`. Band reads return percentages and gpa as numbers (floats), not strings.

**Rules and validations.**
- Name unique per tenant: duplicate gives 400 `"Exam grade scheme '<name>' already exists"`; on update only when the name changes.
- Backend allows zero bands (web and mobile require at least one).
- No check for overlapping bands or gaps.
- Delete: 409 when any exam has `exam_grade_scheme_id` equal to the scheme (`... is referenced by one or more exams and cannot be deleted.`).
- The service commits internally.

**Grade lookup (exact algorithm, `lookup_grade(marks_obtained, max_marks, bands)`).**
1. If `bands` is empty or `max_marks == 0`, return None.
2. `percent = marks_obtained / max_marks * 100` (Decimal, not rounded).
3. Sort bands by `from_percent` descending. Return the first band with `from_percent <= percent <= to_percent` (inclusive both ends). Result: grade label, gpa, remarks, `is_pass`.
4. If no band matches (a gap, or percent above every `to_percent`), return the band with the lowest `from_percent` (usually the failing band).
5. Callers handle absence before calling: absent gives grade `ABS`, gpa 0.0, remarks "Absent", `is_pass` false.

Worked examples with fixture GS1:

| Obtained / max | Percent | Result |
|---|---|---|
| 90 / 100 | 90 | A+ (boundary belongs to the higher band because of the descending sort) |
| 89.99 / 100 | 89.99 | A |
| 89.995 / 100 | 89.995 | No band (gap between 89.99 and 90): fallback lowest band F, fail |
| 35 / 100 | 35 | D, pass |
| 34.99 / 100 | 34.99 | F, fail |
| 0 / 100 | 0 | F, fail |
| 100 / 100 | 100 | A+ |
| 45 / 50 | 90 | A+ (percentage based; max marks do not matter) |
| 101 / 100 | 101 | Above every band: fallback F (fail) |
| 5 / 0 | not computed | None (max marks 0) |
| any / any with no bands | not computed | None |
| Overlap: bands A 80-100 and B 70-85, 82 / 100 | 82 | A (higher `from_percent` is tested first) |

**Error and edge cases.**
- Band with `from_percent` 60 and `to_percent` 50: 422 `"from_percent must be <= to_percent"`.
- Percent 100.01 or -0.01 on a band: 422.
- Deleting a scheme used by an exam: 409. Updating a scheme used by an exam changes grades on the next compute.
- Gap risk: define bands contiguously (for example to_percent 89.99) because percentages carry many decimals.

**Unit-testable logic.**
- `lookup_grade` (every row of the table above), `GradeBandBase` validator, `ABSENT_GRADE` constant, web `gradeBandSchema` and `gradeSchemeSchema`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-03-U01 | `lookup_grade(90, 100, GS1)` | A+, gpa 4.00, `is_pass` true | passing |
| TC-EXM-03-U02 | `lookup_grade(89.99, 100, GS1)` | A, gpa 3.50 | passing |
| TC-EXM-03-U03 | `lookup_grade(89.995, 100, GS1)` (gap) | Fallback lowest band: F, `is_pass` false | passing |
| TC-EXM-03-U04 | `lookup_grade(35, 100, GS1)` and `(34.99, 100, GS1)` | D pass, then F fail | passing |
| TC-EXM-03-U05 | `lookup_grade(0, 100, GS1)` and `(100, 100, GS1)` | F fail, A+ pass | passing |
| TC-EXM-03-U06 | `lookup_grade(45, 50, GS1)` | 90 percent, A+ (max-marks agnostic) | passing |
| TC-EXM-03-U07 | `lookup_grade(101, 100, GS1)` | No band covers 101: fallback lowest band F | passing |
| TC-EXM-03-U08 | `lookup_grade(5, 0, GS1)` | None | passing |
| TC-EXM-03-U09 | `lookup_grade(50, 100, [])` | None | passing |
| TC-EXM-03-U10 | Overlapping bands A 80-100, B 70-85; `lookup_grade(82, 100, bands)` | A | passing |
| TC-EXM-03-U11 | Single band 0-100 pass; `lookup_grade(0, 100, bands)` | That band | passing |
| TC-EXM-03-U12 | `lookup_grade` with Decimal inputs `Decimal("62.5")`, `Decimal("100")` and bands as objects with Decimal percents | C (62.5 within 60-69.99) | passing |
| TC-EXM-03-U13 | `ABSENT_GRADE` constant | label `ABS`, gpa 0.0, remarks `Absent`, `is_pass` False | passing |
| TC-EXM-03-U14 | `GradeBandBase(from_percent=60, to_percent=50, ...)` | Validation error "from_percent must be <= to_percent" | passing |
| TC-EXM-03-U15 | `GradeBandBase` with `from_percent=-0.01`, `to_percent=100.01`, grade label of 11 characters, gpa -1 | Each raises validation error | passing |
| TC-EXM-03-U16 | `GradeBandBase(from_percent=0, to_percent=100, grade_label="A")` | Valid; gpa 0.00, `is_pass` true, sort_order 0 | passing |
| TC-EXM-03-U17 | Web `gradeBandSchema` with from 60 to 50; gpa 11 | Both fail; gpa 10 passes | passing |
| TC-EXM-03-U18 | Web `gradeSchemeSchema` with empty `bands` or empty name | Fails ("At least one grade band required", "Name is required") | passing |
| TC-EXM-03-A01 | POST scheme GS1 with six bands (ADMIN) | 201; bands returned with ids, percents and gpa as numbers | passing |
| TC-EXM-03-A02 | POST same name again | 400 `Exam grade scheme 'QA Standard' already exists` | passing |
| TC-EXM-03-A03 | POST with a band `from_percent` 60 `to_percent` 50 | 422 | passing |
| TC-EXM-03-A04 | POST bands with percent 100.01, -1, grade_label of 11 chars, gpa -0.5 (parametrised) | 422 each | passing |
| TC-EXM-03-A05 | POST with empty `bands` | 201 with `bands` empty (backend allows) | passing |
| TC-EXM-03-A06 | POST band boundaries 0 and 100 exactly | 201 | passing |
| TC-EXM-03-A07 | GET list contains the scheme; GET one by id | 200 each, bands present | passing |
| TC-EXM-03-A08 | GET unknown id | 404 `ExamGradeScheme with id ... not found` | passing |
| TC-EXM-03-A09 | PUT with new name, two bands | 200; old bands gone; only two bands returned | known defect: DEF-EXM-2: PUT /grade-schemes/{kind}/{id} response returns the stale band list instead of the replaced bands |
| TC-EXM-03-A10 | PUT keeping the same name | 200 (no duplicate check when unchanged) | passing |
| TC-EXM-03-A11 | PUT renaming to another existing scheme's name | 400 | passing |
| TC-EXM-03-A12 | PUT unknown id | 404 | passing |
| TC-EXM-03-A13 | DELETE unused scheme then GET | 204 then 404 | passing |
| TC-EXM-03-A14 | DELETE scheme referenced by exam EX1 | 409 | passing |
| TC-EXM-03-A15 | DELETE unknown id | 404 | passing |
| TC-EXM-03-A16 | POST, PUT, DELETE as TEACHER, STAFF, STUDENT, PARENT (parametrised) | 403 each | passing |
| TC-EXM-03-A17 | GET list and GET one as all five roles | 200 for all | passing |
| TC-EXM-03-A18 | All five endpoints with NOAUTH | 401 each | passing |
| TC-EXM-03-A19 | Tenant isolation: scheme created in tenant A, tenant B lists and GETs it | List excludes it; GET 404 | passing |
| TC-EXM-03-A20 | Same scheme name created in tenant A and B | Both 201 (name unique per tenant) | passing |
| TC-EXM-03-A21 | Token A with `cschema` of tenant B on POST | 403 | passing |
| TC-EXM-03-A22 | Create two schemes both `is_default=true` | Both 201 (no exclusivity) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-03-E01 | P1 | Web | Admin | No exam grade scheme named "QA Standard" exists. | 1. Sign in as Admin.<br>2. Open Exam > Grading.<br>3. Click "Open" on "Exam Grade Schemes".<br>4. Click "New Scheme".<br>5. Enter "Scheme Name" "QA Standard".<br>6. Click "Add Band" six times and fill the rows: A+ 90-100 gpa 4 Pass; A 80-89.99 gpa 3.5; B 70-79.99 gpa 3; C 60-69.99 gpa 2; D 35-59.99 gpa 1; F 0-34.99 gpa 0 with "Pass?" unticked.<br>7. Click "Save Scheme". | Toast "Exam grade scheme created successfully"; row "QA Standard" with "6 bands". This is fixture GS1 used by later cases. | planned |
| TC-EXM-03-E02 | P2 | Web | Admin | TC-EXM-03-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Exam Grade Schemes.<br>3. Click the "QA Standard" row. | Read-only band table with From %, To %, Grade, GPA, Remarks and Pass or Fail badges matching GS1. The seeded "Standard Percentage Grading" row shows 7 bands, A+ to E. | planned |
| TC-EXM-03-E03 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Exam Grade Schemes.<br>3. Click "New Scheme".<br>4. Enter "Scheme Name" "QA Doc Empty" and add no band.<br>5. Click "Save Scheme". | The dialog shows "No grade bands defined." and the inline error "At least one grade band required"; no request is sent. | planned |
| TC-EXM-03-E04 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Exam Grade Schemes.<br>3. Click "New Scheme", enter name "QA Doc Range".<br>4. Click "Add Band", enter "From %" 60 and "To %" 50, Grade "X".<br>5. Click "Save Scheme". | Inline "From percent must be <= to percent"; nothing saved. | planned |
| TC-EXM-03-E05 | P2 | Web | Admin | TC-EXM-03-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Exam Grade Schemes.<br>3. Click the Edit icon on "QA Standard".<br>4. Change the GPA of band B to 3.2.<br>5. Click "Save Scheme".<br>6. Expand the row. | Toast "Exam grade scheme updated successfully"; the expanded row shows GPA 3.20 for B (the list is re-fetched; the PUT response itself is stale, DEF-EXM-2). Restore 3.0 afterwards. | planned |
| TC-EXM-03-E06 | P3 | Web | Admin | Seeded scheme "Standard Percentage Grading" (used by the seeded exams). | 1. Sign in as Admin.<br>2. Open Exam > Grading > Exam Grade Schemes.<br>3. Click the trash icon on "Standard Percentage Grading".<br>4. Click "Delete" in "Delete Grade Scheme?". | Error toast "ExamGradeScheme <id> is referenced by one or more exams and cannot be deleted."; the scheme remains. | planned |
| TC-EXM-03-E07 | P2 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Create scheme "QA Doc Temp" with one band 0-100 Pass.<br>3. Click its trash icon.<br>4. Click "Delete" in "Delete Grade Scheme?". | Toast "Grade scheme deleted"; row gone. | planned |
| TC-EXM-03-E08 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Exam Grade Schemes > "New Scheme".<br>3. Enter name "QA Doc Order", add bands A 50-100 and F 0-49.99.<br>4. Drag band F above band A by the grip handle.<br>5. Click "Save Scheme" and expand the row. | The rows swap while dragging; the saved sort order follows the new order. Delete "QA Doc Order" afterwards. | planned |
| TC-EXM-03-E09 | P2 | Web | Admin | Seeded grading data: 1 exam grade scheme, 1 subject grade scheme ("Subject Grading"), 1 remark set ("Co-Scholastic Grading"), plus any QA items. | 1. Sign in as Admin.<br>2. Open Exam > Grading. | Three stat counts (Exam Grade Schemes, Subject Grade Schemes, Remark Grade Sets) equal the row counts of the three list pages; three "Open" cards. | planned |
| TC-EXM-03-E10 | P1 | Mobile | Admin | No scheme named "QA Mobile Scheme". | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading".<br>3. Tap "Exam Grade Schemes".<br>4. Tap "New Scheme".<br>5. Enter "Name *" "QA Mobile Scheme"; tap "Add Band" and enter Grade Label "P", From % 0, To % 100, GPA 1.<br>6. Save. | Toast "Created"; a "QA Mobile Scheme" card is listed. Delete it in TC-EXM-03-E13. | planned |
| TC-EXM-03-E11 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Exam Grade Schemes" > "New Scheme".<br>3. Save with an empty name.<br>4. Enter name "QA Doc Empty", remove all bands, save again. | Toasts "Name is required." and then "At least one grade band required."; nothing saved. | planned |
| TC-EXM-03-E12 | P3 | Mobile | Admin | TC-EXM-03-E10 done. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Exam Grade Schemes".<br>3. Edit "QA Mobile Scheme".<br>4. Toggle the band PASS control to FAIL.<br>5. Save. | Toast "Updated"; the band shows a Fail badge. | planned |
| TC-EXM-03-E13 | P2 | Mobile | Admin | TC-EXM-03-E10 done. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Exam Grade Schemes".<br>3. Tap delete on "QA Mobile Scheme".<br>4. Confirm "Delete Scheme". | Toast "Deleted"; card gone. | planned |
| TC-EXM-03-E14 | P3 | Mobile | Teacher | None. | 1. Sign in as Teacher.<br>2. Open the Exam tab. | No "Grading" tile. In-app navigation to /exam/grade-schemes redirects to /exam/list. | planned |

API tests implemented in: `backend/tests/api/exam/test_f03_f05_grading.py`

Implemented in: backend/tests/unit/exam/test_settings_boards_grading.py (U01-U16); web/src/__tests__/exam/examSchemas.test.ts (U17-U18).

---

## F04 Subject grade schemes

**Purpose.** Admin defines per-subject percentage bands, assigned to individual subjects when configuring an exam, so a subject can be graded and passed differently from the exam total.

**Roles and permissions.**
- Same as F03 (`exams:create/read/update/delete`). Menu: Exam > Grading > "Subject Grade Schemes". Mobile screen admin only.

**Preconditions.**
- None to create. To take effect, a scheme must be assigned to a subject in the create-exam wizard (F06) or through the subject-config update (F07).

**Steps, web.**
1. Exam > Grading > "Subject Grade Schemes" (`/exam/grading/subject-schemes`). Title "Subject Grade Schemes", subtitle "Per-subject grade calculation with pass thresholds".
2. "New Scheme": dialog "Create Subject Grade Scheme" with the same fields as F03 (placeholder name "Science Grading"). Save toast "Subject grade scheme created successfully"; update "Subject grade scheme updated successfully"; delete confirm "Delete Subject Grade Scheme?" then toast "Subject grade scheme deleted".

**Steps, mobile.**
1. Exam tab > "Grading" > "Subject Grade Schemes" (title "Subject Grade Schemes"), same modal and validation as F03 (name placeholder "e.g. Science Grading").

**Expected results.**
- Rows in `subject_grade_schemes` and `subject_grade_bands`.
- During compute (F15), a subject whose config has a `subject_grade_scheme_id` with bands is graded with those bands; otherwise with the exam scheme bands.

**API endpoints.**
- `POST /grade-schemes/subject`, `GET /grade-schemes/subject`, `GET /grade-schemes/subject/{scheme_id}`, `PUT /grade-schemes/subject/{scheme_id}`, `DELETE /grade-schemes/subject/{scheme_id}`. Same body and band rules as F03.

**Rules and validations.**
- Name unique per tenant (400 `Subject grade scheme '<name>' already exists`).
- Delete has no in-use check: deleting a scheme referenced by an exam subject config fails on the foreign key and returns 500 `An error occurred while deleting the subject grade scheme.` (KG-12).
- Same lookup algorithm and gap behaviour as F03.

**Error and edge cases.**
- Subject scheme referenced by a config but with no bands: compute falls back to the exam bands (empty list is falsy).
- A scheme with a lower pass threshold than the exam scheme changes only that subject's pass or fail.

**Unit-testable logic.**
- Subject-or-exam band selection (`subject_bands or exam_bands`) used by compute; `lookup_grade` tests in F03 apply.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-04-U01 | Select bands: subject bands non-empty, exam bands non-empty | Subject bands used | passing |
| TC-EXM-04-U02 | Subject bands empty list, exam bands non-empty | Exam bands used | passing |
| TC-EXM-04-U03 | Subject scheme "Pass at 33": bands F 0-32.99 fail, P 33-100 pass; `lookup_grade(33, 100, bands)` | P, pass (the same 33 percent would be F, fail, under GS1, whose lowest passing band starts at 35) | passing |
| TC-EXM-04-U04 | `lookup_grade(32.99, 100, subject bands)` | F, fail | passing |
| TC-EXM-04-A01 | POST valid subject scheme (ADMIN) | 201 with bands | passing |
| TC-EXM-04-A02 | POST duplicate name | 400 `Subject grade scheme '<name>' already exists` | passing |
| TC-EXM-04-A03 | POST band with `from_percent` greater than `to_percent` | 422 | passing |
| TC-EXM-04-A04 | Same name as an exam grade scheme | 201 (separate table; names independent) | passing |
| TC-EXM-04-A05 | GET list and GET one | 200; unknown id 404 | passing |
| TC-EXM-04-A06 | PUT with new bands | 200; bands replaced | passing |
| TC-EXM-04-A07 | PUT rename to existing name | 400 | passing |
| TC-EXM-04-A08 | PUT unknown id | 404 | passing |
| TC-EXM-04-A09 | DELETE unused scheme | 204; then 404 | passing |
| TC-EXM-04-A10 | DELETE scheme assigned to a subject config of EX1 | 500 `An error occurred while deleting the subject grade scheme.` (KG-12; target behaviour 409) | known defect: KG-12: DELETE /grade-schemes/subject/{id} on a scheme assigned to an exam subject config returns 500 instead o... |
| TC-EXM-04-A11 | DELETE unknown id | 404 | passing |
| TC-EXM-04-A12 | Create, update, delete as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-04-A13 | Read endpoints as all five roles | 200 | passing |
| TC-EXM-04-A14 | All endpoints with NOAUTH | 401 | passing |
| TC-EXM-04-A15 | Tenant isolation (tenant B cannot list or GET tenant A's scheme) and `cschema` mismatch | List excludes; GET 404; mismatch 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-04-E01 | P1 | Web | Admin | No subject grade scheme named "QA Science Grading". | 1. Sign in as Admin.<br>2. Open Exam > Grading > "Subject Grade Schemes" ("Open").<br>3. Click "New Scheme".<br>4. Enter name "QA Science Grading".<br>5. Add bands F 0-32.99 (Pass? unticked) and P 33-100 (Pass? ticked).<br>6. Click "Save Scheme". | Toast "Subject grade scheme created successfully"; row "QA Science Grading" with "2 bands". | planned |
| TC-EXM-04-E02 | P2 | Web | Admin | TC-EXM-04-E01 done; scheme not assigned to any exam subject. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Subject Grade Schemes.<br>3. Edit "QA Science Grading", change band P GPA to 2, "Save Scheme".<br>4. Click the trash icon on the row and click "Delete" in "Delete Subject Grade Scheme?". | Toast "Subject grade scheme updated successfully", then "Subject grade scheme deleted"; row gone. | planned |
| TC-EXM-04-E03 | P3 | Web | Admin | Seeded subject scheme "Subject Grading" (assigned to subjects of the seeded exams). | 1. Sign in as Admin.<br>2. Open Exam > Grading > Subject Grade Schemes.<br>3. Click the trash icon on "Subject Grading".<br>4. Click "Delete" in "Delete Subject Grade Scheme?". | Error toast "An error occurred while deleting the subject grade scheme." (KG-12; target a 409 in-use message); the scheme remains. | planned |
| TC-EXM-04-E04 | P2 | Web | Admin | TC-EXM-04-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Exams > "Create Exam".<br>3. Fill Section 1 and select one class-section in Section 2.<br>4. In Section 3 open a subject row and open its "Grade Scheme" select. | "QA Science Grading" and the seeded "Subject Grading" are options next to "Default". Click "Cancel" to clear the wizard. | planned |
| TC-EXM-04-E05 | P2 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Subject Grade Schemes".<br>3. Tap "New Scheme", enter name "QA Mobile Subject", one band P 0-100.<br>4. Save. | Toast "Created"; card listed. Delete it afterwards. | planned |
| TC-EXM-04-E06 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Subject Grade Schemes" > "New Scheme".<br>3. Enter name "QA Doc Empty", remove all bands, save. | Toast "At least one grade band required."; nothing saved. | planned |

API tests implemented in: `backend/tests/api/exam/test_f03_f05_grading.py`

Implemented in: backend/tests/unit/exam/test_settings_boards_grading.py.

---

## F05 Remark grade sets

**Purpose.** Admin defines named sets of descriptive grades (letter plus label, for example A = Excellent) used by mark components whose entry type is "remarks".

**Roles and permissions.**
- Create `exams:create`, read `exams:read`, update `exams:update`, delete `exams:delete`. Menu: Exam > Grading > "Remark Grade Sets". Mobile screen admin only.

**Preconditions.**
- None.

**Steps, web.**
1. Exam > Grading > "Remark Grade Sets" (`/exam/grading/remarks`). Search "Search set name...". Empty state "No remark grade sets yet" with "Create First Set".
2. "New Set": dialog "Create Remark Grade Set": "Set Name *" (placeholder "Primary Remarks Set"), "Grade Options *" with "Grade Letter" (max 5) and "Label" per row, "Add Option", up and down arrows or drag to reorder, X to remove. A new set starts with one row (A, Excellent).
3. "Save Set". Toasts "Remark grade set created successfully", "Remark grade set updated successfully", "Remark grade set deleted". Delete confirm "Delete Remark Grade Set?".
4. Rows show up to four option badges ("A: Excellent") and "+N more"; expand for the table Grade Letter, Label, Order.

**Steps, mobile.**
1. Exam tab > "Grading" > "Remark Grade Sets". "New Set" modal with "Set Name *", options (letter, label), "Add Option". Validation toasts "Name is required" and "At least one grade option is required". Toasts "Remark set created", "Remark set updated", "Remark set deleted". Delete confirm title "Delete".

**Expected results.**
- Rows in `remark_grade_sets` and `remark_grade_options`. A set can be chosen by a remarks-type component when configuring an exam (F06); web and mobile mark entry have no picker for it (KG-6).

**API endpoints.**
- `POST /remark-grades` (`name` max 100, `options[]` with `grade_letter` max 5, `label` max 50, `sort_order`), `GET /remark-grades`, `GET /remark-grades/{set_id}`, `PUT /remark-grades/{set_id}` (`name` optional, `options` optional: when present replaces all), `DELETE /remark-grades/{set_id}`.

**Rules and validations.**
- Name unique per tenant (400 `Remark grade set '<name>' already exists`).
- Delete cascades options but has no in-use check: a set used by exam components fails on the foreign key with 500 (KG-12).
- Web allows labels up to 100 characters but the backend limit is 50: 51-100 characters give 422 (KG-12).
- `PUT` with `name` null keeps the name; with `options` null keeps options.

**Error and edge cases.**
- Empty `options`: backend accepts it (clients require one).
- Letter of 6 characters: 422.

**Unit-testable logic.**
- `RemarkGradeSetCreate`, `RemarkGradeOptionCreate` bounds; `update_remark_grade_set` partial semantics; web `remarkGradeSetSchema`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-05-U01 | `RemarkGradeOptionCreate(grade_letter="ABCDE", label="x")` and `"ABCDEF"` | 5 characters valid; 6 invalid | passing |
| TC-EXM-05-U02 | `RemarkGradeOptionCreate` label of 50 and 51 characters | 50 valid; 51 invalid | passing |
| TC-EXM-05-U03 | `RemarkGradeSetCreate(name="")` / name of 101 chars | 101 invalid; empty string valid at backend (client rejects) | passing |
| TC-EXM-05-U04 | `update_remark_grade_set` with `options=None` | Options unchanged | passing |
| TC-EXM-05-U05 | `update_remark_grade_set` with `options=[]` | All options removed | passing |
| TC-EXM-05-U06 | Web `remarkGradeSetSchema` with no options; label 101 chars | Both fail | passing |
| TC-EXM-05-A01 | POST set "Primary Remarks" with options A Excellent, B Good (ADMIN) | 201; options have ids and `set_id` | passing |
| TC-EXM-05-A02 | POST duplicate name | 400 | passing |
| TC-EXM-05-A03 | POST option label of 51 characters; letter of 6 characters | 422 each | passing |
| TC-EXM-05-A04 | POST with empty options | 201 | passing |
| TC-EXM-05-A05 | GET list and GET one; unknown id | 200; 404 | passing |
| TC-EXM-05-A06 | PUT rename only | 200; options unchanged | passing |
| TC-EXM-05-A07 | PUT with new options | 200; old options replaced | known defect: DEF-EXM-3: PUT /remark-grades/{id} response returns the stale options instead of the replaced list |
| TC-EXM-05-A08 | PUT renaming to another set's name | 400 | passing |
| TC-EXM-05-A09 | DELETE unused set then GET | 204 then 404 | passing |
| TC-EXM-05-A10 | DELETE set used by a remarks component | 500 (KG-12; target 409) | known defect: KG-12: DELETE /remark-grades/{id} on a set used by an exam component returns 500 instead of 409 |
| TC-EXM-05-A11 | Create, update, delete as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-05-A12 | Read endpoints as all five roles | 200 | passing |
| TC-EXM-05-A13 | All endpoints with NOAUTH | 401 | passing |
| TC-EXM-05-A14 | Tenant isolation and `cschema` mismatch | Other tenant sees nothing; mismatch 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-05-E01 | P1 | Web | Admin | Seeded set "Co-Scholastic Grading" (A to D) exists; no set named "QA Primary Remarks". | 1. Sign in as Admin.<br>2. Open Exam > Grading > "Remark Grade Sets" ("Open").<br>3. Click "New Set".<br>4. Enter "Set Name *" "QA Primary Remarks".<br>5. Keep the first option A / Excellent; click "Add Option" and enter B / Good.<br>6. Click "Save Set". | Toast "Remark grade set created successfully"; the new row shows badges "A: Excellent" and "B: Good" next to the seeded "Co-Scholastic Grading" row. | planned |
| TC-EXM-05-E02 | P3 | Web | Admin | TC-EXM-05-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Remark Grade Sets.<br>3. Edit "QA Primary Remarks".<br>4. Move option B above A with the up arrow.<br>5. Click "Save Set" and expand the row. | Toast "Remark grade set updated successfully"; the expanded table (Grade Letter, Label, Order) lists B first. | planned |
| TC-EXM-05-E03 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Remark Grade Sets > "New Set".<br>3. Enter name "QA Doc Empty" and remove the only option row.<br>4. Click "Save Set". | Inline error "At least one option required"; nothing saved. | planned |
| TC-EXM-05-E04 | P2 | Web | Admin | TC-EXM-05-E01 done; set not used by any exam component. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Remark Grade Sets.<br>3. Click the trash icon on "QA Primary Remarks".<br>4. Click "Delete" in "Delete Remark Grade Set?". | Toast "Remark grade set deleted"; empty state "No remark grade sets yet" if no set remains. | planned |
| TC-EXM-05-E05 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Grading > Remark Grade Sets > "New Set".<br>3. Enter name "QA Doc Long" and a label of 60 characters for option A.<br>4. Click "Save Set". | Error toast from the backend (422, label limit 50; web allows 100, KG-12); nothing saved. | planned |
| TC-EXM-05-E06 | P2 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Remark Grade Sets".<br>3. Tap "New Set", enter "Set Name *" "QA Mobile Remarks", option A Excellent.<br>4. Save. | Toast "Remark set created"; card listed. | planned |
| TC-EXM-05-E07 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Remark Grade Sets" > "New Set".<br>3. Leave the name empty and save. | Toast "Name is required"; nothing saved. | planned |
| TC-EXM-05-E08 | P2 | Mobile | Admin | TC-EXM-05-E06 done. | 1. Sign in as Admin.<br>2. Open Exam tab > "Grading" > "Remark Grade Sets".<br>3. Tap delete on "QA Mobile Remarks" and confirm "Delete". | Toast "Remark set deleted"; card gone. | planned |

API tests implemented in: `backend/tests/api/exam/test_f03_f05_grading.py`

Implemented in: backend/tests/unit/exam/test_settings_boards_grading.py (U01-U05); web/src/__tests__/exam/examSchemas.test.ts (U06).

---

## F06 Create exam, list and view exams

**Purpose.** Admin creates an exam for one or more class-sections in one operation: header details, class-sections, subjects with mark components and max marks, and optional dates. Everyone with read access can list and open exams.

**Roles and permissions.**
- Create: `exams:create`. List and view: `exams:read`.
- Menu: Exam > Exams (all roles). "Create Exam" and "New Exam" are shown only to admin role names (web and mobile), and the web route `/exam/exams/create` redirects other roles to `/exam/exams`.

**Preconditions.**
- An academic year exists and is selected (web reads the selected academic year, mobile has an "Academic Year" select).
- Classes, sections, subjects and class-subject mappings exist (Masters). Only subjects mapped to the class-section with `exclude_marks` false can be configured.
- At least one exam grade scheme (F03) is needed for the web "Create Exam" button on the Exams page to be enabled. Subject grade schemes (F04) and remark sets (F05) are optional.

**Steps, web.**
1. Exam > Exams (`/exam/exams`, title "Exam Management", subtitle "Manage all examinations for the academic year"). Click "Create Exam" (disabled with a banner "Setup required: Configure at least one Exam Grade Scheme before creating exams." when no scheme exists). The dashboard (`/exam`) has a "New Exam" button as well.
2. Page "Create Exam", subtitle "Set up a new examination", five tabs "1 Exam Details", "2 Class & Sections", "3 Subject Configuration", "4 Exam Dates", "5 Review & Submit"; the footer always shows "Cancel", "Fix N issues before submitting" and "Create Exam". Section 1 "Exam Details": "Exam Name *", "Board *" (CBSE, ICSE, State, BTech, Custom), "Custom Board Name *" (Custom only), "Nature *" (Formative, Summative, Cumulative, Custom), "Academic Year *" (read-only, taken from the selected year), "Exam Grade Scheme", "Subject Grade Scheme", "Mark Entry Deadline", "Min Attendance %", "Attendance From", "Attendance To". Button "Next: Class & Sections".
   - There is no Level control: the form default `primary` is always sent (KG-9). `exam_type` is not shown; it is set equal to the exam name, so a name over 50 characters fails.
3. Section 2 "Class & Sections": multi-select "Type to search and select class-sections..." (one option per class-section, or per class when it has no sections). Button "Next: Subject Config" (disabled with nothing selected).
4. Section 3 "Subject Configuration": one tab per selected class-section. Each subject mapped to the class (excluding `exclude_marks`) is an accordion row with "Grade Scheme" (Default or a subject scheme), "Mark Components" table: "Component" (placeholder "Written"), "Type" (Marks or Remarks), "Max Marks" (or a remark-set select "Select set..."), "Min Pass", "In Total" checkbox, "Add Component", trash. Helpers: "Set all max marks:" with "Apply", "Apply same marks to all subjects in this class", "Copy this config to other class(es)". "Grand Total Marks" shows the sum of included marks components. Button "Next: Exam Dates (Optional)".
5. Section 4 "Exam Dates": choose one or more class-sections (checkboxes), "Subject", "Date", "Start Time", "End Time", "Add". Skippable. Button "Review & Submit".
6. Section 5 "Review & Submit": summaries with "Edit" links; a red "Missing required information" box lists Exam Name, Academic Year, Class & Sections, Subject Configuration when missing.
7. Click "Create Exam" (disabled while items are missing). Overlay "Creating exam..." then toast "Exam created successfully" and navigation to `/exam/exams`. "Cancel" clears the wizard.
8. Client rules on submit: every component needs a name; marks components need Max Marks > 0; blank subject configs and configs of deselected class-sections are dropped; at least one configured subject. Wizard state is kept in sessionStorage (`exam-store`).

**Steps, mobile.**
1. Exam tab > "Create Exam" tile or "New Exam" (admin only; other roles are redirected). Screen "Create Exam" (link "Back to Exams") with accordion sections: 1 "Exam Details" (Exam Name, Board, Level, Exam Type, Nature, Academic Year, Grade Scheme, Mark Entry Deadline, Min Attendance %, Attendance From, Attendance To), 2 class-sections, 3 subject components (Grade Scheme, Credit Hours, Component, Type, Max Marks, Min Pass, Remark Set, "Add Component", "Apply same marks to all subjects in this class"), 4 "Add Exam Date" (Class-Section, Subject, Date, Start Time, End Time, Venue), 5 review ("Missing required information" box).
2. Bottom bar "Cancel", "Fix N issues in Review section" and "Create Exam" ("Creating..."). Missing items toast "Fix Issues" with the first missing item (Exam Name, Academic Year, Exam Type, class-sections, subject configuration).
3. On success toast "Exam Created" and the app navigates to `/exam/<id>` using `res.id`, but the API returns `exam_id`, so the detail screen opens with id `undefined` and shows "Failed to load exam" (KG-8).
4. Exams list: Exam > Exams (mobile "Exams" tile `/exam/list`) with search, "All Status" and "All Nature" filters, cards with Board, Type, Level, Subjects, Nature, Deadline, status pill; admin roles get "Edit" on every card and "Delete" on draft cards. Student and Parent see the list titled "My Exams" (status filter only) and open `/exam/my-marks/<id>` from it instead of the detail screen.

**Expected results.**
- Rows in `exams` (status `active`), `exam_class_sections`, `exam_subject_config`, `exam_subject_components`, `exam_dates` in one transaction. Either everything is saved or nothing.
- List shows the exam with `subject_config_count`; detail screens show class-sections, configured subjects and dates (names resolved from Masters because the exam endpoints return ids only).

**API endpoints.**
- `POST /exams`: `ExamCreateFull`.
  - `exam`: `exam_name` (max 150), `board` (string max 50), `custom_board_name`, `level` (enum pre_primary, primary, upper_primary, secondary, inter, diploma, btech, mtech, iit, others), `exam_type` (max 50), `nature` (default formative), `is_internal`, `weightage_percent`, `academic_year_id`, `exam_grade_scheme_id`, `mark_entry_deadline`, `hall_ticket_min_attendance` (0-100), `attendance_from_date`, `attendance_to_date`, `attendance_mode` (max 20), `term` (max 20).
  - `class_sections[]` (min 1): `class_id`, `section_id` (null means all sections of the class).
  - `subject_configs[]` (min 1): `class_id`, `section_id`, `subject_id`, `subject_grade_scheme_id`, `credit_hours`, split fields, `sort_order`, `components[]` (min 1): `component_name` (max 100), `entry_type` (marks or remarks), `max_marks` (>= 0, required for marks), `min_pass_marks` (>= 0), `include_in_total`, `is_internal`, `remark_grade_set_id` (required for remarks), `sort_order`.
  - `exam_dates[]` (optional): `class_id`, `section_id`, `subject_id`, `exam_date`, `start_time`, `end_time`, `venue` (max 100), `notes` (max 300).
  - 201 `{exam_id, exam_name, status:"active", class_sections_created, subject_configs_created, exam_dates_created}`.
- `GET /exams` query `academic_year_id`, `exam_status`, `nature`: bare array of `ExamListItem` (id, exam_name, board, level, exam_type, nature, status, academic_year_id, mark_entry_deadline, hall_ticket_min_attendance, attendance dates, publish_rank, term, created_at, subject_config_count), newest first.
- `GET /exams/{exam_id}`: `ExamRead` (adds hall_ticket_published, hall_ticket_published_at, cloned_from_exam_id, created_by, updated_at). 404 `Exam <id> not found`.

**Rules and validations.**
- The exam is created `active` regardless of anything in the payload (`status` is not part of the schema).
- Every `subject_config.class_id` must appear in `class_sections` (422).
- Every subject must be mapped to that (class, section) in `class_subject_map` with `exclude_marks` false, or to (class, null section) (422 `Subject <id> is not mapped to class ... or has exclude_marks=true`).
- Component rules: marks type needs `max_marks` (422 `max_marks is required when entry_type='marks'`); remarks type needs `remark_grade_set_id` (422). `max_marks` 0 is accepted by the API (web requires > 0). Component `sort_order` is the given value when non-zero, otherwise the component's position in the list.
- Name unique per academic year: 409 `An exam named '<name>' already exists for this academic year.`
- A foreign key failure (unknown academic year, grade scheme, remark set, subject grade scheme) returns 409 `The request conflicts with existing data` (the database message is only logged). Duplicate (class, section, subject) dates inside the payload also return 409.
- `exam_type`, `board`, `level` are plain strings on the exam; no link to board patterns (F02).
- Exam dates are not validated against subject configs or class-sections.
- Total max marks of a class-section = sum of `max_marks` of components with `include_in_total` true and entry type marks. Example EX1: Math 80 + 20, Science 100, English 100 gives 300.

**Error and edge cases.**
- Empty `class_sections`, empty `subject_configs`, a config with no components: 422.
- Extra fields in the payload (for example the web's `exam.subject_grade_scheme_id` and `status`) are ignored.
- Student or Parent calling `GET /exams`: allowed (they hold `exams:read`) and they see all exams of the tenant including drafts.
- Section-less class-sections (`section_id` null) can be created, but mark entry on them does not work in the UI (F11).

**Unit-testable logic.**
- `ComponentPayload` validator, `ExamCreateFull` class-membership validator, component sort-order rule.
- `create_full_exam` with a fake session: status `active`, counts, subject-mapping check (including the null-section slot).
- Web `examDetailsSchema`, `componentSchema`, `classSectionSchema`; web grand-total computation.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-06-U01 | `ComponentPayload(entry_type="marks", max_marks=None)` | ValueError `max_marks is required when entry_type='marks'` | passing |
| TC-EXM-06-U02 | `ComponentPayload(entry_type="remarks", remark_grade_set_id=None)` | ValueError (set required) | passing |
| TC-EXM-06-U03 | `ComponentPayload(entry_type="marks", max_marks=0)` and `max_marks=-1` | 0 valid; -1 invalid (ge=0) | passing |
| TC-EXM-06-U04 | `ComponentPayload(entry_type="remarks", remark_grade_set_id=<uuid>, max_marks=None)` | Valid | passing |
| TC-EXM-06-U05 | `ExamCreateFull` where a subject config uses a class not in `class_sections` | ValueError mentioning the class id | passing |
| TC-EXM-06-U06 | `ExamCreateFull` with empty `class_sections`; empty `subject_configs` | Both invalid (min length 1) | passing |
| TC-EXM-06-U07 | `ExamDetailsPayload(exam_name="x"*151)`, `exam_type="y"*51`, `hall_ticket_min_attendance=101` | Each invalid; 150, 50, 100 valid | passing |
| TC-EXM-06-U08 | `ExamDetailsPayload` with `nature` omitted and `level="kg"` | Default nature formative; level invalid | passing |
| TC-EXM-06-U09 | `create_full_exam` fake session: valid payload | Exam added with `status="active"`; response counts equal payload counts | passing |
| TC-EXM-06-U10 | `create_full_exam` with a subject missing from the loaded mapping | HTTPException 422 | passing |
| TC-EXM-06-U11 | `create_full_exam` with mapping stored under (class, None) only and config section None | Accepted (null-section slot) | passing |
| TC-EXM-06-U12 | Components with `sort_order` 0, 0, 5 | Stored sort orders 0, 1, 5 (zero replaced by index) | passing |
| TC-EXM-06-U13 | Grand total for EX1 (Math 80 included + 20 included, Science 100, English 100, one 10-mark component with `include_in_total=false`) | 300 | blocked: grandTotal is computed inline in web/src/pages/exam/CreateExam.tsx; needs a helper exported |
| TC-EXM-06-U14 | Web `examDetailsSchema` with board `Custom` and empty custom name | Fails with "Custom board name is required when board is Custom" | passing |
| TC-EXM-06-U15 | Web `componentSchema` marks type without max; remarks type without set | Both fail with the documented messages | passing |
| TC-EXM-06-U16 | Web `examDetailsSchema` exam name of 1 character | Fails ("at least 2 characters"); 2 characters passes | passing |
| TC-EXM-06-U17 | Web wizard drops blank configs and configs of deselected class-sections before submit | Only selected, filled configs remain | blocked: config filtering is inline in handleSubmit of web/src/pages/exam/CreateExam.tsx; needs a helper exported |
| TC-EXM-06-A01 | POST valid EX1 payload (3 subjects, 2 dates) as ADMIN | 201; `status` `active`; counts 1, 3, 2; GET `/exams/{id}` shows status `active` | passing |
| TC-EXM-06-A02 | POST the same `exam_name` in the same academic year | 409 `An exam named '<name>' already exists for this academic year.` | passing |
| TC-EXM-06-A03 | POST same name in a different academic year | 201 | passing |
| TC-EXM-06-A04 | POST with a subject not mapped to the class-section | 422 `Subject ... is not mapped ...`; nothing stored (GET `/exams` unchanged) | passing |
| TC-EXM-06-A05 | POST with a subject whose mapping has `exclude_marks=true` | 422 | passing |
| TC-EXM-06-A06 | POST with a subject_config class not in `class_sections` | 422 | passing |
| TC-EXM-06-A07 | POST marks component without `max_marks`; remarks component without set (parametrised) | 422 each | passing |
| TC-EXM-06-A08 | POST component `max_marks` -1 | 422 | passing |
| TC-EXM-06-A09 | POST component `max_marks` 0 | 201 (accepted; it adds nothing to totals) | passing |
| TC-EXM-06-A10 | POST empty `class_sections`, empty `subject_configs`, empty `components` (parametrised) | 422 each | passing |
| TC-EXM-06-A11 | POST `exam_name` 150 and 151 characters | 201 / 422 | passing |
| TC-EXM-06-A12 | POST invalid `nature` and invalid `level` | 422 each | passing |
| TC-EXM-06-A13 | POST `hall_ticket_min_attendance` 100 and 101 | 201 / 422 | passing |
| TC-EXM-06-A14 | POST with a random `academic_year_id` | 409 (foreign key; raw message) | passing |
| TC-EXM-06-A15 | POST with duplicate date rows (same class, section, subject) | 409; exam not created | passing |
| TC-EXM-06-A16 | POST with a remarks component using a valid remark set | 201; component stored with `remark_grade_set_id` | passing |
| TC-EXM-06-A17 | POST with `class_sections` containing a null section | 201; stored with null section | passing |
| TC-EXM-06-A18 | POST with extra unknown fields (`exam.status="published"`, `exam.subject_grade_scheme_id`) | 201; status still `active` | passing |
| TC-EXM-06-A19 | POST as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-06-A20 | GET `/exams` filters: `academic_year_id`, `exam_status=active`, `nature=formative`, combined, and a non-matching value | Matching exams only; non-matching returns `[]`; newest first | passing |
| TC-EXM-06-A21 | GET `/exams` response shape | Bare array; item has `subject_config_count` equal to the number of configs | passing |
| TC-EXM-06-A22 | GET `/exams/{id}` and unknown id | 200 with `ExamRead` fields (hall_ticket_published false, cloned_from_exam_id null); 404 `Exam <id> not found` | passing |
| TC-EXM-06-A23 | GET list and GET one as TEACHER, STAFF, STUDENT, PARENT | 200 each | passing |
| TC-EXM-06-A24 | POST `/exams`, GET `/exams`, GET `/exams/{id}` with NOAUTH | 401 each | passing |
| TC-EXM-06-A25 | Tenant isolation: exam created in tenant A; tenant B lists and GETs by id | List excludes it; GET 404 | passing |
| TC-EXM-06-A26 | Same `exam_name` and year pattern in tenant A and tenant B | Both 201 | passing |
| TC-EXM-06-A27 | Token A with `cschema` of tenant B on POST `/exams` | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-06-E01 | P1 | Web | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. Seeded scheme "Standard Percentage Grading". No exam named "QA FA1" in 2026-2027. | 1. Sign in as Admin.<br>2. Open Exam > Exams.<br>3. Click "Create Exam".<br>4. Section 1: "Exam Name *" "QA FA1", "Board *" State, "Nature *" Formative, "Exam Grade Scheme" "Standard Percentage Grading"; click "Next: Class & Sections".<br>5. Section 2: choose Class 1 / 1-B in "Type to search and select class-sections..."; click "Next: Subject Config".<br>6. Section 3: Mathematics components Written max 80 and Oral max 20; English Written 100; Environmental Studies Written 100; leave the other subjects blank; click "Next: Exam Dates (Optional)".<br>7. Click "Review & Submit".<br>8. Click "Create Exam". | Overlay "Creating exam..."; toast "Exam created successfully"; redirected to /exam/exams; "QA FA1" listed as Active with "3 subjects". Later UI cases call this exam QA FA1 (Grand Total 300; students Advik Mehta, Harsha Raju, Nikhil Krishnan). | planned |
| TC-EXM-06-E02 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Exams > "Create Exam".<br>3. Enter "Exam Name *" "Q".<br>4. Click "Next: Class & Sections". | Inline "Exam name must be at least 2 characters"; tab 1 stays open. | planned |
| TC-EXM-06-E03 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam > Exams > "Create Exam".<br>3. Enter name "QA Doc Board", choose "Board *" Custom, leave "Custom Board Name *" empty.<br>4. Click "Next: Class & Sections". | Inline "Custom board name is required when board is Custom". | planned |
| TC-EXM-06-E04 | P3 | Web | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. | 1. Sign in as Admin.<br>2. Start "Create Exam" with name "QA Doc Max" and one class-section.<br>3. In Section 3 add a Written component and leave "Max Marks" empty.<br>4. Click "Create Exam". | Toast starting "All marks-type components need a max marks value > 0" and tab 3 opens; nothing created. Click "Cancel". | planned |
| TC-EXM-06-E05 | P3 | Web | Admin | Wizard empty (click "Cancel" first if needed). | 1. Sign in as Admin.<br>2. Open "Create Exam", enter name "QA Doc Review".<br>3. Open tab "5 Review & Submit". | Red "Missing required information" box lists "Class & Sections - select at least one (Section 2)" and the subject configuration item; "Create Exam" is disabled and the footer reads "Fix N issues before submitting". | planned |
| TC-EXM-06-E06 | P2 | Web | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. | 1. Sign in as Admin.<br>2. Start "Create Exam" with one class-section.<br>3. In Section 3 enter 100 in "Set all max marks:" and click "Apply". | Every subject's first marks component shows 100; "Grand Total Marks" equals 100 times the number of configured subjects. | planned |
| TC-EXM-06-E07 | P2 | Web | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. | 1. Sign in as Admin.<br>2. Start "Create Exam" with Class 1 / 1-B.<br>3. Configure Mathematics with Written 80 and Oral 20.<br>4. Click "Apply same marks to all subjects in this class". | The other Class 1 subjects copy the Mathematics components (Written 80, Oral 20). | planned |
| TC-EXM-06-E08 | P2 | Web | Admin | Seeded Class 1 / 1-A and Class 1 / 1-B (same subjects). | 1. Sign in as Admin.<br>2. Start "Create Exam" and select both class-sections.<br>3. Configure the first class-section tab.<br>4. Click "Copy this config to other class(es)", select the second and confirm. | Toast "Config copied to 1 class-section(s)"; the second tab shows the same components. | planned |
| TC-EXM-06-E09 | P2 | Web | Admin | Seeded remark set "Co-Scholastic Grading". Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. | 1. Sign in as Admin.<br>2. Start "Create Exam" "QA Doc Remarks" with Class 1 / 1-B.<br>3. For English add a component "Conduct" with "Type" Remarks.<br>4. Choose "Co-Scholastic Grading" in "Select set...".<br>5. Complete and click "Create Exam". | The Max Marks input is replaced by the set select; the exam is created (toast "Exam created successfully"). Clean-up: Deactivate, then Delete "QA Doc Remarks". | planned |
| TC-EXM-06-E10 | P2 | Web | Admin | Seeded Class 1 / 1-A and Class 1 / 1-B. | 1. Sign in as Admin.<br>2. Start "Create Exam" "QA Doc Dates" with Class 1 / 1-A and 1-B and Mathematics configured for both.<br>3. In Section 4 tick both class-sections, choose "Subject" Mathematics, a "Date", "Start Time" 09:00, "End Time" 12:00, click "Add".<br>4. Click "Create Exam".<br>5. Open the new exam > "Dates". | Two date rows appear in Section 4; after creation the exam Dates tab lists both. | planned |
| TC-EXM-06-E11 | P3 | Web | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. | 1. Sign in as Admin.<br>2. Start "Create Exam", select Class 1 / 1-B and configure Mathematics.<br>3. Reload the browser page.<br>4. Click "Cancel".<br>5. Open "Create Exam" again. | After reload the class-section and Mathematics config are restored (sessionStorage "exam-store"); after "Cancel" the wizard is empty. | planned |
| TC-EXM-06-E12 | P3 | Web | Admin | Seeded exam "Half Yearly Examination 2026". | 1. Sign in as Admin.<br>2. Create an exam named "Half Yearly Examination 2026" for Class 1 / 1-B with one subject.<br>3. Click "Create Exam". | Error toast "An exam named 'Half Yearly Examination 2026' already exists for this academic year."; nothing created. | planned |
| TC-EXM-06-E13 | P3 | Web | Admin | A tenant with no exam grade scheme (qa_manual has one seeded). | 1. Sign in as Admin.<br>2. Open Exam > Exams. | "Create Exam" disabled; banner "Setup required: Configure at least one Exam Grade Scheme before creating exams." with link "Go to Grade Schemes". | planned |
| TC-EXM-06-E14 | P2 | Web | Teacher | None. | 1. Sign in as Teacher.<br>2. Open Exam > Exams.<br>3. Open /exam/exams/create in the address bar. | No "Create Exam" button and no Actions column on the list; the create URL redirects to /exam/exams. | planned |
| TC-EXM-06-E15 | P2 | Web | Admin | Seeded exams (two published Unit Tests, one active Half Yearly). | 1. Sign in as Admin.<br>2. Open Exam > Exams.<br>3. Choose "Active" in "All Status".<br>4. Choose "All Status" again and "Formative" in "All Nature".<br>5. Type "Unit Test" in "Search exams...".<br>6. Type "zzz". | Active shows "Half Yearly Examination 2026" (plus QA exams); Formative shows the two Unit Tests; the search keeps the two Unit Tests; "zzz" shows "No exams match your current filters." | planned |
| TC-EXM-06-E16 | P1 | Web | Admin | Seeded exams. | 1. Sign in as Admin.<br>2. Open Exam (dashboard /exam). | Title "Exam Management", "Academic Year: 2026-2027", quick links All Exams, Mark Entry, Results, Hall Tickets, Settings, button "New Exam"; counts Draft, Active, Locked, Published (at least 1 active and 2 published) match the Exams list; exams are grouped in status tables. | planned |
| TC-EXM-06-E17 | P1 | Web | Admin | Seeded exam "Unit Test 1 - Class 1B" (published). | 1. Sign in as Admin.<br>2. Open Exam > Exams.<br>3. Click the "Unit Test 1 - Class 1B" row. | Header with Published badge and "State . primary . Unit Test . formative"; tabs Overview, Dates, Marks, Permissions, Audit Log; cards Academic Year, Mark Entry Deadline, Hall Ticket Attendance, Attendance Period, Hall Ticket Status ("Not Published"); "Configured Subjects" lists English, Hindi, Telugu, Mathematics, Environmental Studies under Class 1 - 1-B. | planned |
| TC-EXM-06-E18 | P3 | Web | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. | 1. Sign in as Admin.<br>2. Create an exam whose name is 51 characters long ("QA " plus 48 letters) with one configured subject.<br>3. Click "Create Exam". | Creation fails with a validation error toast because exam_type (a copy of the name) exceeds 50 characters (KG-9). | planned |
| TC-EXM-06-E19 | P1 | Mobile | Admin | Seeded Class 1 / 1-B with students Advik Mehta (002), Harsha Raju (004), Nikhil Krishnan (007) and subjects Mathematics, English, Environmental Studies. Seeded scheme "Standard Percentage Grading". No exam "QA Mobile FA1". | 1. Sign in as Admin.<br>2. Open the Exam tab and tap "Create Exam".<br>3. Section 1: "Exam Name" "QA Mobile FA1", Board State, Level Primary, "Exam Type" "FA1", Nature Formative, Grade Scheme "Standard Percentage Grading".<br>4. Section 2: select Class 1 / 1-B.<br>5. Section 3: Mathematics Written 80 and Oral 20, English 100, Environmental Studies 100.<br>6. Tap "Create Exam". | Toast "Exam Created"; the exam is stored (visible in Exams). Navigation then opens /exam/undefined with "Failed to load exam" (KG-8). Delete or keep for F09 mobile cases. | planned |
| TC-EXM-06-E20 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Exam tab > "Create Exam".<br>3. Leave Exam Name empty and tap "Create Exam". | Toast "Fix Issues" with "Exam Name (Section 1)"; the footer reads "Fix N issues in Review section". | planned |
| TC-EXM-06-E21 | P2 | Mobile | Admin | Seeded exams plus at least one draft (for example "Copy of QA FA1" from TC-EXM-09-E05). | 1. Sign in as Admin.<br>2. Open Exam tab > "Exams".<br>3. Type "Unit" in "Search exams...".<br>4. Choose a value in "All Status", then in "All Nature". | Cards filter and the count "<n> exams" updates; every card has "Edit"; "Delete" only on draft cards. | planned |
| TC-EXM-06-E22 | P2 | Mobile | Student | Seeded student login Advik Mehta (002). | 1. Sign in as Advik Mehta (002).<br>2. Open the Exam tab.<br>3. Tap "Exams". | Hub shows a "MY EXAMS" card "My Marks" and tiles Exams, Hall Tickets, Results only (no Create Exam or admin tiles); the list is titled "My Exams" with only "All Status" and no Edit or Delete. | planned |
| TC-EXM-06-E23 | P3 | Mobile | Teacher | None. | 1. Sign in as Teacher.<br>2. Open the Exam tab.<br>3. Navigate in-app to /exam/create (for example from a saved link). | No "Create Exam" tile or "New Exam" button; /exam/create redirects to /exam/list. | planned |
| TC-EXM-06-E24 | P3 | Web | Admin | Seeded exam "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open the "Unit Test 1 - Class 1B" detail URL directly in a new browser tab. | Overview card "Academic Year" shows 2026-2027. Currently it shows a dash when the academic year list was not loaded first (KG-23). | blocked: KG-23 academic year not resolved on direct load |

API tests implemented in: `backend/tests/api/exam/test_f06_create_exam.py`

Implemented in: backend/tests/unit/exam/test_exam_create_status.py (U01-U12); web/src/__tests__/exam/examSchemas.test.ts (U14-U16). U13 and U17 blocked.

---

## F07 Class-sections, subject configs and config templates

**Purpose.** After creation, read an exam's class-sections and subject configs, add a class-section, adjust a subject config, and reuse configurations: save a class-section's configs as a template, copy configs between class-sections, apply a template, compare subjects and get copy suggestions.

**Roles and permissions.**
- Read endpoints: `exams:read`. Add class-section, create or save templates, copy, apply: `exams:create`. Update subject config, update template: `exams:update`. Delete template: `exams:delete`. Template list: `exams:list`.
- Web and mobile have no screen for the write operations (hooks and API functions only; the web hooks are `useAddExamClassSection`, `useUpdateExamSubjectConfig`, `useTemplates`, `useCopyPattern` and so on). The read endpoints feed the exam detail, marks summary and mark entry screens.

**Preconditions.**
- An exam exists (F06). For copy and apply, the target class-section must already belong to the exam and have no subject configs.

**Steps, web.**
1. Read only: Exam > Exams > open an exam. "Configured Subjects" lists subjects per class-section (from `class-sections` and `subject-configs`; names are resolved from Masters).
2. Adding class-sections, editing subject configs and templates: no UI. Use the API.

**Steps, mobile.**
1. Read only: Exam tab > Exams > open an exam > "Configured Subjects". No UI for the write operations.

**Expected results.**
- New `exam_class_sections` row (add), `exam_subject_config` and `exam_subject_components` rows (copy and apply), `exam_config_templates` and `exam_config_template_items` rows (templates).
- Responses carry ids only for class and subject names (no names), except template compare and auto-detect which add subject names and class names.

**API endpoints.**
- `GET /exams/{exam_id}/class-sections`: list (`id, exam_id, class_id, section_id, stream_id, created_at`); 404 for unknown exam.
- `POST /exams/{exam_id}/class-sections`: body `{class_id, section_id?}`; 201 `{class_section:{id, exam_id, class_id, section_id}, auto_detect:{suggestions[], has_suggestions}}`.
- `GET /exams/{exam_id}/subject-configs`: list ordered by class, section, sort order, with `components[]`.
- `GET /exams/{exam_id}/subject-configs/{config_id}`: one (404 `ExamSubjectConfig <id> not found`).
- `PUT /exams/{exam_id}/subject-configs/{config_id}`: partial body `subject_grade_scheme_id`, `credit_hours`, `has_internal_external_split`, `internal_max_marks`, `internal_min_pass`, `external_max_marks`, `external_min_pass`, `sort_order`, `is_active`.
- `POST /exam-patterns/templates`: `{template_name (max 150), description, board, level, items[]}`; each item has `subject_id`, optional scheme and split fields, `components[]` (same fields as `ComponentPayload`). 201.
- `POST /exam-patterns/templates/from-exam`: `{template_name, description, exam_id, class_id, section_id}` copies the class-section's configs. 201.
- `GET /exam-patterns/templates` (query `board`, `level`): active templates with `item_count`, newest first.
- `GET /exam-patterns/templates/{template_id}`: template with items (404 if unknown or inactive).
- `PUT /exam-patterns/templates/{template_id}`: body is a free JSON object; only `template_name`, `description`, `board`, `level`, `is_active` are applied.
- `DELETE /exam-patterns/templates/{template_id}`: soft delete (`is_active=false`); returns 200 `{"detail":"Template deactivated"}`.
- `POST /exam-patterns/{exam_id}/copy`: `{source_class_id, source_section_id, target_class_id, target_section_id, skip_missing_subjects}` returns `{configs_created, skipped_subjects}`.
- `POST /exam-patterns/{exam_id}/apply-template`: `{template_id, target_class_id, target_section_id, skip_missing_subjects}` returns the same shape.
- `GET /exam-patterns/{exam_id}/compare` (query `source_class_id`, `source_section_id`, `target_class_id`, `target_section_id`): `{common_subjects, source_only_subjects, target_only_subjects, can_copy_all, copyable_count}`.
- `GET /exam-patterns/{exam_id}/auto-detect` (query `target_class_id`, `target_section_id`): `{suggestions[], has_suggestions}` sorted by overlap count.
- All `exam-patterns` endpoints are rate limited (200 per minute).

**Rules and validations.**
- Add class-section: exam must be `draft` or `active` (409 `Cannot add class-sections to exam with status '<status>'.`); a duplicate (class, section) gives 409 `This class/section is already part of the exam.`; 404 for unknown exam. The class is not validated (a foreign key failure is an unhandled error).
- Subject config update changes only the supplied fields; `exam_id` in the path is not compared with the config's exam; `is_active` has no column and is ignored; components cannot be changed through this endpoint.
- Template name must be unique among active templates (409 `Template named '<name>' already exists.`); the database constraint covers inactive rows too, so reusing the name of a deleted template fails with 500 (KG-12).
- `from-exam`: 404 `No subject configs found for this exam/class/section.` when the class-section has no configs.
- Copy: target must be a class-section of the exam (400 `Target class/section is not part of this exam's class_sections.`); target must have no configs (409); source must have configs (404); subjects of the source not mapped to the target (compared against `class_subject_map`, `exclude_marks` false) cause 422 with a `source_only` list unless `skip_missing_subjects` is true, in which case they are returned in `skipped_subjects`.
- Apply: template must be active (404); same target checks (400, 409); a template subject not mapped to the target gives 422 `Template subject <id> is not mapped to target class/section.` unless `skip_missing_subjects`.
- Compare: source subjects come from the exam's configs for the source class-section; target subjects from the class-subject mapping. `can_copy_all` is true when there are no source-only subjects; `copyable_count` is the number of common subjects.
- Auto-detect: considers every other class-section of the exam that already has configs, keeps those with at least one common subject.

**Error and edge cases.**
- Compare and copy match the section exactly: a null section matches only null section rows.
- A template saved from an exam stores `max_marks` as strings inside JSON; applying it restores them to numbers in the new components.

**Unit-testable logic.**
- `add_class_section_to_exam` status rule; `compare_subjects` set arithmetic (common, source-only, target-only, `can_copy_all`, `copyable_count`); template item JSON mapping; `update_template` allowed-field filter.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-07-U01 | `add_class_section_to_exam` with exam status draft, active, locked, published, finalized (fake session) | draft and active proceed; the other three raise 409 | passing |
| TC-EXM-07-U02 | `compare_subjects` source {Math, Sci}, target {Math, Eng} | common {Math}, source-only {Sci}, target-only {Eng}, `can_copy_all` false, `copyable_count` 1 | passing |
| TC-EXM-07-U03 | `compare_subjects` source {Math}, target {Math, Sci} | `can_copy_all` true, `copyable_count` 1 | passing |
| TC-EXM-07-U04 | `compare_subjects` with empty source | common empty, `copyable_count` 0, `can_copy_all` true | passing |
| TC-EXM-07-U05 | `update_template` payload with `template_name`, `is_active` and an unknown key `foo` | name and flag applied; `foo` ignored | passing |
| TC-EXM-07-U06 | `ExamSubjectConfigUpdate` with `{}` and with `subject_grade_scheme_id=None` set explicitly | Empty dict changes nothing; explicit None clears the scheme (`exclude_unset`) | passing |
| TC-EXM-07-A01 | GET class-sections for EX1; unknown exam | List of one item with ids only, no names; 404 | passing |
| TC-EXM-07-A02 | POST class-section (new class-section) on an active exam (ADMIN) | 201; `class_section.id` present; `auto_detect.has_suggestions` true when another class-section has overlapping configured subjects | passing |
| TC-EXM-07-A03 | POST the same class-section again | 409 `This class/section is already part of the exam.` | passing |
| TC-EXM-07-A04 | POST class-section on a published exam | 409 `Cannot add class-sections to exam with status 'published'.` | passing |
| TC-EXM-07-A05 | POST class-section for unknown exam | 404 | passing |
| TC-EXM-07-A06 | GET subject-configs for EX1 | 3 configs ordered by class, section, sort order; each with `components` | passing |
| TC-EXM-07-A07 | GET one config; unknown config id | 200 with components; 404 `ExamSubjectConfig <id> not found` | passing |
| TC-EXM-07-A08 | PUT config `{"credit_hours": 4, "subject_grade_scheme_id": <subject scheme>}` | 200; fields updated; components unchanged | known defect: DEF-EXM-4: PUT /exams/{id}/subject-configs/{cid} returns 500 MissingGreenlet whenever a column value changes (... |
| TC-EXM-07-A09 | PUT config `{"subject_grade_scheme_id": null}` | 200; scheme cleared | known defect: DEF-EXM-4: PUT subject-configs returns 500 MissingGreenlet when clearing an assigned scheme (the change is com... |
| TC-EXM-07-A10 | PUT config `{"is_active": false}` | 200; no effect on listing (no column) | passing |
| TC-EXM-07-A11 | PUT unknown config | 404 | passing |
| TC-EXM-07-A12 | POST template manually with two items (ADMIN) | 201; `items[].components` populated; GET list shows `item_count` 2 | passing |
| TC-EXM-07-A13 | POST template with an existing active name | 409 `Template named '...' already exists.` | passing |
| TC-EXM-07-A14 | POST template from-exam for EX1 class-section | 201; `source_exam_id` set; items equal the config count | passing |
| TC-EXM-07-A15 | POST template from-exam for a class-section with no configs | 404 | passing |
| TC-EXM-07-A16 | GET templates with `board` and `level` filters | Only matching active templates | passing |
| TC-EXM-07-A17 | GET template by id; unknown id; deactivated template | 200; 404; 404 | passing |
| TC-EXM-07-A18 | PUT template `{"template_name": "New", "description": "d"}` | 200; fields updated | passing |
| TC-EXM-07-A19 | PUT template `{"is_active": false}` then GET list and GET one | Not listed; GET one 404 | passing |
| TC-EXM-07-A20 | DELETE template | 200 `{"detail":"Template deactivated"}`; later GET 404; list excludes it | passing |
| TC-EXM-07-A21 | Create a template with a deleted template's name | 500 (KG-12; database unique constraint includes inactive rows) | known defect: KG-12: creating a template with the name of a deleted (inactive) template returns 500 (database unique constra... |
| TC-EXM-07-A22 | POST copy source section A to a target class-section that has no configs and shares all subjects | 200 `{configs_created: 3, skipped_subjects: []}`; GET subject-configs shows the copied configs and components | passing |
| TC-EXM-07-A23 | POST copy to a target already holding configs | 409 `Target class/section already has subject configs for this exam.` | passing |
| TC-EXM-07-A24 | POST copy to a class-section not in the exam | 400 | passing |
| TC-EXM-07-A25 | POST copy where the source has a subject the target lacks, `skip_missing_subjects=false` | 422 with `source_only` list; nothing copied | passing |
| TC-EXM-07-A26 | Same as A25 with `skip_missing_subjects=true` | 200; common subjects copied; missing ids in `skipped_subjects` | passing |
| TC-EXM-07-A27 | POST copy from a source with no configs | 404 | passing |
| TC-EXM-07-A28 | POST apply-template to an empty target; a template subject not mapped (with and without `skip_missing_subjects`) | 200 with counts; 422; 200 with skipped list | passing |
| TC-EXM-07-A29 | POST apply-template with a deactivated template id | 404 | passing |
| TC-EXM-07-A30 | GET compare for two class-sections | Body has the five keys; `copyable_count` equals the intersection size | passing |
| TC-EXM-07-A31 | GET auto-detect for a new target class-section | Suggestions sorted by `overlap_subject_count` descending; `source_class_name` present | passing |
| TC-EXM-07-A32 | Write endpoints (add class-section, template create, from-exam, copy, apply) as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-07-A33 | PUT config and PUT template as TEACHER; DELETE template as TEACHER | 403 each (they lack update and delete) | passing |
| TC-EXM-07-A34 | GET class-sections, subject-configs, template by id, compare, auto-detect as all five roles | 200 for all (`exams:read`) | passing |
| TC-EXM-07-A35 | GET templates list as ADMIN, TEACHER, STAFF, STUDENT, PARENT | 200 for all five (`exams:list` is seeded for all) | passing |
| TC-EXM-07-A36 | All endpoints of this feature with NOAUTH | 401 each | passing |
| TC-EXM-07-A37 | Tenant isolation: tenant B cannot GET tenant A's template (404) or list it; `cschema` mismatch on POST copy | 404 and empty list; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-07-E01 | P1 | Web | Admin | Seeded exam "Half Yearly Examination 2026" (10 class-sections: Class 1 to Class 5, sections A and B). | 1. Sign in as Admin.<br>2. Open Exam > Exams.<br>3. Open "Half Yearly Examination 2026". | "Configured Subjects" groups subject badges under one "<Class> - <Section>" heading per class-section (10 headings). | planned |
| TC-EXM-07-E02 | P3 | Web | Admin | Seeded exam "Unit Test 1 - Class 1B"; ability to block GET /exams/<id>/subject-configs (browser dev-tools request block). | 1. Sign in as Admin.<br>2. Block the subject-configs request.<br>3. Open the "Unit Test 1 - Class 1B" detail page. | Overview shows "Unable to load the subject list for this exam. Please refresh the page or try again later." | planned |
| TC-EXM-07-E03 | P2 | Mobile | Admin | Seeded exam "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open Exam tab > "Exams".<br>3. Tap "Unit Test 1 - Class 1B". | "Configured Subjects" lists the 5 subjects under Class 1 - 1-B. | planned |

API tests implemented in: `backend/tests/api/exam/test_f07_configs_templates.py`

Implemented in: backend/tests/unit/exam/test_exam_create_status.py.

---

## F08 Exam dates

**Purpose.** Admin schedules each subject of an exam (date, start and end time, venue, notes) per class-section. Dates appear on the exam detail, are printed on hall tickets, and can be sent as a schedule SMS (F19).

**Roles and permissions.**
- Add, edit: `exams:update`. Delete: `exams:delete`. List: `exams:read`.
- Web: "Manage Dates" button and route `/exam/exams/{id}/dates` for admin role names (other roles are redirected to the exam detail; the Parent role sees the page read-only if reached). Mobile: screen "Exam Dates", editing only for admin role names with the permissions above, otherwise titled "Exam Dates (View Only)".

**Preconditions.**
- Exam exists. Class and subject must exist (no check that the subject is configured for the exam).

**Steps, web.**
1. Exam > Exams > open exam > tab "Dates" > "Manage Dates" (or "Add Dates" on an empty state). Page "Exam Dates".
2. Click "Add Date". Dialog "Add Exam Date": "Class *", "Section" (default "All sections"), "Subject *", "Exam Date *", "Start Time", "End Time", "Venue" (placeholder "Hall A"). "Save" is enabled when class, subject and date are filled. Toast "Exam date added".
3. Table columns S.No., Subject, Class, Section, Date, Start, End, Venue, Actions. Edit icon opens "Edit Exam Date" (class, section and subject are locked); toast "Exam date updated". Trash opens "Remove Exam Date?" then toast "Exam date removed". Search box "Search by subject, class or venue...".
4. Dates can also be added at creation (F06 section 4).

**Steps, mobile.**
1. Exam detail > "Manage Dates" (admin) or "View All Dates", or the Exam tab flow to `/exam/dates`. Select the exam chip; list cards with subject, class-section, date, time, venue.
2. Admin: add (modal fields "Class-Section *", "Subject *", "Exam Date *", "Start Time (optional)", "End Time (optional)", "Venue (optional)"), edit, delete (confirm "Delete Date"). Validation toasts "Select a class-section.", "Select a subject.", "Select the exam date.". Toasts "Date Added", "Updated", "Deleted".
3. Mobile add omits `exam_id` from the body, so the request is rejected with 422 (KG-8).

**Expected results.**
- Row in `exam_dates` (unique per exam, class, section, subject). List is ordered by date then subject id.

**API endpoints.**
- `POST /exams/{exam_id}/dates`: body `ExamDateCreate` including `exam_id` (required in the body), `class_id`, `section_id`, `subject_id`, `exam_date`, `start_time`, `end_time`, `venue` (max 100), `notes` (max 300). 201.
- `POST /exams/{exam_id}/dates/bulk`: `{dates:[ExamDateCreate...]}` (min 1). 201 list.
- `POST /exams/{exam_id}/dates/multi-section`: `{exam_id, subject_id, exam_date, start_time, end_time, venue, notes, class_sections:[{class_id, section_id}]}` (min 1). 201 list, one row per class-section.
- `GET /exams/{exam_id}/dates`: list (query `class_id` and `section_id` are sent by the web hook but ignored by the backend).
- `PUT /exams/{exam_id}/dates/{date_id}`: partial `exam_date`, `start_time`, `end_time`, `venue`, `notes`; null fields are not applied.
- `DELETE /exams/{exam_id}/dates/{date_id}`: 204.
- `POST /exams/{exam_id}/dates/send-schedule`: SMS (F19).

**Rules and validations.**
- The three create endpoints take the caller from the `sub` claim and return 201 with `created_by` set to the caller (KG-1 is fixed in code; the xfail API cases below need a rerun).
- Duplicate (exam, class, section, subject): 409. The unique constraint treats a null section as distinct, so duplicates with a null section may not be stopped (database behaviour, not covered by a service check).
- Bulk and multi-section are atomic: any conflict rolls back the whole batch.
- Times are `HH:MM` or `HH:MM:SS`; end before start and past dates are not rejected.
- The path `exam_id` is not compared with the body `exam_id`; the body value is stored. Exam existence is not checked (a missing exam hits a foreign key error that is reported as 409).
- Update cannot change class, section or subject.

**Error and edge cases.**
- Missing `exam_id` in the body: 422 (web sends it, mobile does not).
- Delete or update of an unknown date id: 404.
- Venue of 101 characters or notes of 301: 422.

**Unit-testable logic.**
- `ExamDateCreate`, `ExamDateBulkCreate`, `ExamDateMultiSectionCreate` validators; `update_exam_date` null-skip semantics; the `sub` versus `id` claim usage.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-08-U01 | `ExamDateCreate` without `exam_id` | Validation error | passing |
| TC-EXM-08-U02 | `ExamDateCreate` venue of 100 and 101 characters; notes of 300 and 301 | 100 and 300 valid; 101 and 301 invalid | passing |
| TC-EXM-08-U03 | `ExamDateBulkCreate(dates=[])` | Validation error (min 1) | passing |
| TC-EXM-08-U04 | `ExamDateMultiSectionCreate(class_sections=[])` | Validation error (min 1) | passing |
| TC-EXM-08-U05 | `update_exam_date` payload `{venue: None, notes: "x"}` (fake session) | venue unchanged, notes updated | passing |
| TC-EXM-08-U06 | `ExamDateCreate` with `start_time="09:30"` and `"09:30:00"` | Both parse to time 09:30 | passing |
| TC-EXM-08-U07 | `ExamDateCreate` with `exam_date="2026-13-01"` | Validation error | passing |
| TC-EXM-08-A01 | POST date with a valid body (ADMIN) | 201 with `created_by` equal to the caller (KG-1: currently 500) | passing |
| TC-EXM-08-A02 | POST date without `exam_id` in the body | 422 | passing |
| TC-EXM-08-A03 | POST the same exam, class, section, subject again | 409 | passing |
| TC-EXM-08-A04 | POST bulk with 3 dates | 201 list of 3 (KG-1: currently 500) | passing |
| TC-EXM-08-A05 | POST bulk where the second item duplicates an existing date | 409; first item also not stored | passing |
| TC-EXM-08-A06 | POST multi-section for 2 class-sections | 201 list of 2 with the same date and subject | passing |
| TC-EXM-08-A07 | POST bulk with empty `dates`; multi-section with empty `class_sections` | 422 each | passing |
| TC-EXM-08-A08 | POST date with `venue` of 101 characters | 422 | passing |
| TC-EXM-08-A09 | GET dates for EX1 | Ordered by `exam_date` then subject; fields incl. `created_by`; `class_id` query ignored | passing |
| TC-EXM-08-A10 | PUT date `{"exam_date": "2026-03-02", "venue": "Hall B"}` | 200 updated | passing |
| TC-EXM-08-A11 | PUT date `{}` | 200 unchanged | passing |
| TC-EXM-08-A12 | PUT unknown date id | 404 `ExamDate with id ... not found` | passing |
| TC-EXM-08-A13 | DELETE date then GET list | 204; absent from list | passing |
| TC-EXM-08-A14 | DELETE unknown date id | 404 | passing |
| TC-EXM-08-A15 | POST, PUT as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-08-A16 | DELETE as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-08-A17 | GET dates as all five roles | 200 for all | passing |
| TC-EXM-08-A18 | All endpoints with NOAUTH | 401 each | passing |
| TC-EXM-08-A19 | Tenant isolation: tenant B GET dates of tenant A's exam id | `[]`; PUT or DELETE on A's date id returns 404 | passing |
| TC-EXM-08-A20 | Token A with `cschema` B on POST | 403 | passing |
| TC-EXM-08-A21 | Dates stored before an exam is cloned | Clone does not copy dates: GET dates of the clone returns `[]` | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-08-E01 | P1 | Web | Admin | TC-EXM-06-E01 done. | 1. Sign in as Admin.<br>2. Open QA FA1 > tab "Dates".<br>3. Click "Manage Dates".<br>4. Click "Add Date".<br>5. Choose "Class *" Class 1, "Section" 1-B, "Subject *" Mathematics, an "Exam Date *", "Start Time" 09:00, "End Time" 12:00, "Venue" "QA Hall A".<br>6. Click "Save". | Toast "Exam date added"; the row appears with Subject, Class, Section, Date, Start, End, Venue. | planned |
| TC-EXM-08-E02 | P3 | Web | Admin | TC-EXM-06-E01 done. | 1. Sign in as Admin.<br>2. Open QA FA1 > "Dates" > "Manage Dates" > "Add Date".<br>3. Choose Class and Exam Date but no Subject. | "Save" stays disabled. | planned |
| TC-EXM-08-E03 | P2 | Web | Admin | TC-EXM-08-E01 done. | 1. Sign in as Admin.<br>2. Open the QA FA1 "Exam Dates" page.<br>3. Click the Edit icon on the Mathematics row.<br>4. Change "Exam Date" and click "Save". | In "Edit Exam Date" Class, Section and Subject are disabled; toast "Exam date updated"; the row shows the new date. | planned |
| TC-EXM-08-E04 | P2 | Web | Admin | TC-EXM-08-E01 done. | 1. Sign in as Admin.<br>2. Open the "Exam Dates" page.<br>3. Click the trash icon on the row.<br>4. Click "Remove" in "Remove Exam Date?". | Toast "Exam date removed"; row gone. | planned |
| TC-EXM-08-E05 | P3 | Web | Admin | TC-EXM-08-E01 done. | 1. Sign in as Admin.<br>2. Open the "Exam Dates" page.<br>3. Type "Hall" in "Search by subject, class or venue...".<br>4. Type "zzz". | Only rows whose subject, class or venue match remain; "zzz" leaves none. | planned |
| TC-EXM-08-E06 | P2 | Web | Teacher | Seeded exam "Unit Test 1 - Class 1B" (5 dates, venue Room 1B). | 1. Sign in as Teacher.<br>2. Open "Unit Test 1 - Class 1B" > tab "Dates".<br>3. Open /exam/exams/<id>/dates in the address bar. | The seeded dates are visible but there is no "Manage Dates" or "Add Dates" button; the URL redirects to the exam detail. | planned |
| TC-EXM-08-E07 | P3 | Web | Admin | An exam with no dates (QA FA1 before TC-EXM-08-E01). | 1. Sign in as Admin.<br>2. Open the exam > tab "Dates".<br>3. Click "Manage Dates". | The tab shows "No exam dates scheduled yet." with "Add Dates"; the Exam Dates page shows "No exam dates yet" with "Add First Date". | planned |
| TC-EXM-08-E08 | P2 | Mobile | Admin | TC-EXM-06-E01 done. | 1. Sign in as Admin.<br>2. Open QA FA1 on mobile and tap "Manage Dates" (or the Dates tab).<br>3. Tap add; choose "Class-Section *" Class 1 - 1-B, "Subject *" Mathematics, "Exam Date *".<br>4. Save. | Target: toast "Date Added". Currently the request omits exam_id and the API answers 422 (KG-8). | blocked: KG-8 mobile date create omits exam_id |
| TC-EXM-08-E09 | P2 | Mobile | Admin | TC-EXM-08-E01 done (date created on web). | 1. Sign in as Admin.<br>2. Open QA FA1 on mobile > Exam Dates.<br>3. Edit the Mathematics date (change the venue) and save.<br>4. Delete the date and confirm "Delete Date". | Toasts "Updated" then "Deleted"; the card disappears. | planned |
| TC-EXM-08-E10 | P3 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open QA FA1 > Exam Dates.<br>3. Tap add and save without a class-section. | Toast "Select a class-section."; nothing sent. | planned |
| TC-EXM-08-E11 | P2 | Mobile | Teacher | Seeded exam "Unit Test 1 - Class 1B" (5 dates). | 1. Sign in as Teacher.<br>2. Open Exam tab > "Exams" > "Unit Test 1 - Class 1B".<br>3. Open the Dates tab and tap "View All Dates". | Screen title "Exam Dates (View Only)"; no add, edit or delete controls. | planned |

API tests implemented in: `backend/tests/api/exam/test_f08_dates.py`

Implemented in: backend/tests/unit/exam/test_exam_create_status.py.

---

## F09 Edit, clone, activate, deactivate, delete and unlock (status rules)

**Purpose.** Admin adjusts an exam after creation and moves it through its lifecycle: edit header fields, clone, activate, deactivate, delete, and (API and mobile) unlock a published exam for corrections. The status table is in "Cross-feature reference".

**Roles and permissions.**
- Edit, activate, deactivate, unlock: `exams:update`. Clone: `exams:create`. Delete: `exams:delete`.
- Web and mobile show these actions only to admin role names; edit is shown for draft and active on the detail screens, delete only for draft, activate only for draft, deactivate only for active, unlock (mobile only) only for published.

**Preconditions.**
- Exam exists. Statuses as in the cross-feature table.

**Steps, web.**
1. Exam > Exams > open an exam. Header shows name, status badge and "board . level . exam type . nature".
2. "Edit" (draft or active): dialog "Edit Exam": Exam Name, Exam Grade Scheme, Subject Grade Scheme, Mark Entry Deadline, Min Attendance %, Attendance From, Attendance To, Term; "Save Changes". Toast "Exam updated successfully". The backend ignores the two scheme selects. The list page also has an Edit icon for every status (dialog "Edit Exam" with Exam Name, Mark Entry Deadline, Min Attendance %, Attendance From, Attendance To, Term, "Publish Rank").
3. "Clone": dialog "Clone Exam", "New Exam Name" prefilled "<name> (Copy)", button "Clone", then navigation to the clone. The typed name is ignored by the backend, the clone is always named "Copy of <name>" (KG-10). Toast "Exam cloned successfully".
4. "Activate" (draft): confirm "Activate Exam?" text "...will allow mark entry and hall ticket processing"; toast "Exam activated". "Deactivate" (active): confirm "Deactivate Exam?"; toast "Exam moved back to draft"; returns to the list.
5. "Delete" (draft only): confirm "Delete Exam?"; toast "Exam deleted". The list's trash icon shows only on draft rows.
6. Unlock has no web UI (the hook exists but is unused).

**Steps, mobile.**
1. Exam tab > Exams > open an exam. "Actions": Edit (draft or active; fields Exam Name *, Mark Entry Deadline, Min Attendance, Attendance From, Attendance To, "Publish Rank"), Activate (confirm "Activate Exam"), Deactivate (confirm "Deactivate Exam"), Clone (modal), plus navigation buttons Marks (active only), Results (published or finalized), Hall Tickets, Permissions.
2. "Danger Zone": "Unlock for Corrections" (published only; modal "Reason for unlocking *", button "Unlock Exam", toast "Exam Unlocked"), "Delete Exam" (draft only; confirm "Delete Exam"). Toasts "Exam Updated", "Exam Activated", "Exam Deactivated", "Exam Cloned".

**Expected results.**
- Status changes as in the table; unlock writes an `exam_unlocked` audit row with the reason, delete writes `exam_deleted` with counts of removed marks and results; none of activate, deactivate, clone or edit write audit rows.
- Delete removes student marks, subject results, exam results, then the exam and its class-sections, configs, components, dates, mark permissions and hall ticket rows. The audit log keeps its rows (no foreign key).
- Unlock only changes the status to `active`; computed results, `hall_ticket_published` and marks are kept.

**API endpoints.**
- `PUT /exams/{exam_id}`: partial `ExamUpdate`: `exam_name` (max 150), `mark_entry_deadline`, `hall_ticket_min_attendance` (0-100), `attendance_from_date`, `attendance_to_date`, `publish_rank`, `term`. Other fields are ignored.
- `DELETE /exams/{exam_id}`: 204.
- `POST /exams/{exam_id}/clone`: any body (ignored); 201 `ExamRead` of a draft named `Copy of <name>`, `cloned_from_exam_id` set.
- `POST /exams/{exam_id}/activate`, `POST /exams/{exam_id}/deactivate`: `{exam_id, status}`.
- `POST /exams/{exam_id}/unlock`: body `{reason}` (required); response `{exam_id, status:"active", reason}`.

**Rules and validations.**
- The update endpoint does not check status (its docstring says draft or active only) and does not catch a duplicate name (unhandled integrity error, 500). A `term` over 20 characters hits the column limit (500).
- Activate only from `draft` (409 `Exam status '<s>' cannot be activated. Only draft exams can be set to active.`). Deactivate only from `active` (409 `... cannot be deactivated. Only active exams can be set to draft.`).
- Unlock from `locked`, `published`, `finalized` (409 `Exam status '<s>' cannot be unlocked. Must be locked, published, or finalized.`). A missing `reason` gives 422; an empty string is accepted by the API (mobile requires text); the reason is stored in a 300-character column.
- Delete blocked only for `published` (409 `Exam '<name>' cannot be deleted because it is published. Unpublish or unlock it before deleting.`). Active, locked and finalized exams can be deleted through the API even though the UI offers it for draft only.
- Clone copies only the header (no class-sections, configs, dates); copies deadline, grade scheme, attendance values and flags; fails with 409 if "Copy of <name>" already exists in the academic year (so a second clone fails).

**Error and edge cases.**
- Edit with `hall_ticket_min_attendance` 101: 422. Edit of an unknown id: 404.
- Delete of an exam that has marks: marks and results are removed in the same transaction.
- Deleted exam's audit rows remain readable by exam id (F18).

**Unit-testable logic.**
- `activate_exam`, `deactivate_exam`, `unlock_exam`, `delete_exam`, `clone_exam` against fake sessions, for every status.
- `ExamUpdate` bounds; web and mobile status-based button visibility rules.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-09-U01 | `activate_exam` for status draft, active, locked, published, finalized | draft becomes active; the other four raise 409 | passing |
| TC-EXM-09-U02 | `deactivate_exam` for the same five statuses | active becomes draft; the other four raise 409 | passing |
| TC-EXM-09-U03 | `unlock_exam` for the same five statuses | locked, published, finalized become active; draft and active raise 409 | passing |
| TC-EXM-09-U04 | `delete_exam` for the five statuses (fake session) | published raises 409; the other four delete and call `log_action("exam_deleted")` | passing |
| TC-EXM-09-U05 | `delete_exam` with `performed_by=None` | Deletes without writing an audit row | passing |
| TC-EXM-09-U06 | `clone_exam` default name | New exam status `draft`, name `Copy of <source>`, `cloned_from_exam_id` set, copies deadline, scheme, publish_rank | passing |
| TC-EXM-09-U07 | `clone_exam` when `Copy of <name>` already exists | 409 | passing |
| TC-EXM-09-U08 | `ExamUpdate(hall_ticket_min_attendance=101)`, `exam_name` of 151 characters | Both invalid | passing |
| TC-EXM-09-U09 | `update_exam` with only `exam_name` | Other fields unchanged (`exclude_unset`) | passing |
| TC-EXM-09-U10 | `UnlockExamRequest()` with no reason | Validation error | passing |
| TC-EXM-09-U11 | Web visibility rule: Edit for draft and active only; Delete and Activate for draft only; Deactivate for active only | Truth table matches for all five statuses | blocked: status visibility flags are inline in web/src/pages/exam/ExamList.tsx and ExamDetail.tsx; needs a helper exported |
| TC-EXM-09-U12 | Mobile `canUnlock` is true only for published and admin role | Truth table matches | blocked: canUnlock is inline in mobile/app/exam/[id].tsx; needs a helper exported |
| TC-EXM-09-A01 | PUT `/exams/{id}` `{"exam_name": "QA FA1 v2", "term": "Term 1"}` (ADMIN) | 200 with updated name and term; other fields unchanged | passing |
| TC-EXM-09-A02 | PUT as above on a published exam | 200 (no status check; documents current behaviour) | passing |
| TC-EXM-09-A03 | PUT `exam_name` equal to another exam's name in the same year | 500 (KG-10; target 409) | known defect: KG-10: PUT /exams/{id} with a duplicate exam name returns 500 instead of 409 |
| TC-EXM-09-A04 | PUT `hall_ticket_min_attendance` 101 and `exam_name` 151 characters | 422 each | passing |
| TC-EXM-09-A05 | PUT unknown exam | 404 | passing |
| TC-EXM-09-A06 | PUT body with `board`, `level`, `exam_grade_scheme_id` | 200; those fields unchanged | passing |
| TC-EXM-09-A07 | POST clone of EX1 | 201; `status` draft; `exam_name` `Copy of QA FA1`; `cloned_from_exam_id` is EX1; GET class-sections of the clone returns `[]` | passing |
| TC-EXM-09-A08 | POST clone with body `{"new_name": "Custom"}` | 201; name still `Copy of QA FA1` | passing |
| TC-EXM-09-A09 | POST clone twice | Second returns 409 | passing |
| TC-EXM-09-A10 | POST clone unknown exam | 404 | passing |
| TC-EXM-09-A11 | POST activate on a draft exam | 200 `{status: "active"}` | passing |
| TC-EXM-09-A12 | POST activate on an active exam | 409 | passing |
| TC-EXM-09-A13 | POST deactivate on an active exam | 200 `{status: "draft"}` | passing |
| TC-EXM-09-A14 | POST deactivate on a draft exam | 409 | passing |
| TC-EXM-09-A15 | POST unlock `{"reason": "Marks fix"}` on a published exam | 200 `{status: "active", reason: "Marks fix"}`; audit row `exam_unlocked` with that reason; computed results still present | passing |
| TC-EXM-09-A16 | POST unlock on a draft or active exam | 409 | passing |
| TC-EXM-09-A17 | POST unlock with no body or no `reason` | 422 | passing |
| TC-EXM-09-A18 | POST unlock with a reason of 301 characters | 500 (column limit; document and fix) | known defect: DEF-EXM-5: POST /exams/{id}/unlock with a reason over 300 characters returns 500 (column limit) instead of 422 |
| TC-EXM-09-A19 | DELETE a draft exam with marks and results | 204; GET exam 404; marks, subject results and exam results gone; audit row `exam_deleted` with counts | passing |
| TC-EXM-09-A20 | DELETE an active exam | 204 (API allows; UI does not) | passing |
| TC-EXM-09-A21 | DELETE a published exam | 409 with the "cannot be deleted because it is published" message; exam remains | passing |
| TC-EXM-09-A22 | DELETE unknown exam | 404 | passing |
| TC-EXM-09-A23 | PUT, activate, deactivate, unlock as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-09-A24 | Clone as TEACHER, STAFF, STUDENT, PARENT; DELETE as the same | 403 each | passing |
| TC-EXM-09-A25 | All six endpoints with NOAUTH | 401 each | passing |
| TC-EXM-09-A26 | Tenant isolation: tenant B calls DELETE, activate, clone on tenant A's exam id | 404 each; tenant A exam untouched | passing |
| TC-EXM-09-A27 | Token A with `cschema` B on DELETE | 403 | passing |
| TC-EXM-09-A28 | After DELETE, GET `/exams/{id}/audit` | Still returns the `exam_deleted` row | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-09-E01 | P1 | Web | Admin | TC-EXM-06-E01 done. | 1. Sign in as Admin.<br>2. Open Exam > Exams.<br>3. Click the Edit icon on "QA FA1".<br>4. Change "Exam Name" to "QA FA1 v2".<br>5. Click "Save Changes". | Toast "Exam updated successfully"; the list shows "QA FA1 v2". Rename back to "QA FA1" the same way. | planned |
| TC-EXM-09-E02 | P2 | Web | Admin | Seeded published exam "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open the "Unit Test 1 - Class 1B" detail. | No "Edit", "Activate", "Deactivate" or "Delete" buttons; "Clone" is shown; no unlock control (web has none). | planned |
| TC-EXM-09-E03 | P1 | Web | Admin | A draft exam "QA Doc Draft" (clone of QA FA1 from TC-EXM-09-E05, or deactivate one). | 1. Sign in as Admin.<br>2. Open the draft exam.<br>3. Click "Activate".<br>4. Click "Activate" in "Activate Exam?". | Toast "Exam activated"; badge Active; "Deactivate" now shown and "Activate" and "Delete" hidden. | planned |
| TC-EXM-09-E04 | P2 | Web | Admin | An active exam with no published results. | 1. Sign in as Admin.<br>2. Open the active exam.<br>3. Click "Deactivate".<br>4. Click "Deactivate" in "Deactivate Exam?". | Toast "Exam moved back to draft"; redirected to the list; the exam shows Draft. | planned |
| TC-EXM-09-E05 | P1 | Web | Admin | TC-EXM-06-E01 done; no exam "Copy of QA FA1" exists. | 1. Sign in as Admin.<br>2. Open QA FA1.<br>3. Click "Clone".<br>4. Keep "New Exam Name" ("QA FA1 (Copy)") and click "Clone". | Toast "Exam cloned successfully"; the app opens the new draft named "Copy of QA FA1" (the typed name is ignored, KG-10) with no configured subjects. | planned |
| TC-EXM-09-E06 | P2 | Web | Admin | TC-EXM-09-E05 done ("Copy of QA FA1" is draft). | 1. Sign in as Admin.<br>2. Open "Copy of QA FA1".<br>3. Click "Delete".<br>4. Click "Delete" in "Delete Exam?". | Toast "Exam deleted"; back on the list; the exam is gone. | planned |
| TC-EXM-09-E07 | P3 | Web | Admin | Seeded exams plus a draft (TC-EXM-09-E05 done). | 1. Sign in as Admin.<br>2. Open Exam > Exams.<br>3. Look at the Actions column. | Edit icon on every row; trash icon only on draft rows. | planned |
| TC-EXM-09-E08 | P2 | Web | Teacher | Seeded exam "Half Yearly Examination 2026". | 1. Sign in as Teacher.<br>2. Open Exam > Exams > "Half Yearly Examination 2026". | No Edit, Clone, Activate, Deactivate or Delete buttons; tabs Overview, Dates, Marks only (no Permissions or Audit Log). | planned |
| TC-EXM-09-E09 | P1 | Mobile | Admin | A draft exam (for example "Copy of QA FA1"). | 1. Sign in as Admin.<br>2. Open Exam tab > "Exams" > the draft exam.<br>3. Tap "Activate".<br>4. Confirm "Activate Exam". | Toast "Exam Activated"; status pill ACTIVE; "Deactivate" now in Actions. | planned |
| TC-EXM-09-E10 | P2 | Mobile | Admin | An active exam without results. | 1. Sign in as Admin.<br>2. Open the active exam.<br>3. Tap "Deactivate" and confirm "Deactivate Exam". | Toast "Exam Deactivated"; status pill DRAFT. | planned |
| TC-EXM-09-E11 | P2 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open QA FA1.<br>3. Tap "Edit".<br>4. Change "Exam Name *" to "QA FA1 v2" and tap "Save Changes". | Modal "Edit Exam" notes "Board, level, nature, and academic year cannot be changed after creation."; toast "Exam Updated"; header shows the new name. Rename back. | planned |
| TC-EXM-09-E12 | P3 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open QA FA1 > "Edit".<br>3. Clear "Exam Name *" and tap "Save Changes". | Toast "Validation" "Exam name is required."; nothing saved. | planned |
| TC-EXM-09-E13 | P2 | Mobile | Admin | QA FA1 published (TC-EXM-16-E08 done). Do not unlock the seeded Unit Tests. | 1. Sign in as Admin.<br>2. Open the published exam.<br>3. In "Danger Zone" tap "Unlock for Corrections".<br>4. Enter "Reason for unlocking *" "QA marks fix".<br>5. Tap "Unlock Exam". | Toast "Exam Unlocked"; status ACTIVE; Danger Zone no longer offers Unlock; audit row exam_unlocked with the reason. | planned |
| TC-EXM-09-E14 | P3 | Mobile | Admin | QA FA1 published. | 1. Sign in as Admin.<br>2. Open the published exam > "Unlock for Corrections".<br>3. Leave the reason empty. | "Unlock Exam" is disabled; forcing it shows "Reason is required.". | planned |
| TC-EXM-09-E15 | P2 | Mobile | Admin | A draft exam "QA Doc Draft". | 1. Sign in as Admin.<br>2. Open the draft exam.<br>3. In "Danger Zone" tap "Delete Exam" and confirm "Delete Exam". | Navigates back; the exam is gone from the list. | planned |
| TC-EXM-09-E16 | P2 | Mobile | Admin | QA FA1 exists; no "Copy of QA FA1". | 1. Sign in as Admin.<br>2. Open QA FA1.<br>3. Tap "Clone".<br>4. Enter "New Exam Name" "QA Typed Name" and tap "Clone Exam". | Modal text "A copy of QA FA1 will be created without marks."; toast "Exam Cloned"; the clone opens and is named "Copy of QA FA1" (KG-10). Delete it afterwards. | planned |

API tests implemented in: `backend/tests/api/exam/test_f09_status.py`

Implemented in: backend/tests/unit/exam/test_exam_create_status.py (U01-U10). U11 and U12 blocked.

---

## F10 Mark entry permissions

**Purpose.** Admin restricts mark entry for an exam to named users (for example a clerk or the subject teachers). With no active permission rows, every user holding `exam_marks:create` may enter marks.

**Roles and permissions.**
- Grant and edit: `exams:update`. Revoke: `exams:delete`. List: `exams:read`.
- Web: exam detail tab "Permissions" and page `/exam/exams/{id}/permissions` (admin role names only; others are redirected to the exam detail). Mobile: "Permissions" button on exam detail and screen `/exam/permissions` (admin only; others are redirected to `/exam/list`).

**Preconditions.**
- Exam exists. The user to grant must have a user account (the `users.id`, not the staff id).

**Steps, web.**
1. Exam > Exams > open an exam > tab "Permissions" > "Manage Permissions". Page "Mark Entry Permissions".
2. The blue banner states "Teachers can always enter marks for their assigned subjects. This panel is for granting access to Clerk/CA staff only." This is not what the backend does (see rules).
3. Table columns S.No., User, Granted At, Status (Active or Revoked), Actions (trash). The User column shows `user_display_name`, which the API does not return, so rows read "Unnamed user" (KG-9).
4. "Grant Access to User": type a user id into "Enter User ID", click "Grant Access" (toast "Access granted successfully"). The exam detail tab "Permissions" shows "Manage Permissions" and the text "Delegate mark-entry access to Clerk/CA staff for this exam." Trash opens "Revoke Access?"; toast "Access revoked".

**Steps, mobile.**
1. Exam detail > "Permissions" (or Exam tab flow to `/exam/permissions`). Empty state "No permissions granted yet" with "Grant First Permission" (the exam detail also has a "Mark Permissions (n)" section with "Grant"). "Grant Mark Permission" modal: "Teacher *" (active staff list), "Scope (optional)" (all subjects or one subject config), "Scope Note (optional)". Toasts "Permission Granted", "Updated", "Revoked". Toggle icon pauses or reactivates a permission; the close icon revokes (confirm "Revoke Permission").
2. The request omits `exam_id` from the body, so the API answers 422 (KG-8). The scope fields (class, section, subject config, teacher id) are ignored by the backend: a permission is per user and exam only.

**Expected results.**
- Row in `exam_mark_entry_permissions` (unique intent per exam and user). Revoke is a soft delete (`is_active` false) so the row stays for audit.
- Mark entry behaviour changes immediately for that exam (F11).

**API endpoints.**
- `POST /exams/{exam_id}/mark-permissions`: body `{exam_id, user_id, scope_note}` (`exam_id` required in the body). 201 `MarkPermissionRead` (`id, exam_id, user_id, granted_by, scope_note, is_active, created_at`).
- `GET /exams/{exam_id}/mark-permissions`: all rows (active and revoked), oldest first.
- `PUT /exams/{exam_id}/mark-permissions/{permission_id}`: body `{is_active (required), scope_note}`.
- `DELETE /exams/{exam_id}/mark-permissions/{permission_id}`: 204 (sets `is_active` false).

**Rules and validations.**
- Authorization rule (`authorize_mark_entry`, applied by `GET /exams/{id}/marks` and `POST /exams/{id}/marks`):
  1. If the caller has an active permission row for the exam: allowed.
  2. Else, if the exam has no active permission rows at all: allowed (open access).
  3. Else: 403 `You do not have mark entry permission for this exam`.
  Therefore as soon as one user is granted, every other user (including the subject teachers) is blocked from those two endpoints for that exam. The Excel template and upload endpoints are not checked.
- Grant: an active row for the same (exam, user) gives 409; an inactive row is re-activated (same id, new `granted_by`); otherwise a new row. `scope_note` is stored (max 200 in the column).
- The grant endpoint takes the caller from the `sub` claim and returns 201 with `granted_by` set to the caller (KG-1 is fixed in code; the xfail API cases below need a rerun).
- No check that the user or exam exists (foreign key failure becomes 500). The path `exam_id` is used for the lookup but the body `exam_id` is required too.
- `PUT` and `DELETE` do not verify that the permission belongs to the path exam.

**Error and edge cases.**
- Missing `exam_id` or `user_id` in the body: 422. Missing `is_active` on PUT: 422.
- Revoked row is returned by GET and can be re-activated by PUT or by granting again.
- If all rows are revoked the exam returns to open access.

**Unit-testable logic.**
- `authorize_mark_entry` (every branch) with a fake session; `grant_permission` (new, duplicate active, reactivate); `MarkPermissionCreate` and `MarkPermissionUpdate` schemas.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-10-U01 | `authorize_mark_entry`: caller has an active row | Returns True | passing |
| TC-EXM-10-U02 | `authorize_mark_entry`: exam has no active rows at all | Returns True (open access) | passing |
| TC-EXM-10-U03 | `authorize_mark_entry`: another user has an active row, caller has none | Raises 403 `You do not have mark entry permission for this exam` | passing |
| TC-EXM-10-U04 | `authorize_mark_entry`: caller's row inactive, another user's row active | Raises 403 | passing |
| TC-EXM-10-U05 | `authorize_mark_entry`: only inactive rows exist | Returns True | passing |
| TC-EXM-10-U06 | `grant_permission` with an existing active row | Raises 409 | passing |
| TC-EXM-10-U07 | `grant_permission` with an existing inactive row and a new note | Same row, `is_active` True, `granted_by` updated, note updated | passing |
| TC-EXM-10-U08 | `grant_permission` with no row | New row with `is_active` True | passing |
| TC-EXM-10-U09 | `MarkPermissionCreate` without `exam_id`; `MarkPermissionUpdate` without `is_active` | Both invalid | passing |
| TC-EXM-10-A01 | POST grant `{exam_id, user_id: TEACHER1, scope_note}` (ADMIN) | 201 with `granted_by` the admin id, `is_active` true (KG-1: currently 500) | passing |
| TC-EXM-10-A02 | POST grant without `exam_id` in the body | 422 | passing |
| TC-EXM-10-A03 | POST grant twice for the same user | Second returns 409 | passing |
| TC-EXM-10-A04 | PUT `{"is_active": false}`, then POST grant again | PUT 200; POST re-activates the same row id | passing |
| TC-EXM-10-A05 | GET list after grant, revoke | Both active and revoked rows listed, oldest first | passing |
| TC-EXM-10-A06 | PUT `{"is_active": false, "scope_note": "x"}` | 200 updated | passing |
| TC-EXM-10-A07 | PUT without `is_active` | 422 | passing |
| TC-EXM-10-A08 | PUT unknown permission id | 404 `ExamMarkEntryPermission with id ... not found` | passing |
| TC-EXM-10-A09 | DELETE then GET list | 204; the row remains with `is_active` false | passing |
| TC-EXM-10-A10 | DELETE unknown permission id | 404 | passing |
| TC-EXM-10-A11 | Effect: with a grant for TEACHER1 only, TEACHER2 GET marks grid and POST marks | 403 `You do not have mark entry permission for this exam` for both | passing |
| TC-EXM-10-A12 | Effect: TEACHER1 (granted) GET grid and POST marks | 200 | passing |
| TC-EXM-10-A13 | Effect: revoke the only active grant, TEACHER2 GET grid | 200 (open access restored) | passing |
| TC-EXM-10-A14 | Effect: TEACHER2 (not granted) downloads the template and uploads a file | 200 (these endpoints are not delegated-checked; documents KG-6) | passing |
| TC-EXM-10-A15 | POST, PUT as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-10-A16 | DELETE as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-10-A17 | GET list as all five roles | 200 for all | passing |
| TC-EXM-10-A18 | All endpoints with NOAUTH | 401 each | passing |
| TC-EXM-10-A19 | Tenant isolation: tenant B GET list for tenant A's exam id; PUT or DELETE A's permission id | `[]`; 404 | passing |
| TC-EXM-10-A20 | Token A with `cschema` B on POST | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-10-E01 | P1 | Web | Admin | TC-EXM-06-E01 done; the user id of the QA Staff login (Administration > Users). | 1. Sign in as Admin.<br>2. Open QA FA1 > tab "Permissions".<br>3. Click "Manage Permissions".<br>4. Paste the Staff user id into "Enter User ID".<br>5. Click "Grant Access". | Toast "Access granted successfully"; a row appears with Granted At and Status Active. | planned |
| TC-EXM-10-E02 | P3 | Web | Admin | TC-EXM-10-E01 done. | 1. Sign in as Admin.<br>2. Open the "Mark Entry Permissions" page of QA FA1. | User column reads "Unnamed user" (the API returns no display name, KG-9); the banner still says teachers can always enter marks (KG-9). | planned |
| TC-EXM-10-E03 | P2 | Web | Admin | TC-EXM-10-E01 done. | 1. Sign in as Admin.<br>2. Open the "Mark Entry Permissions" page.<br>3. Click the trash icon on the row.<br>4. Click "Revoke" in "Revoke Access?". | Toast "Access revoked"; Status shows "Revoked" (the row stays). | planned |
| TC-EXM-10-E04 | P3 | Web | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open the "Mark Entry Permissions" page.<br>3. Leave "Enter User ID" empty. | "Grant Access" is disabled. | planned |
| TC-EXM-10-E05 | P2 | Web | Teacher | QA FA1 exists. | 1. Sign in as Teacher.<br>2. Open /exam/exams/<QA FA1 id>/permissions in the address bar. | Redirected to the exam detail; no Permissions tab. | planned |
| TC-EXM-10-E06 | P2 | Web | Teacher | TC-EXM-10-E01 done (only Staff granted). | 1. Sign in as Teacher.<br>2. Open Exam > Marks > QA FA1 > "Enter Marks".<br>3. Type Written 50 for one student.<br>4. Click "Save Marks". | Error toast "You do not have mark entry permission for this exam"; nothing saved (contradicts the page banner, KG-9). Revoke the grant afterwards (TC-EXM-10-E03). | planned |
| TC-EXM-10-E07 | P2 | Mobile | Admin | TC-EXM-06-E01 done. | 1. Sign in as Admin.<br>2. Open QA FA1 > "Permissions".<br>3. Tap "Grant First Permission" (or "Grant").<br>4. Choose a "Teacher *" and save. | Target: toast "Permission Granted". Currently the request omits exam_id and the API answers 422 (KG-8). | blocked: KG-8 mobile grant omits exam_id |
| TC-EXM-10-E08 | P3 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open QA FA1 > "Permissions" > "Grant First Permission".<br>3. Save without choosing a teacher. | Toast "Select a teacher."; nothing sent. | planned |
| TC-EXM-10-E09 | P2 | Mobile | Admin | TC-EXM-10-E01 done (grant made on web). | 1. Sign in as Admin.<br>2. Open QA FA1 > "Permissions".<br>3. Tap the toggle icon on the permission.<br>4. Tap the close icon and confirm "Revoke Permission". | Toasts "Updated" then "Revoked". | planned |
| TC-EXM-10-E10 | P3 | Mobile | Teacher | QA FA1 exists. | 1. Sign in as Teacher.<br>2. Open QA FA1 on mobile. | No "Permissions" button or Mark Permissions section; in-app navigation to /exam/permissions redirects to /exam/list. | planned |

API tests implemented in: `backend/tests/api/exam/test_f10_permissions.py`

Implemented in: backend/tests/unit/exam/test_marks_entry.py.

---

## F11 Mark entry (per student, bulk save, Excel)

**Purpose.** Teachers (or delegated users) enter marks per student and component, save many at once, and optionally fill a downloaded Excel template and upload it. Marks are checked against each component's maximum.

**Roles and permissions.**
- Load the grid and download the template: `exam_marks:read`. Save marks and upload Excel: `exam_marks:create`. Delegation (F10) applies to grid load and save.
- Teacher has all three; Staff only read (cannot save); Admin has all; Student and Parent have none of them (`read_own` and `read_related` do not match the `read` and `create` checks).
- Web: Exam > Marks; buttons shown when `exams:update` or `exam_marks:create`. Mobile: Exam tab > "Mark Entry" (permission `exam_marks:create`).

**Preconditions.**
- Exam with class-section, subject configs and components (F06). Students enrolled in the class-section (`student_admissions`). Exam status is not checked, but both clients list only some statuses: web draft, active, locked; mobile (picker without an exam id) active only.

**Steps, web.**
1. Exam > Marks (`/exam/marks`, title "Mark Entry", subtitle "Select an exam to enter or review marks"). Student and Parent users get a "View My Marks" button here instead (F17). Click an exam.
2. The summary screen (F12) opens; choose class-section and students, click "Enter Marks".
3. Grid "Mark Entry - <exam>" with subtitle "<class> - <section>": columns "Adm#", "Student Name", then for every subject one column per component "Written[80]" plus "Total[100]", and "Grand Total[300]". Cells are numeric inputs (min 0, max = component max). Typing above the max shows toast "Cannot exceed max marks (80) for Written" and the value is rejected.
4. Changed students are counted on the "Save Marks" button and a banner says "Unsaved changes for N students. Click Save Marks to save."
5. Click "Save Marks": one request per subject with only the students that changed, containing every component of that subject (values entered, or existing values). Toast "Marks saved successfully" (or "Some subjects could not be saved", or "No changes to save").
6. "Template": downloads an `.xlsx` generated in the browser (toast "Excel downloaded"; file "<exam> <class> <section>.xlsx", columns "Adm#", "Student Name", "<Subject> <Component>[max]", "<Subject> Total[max]", "Grand Total[max]"). "Upload Excel" reads such a file in the browser, matches rows by "Adm#" and columns by the "<Subject> <Component>" label, puts valid cells into the grid as unsaved edits (toast "Imported N student rows ... Review and click Save Marks.", skipped cells counted when non-numeric or above max) and does not call the server upload endpoint. "Send Marks" opens the Communication quick-send for the class-section parents (cross-module).
7. Absent students (existing `is_absent`) show an "ABS" badge in all their cells for that subject; absence cannot be set from the web grid.

**Steps, mobile.**
1. Exam tab > "Mark Entry" (tile shown with `exam_marks:create`, so not for Staff; or exam detail > "Marks", visible for active exams). With no exam preselected, the exam chips list active exams. A summary card per class-section shows "GRAND TOTAL[max]", subject cards ("Written[80.00] Oral[20.00] Total[100]" and "Enter Marks") and "x/y students selected" with "Change" (modal "Select Students" with "Select all" and "Done").
2. Tap a subject. Choose a "Component" chip; the list shows each selected student with a numeric input and the subject total. Entering above the component max shows the warning "Exceeds Maximum" "Cannot exceed max marks (80)." and rejects the value.
3. Save bar "Save Marks (N changed)"; toast "Marks Saved" "Marks saved successfully."; with nothing changed the warning "No Changes" "No marks have been modified.". Only the selected component's changed rows are sent.
4. "Template" downloads the server template (`GET /marks/template`, with `class_id` and `section_id`; on Expo web it saves `marks_template.xlsx`); "Upload CSV" picks a file and posts it to `/marks/upload`. The upload request sends only `subject_config_id`, so the API answers 422 (class_id and section_id are required) and the screen shows "Upload Failed" (KG-8); the picker also accepts CSV, which the backend rejects with 400.
5. Absent students show an "ABS" badge; there is no absent toggle. A section-less class-section cannot load the grid (the request omits `section_id` and gets 422).

**Expected results.**
- Rows in `student_marks` keyed (exam, student, component, attempt 1): `marks_obtained` (null means not entered), `is_absent`, `remark_grade`, `entry_source` always `manual` (also for uploads), `entered_by`, `updated_by` and `updated_at` on updates. Saving writes no audit log entry.
- Students and parents can see the raw marks immediately (F17).

**API endpoints.**
- `GET /exams/{exam_id}/marks` query `class_id`, `section_id` (nil UUID `00000000-0000-0000-0000-000000000000` means no section), `subject_config_id` (all required), `page` (default 1), `page_size` (default 50). Returns a bare array, ordered by admission number: `{student_id, student_name, admission_number, marks:{<component_id>:{mark_id, marks_obtained (number or null), is_absent, remark_grade, updated_at}}}`. Every enrolled student of the class-section is included even with no marks.
- `POST /exams/{exam_id}/marks`: body `{exam_id, subject_config_id, marks:[{student_id, component_id, marks_obtained (>= 0 or null), remark_grade (max 5), is_absent}], attempt_number (>= 1, default 1)}`. Returns all `student_marks` rows of that exam and subject config.
- `GET /exams/{exam_id}/marks/template` query `class_id`, `section_id`, `subject_config_id`: `.xlsx` "Marks Entry" sheet: columns `student_id`, `Roll No`, `Student Name`, then `<component name> (Max: <max>)` per component (for example `Written (Max: 80.00)`), then `Remarks`; one row per enrolled student, pre-filled with existing marks and the text `ABS` for absent components. Filename `marks_template_<exam_id>.xlsx`.
- `POST /exams/{exam_id}/marks/upload` query `class_id`, `section_id`, `subject_config_id`, multipart `file`: returns `{status:"done", written, errors[], total_rows}`.

**Rules and validations.**
- Validation against max marks: before any write, every item with a non-null `marks_obtained` is compared with its component's `max_marks` (when not null). `marks_obtained > max` gives 422 `marks_obtained (<v>) exceeds the component maximum (<max>) for component <id>.` and nothing in the batch is saved. Equal to max is accepted; 0 is accepted; negative is rejected by the schema (422); null means "not entered".
- Components without `max_marks` (remarks components) are not range checked; `remark_grade` is not checked against the component's remark set.
- Upsert key is (payload `exam_id`, student, component, attempt). An existing row has `marks_obtained`, `remark_grade`, `is_absent` overwritten (so omitting `remark_grade` clears it). Authorization uses the path `exam_id` while rows are written with the body `exam_id` (KG-6).
- Not checked: exam status, mark entry deadline, that the component belongs to `subject_config_id`, that the student is enrolled, that `subject_config_id` belongs to the exam. A nonexistent student or component returns 409 `A data conflict occurred while saving marks. Check for duplicate entries.` (foreign key); an unknown `subject_config_id` on save returns 404.
- Absent: `is_absent` true is stored as sent (marks may also be stored). In results (F15) any absent component makes the whole subject absent.
- Stored precision is two decimals (45.678 is stored as 45.68). Marks above the column range fail with 500.
- Excel upload: parsed by `openpyxl` (`.xlsx` only; `.xls` and `.csv` give 400 `Invalid Excel file: ...`). Row 1 is the header. Column A (`student_id`) identifies the student; marks are read from column D onward and matched by the exact header text `<component name> (Max: <max>)`. Blank rows are skipped; a row without `student_id` adds the error `Row N: missing student_id`; an invalid uuid adds `Student <value>: ...`. Empty cells, non-numeric cells and the text `ABS` are skipped. Valid numbers are saved with `is_absent` false and `remark_grade` null (so uploading over an absent cell clears the absent flag). A value above the component max fails the whole file with 422. The `class_id` and `section_id` are required query values but not used. The upload does not call `authorize_mark_entry`.
- Template and grid endpoints list students from `student_admissions` where `current_class_id` equals the class and, when a section is given, `current_section_id` equals it.

**Error and edge cases.**
- Pagination values are not validated: `page_size` 0 returns an empty list, a negative page produces a database error (500).
- Section-less class-sections: web queries are disabled when the section is empty (the grid shows "No students found for this class-section."), mobile omits `section_id` (422).
- Saving on a locked or published exam succeeds.
- Number inputs: web converts the text with `parseFloat`; clearing a cell keeps the existing stored value on save (it does not clear marks).

**Unit-testable logic.**
- `upsert_marks` validation and upsert branches (fake session); `MarkEntryItem` and `MarkEntryCreate` schemas; `parse_excel_upload` (header and row handling, errors); `generate_excel_template` header text; the inline upload header-to-component mapping and numeric parsing; web grid totals (subject total, grand total, absent handling, max rejection) and Excel import matching; mobile `subjectTotalForStudent`, `grandTotalForStudent`, `updateMark` max rule.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-11-U01 | `upsert_marks`: item 80 for a component with max 80 | Accepted | passing |
| TC-EXM-11-U02 | `upsert_marks`: item 80.01 for max 80 | HTTPException 422 `marks_obtained (80.01) exceeds the component maximum (80.0)...`; no row added | passing |
| TC-EXM-11-U03 | `upsert_marks`: item 0 and item `None` | Both accepted; `None` stored as null | passing |
| TC-EXM-11-U04 | `MarkEntryItem(marks_obtained=-0.01)` | Validation error (ge=0) | passing |
| TC-EXM-11-U05 | `upsert_marks`: batch of 3 items where the third exceeds max | 422 and no item written (validation runs before writes) | passing |
| TC-EXM-11-U06 | `upsert_marks`: component with `max_marks=None` (remarks) and marks 1000 | Accepted (no range check) | passing |
| TC-EXM-11-U07 | `upsert_marks`: existing row for (exam, student, component, attempt 1) | Row updated in place: marks, remark_grade, is_absent replaced; `updated_by` and `updated_at` set | passing |
| TC-EXM-11-U08 | `upsert_marks`: no existing row | New row with `entry_source="manual"` and `entered_by` set | passing |
| TC-EXM-11-U09 | `upsert_marks` returns the written count | Equals the number of items | passing |
| TC-EXM-11-U10 | `upsert_marks`: same student and component but `attempt_number` 2 | Separate row from attempt 1 | passing |
| TC-EXM-11-U11 | `upsert_marks`: item with `is_absent=true` and marks 40 | Stored as given (both) | passing |
| TC-EXM-11-U12 | `MarkEntryCreate(marks=[])`, `attempt_number=0` | Both invalid | passing |
| TC-EXM-11-U13 | `MarkEntryItem(remark_grade="ABCDEF")` | Invalid (max 5) | passing |
| TC-EXM-11-U14 | `parse_excel_upload` with a workbook of header `student_id, Roll No, Student Name, Written (Max: 80.00), Remarks` and 2 data rows | `total_rows` 2; each row's `row_data` keyed by `Written (Max: 80.00)` | passing |
| TC-EXM-11-U15 | `parse_excel_upload` row with empty column A | `errors` contains `Row 2: missing student_id`; row skipped | passing |
| TC-EXM-11-U16 | `parse_excel_upload` entirely blank row | Skipped silently | passing |
| TC-EXM-11-U17 | `parse_excel_upload` with non-xlsx bytes | HTTPException 400 `Invalid Excel file: ...` | passing |
| TC-EXM-11-U18 | `generate_excel_template` for components Written 80 and Oral 20 | Headers `student_id`, `Roll No`, `Student Name`, `Written (Max: 80.00)`, `Oral (Max: 20.00)`, `Remarks` | passing |
| TC-EXM-11-U19 | `generate_excel_template` with an absent mark | Cell value `ABS` for that component; entered marks written as numbers | passing |
| TC-EXM-11-U20 | Upload mapping: cell values `"45"`, `""`, `"ABS"`, `"abc"`, `45.5` | 45 kept, empty skipped, ABS skipped, abc skipped, 45.5 kept | passing |
| TC-EXM-11-U21 | Web grid subject total: Written 62 + Oral 18 | 80 of max 100 | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U22 | Web grid subject total with only Written entered (62) | 62 (counts entered cells only; max still 100) | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U23 | Web grid subject total when any component of the subject is absent | Absent: obtained null, shown as `ABS` | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U24 | Web grid grand total: Math 80, Science `ABS`, English 70 | 150 of max 300 (absent subject skipped in obtained, max still counts) | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U25 | Web cell change with value above max (81 vs 80) and value equal (80) | 81 rejected with the warning; 80 accepted | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U26 | Web Excel import: header `Math Written[80]`, values `75`, `81`, `x`, empty | 75 imported; 81 skipped (over max); x skipped; empty ignored; skipped count 2 | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U27 | Mobile `updateMark` with 81 against max 80 | Warning shown; local value unchanged | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-U28 | Mobile `subjectTotalForStudent` with no entered components | null; with Written 62, Oral 18 returns 80 | blocked: logic is inline in web/src/pages/exam/MarkEntryGrid.tsx (U21-U26) or mobile/app/exam/marks.tsx (U27-U28); needs helpers exported |
| TC-EXM-11-A01 | GET grid for EX1 class-section, subject config Math (TEACHER) | 200 array of all enrolled students in admission order; `marks` has one entry per component with `mark_id` null and `marks_obtained` null | passing |
| TC-EXM-11-A02 | GET grid with `section_id` = nil UUID for a section-less class-section | 200; roster of the whole class | passing |
| TC-EXM-11-A03 | GET grid missing `class_id`, `section_id` or `subject_config_id` (parametrised) | 422 each | passing |
| TC-EXM-11-A04 | GET grid with `page_size=1&page=2` | Second student only | passing |
| TC-EXM-11-A05 | GET grid for an unknown `subject_config_id` | 200 with the roster and empty `marks` objects (no 404) | passing |
| TC-EXM-11-A06 | GET grid as ADMIN, TEACHER, STAFF | 200 for all three | passing |
| TC-EXM-11-A07 | GET grid as STUDENT and PARENT | 403 (no `exam_marks:read`) | passing |
| TC-EXM-11-A08 | POST save one student, Written 62 (TEACHER) | 200; response lists `student_marks` rows for the subject config; `entry_source` `manual`; `marks_obtained` `"62.00"` | passing |
| TC-EXM-11-A09 | POST save bulk: 4 students x 2 components | 200; 8 rows | passing |
| TC-EXM-11-A10 | POST save again with different marks | Same row ids; values updated; `updated_at` set | passing |
| TC-EXM-11-A11 | POST marks equal to max (80 of 80) | 200 | passing |
| TC-EXM-11-A12 | POST marks max + 0.01 (80.01) | 422 `exceeds the component maximum`; nothing saved | passing |
| TC-EXM-11-A13 | POST marks max + 1 (81) | 422 | passing |
| TC-EXM-11-A14 | POST marks 0 | 200; stored `"0.00"` | passing |
| TC-EXM-11-A15 | POST marks -1 | 422 | passing |
| TC-EXM-11-A16 | POST marks null (clear) after a value exists | 200; `marks_obtained` null | passing |
| TC-EXM-11-A17 | POST `is_absent: true`, marks null | 200; row `is_absent` true | passing |
| TC-EXM-11-A18 | POST `is_absent: true` with marks 40 | 200; both stored | passing |
| TC-EXM-11-A19 | POST marks 45.678 | 200; stored and returned as `"45.68"` | passing |
| TC-EXM-11-A20 | POST batch where one item exceeds max | 422; none of the batch persisted (re-GET grid shows unchanged) | passing |
| TC-EXM-11-A21 | POST empty `marks`; `attempt_number` 0; `remark_grade` of 6 chars (parametrised) | 422 each | passing |
| TC-EXM-11-A22 | POST with an unknown `component_id`; unknown `student_id` | 409 `A data conflict occurred while saving marks...` | passing |
| TC-EXM-11-A23 | POST with an unknown `subject_config_id` | 404 `ExamSubjectConfig with id ... not found` | passing |
| TC-EXM-11-A24 | POST without `exam_id` in the body | 422 | passing |
| TC-EXM-11-A25 | POST on a published exam | 200 (no status check; documents KG-6) | passing |
| TC-EXM-11-A26 | POST with `attempt_number` 2 for a student and component that already have attempt 1 | New rows are created for attempt 2 (unique per attempt); attempt 1 rows unchanged; response lists rows of both attempts | passing |
| TC-EXM-11-A27 | POST marks to a remarks component (max null) with `remark_grade` "A" | 200; `remark_grade` stored | passing |
| TC-EXM-11-A28 | POST save as STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-11-A29 | POST save as ADMIN and TEACHER | 200 | passing |
| TC-EXM-11-A30 | Saving marks does not create an audit entry | GET `/exams/{id}/audit` has no `mark_entered` row | passing |
| TC-EXM-11-A31 | GET template (TEACHER) | 200, content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; header row as in U18; one row per enrolled student | passing |
| TC-EXM-11-A32 | GET template after marks were saved (one absent) | Entered marks pre-filled as numbers; absent cell `ABS` | passing |
| TC-EXM-11-A33 | GET template missing a required query parameter; unknown `subject_config_id` | 422; 404 `Subject config not found` | passing |
| TC-EXM-11-A34 | GET template as STAFF and ADMIN | 200 | passing |
| TC-EXM-11-A35 | GET template as STUDENT and PARENT | 403 | passing |
| TC-EXM-11-A36 | POST upload of the downloaded template with marks filled for 3 students | 200 `{status:"done", written: 3 x components entered, errors: [], total_rows: 3}`; grid shows the marks | passing |
| TC-EXM-11-A37 | POST upload with a cell `ABS`, an empty cell and a text cell | Those cells skipped; `written` counts only numeric cells; no error entries | passing |
| TC-EXM-11-A38 | POST upload with a value above the component max | 422; no marks from the file saved | passing |
| TC-EXM-11-A39 | POST upload over an absent student's cell with a number | 200; that component's `is_absent` becomes false (clears absence) | passing |
| TC-EXM-11-A40 | POST upload where a row has no `student_id` and another has an invalid uuid | 200; `errors` contains `Row N: missing student_id` and `Student <value>: ...`; valid rows written | passing |
| TC-EXM-11-A41 | POST upload with renamed headers (for example `Written` without `(Max: ...)`) | 200 `{written: 0}` (columns silently ignored) | passing |
| TC-EXM-11-A42 | POST upload with a `.csv` file and with random bytes | 400 `Invalid Excel file: ...` | passing |
| TC-EXM-11-A43 | POST upload without `class_id` or `section_id` or `subject_config_id` | 422 each | passing |
| TC-EXM-11-A44 | POST upload as STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-11-A45 | POST upload as a TEACHER who is not in the delegated permission list while a delegation exists | 200 (upload skips the delegation check; KG-6) | passing |
| TC-EXM-11-A46 | All four endpoints with NOAUTH | 401 each | passing |
| TC-EXM-11-A47 | Tenant isolation: tenant B GET grid with tenant A's exam and config ids | No tenant A students returned (empty roster or empty marks); POST with A's component ids returns 409 or 404, nothing written | passing |
| TC-EXM-11-A48 | Token A with `cschema` B on POST marks | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-11-E01 | P1 | Web | Teacher | TC-EXM-06-E01 done; no active mark permission rows on QA FA1. | 1. Sign in as Teacher.<br>2. Open Exam > Marks.<br>3. Click "Enter Marks" on QA FA1.<br>4. On the summary click "Enter Marks".<br>5. For Advik Mehta type Mathematics Written 62 and Oral 18, English 70, Environmental Studies 90.<br>6. Click "Save Marks".<br>7. Reload the page. | Mathematics Total shows 80 and Grand Total 240; the banner "Unsaved changes for 1 student." shows before saving; toast "Marks saved successfully"; values persist after reload. | planned |
| TC-EXM-11-E02 | P2 | Web | Teacher | Grid of QA FA1 open. | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid.<br>3. Type 81 in a "Written[80]" cell. | Toast "Cannot exceed max marks (80) for Written"; the value is not entered. | planned |
| TC-EXM-11-E03 | P3 | Web | Teacher | Grid of QA FA1 open, no edits. | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid.<br>3. Look at "Save Marks" without editing. | "Save Marks" is disabled (no changed students). | planned |
| TC-EXM-11-E04 | P2 | Web | Teacher | Grid of QA FA1 open. | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid.<br>3. Click "Template". | Toast "Excel downloaded"; an .xlsx named "<exam> <class> <section>.xlsx" with columns Adm#, Student Name, "<Subject> <Component>[max]", subject totals and "Grand Total[300]". | planned |
| TC-EXM-11-E05 | P1 | Web | Teacher | TC-EXM-11-E04 done; template filled with Mathematics Written 70 for Harsha Raju and Nikhil Krishnan. | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid.<br>3. Click "Upload Excel" and choose the filled file.<br>4. Click "Save Marks". | Toast "Imported 2 student rows ... Review and click Save Marks."; cells show as unsaved; after Save toast "Marks saved successfully". | planned |
| TC-EXM-11-E06 | P3 | Web | Teacher | A QA FA1 template with one cell 81 under Mathematics Written[80] and one cell "abc". | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid.<br>3. Click "Upload Excel" and choose the file. | Toast includes "2 cell(s) skipped (invalid or over max marks)"; valid cells are imported. | planned |
| TC-EXM-11-E07 | P3 | Web | Teacher | An .xlsx without an "Adm#" column. | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid.<br>3. Click "Upload Excel" and choose the file. | Error toast starting "Couldn't find an "Adm#" column"; nothing imported. | planned |
| TC-EXM-11-E08 | P3 | Web | Teacher | Harsha Raju has English Written saved with is_absent true on QA FA1 (only POST /exams/<id>/marks can set it, KG-7). | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid. | Every English cell of Harsha Raju shows an "ABS" badge (read-only) and the English total shows ABS. | planned |
| TC-EXM-11-E09 | P2 | Web | Staff | Seeded exam "Half Yearly Examination 2026". | 1. Sign in as Staff.<br>2. Open Exam > Marks > "Half Yearly Examination 2026" > "Enter Marks". | Inputs are read-only; "Upload Excel" and "Save Marks" are hidden. | planned |
| TC-EXM-11-E10 | P2 | Web | Teacher | Same as TC-EXM-10-E06 (a grant exists for another user only). | 1. Sign in as Teacher.<br>2. Open the QA FA1 grid, type a mark, click "Save Marks". | Error toast "You do not have mark entry permission for this exam". | planned |
| TC-EXM-11-E11 | P3 | Web | Teacher | An exam whose class-section has no section (section null). | 1. Sign in as Teacher.<br>2. Open Exam > Marks > that exam > "Enter Marks". | Grid shows "No students found for this class-section." (web queries are disabled for an empty section, KG-17). | planned |
| TC-EXM-11-E12 | P2 | Web | Teacher | Seeded exams (Half Yearly active, both Unit Tests published) and a draft QA exam. | 1. Sign in as Teacher.<br>2. Open Exam > Marks. | "Half Yearly Examination 2026" and draft QA exams are listed with "Enter Marks"; the published Unit Tests are absent. | planned |
| TC-EXM-11-E13 | P2 | Web | Teacher | TC-EXM-06-E01 done (3 students). | 1. Sign in as Teacher.<br>2. Open the QA FA1 summary.<br>3. Untick Nikhil Krishnan.<br>4. Click "Enter Marks". | Grid lists only Advik Mehta and Harsha Raju; the subtitle ends ". 2 selected students". | planned |
| TC-EXM-11-E14 | P1 | Mobile | Teacher | TC-EXM-06-E01 done; no active mark permissions. | 1. Sign in as Teacher.<br>2. Open Exam tab > "Mark Entry".<br>3. Tap the QA FA1 exam chip.<br>4. Tap "Enter Marks" on the Mathematics card.<br>5. Choose the "Written" component chip.<br>6. Enter 62 for Advik Mehta.<br>7. Tap "Save Marks (1 changed)". | Toast "Marks Saved" "Marks saved successfully."; the value is there after reopening. | planned |
| TC-EXM-11-E15 | P2 | Mobile | Teacher | QA FA1 Mathematics Written selected. | 1. Sign in as Teacher.<br>2. Open QA FA1 Mathematics > Written.<br>3. Enter 81 for Harsha Raju. | Warning "Exceeds Maximum" "Cannot exceed max marks (80)."; value rejected. | planned |
| TC-EXM-11-E16 | P3 | Mobile | Teacher | QA FA1 Mathematics Written selected, no edits. | 1. Sign in as Teacher.<br>2. Open QA FA1 Mathematics > Written.<br>3. Tap "Save Marks (0 changed)". | Warning "No Changes" "No marks have been modified." | planned |
| TC-EXM-11-E17 | P2 | Mobile | Teacher | TC-EXM-06-E01 done (3 students). | 1. Sign in as Teacher.<br>2. Open Exam tab > "Mark Entry" > QA FA1.<br>3. Tap "Change" next to "3/3 students selected".<br>4. Untick Nikhil Krishnan and tap "Done". | Counter reads "2/3 students selected"; the component list shows Advik Mehta and Harsha Raju only. | planned |
| TC-EXM-11-E18 | P3 | Mobile | Teacher | QA FA1 Mathematics selected. | 1. Sign in as Teacher.<br>2. Open QA FA1 Mathematics in Mark Entry.<br>3. Tap "Template". | marks_template.xlsx is downloaded (Expo web) or shared (native) with headers student_id, Roll No, Student Name, "Written (Max: 80.00)", "Oral (Max: 20.00)", Remarks. | planned |
| TC-EXM-11-E19 | P2 | Mobile | Teacher | TC-EXM-11-E18 done; template filled. | 1. Sign in as Teacher.<br>2. Open QA FA1 Mathematics in Mark Entry.<br>3. Tap "Upload CSV" and pick the filled .xlsx. | Target: toast "Upload Complete" with the written count. Currently the request omits class_id and section_id, the API answers 422 and the screen shows "Upload Failed" (KG-8). | blocked: KG-8 mobile upload omits class_id and section_id |
| TC-EXM-11-E20 | P3 | Mobile | Teacher | Same absent mark as TC-EXM-11-E08. | 1. Sign in as Teacher.<br>2. Open QA FA1 English > Written in Mark Entry. | Harsha Raju shows an "ABS" badge instead of an input; there is no absent toggle (KG-7). | planned |
| TC-EXM-11-E21 | P2 | Mobile | Staff | Seeded exam "Half Yearly Examination 2026". | 1. Sign in as Staff.<br>2. Open "Half Yearly Examination 2026" on mobile > "Marks". | Subject cards show components and totals but no "Enter Marks" link; no save bar. The Exam tab has no "Mark Entry" tile for Staff. | planned |
| TC-EXM-11-E22 | P3 | Mobile | Student | Seeded student login Advik Mehta (002). | 1. Sign in as Advik Mehta (002).<br>2. Open the Exam tab. | No "Mark Entry" tile. | planned |

API tests implemented in: `backend/tests/api/exam/test_f11_marks.py`

Implemented in: backend/tests/unit/exam/test_marks_entry.py (U01-U20; U20 drives the upload endpoint function with patched dependencies). U21-U28 blocked.

---

## F12 Marks summary

**Purpose.** Before opening the grid, the user picks a class-section and the students to work on, and sees the subjects, components and maximum marks for that class-section.

**Roles and permissions.**
- Read data comes from `exams:read` endpoints (class-sections, subject-configs) plus the Masters students-by-class-section lookup.
- "Enter Marks" is shown to users with `exams:update` or `exam_marks:create`.
- Reached from Exam > Marks > exam (web) and from exam detail > "Marks" tab > "View Summary" (web) or "View Summary" (mobile).

**Preconditions.**
- Exam with at least one class-section and subject configs.

**Steps, web.**
1. Exam > Marks > click an exam (or exam detail > "Marks" > "View Summary"). Page "Mark Entry", subtitle "<exam> . <board> . <type>".
2. Select "Class - Section". The badge shows the subject count.
3. Left panel "Students" with a counter "selected/total", search "Search name or admission #", "Select all", and a checkbox per student (name and admission number). All students start selected.
4. Right panel table: Subject, Components (badges "Written [80]"), Max Marks (sum of included marks components, or "-").
5. "Enter Marks" (badge shows the selected count when fewer than all) opens the grid with only the selected students (stored in sessionStorage). Disabled when no student is selected.
6. States: "No class-sections assigned to this exam." with advice to configure class-sections; amber banner "Unable to load mark entry details" on load errors; "No subjects configured for this class-section."

**Steps, mobile.**
1. Exam detail > "Mark Entry" > "View Summary" (`/exam/marks-summary`). Class-section select, student checklist with search and "Select all", subject table, "Enter Marks" button opens `/exam/marks`.

**Expected results.**
- Display only. The summary shows no completion or entered-count status; it lists configuration.

**API endpoints.**
- `GET /exams/{exam_id}`, `GET /exams/{exam_id}/class-sections`, `GET /exams/{exam_id}/subject-configs` (F06, F07), plus the Masters endpoint for students by class-section.

**Rules and validations.**
- Max Marks per subject = sum of `max_marks` of components with `include_in_total` true and `entry_type` marks.
- Section-less class-sections pass the section as `null` (web path segment `null`).

**Error and edge cases.**
- Empty roster: "No students in this class-section." Search with no match: `No students match "<text>".`
- Exam without subject configs: empty subjects message and "Enter Marks" hidden.

**Unit-testable logic.**
- Per-subject max total (included marks components), select-all and toggle logic, search filter on name and admission number.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-12-U01 | Subject max total: components Written 80 (included), Oral 20 (included), Project 10 (not included), Grade remarks (remarks type) | 100 | blocked: subject max total is inline in web/src/pages/exam/MarkEntrySummary.tsx |
| TC-EXM-12-U02 | Subject max total when no component qualifies | 0 (displayed as a dash) | blocked: subject max total is inline in web/src/pages/exam/MarkEntrySummary.tsx |
| TC-EXM-12-U03 | Student filter by name "ann" and admission "A-00" (case-insensitive) | Matches either field | blocked: student filter is inline in web/src/pages/exam/MarkEntrySummary.tsx |
| TC-EXM-12-U04 | `toggleAll(false)` then `toggleAll(true)` | Empty set, then all ids | blocked: toggleAll is inline in web/src/pages/exam/MarkEntrySummary.tsx |
| TC-EXM-12-A01 | GET class-sections and subject-configs for EX1 as TEACHER and STAFF | 200 each; data sufficient to build the summary (one class-section, three configs) | passing |
| TC-EXM-12-A02 | GET class-sections and subject-configs as STUDENT | 200 (documents exposure; students are not offered this screen) | passing |
| TC-EXM-12-A03 | Tenant isolation: tenant B requests tenant A's class-sections | 404 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-12-E01 | P1 | Web | Teacher | TC-EXM-06-E01 done. | 1. Sign in as Teacher.<br>2. Open Exam > Marks.<br>3. Click "Enter Marks" on QA FA1. | Page "Mark Entry" with subtitle "QA FA1 . State . QA FA1"; Class 1 - 1-B selected; Advik Mehta, Harsha Raju and Nikhil Krishnan ticked with counter 3/3; the table lists Mathematics (Written [80], Oral [20], Max 100), English (100), Environmental Studies (100). | planned |
| TC-EXM-12-E02 | P2 | Web | Teacher | TC-EXM-06-E01 done. | 1. Sign in as Teacher.<br>2. Open the QA FA1 summary.<br>3. Untick Nikhil Krishnan.<br>4. Click "Enter Marks". | The button badge shows 2; the grid lists Advik Mehta and Harsha Raju. | planned |
| TC-EXM-12-E03 | P3 | Web | Teacher | TC-EXM-06-E01 done. | 1. Sign in as Teacher.<br>2. Open the QA FA1 summary.<br>3. Click "Select all" twice.<br>4. Type "xyz" in "Search name or admission #". | Counter goes 0/3 then 3/3; the search shows "No students match "xyz"." | planned |
| TC-EXM-12-E04 | P3 | Web | Teacher | TC-EXM-06-E01 done. | 1. Sign in as Teacher.<br>2. Open the QA FA1 summary.<br>3. Untick all students. | "Enter Marks" is disabled. | planned |
| TC-EXM-12-E05 | P3 | Web | Admin | An exam with no class-sections ("Copy of QA FA1" from TC-EXM-09-E05). | 1. Sign in as Admin.<br>2. Open Exam > Marks.<br>3. Click "Enter Marks" on "Copy of QA FA1". | Message "No class-sections assigned to this exam." | planned |
| TC-EXM-12-E06 | P2 | Web | Staff | Seeded exam "Half Yearly Examination 2026". | 1. Sign in as Staff.<br>2. Open Exam > Marks > "Half Yearly Examination 2026". | The summary is shown without an "Enter Marks" button. | planned |
| TC-EXM-12-E07 | P2 | Web | Teacher | Seeded exam "Half Yearly Examination 2026" (10 class-sections). | 1. Sign in as Teacher.<br>2. Open Exam > Marks > "Enter Marks" on "Half Yearly Examination 2026".<br>3. Change the "Class - Section" select to Class 2 - 2-A. | The student list and subjects table reload for Class 2 - 2-A (Written 80 and Internal Assessment 20 per subject). | planned |
| TC-EXM-12-E08 | P1 | Mobile | Teacher | TC-EXM-06-E01 done. | 1. Sign in as Teacher.<br>2. Open QA FA1 on mobile > "Marks" tab > "View Summary". | Screen "Mark Entry" with exam, board and type, Class and Section, "Students 3/3", "Select all", search "Search name or admission #", subject list with max marks and components. | planned |
| TC-EXM-12-E09 | P2 | Mobile | Teacher | TC-EXM-12-E08 open. | 1. Sign in as Teacher.<br>2. On the summary tap "Enter Marks". | Opens /exam/marks for QA FA1 with the selected students. | planned |

API tests implemented in: `backend/tests/api/exam/test_f12_f18_f19_summary_audit_notify.py`

All U cases blocked (logic is inline in web/src/pages/exam/MarkEntrySummary.tsx).

---

## F13 Hall ticket eligibility

**Purpose.** For an exam, find which enrolled students may sit it, based on attendance and fee payment, review the lists, and let an admin override a failed check.

**Roles and permissions.**
- Compute, override: `exams:update`. Lists (enrolled, eligible, ineligible): `exams:read`.
- Menu: Exam > Hall Tickets (all roles; student and parent views are different, see rules). Mobile: Exam tab > "Hall Tickets" (tile requires `exams:read`).

**Preconditions.**
- Exam with class-sections and enrolled students. For the attendance check: exam `attendance_from_date` and `attendance_to_date` set, attendance records in `student_attendance`. For the fee check: `hall_ticket_min_fee_paid_pct` set in Exam settings (F01) and fee mappings and completed transactions for the exam's academic year.

**Steps, web.**
1. Exam > Hall Tickets (`/exam/hall-tickets`, title "Hall Tickets", subtitle "Manage eligibility and download hall tickets for each exam"). Draft exams are not listed. Click an exam.
2. Admin view "Hall Tickets - <exam>": cards "Total Students", "Eligible", "Ineligible"; buttons "Back", "Recompute" (needs `exams:update`; toast "Eligibility computed successfully"), "Publish Hall Tickets" (F14), "Download" (F14).
3. Tabs "All Students" (enrolled list), "Eligible", "Ineligible", each with search "Search by student name or admission number...". The tables show Attendance and Fee icons (an "Override" badge when overridden), Eligible badge and Reasons ("Fee payment pending", "Attendance below requirement", "Fee pending and low attendance").
4. On the "Ineligible" tab the Override column has "Attendance" (when attendance failed) and "Fee" (when fee failed) buttons. Each click sends one override flag and the student moves to "Eligible" when both checks then pass. Buttons disable once set; there is no way to remove an override on web.
5. Student role opens `/exam/hall-tickets/{id}` ("Hall Ticket - <exam>", "Your hall ticket eligibility status"): intended card "You are eligible for the hall ticket" or "You are not eligible...", Hall Ticket No, Attendance %, Fee Status; Parent role: same for the selected child. The page reads the eligible and ineligible lists, which now return 403 for Student and Parent, so it always shows "You are not enrolled in this exam." ("<child> is not enrolled in this exam." for a parent) (KG-21).

**Steps, mobile.**
1. Exam > "Hall Tickets": list of non-draft exams; "Manage" opens `/exam/hall-tickets/<id>`.
2. Admin and staff view: counters "<n> eligible" and "<n> ineligible", tabs "Eligible (n)" and "Ineligible (n)", header buttons "Compute" (also "Compute Eligibility" on the empty state "No eligible students found"), "Publish" and "Download All" (Teacher and Staff see only "Download All"). "Compute" (confirm "Check attendance and fee status for all students?"), publish and download (F14). Each student card shows status, attendance %, Fee Paid or Unpaid, an "Overridden" tag, reason, and a button "Mark Eligible" or "Mark Ineligible" (needs `exams:update`; confirm "Override <name> to eligible?"; toast "Eligibility Updated").
3. "Mark Eligible" sends both overrides true; "Mark Ineligible" sends both false, which removes overrides but cannot make a student ineligible who genuinely passes both checks.
4. Student and Parent: read-only card as on web; it also shows "You are not enrolled in this exam." because the lists return 403 (KG-21).

**Expected results.**
- One `hall_ticket_eligibility` row per (exam, student): `attendance_percent`, `attendance_ok`, `fee_paid`, `attendance_override`, `fee_override`, `ineligibility_reason`, `is_eligible`, `hall_ticket_number`, `computed_at`.
- Audit rows `hall_tickets_computed` (counts) and `eligibility_overridden` (student id, flags, final eligibility).

**API endpoints.**
- `GET /exams/{exam_id}/hall-tickets/enrolled-students`: `[{student_id, class_id, section_id, student_name, admission_number}]`, no compute needed, ordered by name.
- `POST /exams/{exam_id}/hall-tickets/compute`: returns `{exam_id, total_students, eligible, ineligible}`.
- `GET /exams/{exam_id}/hall-tickets/eligible` and `.../ineligible`: `HallTicketEligibilityRead` list plus `student_name` and `admission_number`, ordered by hall ticket number (nulls last) then name.
- `PUT /exams/{exam_id}/hall-tickets/{student_id}/override`: body `{attendance_override: bool=false, fee_override: bool=false}`; returns the updated row.

**Rules and validations (exact calculations, `hall_ticket_service.compute_eligibility`).**
1. Students: distinct students enrolled (`student_admissions.current_class_id`, and `current_section_id` when the exam class-section has a section) in any class-section of the exam. No students: returns zero counts.
2. Minimum attendance: `hall_ticket_min_attendance` from Exam settings when set and not 0, otherwise 75.00. The exam's own `hall_ticket_min_attendance` field is not used (KG-11).
3. Attendance check: if the exam lacks `attendance_from_date` or `attendance_to_date`, the check is skipped (`attendance_percent` null, `attendance_ok` true). Otherwise `attendance_percent = (count of records with status 'present') * 100 / (count of all records between the two dates inclusive)`; no records gives null and `attendance_ok` false. `attendance_ok = percent >= minimum` (equal passes). Statuses `late` and `half_day` count as not present.
4. Fee check: if `hall_ticket_min_fee_paid_pct` is null the check is skipped (`fee_paid` true). Otherwise `fee_pct = completed transactions total_amount / assigned total_fee * 100` for the exam's academic year, 0 when nothing is assigned; `fee_paid = fee_pct >= minimum` (equal passes; a minimum of 0 always passes).
5. Existing overrides are applied: final attendance ok = `attendance_ok` OR `attendance_override`; final fee ok = `fee_paid` OR `fee_override`. `is_eligible` = both final values true.
6. Reason: both failing gives `BOTH`; only attendance `LOW_ATTENDANCE`; only fee `FEE_PENDING`; eligible gives null.
7. Hall ticket number for eligible students: `HT-2025-` plus the student's 1-based position in the unordered enrolled list, zero-padded to 4 digits (for example `HT-2025-0007`); not unique across exams, the year is fixed, positions count ineligible students too, numbers can change on every recompute (KG-13). Ineligible students get null.
8. Rows are created or updated (never deleted); `attendance_ok` and `fee_paid` store the raw check results without overrides. Recompute keeps overrides.
9. Override endpoint: sets `attendance_override` and `fee_override` from the body (both flags are replaced; an omitted flag becomes false), then `is_eligible = (attendance_ok OR attendance_override) AND (fee_paid OR fee_override)` and recomputes the reason. It does not assign a hall ticket number, so a newly eligible student has a null number until the next compute (KG-13). 404 `Eligibility record not found. Run compute first.` when no row exists.
10. No exam status check.

Worked examples (minimum attendance 75, minimum fee 50):

| Student | Attendance records | Fee | Attendance % | Fee % | Result |
|---|---|---|---|---|---|
| S1 | 72 present of 80 | assigned 10000, paid 8000 | 90.00 | 80.00 | eligible, number `HT-2025-nnnn` |
| S2 | 60 present of 80 | paid 5000 of 10000 | 75.00 (equal passes) | 50.00 (equal passes) | eligible |
| S3 | 59 present of 80 | paid 8000 of 10000 | 73.75 | 80.00 | `LOW_ATTENDANCE` |
| S4 | 72 of 80 | paid 4999.99 of 10000 | 90.00 | 49.9999 | `FEE_PENDING` |
| S5 | 40 of 80 | no fee mapping | 50.00 | 0 | `BOTH` |
| S6 | 30 present, 20 late of 80 | paid 8000 of 10000 | 37.50 (late not counted) | 80.00 | `LOW_ATTENDANCE` |
| S3 after override `{attendance_override:true}` | | | | | eligible, number null |
| S5 after override `{attendance_override:true}` | | | | | still `FEE_PENDING` |
| S5 after override `{attendance_override:true, fee_override:true}` | | | | | eligible |
| S5 then override `{fee_override:true}` only | | | | | `LOW_ATTENDANCE` (attendance override replaced by false) |

**Error and edge cases.**
- Exam without attendance dates: everyone passes the attendance check.
- Recompute after enrollment changes: students who left the class-section keep their old row (not removed).
- Student and Parent get 403 `Not allowed for this role` on the eligible and ineligible lists; `enrolled-students` stays readable to them (KG-3).
- Override for a student who is not in the exam: 404.

**Unit-testable logic.**
- `compute_eligibility` with patched helper functions (attendance, fee, enrolled students) and fake rows: thresholds, equality, skipped checks, overrides, reasons, numbering; `_generate_hall_ticket_number`; `override_eligibility`; settings fallback of 75.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-13-U01 | Attendance 90.00 vs minimum 75 | `attendance_ok` true | passing |
| TC-EXM-13-U02 | Attendance exactly 75.00 vs minimum 75 | true (>=) | passing |
| TC-EXM-13-U03 | Attendance 73.75 vs minimum 75 | false | passing |
| TC-EXM-13-U04 | Attendance None (no records) with dates configured | `attendance_ok` false | passing |
| TC-EXM-13-U05 | Exam without `attendance_from_date` or `attendance_to_date` | Check skipped: percent None, `attendance_ok` true | passing |
| TC-EXM-13-U06 | Settings row missing; settings `hall_ticket_min_attendance` None; settings 0 | Minimum 75.00 in all three cases | passing |
| TC-EXM-13-U07 | Settings `hall_ticket_min_attendance` 80 and attendance 78 | `attendance_ok` false | passing |
| TC-EXM-13-U08 | Fee minimum None | `fee_paid` true; fee helper not called | passing |
| TC-EXM-13-U09 | Fee minimum 50, pct 50.00 and 49.9999 | true, then false | passing |
| TC-EXM-13-U10 | Fee minimum 50 and no fee assigned | pct 0; `fee_paid` false | passing |
| TC-EXM-13-U11 | Fee minimum 0 and pct 0 | `fee_paid` true | passing |
| TC-EXM-13-U12 | Reasons: (att ok, fee ok), (att bad, fee ok), (att ok, fee bad), (both bad) | null, `LOW_ATTENDANCE`, `FEE_PENDING`, `BOTH` | passing |
| TC-EXM-13-U13 | Existing row with `attendance_override` true and attendance bad, fee ok | `is_eligible` true; stored `attendance_ok` still false | passing |
| TC-EXM-13-U14 | Existing row with both overrides true and both checks bad | eligible; reason null | passing |
| TC-EXM-13-U15 | `_generate_hall_ticket_number(exam, 7)` / `(exam, 1234)` / `(exam, 12345)` | `HT-2025-0007` / `HT-2025-1234` / `HT-2025-12345` | passing |
| TC-EXM-13-U16 | Numbering: students [ineligible, eligible, eligible] | Eligible students get `HT-2025-0002` and `HT-2025-0003`; ineligible None | passing |
| TC-EXM-13-U17 | `override_eligibility` `(true, false)` on a row with `attendance_ok` false and `fee_paid` true | `is_eligible` true, reason None | passing |
| TC-EXM-13-U18 | `override_eligibility` `(false, true)` on a row with attendance bad and fee bad | `is_eligible` false, reason `LOW_ATTENDANCE` | passing |
| TC-EXM-13-U19 | `override_eligibility` for a missing row | 404 `Eligibility record not found. Run compute first.` | passing |
| TC-EXM-13-U20 | `override_eligibility` second call with fewer flags | Flags replaced (not merged) | passing |
| TC-EXM-13-U21 | `compute_eligibility` with no enrolled students | `{total_students: 0, eligible: 0, ineligible: 0}` | passing |
| TC-EXM-13-U22 | Attendance helper result `Decimal('73.7500000000')` from the SQL percentage, minimum 75 | Compared as a Decimal: `attendance_ok` false; stored value fits Numeric(5,2) | passing |
| TC-EXM-13-A01 | POST compute for EX1 with S1..S4 set up as the worked examples (ADMIN) | 200 `{total_students: 4, eligible: n, ineligible: m}` matching the setup | passing |
| TC-EXM-13-A02 | GET eligible and GET ineligible after compute | Each row has `student_name`, `admission_number`, `attendance_percent`, `attendance_ok`, `fee_paid`, `is_eligible`, `ineligibility_reason`; eligible rows have `hall_ticket_number` matching `HT-2025-\d{4}` | passing |
| TC-EXM-13-A03 | POST compute twice | Second call updates the same rows (no duplicates); counts unchanged | passing |
| TC-EXM-13-A04 | POST compute with no min fee in settings | `fee_paid` true for all | passing |
| TC-EXM-13-A05 | POST compute for an exam without attendance dates | `attendance_ok` true for all; `attendance_percent` null | passing |
| TC-EXM-13-A06 | POST compute unknown exam | 404 | passing |
| TC-EXM-13-A07 | POST compute for a draft exam | 200 (no status check) | passing |
| TC-EXM-13-A08 | POST compute writes an audit row | GET audit shows `hall_tickets_computed` with metadata counts | passing |
| TC-EXM-13-A09 | GET enrolled-students | Distinct students across the exam's class-sections with names and admission numbers, ordered by name; works before compute | passing |
| TC-EXM-13-A10 | PUT override `{attendance_override: true}` for S3 (LOW_ATTENDANCE) | 200; `is_eligible` true; `attendance_override` true | passing |
| TC-EXM-13-A11 | PUT override `{attendance_override: true}` for S5 (BOTH) | 200; `is_eligible` false; reason `FEE_PENDING` | passing |
| TC-EXM-13-A12 | PUT override `{}` for an overridden student | 200; both flags false; eligibility recomputed from raw checks | passing |
| TC-EXM-13-A13 | PUT override before any compute | 404 `Eligibility record not found. Run compute first.` | passing |
| TC-EXM-13-A14 | PUT override then recompute | Override flags kept; `is_eligible` still true | passing |
| TC-EXM-13-A15 | PUT override writes an audit row | `eligibility_overridden` with `student_id` and `final_eligible` | passing |
| TC-EXM-13-A16 | Override of S3 then GET eligible | S3 listed with `hall_ticket_number` null until recompute (KG-13) | passing |
| TC-EXM-13-A17 | Compute and override as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-13-A18 | GET enrolled-students, eligible, ineligible as all five roles | 200 for all (STUDENT and PARENT receive all students; documents KG-3) | passing |
| TC-EXM-13-A19 | All four endpoint groups with NOAUTH | 401 each | passing |
| TC-EXM-13-A20 | Tenant isolation: tenant B GET eligible for tenant A's exam id; PUT override | Empty list; 404 | passing |
| TC-EXM-13-A21 | Token A with `cschema` B on POST compute | 403 | passing |
| TC-EXM-13-A22 | Student S6 with 30 present and 20 late records of 80 (attendance window), minimum 75 | `attendance_percent` 37.50 (late not counted); reason `LOW_ATTENDANCE` | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-13-E01 | P1 | Web | Admin | QA FA1 with "Attendance From" 2026-09-25 and "Attendance To" 2026-10-01 (set with Edit) and Exam Settings "Minimum Attendance %" 90 (seeded 60; restore afterwards). Seeded attendance gives Advik Mehta and Harsha Raju 80.00 and Nikhil Krishnan 100.00 in that window. | 1. Sign in as Admin.<br>2. Open Exam > Hall Tickets.<br>3. Click "Manage" on QA FA1.<br>4. Click "Recompute". | Toast "Eligibility computed successfully"; cards Total Students 3, Eligible 1 (Nikhil Krishnan), Ineligible 2. | planned |
| TC-EXM-13-E02 | P2 | Web | Admin | TC-EXM-13-E01 done. | 1. Sign in as Admin.<br>2. Open the QA FA1 hall ticket page.<br>3. Open tab "Ineligible". | Advik Mehta shows the Attendance cross icon, attendance 80.00, reason "Attendance below requirement" and an Override button "Attendance". | planned |
| TC-EXM-13-E03 | P1 | Web | Admin | TC-EXM-13-E02 done. | 1. Sign in as Admin.<br>2. On the "Ineligible" tab click "Attendance" for Advik Mehta.<br>3. Open tab "Eligible". | Advik Mehta is listed as eligible with an "Override" badge in the Attendance column; his hall ticket number stays empty until the next recompute (KG-13). | planned |
| TC-EXM-13-E04 | P3 | Web | Admin | TC-EXM-13-E01 done with Exam Settings "Minimum Fee Paid %" 100 as well (restore empty), so Harsha Raju fails both checks ("Fee pending and low attendance"). | 1. Sign in as Admin.<br>2. On "Ineligible" click "Fee" for Harsha Raju.<br>3. Click "Attendance" for Harsha Raju. | After the second click the fee override is lost because each call replaces both flags (KG-13); Harsha Raju shows "Fee payment pending". | planned |
| TC-EXM-13-E05 | P3 | Web | Admin | Seeded hall tickets of "Half Yearly Examination 2026" (21 eligible, published). | 1. Sign in as Admin.<br>2. Open Exam > Hall Tickets > "Manage" on "Half Yearly Examination 2026".<br>3. Open tab "Eligible".<br>4. Type "001" in "Search by student name or admission number...". | The list narrows to Karthik Reddy (001). | planned |
| TC-EXM-13-E06 | P3 | Web | Admin | A draft QA exam exists (TC-EXM-09-E05). | 1. Sign in as Admin.<br>2. Open Exam > Hall Tickets. | Draft exams are not listed; each listed exam has "Manage". | planned |
| TC-EXM-13-E07 | P2 | Web | Teacher | Seeded hall tickets of "Half Yearly Examination 2026". | 1. Sign in as Teacher.<br>2. Open Exam > Hall Tickets > "Manage" on "Half Yearly Examination 2026". | "Recompute", "Publish Hall Tickets" and the Override column are hidden; the lists are visible. | planned |
| TC-EXM-13-E08 | P2 | Web | Student | Seeded student login Karthik Reddy (001), eligible for "Half Yearly Examination 2026" (HT-2025-0005). | 1. Sign in as Karthik Reddy (001).<br>2. Open Exam > Hall Tickets.<br>3. Click "Manage" on "Half Yearly Examination 2026". | Target: card "You are eligible for the hall ticket" (or not eligible) with Hall Ticket No, Attendance % and Fee Status for the signed-in student. Currently the eligible and ineligible lists return 403 for Student, so the page always shows "You are not enrolled in this exam." (KG-21). | blocked: KG-21 student hall ticket view reads lists that now return 403 |
| TC-EXM-13-E09 | P2 | Web | Parent | Seeded parent login of Harsha Raju (004, Class 1 / 1-B) and Tanvi Raju (005, Class 4) (the QA Parent login has no linked child); both children are eligible for "Half Yearly Examination 2026". | 1. Sign in as the parent of Harsha and Tanvi Raju.<br>2. Select Harsha Raju.<br>3. Open Exam > Hall Tickets > "Manage" on "Half Yearly Examination 2026". | Target: card for that child. Currently the lists return 403 for Parent and the page shows "<child> is not enrolled in this exam." (KG-21). | blocked: KG-21 parent hall ticket view reads lists that now return 403 |
| TC-EXM-13-E10 | P1 | Mobile | Admin | QA FA1 with "Attendance From" 2026-09-25 and "Attendance To" 2026-10-01 (set with Edit) and Exam Settings "Minimum Attendance %" 90 (seeded 60; restore afterwards). Seeded attendance gives Advik Mehta and Harsha Raju 80.00 and Nikhil Krishnan 100.00 in that window; no compute yet on QA FA1. | 1. Sign in as Admin.<br>2. Open Exam tab > "Hall Tickets".<br>3. Tap "Manage" on QA FA1.<br>4. Tap "Compute" (or "Compute Eligibility" on the empty state) and confirm. | Toast "Eligibility Computed"; the counters "<n> eligible" and "<n> ineligible" and the tabs "Eligible (n)" and "Ineligible (n)" fill. | planned |
| TC-EXM-13-E11 | P2 | Mobile | Admin | TC-EXM-13-E10 done; Advik Mehta ineligible. | 1. Sign in as Admin.<br>2. Open the "Ineligible" tab.<br>3. Tap "Mark Eligible" on Advik Mehta.<br>4. Confirm "Override". | Toast "Eligibility Updated"; Advik Mehta moves to Eligible with an "Overridden" tag. | planned |
| TC-EXM-13-E12 | P3 | Mobile | Admin | TC-EXM-13-E10 done; Nikhil Krishnan genuinely eligible. | 1. Sign in as Admin.<br>2. Open the "Eligible" tab.<br>3. Tap "Mark Ineligible" on Nikhil Krishnan and confirm "Override". | Nikhil Krishnan stays eligible (only overrides are cleared, KG-13). | planned |
| TC-EXM-13-E13 | P2 | Mobile | Teacher | Seeded hall tickets of "Half Yearly Examination 2026". | 1. Sign in as Teacher.<br>2. Open Exam tab > "Hall Tickets" > "Manage" on "Half Yearly Examination 2026". | Only "Download All" is offered; "Compute", "Publish", "Mark Eligible" and "Mark Ineligible" are hidden. | planned |
| TC-EXM-13-E14 | P2 | Mobile | Student | Seeded student login Karthik Reddy (001), eligible for "Half Yearly Examination 2026". | 1. Sign in as Karthik Reddy (001).<br>2. Open Exam tab > "Hall Tickets" > "Half Yearly Examination 2026". | Target: self-service card with eligibility, Attendance and Fee Status. Currently "You are not enrolled in this exam." because the lists return 403 (KG-21). | blocked: KG-21 student hall ticket view reads lists that now return 403 |

API tests implemented in: `backend/tests/api/exam/test_f13_f14_hall_tickets.py`

Implemented in: backend/tests/unit/exam/test_hall_tickets.py.

---

## F14 Hall ticket publish and download

**Purpose.** Admin makes hall tickets available and downloads one student's ticket as a PDF or all eligible tickets as a ZIP; students and parents download their own.

**Roles and permissions.**
- Publish: `exams:update`. Download one and download all: `exams:read`. Download-all returns 403 for Student and Parent; download one is limited to the own record (Student) or a linked child (Parent).
- Web: button "Publish Hall Tickets" and "Download" on the admin hall ticket page; page `/exam/hall-tickets/{id}/download`. Mobile: "Publish" and "Download All" on the hall tickets screen; `/exam/hall-ticket-download` lists eligible tickets.

**Preconditions.**
- Eligibility computed (F13); the student must be eligible for a PDF.

**Steps, web.**
1. Admin hall ticket page > "Publish Hall Tickets" > confirm "Publish Hall Tickets?" (text "This will make hall tickets visible to eligible students for <exam>."). Toast "Hall tickets published successfully". The exam detail card "Hall Ticket Status" changes to "Published".
2. "Download" opens "Download Hall Tickets - <exam>" with "<n> eligible students", search, columns Student, Adm#, Class / Section. "Preview" opens a "Hall Ticket Preview" dialog with the hall ticket card (exam, student, hall ticket number, schedule). "PDF" downloads one ticket (toast "Downloaded"). "Download All" (toast "Hall tickets downloaded") saves the ZIP as `hall-tickets-<exam name>.pdf` (KG-9). One ticket is saved as `hall-ticket-<admission no>.pdf`.
3. Student and Parent: after publication the eligibility card shows "Download Hall Ticket" (only when eligible and published); before publication "Hall tickets have not been published yet. Check back later." This gating is client-side only. The card never loads at present (KG-21).

**Steps, mobile.**
1. Hall tickets screen > "Publish" (confirm "Publish hall tickets to all eligible students?"; toast "Hall Tickets Published"). "Download All" (confirm "Download all eligible hall tickets as ZIP?") saves `hall_tickets_<examId>.zip`; each eligible card has "Download PDF" (file `hall-ticket.pdf` or `hall_ticket_<studentId>.pdf`). Student and Parent cards show "Download Hall Ticket".

**Expected results.**
- `exams.hall_ticket_published` true and `hall_ticket_published_at` set; audit row `hall_tickets_published`.
- A PDF (A4) with school name (first organization name, else "School"), title "HALL TICKET", exam name, a table Hall Ticket No., Student Name, Admission No., Class & Section, an "Examination Schedule" table (Subject, Date `dd-mm-yyyy`, Start, End, Venue with default "Main Hall") built from `exam_dates` of the student's class (and section, or section-less dates), four instruction lines and signature lines. With no dates: "No exam dates configured yet."

**API endpoints.**
- `POST /exams/{exam_id}/hall-tickets/publish`: returns `{exam_id, hall_ticket_published, hall_ticket_published_at}`.
- `GET /exams/{exam_id}/hall-tickets/download?student_id=<uuid>`: `application/pdf`, filename `hall-ticket-<student_id>.pdf`.
- `GET /exams/{exam_id}/hall-tickets/download-all`: `application/zip`, filename `hall-tickets-<exam_id>.zip`, containing `hall-ticket-<hall ticket number>.pdf` per eligible student (a student that fails to render is skipped silently).

**Rules and validations.**
- Publish sets the flag and timestamp every time it is called (repeatable; the timestamp is overwritten). It does not require compute, a status, or any eligible student, and there is no unpublish.
- Download one: `student_id` required (422); no eligibility row gives 404 `Hall ticket not found. Run compute first.`; not eligible gives 403 `Student is not eligible for a hall ticket.`; student not found 404. The published flag is not checked. A Student may download only their own ticket and a Parent only a linked child's (`ensure_student_access`, 403 otherwise).
- Download all: 404 `No eligible students found. Run compute first.` when none eligible.
- A student whose override made them eligible but who has no number prints "-" for Hall Ticket No.

**Error and edge cases.**
- Unknown exam on publish: 404. Unknown exam on download: 404 from the eligibility lookup.
- Download before publication works (the published flag is not enforced, KG-13).

**Unit-testable logic.**
- `publish_hall_tickets` flag and timestamp; `_build_pdf` content (starts with `%PDF`, includes number, name, schedule rows) using a data dict; `_load_hall_ticket_data` error mapping (404, 403) with fakes; ZIP assembly skipping failures.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-14-U01 | `publish_hall_tickets` on an exam | `hall_ticket_published` True and `hall_ticket_published_at` set | passing |
| TC-EXM-14-U02 | `publish_hall_tickets` called twice | Still True; timestamp refreshed | passing |
| TC-EXM-14-U03 | `_build_pdf` with a data dict of 2 schedule rows | Bytes start with `%PDF`; non-empty | passing |
| TC-EXM-14-U04 | `_build_pdf` with no schedule rows and number None | Builds; contains the fallback text and a dash for the number | passing |
| TC-EXM-14-U05 | `_load_hall_ticket_data` with no eligibility row | HTTPException 404 `Hall ticket not found. Run compute first.` | passing |
| TC-EXM-14-U06 | `_load_hall_ticket_data` with `is_eligible` False | HTTPException 403 `Student is not eligible for a hall ticket.` | passing |
| TC-EXM-14-U07 | `generate_all_hall_tickets_zip` with 3 eligible rows, one render raising | ZIP with 2 entries | passing |
| TC-EXM-14-U08 | `generate_all_hall_tickets_zip` with no eligible rows | HTTPException 404 | passing |
| TC-EXM-14-U09 | ZIP entry naming | `hall-ticket-<HT number>.pdf`; student id used when the number is null | passing |
| TC-EXM-14-A01 | POST publish after compute (ADMIN) | 200 `hall_ticket_published` true with a timestamp; GET exam shows the same | passing |
| TC-EXM-14-A02 | POST publish twice | 200 both times; second timestamp later or equal | passing |
| TC-EXM-14-A03 | POST publish before any compute | 200 (no precondition) | passing |
| TC-EXM-14-A04 | POST publish unknown exam | 404 | passing |
| TC-EXM-14-A05 | POST publish writes an audit row | `hall_tickets_published` present | passing |
| TC-EXM-14-A06 | GET download for an eligible student (ADMIN) | 200 `application/pdf`; body starts with `%PDF`; `Content-Disposition` filename `hall-ticket-<student_id>.pdf` | passing |
| TC-EXM-14-A07 | GET download for an ineligible student | 403 `Student is not eligible for a hall ticket.` | passing |
| TC-EXM-14-A08 | GET download for a student with no eligibility row | 404 | passing |
| TC-EXM-14-A09 | GET download without `student_id` | 422 | passing |
| TC-EXM-14-A10 | GET download for a student whose class has exam dates | PDF is produced (schedule content verified by text extraction: subject names and `dd-mm-yyyy` dates) | passing |
| TC-EXM-14-A11 | GET download before publish | 200 (the published flag is not enforced; documents KG-13) | passing |
| TC-EXM-14-A12 | GET download-all with 3 eligible students | 200 `application/zip`; archive has 3 PDFs named by hall ticket number | passing |
| TC-EXM-14-A13 | GET download-all with no eligible students | 404 `No eligible students found. Run compute first.` | passing |
| TC-EXM-14-A14 | GET download as STUDENT for another student's id | 200 (exposure; documents KG-3; target 403) | passing |
| TC-EXM-14-A15 | POST publish as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-14-A16 | GET download and download-all as ADMIN, TEACHER, STAFF, STUDENT, PARENT | 200 for all (`exams:read`) | passing |
| TC-EXM-14-A17 | All three endpoints with NOAUTH | 401 each | passing |
| TC-EXM-14-A18 | Tenant isolation: tenant B download for tenant A's exam and student | 404 | passing |
| TC-EXM-14-A19 | Token A with `cschema` B on publish | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-14-E01 | P1 | Web | Admin | TC-EXM-13-E01 done. | 1. Sign in as Admin.<br>2. Open the QA FA1 hall ticket page.<br>3. Click "Publish Hall Tickets".<br>4. Click "Publish" in "Publish Hall Tickets?".<br>5. Open the QA FA1 detail Overview. | Toast "Hall tickets published successfully"; the "Hall Ticket Status" card shows "Published". | planned |
| TC-EXM-14-E02 | P2 | Web | Admin | Seeded hall tickets of "Half Yearly Examination 2026" (21 eligible). | 1. Sign in as Admin.<br>2. Open the "Half Yearly Examination 2026" hall ticket page.<br>3. Click "Download".<br>4. Click "Preview" on Karthik Reddy. | Page "Download Hall Tickets - Half Yearly Examination 2026" with "21 eligible students"; dialog "Hall Ticket Preview" with the exam, Karthik Reddy, HT-2025-0005 and the schedule. | planned |
| TC-EXM-14-E03 | P1 | Web | Admin | Seeded hall tickets of "Half Yearly Examination 2026". | 1. Sign in as Admin.<br>2. Open the "Half Yearly Examination 2026" download page.<br>3. Click "PDF" on Karthik Reddy. | File "hall-ticket-001.pdf" downloads and opens as a PDF with HALL TICKET, the student details and the Class 1 schedule; toast "Downloaded". | planned |
| TC-EXM-14-E04 | P3 | Web | Admin | Seeded hall tickets of "Half Yearly Examination 2026". | 1. Sign in as Admin.<br>2. Open the "Half Yearly Examination 2026" download page.<br>3. Click "Download All". | Toast "Hall tickets downloaded"; the file is named "hall-tickets-Half Yearly Examination 2026.pdf" but its content is a ZIP of 21 PDFs (KG-9). | planned |
| TC-EXM-14-E05 | P3 | Web | Admin | Seeded exam "Unit Test 1 - Class 1B" (no hall ticket compute). | 1. Sign in as Admin.<br>2. Open /exam/hall-tickets/<Unit Test 1 - Class 1B id>/download. | "No eligible students found." and "Download All" disabled. | planned |
| TC-EXM-14-E06 | P2 | Web | Student | Seeded student login Karthik Reddy (001); "Half Yearly Examination 2026" hall tickets are published and he is eligible. | 1. Sign in as Karthik Reddy (001).<br>2. Open Exam > Hall Tickets > "Half Yearly Examination 2026".<br>3. Click "Download Hall Ticket". | Target: PDF downloads; toast "Hall ticket downloaded". Blocked: the card never loads for students (KG-21). | blocked: KG-21 student hall ticket view reads lists that now return 403 |
| TC-EXM-14-E07 | P3 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); TC-EXM-13-E01 done on QA FA1, hall tickets not published. | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Hall Tickets > QA FA1. | Target: "Hall tickets have not been published yet. Check back later." and no button. Blocked by KG-21. | blocked: KG-21 student hall ticket view reads lists that now return 403 |
| TC-EXM-14-E08 | P3 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); TC-EXM-13-E01 done (Advik ineligible, no override). | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Hall Tickets > QA FA1. | Target: red card "You are not eligible for the hall ticket" with the reason; no download. Blocked by KG-21. | blocked: KG-21 student hall ticket view reads lists that now return 403 |
| TC-EXM-14-E09 | P1 | Mobile | Admin | TC-EXM-13-E10 done. | 1. Sign in as Admin.<br>2. Open the QA FA1 hall tickets screen.<br>3. Tap "Publish" and confirm. | Toast "Hall Tickets Published". | planned |
| TC-EXM-14-E10 | P2 | Mobile | Admin | Seeded hall tickets of "Half Yearly Examination 2026". | 1. Sign in as Admin.<br>2. Open Exam tab > "Hall Tickets" > "Manage" on "Half Yearly Examination 2026".<br>3. On the "Eligible" tab tap "Download PDF" on Karthik Reddy. | A PDF is saved (Expo web) or shared (native); toast "Hall ticket downloaded". | planned |
| TC-EXM-14-E11 | P2 | Mobile | Admin | Seeded hall tickets of "Half Yearly Examination 2026". | 1. Sign in as Admin.<br>2. Open the "Half Yearly Examination 2026" hall tickets screen.<br>3. Tap "Download All" and confirm. | hall_tickets_<examId>.zip is saved or shared; toast "Hall tickets downloaded". | planned |
| TC-EXM-14-E12 | P3 | Mobile | Admin | Seeded hall tickets of "Half Yearly Examination 2026"; ability to block the download request. | 1. Sign in as Admin.<br>2. Block GET /hall-tickets/download.<br>3. Tap "Download PDF". | Toast "Download Failed" "Could not download file. Please try again." | planned |

API tests implemented in: `backend/tests/api/exam/test_f13_f14_hall_tickets.py`

Implemented in: backend/tests/unit/exam/test_hall_tickets.py.

---

## F15 Result computation

**Purpose.** After marks are entered, admin computes every student's subject results and overall result: totals, percentage, grade, GPA, pass or fail and rank within the class-section.

**Roles and permissions.**
- Compute: `exams:update`. The results are read through F16.
- Web: "Compute Results" on the results view (`/exam/results/{id}`) and "Run Compute" on `/exam/exams/{id}/results` (both enabled only for status `active` or `locked`; the second page is not linked from the UI). Mobile: "Compute" on the Results screen (permission `exams:update`).

**Preconditions.**
- Exam has subject configs and at least one saved mark. Exam grade scheme (F03) assigned; subject schemes optional.

**Steps, web.**
1. Exam > Results > "View Results" on an exam (statuses active, locked, published, finalized are listed) > "Compute Results". The table shows "Computing..." and then the results table. Toast "Aggregates computed successfully". The web always sends `force=true`, so it can be run repeatedly.
2. Alternative page `/exam/exams/{id}/results` ("Results - <exam>"): "Step 1 - Compute Aggregates" with "Run Compute" (shows "Done"), hint "Exam must be in Active or Locked status to compute." when the status does not allow it.

**Steps, mobile.**
1. Exam > Results > select the exam chip > "Compute" (confirm "Recompute all results for this exam?"). The call sends no `force`, so a second run returns 409 and the screen shows the toast "Failed to compute results." Toast "Results Computed" on success.

**Expected results.**
- For every student that has at least one saved mark: one `student_exam_results` row and one `student_subject_results` row per subject config of the exam. `rank` is set per class-section. Audit row `results_computed` with `students_computed`.

**API endpoints.**
- `POST /exams/{exam_id}/compute?force=false|true`: returns `{exam_id, students_computed, status:"computed"}`.

**Rules and validations (exact calculations, `aggregate_service.compute_exam_aggregate`).**
1. Exam must exist (404). Without `force`, if any exam result already exists: 409 `Results already computed. Pass force=true to recompute.`
2. The exam must have at least one subject config, else 422 `No subject configs found for this exam.`
3. Students processed = distinct students that have at least one `student_marks` row for the exam. If none: returns 0 and changes nothing (also with `force`, existing results are not deleted).
4. With `force=true` all existing subject and exam results of the exam are deleted first.
5. For every student and every subject config of the exam (all class-sections of the exam):
   - For each component: no mark row means skip. If the mark row is absent, the subject is absent: stop. Otherwise, if `include_in_total` is true and `marks_obtained` is not null: add the marks to `sub_obtained` and, when the component's `max_marks` is non-zero, add it to `sub_max` (so `sub_max` counts only components that have an entered mark). Components with `include_in_total` false, null marks, or no max do not contribute. `remark_grade` is never used.
   - If absent: grade is `ABS`, gpa 0.0, `is_pass` false, `sub_obtained` reset to 0, `is_absent` true.
   - Else if `sub_max > 0`: `lookup_grade(sub_obtained, sub_max, subject bands or exam bands)` (F03/F04) and, if that returns nothing (no bands at all), the `ABS` grade. A subject with no bands anywhere therefore gets label `ABS` and fails.
   - Else (`sub_max == 0`, for example no marks entered for that subject): grade `ABS`, `is_pass` false, `is_absent` false.
   - Subject `percentage` = `sub_obtained / sub_max * 100` rounded to 2 decimals (`round`, half-even); null when `sub_max == 0`. `max_marks` stored as `sub_max` or null. `marks_obtained` is the sum (0 when absent).
   - Subject pass = the grade band's `is_pass` (false when absent). Min pass marks on components and subjects are ignored.
   - Only non-absent subjects with `sub_max > 0` add to the overall `total_obtained` and `total_max`.
6. Overall: `percentage = total_obtained / total_max * 100` rounded to 2 decimals (null when `total_max == 0`); `total_marks_obtained` and `total_max_marks` rounded to 2 decimals. Overall grade and gpa come from `lookup_grade(total_obtained, total_max, exam bands)`, only when the exam has bands and `total_max > 0`, else null.
7. `is_passed` (overall) = every subject row passed. It does not depend on the overall grade or percentage.
8. Rank: students are grouped by (class_id, section_id) from the exam's class-sections (a student with no matching class-section forms a group of its own, keyed by none). Within a group, students are sorted by the unrounded overall percentage descending and numbered 1, 2, 3, ... Equal percentages receive consecutive different ranks in an unspecified order (no shared ranks, no gaps). Failed and absent students are ranked too. `publish_rank` is ignored.
9. The exam status is not checked and not changed. Audit row `results_computed` is written even when 0 students were computed.

Worked examples with GS1 (Math Written 80 + Oral 20, Science Written 100, English Written 100):

| Student | Marks | Subject rows | Overall | Rank |
|---|---|---|---|---|
| S1 | Math 62+18, Science 90, English 70 | Math 80/100 80.00 A pass; Science 90/100 90.00 A+; English 70/100 70.00 B | 240/300 = 80.00, grade A, gpa 3.50, `is_passed` true | 2 |
| S2 | Math 68+17, Science 95, English 90 | 85 A; 95 A+; 90 A+ | 270/300 = 90.00, A+, gpa 4.00, pass | 1 |
| S3 | Math 45+10, Science 45, English 30 | 55 D pass; 45 D pass; 30 F fail | 130/300 = 43.33, D, gpa 1.00, `is_passed` false | 4 |
| S4 | Math 62+18, Science Written absent, English 70 | Math 80 A; Science `ABS`, marks 0, max null, percentage null, `is_absent` true, fail; English 70 B | 150/200 = 75.00 (Science excluded), B, `is_passed` false | 3 |
| S6 (partial) | Math Written 50, Oral not entered | Math 50/80 = 62.50, C (max counts only the entered component) | depends on the other subjects | |
| S7 (tie) | same totals as S1 (80.00) | | 80.00 | 2 and 3 for S1 and S7 in either order; S4 then 4, S3 5 |
| Half-even rounding | 1 / 800 * 100 = 0.125 | | stored 0.12 | |
| Rounding up | 200/300 | | 66.67 | |
| Subject with only remarks components | any remark grades | `sub_max` 0: `ABS`, fail | student fails overall | | |
| No grade scheme anywhere | any marks | every subject `ABS`, fail; overall grade null | `is_passed` false for all | | |

**Error and edge cases.**
- Multi-class exams: every config of the exam is applied to every student, so a student gets an `ABS` row and a fail for subjects of other class-sections (KG-5). The same happens for any subject without saved marks.
- Partially entered marks inflate the percentage because only entered components add to `sub_max`.
- Student without a class-section match: still computed, ranked in the "none" group.
- Recompute after unlock and mark corrections: use `force=true`.
- Students with marks but no longer enrolled are still computed.

**Unit-testable logic.**
- The whole algorithm with a fake session and fake rows (`compute_exam_aggregate`): subject sums, absent handling, band selection, rounding, pass criteria, rank grouping and ties, force and 409 behaviour, zero-student early return.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-15-U01 | S1 data from the table | Math 80.00 A pass, Science 90.00 A+, English 70.00 B; overall 240/300, 80.00, A, gpa 3.50, `is_passed` True | passing |
| TC-EXM-15-U02 | S2 data | Overall 270/300, 90.00, A+, gpa 4.00, pass | passing |
| TC-EXM-15-U03 | S3 data | Subject English F fail; overall 130/300 = 43.33, grade D, `is_passed` False | passing |
| TC-EXM-15-U04 | S4 data (Science absent) | Science row: `is_absent` True, marks 0, `max_marks` None, percentage None, grade `ABS`, gpa 0.00, not passed; overall 150/200 = 75.00 grade B; `is_passed` False | passing |
| TC-EXM-15-U05 | Student absent on the second component only (Written 60 entered then Oral absent) | `sub_obtained` reset to 0; `max_marks` 80 (Written counted before the absence), percentage 0.00, grade `ABS` | passing |
| TC-EXM-15-U06 | Partial entry: Math Written 50 entered, Oral missing | `sub_max` 80; 50/80 = 62.50 percent; grade C | passing |
| TC-EXM-15-U07 | Component with `include_in_total=false` (10 marks entered) | Not added to obtained or max | passing |
| TC-EXM-15-U08 | Component with `max_marks` 0 and marks 0 entered | `sub_max` stays 0; subject `ABS`, not passed | passing |
| TC-EXM-15-U09 | Entered mark null (row exists, not entered) | Treated as not entered | passing |
| TC-EXM-15-U10 | Subject with only a remarks component | `sub_max` 0; grade `ABS`; not passed; excluded from totals | passing |
| TC-EXM-15-U11 | Subject with a subject grade scheme (pass at 33) and exam scheme GS1 | 33/100 gives pass in that subject and an exam-scheme grade F is not used for it | passing |
| TC-EXM-15-U12 | Subject scheme with no bands | Falls back to exam bands | passing |
| TC-EXM-15-U13 | No bands anywhere | Every subject `ABS`, not passed; overall grade and gpa None | passing |
| TC-EXM-15-U14 | Exam grade scheme missing on the exam but subject schemes present | Subject grades from subject bands; overall grade None; overall pass from subjects | passing |
| TC-EXM-15-U15 | Overall percentage 130/300 | 43.33 (rounded, `Decimal` half-even) | passing |
| TC-EXM-15-U16 | Overall 200/300 | 66.67 | passing |
| TC-EXM-15-U17 | Half-even boundary: 1 of 800 | 0.12 (not 0.13) | passing |
| TC-EXM-15-U18 | Ranking: percentages 90.00, 80.00, 75.00, 43.33 in one class-section | Ranks 1, 2, 3, 4 | passing |
| TC-EXM-15-U19 | Ranking tie: two students 80.00 | Ranks {2, 3} assigned one each; next student gets 4 | passing |
| TC-EXM-15-U20 | Ranking uses the unrounded percentage: 66.666 and 66.667 (both display 66.67) | The 66.667 student ranks ahead | passing |
| TC-EXM-15-U21 | Ranking groups: two class-sections with their own top students | Each group starts at rank 1 | passing |
| TC-EXM-15-U22 | A failed student with a higher percentage than a passing student | Still ranked above (pass or fail does not affect rank) | passing |
| TC-EXM-15-U23 | `compute_exam_aggregate` with existing results and `force=False` | HTTPException 409 `Results already computed. Pass force=true to recompute.` | passing |
| TC-EXM-15-U24 | `compute_exam_aggregate` with `force=True` and existing results | Old subject and exam results deleted, new ones added | passing |
| TC-EXM-15-U25 | `compute_exam_aggregate` with no subject configs | HTTPException 422 | passing |
| TC-EXM-15-U26 | `compute_exam_aggregate` with configs but no marks and existing results, `force=True` | Returns 0; existing results not deleted | passing |
| TC-EXM-15-U27 | `compute_exam_aggregate` unknown exam | HTTPException 404 | passing |
| TC-EXM-15-U28 | Two class-sections' configs applied to a student who only has marks for one | The other class's subjects yield `ABS` rows with `is_absent` False and the student fails overall (documents KG-5) | passing |
| TC-EXM-15-A01 | Save marks for S1..S4 as in the table, POST compute (ADMIN) | 200 `{students_computed: 4, status: "computed"}` | passing |
| TC-EXM-15-A02 | GET `/exams/{id}/results` after A01 | Four rows ordered by rank: S2 (90.00, A+, rank 1), S1 (80.00, A, 2), S4 (75.00, B, 3, `is_passed` false), S3 (43.33, D, 4, `is_passed` false); decimals as strings (`"80.00"`) | passing |
| TC-EXM-15-A03 | A02 `subject_results` for S4 | Science: `is_absent` true, `grade_label` `ABS`, `max_marks` null, `percentage` null | passing |
| TC-EXM-15-A04 | POST compute again without `force` | 409 `Results already computed. Pass force=true to recompute.` | passing |
| TC-EXM-15-A05 | Change one mark, POST compute with `force=true`, GET results | 200; values and ranks reflect the change; row count still 4 | passing |
| TC-EXM-15-A06 | POST compute for an exam with no marks | 200 `students_computed` 0; GET results `[]` | passing |
| TC-EXM-15-A07 | POST compute for an exam with no subject configs (cloned header) | 422 `No subject configs found for this exam.` | passing |
| TC-EXM-15-A08 | POST compute unknown exam | 404 | passing |
| TC-EXM-15-A09 | POST compute on a published exam and on a draft exam | 200 both (no status check; exam status unchanged) | passing |
| TC-EXM-15-A10 | POST compute writes an audit row | GET audit contains `results_computed` with metadata `students_computed` 4 | passing |
| TC-EXM-15-A11 | POST compute with `force=maybe` | 422 | passing |
| TC-EXM-15-A12 | POST compute as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-15-A13 | POST compute with NOAUTH | 401 | passing |
| TC-EXM-15-A14 | Tenant isolation: tenant B POST compute on tenant A's exam id | 404 | passing |
| TC-EXM-15-A15 | Token A with `cschema` B | 403 | passing |
| TC-EXM-15-A16 | Compute for a class where grade scheme is absent | Subjects `ABS`; `grade_label` null on the overall row; `is_passed` false | passing |
| TC-EXM-15-A17 | Compute with a subject grade scheme (pass 33) assigned to Science | A Science mark of 33/100 gives `is_passed` true for that subject | passing |
| TC-EXM-15-A18 | Save a tie (two students 80.00) then compute | Ranks 2 and 3 given to the two (either order); no duplicate rank values | passing |
| TC-EXM-15-A19 | Two class-sections in one exam | Each section ranks from 1; students also receive `ABS` rows for the other section's subjects (documents KG-5) | known defect: KG-5: compute applies every section's subject configs to every student, creating ABS rows and failing students... |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-15-E01 | P1 | Web | Admin | QA FA1 active with marks saved for Advik Mehta, Harsha Raju and Nikhil Krishnan (TC-EXM-11-E01 for all three). | 1. Sign in as Admin.<br>2. Open Exam > Results.<br>3. Click "View Results" on QA FA1.<br>4. Click "Compute Results". | Table shows "Computing..." then three rows; toast "Aggregates computed successfully"; columns Total, %, Grade, GPA, Rank, Result. | planned |
| TC-EXM-15-E02 | P2 | Web | Admin | TC-EXM-15-E01 done. | 1. Sign in as Admin.<br>2. On the QA FA1 results view click "Compute Results" again. | Succeeds again (web always sends force=true); same rows. | planned |
| TC-EXM-15-E03 | P3 | Web | Admin | A draft QA exam exists (TC-EXM-09-E05). | 1. Sign in as Admin.<br>2. Open Exam > Results. | The draft exam is not listed (only active, locked, published, finalized). | planned |
| TC-EXM-15-E04 | P3 | Web | Admin | Seeded published exam "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open Exam > Results > "View Results" on "Unit Test 1 - Class 1B". | "Compute Results" is hidden. | planned |
| TC-EXM-15-E05 | P2 | Web | Admin | Seeded computed results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open Exam > Results > "View Results" on "Unit Test 1 - Class 1B".<br>3. Read the three rows. | Advik Mehta: Total 97.5, 78.0%, B+, GPA 8.00, Rank 1, Pass; Harsha Raju: 72.8%, B+, Rank 2; Nikhil Krishnan: 68.0%, B, Rank 3; each subject column shows marks out of 25. | planned |
| TC-EXM-15-E06 | P3 | Web | Teacher | QA FA1 active with marks. | 1. Sign in as Teacher.<br>2. Open Exam > Results > "View Results" on QA FA1.<br>3. Click "Compute Results". | The button is shown (gated by status only); the API answers 403 and an error toast appears; results unchanged. | planned |
| TC-EXM-15-E07 | P1 | Mobile | Admin | QA FA1 active with marks and no results yet. | 1. Sign in as Admin.<br>2. Open Exam tab > "Results".<br>3. Select QA FA1.<br>4. Tap "Compute" (or "Compute Results" on the empty state) and confirm "Recompute all results for this exam?". | Toast "Results Computed"; the list shows percentage, rank and PASS or FAIL per student. | planned |
| TC-EXM-15-E08 | P3 | Mobile | Admin | TC-EXM-15-E07 done. | 1. Sign in as Admin.<br>2. Tap "Compute" again and confirm. | API 409 (no force); toast "Failed to compute results." | planned |
| TC-EXM-15-E09 | P2 | Mobile | Admin | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open Exam tab > "Results" > "Unit Test 1 - Class 1B".<br>3. Tap the Advik Mehta row. | Detail "<total> / <max> marks . Rank #1" (97.5 of 125), per-subject marks, grade B+, PASS. | planned |

API tests implemented in: `backend/tests/api/exam/test_f15_f16_results.py`

Implemented in: backend/tests/unit/exam/test_results_compute.py.

---

## F16 Result publish, view and export

**Purpose.** Admin publishes computed results so students and parents can see them, reviews the full result list, and exports it.

**Roles and permissions.**
- Publish: `exams:update`. List and single result: `exams:read`. Export: client-side only (no endpoint).
- Web: Exam > Results (all roles; the admin view at `/exam/results/{id}`, the student and parent views in F17). The "Publish Results" button exists on `/exam/exams/{id}/results` (not linked) and is enabled only for status `locked`, which no endpoint sets, so web cannot publish (KG-4). Mobile: "Publish" on the Results screen (permission `exams:update`).

**Preconditions.**
- Results computed (F15) for the data to be useful; the API does not require it.

**Steps, web.**
1. Exam > Results (title "Results", exams with status active, locked, published or finalized). "View Results" opens `/exam/results/{id}`: "Results - <exam>", subtitle "<n> students - <status>", search "Search student...", "Export" menu ("Export to CSV", "Export to Excel"), table S.No., Student, Adm#, one column per subject (marks, grade, "ABS" badge), Total, %, Grade, GPA, Rank, Result (Pass or Fail badge), and "Showing x of y students".
2. Export CSV downloads `<exam>_results.csv`, Excel downloads `<exam>_results.xlsx`, with the filtered rows and columns S.No., Student, Adm#, one per subject (`ABS` or marks), Total (one decimal), % (one decimal with percent sign), Grade, GPA (two decimals), Rank, Result. Disabled when no rows.
3. Publish on `/exam/exams/{id}/results`: "Step 2 - Publish Results" (text: "Publishing makes results visible to students and parents. This action cannot be undone without unlocking the exam."), button "Publish Results" disabled unless status `locked`, hint "Exam must be in Locked status to publish.", confirm "Publish Results?", toast "Results published successfully". "Open Results View" links to the list.

**Steps, mobile.**
1. Exam > Results > exam chip > "Publish" > confirm "Publish results to students and parents?" > toast "Results Published". The list shows each student with percentage, rank and PASS or FAIL; tap a row for the subject detail. No export.

**Expected results.**
- `exams.status` becomes `published`; audit row `results_published`. No SMS is sent and `published_at` in the response is null.

**API endpoints.**
- `POST /exams/{exam_id}/publish`: returns `{exam_id, status:"published", published_at: null}`.
- `GET /exams/{exam_id}/results` query `class_id`, `section_id`, `student_id` (optional filters): list of `StudentExamResultRead`: `id, exam_id, student_id, student_name, admission_number, total_marks_obtained, total_max_marks, percentage, grade_label, gpa, rank, is_passed, computed_at, subject_results[]` (each: `subject_config_id, subject_name, marks_obtained, max_marks, percentage, grade_label, gpa, remark_grade, is_absent, is_passed`). Decimals are strings.
- `GET /exams/{exam_id}/results/{student_id}`: one student's result; 404 `No result found for student <id> in exam <id>`.

**Rules and validations.**
- Publish allowed from `active`, `locked`, `finalized`; from `draft` or `published` gives 409 `Exam status '<s>' cannot be published. Must be locked or active.` It does not check that results exist, and republishing an already published exam is rejected.
- The list ignores publish status: it returns computed results of draft, active and published exams alike to staff roles; Student and Parent get 403. `GET /results/{student_id}` is limited to the own record or a linked child but also ignores publish status (KG-3). Ordering: rank ascending with nulls last, then student name. Unknown exam: `[]`.
- Filters: `class_id` and `section_id` match the student's current admission; both together require both.
- `publish_rank` is ignored: rank is always returned.

**Error and edge cases.**
- Published exam can be edited, recomputed (F15) and unlocked (F09) via the API.
- Results exist for students with marks only.

**Unit-testable logic.**
- `publish_exam` status rule for all five statuses; export row building (CSV quoting, ABS, number formats); results table sort and search.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-16-U01 | `publish_exam` for draft, active, locked, published, finalized (fake session) | active, locked, finalized become published; draft and published raise 409 | passing |
| TC-EXM-16-U02 | `publish_exam` error text | `Exam status 'draft' cannot be published. Must be locked or active.` | passing |
| TC-EXM-16-U03 | Web `buildRows` for a result with marks 80.0, percentage 80, gpa 3.5, rank 2, passed | `Total` "80.0", `%` "80.0%", `GPA` "3.50", `Rank` "2", `Result` "Pass" | blocked: buildRows is inline in web/src/pages/exam/StudentResults.tsx |
| TC-EXM-16-U04 | Web `buildRows` for an absent subject and null percentage | Subject cell `ABS`; `%` and `Total` show "-" where null | blocked: buildRows is inline in web/src/pages/exam/StudentResults.tsx |
| TC-EXM-16-U05 | Web CSV export with a student name containing a comma and a quote | Value wrapped in quotes with the quote doubled | blocked: CSV export is inline in handleExportCSV of web/src/pages/exam/StudentResults.tsx |
| TC-EXM-16-U06 | ResultsTable sorting by percent and rank with null ranks | Null rank sorts last (treated as 999) | blocked: sorting is inline in web/src/components/exam/ResultsTable.tsx |
| TC-EXM-16-U07 | ResultsTable search by name and admission number | Case-insensitive filter | blocked: search filter is inline in web/src/components/exam/ResultsTable.tsx |
| TC-EXM-16-U08 | Web `canPublish` and `canCompute` flags for each status | publish only when `locked`; compute when `active` or `locked` | blocked: canPublish and canCompute are inline in web/src/pages/exam/ResultsPublish.tsx and StudentResults.tsx |
| TC-EXM-16-A01 | POST publish on an active exam with computed results (ADMIN) | 200 `{status: "published", published_at: null}`; GET exam shows `published` | passing |
| TC-EXM-16-A02 | POST publish on a locked exam and on a finalized exam (fixtures set directly in the database) | 200 each | skipped: locked and finalized exams cannot be produced through the API and the database must not be touched directly |
| TC-EXM-16-A03 | POST publish on a draft exam | 409 `... cannot be published. Must be locked or active.` | passing |
| TC-EXM-16-A04 | POST publish on an already published exam | 409 | passing |
| TC-EXM-16-A05 | POST publish before any compute | 200 (no precondition) | passing |
| TC-EXM-16-A06 | POST publish unknown exam | 404 | passing |
| TC-EXM-16-A07 | POST publish writes an audit row | `results_published` present | passing |
| TC-EXM-16-A08 | POST publish as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-16-A09 | GET results with no filters (after F15 A01) | 4 rows ordered by rank then name; fields and string decimals as documented | passing |
| TC-EXM-16-A10 | GET results with `student_id` | Only that student | passing |
| TC-EXM-16-A11 | GET results with `class_id` and `section_id` of the exam's class-section | All four; with another section id `[]` | passing |
| TC-EXM-16-A12 | GET results with `class_id` only | Students admitted to that class | passing |
| TC-EXM-16-A13 | GET results for an exam without computation; unknown exam | `[]` both | passing |
| TC-EXM-16-A14 | GET results before publish (draft, active exam) | 200 with data (publication not enforced; documents KG-3) | passing |
| TC-EXM-16-A15 | GET results as STUDENT and PARENT | 200 with all students (target 403; documents KG-3) | passing |
| TC-EXM-16-A16 | GET single result for S1 | 200 with `subject_results` ordered by subject sort order; `rank` 2 | passing |
| TC-EXM-16-A17 | GET single result for a student without a result; unknown student | 404 `No result found for student ... in exam ...` | passing |
| TC-EXM-16-A18 | GET results and GET single as ADMIN, TEACHER, STAFF | 200 each | passing |
| TC-EXM-16-A19 | GET results, GET single, POST publish with NOAUTH | 401 each | passing |
| TC-EXM-16-A20 | Tenant isolation: tenant B GET results of tenant A's exam | `[]`; GET single 404 | passing |
| TC-EXM-16-A21 | Token A with `cschema` B on GET results | 403 | passing |
| TC-EXM-16-A22 | After publish, `publish_rank=false` on the exam | Results still contain `rank` (flag ignored; documents KG-11) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-16-E01 | P2 | Web | Admin | Seeded results of "Unit Test 1 - Class 1B" (3 students). | 1. Sign in as Admin.<br>2. Open Exam > Results > "View Results" on "Unit Test 1 - Class 1B".<br>3. Type "Advik" in "Search student...". | Table shows one row; footer "Showing 1 of 3 students". | planned |
| TC-EXM-16-E02 | P1 | Web | Admin | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open the "Unit Test 1 - Class 1B" results view.<br>3. Click "Export" > "Export to CSV". | File "Unit Test 1 - Class 1B_results.csv" downloads; header S.No., Student, Adm#, one column per subject, Total, %, Grade, GPA, Rank, Result; values match the table. | planned |
| TC-EXM-16-E03 | P2 | Web | Admin | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open the "Unit Test 1 - Class 1B" results view.<br>3. Click "Export" > "Export to Excel". | File "Unit Test 1 - Class 1B_results.xlsx" downloads with sheet "Results". | planned |
| TC-EXM-16-E04 | P3 | Web | Admin | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open the "Unit Test 1 - Class 1B" results view.<br>3. Type "zzz" in "Search student...". | "Export" is disabled. | planned |
| TC-EXM-16-E05 | P3 | Web | Admin | Seeded active exam "Half Yearly Examination 2026". | 1. Sign in as Admin.<br>2. Open /exam/exams/<Half Yearly Examination 2026 id>/results. | "Run Compute" enabled; "Publish Results" disabled with "Exam must be in Locked status to publish." (no lock step exists, KG-4). | planned |
| TC-EXM-16-E06 | P3 | Web | Admin | Seeded published exam "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open /exam/exams/<Unit Test 1 - Class 1B id>/results. | Text "Results have been published." | planned |
| TC-EXM-16-E07 | P3 | Web | Admin | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open the "Unit Test 1 - Class 1B" results view.<br>3. Click the Total, % and Rank headers. | Rows reorder by each column; unranked rows sort last. | planned |
| TC-EXM-16-E08 | P1 | Mobile | Admin | TC-EXM-15-E01 or TC-EXM-15-E07 done (QA FA1 active with results). | 1. Sign in as Admin.<br>2. Open Exam tab > "Results" > QA FA1.<br>3. Tap "Publish".<br>4. Confirm "Publish results to students and parents?". | Toast "Results Published"; QA FA1 shows PUBLISHED in the lists. This is the only UI path to publish (KG-4). | planned |
| TC-EXM-16-E09 | P2 | Mobile | Teacher | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Teacher.<br>2. Open Exam tab > "Results" > "Unit Test 1 - Class 1B". | Student list visible; "Compute" and "Publish" hidden. | planned |
| TC-EXM-16-E10 | P3 | Mobile | Admin | Seeded results of "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open Exam tab > "Results" > "Unit Test 1 - Class 1B".<br>3. Tap a student row.<br>4. Go back. | The detail card opens and back returns to the list. | planned |

API tests implemented in: `backend/tests/api/exam/test_f15_f16_results.py`

Implemented in: backend/tests/unit/exam/test_results_audit_notify.py (U01-U02). U03-U08 blocked.

---

## F17 Student and parent views (my marks, my results)

**Purpose.** Students see their own marks (as soon as teachers save them) and their published result; parents see the same for a linked child.

**Roles and permissions.**
- `GET /exams/{id}/my-marks` and `child-marks`: `exams:read` plus identity from the token (student id or parent id).
- `GET /exams/{id}/my-result`: `exam_results:read_own`. `GET /exams/my-results`: `exam_results:list_own` (route order fixed, KG-2; still 403 for every student because the role lacks the permission, DEF-EXM-6). `GET /exams/{id}/child-result/{student_id}`: `exams:read` plus parent identity and a parent-child link.
- Menu: Exam > Marks (button "View My Marks") and Exam > Results (button "View Results") for Student and Parent; mobile Exam tab "My Marks" card and "Results" tile.

**Preconditions.**
- Student or parent account linked to a student. For results: exam published or finalized and results computed. For a parent, the child must be linked through `student_parent_links` and selected in the app's child switcher.

**Steps, web.**
1. Exam > Marks (exams with status draft, active or locked are listed): "View My Marks" opens `/exam/my-marks/{examId}`: header with the exam name and student name; a card per subject with "<obtained> / <max>" (green when at least 35 percent of the subject max, red below), rows per component showing "<marks> / <max>", "Not entered", "Absent", and the remark grade badge. Empty state "No marks entered yet" "Marks will appear here once the teacher saves them."
2. Exam > Results > "View Results": student sees the result card: "Pass" or "Fail", "Grade: <label>", Total Marks "<obtained> / <max>", Percentage, GPA, Rank (`#n`), and a subject table (Subject, Marks, %, Grade, Result; `Absent` badge). Before publication the message is "Results have not been published yet. Check back later." Parent sees the same for the selected child.

**Steps, mobile.**
1. Exam tab > "My Marks" (student or parent) > exam list (statuses active, draft, locked) > exam: subject cards with totals, overall percentage in the header, "Absent" and "Not entered" badges, empty state "No marks available yet. Marks will appear after your teacher enters them."
2. Exam > Results (student or parent: list of active, locked, published, finalized exams) > exam: banner Pass or Fail, Grade, Total, Percentage, GPA, Rank, subject rows (`AB` for absent). Unpublished: "Results have not been published yet. Check back later."

**Expected results.**
- Raw marks are visible as saved (any exam status, including draft). Computed results are visible only once the exam is `published` or `finalized`.

**API endpoints.**
- `GET /exams/{exam_id}/my-marks`: `StudentMarksView {exam_id, student_id, student_name, subjects[{subject_config_id, subject_name, components[{component_name, marks_obtained, max_marks, is_absent, remark_grade}]}]}`; ordered by subject then component sort order. Decimals are strings.
- `GET /exams/{exam_id}/child-marks/{student_id}`: same view for a linked child.
- `GET /exams/{exam_id}/my-result`: `StudentExamResultRead` for the caller.
- `GET /exams/{exam_id}/child-result/{student_id}`: same for a linked child.
- `GET /exams/my-results`: list of the caller's published results. The route is now matched before `GET /exams/{exam_id}` (KG-2 fixed) but returns 403 `permission_denied` for every student (DEF-EXM-6). The web and mobile API functions call it but no screen uses it.

**Rules and validations.**
- `my-marks` and `my-result` require a student identity: a caller without one (Admin, Teacher, Parent) gets 400 `Only students can access this endpoint` (or 403 first when the role lacks the permission, as for `my-result`: Admin, Teacher, Staff and Parent lack `exam_results:read_own`).
- `child-marks` and `child-result` require a parent identity: others get 400 `Only parents can access this endpoint`. An unlinked student id gives 403 `Cannot access marks for unrelated student` or `Cannot access results for unrelated student`.
- Result endpoints: exam status not `published` or `finalized` gives 403 `Results are not yet published for this exam.`; a published exam without a result row for the student gives 404 `No result found for student <id> in exam <id>`.
- `my-marks` returns only the caller's own marks; no other student's data is included. It shows marks for any exam status and does not wait for compute or publish.
- Rank and GPA are returned regardless of `publish_rank`.

**Error and edge cases.**
- Student with no marks: `subjects` is an empty list.
- Parent with several children: the app passes the selected child id; switching the child changes the data.
- Student and Parent get 403 on the F16 result list; `GET /results/{student_id}` returns only their own or a linked child's result (KG-3).
- The web Marks list and the mobile "My Marks" list show only draft, active and locked exams, so a student cannot open the raw marks of a published exam from them (web: only by URL; mobile: from the Exams list) (KG-24).

**Unit-testable logic.**
- `get_student_raw_marks` grouping and ordering (fake rows); `get_published_result_or_403` for each status; web subject card colour rule (35 percent); mobile overall percentage (skips absent subjects).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-17-U01 | `get_published_result_or_403` with status draft, active, locked | HTTPException 403 `Results are not yet published for this exam.` | passing |
| TC-EXM-17-U02 | `get_published_result_or_403` with status published and finalized | Returns the student result | passing |
| TC-EXM-17-U03 | `get_published_result_or_403` published but no row | HTTPException 404 | passing |
| TC-EXM-17-U04 | `get_student_raw_marks` rows for two subjects (sort orders 2 and 1) | Subjects ordered by sort order; `_sort` key removed; components ordered | passing |
| TC-EXM-17-U05 | `get_student_raw_marks` with no rows | `subjects` empty; `student_name` from the student row | passing |
| TC-EXM-17-U06 | Web subject card colour: obtained 35 of 100 and 34 of 100 | Green at 35 percent; red below | blocked: card colour rule is inline in the web my-marks page component |
| TC-EXM-17-U07 | Mobile `overallPct`: subjects (80/100), (absent), (70/100) | 75.0 (absent subject skipped for both obtained and max) | blocked: overallPct is a useMemo inside mobile/app/exam/my-marks/[examId].tsx |
| TC-EXM-17-U08 | Mobile `overallPct` with nothing entered | null (no percentage shown) | blocked: overallPct is a useMemo inside mobile/app/exam/my-marks/[examId].tsx |
| TC-EXM-17-A01 | GET my-marks as STUDENT after marks were saved (draft exam) | 200 with the student's subjects and components; marks as strings | passing |
| TC-EXM-17-A02 | GET my-marks as STUDENT A when STUDENT B also has marks | Only A's `student_id` and marks | passing |
| TC-EXM-17-A03 | GET my-marks for a student without marks | 200 `subjects: []` | passing |
| TC-EXM-17-A04 | GET my-marks as ADMIN, TEACHER, STAFF, PARENT | 400 `Only students can access this endpoint` | passing |
| TC-EXM-17-A05 | GET my-marks for an unknown exam id | 200 with empty `subjects` (no exam check) | passing |
| TC-EXM-17-A06 | GET child-marks as PARENT for a linked child | 200 | passing |
| TC-EXM-17-A07 | GET child-marks as PARENT for an unlinked student | 403 `Cannot access marks for unrelated student` | passing |
| TC-EXM-17-A08 | GET child-marks as STUDENT, ADMIN | 400 `Only parents can access this endpoint` | passing |
| TC-EXM-17-A09 | GET my-result as STUDENT, exam published and computed | 200 with total, percentage, grade, gpa, rank, `subject_results` | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |
| TC-EXM-17-A10 | GET my-result as STUDENT, exam active | 403 `Results are not yet published for this exam.` | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |
| TC-EXM-17-A11 | GET my-result as STUDENT, published but no result row | 404 | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |
| TC-EXM-17-A12 | GET my-result as ADMIN, TEACHER, STAFF, PARENT | 403 each (no `exam_results:read_own`) | passing |
| TC-EXM-17-A13 | GET child-result as PARENT for a linked child, exam published | 200 | passing |
| TC-EXM-17-A14 | GET child-result as PARENT for a linked child, exam active | 403 `Results are not yet published for this exam.` | passing |
| TC-EXM-17-A15 | GET child-result as PARENT for an unlinked student | 403 `Cannot access results for unrelated student` | passing |
| TC-EXM-17-A16 | GET child-result as STUDENT and as ADMIN | 400 `Only parents can access this endpoint` | passing |
| TC-EXM-17-A17 | GET `/exams/my-results` as STUDENT | 422 (route shadowed by `/exams/{exam_id}`; documents KG-2; target 200 with published results only) | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |
| TC-EXM-17-A18 | After the route order is fixed: STUDENT with results in a published and an active exam | List contains only the published exam | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |
| TC-EXM-17-A19 | After the fix: GET my-results as ADMIN and PARENT | 403 and 403 (no `exam_results:list_own`) | passing |
| TC-EXM-17-A20 | STUDENT with a result in an exam, then the exam is unlocked | my-result returns 403 again (status active) | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |
| TC-EXM-17-A21 | All five endpoints with NOAUTH | 401 each | passing |
| TC-EXM-17-A22 | Tenant isolation: STUDENT of tenant B requests my-marks and my-result for tenant A's exam id | Empty marks; my-result is not returned (404 target; currently 403 because the Student role has no `exam_results:read_own`, DEF-EXM-6) | passing |
| TC-EXM-17-A23 | Token A with `cschema` B | 403 | passing |
| TC-EXM-17-A24 | Unlocked then re-published exam | my-result shows recomputed values after `force` compute | known defect: DEF-EXM-6: Student role has no exam_results:read_own (permission catalog and Full plan omit exam_results), so ... |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-17-E01 | P1 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); QA FA1 (active) with marks saved for Advik Mehta (TC-EXM-11-E01). | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Marks.<br>3. Click "View My Marks" on QA FA1. | Header with the exam and "Advik Mehta"; a card per subject "<obtained> / <max>" (green at 35 percent or more, red below), component rows with marks or "Not entered". | planned |
| TC-EXM-17-E02 | P3 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); no marks in "Half Yearly Examination 2026". | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Marks > "View My Marks" on "Half Yearly Examination 2026". | Empty state "No marks entered yet" "Marks will appear here once the teacher saves them." | planned |
| TC-EXM-17-E03 | P2 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); seeded published results of "Unit Test 1 - Class 1B" (Advik rank 1). | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Results.<br>3. Click "View Results" on "Unit Test 1 - Class 1B". | Target: Pass card, Grade B+, Total Marks 97.5 / 125, Percentage 78, GPA, Rank #1 and the subject table. Currently my-result returns 403 for every student (DEF-EXM-6) and the page shows "Results have not been published yet. Check back later." | blocked: DEF-EXM-6 Student role lacks exam_results:read_own |
| TC-EXM-17-E04 | P3 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); seeded active exam "Half Yearly Examination 2026". | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Results > "View Results" on "Half Yearly Examination 2026". | Page "Results - Half Yearly Examination 2026", "Your exam result", message "Results have not been published yet. Check back later." | planned |
| TC-EXM-17-E05 | P2 | Web | Parent | Seeded parent login of Harsha Raju (004, Class 1 / 1-B) and Tanvi Raju (005, Class 4) (the QA Parent login has no linked child); QA FA1 marks saved for Harsha (TC-EXM-11-E01). | 1. Sign in as the parent of Harsha and Tanvi Raju.<br>2. Select Harsha Raju in the child switcher.<br>3. Open Exam > Marks > "View My Marks" on QA FA1.<br>4. Switch to Tanvi Raju. | Harsha's QA FA1 marks are shown; after switching, Tanvi (Class 4, not in QA FA1) shows the "No marks entered yet" empty state. | planned |
| TC-EXM-17-E06 | P2 | Web | Parent | Seeded parent login of Harsha Raju (004, Class 1 / 1-B) and Tanvi Raju (005, Class 4) (the QA Parent login has no linked child); seeded published results of "Unit Test 1 - Class 1B". | 1. Sign in as the parent of Harsha and Tanvi Raju.<br>2. Select Harsha Raju.<br>3. Open Exam > Results > "View Results" on "Unit Test 1 - Class 1B". | Harsha Raju's result card: Pass, Grade B+, Percentage 72.80, Rank #2, subject table (child-result works for parents). | planned |
| TC-EXM-17-E07 | P3 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student). | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Marks. | Each row offers "View My Marks" (no "Enter Marks"); the grid cannot be opened. | planned |
| TC-EXM-17-E08 | P1 | Mobile | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); seeded marks of "Unit Test 1 - Class 1B". | 1. Sign in as Advik Mehta (002).<br>2. Open Exam tab > "Exams".<br>3. Tap "Unit Test 1 - Class 1B". | The My Marks screen shows five subject cards (English 23.50 / 25, Hindi 15.00 / 25, Telugu 19.00 / 25, Mathematics 16.50 / 25, Environmental Studies 23.50 / 25) and the overall percentage 78 in the header. (The "My Marks" list itself omits published exams, KG-24.) | planned |
| TC-EXM-17-E09 | P2 | Mobile | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); seeded published results of "Unit Test 1 - Class 1B". | 1. Sign in as Advik Mehta (002).<br>2. Open Exam tab > "Results" > "Unit Test 1 - Class 1B". | Target: banner Pass or Fail, Grade, Total, Percentage, GPA, Rank and subject rows. Blocked: my-result returns 403 (DEF-EXM-6). | blocked: DEF-EXM-6 Student role lacks exam_results:read_own |
| TC-EXM-17-E10 | P3 | Mobile | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); seeded active exam "Half Yearly Examination 2026". | 1. Sign in as Advik Mehta (002).<br>2. Open Exam tab > "Results" > "Half Yearly Examination 2026". | "Back to Results" and "Results have not been published yet. Check back later." | planned |
| TC-EXM-17-E11 | P2 | Mobile | Parent | Seeded parent login of Harsha Raju (004, Class 1 / 1-B) and Tanvi Raju (005, Class 4) (the QA Parent login has no linked child); seeded marks of "Unit Test 1 - Class 1B" for Harsha. | 1. Sign in as the parent of Harsha and Tanvi Raju.<br>2. Select Harsha Raju.<br>3. Open Exam tab > "Exams" > "Unit Test 1 - Class 1B". | Harsha Raju's name and marks (English 22.00 / 25 and so on). | planned |
| TC-EXM-17-E12 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Navigate in-app to /exam/my-marks. | Redirected to /exam/list. | planned |
| TC-EXM-17-E13 | P3 | Web | Student | Seeded student login Advik Mehta (admission 002, Class 1 / 1-B; the first sign-in forces a password change; the QA Student login is not linked to a student); seeded published exam "Unit Test 1 - Class 1B" with his marks. | 1. Sign in as Advik Mehta (002).<br>2. Open Exam > Marks. | Target: "Unit Test 1 - Class 1B" is listed with "View My Marks". Currently Student and Parent see only draft, active and locked exams there (mobile "My Marks" list too), so marks of a published exam are reachable only by URL /exam/my-marks/<id> on web or through the Exams list on mobile (KG-24). | blocked: KG-24 Marks list hides published exams from students and parents |

API tests implemented in: `backend/tests/api/exam/test_f17_my_views.py`

Implemented in: backend/tests/unit/exam/test_results_audit_notify.py (U01-U05). U06-U08 blocked.

---

## F18 Audit log

**Purpose.** Admin reviews a trail of key actions taken on an exam.

**Roles and permissions.**
- `exams:read` (the endpoint docstring says admin only, the check is `exams:read`).
- Menu: Exam > Exam Audit (admin menu; the exam detail tab "Audit Log" is admin only; route `/exam/exams/{id}/audit` redirects other roles). Mobile: "Audit Log" tile (admin only) and the "Audit Log" section on the exam detail.

**Preconditions.**
- Actions that write audit rows have happened.

**Steps, web.**
1. Exam > Exam Audit (`/exam/audit`, title "Audit Log", subtitle "Select an exam to view its activity history"): table of exams; click one. Or exam detail > tab "Audit Log" > "View Audit Log".
2. Page "Audit Log - <exam>": search "Search action, reason, value...", "Refresh", cards with an action badge (destructive style for delete and unlock, default for publish and compute), "old to new" values, reason, and the timestamp. Pager with "Page n" and previous or next buttons (next enabled when the page returned 20 rows). Empty state "No audit entries found."
3. The page does not show the actor.

**Steps, mobile.**
1. Exam tab > "Audit Log" > exam row "View Log" > `/exam/audit-log` with search "Search action, actor, description...". Exam detail > "Audit Log" section (admin) expands the latest 20 entries ("No audit entries.").

**Expected results.**
- Newest first, 20 per page by default. Rows are append-only and survive exam deletion.

**API endpoints.**
- `GET /exams/{exam_id}/audit` query `page` (>= 1, default 1), `page_size` (1-100, default 20): list of `{id, exam_id, student_id, subject_id, action, old_value, new_value, reason, performed_by, performed_at, metadata_}`.

**Rules and validations.**
- Recorded actions (the only ones that write rows): `exam_deleted` (old value = status, metadata exam name and counts), `exam_unlocked` (reason), `results_computed` (students_computed), `results_published`, `hall_tickets_computed` (counts), `eligibility_overridden` (student id, flags, final eligibility), `hall_tickets_published`, `notification_queued` (type, audience, recipients).
- Not recorded: create, edit, clone, activate, deactivate, mark entry or upload, dates, mark permissions, grade schemes, templates, SMS sends. The `AuditAction` enum values `mark_entered`, `mark_updated` and others are not used.
- The log is append-only (no update or delete endpoint). `old_value` and `new_value` are limited to 50 characters, `reason` to 300.
- The exam is not checked for existence: an unknown id returns `[]`.

**Error and edge cases.**
- `page` 0, `page_size` 0 or 101: 422.
- Student and Parent get 403 `Not allowed for this role` on the audit endpoint. The web Exam Audit exam list (`/exam/audit`) still opens for every role; "View Log" then redirects non-admins to the exam detail.

**Unit-testable logic.**
- `log_action` row construction; `get_audit_log` offset and limit; web `actionVariant`; web pager enable rule.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-18-U01 | `log_action` with exam id, action, performer, reason, metadata | Entry added with those fields; `metadata_` set; flushed | passing |
| TC-EXM-18-U02 | `get_audit_log` page 3, page_size 20 | Offset 40, limit 20, ordered by `performed_at` descending | passing |
| TC-EXM-18-U03 | Web `actionVariant` for `exam_deleted`, `exam_unlocked`, `results_published`, `results_computed`, `hall_tickets_computed`, `eligibility_overridden` | destructive, destructive, default, default, default (contains `compute`), secondary | blocked: actionVariant is a non-exported const in web/src/pages/exam/AuditLog.tsx; needs it exported |
| TC-EXM-18-U04 | Web pager: 20 entries and 19 entries on a page | Next enabled with 20; disabled with 19 | blocked: pager logic is inline in web/src/pages/exam/AuditLog.tsx |
| TC-EXM-18-A01 | After compute and publish, GET audit (ADMIN) | Newest first: `results_published`, `results_computed`; each has `performed_by` equal to the admin id and `performed_at` | passing |
| TC-EXM-18-A02 | After unlock with reason "Marks fix" | Row `exam_unlocked` with `reason` "Marks fix" | passing |
| TC-EXM-18-A03 | After hall ticket compute, override, publish | Rows `hall_tickets_computed` (metadata counts), `eligibility_overridden` (student_id set, metadata), `hall_tickets_published` | passing |
| TC-EXM-18-A04 | After POST notify | Row `notification_queued` with metadata type, audience, recipients | passing |
| TC-EXM-18-A05 | After delete of an exam, GET audit for that id | Row `exam_deleted` with `old_value` the previous status and metadata counts | passing |
| TC-EXM-18-A06 | After creating, editing, cloning, activating, saving marks | No new audit rows | passing |
| TC-EXM-18-A07 | Pagination: 25 rows, `page=1&page_size=20`, then `page=2` | 20 then 5 rows | passing |
| TC-EXM-18-A08 | `page_size=100` | 200 | passing |
| TC-EXM-18-A09 | `page_size=101`, `page=0`, `page_size=0` (parametrised) | 422 each | passing |
| TC-EXM-18-A10 | GET audit for an unknown exam id | 200 `[]` | passing |
| TC-EXM-18-A11 | GET audit as ADMIN, TEACHER, STAFF, STUDENT, PARENT | 200 for all (documents KG-3) | passing |
| TC-EXM-18-A12 | GET audit with NOAUTH | 401 | passing |
| TC-EXM-18-A13 | Tenant isolation: tenant B GET audit for tenant A's exam id | `[]` | passing |
| TC-EXM-18-A14 | Token A with `cschema` B | 403 | passing |
| TC-EXM-18-A15 | Append-only: no PUT, PATCH or DELETE route exists on `/exams/{id}/audit` | 405 for each | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-18-E01 | P1 | Web | Admin | Seeded audit rows of "Unit Test 1 - Class 1B" (results_computed, results_published). | 1. Sign in as Admin.<br>2. Open Exam > Exam Audit.<br>3. Click "View Log" on "Unit Test 1 - Class 1B". | "Audit Log - Unit Test 1 - Class 1B" lists results_published then results_computed with badges and local timestamps, newest first. | planned |
| TC-EXM-18-E02 | P3 | Web | Admin | TC-EXM-18-E01 open. | 1. Sign in as Admin.<br>2. Type "publish" in "Search action, reason, value...". | Only the results_published entry remains. | planned |
| TC-EXM-18-E03 | P3 | Web | Admin | TC-EXM-18-E01 open. | 1. Sign in as Admin.<br>2. Click "Refresh". | Spinner, then the list reloads. | planned |
| TC-EXM-18-E04 | P3 | Web | Admin | An exam with no audited actions (for example a fresh clone). | 1. Sign in as Admin.<br>2. Open its audit log. | "No audit entries found." | planned |
| TC-EXM-18-E05 | P2 | Web | Teacher | Seeded exam "Unit Test 1 - Class 1B". | 1. Sign in as Teacher.<br>2. Open Exam > Exam Audit > "View Log" on "Unit Test 1 - Class 1B". | Redirected to the exam detail (the exam list page itself is reachable); no "Audit Log" tab. | planned |
| TC-EXM-18-E06 | P3 | Web | Admin | QA FA1 with more than 20 audit entries (click "Recompute" on its hall ticket page 21 times). | 1. Sign in as Admin.<br>2. Open its audit log.<br>3. Click the next-page arrow. | Next is enabled on page 1; "Page 2" shows the older entries. | planned |
| TC-EXM-18-E07 | P1 | Mobile | Admin | Seeded audit rows of "Half Yearly Examination 2026" (hall_tickets_computed, hall_tickets_published). | 1. Sign in as Admin.<br>2. Open the Exam tab and tap "Audit Log".<br>3. Tap "View Log" on "Half Yearly Examination 2026".<br>4. Type "publish" in the search box. | List "Exam Audit Logs" with search "Search by name, board, or status..."; the log lists both hall ticket entries and the search keeps hall_tickets_published. | planned |
| TC-EXM-18-E08 | P3 | Mobile | Admin | Seeded exam "Unit Test 1 - Class 1B". | 1. Sign in as Admin.<br>2. Open "Unit Test 1 - Class 1B" on mobile.<br>3. Expand the "Audit Log" section. | The two seeded entries are listed. | planned |
| TC-EXM-18-E09 | P3 | Mobile | Teacher | None. | 1. Sign in as Teacher.<br>2. Open the Exam tab. | No "Audit Log" tile; in-app navigation to /exam/audit redirects to /exam/list. | planned |

API tests implemented in: `backend/tests/api/exam/test_f12_f18_f19_summary_audit_notify.py`

Implemented in: backend/tests/unit/exam/test_results_audit_notify.py (U01-U02). U03-U04 blocked.

---

## F19 Notifications

**Purpose.** Admin informs students and parents about an exam. The module offers a notification request that only counts recipients, and three SMS endpoints that queue messages to parents.

**Roles and permissions.**
- `POST /exams/{id}/notify`: `exams:update`.
- `POST /exams/{id}/dates/send-schedule`, `POST /exams/{id}/send-results-notification`, `POST /exams/{id}/send-hall-ticket-notification`: `exams:send_sms`. No seeded role has this permission (Admin included), so these return 403 until it is granted.
- Web: route `/exam/exams/{id}/notify` (admin role names; not linked from any screen). Mobile: exam detail > "Send Exam Notification" (admin) and `/exam/notify` (guard `exams:update`).

**Preconditions.**
- For notify: exam with class-sections and enrolled students. For the SMS endpoints: parents linked to the students with a phone number, an SMS gateway configured and a Celery worker.

**Steps, web.**
1. Open `/exam/exams/{id}/notify` (no menu entry or button leads here). Page "Notifications - <exam>", subtitle "Send exam-related notifications": "Target Audience" chips (Students, Parents, Students and Parents), "Channels" chips (SMS, Email, Push Notification), "Message" textarea with a character counter, button "Send Notification".
2. Rules: message at least 10 characters; at least one channel. Toast "<n> notification(s) queued". The form resets. The type is always sent as `custom`.
3. Related, cross-module: "Send Marks" on the mark grid and a per-class-section "Send Exam Schedule Message" button on the exam overview use the Communication module quick-send; they do not call the endpoints above.

**Steps, mobile.**
1. Exam detail > "Send Exam Notification" (or `/exam/notify`). Screen "Send Exam Notification": "Select Exam *", "Notification Type *" (Hall Ticket Available, Results Published, Exam Schedule, Custom), "Message *", "Target Audience *" (Students, Parents, Both), "Delivery Channels *" (push, email, SMS). Validation toasts "Please select an exam", "Please enter a notification type", "Please enter a message", "Please select at least one delivery channel". Success toast reports the queued count.

**Expected results.**
- `notify`: response with the number of recipients that would be notified; nothing is sent or stored (the service is a stub); an audit row `notification_queued` is written.
- SMS endpoints: rows in `notification_queue` (channel `sms`, status `queued`, target type `exam_schedule`, `results_notification` or `hall_ticket_notification`) and a Celery task `send_notification_batch` is started with the queue ids.

**API endpoints.**
- `POST /exams/{exam_id}/notify`: body `{notification_type (string), message, target_audience ("students" default, "parents", "all"), send_push=true, send_sms=false, send_email=true}`; returns `{exam_id, notifications_queued, notification_type}`.
- `POST /exams/{exam_id}/dates/send-schedule`: `student_ids` is a bare list parameter, so it is read from the JSON body as an array of uuids. Returns `{status:"queued", queued_count, skipped_count, detail}`.
- `POST /exams/{exam_id}/send-results-notification?student_ids=<uuid>&student_ids=<uuid>`: required repeated query parameter.
- `POST /exams/{exam_id}/send-hall-ticket-notification?student_ids=...`: same.

**Rules and validations.**
- `notify` recipient count: "students" = distinct students enrolled in the exam's class-sections; "parents" = distinct parent ids linked to those students; any other `target_audience` value (including "all" and the mobile value "both") = students plus parents. The channel flags and `notification_type` do not change behaviour. The exam is not checked: an unknown id returns 200 with 0. A missing `message` gives 422 (no minimum length on the server).
- SMS endpoints: unknown exam 404 `Exam not found`. Per student: student not found, no linked parent, or parent without phone is skipped and counted in `skipped_count`; otherwise one queue row addressed to the first linked parent. Messages: schedule "Dear <parent>, the <exam> exam for <student> begins on TBA. Timetable on the app. - COS360" (the date is always `TBA` because the exam header has no date), results "Results for <student> - <exam> are published. View on the app. - COS360" (template variables carry total marks and percentage when a result exists, `N/A` otherwise), hall ticket "Hall ticket for <student> (<exam>) is ready. Download from the app. - COS360" (variables carry the hall ticket number or `N/A`). Results and hall ticket sends do not require publication.
- The triggering user id is read from the `sub` claim. The audit log does not record SMS sends.

**Error and edge cases.**
- Missing `student_ids` on the results and hall ticket endpoints: 422. Empty list: `queued_count` 0.
- Without a worker or broker the `.delay` call can fail after the rows are committed.

**Unit-testable logic.**
- `queue_notifications` branch selection for students, parents and all (with a fake session returning counts); web `notificationSchema` (message min length, channel min 1); message string formats.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXM-19-U01 | `queue_notifications` with `target_audience="students"` (fake session returning 4) | Returns 4 using the student count query | passing |
| TC-EXM-19-U02 | `queue_notifications` with `"parents"` returning 3 | Returns 3 using the parent count query | passing |
| TC-EXM-19-U03 | `queue_notifications` with `"all"` and `"both"` | Both use the combined query (students plus parents) | passing |
| TC-EXM-19-U04 | `queue_notifications` when the query returns no row or NULL | Returns 0 | passing |
| TC-EXM-19-U05 | `NotificationRequest` defaults | `target_audience` "students", `send_push` True, `send_sms` False, `send_email` True | passing |
| TC-EXM-19-U06 | `NotificationRequest` without `message` | Validation error | passing |
| TC-EXM-19-U07 | Web `notificationSchema` message of 9 and 10 characters; no channels | 9 invalid; 10 valid; empty channels invalid | blocked: notificationSchema is a non-exported const in web/src/pages/exam/ExamNotification.tsx; needs it exported |
| TC-EXM-19-U08 | Results message text for a student "Ann Lee" and exam "QA FA1" | `Results for Ann Lee - QA FA1 are published. View on the app. - COS360` (the code uses an em dash, U+2014, where this text has a hyphen) | passing |
| TC-EXM-19-A01 | POST notify `{notification_type:"custom", message:"Exam starts Monday", target_audience:"students"}` (ADMIN) | 200 `{notifications_queued: 4, notification_type: "custom"}` for four enrolled students | passing |
| TC-EXM-19-A02 | POST notify audience `parents` with 3 linked parents (2 children share one parent) | `notifications_queued` equals the distinct parent count | passing |
| TC-EXM-19-A03 | POST notify audience `all`; audience `both`; audience `xyz` | Students plus parents each time | passing |
| TC-EXM-19-A04 | POST notify without `message` | 422 | passing |
| TC-EXM-19-A05 | POST notify for an unknown exam | 200 with `notifications_queued` 0 | passing |
| TC-EXM-19-A06 | POST notify writes an audit row | `notification_queued` with metadata type, audience, recipients | passing |
| TC-EXM-19-A07 | POST notify as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-19-A08 | POST send-schedule as ADMIN (no `exams:send_sms`) | 403 | passing |
| TC-EXM-19-A09 | POST send-schedule as ADMIN+SMS with 2 student ids (one with a parent phone, one without), Celery task mocked | 200 `{status:"queued", queued_count: 1, skipped_count: 1}`; one `notification_queue` row `exam_schedule`; task called with the row id and tenant | skipped: needs exams:send_sms granted to a role (role grants must not change) and would reach the SMS queue and Celery |
| TC-EXM-19-A10 | POST send-schedule with an empty list or no body | 200 `queued_count` 0 | skipped: needs exams:send_sms granted to a role (role grants must not change) and would reach the SMS queue and Celery |
| TC-EXM-19-A11 | POST send-schedule unknown exam | 404 `Exam not found` | skipped: needs exams:send_sms granted to a role (role grants must not change); |
| TC-EXM-19-A12 | POST send-schedule with an unknown student id | Counted in `skipped_count` | skipped: needs exams:send_sms granted to a role and a parent phone; |
| TC-EXM-19-A13 | Queue row text for send-schedule | `rendered_message` contains `begins on TBA` | skipped: needs exams:send_sms granted to a role and would queue a real SMS |
| TC-EXM-19-A14 | POST send-results-notification with two student ids as ADMIN+SMS | 200 `queued_count` 2; rows `results_notification`; variables include total marks and percentage | skipped: needs exams:send_sms granted to a role and would queue a real SMS |
| TC-EXM-19-A15 | POST send-results-notification for a student with no result | Queued with `N/A` variables | skipped: needs exams:send_sms granted to a role and would queue a real SMS |
| TC-EXM-19-A16 | POST send-results-notification without `student_ids` | 422 | passing |
| TC-EXM-19-A17 | POST send-results-notification unknown exam | 404 | skipped: the unknown-exam 404 is only reachable after the exams:send_sms check, which no seeded role passes |
| TC-EXM-19-A18 | POST send-hall-ticket-notification with ids as ADMIN+SMS | 200; rows `hall_ticket_notification`; variables carry the hall ticket number or `N/A` | skipped: needs exams:send_sms granted to a role and would queue a real SMS |
| TC-EXM-19-A19 | POST send-hall-ticket-notification without `student_ids`; unknown exam | 422; 404 | passing |
| TC-EXM-19-A20 | The three SMS endpoints as TEACHER, STAFF, STUDENT, PARENT | 403 each | passing |
| TC-EXM-19-A21 | The three SMS endpoints and notify with NOAUTH | 401 each | passing |
| TC-EXM-19-A22 | Tenant isolation: ADMIN+SMS of tenant B sends for tenant A's exam and student ids | 404 for the exam; no queue rows in either tenant | skipped: needs exams:send_sms granted to a tenant B admin (role grants must not change) |
| TC-EXM-19-A23 | Token A with `cschema` B on notify | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXM-19-E01 | P1 | Web | Admin | TC-EXM-06-E01 done (3 students). | 1. Sign in as Admin.<br>2. Open /exam/exams/<QA FA1 id>/notify.<br>3. Choose "Target Audience" "Students".<br>4. Keep only channel "Push Notification".<br>5. Enter "Message" "QA exam starts Monday".<br>6. Click "Send Notification". | Toast "3 notification(s) queued"; the form resets. Nothing is sent (stub); audit row notification_queued. | planned |
| TC-EXM-19-E02 | P3 | Web | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open the notify page.<br>3. Enter a 5-character message and click "Send Notification". | Inline "Message must be at least 10 characters". | planned |
| TC-EXM-19-E03 | P3 | Web | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open the notify page.<br>3. Deselect every channel and click "Send Notification". | Inline "Select at least one channel". | planned |
| TC-EXM-19-E04 | P2 | Web | Teacher | QA FA1 exists. | 1. Sign in as Teacher.<br>2. Open /exam/exams/<id>/notify. | Redirected to the exam detail. | planned |
| TC-EXM-19-E05 | P1 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open QA FA1 > "Send Exam Notification".<br>3. Choose "Notification Type *" "Custom", "Message *" "QA exam starts Monday", "Target Audience *" "Both", channel "Push Notification".<br>4. Tap "Send Notification". | Success toast with the queued count. | planned |
| TC-EXM-19-E06 | P3 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open "Send Exam Notification".<br>3. Leave "Message *" empty and tap "Send Notification". | Toast "Please enter a message". | planned |
| TC-EXM-19-E07 | P3 | Mobile | Admin | QA FA1 exists. | 1. Sign in as Admin.<br>2. Open "Send Exam Notification", enter a message.<br>3. Turn off all delivery channels and tap "Send Notification". | Toast "Please select at least one delivery channel". | planned |
| TC-EXM-19-E08 | P3 | Mobile | Teacher | None. | 1. Sign in as Teacher.<br>2. Navigate in-app to /exam/notify. | "You don't have permission to send notifications". | planned |

API tests implemented in: `backend/tests/api/exam/test_f12_f18_f19_summary_audit_notify.py`

Implemented in: backend/tests/unit/exam/test_results_audit_notify.py (U01-U06, U08). U07 blocked.

---

## Known gaps

Defects and doc-versus-code differences found while writing this page. Fix them in code or in `docs/modules/exam.md` and update the matching test cases.

| ID | Gap | Where | Affects |
|---|---|---|---|
| KG-1 | Fixed in code (2026-10-05): grant mark permission and the three exam-date create endpoints now read the `sub` claim. They used `current_user.get("id")` and returned 500. The API cases marked `xfail: KG-1` need a rerun. Mobile date create and grant still fail for another reason (KG-8). | `mark_permission_endpoints.py`, `exam_date_endpoints.py` | F08, F10 |
| KG-2 | Fixed in code: `exam_result_router` is included before `exam_router`, so `GET /exams/my-results` is no longer parsed as a uuid. It now returns 403 for students because of DEF-EXM-6. The API cases marked `xfail: KG-2` need a rerun. | `main_router.py`, `result_endpoints.py` | F17 |
| KG-3 | Partly fixed in code: the result list, hall ticket eligible and ineligible lists, download-all and the audit log return 403 for the role names Student and Parent, and single-student result and hall ticket download check ownership (`ensure_student_access`). Still open: `GET /results/{student_id}` ignores publish status; `enrolled-students`, class-sections, subject configs and dates stay readable through `exams:read`; custom role names are not blocked; the seeded `exam_hall_tickets:*_own` and `*_related` permissions are unused. The self-service views broke as a result (KG-21). | `hall_ticket_endpoints.py`, `result_endpoints.py`, `audit_endpoints.py` | F13, F14, F16, F17, F18 |
| KG-4 | No endpoint sets `locked` or `finalized`. The web publish button requires `locked`, so web cannot publish; the backend accepts publish from `active`. The ResultsPublish page has no navigation link. Mobile publishes from any status. | `ResultsPublish.tsx`, `result_service.publish_exam` | F16 |
| KG-5 | Compute applies every subject config of the exam to every student: multi-class exams and subjects without saved marks create `ABS` rows and fail the student. Remarks-only subjects (max 0) fail. No grade scheme anywhere gives `ABS` and fail. `sub_max` counts only entered components, which inflates percentages for partial marks. Rank ties receive distinct consecutive ranks. `publish_rank` is ignored. Component and subject minimum pass marks are ignored. | `aggregate_service.py` | F15, F16 |
| KG-6 | Mark entry does not check exam status, deadline, enrollment, that the component belongs to the config, or `remark_grade` membership. Authorization uses the path exam id but rows use the body exam id. Upload and template skip the delegation check and upload sets `entry_source` to `manual`. | `mark_entry_endpoints.py`, `mark_entry_service.py` | F10, F11 |
| KG-7 | Absent cannot be set from web (read-only badge), mobile (no toggle) or Excel (the text `ABS` is skipped, numbers clear absence). Only `POST /marks` with `is_absent` sets it. | `MarkEntryGrid.tsx`, `marks.tsx`, `mark_entry_endpoints.py` | F11 |
| KG-8 | Mobile defects: create success navigates with `res.id` but the API returns `exam_id` (opens `/exam/undefined`); date create and permission grant omit the required body `exam_id` (422); Excel upload omits `class_id` and `section_id` (422) and accepts CSV (backend 400); the grid request omits `section_id` for section-less class-sections (422); the permission teacher select falls back to the staff id when there is no user id. | `create.tsx`, `dates.tsx`, `permissions.tsx`, `marks.tsx`, `src/api/exam.ts` | F06, F08, F10, F11 |
| KG-9 | Web defects: the Exam Settings page cannot load on a tenant with no settings row (404); the create wizard has no Level control (always `primary`) and copies the exam name into `exam_type` (50 character limit); "Download All" saves a ZIP under a `.pdf` name; the permissions page shows "Unnamed user" (API returns no display name) and its banner wrongly says teachers can always enter marks; `/exam/exams/{id}/notify` and `/exam/exams/{id}/results` have no link; first-time web settings save is impossible. | `ExamSettings.tsx`, `CreateExam.tsx`, `HallTicketDownload.tsx`, `MarkPermissions.tsx` | F01, F06, F10, F14, F16, F19 |
| KG-10 | `PUT /exams/{id}` has no status check (docstring says draft or active), returns 500 on a duplicate name and on `term` over 20 characters. Clone ignores the request body name. Delete is allowed for every status except published (UI draft only; the graph view says draft only). | `exam_endpoints.py`, `exam_service.py` | F09 |
| KG-11 | Stored but unused: `publish_rank`, `mark_entry_deadline`, `weightage_percent`, `term`, `attendance_mode`, `is_internal`, `credit_hours`, internal and external split fields, component `min_pass_marks`, exam `hall_ticket_min_attendance`, settings `default_board`, `custom_board_name`, `exam_fee_type_id`, `grace_*`, `reconduct_max_failed_subjects`, attempt numbers above 1, `is_default` on grade schemes. Mobile settings PUT sends four fields and so resets the others (full overwrite). | various | F01, F06, F15, F16 |
| KG-12 | Deleting a subject grade scheme or remark set that is referenced fails with 500 (foreign key) instead of 409. Template names are unique across inactive rows in the database but checked only among active ones (500 on reuse). Web remark label limit (100) is above the backend limit (50). | `grading_service.py`, `remark_grade_service.py`, `exam_pattern_service.py`, `examSchemas.ts` | F04, F05, F07 |
| KG-13 | Hall tickets: numbers are `HT-2025-` plus an unstable list position (fixed year, change on recompute, skip ineligible positions); the published flag is not required for download; override does not assign a number; each override call replaces both flags (web "Fee" then "Attendance" loses the fee override); mobile "Mark Ineligible" cannot make a genuinely eligible student ineligible; stale rows remain after enrollment changes; `late` and `half_day` count as absent; the exam's own `hall_ticket_min_attendance` is ignored. | `hall_ticket_service.py`, `hall_ticket_pdf.py`, `EligibilityPanel.tsx`, `hall-tickets/[examId].tsx` | F13, F14 |
| KG-14 | `exams:send_sms` is not in any seeded role, so the three SMS endpoints return 403 for Admin until granted. The schedule SMS always says `TBA`. `docs/modules/exam.md` says these endpoints fail with 500 from wrong imports; the imports in `result_endpoints.py` and `hall_ticket_endpoints.py` are now valid and `HTTPException` is imported. | `exam_date_endpoints.py`, `result_endpoints.py`, `hall_ticket_endpoints.py`, `permission_catalog.py` | F19 |
| KG-15 | Remaining doc and code differences: `docs/modules/exam.md` parity table says mobile mark entry has an absent toggle (it shows a read-only "ABS" badge only); the publish error text says "Must be locked or active" but `finalized` is accepted. | `docs/modules/exam.md` | F11, F16 |
| KG-16 | `POST /exams/{id}/notify` only counts recipients and sends nothing. Audit rows are written only for delete, unlock, compute, publish, hall ticket compute, override and publish, and notify. | `notification_service.py`, `audit_service.py` | F18, F19 |
| KG-17 | Mark grid pagination is unvalidated (negative page gives 500). Section-less class-sections cannot be used for mark entry in web (queries disabled) or mobile (422). | `mark_entry_endpoints.py`, `useExam.ts`, `marks.tsx` | F11 |
| KG-18 | Subject config update accepts `is_active` but the table has no such column; `exam_id` in config, date and permission paths is not compared with the row's exam; the grid does not check that the config belongs to the exam or class. | `exam_subject_config_service.py`, `mark_entry_service.py` | F07, F10, F11 |
| KG-19 | Exam create accepts any string for `board` (not the enum), reports foreign key failures as a generic 409, and the web wizard sends `status` and `subject_grade_scheme_id` that the backend drops. Board patterns are not linked to exam creation. | `exam_create_full_schema.py`, `exam_endpoints.py` | F02, F06 |
| KG-20 | Mobile admin-only exam screens (Exam Settings, Board Patterns, the three grading screens, Create Exam, Mark Permissions, Audit list and Audit Log) crash on a cold load of their URL (Expo web address bar or refresh) with "Something went wrong" / "Attempted to navigate before mounting the Root Layout component": the role guard calls `router.replace` before auth and the root layout are ready. Opening them from the hub works. | `mobile/app/exam/settings.tsx`, `board-patterns.tsx`, `grade-schemes.tsx`, `subject-grade-schemes.tsx`, `remark-sets.tsx`, `create.tsx`, `permissions.tsx`, `audit.tsx`, `audit-log.tsx` | F01 to F05, F06, F10, F18 |
| KG-21 | Student and Parent hall ticket views (web `StudentHallTicketView` and the parent view in `HallTicketEligibility.tsx`, mobile `hall-tickets/[examId].tsx`) read the eligible and ineligible lists, which now return 403 for those roles, so they always show "You are not enrolled in this exam." and no download button. They need an own-record endpoint. | web `HallTicketEligibility.tsx`, mobile `hall-tickets/[examId].tsx` | F13, F14 |
| KG-22 | Web Board Patterns page shows "New Pattern", "Create First Pattern", edit and delete to every role (no route guard and no permission gate); the API answers 403 for Teacher and Staff. The sidebar also lists Board Patterns, Grading and Exam Settings for Teacher and Staff. | `web/src/pages/exam/BoardPatternSetup.tsx` | F02 |
| KG-23 | Web exam detail card "Academic Year" shows a dash when the page is opened directly, because it looks the id up in an academic year store that the page does not load (mobile shows the year). | `web/src/pages/exam/ExamDetail.tsx` | F06 |
| KG-24 | The web Marks list and the mobile "My Marks" list keep only draft, active and locked exams for every role, so a Student or Parent cannot open the raw marks of a published exam from them (web only by URL `/exam/my-marks/<id>`; mobile through the Exams list). | `web/src/pages/exam/MarkEntryExamList.tsx`, `mobile/app/exam/my-marks/index.tsx` | F17 |
| DEF-EXM-1 | `PUT /board-patterns/{id}` with `exam_types` returns the stale (old) exam types in the response; a following GET shows the replaced list. | board pattern service | F02 |
| DEF-EXM-2 | `PUT /grade-schemes/{kind}/{id}` with `bands` returns the stale band list in the response; a following GET is correct. | grading service | F03 |
| DEF-EXM-3 | `PUT /remark-grades/{id}` with `options` returns the stale options in the response; a following GET is correct. | remark grade service | F05 |
| DEF-EXM-4 | `PUT /exams/{id}/subject-configs/{cid}` returns 500 (MissingGreenlet) whenever a column value changes; the change is committed. | `exam_subject_config_service.py` | F07 |
| DEF-EXM-5 | `POST /exams/{id}/unlock` with a reason over 300 characters returns 500 (column limit) instead of 422. | `exam_endpoints.py` | F09 |
| DEF-EXM-6 | The Student role never receives `exam_results:read_own` (nor `exam_marks:read_own`, `exam_hall_tickets:*_own`): `ALL_ADMIN`, which defines the Full plan, omits those resources and role seeding filters role permissions by plan resources. `GET /exams/{id}/my-result` returns 403 `permission_denied` for every student, so students cannot see their published result. | `permission_catalog.py` (`ALL_ADMIN`), `role_seed_service.py`, `result_endpoints.py` | F09, F17 |
| DEF-EXM-7 | Fixed in code (2026-10-05, section parameter cast in `_load_hall_ticket_data`): hall ticket PDF and download-all work again. The API cases marked `xfail: DEF-EXM-7` need a rerun. | `hall_ticket_pdf.py` | F14 |
