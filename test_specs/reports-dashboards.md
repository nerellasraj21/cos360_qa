# Reports and dashboards (RPT)

This module covers everything a user meets after login that summarises the school: the home dashboard and module hub pages (cards built from the user's menu and permissions, on web and mobile), the Reports hub, and the report endpoints under `/api/v1/reports/*` (student, staff, fee, attendance and financial reports with CSV, Excel and PDF export, plus an export history that is never written). The expense reports live in the Expense module (EXP F14) and are cross-referenced here. The mobile app additionally has client-side Academic and Transport reports and a student attendance report built from list APIs, and the web app has a fee reports page. There is no web page for student, staff, financial or generic attendance reports; those endpoints are API-only on web. This page documents what the code does on 2026-10-02 and, where `docs/modules/reports-dashboards.md` disagrees with the code, the code wins and the difference is listed under Known gaps.

_Last verified against code: 2026-10-02_

Conventions: test IDs follow `docs/testing/strategy.md` (`TC-RPT-<FF>-<P><NN>`; U unit, A API, E end to end). All Status values are `planned`. Where a UI label contains the rupee sign or a dash character it is written here as "Rs" or a hyphen (plain text only). "Today" in numeric examples is 2026-10-02.

## Roles

Report endpoints check `<group>_reports` permissions (`read` to view, `export` to download) and the audit endpoints check `reports:read`. The attendance, fee and financial read endpoints skip the check for tokens flagged `is_superadmin`. Default grants from `backend/app/service/tenant/permission_catalog.py` (the QA tenant copies `test_tenant_schema`; read the real matrix from the login response before asserting a role):

| Role | Report grants in the default catalog |
|---|---|
| Admin | `student_reports`, `staff_reports`, `fee_reports`, `attendance_reports`, `financial_reports`: read, export. `reports`: read. `expense_reports`: read, list, export. |
| Staff | `fee_reports`, `student_reports`, `attendance_reports`: read, export. `staff_reports`: read only. `reports`: read. No `financial_reports`, no `expense_reports`. |
| Teacher | `student_reports`, `attendance_reports`: read, export. `reports`: read. Nothing else. |
| Student, Parent | None. The mobile app hides the Reports tab for them; the web menu has no Reports node for them by default. |

Dashboards: which cards a user sees depends on the menu returned at login (web) and on menu plus permissions (mobile), not on a permission string. Role rules in client code: web `filterMenuForRole` hides Fee for teachers and "My Fees" for students and the names Route Stops, Transport Trips, Student Transport for everyone; mobile hides Masters, Communication, Reports and Transport for student and parent, and Fee for teacher.

## Feature index

| ID | Title |
|---|---|
| F01 | Home dashboard (web and mobile, role-based cards) |
| F02 | Module hub pages |
| F03 | Reports hub |
| F04 | Student reports |
| F05 | Staff reports |
| F06 | Fee reports (collection, pending, structure) |
| F07 | Attendance reports (student and staff) |
| F08 | Financial reports (expenditure, ledger, summary) |
| F09 | Expense reports (entry points and cross-checks) |
| F10 | Academic report (mobile, client-side) |
| F11 | Transport report (mobile, client-side) |
| F12 | Report conventions and exports |
| F13 | Export history and download |

Endpoint prefixes under `/api/v1` (mounted in `backend/app/api/v1/main_router.py`): `/reports/students`, `/reports/staff`, `/reports/fees`, `/reports/attendance`, `/reports/financial`, `/reports` (audit and download).

---

## F01 Home dashboard (web and mobile, role-based cards)

**Purpose**: After login see a welcome and one card per module the user may open.

**Roles and permissions**: No permission string. Web cards come from the processed menu (`useMenuData`); mobile cards are the union of the permission-entitled static module list and the top-level backend menu entries.

**Preconditions**: Logged in; menu and permissions delivered by the login response.

**Steps, web**
1. Log in; `/` redirects to `/dashboard`. Header "Dashboard", subtitle "Welcome back, <name> (<Role>)" (name is the parent profile name or the username) or "Welcome to COS360 School Management System".
2. A grid shows one card per top-level menu item except "Dashboard", in the canonical order Students, Staff Management, Exam, Fee, Expense, Communication, Reports, Masters, Administration, Transport. Each card has an icon, the menu name and a description (for example Expense: "Expense transactions, approvals and summaries"; Transport: "Routes, vehicles and trips"; Reports: "Analytics and reports across modules"; unknown names: "Open <name>").
3. Click a card to open the module hub or page.

**Steps, mobile**
1. Open the Home tab (title "Dashboard"). The hero card shows "Good Morning," or "Good Afternoon," or "Good Evening," (before 12:00, before 17:00, otherwise), the username, today's date (for example "Friday, October 2") and an avatar with the first letter.
2. Under "Modules" tap a card (Students, Staff Management, Exam Management, Fee Management, Expense, Communication, Reports, Masters, Administration, Transport). With no visible card: lock icon and "No modules available. Contact your administrator."

**Expected results**: Web shows exactly the menu nodes the role is allowed; mobile shows the union of permission-entitled and menu-granted modules with the role hide rules applied, sorted in the web order.

**API endpoints**: None specific; the data comes from the login response (`menu`, `permissions`). See AUTH.

**Rules and validations**
- Web: teachers do not get Fee; students do not get "My Fees"; "Student Transport", "Route Stops", "Transport Trips" items are hidden everywhere; students and parents get a self-service Fee submenu injected when the backend sent none.
- Mobile: `hideForRoles` lists (lowercase role names): teacher hides Fee Management; student, parent, guardian, father, mother hide Communication, Reports, Masters and Transport. `alwaysShow` modules (Communication, Reports, Transport) appear for every other role. Other modules appear when the user has `read`, `list` or `read_own` on any of the module's resources (Students: `student_admissions`; Staff Management: `staff`, `designations`, `staff_attendance`; Exam: `exams`; Fee: `fee_transactions`; Expense: `expense_transactions`; Masters: `academic_years`; Administration: `user_management`, `role_management`, `staff`).
- Menu names are mapped to modules through aliases (Fee, Fees, Fee Management; Exam, Exams, Exam Management; Expense, Expenses; Administration, Admin). A menu entry without a styled module and without a path is skipped.
- Mobile tab bar visibility follows `moduleResources` per tab (for example Masters: `academic_years`, `classes`, `subjects`, `holiday_management`, `timetable_management`; Expense: `expense_categories`, `expense_transactions`, `expense_types`). Web has no equivalent.

**Error and edge cases**: User with no menu: web grid empty (header only); mobile shows the empty message. A late-loading menu on mobile never blanks the grid because permission-derived cards render first.

**Unit-testable logic**: Web `filterMenuForRole`, `MENU_ORDER` sorting, `ensureFeeMenu`, `injectFeeSubmenu`; mobile `accessibleModules` memo (permission filter, role hide rules, menu union, alias mapping, ordering), `roleTopLevelMenu`; greeting by hour.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-01-U01 | Web `filterMenuForRole` for role "teacher" with a Fee node | Fee node removed | passing |
| TC-RPT-01-U02 | Web `filterMenuForRole` for "student" with children "My Fees" and "Fee Receipts" | "My Fees" removed | passing |
| TC-RPT-01-U03 | Web filter on a Transport node with children Routes, Route Stops, Trips | Route Stops removed for all roles | passing |
| TC-RPT-01-U04 | Web ordering of top-level items [Reports, Students, Transport, Fee Management, Expense] | Students, Fee Management, Expense, Reports, Transport | passing |
| TC-RPT-01-U05 | Web `injectFeeSubmenu` for a flat L0 "Fee Management" for roles Admin and "teacher" | Children injected for Admin; untouched for teacher | passing |
| TC-RPT-01-U06 | Mobile `accessibleModules` for role "student" with no permissions | Students only if `student_admissions` granted; no Communication, Reports, Masters, Transport | blocked: mobile accessibleModules memo and greeting are inline in mobile/app/(tabs)/index.tsx; needs the helper exported (the shared menuUtils rules are covered in mobile/__tests__/reports/menuUtils.test.ts) |
| TC-RPT-01-U07 | Mobile for role "teacher" with `fee_transactions:list` | Fee Management hidden (role rule beats permission) | blocked: mobile accessibleModules memo and greeting are inline in mobile/app/(tabs)/index.tsx; needs the helper exported (the shared menuUtils rules are covered in mobile/__tests__/reports/menuUtils.test.ts) |
| TC-RPT-01-U08 | Mobile for Admin with `expense_transactions:list` and a menu node "Expenses" | One Expense card (alias dedupes the menu node) | blocked: mobile accessibleModules memo and greeting are inline in mobile/app/(tabs)/index.tsx; needs the helper exported (the shared menuUtils rules are covered in mobile/__tests__/reports/menuUtils.test.ts) |
| TC-RPT-01-U09 | Mobile menu node with an unknown name and a null path | Skipped; with a path, a generic card is added | blocked: mobile accessibleModules memo and greeting are inline in mobile/app/(tabs)/index.tsx; needs the helper exported (the shared menuUtils rules are covered in mobile/__tests__/reports/menuUtils.test.ts) |
| TC-RPT-01-U10 | Greeting at hours 9, 12, 16, 17, 23 | Good Morning, Good Afternoon, Good Afternoon, Good Evening, Good Evening | blocked: mobile accessibleModules memo and greeting are inline in mobile/app/(tabs)/index.tsx; needs the helper exported (the shared menuUtils rules are covered in mobile/__tests__/reports/menuUtils.test.ts) |
| TC-RPT-01-U11 | Mobile card order for permissions that produce [Transport, Students, Fee] | Students, Fee Management, Transport | blocked: mobile accessibleModules memo and greeting are inline in mobile/app/(tabs)/index.tsx; needs the helper exported (the shared menuUtils rules are covered in mobile/__tests__/reports/menuUtils.test.ts) |
| TC-RPT-01-A01 | Login as Admin and read `menu` and `permissions` | Menu contains the module nodes used by the dashboard; permissions map present | passing |
| TC-RPT-01-A02 | Login as Teacher | No `fee_*` grants; the client hides any Fee node | passing |
| TC-RPT-01-A03 | Login as Student and as Parent | Menu limited to the student and parent URL allowlist (dashboard, students, fee self-service, exam) | passing |

API tests implemented in: backend/tests/api/reports/test_conventions_audit.py
| TC-RPT-01-E01 | Web Admin logs in | Lands on `/dashboard`; header "Dashboard"; welcome text includes the username and "(Admin)"; cards for every module in canonical order | planned |
| TC-RPT-01-E02 | Web Teacher | No Fee card | planned |
| TC-RPT-01-E03 | Web Student | No Masters, Reports, Communication cards; a Fee card with self-service entries | planned |
| TC-RPT-01-E04 | Web Parent | Welcome text uses the parent profile name | planned |
| TC-RPT-01-E05 | Web: click the Expense card | Navigates to `/expense` | planned |
| TC-RPT-01-E06 | Mobile Admin | Hero greeting, date, avatar letter; module cards in web order | planned |
| TC-RPT-01-E07 | Mobile Teacher | No Fee Management card | planned |
| TC-RPT-01-E08 | Mobile Student | No Communication, Reports, Masters or Transport cards | planned |
| TC-RPT-01-E09 | Mobile user with no permissions and an empty menu | "No modules available. Contact your administrator." | planned |
| TC-RPT-01-E10 | Mobile: tap the Reports card | Opens the Reports tab | planned |

Implemented in (phase 1 unit tests): web/src/__tests__/reports/menu.test.ts (drives useMenuData with the store and query mocked); mobile mirror in mobile/__tests__/reports/menuUtils.test.ts.

---

## F02 Module hub pages

**Purpose**: Each module landing page lists its sections as cards built from the user's menu.

**Roles and permissions**: No permission check on the hubs; cards depend on the menu grants. Expense, Fee and Exam have their own overview pages (EXP F01 covers expense).

**Preconditions**: Menu children exist for the module and the role.

**Steps, web**
1. Open a hub: `/admin` (header "Administration", subtitle "Manage system settings, users, roles, and organization-wide configurations", section label "Administration Sections"), `/masters` ("Masters Dashboard", "Configure and manage all master data for the school system", "Masters Sections"), `/students` ("Students Dashboard", "Comprehensive management of student data, admissions, and records", "Students Sections"), `/transport` ("Transport Dashboard", see TRN F01), `/reports` (F03).
2. Cards are the children of that module's node in the raw menu (not the processed sidebar menu). A card with a path navigates; a card without a path is dimmed. The Students hub hides "Student Transport"; the Transport hub hides Route Stops, Transport Trips and Student Transport. Card descriptions come from a hard-coded map keyed by menu name, otherwise "Manage <name>".
3. There is no "Coming Soon" banner in the web hub code.

**Steps, mobile**
1. Tabs for masters, students, staff, fees, exam, expense, transport, communication, reports and admin act as hubs. The Masters tab (`/(tabs)/masters`) merges permission-based sections with the menu; the Expense tab lists Overview, Categories, Types, Transactions, Departments, Summary (EXP F01); the Transport tab lists Routes and Vehicles (TRN F01).

**Expected results**: Hub cards match the tenant's menu rows for the role; because hubs read the raw menu while the sidebar reads the processed menu, the two can differ (the sidebar adds the Fee submenu and "School Registration" under Masters and removes hidden names).

**API endpoints**: None specific (the menu comes from login; menu administration is in AUTH and TEN).

**Rules and validations**: A screen that exists in code but has no child entry in the tenant's `menus` table does not appear on web hubs; on mobile it appears only if it is in that hub's fallback or permission list.

**Error and edge cases**: A role with no children for the module sees a header and no cards. A child without a path is greyed out and inert.

**Unit-testable logic**: Hub card selection (find the node by lowercased name, filter hidden names); description lookup with the fallback text.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-02-U01 | Students hub filter on children [Admission, Student Transport, Attendance] | Admission and Attendance only | blocked: hub card selection and description lookup are inline in the web route components (routes/_app/*/index.tsx); needs the helpers exported |
| TC-RPT-02-U02 | Description lookup for "Holidays" and for an unmapped name "Foo Bar" | Mapped text; "Manage foo bar" | blocked: hub card selection and description lookup are inline in the web route components (routes/_app/*/index.tsx); needs the helpers exported |
| TC-RPT-02-U03 | Hub node lookup is case-insensitive | A "MASTERS" menu node is found for the Masters hub | blocked: hub card selection and description lookup are inline in the web route components (routes/_app/*/index.tsx); needs the helpers exported |
| TC-RPT-02-A01 | Login response `menu` for Admin | Contains the module nodes with children and `path` values used by the hubs | passing |
| TC-RPT-02-A02 | Login response menu for Student versus Admin | Student tree is the allowlisted subset | passing |

API tests implemented in: backend/tests/api/reports/test_conventions_audit.py
| TC-RPT-02-E01 | Web Admin opens `/admin` | Header "Administration"; cards from the Administration node | planned |
| TC-RPT-02-E02 | Web Admin opens `/masters` | "Masters Dashboard" with a card per Masters child | planned |
| TC-RPT-02-E03 | Web Admin opens `/students` | "Students Dashboard"; no "Student Transport" card | planned |
| TC-RPT-02-E04 | Web: click a card whose menu item has a path | Navigates to that path | planned |
| TC-RPT-02-E05 | Web: a card without a path | Dimmed; click does nothing | planned |
| TC-RPT-02-E06 | Web: compare hub cards with sidebar children for Masters | Hub lacks the injected "School Registration" entry the sidebar shows | planned |
| TC-RPT-02-E07 | Mobile Admin opens the Masters tab | Permission-based sections plus menu sections | planned |
| TC-RPT-02-E08 | Mobile Teacher | Masters tab visible only when the teacher holds one of the module resources | planned |

---

## F03 Reports hub

**Purpose**: One place to reach the available reports.

**Roles and permissions**: The web hub is built from the Reports node of the menu; when the node has no children, two fallback cards appear for users with `fee_reports:read` (Fee Reports to `/fee/reports`) and `expense_reports:read` (Expense Reports to `/expense/reports`). Mobile hides the tab for student and parent; cards need `read` or `list` on any resource listed for the card.

**Preconditions**: Reports node seeded in the menu (the demo catalog seeds "Reports" with no children, which triggers the fallback cards).

**Steps, web**
1. Open Reports (`/reports`). Header "Reports", subtitle "Comprehensive analytics and reporting across all school modules", label "Reports Sections".
2. Cards use descriptions from a map: Student Reports ("Attendance, performance, and enrollment analytics"), Fee Reports ("Fee collection, outstanding dues, and payment summaries"), Academic Reports ("Exam results, marks, and grade distribution"), Expense Reports ("Expense analysis, budget vs actual, and department-wise reports"), Transport Reports ("Route utilization, vehicle usage, and trip analytics"), Staff Reports ("Staff attendance, performance, and workforce analytics"), Export & Downloads ("Bulk export data in CSV, PDF, and Excel formats"); other names get "<name> analytics and reports". Only cards with a path navigate. Only fee and expense reports have web pages.

**Steps, mobile**
1. Reports tab (title "Reports", banner "Reports"). Cards: Student Reports (resources `students`, `student_attendance`; route `/reports/student-reports`), Fee Reports (`fee_reports`, `fee_transactions`), Staff Reports (`staff`, `staff_attendance`), Transport Reports (`routes`, `vehicles`, `transport_trips`), Academic Reports (`exams`, `exam_results`); backend menu children not covered by these are appended. The standalone `/reports` stack screen (title "Reports") lists the same five with subtitles ("Collection summary, pending fees, fee structure" for Fee, "Admission stats, class-wise strength, demographics" for Student, "Exam results, grade distributions, subject performance" for Academic, "Staff attendance, designation-wise count" for Staff, "Route utilisation, student transport summary" for Transport) using permissions only.

**Expected results**: Each visible card opens its report screen; a user without the card's resources does not see it.

**API endpoints**: None specific.

**Rules and validations**: Hub completeness depends on seeded menu rows (web) and the static list (mobile). Mobile screens add gates: Staff, Academic and Transport screens block role `student`, the Fee screen blocks `teacher`, Student Reports has no role block.

**Error and edge cases**: A user without matching permissions sees no cards; direct navigation to a screen shows the access gate.

**Unit-testable logic**: Web fallback section builder; mobile permission filter and merge with menu children (dedupe by route).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-03-U01 | Web fallback with grants `fee_reports:read` only | One card "Fee Reports" with path `/fee/reports` | blocked: fallback section builder is inline in web/src/routes/_app/reports/index.tsx; needs the helper exported |
| TC-RPT-03-U02 | Web fallback with both fee and expense grants | Two cards, Fee Reports then Expense Reports | blocked: fallback section builder is inline in web/src/routes/_app/reports/index.tsx; needs the helper exported |
| TC-RPT-03-U03 | Web: menu children present and fallback grants present | Menu children win; fallback ignored | blocked: fallback section builder is inline in web/src/routes/_app/reports/index.tsx; needs the helper exported |
| TC-RPT-03-U04 | Mobile filter for a user with only `student_attendance:list` | Student Reports card only | blocked: mobile reports hub filter and merge are inline in the mobile reports screen; needs the helper exported |
| TC-RPT-03-U05 | Mobile merge: menu child whose mapped route equals an existing card | Not duplicated | blocked: mobile reports hub filter and merge are inline in the mobile reports screen; needs the helper exported |
| TC-RPT-03-A01 | Admin login `permissions` include `fee_reports` and `expense_reports` | Both present with `read` | passing |
| TC-RPT-03-A02 | Teacher login `permissions` | `student_reports` and `attendance_reports` present; no `fee_reports` | passing |

API tests implemented in: backend/tests/api/reports/test_conventions_audit.py
| TC-RPT-03-E01 | Web Admin opens `/reports` with the Reports node childless | Fee Reports and Expense Reports cards (fallback) | planned |
| TC-RPT-03-E02 | Web: click "Fee Reports" | Opens `/fee/reports` | planned |
| TC-RPT-03-E03 | Web: tenant menu with a child "Student Reports" without a path | Card dimmed, no navigation | planned |
| TC-RPT-03-E04 | Mobile Admin opens the Reports tab | Five report cards | planned |
| TC-RPT-03-E05 | Mobile Teacher | Only cards whose resources the teacher holds (Student Reports; Academic and Transport when exam or route grants exist); no Fee Reports | planned |
| TC-RPT-03-E06 | Mobile Student | Reports tab absent | planned |

---

## F04 Student reports

**Purpose**: List students (by admission) with class and section, address and city, and view one student's admission details; export the list.

**Roles and permissions**: `student_reports:read` (summary, details), `student_reports:export` (export). Admin, Staff and Teacher in the default catalog.

**Preconditions**: Admissions with class, section and academic year set.

**Steps, web**: No page. Call the API directly; this is the web gap.

**Steps, mobile**: The mobile "Student Reports" screen does not use these endpoints; it is the attendance report in F07.

**Expected results**: `GET /reports/students/summary` returns the standard report envelope (F12) with one row per admission.

**API endpoints**
- `GET /reports/students/summary?academic_year_id=&class_id=&section_id=&gender=&caste=&religion=&student_type=&address_city=&page=1&page_size=100&sort_by=&sort_order=asc|desc`. Row fields: `sl_no`, `admission_no`, `student_id`, `class_section` ("<class>-<section>"), `address` (line 1), `city`, `academic_year`.
- `GET /reports/students/details/{student_id}?academic_year_id=` returns `{data: {id, admission_number, student_id, admission_date, address_line1, address_line2, city, state, previous_school_name, previous_class, class_name, section_name, academic_year}}`.
- `POST /reports/students/export` body `{report_type: "student_summary", filters: {...StudentSummaryFilter}, format: "csv"|"xlsx"|"pdf", filename}` returns the file.

**Rules and validations**
- Only `academic_year_id`, `class_id`, `section_id` and `address_city` filter the data; `gender`, `caste`, `religion` and `student_type` are accepted and ignored.
- Joins to class, section and academic year are inner joins, so an admission without a section or class is not listed.
- `sort_by` must be an attribute of `Admission`; unknown names are ignored. `page >= 1`, `page_size` 1-1000 (default 100).
- A permission failure on the summary endpoint becomes 500 "Internal server error" (bare `except`); details and export re-raise the 403.
- `report_type` must be `student_summary` (else 400 "Unsupported report type"); a format other than csv, xlsx, pdf is rejected by the request schema (422) before the endpoint's own 400 message.

**Error and edge cases**: Unknown student in details 404 "Student not found"; no matching rows returns `data: []`, `total_count: 0`, `total_pages: 0`.

**Unit-testable logic**: `apply_filters` mapping (ignored keys), `total_pages` ceiling, `sl_no` offset, `apply_sorting` attribute check.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-04-U01 | `apply_filters` with `{"class_id": X, "gender": "F"}` and mappings without gender | Only the class predicate is added | passing |
| TC-RPT-04-U02 | `sl_no` for page 3, page_size 50 | Rows numbered 101 to 150 | passing |
| TC-RPT-04-U03 | `apply_sorting(sort_by="nonexistent")` | Query unchanged | passing |
| TC-RPT-04-U04 | `total_pages` for total 0, 1, 100, 101 with page_size 100 | 0, 1, 1, 2 | passing |
| TC-RPT-04-A01 | Admin `GET /reports/students/summary` with 3 admissions | 200; `total_count=3`; each row has the seven documented fields; `class_section` like "5-A" | passing |
| TC-RPT-04-A02 | `?class_id=<c>`; `?section_id=<s>`; `?address_city=<city>`; `?academic_year_id=<y>` | Each narrows the rows | passing |
| TC-RPT-04-A03 | `?gender=Female&caste=X&religion=Y&student_type=Z` | All rows returned (filters ignored); documents the gap | passing |
| TC-RPT-04-A04 | `?page=2&page_size=2` with 5 rows | 2 rows, `sl_no` 3 and 4, `total_pages=3` | passing |
| TC-RPT-04-A05 | `?page=0`; `?page_size=1001`; `?sort_order=up` | 422 each | passing |
| TC-RPT-04-A06 | `?sort_by=admission_number&sort_order=desc` | Rows in descending admission number | passing |
| TC-RPT-04-A07 | Admission with no section | Not present in the result | passing |
| TC-RPT-04-A08 | `GET /reports/students/details/{student_id}` for an admitted student | 200 `{data:{...}}` with the thirteen documented fields | passing |
| TC-RPT-04-A09 | `details` with an unknown student; with an `academic_year_id` that has no admission | 404 "Student not found" for both | passing |
| TC-RPT-04-A10 | `POST /reports/students/export` csv for `student_summary` | 200 `text/csv`; `Content-Disposition: attachment; filename=student_student_summary_<tenant id>.csv`; header row equals the row keys | passing |
| TC-RPT-04-A11 | Export with `format:"xlsx"` and `"pdf"` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; `application/pdf` | passing |
| TC-RPT-04-A12 | Export with `format:"docx"`; `report_type:"other"`; custom `filename:"qa_students"` | 422; 400 "Unsupported report type"; filename `qa_students.csv` | passing |
| TC-RPT-04-A13 | Export of 150 rows with `filters:{page_size:100}` | All 150 rows exported (page filters ignored) | passing |
| TC-RPT-04-A14 | Export when no rows match | 200 with an empty body and a filename without extension (documents the gap) | passing |
| TC-RPT-04-A15 | Role matrix on summary and details | Admin, Staff, Teacher 200; Student, Parent denied (summary returns 500, details returns 403) | passing; xfail: RPT-BUG-SUMMARY-500 (summary denial is 500, target 403) |
| TC-RPT-04-A16 | Role matrix on export | Admin, Staff, Teacher 200; Student, Parent 403 | passing |
| TC-RPT-04-A17 | No token on each endpoint | 401 (the summary may surface as 500 because of the bare except; record the status) | passing |
| TC-RPT-04-A18 | Tenant isolation | Tenant B summary and export contain no tenant A admissions; details of an A student returns 404 | passing |

API tests implemented in: backend/tests/api/reports/test_student_reports.py
| TC-RPT-04-E01 | Web: look for a student report page | None exists; the Reports hub offers none (documents the gap) | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_lists.py.

---

## F05 Staff reports

**Purpose**: List staff with department and designation and view one staff member's details; export the list.

**Roles and permissions**: `staff_reports:read` (summary, details), `staff_reports:export` (export). Admin has both; Staff has read only.

**Preconditions**: Staff rows with a designation.

**Steps, web**: No page.

**Steps, mobile**: The mobile "Staff Reports" screen is the attendance report (F07), not these endpoints.

**Expected results**: Standard report envelope (F12) with one row per staff member.

**API endpoints**
- `GET /reports/staff/summary?academic_year_id=&department_id=&gender=&caste=&employment_type=&address_city=&subject_id=&page=&page_size=&sort_by=&sort_order=`. Row fields: `sl_no`, `staff_id`, `full_name`, `department`, `designation`, `email`, `phone`, `address`, `gender`, `is_active`, `academic_year` (always "N/A").
- `GET /reports/staff/details/{staff_id}` returns `{data: {id, full_name, first_name, last_name, email, phone, address, date_of_birth, gender, qualification, experience_years, joining_date, is_active, department, designation_name, academic_year}}`.
- `POST /reports/staff/export` body `{report_type: "staff_summary", filters, format, filename}`.

**Rules and validations**
- Only `gender` filters the data. `department_id`, `employment_type`, `caste`, `address_city`, `subject_id` and `academic_year_id` are accepted and ignored (the service maps `department`, which the filter model does not have).
- Staff without a designation are excluded (inner join).
- A permission failure on the summary endpoint returns 500 "Internal server error"; details and export re-raise 403.
- `report_type` must be `staff_summary`.

**Error and edge cases**: Unknown staff 404 "Staff not found".

**Unit-testable logic**: Filter mapping (gender only), inner-join exclusion, name concatenation `"<first> <last>"`, `academic_year` constant.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-05-U01 | `apply_filters` with `{"gender":"Male","department_id":X}` and mappings `{gender, department}` | Only the gender predicate applies | passing |
| TC-RPT-05-U02 | Row builder for staff "Asha" "Rao" | `full_name="Asha Rao"`, `academic_year="N/A"` | passing |
| TC-RPT-05-A01 | Admin `GET /reports/staff/summary` with 3 staff | 200 `total_count=3`; documented fields | passing |
| TC-RPT-05-A02 | `?gender=Female` | Only female staff | passing |
| TC-RPT-05-A03 | `?department_id=<d>&employment_type=x&subject_id=<s>` | All staff returned (filters ignored) | passing |
| TC-RPT-05-A04 | Staff row without a designation | Excluded from the summary | passing |
| TC-RPT-05-A05 | `?page=2&page_size=2` with 5 staff; `?page_size=0` | `sl_no` 3 and 4; 422 | passing |
| TC-RPT-05-A06 | `GET /reports/staff/details/{staff_id}` | 200 with the sixteen documented fields | passing |
| TC-RPT-05-A07 | Details for an unknown staff id | 404 "Staff not found" | passing |
| TC-RPT-05-A08 | `POST /reports/staff/export` csv, xlsx, pdf | 200 with `text/csv`, the spreadsheet type, `application/pdf` | passing; xfail: RPT-EXPORT-ENUM (gender cell is GenderEnum.Male) |
| TC-RPT-05-A09 | Export with `report_type:"staff_attendance"` | 400 "Unsupported report type" | passing |
| TC-RPT-05-A10 | Role matrix summary and details | Admin 200; Staff 200; Teacher, Student, Parent denied (summary 500, details 403) | passing; xfail: RPT-BUG-SUMMARY-500 (summary denial is 500, target 403) |
| TC-RPT-05-A11 | Role matrix export | Admin 200; Staff 403 (read only); Teacher, Student, Parent 403 | passing |
| TC-RPT-05-A12 | Tenant isolation | Tenant B sees no tenant A staff | passing |

API tests implemented in: backend/tests/api/reports/test_staff_reports.py
| TC-RPT-05-E01 | Web: look for a staff report page | None exists (documents the gap) | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_lists.py.

---

## F06 Fee reports (collection, pending, structure)

**Purpose**: Analyse fee collection, outstanding balances and the fee structure, with summary statistics and export.

**Roles and permissions**: `fee_reports:read` (all GET endpoints; skipped for superadmin tokens), `fee_reports:export` (export). Admin and Staff in the default catalog. Web page guard `fee_reports:read`; the mobile screen blocks the teacher role.

**Preconditions**: Fee types, class mappings, student mappings and transactions (FEE module).

**Steps, web**
1. Open Fee > Fee Reports (`/fee/reports`; menu label "Fee Reports"). Header "Fee Reports & Export", subtitle "Generate reports and export fee data".
2. Filters: class, section, "All Categories" (fee category), "From" and "To" dates, "All Methods" (Cash, UPI, Cheque, Bank Transfer), "All Status" (Completed, Pending, Cancelled, Bounced), "Clear". Until one filter is chosen the page shows "Select at least one filter to generate a report".
3. Tabs "Collection Summary", "Pending Fees", "Fee Structure", each with statistic cards and a paginated table (page size 50, Previous and Next).
4. Collection table columns: S.No., Transaction #, Student, Class/Section, Category, Type, Term, Due, Paid, Method, Status, Date, Collected By. Pending: S.No., Admission No, Student, Class/Section, Category, Type, Term, Due, Paid, Balance, Due Date, Days Overdue. Structure: S.No., category, type, term, class, amount, year, status.
5. A format selector (CSV, Excel, PDF; default Excel) and "Export" (enabled only with at least one filter) download the report for the active tab: `fee_collection_summary`, `pending_fees` or `fee_structure`.

**Steps, mobile**
1. Reports tab, "Fee Reports" (blocked for teacher). Banner "Fee Reports" with "Export" (CSV share of the active tab). Tabs "Collection", "Pending", "Structure". On Collection a date filter: "All Time", "Today", "Last 7D", "This Month". Stat tiles: Collected, Rate (collection), Total Pending, Students, Overdue (pending), Avg Fee, Categories, Fee Types (structure).

**Expected results**: Tables and stats agree with the underlying fee data; exports contain every matching row.

**API endpoints**
- `GET /reports/fees/collection-summary?academic_year_id=&fee_category_id=&fee_type_id=&payment_method=&status=&date_from=&date_to=&class_id=&section_id=&page=1&page_size=100&sort_by=&sort_order=desc`; row fields `sl_no`, `transaction_number`, `student_admission_no`, `student_name`, `class_section` ("Class - Section"), `fee_category`, `fee_type`, `fee_term`, `amount_due`, `amount_paid`, `payment_method`, `payment_status`, `transaction_date`, `collected_by`.
- `GET /reports/fees/collection-summary/stats` returns `{total_collected, total_due, collection_percentage, payment_methods, fee_categories, monthly_collection}`.
- `GET /reports/fees/pending-fees?academic_year_id=&fee_category_id=&fee_type_id=&fee_term_id=&class_id=&section_id=&days_overdue=&amount_min=&amount_max=&page=&page_size=&sort_by=&sort_order=asc`; row fields `sl_no`, `student_admission_no`, `student_name`, `class_section`, `fee_category`, `fee_type`, `fee_term` ("Annual" when no term), `amount_due`, `amount_paid`, `balance_amount`, `due_date`, `days_overdue`.
- `GET /reports/fees/pending-fees/stats` returns `{total_pending_amount, total_overdue_amount, total_students_with_pending, total_students_overdue, average_overdue_days, fee_categories_pending, class_wise_pending}`.
- `GET /reports/fees/fee-structure?academic_year_id=&fee_category_id=&fee_type_id=&class_id=&page=&page_size=&sort_by=&sort_order=asc`; row fields `sl_no`, `fee_category`, `fee_type`, `fee_term`, `class_name`, `section_name` (null), `fee_amount`, `academic_year`, `status`.
- `GET /reports/fees/fee-structure/stats` returns `{total_fee_types, total_categories, total_terms, average_fee_amount, fee_range: {min, max}, category_wise_breakdown}`.
- `POST /reports/fees/export` body `{report_type: "fee_collection_summary"|"pending_fees"|"fee_structure", filters, format, filename}`.

**Rules and validations**
- Collection stats count only `completed` transactions: `total_collected = sum(amount_paid)`; `total_due = sum over distinct (student, fee type, term date) of the maximum amount_due`; `collection_percentage = round(collected / due x 100, 2)`, 0 when due is 0; `payment_methods`, `fee_categories` and `monthly_collection` ("YYYY-MM") group the collected amounts.
- Pending rows: each fee mapping instalment with `due - paid > 0`. Paid amounts come from `completed` fee transactions per instalment (or per fee type when the mapping has no term dates). `days_overdue = today - due_date` when the due date is before today, else null. `amount_min`, `amount_max` and `days_overdue` filter the computed rows; `days_overdue` keeps rows overdue by at least that many days. Stats: overdue rows are those with `days_overdue > 0`; `average_overdue_days = round(mean, 1)`; totals rounded to 2 places.
- Date filters: `date_from` is a datetime or date string; a `date_to` given as `YYYY-MM-DD` is extended to 23:59:59.999999.
- These routes use bare parameter defaults, so `page=0` or `page_size=5000` surface as 500 (the validation error is caught), and an invalid date string also gives 500; the collection-summary 500 includes the exception text in `detail`.
- Export ignores page and page_size and returns every row; unsupported `report_type` gives 400 "Unsupported fee report type".

**Error and edge cases**: No matching data returns `data: []` and stats with zeros (`collection_percentage` 0.0). Superadmin tokens bypass the read permission check but not the export check.

**Unit-testable logic**: Collection stats arithmetic; pending balance and overdue computation; `_parse_date_to`; stats aggregation maps; sorting of pending rows (None values last).

**Test cases**

Fixture: student S1 has fee type Tuition with a mapped instalment due 5000.00 on 2026-08-01. Completed transaction T1 pays 3000.00 on 2026-09-05 (cash). A cancelled transaction T2 of 700.00 exists. Student S2 has an instalment of 4000.00 due 2026-12-01 with nothing paid.

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-06-U01 | Collection stats for T1 only | `total_collected=3000.0`, `total_due=5000.0`, `collection_percentage=60.0`, `payment_methods={"cash":3000.0}`, `monthly_collection={"2026-09":3000.0}` | passing |
| TC-RPT-06-U02 | Add completed T3 paying 2000.00 on the same instalment | `total_collected=5000.0`, `total_due=5000.0` (maximum per instalment), percentage 100.0 | blocked: sum and per-instalment max run in SQL (needs a database; covered by the API phase); predicate shape checked under TC-RPT-06-U03 |
| TC-RPT-06-U03 | Cancelled T2 present | Not counted in collected or due | passing |
| TC-RPT-06-U04 | `total_due=0` | `collection_percentage=0.0` | passing |
| TC-RPT-06-U05 | Pending balance for S1 | balance 2000.0; `days_overdue=62` on 2026-10-02 | passing |
| TC-RPT-06-U06 | Pending when paid equals due | Row excluded | passing |
| TC-RPT-06-U07 | Due date equal to today | `days_overdue=None` (not before today) | passing |
| TC-RPT-06-U08 | Pending S2 (due 2026-12-01) | Included with `days_overdue=None`; not counted as overdue in stats | passing |
| TC-RPT-06-U09 | Pending stats for S1 and S2 | `total_pending_amount=6000.0`, `total_overdue_amount=2000.0`, `total_students_with_pending=2`, `total_students_overdue=1`, `average_overdue_days=62.0` | passing |
| TC-RPT-06-U10 | Filters `amount_min=3000`; `amount_max=3000`; `days_overdue=60`; `days_overdue=63` | S2 only; S1 only; S1 only; no rows | passing |
| TC-RPT-06-U11 | `_parse_date_to("2026-09-30")` and `("2026-09-30T10:00:00")` | 2026-09-30 23:59:59.999999; unchanged datetime | passing |
| TC-RPT-06-U12 | Pending sort by `days_overdue` (a key that can be None) ascending and descending, and by `balance_amount` descending | Rows with None last in both directions; balance order 4000.00 then 2000.00 | passing |
| TC-RPT-06-U13 | Structure stats for class mapping totals 1000 and 3000 | `average_fee_amount=2000.0`, `fee_range={"min":1000.0,"max":3000.0}` | passing |
| TC-RPT-06-A01 | Admin `GET /reports/fees/collection-summary` for the fixture | Rows only for item lines with a transaction; documented fields; `amount_due` and `amount_paid` are numbers | passing (empty-scope shape only); skipped: completed payments cannot be cleaned up |
| TC-RPT-06-A02 | `?status=completed`; `?payment_method=cash`; `?fee_type_id=<t>`; `?class_id=<c>` | Each narrows rows | skipped: needs completed fee payments |
| TC-RPT-06-A03 | `?date_from=2026-09-01&date_to=2026-09-05` (date-only upper bound) | Includes T1 created on 2026-09-05 | passing |
| TC-RPT-06-A04 | `?date_from=garbage` | 422 "date_from must be an ISO date or datetime" | passing |
| TC-RPT-06-A05 | `?page=2&page_size=1` with 3 rows | `sl_no` 2, `total_pages=3` | passing |
| TC-RPT-06-A06 | `?page=0`; `?page_size=5000` | Both 422 (router-level bounds) | passing |
| TC-RPT-06-A07 | `?sort_by=transaction_number&sort_order=asc`; unknown `sort_by` | Ordered; unknown ignored | passing |
| TC-RPT-06-A08 | `GET .../collection-summary/stats` | Matches U01 | passing |
| TC-RPT-06-A09 | `GET /reports/fees/pending-fees` | S1 row (balance 2000.0, days_overdue 62) and S2 row (balance 4000.0, days_overdue null) | xfail: RPT-PENDING-SPLIT |
| TC-RPT-06-A10 | `?days_overdue=30`; `?amount_min=2500&amount_max=5000` | S1 only; S2 only | xfail: RPT-PENDING-SPLIT |
| TC-RPT-06-A11 | `GET .../pending-fees/stats` | Matches U09 | xfail: RPT-PENDING-SPLIT |
| TC-RPT-06-A12 | `GET /reports/fees/fee-structure` | One row per (fee type, class mapping) with `section_name` null | passing |
| TC-RPT-06-A13 | `GET .../fee-structure/stats` | Matches U13; `category_wise_breakdown` counts fee types per category | passing |
| TC-RPT-06-A14 | `POST /reports/fees/export` for each of the three report types in csv, xlsx, pdf | 200 with the right content type and every matching row | passing |
| TC-RPT-06-A15 | Export with `report_type:"x"`; with `format:"json"` | 400 "Unsupported fee report type"; 422 | passing |
| TC-RPT-06-A16 | Export collection summary with `filters:{"date_to":"2026-09-30"}` | Rows through the end of 2026-09-30 | passing |
| TC-RPT-06-A17 | Role matrix on all GET endpoints | Admin and Staff 200; Teacher, Student, Parent 403 | passing |
| TC-RPT-06-A18 | Role matrix on export | Admin and Staff 200; Teacher, Student, Parent 403 | passing |
| TC-RPT-06-A19 | Tenant isolation | Tenant B reports and stats exclude tenant A's transactions | passing |

API tests implemented in: backend/tests/api/reports/test_fee_reports.py
| TC-RPT-06-E01 | Web Admin opens `/fee/reports` | Prompt "Select at least one filter to generate a report"; no table data | planned |
| TC-RPT-06-E02 | Web: set a class filter | Collection Summary table and four stat cards load | planned |
| TC-RPT-06-E03 | Web: switch to Pending Fees | Table with Balance and Days Overdue columns; cards Total Pending, Total Overdue, Students Pending, Avg Overdue Days | planned |
| TC-RPT-06-E04 | Web: switch to Fee Structure | Cards Fee Types, Categories, Terms, Avg Fee | planned |
| TC-RPT-06-E05 | Web: choose a payment method and status, click "Clear" | Filters reset; the empty prompt returns | planned |
| TC-RPT-06-E06 | Web: select Excel and click "Export" with a filter set | A spreadsheet file downloads | planned |
| TC-RPT-06-E07 | Web: Next page on a table with more than 50 rows | Page 2 loads with continued S.No. | planned |
| TC-RPT-06-E08 | Web Teacher opens the page | Access denied panel | planned |
| TC-RPT-06-E09 | Mobile Admin: Fee Reports, switch tabs | Collection, Pending, Structure stats and lists load | planned |
| TC-RPT-06-E10 | Mobile: date filter "Today" on Collection | List and stats re-query with today's range | planned |
| TC-RPT-06-E11 | Mobile: Export | A CSV of the active tab is shared | planned |
| TC-RPT-06-E12 | Mobile Teacher | Screen blocked by the access gate | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_fee.py.

---

## F07 Attendance reports (student and staff)

**Purpose**: Review student or staff attendance records over a period with summary percentages; export them.

**Roles and permissions**: `attendance_reports:read` (list and stats; skipped for superadmin tokens), `attendance_reports:export` (export). Admin, Staff and Teacher in the default catalog.

**Preconditions**: Attendance rows (student attendance from the Students module, staff attendance from the Staff module).

**Steps, web**: No page for student attendance reports. The staff attendance API wrappers and hooks (`useStaffAttendanceReport`, `useStaffAttendanceStats`, `useExportStaffAttendance`) exist but no page calls them.

**Steps, mobile**
1. Reports tab, "Student Reports" (banner "Student Attendance Report"). Filter chips "Today", "Last 7D", "Last 30D"; tiles Present, Absent, Late, "Present Rate"; list "ATTENDANCE RECORDS"; "Export" shares a CSV (`student_attendance_report.csv`). Empty: "No records for this period". This screen is client-side: it loads `GET /student/attendance/search` and counts statuses itself (rate = present / total records, one decimal, a dash when empty).
2. Reports tab, "Staff Reports" (banner "Staff Attendance Report", blocks role student). Chips "Today", "Last 7D", "Last 30D", "Last 90D"; tiles Present, Absent, Rate (`attendance_percentage` with one decimal); list "RECORDS" (first 100 rows); "Export" CSV built from the on-screen rows. It calls the staff stats and report endpoints below.

**Expected results**: API rows and stats are computed server side for staff and student reports; the mobile student screen computes from raw attendance.

**API endpoints**
- `GET /reports/attendance/students?academic_year_id=&class_id=&section_id=&student_id=&date_from=&date_to=&attendance_status=&month=&year=&page=&page_size=&sort_by=&sort_order=` row fields `sl_no`, `admission_no`, `student_name`, `class_section`, `date`, `attendance_status`, `marked_at` (always null), `remarks`, `academic_year`.
- `GET /reports/attendance/students/stats` returns `{summary_stats: {total_students, present_count, absent_count, late_count, half_day_count, leave_count, excused_count, attendance_percentage, date_range}, class_wise_stats: [], monthly_trends: [], top_absentees: []}`.
- `GET /reports/attendance/staff?staff_id=&department=&designation_id=&date_from=&date_to=&attendance_status=&month=&year=&page=&page_size=&sort_by=&sort_order=` row fields `sl_no`, `staff_id` (staff UUID), `staff_name`, `designation`, `department`, `date`, `attendance_status`, `clock_in`, `clock_out`, `total_hours`, `marked_at` (all null), `remarks`.
- `GET /reports/attendance/staff/stats` returns `{summary_stats: {total_staff, present_count, absent_count, late_count, half_day_count, excused_count, attendance_percentage, date_range}, department_wise_stats: [], monthly_trends: [], late_arrivals: []}`.
- `POST /reports/attendance/export` body `{report_type: "student_attendance"|"staff_attendance", filters, format, filename}`.

**Rules and validations**
- `attendance_percentage = (present + 0.5 x half_day) / total_records x 100`, rounded to 2 places, 0.0 when there are no records. `date_range` is "<min date> to <max date>" of the matching rows.
- Status counts are case-sensitive on stored text: student stats count `present`, `absent`, `late`, `half_day`, `leave` and `Excused` (capital E); staff stats count `present`, `absent`, `late`, `half_day`, `excused`.
- Stats endpoints ignore `attendance_status`, `month`, `year` and (students) `student_id`; the list endpoints apply `month` and `year` only when both are given (`month` 1-12).
- `date_from` and `date_to` are inclusive dates. `page_size` 1-1000 (default 100).
- The student list joins every admission of the student with no academic-year restriction, so a student with several admissions can appear more than once.
- `sort_by` must be an attribute of the attendance model (default order: date descending, then first name).
- Student attendance export requires `report_type` `student_attendance`, staff `staff_attendance` (else 400 "Unsupported attendance report type").

**Error and edge cases**: No rows: empty `data`, zero stats, `date_range` null. Permission failures here re-raise as 403.

**Unit-testable logic**: Percentage formula and rounding; status counting; pagination offset and `sl_no`; month and year predicate; the mobile client-side count and rate.

**Test cases**

Fixture for stats: 12 student records in 2026-09: 8 present, 2 half_day, 1 absent, 1 late.

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-07-U01 | Percentage for 8 present, 2 half_day of 12 | (8 + 1) / 12 x 100 = 75.0 | passing |
| TC-RPT-07-U02 | Percentage for 1 present of 3 | 33.33 | passing |
| TC-RPT-07-U03 | Percentage with 0 records | 0.0 | passing |
| TC-RPT-07-U04 | Excused counting with status "Excused" and "excused" | Only "Excused" counted for students; only "excused" for staff | passing |
| TC-RPT-07-U05 | `date_range` for min 2026-09-01 and max 2026-09-30 | "2026-09-01 to 2026-09-30" | passing |
| TC-RPT-07-U06 | `month=9` without `year` | No month predicate added | passing |
| TC-RPT-07-U07 | `sl_no` for page 2, page_size 25 | Starts at 26 | passing |
| TC-RPT-07-U08 | Mobile student screen rate for 5 present of 8 | "62.5%"; with 0 records a dash | blocked: mobile rate calculation is inline in the mobile student attendance report screen; needs the helper exported |
| TC-RPT-07-A01 | Admin `GET /reports/attendance/students` for the fixture | `total_count=12`; rows ordered by date descending; `marked_at` null | passing |
| TC-RPT-07-A02 | `?attendance_status=absent`; `?date_from=2026-09-10&date_to=2026-09-10`; `?student_id=<s>`; `?class_id=<c>` | Each narrows rows | passing |
| TC-RPT-07-A03 | `?month=9&year=2026`; `?month=13` | Rows for September 2026; 422 | passing |
| TC-RPT-07-A04 | `?page=2&page_size=5`; `?page=0`; `?page_size=1001`; `?sort_order=x` | Second page of 5 with `sl_no` 6 to 10; 422 for the invalid ones | passing |
| TC-RPT-07-A05 | Student with two admissions | Rows duplicated per admission (documents the gap) | skipped: admission API cannot produce two admissions for one student |
| TC-RPT-07-A06 | `GET /reports/attendance/students/stats` for the fixture | `total_students` as distinct students, `present_count=8`, `half_day_count=2`, `absent_count=1`, `late_count=1`, `attendance_percentage=75.0` | passing |
| TC-RPT-07-A07 | Stats with `?attendance_status=absent&month=9&year=2026` | Same totals as without those parameters (ignored) | passing |
| TC-RPT-07-A08 | `GET /reports/attendance/staff` with 3 staff records | Documented fields; `clock_in`, `clock_out`, `total_hours`, `marked_at` null; `staff_id` is a UUID | passing |
| TC-RPT-07-A09 | Staff filters `?department=Admin&designation_id=<d>&staff_id=<s>&attendance_status=present` | Each narrows the rows | passing |
| TC-RPT-07-A10 | `GET /reports/attendance/staff/stats` | `total_staff`, status counts and percentage per the formula | passing |
| TC-RPT-07-A11 | `POST /reports/attendance/export` student_attendance csv, xlsx, pdf; staff_attendance csv | 200 with the right content types; all rows regardless of `page_size` | passing |
| TC-RPT-07-A12 | Export `report_type:"fees"` | 400 "Unsupported attendance report type" | passing |
| TC-RPT-07-A13 | Role matrix on list and stats | Admin, Staff, Teacher 200; Student, Parent 403 | passing |
| TC-RPT-07-A14 | Role matrix on export | Admin, Staff, Teacher 200; Student, Parent 403 | passing |
| TC-RPT-07-A15 | Tenant isolation | Tenant B reports and stats exclude tenant A's attendance | passing |

API tests implemented in: backend/tests/api/reports/test_attendance_reports.py
| TC-RPT-07-E01 | Mobile Admin: Student Reports with "Last 7D" | Tiles Present, Absent, Late, Present Rate and a records list | planned |
| TC-RPT-07-E02 | Mobile: Student Reports with no records | "No records for this period" and a dash for the rate | planned |
| TC-RPT-07-E03 | Mobile: Export on Student Reports | A CSV named `student_attendance_report.csv` is shared | planned |
| TC-RPT-07-E04 | Mobile Admin: Staff Reports, chip "Last 30D" | Present, Absent, Rate tiles from the stats endpoint; list "RECORDS" | planned |
| TC-RPT-07-E05 | Mobile Student opens Staff Reports | Blocked by the screen gate | planned |
| TC-RPT-07-E06 | Web: look for an attendance report page | None exists (documents the gap) | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_lists.py.

---

## F08 Financial reports (expenditure, ledger, summary)

**Purpose**: See expenses by transaction, a combined income and expense ledger, and a period summary of fee income versus spend.

**Roles and permissions**: `financial_reports:read` (all three GET endpoints; skipped for superadmin tokens), `financial_reports:export` (export of expenditure and ledger). Admin only in the default catalog.

**Preconditions**: Expense transactions (EXP) and fee transactions (FEE).

**Steps, web and mobile**: No screen on either client for financial reports (API only).

**Expected results**: JSON envelopes (F12) and files.

**API endpoints**
- `GET /reports/financial/expenditure?date_from=&date_to=&category_id=&type_id=&amount_min=&amount_max=&department=&month=&year=&page=&page_size=&sort_by=&sort_order=asc`; row fields `sl_no`, `transaction_id`, `date`, `category_name`, `type_name`, `description`, `amount`, `department` (name, else the raw department id), `approved_by`, `approved_at`, `receipt_number` (the reference number), `vendor_name`, `created_at`.
- `GET /reports/financial/ledger?date_from=&date_to=&account_type=&transaction_type=&reference_type=&amount_min=&amount_max=&month=&year=&page=&page_size=&sort_by=&sort_order=` row fields `sl_no`, `transaction_id`, `date`, `account_type`, `transaction_type`, `reference_type`, `reference_id`, `amount`, `balance`, `description`, `created_at`.
- `GET /reports/financial/summary?date_from=&date_to=&period_type=monthly|quarterly|yearly&include_fees=true&include_expenses=true&month=&year=` returns `{summary_data: {period, total_income, total_expenses, net_balance, fee_collections, fee_pending, expense_by_category, expense_by_type, monthly_trends}, income_breakdown: [], expense_breakdown: [], budget_comparison: [], cash_flow_trends: []}`.
- `POST /reports/financial/export` body `{report_type: "expenditure"|"ledger", filters, format, filename}`. There is no summary export.

**Rules and validations**
- Expenditure lists every expense including rejected and cancelled ones; the `department` filter must be a UUID string (an invalid string is silently ignored); `amount_min` and `amount_max` of 0 are ignored; `month` and `year` apply only together.
- Ledger = expenses (account type "Expense", transaction type "Debit", reference type "Expense Payment") whose status is not `rejected`, `cancelled` or `deleted`, plus fee transactions with status `completed` (account type "Income", "Credit", "Fee Payment", description "Fee payment for <first> <last>"). The fee timestamp is cast to a date. Default order: date descending then created_at descending. `reference_type` is accepted and ignored. `balance` is a running total that starts at 0.00 on every page and adds credits and subtracts debits in the displayed order.
- Summary: range = both `date_from` and `date_to`, else `month` plus `year`, else the current month (a lone `date_from` is ignored). `total_income` = completed fee transactions in range (by date); `total_expenses` = expenses not rejected, cancelled or deleted in range (pending and approved count); `net_balance = income - expenses`; `fee_pending` is always 0; `period` is "<from> to <to>"; `period_type` and the four breakdown lists are unused.
- `include_fees=false` or `include_expenses=false` zeroes that side.

**Error and edge cases**: Empty ranges return zeros and empty maps; permission failures re-raise 403; unsupported export type 400 "Unsupported financial report type".

**Unit-testable logic**: Summary date-range resolution; the excluded-status set; running balance; amount filter zero handling; department filter parsing.

**Test cases**

Fixture for 2026-09: completed fee transactions 6000.00 (2026-09-05) and 4000.00 (2026-09-20); a pending fee transaction 999.00; expenses: pending 1000.00 (Utilities/Electricity, 2026-09-10), approved 500.00 (Utilities/Water, 2026-09-12), rejected 700.00 (2026-09-14), cancelled 50.00 (2026-09-15).

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-08-U01 | Summary for the fixture with `month=9&year=2026` | `period="2026-09-01 to 2026-09-30"`, `fee_collections=10000.00`, `total_income=10000.00`, `total_expenses=1500.00`, `net_balance=8500.00` | passing |
| TC-RPT-08-U02 | Summary `include_fees=false` | `total_income=0.00`, `total_expenses=1500.00`, `net_balance=-1500.00` | passing |
| TC-RPT-08-U03 | Summary `include_expenses=false` | `total_expenses=0.00`, `expense_by_category={}`, `net_balance=10000.00` | passing |
| TC-RPT-08-U04 | Range resolution: only `date_from` given | Falls back to the current month (2026-10-01 to 2026-10-31) | passing |
| TC-RPT-08-U05 | Range resolution: `month=2&year=2028` | 2028-02-01 to 2028-02-29 | passing |
| TC-RPT-08-U06 | Ledger running balance for credit 6000, debit 1000 in that page order | Balances 6000.0 then 5000.0 | passing |
| TC-RPT-08-U07 | Ledger running balance on the next page | The first row of page 2 starts from 0, not from the page 1 total | passing |
| TC-RPT-08-U08 | Excluded expense status set | Exactly rejected, cancelled, deleted | passing |
| TC-RPT-08-U09 | `department` filter "not-a-uuid" | Predicate skipped | passing |
| TC-RPT-08-A01 | Admin `GET /reports/financial/summary?month=9&year=2026` | Matches U01; `expense_by_category={"Utilities":1500.0}`, `expense_by_type={"Electricity":1000.0,"Water":500.0}`; `fee_pending=0` | passing |
| TC-RPT-08-A02 | `?date_from=2026-09-01&date_to=2026-09-10` | Fee income 6000.00 (09-05) and expenses 1000.00 (09-10) | passing |
| TC-RPT-08-A03 | `?period_type=weekly`; `?month=13` | 422 | passing |
| TC-RPT-08-A04 | `GET /reports/financial/expenditure` for the fixture | All four expenses (including rejected and cancelled), newest `transaction_date` first, documented fields | passing |
| TC-RPT-08-A05 | Expenditure `?category_id=<c>&type_id=<t>`; `?amount_min=600&amount_max=1000`; `?department=<uuid>`; `?month=9&year=2026` | Each narrows rows; the amount range returns 700.00 and 1000.00 | passing |
| TC-RPT-08-A06 | Expenditure row whose department row is missing | `department` shows the raw id | skipped: a department row cannot be removed |
| TC-RPT-08-A07 | Expenditure `?page=2&page_size=2` | `sl_no` 3 and 4 | passing |
| TC-RPT-08-A08 | `GET /reports/financial/ledger` for the fixture | 4 rows: fee credits 6000.00 and 4000.00, expense debits 1000.00 and 500.00 (rejected, cancelled and the pending fee row absent) | passing |
| TC-RPT-08-A09 | Ledger `?account_type=Income`; `?transaction_type=Debit`; `?reference_type=Fee Payment` | Income only; debit only; `reference_type` ignored (all four rows) | passing |
| TC-RPT-08-A10 | Ledger `?page_size=2&page=2` | `balance` of the first row on page 2 reflects only that page | passing |
| TC-RPT-08-A11 | `POST /reports/financial/export` expenditure and ledger in csv, xlsx, pdf | 200 with the content type and all rows | passing |
| TC-RPT-08-A12 | Export `report_type:"summary"` | 400 "Unsupported financial report type" | passing |
| TC-RPT-08-A13 | Role matrix on GET endpoints | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-RPT-08-A14 | Role matrix on export | Admin 200; others 403 | passing |
| TC-RPT-08-A15 | Tenant isolation | Tenant B summary, ledger and expenditure exclude tenant A data | passing |

API tests implemented in: backend/tests/api/reports/test_financial_reports.py
| TC-RPT-08-E01 | Web and mobile: look for a financial report screen | None exists on either client (documents the gap) | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_lists.py.

---

## F09 Expense reports (entry points and cross-checks)

**Purpose**: Reach the expense reports from the Reports area and confirm they agree with the financial reports. The report endpoints, filters, arithmetic and exports are specified in EXP F14; this section only covers entry points and cross-module consistency.

**Roles and permissions**: As EXP F14 (`expense_reports:read`, `:export`); the Reports hub fallback card requires `expense_reports:read`.

**Preconditions**: Expense transactions exist.

**Steps, web**
1. Open Reports (`/reports`). When the Reports node has no children, an "Expense Reports" card (from the `expense_reports:read` fallback) opens `/expense/reports`; when the menu has an "Expense Reports" child, that card is used.
2. Use the page as described in EXP F14.

**Steps, mobile**
1. The Reports tab has no Expense Reports card; open "Expense Reports" from the Expense navigation (drawer menu mapping `/expense/reports`).

**Expected results**: Expense report totals count every status; the financial summary counts everything except rejected, cancelled and deleted, so the two differ by exactly the rejected, cancelled and deleted amounts.

**API endpoints**: `GET /expense/reports/by-category`, `/by-type`, `/trend`, `/summary`, `POST /expense/reports/export`, `GET /expense/reports/export/{id}/status` (specified in EXP F14) and `GET /reports/financial/summary` (F08) for the cross-check.

**Rules and validations**: See EXP F14 and F08. The web page guard is `expense_reports:list`; the endpoints check `read`.

**Error and edge cases**: A user with `expense_reports:list` only sees the page but every call returns 403.

**Unit-testable logic**: Difference calculation between the two reports for a given status mix.

**Test cases**

Uses the F08 fixture expenses (pending 1000.00, approved 500.00, rejected 700.00, cancelled 50.00 in 2026-09).

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-09-U01 | Difference between the expense report total and the financial summary expenses | 750.00 (rejected 700.00 plus cancelled 50.00) | passing |
| TC-RPT-09-A01 | `GET /expense/reports/by-category?start_date=2026-09-01&end_date=2026-09-30` | Total 2250.00 over 4 transactions | passing |
| TC-RPT-09-A02 | `GET /reports/financial/summary?month=9&year=2026` | `total_expenses=1500.00` | passing |
| TC-RPT-09-A03 | `GET /reports/financial/expenditure?month=9&year=2026` | Total of the listed amounts 2250.00 (expenditure lists every status) | passing |
| TC-RPT-09-A04 | Admin with `expense_reports:read` and Staff without it call `/expense/reports/by-category` | 200; 403 | passing |

API tests implemented in: backend/tests/api/reports/test_financial_reports.py
| TC-RPT-09-E01 | Web Admin on `/reports` (childless Reports node) | "Expense Reports" fallback card opens `/expense/reports` | planned |
| TC-RPT-09-E02 | Web: generate the by-category report for 2026-09 | Total Amount 2250.00 in the summary card | planned |
| TC-RPT-09-E03 | Mobile Admin: Expense Reports from the drawer | Screen "Expense Reports" with tabs By Category, By Type, Trend | planned |
| TC-RPT-09-E04 | Mobile: Reports tab | No Expense Reports card (documents the entry-point difference) | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_lists.py.

---

## F10 Academic report (mobile, client-side)

**Purpose**: See how many exams are published, active and in draft and list them. There is no backend academic report endpoint.

**Roles and permissions**: Screen gate `exams` or `exam_results` (read or list) and role `student` blocked. The data call is the exam list (`exams:read` or `list`).

**Preconditions**: Exams exist (EXM module).

**Steps, web**: No page.

**Steps, mobile**
1. Reports tab, "Academic Reports" (screen "Academic Reports", banner "Academic / Exam Overview"). Tiles "Published" (status published or finalized), "Active" and "Draft"; section "ALL EXAMS" lists each exam (type with underscores replaced, board, academic year title). "Export" shares a CSV of the exams. Empty: "No exams found".

**Expected results**: Counts are computed on the device from the exam list.

**API endpoints**: The exam list through `examsApi.list()` (see EXM); no `/reports/academic`.

**Rules and validations**: Published = status `published` or `finalized`; Active = `active`; Draft = `draft`; other statuses appear in the list but in no tile.

**Error and edge cases**: Student role blocked; no exams shows the empty text.

**Unit-testable logic**: Status counters.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-10-U01 | Counters for statuses [published, finalized, active, draft, draft, cancelled] | Published 2, Active 1, Draft 2 | blocked: status counters are inline in the mobile academic reports screen; needs the helper exported |
| TC-RPT-10-A01 | `GET /reports/academic` | 404 (no such endpoint) | passing |
| TC-RPT-10-A02 | Teacher and Admin call the exam list | 200 (grants `exams:read` or `list`) | passing |

API tests implemented in: backend/tests/api/reports/test_conventions_audit.py
| TC-RPT-10-E01 | Mobile Admin: Academic Reports | Three tiles and the "ALL EXAMS" list | planned |
| TC-RPT-10-E02 | Mobile: Export | A CSV of exams is shared | planned |
| TC-RPT-10-E03 | Mobile Student | Blocked by the gate | planned |
| TC-RPT-10-E04 | Mobile with no exams | "No exams found" | planned |

---

## F11 Transport report (mobile, client-side)

**Purpose**: See counts and lists of routes, vehicles and trips. There is no backend transport report endpoint.

**Roles and permissions**: Screen gate `routes`, `vehicles` or `transport_trips` (read or list) and role `student` blocked; data calls need `routes:list`, `vehicles:list`, `transport_trips:list`.

**Preconditions**: Transport data (TRN).

**Steps, web**: No page.

**Steps, mobile**
1. Reports tab, "Transport Reports" (banner "Transport Overview"). Tiles "Routes", "Vehicles", "Trips"; sections "ROUTES" and "VEHICLES" (empty texts "No routes configured", "No vehicles configured"); "Export" shares `transport_report.csv` with rows typed Route, Vehicle, Trip (columns Type, Name, Details, Status).

**Expected results**: Counts come from `GET /masters/routes/all_routes`, `GET /masters/vehicles/` and `GET /masters/trips/`; active counts use `is_active`.

**API endpoints**: Those three list endpoints (TRN F04, F06, F07); no `/reports/transport`.

**Rules and validations**: Trips have no `is_active`; the trips tile counts all trips.

**Error and edge cases**: A role without one of the list grants gets 403 on that call and the screen shows an error or zero.

**Unit-testable logic**: CSV row builder; active counters.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-11-U01 | Export rows for 1 route, 1 vehicle, 1 trip | Header Type, Name, Details, Status; rows Route (name, "A to B", Active), Vehicle (name, registration, Active), Trip ("Trip #1", id, empty) | blocked: CSV row builder is inline in the mobile transport report screen; needs the helper exported |
| TC-RPT-11-U02 | Active counters for routes [active, inactive] | 1 | blocked: active counters are inline in the mobile transport report screen; needs the helper exported |
| TC-RPT-11-A01 | `GET /reports/transport` | 404 | passing |
| TC-RPT-11-A02 | Teacher calls the three list endpoints | All 200 (read and list grants) | passing |

API tests implemented in: backend/tests/api/reports/test_conventions_audit.py
| TC-RPT-11-E01 | Mobile Admin: Transport Reports | Tiles with counts; ROUTES and VEHICLES lists | planned |
| TC-RPT-11-E02 | Mobile: Export | CSV `transport_report.csv` shared | planned |
| TC-RPT-11-E03 | Mobile Student | Blocked by the gate | planned |
| TC-RPT-11-E04 | Mobile in an empty tenant | "No routes configured" and "No vehicles configured" | planned |

---

## F12 Report conventions and exports

**Purpose**: One set of rules shared by every `/reports/*` endpoint: the response envelope, pagination, filtering and export formats.

**Roles and permissions**: Per report group (F04 to F08).

**Preconditions**: A report with data.

**Steps, web**: Fee Reports page only: format selector (CSV, Excel, PDF) and "Export". The download is a blob.

**Steps, mobile**: CSV exports are built from on-screen data with the share sheet (`exportToCsv`); the server export endpoints are not called by any mobile screen.

**Expected results**: Reports return `{data, total_count, page, page_size, total_pages}`; exports return a file with `Content-Disposition: attachment; filename=<name>.<ext>` and `Content-Length`.

**API endpoints**: All `GET` report endpoints and `POST .../export` of F04 to F08.

**Rules and validations**
- Envelope: `total_pages = ceil(total_count / page_size)`; `sl_no` continues across pages. List parameters `page >= 1`, `page_size` 1-1000 (default 100), `sort_order` asc or desc, except the fee routes which do not validate them (F06).
- Export request body: `report_type`, `filters` (object, parsed into the same filter model as the list), `format` in csv, xlsx, pdf (else 422 from the schema), optional `filename`. Default filename `<group>_<report_type>_<tenant id>`. The filename is used verbatim in the header (not sanitised).
- Every export fetches all rows (page and page_size in `filters` are ignored) and streams the file synchronously. The background export path (`should_use_background_job`, `create_background_export_job`) is not called by any endpoint.
- CSV: UTF-8, header from the first row's keys. Excel: sheet named per report, bold white header on a blue fill, column width capped at 50, datetimes as `YYYY-MM-DD HH:MM:SS`. PDF: A4, title, optional subtitle "Report Type: <Title Case>", a "Generated on" line, the table and "Total Records: <n>".
- Empty data: the generators return an empty body and the filename without an extension.
- `validate_export_limits` (5000 rows) exists but is not called.

**Error and edge cases**: Unsupported report type 400; invalid format 422; unauthenticated 401; permission denied 403 (500 on the student and staff summary endpoints).

**Unit-testable logic**: `generate_csv_export`, `generate_excel_export`, `generate_pdf_export`, `fetch_all_rows`, `apply_pagination`, `should_use_background_job`, `validate_export_limits`, the `total_pages` ceiling.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-12-U01 | `generate_csv_export([{"a":1,"b":"x"},{"a":2,"b":"y"}], "f")` | Bytes with header `a,b`, rows `1,x` and `2,y`; filename `f.csv` | passing |
| TC-RPT-12-U02 | `generate_csv_export([], "f")` | `(b"", "f")` (no extension) | passing |
| TC-RPT-12-U03 | `generate_excel_export` with a datetime value and a None | Datetime formatted `YYYY-MM-DD HH:MM:SS`; None written as empty; header cell bold | passing |
| TC-RPT-12-U04 | `generate_excel_export` column width for a 100-character value | Width capped at 50 | passing |
| TC-RPT-12-U05 | `generate_pdf_export` with 3 rows | Valid PDF bytes (start with `%PDF`); filename `.pdf`; the document contains "Total Records: 3" | passing |
| TC-RPT-12-U06 | `fetch_all_rows` when the first page returns 100 of total 250 | Re-fetches with page_size 250 and returns 250 rows | passing |
| TC-RPT-12-U07 | `fetch_all_rows` when the first call returns all rows | Single fetch | passing |
| TC-RPT-12-U08 | `apply_pagination(page=3, page_size=50)` | offset 100, limit 50 | passing |
| TC-RPT-12-U09 | `should_use_background_job` for (1001, csv), (501, xlsx), (500, xlsx), (301, pdf), (300, pdf) | True, True, False, True, False | passing |
| TC-RPT-12-U10 | `validate_export_limits(5000)` and `(5001)` | Valid; invalid with the row-limit message | passing |
| TC-RPT-12-U11 | `total_pages` for (250, 100), (0, 100), (100, 100) | 3, 0, 1 | passing |
| TC-RPT-12-A01 | Any list endpoint response shape | Keys `data`, `total_count`, `page`, `page_size`, `total_pages` with integer types | passing |
| TC-RPT-12-A02 | `POST` export with `format:"csv"` for every report group | `Content-Type: text/csv`, attachment header, `Content-Length` equals the body length | passing |
| TC-RPT-12-A03 | `POST` export with `format:"xlsx"`; open the body as a workbook | Valid workbook with a worksheet; the first row equals the data keys | passing |
| TC-RPT-12-A04 | `POST` export with `format:"pdf"` | Body starts with `%PDF` | passing |
| TC-RPT-12-A05 | `POST` export with `format:"xls"` | 422 | passing |
| TC-RPT-12-A06 | `POST` export with a `filename` containing a space and a dot | Header filename equals the supplied text plus the extension (unsanitised); record for hardening | passing |
| TC-RPT-12-A07 | Export of 1500 rows | 200 synchronous file with all 1500 rows (no background job, no 5000-row limit) | skipped: 1500 rows cannot be created and cleaned up |
| TC-RPT-12-A08 | Export request without `filters` or without `report_type` | 422 | passing |
| TC-RPT-12-A09 | Calls without a token on a GET and a POST | 401 | passing |
| TC-RPT-12-E01 | Web fee reports: export with each of CSV, Excel, PDF | Three downloads with the matching extension | planned |
| TC-RPT-12-E02 | Mobile: Export on any report screen | A CSV is produced and the share sheet opens | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_export.py (U11 in test_phase1_reports_lists.py).

---

## F13 Export history and download

**Purpose**: List a user's recorded exports and download a finished one. In the current code nothing writes the audit table, so these endpoints have no data to return.

**Roles and permissions**: `reports:read` for all three endpoints (Admin, Staff, Teacher in the default catalog). Records are filtered to the caller's user id and tenant id.

**Preconditions**: A `report_audit` record, which only the unused background export path creates.

**Steps, web and mobile**: No screen.

**Expected results**: The history list is empty; any id returns 404.

**API endpoints**
- `GET /reports/audit?page=1&page_size=50&status=&report_type=` (`page_size` 1-100) returns a list of `{id, user_id, tenant_id, report_type, filters_applied, export_format, file_path, file_size, status, error_message, created_at, updated_at, completed_at, is_background_job}`, newest first.
- `GET /reports/audit/{audit_id}` returns one record or 404 "Export record not found".
- `GET /reports/download/{audit_id}` returns the file when the status is `completed`.

**Rules and validations**
- Download: 404 "Export record not found"; 400 "Export is not completed. Current status: <status>" when not completed; 404 "Export file not found" without a path; 404 "Export file not found on disk" when the file is missing.
- A permission failure on `GET /reports/audit` returns 500 "Internal server error" (bare `except`); the other two re-raise 403.
- Exports made through the synchronous endpoints are not audited.
- The background job path is broken (see Known gaps) and the advertised `/reports/export-status/{id}` route does not exist.

**Error and edge cases**: A record belonging to another user or tenant returns 404.

**Unit-testable logic**: Filter composition (user, tenant, status, report type); download guards; content-type map (csv, xlsx, pdf, default octet-stream).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-RPT-13-U01 | Content-type map for csv, xlsx, pdf, "zip" | text/csv, the spreadsheet type, application/pdf, application/octet-stream | passing |
| TC-RPT-13-U02 | Download guard order for status "pending" | 400 "Export is not completed. Current status: pending" | passing |
| TC-RPT-13-U03 | Download guard for a completed record without `file_path` | 404 "Export file not found" | passing |
| TC-RPT-13-A01 | After exporting a report synchronously, `GET /reports/audit` | `[]` (exports are not audited); record any 500 caused by the user id type | passing |
| TC-RPT-13-A02 | `GET /reports/audit?page_size=101`; `?page=0` | 422 | passing |
| TC-RPT-13-A03 | `GET /reports/audit/{random uuid}`; malformed id | 404 "Export record not found"; 422 | passing |
| TC-RPT-13-A04 | `GET /reports/download/{random uuid}` | 404 "Export record not found" | passing |
| TC-RPT-13-A05 | Insert a `completed` audit row with a real file for the user and download it | 200 with the file bytes and `Content-Disposition` | skipped: needs a report_audit row; tests may not write the database |
| TC-RPT-13-A06 | Insert a `pending` row and download | 400 with the status in the message | skipped: needs a report_audit row; tests may not write the database |
| TC-RPT-13-A07 | Another user's or another tenant's record id | 404 | passing |
| TC-RPT-13-A08 | Role matrix on the three endpoints | Admin, Staff, Teacher pass the check; Student, Parent denied (list returns 500, the others 403) | passing; xfail: RPT-BUG-AUDIT-500 (list denial is 500, target 403) |
| TC-RPT-13-A09 | No token | 401 | passing |

API tests implemented in: backend/tests/api/reports/test_conventions_audit.py

Implemented in (phase 1 unit tests): backend/tests/unit/reports/test_phase1_reports_export.py.

---

## Known gaps

Differences between `docs/modules/reports-dashboards.md` (or the UI) and the code, plus defects found while reading it. Record test outcomes against these in the Status column.

1. The web home dashboard is no longer empty: it renders module cards from the processed menu. The module doc ("just a page header") and its Known gaps line "The web home dashboard has no content" are out of date.
2. The module doc says each web hub shows a "Coming Soon" banner; no such banner exists in the web hub code (admin, masters, students, transport, reports).
3. The module doc says student and staff report endpoints return 500 for permission failures. Only the summary endpoints (and `GET /reports/audit`) do; student and staff details and exports re-raise the 403, and the fee, attendance and financial endpoints re-raise too.
4. Student summary: `gender`, `caste`, `religion` and `student_type` filters are ignored; rows carry no student name, father name or contact (the `StudentSummaryData` schema is unused); admissions without a section are dropped by inner joins.
5. Staff summary: only `gender` filters; `department_id`, `employment_type`, `caste`, `address_city`, `subject_id` and `academic_year_id` are ignored; staff without a designation are excluded; `academic_year` is always "N/A".
6. Attendance: stats endpoints ignore `attendance_status`, `month`, `year` and (students) `student_id`; the student excused status is counted as "Excused" and the staff one as "excused"; `marked_at`, `clock_in`, `clock_out` and `total_hours` are always null; the student list can repeat a student with several admissions; the staff row `staff_id` is the UUID (no employee code).
7. Fee reports: routes use bare parameter defaults, so out-of-range paging or malformed dates return 500, and the collection summary error includes the exception text; the web page needs at least one filter before it shows data and exports; the web export filters for pending and structure include keys those filter models ignore.
8. Financial: the ledger running balance restarts on every page; `reference_type` is ignored; a lone `date_from` on the summary is ignored (falls back to the current month); pending expenses count as spend; `fee_pending`, the four breakdown lists and `monthly_trends` are empty or zero; there is no summary export; no web or mobile screen consumes these endpoints.
9. Exports: empty data returns a 200 with an empty body and a filename without extension; `filename` is placed in the header unsanitised; `validate_export_limits` and the background path are not used; large exports are synchronous.
10. Export history: `GET /reports/audit` and `/download/{id}` have nothing to return because exports are not audited; the background export path is broken and unused (see the module doc).
11. Web has no pages for student, staff, attendance or financial reports (the staff attendance report hooks exist but no component uses them). The web Reports hub depends on seeded menu children; the demo catalog seeds none, so only the fee and expense fallback cards appear.
12. Mobile "Student Reports" does not call the student report endpoints; it counts `GET /student/attendance/search` rows on the device, and its rate ignores half-day and leave. Mobile "Staff Reports" shows only the first 100 records. Academic and Transport reports are client-side aggregations with no backend.
13. Mobile Reports has two hubs: the tab merges permissions with the menu, the stack screen `/reports` is permission-only. The mobile Reports tab has no Expense Reports card.
14. The web `/transport` and `/students` hubs and the sidebar hide "Student Transport", "Route Stops" and "Transport Trips"; hubs read the raw menu while the sidebar reads the processed one, so their lists can differ.
15. Mobile Fee Reports is blocked for the teacher role while the teacher has no fee report grants anyway; the Student Reports screen has no role block.
16. The web `ExpenseReports` page guard (`expense_reports:list`) and the endpoint checks (`read`) disagree (see EXP).
