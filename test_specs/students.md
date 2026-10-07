# Students (STU)

Feature documentation and test specification for the Students module: admission (student plus parent/guardian accounts), student list and details, editing, activation, bulk upload, student attendance, student documents, the student and parent self-service views, student profile, parent-child selection, student-parent links and student transport assignment. Test case IDs use the scheme `TC-STU-<FF>-<P><NN>` from `docs/testing/strategy.md`. Facts were read from the code on 2026-10-02 and the walkthroughs were re-checked against the running web and mobile apps on 2026-10-07; where `docs/modules/students.md` disagrees with the code, this page documents the code and lists the difference under "Known gaps".

_Last verified against code: 2026-10-07_

Related: `docs/modules/students.md` (rules and gotchas), `docs/permissions.md`, `docs/architecture.md`, `docs/features/certificates.md` (certificates; the merged documents list here reads `student_certificates`).

## Roles

| Role | What it can do in this module (default catalog, `backend/app/service/tenant/permission_catalog.py`) |
|---|---|
| Admin | Everything: `student_admissions:create/read/update/delete/list`, `student_attendance:*`, `student_documents:*`, `student_transport:*`, `parent_management:*`, `students:list` |
| Staff | Admissions create/read/update/list (no delete), attendance create/read/update/list (no delete), documents create/read/update/list (no delete), transport create/read/update/list, `parent_management` create/read/update/list, `students:list` |
| Teacher | `student_admissions:read/list`, `student_attendance:create/read/update/list`, `student_documents:read/list`, `students:list`. No admission create/update, no transport, no parent links. Not limited to own classes (no teacher-class table) |
| Student | Own scope only: `student_admissions:read_own/list_own`, `student_attendance:read_own/list_own`, `student_documents:read_own/list_own`, `student_transport:read_own`, `profile:read_own/update_own` |
| Parent | Related scope (linked children) only: `student_admissions:read_related/list_related`, `student_attendance:read_related/list_related`, `student_documents:read_related/list_related`, `student_transport:read_related` |

Important about the default catalog: several endpoints call `check_role_plan_permission_with_error`, which needs the exact action (`list`, `read`) and ignores `_own`/`_related`. Student and Parent therefore get 403 on those endpoints under the default catalog (documents list, attendance list and by-id, admission by-admission, dropdowns). Endpoints that call `check_user_resource_access` honour `_own`/`_related` and return scoped data. Each feature below states which kind its endpoints are. The test cases assert the default catalog; if the QA tenant grants more, parametrise the expectation.

## Feature index

| ID | Title |
|---|---|
| F01 | Students menu, dashboard and role views |
| F02 | Admission number preview and generation |
| F03 | New admission (web wizard, mobile form, API) |
| F04 | Parent and guardian accounts created or reused at admission |
| F05 | Student photo upload and removal |
| F06 | Admission list, search and student dropdowns |
| F07 | Admission details view |
| F08 | Edit admission |
| F09 | Activate, deactivate and delete a student |
| F10 | Bulk admission upload (Excel) |
| F11 | Mark student attendance |
| F12 | Correct or delete attendance |
| F13 | Attendance history and percentage |
| F14 | Upload and replace a student document |
| F15 | List student documents and the merged documents view |
| F16 | Delete and download a student document |
| F17 | Student own admission view and parent child admission view |
| F18 | Student profile |
| F19 | Parent child selection |
| F20 | Student-parent links (admin API) |
| F21 | Student transport assignment |
| F22 | Manual SMS triggers (admission confirmation, absence alerts, homework reminders) |

## Conventions for the test tables

- "Default catalog" means the role grants in `permission_catalog.py`. "403" is the permission failure. For `check_user_resource_access` endpoints a targeted id outside the caller's own/related scope returns 404, not 403.
- QA data assumed: tenants `qa_school` (tenant A) and a second tenant B; one active academic year; classes "Class 1" and "Class 2" each with sections "A" and "B"; at least 12 admitted students in Class 1 / A; two parents each linked to different children; one parent linked to two children (siblings).
- "Tenant isolation" cases: data created in tenant A is invisible in tenant B, and a token for tenant A sent with a `cschema` header for tenant B gets 403.
- "Unauthenticated" means no `Authorization` header: 401.
- Errors raised through `create_validation_error` return **400**, `create_business_rule_error` returns **422**, `create_not_found_error` returns 404, `create_database_error` returns 500 (body `detail` is an object with `error_code`, `message`, `details`, `request_id`).
- Web screens are in `web/src`, mobile screens in `mobile/app`. Menu labels come from the tenant `menus` table; the demo seed (`backend/scripts/seed_demo_catalog.py`) uses Students > Admission, Attendance, Student Documents, Student Certificates, Certificate Types, Certificate Templates, Student Transport. The web hides "Student Transport" from the sidebar and the dashboard (`web/src/lib/menuUtils.ts`), so it is opened by URL.

### Manual UI test data

UI cases (IDs ending `-E`) use an 8-column layout: ID, Priority (`P1` smoke, `P2` regression, `P3` edge, negative or cosmetic), Platform, Role, Preconditions, Steps, Expected, Status. They run against the seeded manual-test tenant `qa_manual` (web http://localhost:5174 started with `VITE_DEFAULT_TENANT=qa_manual`; mobile Expo web http://localhost:8082, organisation "qa_manual"; setup and reset in `docs/testing/test-environment.md`). Rebuild it with `setup_manual_tenant.py --reset` before a test cycle so every tester starts from the same data.

- Staff logins: the QA Admin, QA Staff and QA Teacher logins (QA `.env`).
- Unlinked logins: the QA Student and QA Parent logins also exist in `qa_manual` but are not linked to any student. Cases call them "QA Student login (unlinked)" and "QA Parent login (unlinked)" and use them only for empty states.
- Seeded logins: a seeded student signs in with the admission number ("Seeded student login 004"), a seeded parent with the email ("Seeded parent login venkat.raju@example.com"); both start with the temporary password and must change it at the first sign-in.
- Seeded classes: Nursery, LKG, UKG and Class 1 to Class 5, each with two sections (NUR-A/B, LKG-A/B, UKG-A/B, 1-A/1-B ... 5-A/5-B). The active academic year is shown in the header.
- Seeded students used by the cases (all admitted 2026-06-10; attendance seeded on 2026-09-25, 2026-09-28, 2026-09-29, 2026-09-30 and 2026-10-01):
  - Harsha Raju (004, Class 1 / 1-B) and his sister Tanvi Raju (005, Class 4 / 4-B); parent login venkat.raju@example.com (father Venkat Raju). Harsha rides "Route 2 - Uppal", Tanvi "Route 1 - Kukatpally".
  - Advik Mehta (002, Class 1 / 1-B), only child of satish.mehta@example.com; Nikhil Krishnan (007) is the third student of 1-B.
  - Saanvi Iyer (003) and Kavya Verma (006) are the only students of Class 1 / 1-A.
  - Karthik Reddy (001, Class 3 / 3-B, uploaded document "Aadhaar Card") and his sister Ananya Reddy (Nursery, document "Birth Certificate"); parent login prakash.reddy@example.com.
  - Arjun Yadav and Rahul Menon (Class 2 / 2-A) have no transport assignment.
- Data the cases create (names start with "QA "): "QA Asha Rao" (TC-STU-03-E01, Class 2 / 2-A, no date of birth, father "QA Ramesh Rao", qa.father1@example.com, 9000000001), her sibling "QA Ravi Rao" (TC-STU-04-E01, same father email), "QA Mobile Kid" (TC-STU-03-E13). "QA Student login" is the admission number of QA Asha Rao; it is used only where a case changes the student's own data. "QA Parent login" is qa.father1@example.com after TC-STU-04-E01.
- Read seeded rows freely but do not edit, deactivate or delete them; cases that change data use the "QA " records. Delete or deactivate what you create when the run ends.

---

## F01 Students menu, dashboard and role views

**Purpose.** Reach every student screen from the sidebar or the Students dashboard and get the view that matches the role.

**Roles and permissions.** The sidebar tree comes from the login response (`menu`), filtered by `role_menu_permissions.can_view`. Admin, Staff and Teacher get every menu. Student and Parent get only the URL allowlist `STUDENT_PARENT_MENU_URLS`: `/dashboard`, `/students`, `/students/admission`, `/students/attendance`, `/students/studenttransport`, `/students/studentdocuments`, `/students/studentcertificates` (plus fee and exam entries). Menu visibility does not grant API access.

**Preconditions.** Tenant provisioned with the five default roles and the Students menu rows (demo seed or catalog import).

**Steps, web.**
1. Log in. Open the sidebar entry "Students" (route `/students`).
2. The page "Students Dashboard" (subtitle "Comprehensive management of student data, admissions, and records") shows a section "Students Sections" with one card per child menu item of "Students", each with a description line (for example "Manage student admissions and enrollment records"). "Student Transport" is hidden both on the dashboard and in the sidebar (`HIDDEN_MENU_ITEMS` in `web/src/lib/menuUtils.ts`); open it by URL.
3. Click a card or a sidebar child to open: Admission (`/students/admission`), Attendance (`/students/attendance`), Student Documents (`/students/studentdocuments`), Student Certificates (`/students/studentcertificates`), Certificate Types (`/students/certificatetypes`), Certificate Templates (`/students/certificatetemplates`). Student Transport is at `/students/studenttransport`.
4. Routes that exist but are not in the default menu (reachable by typing the URL): `/students/documentsupload` ("Document Upload"), `/students/mydocuments` ("My Documents"), `/students/mycertificates`, `/students/certificates`, `/students/certificatesupload`, `/students/profile` ("Student Profile"), `/students/admission/<admission id>` ("Admission Details").
5. Role views on the same route: `/students/admission` shows the admission table for every role except Parent, who gets "Admission - <child name> (#<number>)" for the selected child; `/students/attendance` shows "Student Attendance" (Admin, Staff, Teacher), "My Attendance" (Student) or "Children's Attendance" (Parent); `/students/studentdocuments` shows a student picker (staff), own list (Student) or selected child (Parent).

**Steps, mobile.** The Students hub and tabs are hard-coded and filtered by permission and the backend menu. `app/students/index.tsx` is the list screen titled "Students (<total>)" (guard: `ScreenAccessGate` on resources `students`, `student_admissions`): search box "Search by name or admission no...", cards with an initials avatar, the name and "<admission number> . <admitted class id>", 30 per page with a page pager. Admission screens: `admission.tsx` ("Student Admissions"), `myadmission.tsx`, `attendance.tsx` ("Attendance"), `documents.tsx` ("Documents"), `studentdocuments.tsx` ("Student Documents"), `mydocuments.tsx`, `profile.tsx`, `transport.tsx` ("Student Transport"), `[id].tsx` ("Student Details").

**Expected results.** Each role sees only the entries it is granted; the dashboard and the sidebar list exactly the child menu items minus "Student Transport"; pages never show another role's view. Admin, Staff and Teacher see six cards; Student and Parent see Admission, Attendance, Student Documents and Student Certificates.

**API endpoints.** None owned by this feature. The menu comes from `POST /auth/login` (see `docs/features/auth.md`).

**Rules and validations.**
- The web does not guard routes by permission; typing a URL opens the page and its API calls return 403 (`docs/permissions.md` section 6).
- Role detection on web lowercases the role name; on mobile the parent check also accepts `guardian`, `father`, `mother`.

**Error and edge cases.** A Student typing `/students/certificatetypes` sees the type list read-only (the Student role holds `certificate_types:list`). A Parent gets 403 from the list call; the page shows "No certificate types found." with a "Create First Certificate Type" button that is not permission-gated. A tenant with no "Students" menu shows an empty "Students Sections" area (the heading is hidden when there are no children).

**Unit-testable logic.** Web `lib/menuUtils.ts` role filtering; dashboard HIDDEN set filter (`student transport`). Mobile role-name parent detection.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-01-U01 | Dashboard section filter given menu children [Admission, Attendance, Student Transport] | Cards rendered for Admission and Attendance only; "Student Transport" excluded (case-insensitive match) | passing |
| TC-STU-01-U02 | Mobile parent detection for role names `Parent`, `guardian`, `Father`, `MOTHER`, `Student`, `Teacher` | true for the first four, false for Student and Teacher | passing |
| TC-STU-01-A01 | `POST /auth/login` as Student, Parent, Admin, Staff, Teacher; inspect `menu` | Student and Parent trees contain only the allowlisted Students children; Admin, Staff, Teacher contain all seven Students children | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-01-E01 | P1 | Web | Admin | QA Admin login | 1. Sign in as Admin.<br>2. Click "Students" in the sidebar.<br>3. Read the cards under "STUDENTS SECTIONS".<br>4. Expand "Students" in the sidebar.<br>5. Click the "Admission" card. | Page "Students Dashboard" with subtitle "Comprehensive management of student data, admissions, and records"; six cards Admission, Attendance, Student Documents, Student Certificates, Certificate Types, Certificate Templates, each with a description line; no Student Transport card and no Student Transport entry in the sidebar; step 5 opens /students/admission titled "Student Admissions" | passing |
| TC-STU-01-E02 | P2 | Web | Student | Seeded student login 004 (Harsha Raju) | 1. Sign in with the seeded student login 004.<br>2. Click "Students" in the sidebar.<br>3. Read the cards and the sidebar children of "Students". | Exactly four cards and sidebar children: Admission, Attendance, Student Documents, Student Certificates; no Certificate Types, Certificate Templates or Student Transport | planned |
| TC-STU-01-E03 | P2 | Web | Parent | Seeded parent login venkat.raju@example.com | 1. Sign in as venkat.raju@example.com.<br>2. Click "Students" in the sidebar.<br>3. Look at the page header. | Same four cards as TC-STU-01-E02; the header shows the child selector with the first child (Harsha Raju) selected | planned |
| TC-STU-01-E04 | P3 | Web | Student | Seeded student login 004; seeded certificate types | 1. Sign in with the seeded student login 004.<br>2. Type /students/certificatetypes in the address bar and press Enter. | "Certificate Types" page lists the types read-only: no "Add Certificate Type" button and no Edit or Delete icons; no crash | planned |
| TC-STU-01-E05 | P2 | Web | Admin | Admission id of seeded student Harsha Raju (004) known (from the API or the network tab) | 1. Sign in as Admin.<br>2. Type /students/admission/<admission id> in the address bar and press Enter.<br>3. Click "Back to List". | Page "Admission Details" with the full detail table of Harsha Raju; "Back to List" returns to "Student Admissions" | planned |
| TC-STU-01-E06 | P2 | Mobile | Admin | QA Admin login; 30 seeded admissions | 1. Sign in as Admin on mobile.<br>2. Open Students. | Header "Students (N)" with N equal to the total number of admissions (30 seeded plus any QA ones); search box "Search by name or admission no..."; cards with an initials avatar, the student name and the admission number; a page pager when N is above 30 | planned |
| TC-STU-01-E07 | P2 | Mobile | Teacher | QA Teacher login; seeded admissions | 1. Sign in as Teacher on mobile.<br>2. Open Students. | "Students (N)" list loads with cards (Teacher holds students:list and student_admissions:list); no Access Denied | planned |
| TC-STU-01-E08 | P3 | Web | Parent | QA Parent login (unlinked) | 1. Sign in with the QA Parent login (unlinked).<br>2. Type /students/certificatetypes in the address bar and press Enter. | An access or error message is shown and no create control is offered (the list call returns 403) | blocked: Known gap 23 (403 shown as "No certificate types found." with a "Create First Certificate Type" button) |
| TC-STU-01-E09 | P3 | Mobile | Admin | Seeded student Harsha Raju (004, Class 1 / 1-B) | 1. Sign in as Admin on mobile.<br>2. Open Students.<br>3. Type "Harsha" in "Search by name or admission no...".<br>4. Read the second line of the card. | The card shows the admission number and the class name "Class 1" | blocked: Known gap 12 (card prints the admitted class id, a UUID) |

API tests implemented in: backend/tests/api/students/test_profile_links.py

Implemented in: mobile/__tests__/students/menuRules.test.ts (mobile menuChildrenFor and applyRoleMenuRules; the web hub filter is inline in routes/_app/students/index.tsx). U02 asserts parent-like roles get the self-service rules and Teacher does not; Student versus Parent cannot be told apart through the exported API.

---

## F02 Admission number preview and generation

**Purpose.** Suggest and assign the next admission number, which is also the student's login username.

**Roles and permissions.** Preview `GET /students/admission/next-admission-number` needs `student_admissions:create` (Admin, Staff; menu: Students > Admission). Type options `GET /students/admission/admission-types/dropdown` need `student_admissions:read` (Admin, Staff, Teacher). Both use the exact-action check, so Student and Parent get 403.

**Preconditions.** An academic year exists (admission needs it, the preview does not).

**Steps, web.**
1. Students > Admission > "New Admission".
2. On the first step ("Student & Academic Details") the field "Admission Number" is filled automatically with a verified free number; the hint "Next available: <number>" shows under it while there is no error.
3. In "Academic Details" change "Admission Type" (default "Regular"; options "Pre Primary" and "Regular", relabelled from the API labels "Pre Primary Admission" and "Regular Admission") - the placeholder becomes `e.g. <year>0001` for pre primary or `e.g. 001` for regular and the suggestion is fetched again; an already typed number is never overwritten.
4. Tab out of the field: the client checks the number against existing students (fee student search) and shows "Admission number already exists. Please use a different number." when it is taken. Clearing the field and clicking "Next" shows "Admission number is required".

**Steps, mobile.** Same flow in `app/students/admission.tsx` (field "Admission Number", dropdown "Admission Type (Optional)"). The regular placeholder there reads `e.g. 2026001`, which does not match the real format (see Known gaps). A duplicate number is reported on "Create Admission" as toast "Validation Error - Admission number already exists. Please use a different number.".

**Expected results.** A suggested number is shown; a blank number sent to the API is generated server-side at create time; nothing is reserved by the preview.

**API endpoints.**
- `GET /students/admission/next-admission-number?type=regular|pre_primary` (default `regular`) returns `{next_number, format, type, note}`.
- `GET /students/admission/admission-types/dropdown` returns `[{value:"pre_primary",label:"Pre Primary Admission"},{value:"regular",label:"Regular Admission"}]`.
- Generation happens inside `POST /students/admission/` (F03) through `generate_admission_number`.

**Rules and validations.**
- Pre primary: `{YEAR}{SEQ:04d}`, for example `20260001`. `SEQ` = count of admissions with `admission_type = pre_primary` and `admission_date` in that year, plus 1. The year comes from the admission date (the preview uses today).
- Regular: `{SEQ:03d}`, for example `001`. `SEQ` = count of all `regular` admissions plus 1; one global sequence that never resets; above 999 the number simply grows to four digits.
- If the candidate already exists in `student_admissions.admission_number`, the sequence keeps increasing until it is free.
- Admission type when not sent: `pre_primary` if `student.is_primary == "primary"`, else `regular`. An explicit `admission_type` always wins. `type` outside `pre_primary|regular` is rejected (422).
- A manual number is trimmed; blank or whitespace means "generate". A manual number must be unique in `student_admissions.admission_number` (422 "Admission number '<n>' is already in use") and must not equal an existing `users.username` (422 "... is already in use as a login"). Any free text up to 50 characters is accepted.
- The web client verifies the suggestion with the fee student search (`feeCollectionApi.searchStudents`) and increments numeric values up to 50 times; a network error is treated as "free" and the server decides at create.

**Error and edge cases.** After deleting admissions, counts shrink and a generated candidate may collide with a manual number; the collision loop skips it. Two admins creating at once can both see the same preview; the second create gets the next number or a 422 if typed manually.

**Unit-testable logic.** `generate_admission_number(db, admission_date, admission_type)` with a fake session returning counts and existing numbers; admission type derivation; web `incrementAdmissionNumber`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-02-U01 | Regular, 0 existing regular admissions | "001" | passing |
| TC-STU-02-U02 | Regular, 41 existing | "042" | passing |
| TC-STU-02-U03 | Regular, 999 existing (boundary) | "1000" | passing |
| TC-STU-02-U04 | Pre primary, no admissions in 2026, admission_date 2026-04-01 | "20260001" | passing |
| TC-STU-02-U05 | Pre primary, 3 in 2025 and 0 in 2026; admission_date 2026-01-05, then 2025-12-31 | "20260001", then "20250004" (year taken from admission_date, sequence per year) | passing |
| TC-STU-02-U06 | Candidate "003" already exists (count = 2) | Returns "004"; if "003" and "004" both exist returns "005" | passing |
| TC-STU-02-U07 | Type derivation: (None, is_primary "primary"), (None, "not_primary"), ("regular", "primary") | pre_primary, regular, regular | passing |
| TC-STU-02-U08 | Manual number "   " vs "  A-77 " | First treated as blank (generate); second trimmed to "A-77" | passing |
| TC-STU-02-U09 | Web `incrementAdmissionNumber("0099")`, `("20260009")`, `("999")`, `("A12")` | "0100", "20260010", "1000", "A12" (non numeric unchanged) | blocked: incrementAdmissionNumber is not exported from web StudentStepForm.tsx |
| TC-STU-02-A01 | Admin `GET next-admission-number` with 0 regular admissions | 200 `{next_number:"001", format:"{SEQ:03d}", type:"regular", note:"Preview only..."}` | passing |
| TC-STU-02-A02 | Admin `?type=pre_primary` | 200, `format` "{YEAR}{SEQ:04d}", `next_number` starts with the current year and ends with a 4 digit sequence | passing |
| TC-STU-02-A03 | `type` omitted | Same as `type=regular` | passing |
| TC-STU-02-A04 | `?type=primary` and `?type=` (empty) | 422 validation error (Literal) | passing |
| TC-STU-02-A05 | Preview twice, then create one regular admission, preview again | First two identical (nothing reserved); third is the next sequence ("001" -> "002") | passing |
| TC-STU-02-A06 | Permission matrix on next-admission-number | Admin 200, Staff 200, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-02-A07 | Permission matrix on admission-types/dropdown | Admin 200, Staff 200, Teacher 200, Student 403, Parent 403; body is exactly the two options above | passing |
| TC-STU-02-A08 | No token on both endpoints | 401 | passing |
| TC-STU-02-A09 | Tenant isolation: tenant A has 5 regular admissions, tenant B has 0 | Tenant B Admin preview is unaffected by tenant A admissions; tenant A token with tenant B `cschema` header gets 403 | passing |
| TC-STU-02-A10 | Create two regular admissions back to back with blank `admission_number` | Responses carry "001" and "002" (or the next two free numbers) | passing |
| TC-STU-02-A11 | Create with `admission_number` equal to an existing admission number; then equal to an existing user's username | 422 "Admission number '<n>' is already in use"; 422 "... is already in use as a login" | passing |
| TC-STU-02-A12 | Create with manual number "ABC-9" | 201; response `admission_number` "ABC-9"; the student user's username is "ABC-9" | passing |
| TC-STU-02-A13 | Create pre primary with `admission_date` 2025-06-01 and blank number | Number starts with "2025" | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-02-E01 | P1 | Web | Admin | QA Admin login; active academic year in the header | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "New Admission". | Dialog "New Student Admission", "Student & Academic Details", "Step 1 of 5"; "Admission Number" is pre-filled with a free number and the hint "Next available: <n>" shows under it; placeholder "e.g. 001"; "Admission Type" shows "Regular" | passing |
| TC-STU-02-E02 | P2 | Web | Admin | QA Admin login | 1. Sign in as Admin.<br>2. Open Students > Admission and click "New Admission".<br>3. Clear "Admission Number".<br>4. Set "Admission Type" to "Pre Primary". | Placeholder becomes "e.g. <current year>0001" and the field refills with the pre primary suggestion (<current year> followed by a 4 digit sequence) | planned |
| TC-STU-02-E03 | P2 | Web | Admin | Seeded student Harsha Raju (004) | 1. Sign in as Admin.<br>2. Open Students > Admission and click "New Admission".<br>3. Replace "Admission Number" with "004".<br>4. Press Tab. | Inline error "Admission number already exists. Please use a different number." under the field | planned |
| TC-STU-02-E04 | P2 | Mobile | Admin | Seeded student Harsha Raju (004) | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission and tap "New Admission".<br>3. Wait until "Admission Number" is pre-filled.<br>4. Replace it with "004".<br>5. Fill the required fields of every step with "QA " data.<br>6. Tap "Create Admission". | Toast "Validation Error - Admission number already exists. Please use a different number."; the form returns to step 1 with the error under "Admission Number"; nothing is created | planned |
| TC-STU-02-E05 | P3 | Web | Admin | QA Admin login | 1. Sign in as Admin.<br>2. Open Students > Admission and click "New Admission".<br>3. Clear "Admission Number".<br>4. Enter First Name "QA Test" and select a Joining Class.<br>5. Click "Next". | Red alert "Please fill in the required fields before continuing: Admission Number"; inline "Admission number is required"; still Step 1 of 5 | planned |

API tests implemented in: backend/tests/api/students/test_admission_create.py

Implemented in: backend/tests/unit/student/test_admission_number.py

---

## F03 New admission (web wizard, mobile form, API)

**Purpose.** Admit a student: one call creates the student user, student, father/mother/optional guardian parents and users, the links and the admission record.

**Roles and permissions.** `student_admissions:create` (Admin, Staff). Menu: Students > Admission. The "New Admission" button is hidden without the permission.

**Preconditions.** Active academic year selected in the header (web), classes and sections from Masters, optional castes and locations. Roles `Student` and `Parent` must exist in the tenant, otherwise 422 "Required roles (Student/Parent) not found in system".

**Steps, web.**
1. Students > Admission > "New Admission" opens the dialog "New Student Admission" with a progress bar "Step n of 5".
2. Step 1 "Student & Academic Details". Optional "Student Photo" ("Choose photo", JPG, PNG or WebP, max 2 MB, otherwise toast "Photo must be under 2 MB"). Student Details: "Admission Number", "First Name" *, "Last Name", "Date of Birth", "Gender" (Male, Female, Other; sent as M, F, O), "Student Type" (Day Scholar, Hostel), "Nationality", "Mother Tongue" (default Telugu), "Aadhar Number (Optional)", "APAAR Number (Optional)", "Caste (Optional)", "Sub Caste (Optional)", "Community (Optional)", "Identification Marks (Optional)". Academic Details: "Admission Date" (cannot be after today), "Admission Type", "Joining Class" *, "Joining Section", checkbox "Current Class/Section same as Admission Class/Section", "Current Class", "Current Section". Click "Next".
3. Step 2 "Parent Details" (section heading "Parent & Guardian Details"). Father's Information: "Name" *, "Email", "Phone" with checkbox "Primary" (checked by default, makes the phone required), "Occupation (Optional)", "Salary Range (Optional)", "Aadhar Number (Optional)", "Gender (Optional)", "Relation to Student" (read only "Father"). Mother's Information: same fields, name and phone optional. "Guardian's Information (Optional)": "Name (Optional)", Email (required once a name is typed: "Guardian's email is required"), Phone, Occupation, Salary Range, Aadhar Number, Gender, Relation to Student. Field messages: "Father's name is required", "Phone number is required", "Phone number must contain digits only", "Must be exactly 10 digits" (with the count entered), "Aadhar number must be 12 digits", "Invalid email address", "Mother's email must be different from father's email". Click "Next".
4. Step 3 "Address Details": "Address Line 1" *, "Address Line 2 (Optional)", "City (Optional)", "State (Optional)", "District (Optional)", "Mandal (Optional)", "Pincode (Optional)". Click "Next".
5. Step 4 "Previous School": select "Previous School" No/Yes; when Yes: "Previous School Name (Optional)", "Previous Class (Optional)", "Previous School Remarks (Optional)". Click "Next".
6. Step 5 "Review & Submit": read-only summary. Click "Create Admission" (button shows "Creating..."). "Previous" goes back, "Cancel" closes the dialog.
7. "Next" validates the step: missing or invalid fields are listed in a red alert "Please fill in the required fields before continuing: <labels>" (labels such as "Joining Class", "Student First Name", "Student Aadhar Number", "Father's Name", "Father's Phone", "Address Line 1") and the step does not change. On "Create Admission" a missing required value gives toast "Please fill in required fields: <names>" and jumps to the earliest step; equal father and mother emails give toast "Father's and Mother's email addresses must be different"; no academic year in the header gives "Academic Year is required. Please select an academic year from the header dropdown.".
8. On success: toast "Student admission created successfully!", the optional photo is uploaded, the dialog closes and the table refreshes. A server error shows toast "Failed to create admission: <detail>".

**Steps, mobile.** Students > Admission (screen "Student Admissions") > "New Admission". Same five steps ("Student & Academic Details", "Parent Information", "Address Details", "Previous School", "Review & Submit") with collapsible sections, a "Step n of 5" bar, buttons "Previous", "Cancel", "Next", "Create Admission". Dates can be typed as DD/MM/YYYY or picked; the form state stays `YYYY-MM-DD`. Extra fields not on web: "Academic Year *" (required, "Required" when empty) and "Admitted Year (Optional)" dropdowns; "Student Type (Optional)". Inline errors include "First name is required", "Required" (Joining Class, Academic Year, Admission Date), "Father's name is required", "Phone number is required", "Guardian's email is required", "Address is required". Photo is picked on the first step and uploaded after create. Success toast "Success - Student admission created successfully!".

**Expected results.** HTTP 201 with `StudentAdmissionResponse` (admission fields plus `student` with nested `father`, `mother`, `guardian`; `student.is_active` is null on create). Stored: `users` (student, username = admission number, password hash of the default student password, `is_first_login = TRUE`), `students`, `parents` + `users` for father and mother (and guardian), `student_parent_links`, `student_admissions`. Mandatory class fees are auto-applied; a failure there is only logged.

**API endpoints.** `POST /students/admission/` with `academic_year_id`*, `admitted_class_id`*, `address_line1`*, `admission_date`, `admission_type`, `admission_number`, section and current class ids, `state_id`/`district_id`/`mandal_id`, previous school fields, and `student{first_name*, last_name*, date_of_birth, gender, is_primary, aadhar_number, apaar_number, caste, caste_id, sub_caste, sub_caste_id, community, nationality, mother_tongue, identification_marks, primary_phone, father{...}*, mother{...}*, guardian{...}}`. Each parent object needs `relation_to_student` (`Father`, `Mother`, `Guardian`).

**Rules and validations.**
- Required by the schema: `academic_year_id`, `admitted_class_id`, `address_line1` (min length 1), `student.first_name`, `student.last_name` (optional; missing, null or blank is stored as `""`), `student.father`, `student.mother`, `father.phone`, each parent's `relation_to_student`. A blank `first_name` (after trim) is 400 "Student first name is required".
- `student.father.name` is NOT enforced by the API: a blank or missing parent name becomes the relation label ("Father", "Mother", "Guardian") before the "name is required" check runs. Only the web and mobile forms enforce it.
- `date_of_birth` blank or null becomes `1900-01-01`. `aadhar_number` and `apaar_number` must be exactly 12 digits; `primary_phone` exactly 10 digits (422 otherwise). Parent `aadhar_number` must also be 12 digits when given (422, enforced by `ParentBase`); parent `salary_range` must be one of `below_1l|1l_3l|3l_5l|5l_10l|above_10l`. `email` must be a valid email (EmailStr).
- `admission_date` defaults to today; a future date is 400 "Admission date cannot be in the future".
- Father and mother emails must differ (400). An email that belongs to a non-Parent user is rejected (422 "Email <e> is already registered to a <Role>, not a parent").
- The admission number rules are in F02. `admission_type` is `pre_primary` or `regular`.
- Client rules (web and mobile): phones exactly 10 digits and digits only; father phone required unless "Primary" is unticked; guardian email required once a guardian name is entered; Aadhar/APAAR 12 digits; pincode 6 digits (the backend ignores `pincode`); admission date not in the future; mother email different from father email.
- `state` is sent as the state UUID (same value as `state_id`); `caste` and `sub_caste` are sent as caste UUIDs (web) - see Known gaps.
- Everything is one transaction; any failure rolls all rows back.

**Error and edge cases.** Missing role rows 422; duplicate number 422; duplicate email vs non-parent 422; blank first name 400; bad Aadhar 422; unauthorised 403. A blank father phone from the API is 422 "father.phone is required".

**Unit-testable logic.** Pydantic validators on `StudentBase`/`StudentCreate`/`ParentBase`; `PLACEHOLDER_DATE_OF_BIRTH`; web `validatePhoneDigits`, `makeExactDigitsValidator`, required-field list; mobile `computeStepErrors`, `validatePhone`, `isFutureDate`, `isValidDate`, `isValidEmail`, `isValidAadhar`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-03-U01 | `StudentBase` with `aadhar_number` "12345678901" (11), "1234567890123" (13), "12345678901a", "123456789012", "" | First three raise "Must be a 12-digit number"; last two accepted | passing |
| TC-STU-03-U02 | `primary_phone` "123456789" (9), "12345678901" (11), "1234567890", None | 9 and 11 rejected "Must be a 10-digit number"; others accepted | passing |
| TC-STU-03-U03 | `date_of_birth` None, "" and "2015-06-30" | First two become 1900-01-01; third unchanged | passing |
| TC-STU-03-U04 | `ParentBase` with name None, "  ", "Asha" and relation "Mother" | Names become "Mother", "Mother", "Asha" | passing |
| TC-STU-03-U05 | `ParentBase` relation "Uncle" or missing; salary_range "2l_4l" | Validation errors (Literal) | passing |
| TC-STU-03-U06 | `StudentCreate` with father.phone None and with father.phone "9876543210" | First raises "father.phone is required"; second accepted | passing |
| TC-STU-03-U07 | `StudentCreate` with father.name None | Accepted; father.name == "Father" (name check cannot fire) | passing |
| TC-STU-03-U08 | `StudentAdmissionBase` with `address_line1` "" and "x" | "" rejected (min length 1); "x" accepted | passing |
| TC-STU-03-U09 | `ParentBase.email` "a@b", "ok@x.com", None | "a@b" rejected; others accepted | passing |
| TC-STU-03-U10 | Web `validatePhoneDigits` with "", "98765", "98765432101", "98765abcde", "9876543210" | true, message (too short), message (too long), message (digits only), true | blocked: validatePhoneDigits is not exported from web ParentsStepForm.tsx |
| TC-STU-03-U11 | Web `makeExactDigitsValidator('Aadhar number',12)` with "", 11 digits, 12 digits, 13 digits | true, short message, true, long message | blocked: makeExactDigitsValidator is not exported from web StudentStepForm.tsx |
| TC-STU-03-U12 | Mobile `computeStepErrors(1)` with father name "", father phone "" (required), guardian name "Raj" and no guardian email | errors for father name, father phone ("Phone number is required"), guardian email ("Guardian's email is required") | blocked: computeStepErrors is inside the component in mobile app/students/admission.tsx |
| TC-STU-03-U13 | Mobile `isFutureDate` for tomorrow and today; `isValidDate("2026-13-40")` | true/false; false | blocked: isFutureDate and isValidDate are not exported from mobile app/students/admission.tsx |
| TC-STU-03-A01 | Admin creates admission with only required fields (no optional fields; mother object with only `relation_to_student`) | 201; `student.last_name` "" if sent "", `date_of_birth` "1900-01-01", mother name "Mother", `admission_date` = today, regular type, number "001" | passing |
| TC-STU-03-A02 | Admin creates with every field populated (Aadhar, APAAR, caste, locations, previous school, guardian with email) | 201; response echoes all fields; `student.father`, `student.mother`, `student.guardian` populated | known defect: STU-BUG-2: POST /students/admission/ response has student.father, mother and guardian null |
| TC-STU-03-A03 | `is_primary` "primary" and no `admission_type` | 201; stored `admission_type` pre_primary; number `<year>0001` | passing |
| TC-STU-03-A04 | Explicit `admission_type` "regular" with `is_primary` "primary" | regular wins; number "00n" format | passing |
| TC-STU-03-A05 | Missing each of `academic_year_id`, `admitted_class_id`, `address_line1`, `student.first_name`, `student.father`, `student.mother`, `father.phone` (one case per field) | 422 naming the field | passing |
| TC-STU-03-A06 | `first_name` "   " | 400 "Student first name is required" | passing |
| TC-STU-03-A07 | `address_line1` "" | 422 | passing |
| TC-STU-03-A08 | Boundaries: Aadhar 11/12/13 digits, APAAR 11/12/13, primary_phone 9/10/11, parent Aadhar 11/12/13 | 422 for 11 and 13 (9 and 11 for phone), 201 for 12 (10 for phone) | passing |
| TC-STU-03-A09 | `admission_date` tomorrow; today; yesterday | 400 "Admission date cannot be in the future"; 201; 201 | passing |
| TC-STU-03-A10 | Same email for father and mother | 400 "Father and mother cannot have the same email address" | passing |
| TC-STU-03-A11 | Father email already used by a Staff user | 422 "Email <e> is already registered to a Staff, not a parent" | passing |
| TC-STU-03-A12 | Invalid `salary_range` "2l_4l"; invalid parent email "abc" | 422 | passing |
| TC-STU-03-A13 | Father name omitted | 201 and father name stored as "Father" (documented gap, see Known gaps) | passing |
| TC-STU-03-A14 | Roles `Student` or `Parent` missing in the tenant | 422 "Required roles (Student/Parent) not found in system" | skipped: needs a tenant without the Student and Parent roles; |
| TC-STU-03-A15 | Student can log in after create: `POST /auth/login` with username = admission number and the default student password | Login returns `requires_password_change` true (first login) | passing |
| TC-STU-03-A16 | Admission is atomic: force a failure after the student row (for example invalid `admitted_class_id` UUID that violates the FK) | Error response and no `users`, `students`, `parents` or `student_admissions` rows were left behind | passing |
| TC-STU-03-A17 | A class has a mandatory (`all_by_default`) fee mapping; create the admission | 201 and a fee student mapping exists; when the mapping step is made to fail the admission still returns 201 | skipped: needs a mandatory fee class mapping, which belongs to the FEE module fixtures |
| TC-STU-03-A18 | Permission matrix for `POST /students/admission/` | Admin 201, Staff 201, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-03-A19 | No token | 401 | passing |
| TC-STU-03-A20 | Tenant isolation: create in tenant A, list in tenant B; use token A with `cschema` B | Row absent in B; 403 for the mismatch | passing |
| TC-STU-03-A21 | Extra fields `pincode` and `student.student_name` in the body | Accepted and ignored (201); not stored | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-03-E01 | P1 | Web | Admin | Seeded Class 2 with section 2-A; no student "QA Asha Rao" yet | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "New Admission" and note the "Admission Number".<br>4. Enter First Name "QA Asha" and Last Name "Rao".<br>5. Select Joining Class "Class 2" and Joining Section "2-A".<br>6. Click "Next".<br>7. Enter Father Name "QA Ramesh Rao", Email "qa.father1@example.com", Phone "9000000001".<br>8. Click "Next".<br>9. Enter Address Line 1 "QA 1 Main Road".<br>10. Click "Next" twice.<br>11. Click "Create Admission".<br>12. Set "Rows per page" to 100 (the "Search..." box filters only the current page), then search the new name. | Toast "Student admission created successfully!"; the dialog closes; the table shows the noted number, "QA Asha Rao", Class 2, 2-A and an Active badge; a student login with the admission number as username and a parent login qa.father1@example.com exist | known defect: UI-STU-01: a new admission with only the Joining Class/Section filled has no current class or section, so the ... |
| TC-STU-03-E02 | P2 | Web | Admin | QA Admin login | 1. Sign in as Admin.<br>2. Open Students > Admission and click "New Admission".<br>3. Leave First Name and Joining Class empty.<br>4. Click "Next". | Red alert "Please fill in the required fields before continuing: Joining Class, Student First Name"; inline "First name is required"; still Step 1 of 5 | planned |
| TC-STU-03-E03 | P3 | Web | Admin | QA Admin login | 1. Sign in as Admin.<br>2. Open the "New Admission" dialog.<br>3. Fill First Name "QA Test" and a Joining Class.<br>4. Enter "Aadhar Number (Optional)" "12345678901".<br>5. Click "Next". | Inline message starting "Aadhar number is less than 12 digits" with the count entered; the alert lists "Student Aadhar Number"; step does not change | planned |
| TC-STU-03-E04 | P3 | Web | Admin | QA Admin login | 1. Open the "New Admission" dialog and complete step 1 with "QA Test" data.<br>2. Click "Next".<br>3. Enter Father Name "QA Father", leave Phone empty ("Primary" ticked).<br>4. Click "Next".<br>5. Untick "Primary".<br>6. Click "Next", fill Address Line 1 "QA Road", go to "Review & Submit" and click "Create Admission". | Step 4: "Phone number is required" and the alert lists "Father's Phone"; step 6: "Next" is allowed after unticking, but "Create Admission" shows toast "Please fill in required fields: Father's Phone" and returns to step 2; nothing is created | planned |
| TC-STU-03-E05 | P3 | Web | Admin | QA Admin login | 1. Open the "New Admission" dialog and complete step 1.<br>2. Click "Next".<br>3. Enter Father Email "qa.same@example.com" and Mother Email "qa.same@example.com".<br>4. Click "Next". | Inline "Mother's email must be different from father's email" under the mother email | planned |
| TC-STU-03-E06 | P2 | Web | Admin | QA Admin login | 1. Open the "New Admission" dialog and complete step 1.<br>2. Click "Next".<br>3. Fill the father fields.<br>4. Enter Guardian "Name (Optional)" "QA Guardian" and leave its Email empty.<br>5. Click "Next". | Inline "Guardian's email is required"; the alert lists the guardian email; still on "Parent Details" | planned |
| TC-STU-03-E07 | P3 | Web | Admin | QA Admin login | 1. Open the "New Admission" dialog.<br>2. Open the "Admission Date" picker and try to pick tomorrow.<br>3. Type tomorrow's date in the field.<br>4. Click "Next". | Dates after today cannot be picked (max is today); a typed future date gives "Admission date cannot be in the future" and blocks "Next" | planned |
| TC-STU-03-E08 | P2 | Web | Admin | Seeded Class 2 / 2-A | 1. Create an admission "QA Prev Yes" as in TC-STU-03-E01 but on "Previous School" select "Yes" and enter Name "QA Old School", Class "LKG", Remarks "QA moved".<br>2. Create an admission "QA Prev No" leaving "Previous School" on "No".<br>3. Open "View Admission" for both. | "QA Prev Yes" shows Previous School Name "QA Old School", Previous Class "LKG", Previous School Remark "QA moved"; "QA Prev No" has is_previous_school false and stores "NA" for the three fields (the view hides the previous school rows) | planned |
| TC-STU-03-E09 | P2 | Web | Admin | Seeded student Harsha Raju (004) | 1. Open the "New Admission" dialog.<br>2. Fill all required fields with "QA Dup" data.<br>3. On step 1 replace "Admission Number" with "004" and do not tab out of it.<br>4. Go to "Review & Submit" and click "Create Admission". | The wizard returns to step 1 with the field error "Admission number already exists. Please use a different number."; nothing is created | planned |
| TC-STU-03-E10 | P3 | Web | Admin | A 3 MB JPG and a 1 MB JPG on the test machine | 1. Open the "New Admission" dialog.<br>2. Click "Choose photo" and pick the 3 MB file.<br>3. Click "Choose photo" and pick the 1 MB file.<br>4. Complete the admission "QA Photo Kid" and click "Create Admission".<br>5. Open "View Admission" for it. | Step 2: toast "Photo must be under 2 MB" and no preview; step 3: round preview; after create the view shows the photo | planned |
| TC-STU-03-E11 | P3 | Web | Admin | QA Admin login | 1. Open the "New Admission" dialog and fill steps 1 to 3 with "QA Back" data.<br>2. On "Address Details" click "Previous".<br>3. Check the parent fields, then click "Cancel".<br>4. Search the table for "QA Back". | "Previous" shows "Parent Details" with the typed data kept; "Cancel" closes the dialog; no "QA Back" admission exists | planned |
| TC-STU-03-E12 | P2 | Web | Staff, Teacher, Student | QA Staff and QA Teacher logins; seeded student login 004 | 1. Sign in as Staff and open Students > Admission.<br>2. Repeat as Teacher.<br>3. Repeat with the seeded student login 004. | Staff sees "Bulk Upload" and "New Admission"; Teacher and Student see neither | planned |
| TC-STU-03-E13 | P1 | Mobile | Admin | Seeded Class 2 / 2-A | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission and tap "New Admission".<br>3. Enter First Name "QA Mobile", Last Name "Kid", choose "Academic Year *" (the active year), Joining Class "Class 2".<br>4. Tap "Next".<br>5. Enter Father Name "QA Mobile Father", Phone "9000000003".<br>6. Tap "Next", enter Address Line 1 "QA Mobile Road".<br>7. Tap "Next" twice, then "Create Admission". | Toast "Success - Student admission created successfully!"; "Student Admissions" lists "QA Mobile Kid" | passing |
| TC-STU-03-E14 | P2 | Mobile | Admin | QA Admin login | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission and tap "New Admission".<br>3. Leave First Name and Joining Class empty.<br>4. Tap "Next". | Inline "First name is required" and "Required" under the class; the sections holding the errors are expanded; still "Step 1 of 5" | planned |
| TC-STU-03-E15 | P3 | Mobile | Admin | QA Admin login | 1. Open the mobile "New Admission" form.<br>2. Fill First Name "QA Year" and Joining Class, leave "Academic Year *" empty.<br>3. Tap "Next". | "Required" under "Academic Year *"; the step does not change (the label and validation now mark the year as required) | planned |

API tests implemented in: backend/tests/api/students/test_admission_create.py

Implemented in: backend/tests/unit/student/test_admission_schemas.py. U07 asserts the current behaviour (father.name None becomes Father) and is the documented defect KG-3.

---

## F04 Parent and guardian accounts created or reused at admission

**Purpose.** Give every parent a login and share one parent account across siblings.

**Roles and permissions.** Created as part of `POST /students/admission/` (`student_admissions:create`: Admin, Staff). No separate screen.

**Preconditions.** Role `Parent` exists.

**Steps, web and mobile.** Fill the Parent Details step of F03. To admit a sibling, enter the same father (or mother or guardian) email as an existing parent.

**Expected results.**
- New parent: a `parents` row and a `users` row with role Parent, username = email, or `<admission number>.father` / `.mother` when the email is blank, default parent password, `is_first_login = TRUE`. A guardian is created only when an email is present (username = email).
- Existing parent (matching email on a user with role Parent): no new user; the parent's fields (name, phone, occupation, salary range, Aadhar, gender) are overwritten with the new payload; a new `student_parent_links` row links the new child. Links are not duplicated.

**API endpoints.** Same call as F03. Parents of a student: `GET /student-parent-links/student/{student_id}/parents` (F20).

**Rules and validations.**
- Reuse is by email and only among users with role Parent. The email itself is never changed on reuse.
- A guardian with a blank email is silently dropped (no parent, user or link). Both clients require the guardian email once a name is typed.
- Editing a parent through one child's admission changes it for all siblings (F08).
- Usernames are never regenerated after edits.

**Error and edge cases.** Existing parent user with no `parents` row: 404 "Parent record not found for existing father user <email>". Father and mother with the same email: 400 (F03). Blank father email and blank mother email both get distinct fallback usernames.

**Unit-testable logic.** Username fallback rule (`email or f"{admission_number}.father"`), reuse overwrite loop (fields except `email`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-04-U01 | Username rule for father with email "f@x.com" and with None, admission number "001" | "f@x.com"; "001.father" | passing |
| TC-STU-04-U02 | Overwrite loop on an existing parent with payload name "New", phone "9000000001", email "other@x.com" | name and phone updated; email unchanged | passing |
| TC-STU-04-A01 | Create admission with new father and mother emails | 201; two Parent users exist; `GET /student-parent-links/student/{id}/parents` returns 2 parents; both have `is_first_login` TRUE | passing |
| TC-STU-04-A02 | Create admission with blank father and mother emails | Parent usernames "<number>.father" and "<number>.mother" | passing |
| TC-STU-04-A03 | Sibling admission reusing the father email with a changed phone | Same parent id; phone overwritten; the parent now lists 2 children; no new Parent user | passing |
| TC-STU-04-A04 | Guardian with email | Guardian parent, user and link created; response `student.guardian` populated | passing |
| TC-STU-04-A05 | Guardian name given but email blank | 422 with `guardian.email is required` | passing |
| TC-STU-04-A06 | Guardian email equal to an existing Parent's email | Existing guardian parent reused and linked | passing |
| TC-STU-04-A07 | Mother email equal to an existing Student user's email | 422 email_role_conflict | passing |
| TC-STU-04-A08 | Parent login: `POST /auth/login` with father email and the default parent password | `requires_password_change` true; after set-password the token role is Parent | passing |
| TC-STU-04-A09 | `GET /student-parent-links/my-children` as the shared parent after two admissions | Returns both children | passing |
| TC-STU-04-A10 | Permission matrix of the creating endpoint | Admin 201, Staff 201, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-04-A11 | Tenant isolation: parent email already used in tenant B | Tenant A admission creates a separate parent (emails are unique per tenant) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-04-E01 | P1 | Web | Admin | TC-STU-03-E01 done | 1. Sign in as Admin.<br>2. Create an admission "QA Ravi Rao" in Class 2 / 2-A with Father Name "QA Ramesh Rao", Email "qa.father1@example.com", Phone "9000000002".<br>3. Open "View Admission" for "QA Asha Rao". | Both admissions exist; QA Asha Rao's view shows Father Phone "9000000002" (one shared parent record); the parent login qa.father1@example.com now has two children | passing |
| TC-STU-04-E02 | P2 | Web | Admin | Seeded Class 2 / 2-A | 1. Create an admission "QA No Email" leaving Father Email and Mother Email empty.<br>2. Open "View Admission" for it. | Admission succeeds; "Father Email" and "Mother Email" show "N/A"; parent usernames are "<admission number>.father" and "<admission number>.mother" | planned |
| TC-STU-04-E03 | P2 | Mobile | Admin | QA Admin login | 1. Open the mobile "New Admission" form and complete step 1.<br>2. Tap "Next".<br>3. Fill the father fields and enter a guardian name "QA Guardian" without email.<br>4. Tap "Next". | Inline "Guardian's email is required" in the guardian section; the step does not change | planned |

API tests implemented in: backend/tests/api/students/test_admission_create.py

Implemented in: backend/tests/unit/student/test_admission_service.py (drives add_admission with a scripted fake session).

---

## F05 Student photo upload and removal

**Purpose.** Attach or remove a student's photo.

**Roles and permissions.** `student_admissions:update` (Admin, Staff). Both endpoints use the exact-action check.

**Preconditions.** The student exists.

**Steps, web.**
1. During admission: Step 1 "Student Photo (Optional)" > "Choose photo"; uploaded after "Create Admission" (a failure is silent).
2. Existing student: Students > Admission, row action "Edit Admission", dialog "Edit Admission - <number>": under "Student Photo" click "Choose photo" (uploads immediately, label "Uploading...") or the small X "Remove photo" on the picture. The photo shows in "Admission Details" view.

**Steps, mobile.** Admission form step 1 photo picker; uploaded after create or update; the view modal shows the photo.

**Expected results.** `photo_url` on `student` points to `/media/<tenant id>/student/photos/<student id>.<ext>`; clients prefix the API origin. The file is public (media is served without auth).

**API endpoints.**
- `POST /students/admission/id/{student_id}/photo` multipart field `photo` returns `StudentOut` with `photo_url`.
- `DELETE /students/admission/id/{student_id}/photo` returns `{"detail":"Student photo deleted successfully"}`.

**Rules and validations.**
- Extensions `.jpg .jpeg .png .webp` (checked on the filename only, 400 "Only jpg, png, webp files are allowed"). Max 2 MB: a file larger than 2,097,152 bytes is 400 "File size must not exceed 2 MB"; exactly 2,097,152 bytes is accepted.
- The file is named `<student id><ext>`; uploading a different extension removes the previous file.
- Delete of a student with no photo is 404 "No photo to delete". Unknown student 404 "Student not found".

**Error and edge cases.** Web checks the 2 MB limit client side before calling. A `.png` extension with non-image content is accepted (no content sniffing). Files are not removed when the student is deleted.

**Unit-testable logic.** Size and extension checks in `upload_student_photo` with a fake `UploadFile` and session.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-05-U01 | Extension check for "a.JPG", "a.jpeg", "a.png", "a.webp", "a.gif", "a" | First four accepted (case-insensitive); last two rejected | passing |
| TC-STU-05-U02 | Size check at 2,097,152 and 2,097,153 bytes | Accepted; rejected "File size must not exceed 2 MB" | passing |
| TC-STU-05-U03 | Replacing `<id>.png` with `<id>.jpg` | Old file removed, new URL stored | passing |
| TC-STU-05-A01 | Admin uploads a 100 KB PNG | 200; `photo_url` "/media/<tenant id>/student/photos/<student id>.png"; file exists on disk | passing |
| TC-STU-05-A02 | Upload `.gif`; upload 2 MB + 1 byte; upload exactly 2 MB | 400; 400; 200 | skipped: size boundary needs a 2 MB file; |
| TC-STU-05-A03 | Upload for an unknown student id | 404 "Student not found" | passing |
| TC-STU-05-A04 | Delete an existing photo, then delete again | 200 `{"detail":...}`; then 404 "No photo to delete"; `photo_url` null afterwards | passing |
| TC-STU-05-A05 | Missing multipart field `photo` | 422 | passing |
| TC-STU-05-A06 | Permission matrix for upload and delete | Admin 200, Staff 200, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-05-A07 | No token | 401 | passing |
| TC-STU-05-A08 | Tenant isolation: tenant B Admin uploads a photo for a tenant A student id; tenant A token with B header | 404 (student not visible); 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-05-E01 | P3 | Web | Admin | TC-STU-03-E01 done; a 3 MB JPG | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "Edit Admission" on "QA Asha Rao".<br>4. Under "Student Photo" click "Choose photo" and pick the 3 MB file. | Toast "Photo must be under 2 MB"; no upload request; the photo placeholder stays | planned |
| TC-STU-05-E02 | P1 | Web | Admin | TC-STU-03-E01 done; a 200 KB JPG | 1. Open "Edit Admission" on "QA Asha Rao".<br>2. Click "Choose photo" and pick the JPG.<br>3. Click the X "Remove photo" on the picture. | Step 2: label "Uploading..." then toast "Photo uploaded successfully" and the picture shows; step 3: toast "Photo removed successfully" and the placeholder icon returns | passing |
| TC-STU-05-E03 | P2 | Mobile | Admin | Seeded Class 2 / 2-A; a JPG on the device | 1. Open the mobile "New Admission" form.<br>2. Pick the photo on step 1.<br>3. Complete the admission "QA Mobile Photo" and tap "Create Admission".<br>4. Tap "View" on its card. | The view modal shows the uploaded photo | planned |

API tests implemented in: backend/tests/api/students/test_photo.py

Implemented in: backend/tests/unit/student/test_admission_service.py (upload_student_photo in a temp working directory).

---

## F06 Admission list, search and student dropdowns

**Purpose.** Browse admitted students, find one, and fill student pickers.

**Roles and permissions.** List `GET /students/admission/` and search use `check_user_resource_access(student_admissions, list)`: Admin, Staff, Teacher see all; Student sees only their own admission (`list_own`); Parent only linked children (`list_related`). Dropdowns need `students:list` (Admin, Staff, Teacher). `GET /by-admission/{admission_id}` needs `student_admissions:read` (exact). Menu: Students > Admission.

**Preconditions.** At least one admission.

**Steps, web.** Students > Admission. The table "Admission No. | Student Name | Class | Section | Academic Year | Admission Date | Status | Actions" has an "S.No." first column and is paged (default 10 rows; "Rows per page" 5, 10, 20, 50, 100; "Previous" and "Next"; a range label such as "1-10 of <total>"). Above it a "Filters" bar has a "Search..." box that filters the rows of the current page only (client side), so set "Rows per page" to 100 before searching for a record that is not on page 1, and the column headers sort. Status shows an Active/Inactive badge. Class and Section cells are inline editable (see F08). Row actions: "Send Welcome Message" (only with `communications:create`, so Admin by default), "View Admission", "Edit Admission" and "Deactivate Student" / "Activate Student" (both need `student_admissions:update`). Empty table: "No data". Pickers elsewhere use the dropdown endpoints (documents, certificates, transport).

**Steps, mobile.** Students > Admission: search field "Search" (server search `GET /students/admission/search`), buttons "Bulk Import" and "New Admission" (create permission), cards with admission number, name, class, status and actions "View", "Edit", "Deactivate"/"Activate"; pager; empty text "No admissions found". Separate screen "Students (N)" (`app/students/index.tsx`): 30 per page, client-side filter over the loaded page only ("No students found." when nothing matches), card shows the admission number and the admitted class id.

**Expected results.** Newest admissions first (ordered by `admission_date` descending). Responses carry `items`, `total_count`, `has_next`.

**API endpoints.**
- `GET /students/admission/?skip=0&limit=10&class_id=&section_id=&as_of_date=` returns `PaginatedResponse<StudentAdmissionResponse>`. `skip >= 0`, `limit` 1..100 (default 10). `class_id`/`section_id` filter on the **current** class and section. `as_of_date` keeps admissions with `admission_date <= as_of_date`. `active_only=true` (default false) keeps only students whose account is active.
- `GET /students/admission/search?query=` (min length 1) returns up to 10 students `{id, name, first_name, last_name}`, ordered by first and last name, matched on first name, last name or full name (not admission number); scoped by role.
- `GET /students/admission/by-admission/{admission_id}` returns the student (`StudentOut`).
- `GET /students/admission/students/dropdown` returns `[{id, display_name "First Last (ADM)", first_name, last_name, admission_number ("N/A" when none)}]` sorted by display name.
- `GET /students/admission/students/dropdown/simple` returns `[{id, name}]` sorted by name. Both support `class_id`, `section_id`, `active_only` (default true), `as_of_date`.

**Rules and validations.**
- The list fills `student.father` and `student.mother` and `student.is_active`, not `student.guardian`.
- The list returns inactive students too; dropdowns exclude them by default.
- Out-of-range `limit` (0 or 101) or negative `skip` is 422.
- Role scoping: Student gets at most their own row; Parent gets only linked children; a role with no `list` or `_own`/`_related` grant gets 403.

**Error and edge cases.** A list call without `limit` returns 10 rows; the attendance rosters page through it 100 at a time (see F11). The web "Search..." box only searches the page on screen, so a student on another page is not found. Empty class returns `items: []`, `total_count: 0`, `has_next: false`.

**Unit-testable logic.** `has_next = (skip + limit) < total_count`; dropdown display-name formatting and sort; `as_of_date` filter.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-06-U01 | `has_next` for (skip 0, limit 10, total 10), (0,10,11), (10,10,20), (10,10,21) | false, true, false, true | passing |
| TC-STU-06-U02 | Dropdown display name for ("Asha","Rao","001") and admission number None | "Asha Rao (001)"; "Asha Rao" with admission_number "N/A" | passing |
| TC-STU-06-U03 | Dropdown sort of ["Zed Z (3)","Amy A (1)"] | "Amy A (1)" first | passing |
| TC-STU-06-A01 | Admin lists with 25 admissions, `limit=10&skip=0` and `skip=20` | 10 items `has_next` true; 5 items `has_next` false; `total_count` 25 | passing |
| TC-STU-06-A02 | `limit=0`, `limit=101`, `skip=-1` | 422 each; `limit=100` is accepted | passing |
| TC-STU-06-A03 | Filter by `class_id` and `section_id` of Class 1 / A | Only students whose current class and section match | passing |
| TC-STU-06-A04 | `as_of_date` earlier than a student's admission date | That student is excluded; boundary: equal date is included | passing |
| TC-STU-06-A05 | List contains a deactivated student | Included with `student.is_active` false; `student.guardian` is null even when a guardian exists | passing |
| TC-STU-06-A06 | Search "asha" (case-insensitive), "Asha R", and an admission number "001" | Name matches returned (max 10, ordered); admission number matches nothing | passing |
| TC-STU-06-A07 | Search with empty `query` | 422 (min length 1) | passing |
| TC-STU-06-A08 | List and search as Student | Only the student's own row; `total_count` 1 | passing |
| TC-STU-06-A09 | List and search as Parent with two children, one other family's child exists | Exactly the two linked children | passing |
| TC-STU-06-A10 | Teacher and Staff list | All students (no class scoping) | passing |
| TC-STU-06-A11 | Dropdown default and `active_only=false`; with `class_id` | Inactive excluded by default and included with false; class filter applied | passing |
| TC-STU-06-A12 | Dropdown permission matrix | Admin, Staff, Teacher 200; Student 403; Parent 403 | passing |
| TC-STU-06-A13 | `by-admission/{admission_id}` with a valid admission id, a student id, a random id | Student returned; 404 "Admission ID not found" for the student id and random id | passing |
| TC-STU-06-A14 | `by-admission` permission matrix | Admin, Staff, Teacher 200; Student 403; Parent 403 | passing |
| TC-STU-06-A15 | No token on list, search, by-admission, both dropdowns | 401 | passing |
| TC-STU-06-A16 | Tenant isolation: tenant B Admin lists; tenant A token with B header | Tenant A students absent; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-06-E01 | P1 | Web | Admin | 30 seeded admissions | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "Next" below the table. | Columns S.No., Admission No., Student Name, Class, Section, Academic Year, Admission Date, Status, Actions; 10 rows, newest admission date first; range "1-10 of <total>"; "Next" shows rows 11 to 20 | passing |
| TC-STU-06-E02 | P2 | Web | Admin | 30 seeded admissions | 1. Open Students > Admission.<br>2. Change "Rows per page" to 20. | 20 rows; range "1-20 of <total>" with the same total as before | planned |
| TC-STU-06-E03 | P2 | Web | Teacher | QA Teacher login; seeded admissions | 1. Sign in as Teacher.<br>2. Open Students > Admission. | Rows visible with only the "View Admission" action; no "Send Welcome Message", "Edit Admission" or "Deactivate Student"; no "New Admission" or "Bulk Upload" | planned |
| TC-STU-06-E04 | P2 | Web | Student | Seeded student login 004 (Harsha Raju) | 1. Sign in with the seeded student login 004.<br>2. Open Students > Admission. | Table with one row (Harsha Raju) and only "View Admission"; no create, edit or toggle controls | planned |
| TC-STU-06-E05 | P2 | Mobile | Admin | Seeded students Harsha Raju and Tanvi Raju | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission.<br>3. Type "Raju" in "Search". | The list narrows to Harsha Raju and Tanvi Raju (server search on name); clearing the box restores the list | planned |
| TC-STU-06-E06 | P3 | Mobile | Admin | Seeded student Harsha Raju (004) | 1. Open Students ("Students (N)") on mobile.<br>2. Type "004" in the search box.<br>3. Type "QA zzz". | Step 2: only matching cards of the loaded page; step 3: "No students found." | planned |
| TC-STU-06-E07 | P3 | Web | Admin | 30 seeded admissions (more than one page) | 1. Open Students > Admission.<br>2. Keep "Rows per page" at 10 (at 100 every match is on one page), then type "Raju" in the "Search..." box.<br>3. Click the "Student Name" header twice. | Only rows of the current page that match are shown (a matching student on another page is not found); the header click sorts ascending then descending | planned |

API tests implemented in: backend/tests/api/students/test_admission_read.py

Implemented in: backend/tests/unit/student/test_admission_service.py.

---

## F07 Admission details view

**Purpose.** See the complete admission record of one student.

**Roles and permissions.** `GET /students/admission/id/{student_id}` uses `check_user_resource_access(student_admissions, read, target)`: Admin, Staff, Teacher read any; Student only their own id; Parent only linked children (others 404).

**Preconditions.** Admission exists.

**Steps, web.** Students > Admission, row action "View Admission": dialog "Admission Details - <number>" with the student name and photo and a two-column table (labels: Admission Number, Admission Date, Academic Year, Admitted Class, Admitted Section, Current Class, Current Section, Address Line 1, Address Line 2, City, State, District, Mandal, Student Name, Date of Birth, Gender, Aadhar Number, APAAR Number, Primary Phone, Caste, Sub Caste, Community, Nationality, Mother Tongue, Identification Marks, Father/Mother/Guardian Name, Email, Phone, Occupation, Aadhar, Gender, and Previous School Name/Class/Remark when applicable). "Close" closes it. The alternative full page `/students/admission/<admission id>` shows the same table titled "Admission Details" with "Back to List".

**Steps, mobile.** Admission list card > "View" (modal with the same fields and a photo). Students list card opens "Student Details" (`app/students/[id].tsx`): "Admission Number", status, "Basic Information", "Address", "Father", "Mother", "Recent Attendance (30d)", "Certificates", "Documents", "Transport", button "Edit Student".

**Expected results.** Dates "1900-01-01" display as "N/A" on web. Ids resolve to names (class, section, year, state, district, mandal, caste). Gender M/F/O displays as Male/Female/Other.

**API endpoints.** `GET /students/admission/id/{student_id}` returns `StudentAdmissionResponse`; `student.father/mother/guardian` populated, `student.is_active` null.

**Rules and validations.** The path id is the **student id**. An admission id gives 404. Out-of-scope id for Student or Parent gives 404 "Student admission not found" (not 403).

**Error and edge cases.** Mobile `[id].tsx` is opened with the student id but looks it up by admission id (`items.find(s => s.id === id)`) in the first page of admissions only (default limit 10), so every card opened from "Students (N)" shows "Student not found" (see Known gaps). The web detail page expects an admission id while the table uses student ids. A failed detail load shows toast "Failed to load admission details".

**Unit-testable logic.** Web `formatDate` (1900-01-01 and invalid values give "N/A"), `formatGender`; mobile `formatGender`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-07-U01 | Web `formatDate` for "1900-01-01", "", undefined, "2026-04-01" | "N/A", "N/A", "N/A", localized date | blocked: formatDate is inline in web AdmissionTable.tsx, not exported |
| TC-STU-07-U02 | `formatGender` for "M", "female", "O", "x", undefined | "Male", "Female", "Other", "X", "N/A" | blocked: formatGender is inline in web AdmissionTable.tsx and mobile myadmission.tsx, not exported |
| TC-STU-07-A01 | Admin reads an admission by student id | 200 with admission fields, `student.father`, `student.mother`, `student.guardian`, `student.photo_url` | passing |
| TC-STU-07-A02 | Read with an admission id or a random UUID | 404 "Student admission not found" | passing |
| TC-STU-07-A03 | Student reads own id; reads another student's id | 200; 404 | passing |
| TC-STU-07-A04 | Parent reads a linked child; reads an unlinked child | 200; 404 | passing |
| TC-STU-07-A05 | Staff and Teacher read any student | 200 | passing |
| TC-STU-07-A06 | Malformed id "abc" | 422 | passing |
| TC-STU-07-A07 | No token | 401 | passing |
| TC-STU-07-A08 | Tenant isolation: tenant B Admin reads a tenant A student id; token A with B header | 200 `[]` for reads and 404 for the link create (RLS hides tenant A rows; unknown ids give an empty list, not 404); 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-07-E01 | P1 | Web | Admin | Seeded student Harsha Raju (004, Class 1 / 1-B) | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Set "Rows per page" to 100, search "Harsha Raju" and click "View Admission" on that row.<br>4. Click "Close". | Dialog "Admission Details - <number>" with the name "Harsha Raju" under the title; Admitted Class "Class 1", Current Section "1-B", Father Name "Venkat Raju", Father Email "venkat.raju@example.com", City "Hyderabad"; names are shown, not ids; empty optional fields show "N/A" | passing |
| TC-STU-07-E02 | P3 | Web | Admin | TC-STU-03-E01 done (no date of birth entered) | 1. Open "View Admission" on "QA Asha Rao". | "Date of Birth" shows "N/A" (stored sentinel 1900-01-01) | planned |
| TC-STU-07-E03 | P3 | Web | Admin | Admission id of Harsha Raju (004) known | 1. Open /students/admission/<admission id of Harsha Raju>.<br>2. Compare with the "View Admission" dialog.<br>3. Click "Back to List". | Same values on the page "Admission Details"; "Back to List" returns to the table | planned |
| TC-STU-07-E04 | P2 | Mobile | Admin | Seeded student Harsha Raju (004) | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission.<br>3. Tap "View" on "Harsha Raju".<br>4. Close the modal. | Modal with Admission Number, Academic Year, class, student, parent and address fields of Harsha Raju; the close button closes it | planned |
| TC-STU-07-E05 | P2 | Mobile | Admin | Seeded student Harsha Raju (004) | 1. Open Students ("Students (N)") on mobile.<br>2. Tap the card of "Harsha Raju". | "Student Details" shows "Admission Number", status, "Basic Information", "Address", "Father", "Mother", "Recent Attendance (30d)", "Certificates", "Documents", "Transport" and "Edit Student" | blocked: Known gap 12 (lookup by admission id, always "Student not found") |

API tests implemented in: backend/tests/api/students/test_admission_read.py

---

## F08 Edit admission

**Purpose.** Correct admission, student and parent details.

**Roles and permissions.** `PATCH /students/admission/{student_id}` uses `check_user_resource_access(student_admissions, update, target)`: Admin and Staff (scope all). Teacher, Student, Parent have no `update`, so 403. The web "Edit Admission" icon needs `student_admissions:update`.

**Preconditions.** Admission exists.

**Steps, web.**
1. Students > Admission, row action "Edit Admission" opens "Edit Admission - <number>".
2. Change fields: Student photo; First Name *, Last Name, Date of Birth, Gender, "Primary Status" (Not Primary, Primary), Aadhar Number (Optional), APAAR Number (Optional), Primary Phone, Nationality, Mother Tongue, Caste, Sub Caste, Community, Identification Marks; Admission Number *, Admission Date, Admission Type, Academic Year *, Admitted Class *, Admitted Section, Current Class, Current Section; Address Line 1 *, Address Line 2, City, State, District, Mandal; "Has Previous School", Previous School Name, Previous Class, Previous School Remark; "Father's Details" (Name *, Email, Phone *, Occupation, Aadhar Number, Gender, Salary Range), "Mother's Details" and "Guardian's Details (Optional)" (same, optional).
3. Click "Update Admission" (label "Updating...") or "Cancel". Errors are listed together; toast "Please fix the highlighted fields before saving". Success toast "Student admission updated successfully!"; a server error shows "Failed to update admission: <detail>".
4. Quick edit: in the table, Class and Section cells are inline editable; saving sends only the current class and section.

**Steps, mobile.** Admission list card > "Edit" opens the same 5-step form in edit mode ("Update Admission").

**Expected results.** Only sent fields change (`exclude_unset`). Student, admission and linked parent rows are updated in one transaction; response is the updated admission.

**API endpoints.** `PATCH /students/admission/{student_id}` body `StudentAdmissionUpdate` (admission fields, flat student fields, `father_*`, `mother_*`, `guardian_*` fields).

**Rules and validations.**
- `admission_date` cannot be null (400) or in the future (400). `admission_number` blank is ignored (kept); a changed number must be unique (422 "Admission number '<n>' is already in use"); the username does not change.
- `first_name` cannot be blank (400); `date_of_birth` blank becomes 1900-01-01; `father_name` and `father_phone` cannot be blank (400); `academic_year_id` and `admitted_class_id` cannot be set to null (400).
- Father and mother emails must differ (400). Emails are optional and may be cleared; `users.email` is not changed.
- The PATCH schema does not validate Aadhar, APAAR, phone or email formats (the web edit form does: 12 digits, 10 digits, email pattern). A guardian can be updated only if one is already linked; a new guardian cannot be added.
- Parent edits apply to the shared parent record (siblings see the change).

**Error and edge cases.** Unknown student id 404 "Admission not found". Admission id used instead of student id gives 404. Integrity error 500 "database" message.

**Unit-testable logic.** Field grouping (STUDENT_FIELDS, FATHER_FIELDS...), prefix stripping, web `aadharMsg`/`emailMsg`, required-field list in the edit save handler.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-08-U01 | Parent field mapping: `father_phone` -> parent.phone, `mother_occupation` -> parent.occupation | Correct attribute set after stripping the prefix | passing |
| TC-STU-08-U02 | Web edit validation with father phone "12345" and Aadhar "123" | Messages listed for both; save blocked | blocked: web edit validation is inline in the AdmissionTable.tsx save handler |
| TC-STU-08-A01 | Admin patches `first_name` only | 200; only first name changed | passing |
| TC-STU-08-A02 | Patch `father_phone`, `mother_email`, `guardian_name` of an existing guardian | Parent rows updated; response reflects the changes | passing |
| TC-STU-08-A03 | Patch `admission_number` to an existing one; to a free one; to "  " | 422; 200 (username unchanged); 200 and old number kept | passing |
| TC-STU-08-A04 | Patch `admission_date` null; tomorrow; today | 400; 400; 200 | passing |
| TC-STU-08-A05 | Patch `first_name` ""; `father_name` ""; `father_phone` "" | 400 each | passing |
| TC-STU-08-A06 | Patch `academic_year_id` null; `admitted_class_id` null | 400 each | passing |
| TC-STU-08-A07 | Patch `date_of_birth` null | 200; stored 1900-01-01 | passing |
| TC-STU-08-A08 | Patch `father_email` equal to the mother's email | 400 "Father and mother cannot have the same email address" | passing |
| TC-STU-08-A09 | Patch `aadhar_number` "abc" and `primary_phone` "1" | 422 for each | passing |
| TC-STU-08-A10 | Patch `guardian_name` when no guardian is linked | 200; nothing created | passing |
| TC-STU-08-A11 | Shared parent edit: patch the father phone via child 1 | Child 2's details show the new phone | passing |
| TC-STU-08-A12 | Patch with an admission id or random id | 404 "Admission not found" | passing |
| TC-STU-08-A13 | Permission matrix | Admin 200, Staff 200, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-08-A14 | No token | 401 | passing |
| TC-STU-08-A15 | Tenant isolation: tenant B Admin patches a tenant A student; token A with B header | 404; 403 | passing |
| TC-STU-08-A16 | Patch `admission_type` from regular to pre_primary | 200; number unchanged | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-08-E01 | P1 | Web | Admin | TC-STU-03-E01 done | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "Edit Admission" on "QA Asha Rao".<br>4. Change Last Name to "Rao-Edited" and Current Section to "2-B".<br>5. Click "Update Admission". | Toast "Student admission updated successfully!"; the row shows "QA Asha Rao-Edited" with Section 2-B; "View Admission" shows the new values | passing |
| TC-STU-08-E02 | P2 | Web | Admin | TC-STU-03-E01 done | 1. Open "Edit Admission" on "QA Asha Rao".<br>2. Clear "Admission Number *" and Father "Phone *".<br>3. Click "Update Admission". | Toast "Please fix the highlighted fields before saving"; the error list names "Admission Number" and "Father Phone (must be 10 digits)"; nothing is saved | planned |
| TC-STU-08-E03 | P2 | Web | Admin | TC-STU-04-E01 done | 1. Open "Edit Admission" on "QA Ravi Rao".<br>2. Replace "Admission Number *" with the number of QA Asha Rao.<br>3. Click "Update Admission". | Inline "Admission number already exists. It must be unique."; nothing is saved | planned |
| TC-STU-08-E04 | P2 | Web | Admin | TC-STU-03-E01 done; seeded Class 3 / 3-A | 1. Open Students > Admission.<br>2. Click the Class cell of "QA Asha Rao" and choose "Class 3".<br>3. Click the Section cell and choose "3-A".<br>4. Save the inline edit. | Toast "Student admission updated successfully!"; the row shows Class 3 / 3-A (current class and section changed, admitted class unchanged) | planned |
| TC-STU-08-E05 | P2 | Web | Teacher, Student | QA Teacher login; seeded student login 004 | 1. Sign in as Teacher and open Students > Admission.<br>2. Sign in with the seeded student login 004 and open Students > Admission. | No "Edit Admission" icon for either role | planned |
| TC-STU-08-E06 | P2 | Mobile | Admin | TC-STU-03-E13 done | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission and tap "Edit" on "QA Mobile Kid".<br>3. Change Nationality to "QA Nation".<br>4. Go to the last step and tap "Update Admission".<br>5. Tap "View". | Toast "Success - Student admission updated successfully!"; the view shows Nationality "QA Nation" | planned |

API tests implemented in: backend/tests/api/students/test_admission_manage.py

Implemented in: backend/tests/unit/student/test_admission_service.py.

---

## F09 Activate, deactivate and delete a student

**Purpose.** Block or restore a student's login without losing data; the delete endpoint exists but must not be used.

**Roles and permissions.** `PATCH /students/admission/{student_id}/toggle-active` needs `student_admissions:update` (Admin, Staff); `DELETE /students/admission/{admission_id}` needs `student_admissions:delete` (Admin).

**Preconditions.** Student exists.

**Steps, web.** Students > Admission, row action "Deactivate Student" (red) or "Activate Student": confirm dialog "Disable Student" / "Enable Student" with "Are you sure you want to disable <name>?" and buttons "Disable"/"Enable". Toast "Student disabled successfully!" or "Student enabled successfully!". There is no delete button.

**Steps, mobile.** Admission card action "Deactivate" / "Activate": confirm modal "Deactivate Student" / "Activate Student" with button "Deactivate" / "Activate". Toast "Success - Student status updated" (failure: "Failed to update student status").

**Expected results.** `users.is_active` flips; an inactive student cannot log in; dropdowns exclude the student; the list still shows them with an Inactive badge.

**API endpoints.**
- `PATCH /students/admission/{student_id}/toggle-active` flips the current value (the web sends a body that is ignored) and returns the admission with `student.is_active`.
- `DELETE /students/admission/{admission_id}` answers 200 `{"message": ...}`. It deletes the student's attendance, documents, certificates (uploaded and generated), fee mappings with their term amounts, transport assignments and trips, the parent links, the admission, the student and the student user. A parent (and their user) is deleted only when no other student is linked to them. It answers 409 when the student has fee payments, fee concessions, previous fee dues, exam marks or results, homework records, or another admission, or when a foreign key still references the student; nothing is deleted in that case.

**Rules and validations.** Toggle is a flip, not a set: two quick clicks end where they started. A student with no linked user gives 400 "Student has no associated user". Unknown id 404.

**Error and edge cases.** Delete uses the **admission id** (student id gives 404). Shared parents are kept. Uploaded document files and the photo file are not removed from disk. Prefer toggle-active for students with history.

**Unit-testable logic.** Flip logic on `user.is_active`; web toast wording from the `isActive` argument.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-09-U01 | Flip logic with a fake student whose user is_active True then False | Becomes False then True; returned `student.is_active` matches | passing |
| TC-STU-09-A01 | Admin toggles an active student | 200; `student.is_active` false; toggling again true | passing |
| TC-STU-09-A02 | After deactivation the student logs in | `POST /auth/login` fails (inactive user) | passing |
| TC-STU-09-A03 | Deactivated student in dropdowns | Absent by default, present with `active_only=false`; present in the admission list | passing |
| TC-STU-09-A04 | Toggle an unknown id; with an admission id | 404 "Student not found" | passing |
| TC-STU-09-A05 | Toggle permission matrix | Admin 200, Staff 200, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-09-A06 | Delete permission matrix on a throwaway admission | Admin: 200 and data removed; Staff 403; Teacher 403; Student 403; Parent 403 | passing |
| TC-STU-09-A07 | Delete a student whose father is shared with a sibling | 200; the shared father (and user) remain linked to the sibling; the mother, if not shared, is deleted | passing |
| TC-STU-09-A08 | Delete a student with a fee payment or exam marks | 409 and nothing deleted | skipped: blocked: needs a fee payment or exam marks for the student, which belong to FEE and EXM fixtures |
| TC-STU-09-A11 | Delete an unknown id | 404 "Admission not found" | passing |
| TC-STU-09-A09 | No token on both endpoints | 401 | passing |
| TC-STU-09-A10 | Tenant isolation for toggle: tenant B Admin toggles a tenant A student; token A with B header | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-09-E01 | P1 | Web | Admin | TC-STU-03-E13 done ("QA Mobile Kid" active) | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "Deactivate Student" on "QA Mobile Kid".<br>4. Click "Disable".<br>5. Click "Activate Student" on the same row and click "Enable". | Dialog "Disable Student" "Are you sure you want to disable QA Mobile Kid?"; toast "Student disabled successfully!", badge Inactive and the icon becomes "Activate Student"; step 5: dialog "Enable Student", toast "Student enabled successfully!", badge Active | passing |
| TC-STU-09-E02 | P3 | Web | Admin | An active "QA " student | 1. Click "Deactivate Student" on the row.<br>2. Click "Cancel". | Dialog closes; badge stays Active; no request sent | planned |
| TC-STU-09-E03 | P2 | Web | Staff, Teacher | QA Staff and QA Teacher logins; seeded admissions | 1. Sign in as Staff and open Students > Admission.<br>2. Sign in as Teacher and open Students > Admission. | Staff sees "Deactivate Student" (or "Activate Student"); Teacher does not | planned |
| TC-STU-09-E04 | P2 | Mobile | Admin | An active "QA " student | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission.<br>3. Tap "Deactivate" on the card and confirm "Deactivate".<br>4. Tap "Activate" and confirm "Activate". | Confirm modals "Deactivate Student" and "Activate Student"; toast "Success - Student status updated" each time; the card status changes to inactive and back to active | planned |

API tests implemented in: backend/tests/api/students/test_admission_manage.py

Implemented in: backend/tests/unit/student/test_admission_service.py.

---

## F10 Bulk admission upload (Excel)

**Purpose.** Create many admissions from a spreadsheet; each row is independent.

**Roles and permissions.** `student_admissions:create` for upload, template download and the number preview (Admin, Staff).

**Preconditions.** An active academic year (the sheet has no year column); classes and sections exist; the template file `backend/app/static/templates/student_admission_bulk_upload_template.xlsx` exists.

**Steps, web.**
1. Students > Admission > "Bulk Upload" opens "Bulk Admission Upload" ("Download the template, fill in student rows, then upload the completed sheet.").
2. "Download Template" saves `bulk_admission_template.xlsx` (blank, with Class/Section/Caste/Sub caste dropdowns).
3. Fill the sheet "Student Admission". Click "Browse File" (accepts .xlsx, .xls), then "Upload".
4. The result box shows "<created> of <total> admission(s) created", a list "Row n: <name> (<admission number>)" and "<k> row(s) failed" with the error lines. "Close" ends. A whole-file error shows toast "Bulk upload failed: <detail>"; a template error "Failed to download template: <detail>".

**Steps, mobile.** Students > Admission > "Bulk Import" opens "Bulk Import Students": step 1 "Download Template" with the option "Auto Fetch Details" and button "Download Blank Template" or "Download Pre-filled Template"; step 2 "Upload Filled File" ("Tap to select the filled Excel file") and "Upload & Create Admissions"; "Results" chips "<n> created" and "<n> total rows" plus error lines. Toasts: "Upload Complete - <c> of <t> admissions created successfully.", "Upload Finished With Errors - <c> created, <e> failed. See details below.", "Upload Failed - <detail>", "Please select an Excel (.xlsx/.xls) file" for another file type.

**Expected results.** Valid rows are created via the normal admission flow (accounts, links, fees); invalid rows are listed and skipped. Response `{created:[{row, student_id, admission_number, name}], errors:["Row n: ..."], total_rows}`.

**API endpoints.**
- `POST /students/admission/bulk-upload` multipart `file` (.xlsx or .xls, else 400 "File must be an Excel (.xlsx/.xls) file").
- `GET /students/admission/bulk-upload/template?include_data=false|true` returns an xlsx stream (`student_admission_bulk_upload_template.xlsx`); true pre-fills one row per existing admission.

**Rules and validations.**
- The workbook sheet "Student Admission" is used (falls back to the active sheet). Required headers (case-sensitive, exact): `First name`, `joining class`, `Father name`, `Father phone`, `Address Line 1`; otherwise 400 "Missing required column(s): ...". Unreadable file 400 "Invalid Excel file: ...".
- Other headers read: `Admission no`, `Admission date`, `last name`, `Date of birth` (a header starting with "Date of birth" is accepted, hint stripped), `Gender`, `Student type`, `Nationality`, `Mother Tongue`, `Apaar no`, `Aadhar No`, `Caste`, `Sub caste`, `Community`, `Identification marks`, `joining section`, `Current class`, `Current Section`, `Father Email|Occupatio|Aadhar|Gender|Salary`, `Mother Name|Email|Phone|Occupation|Aadhar No|Gender|Salary`, `Guardian Name|Email|Phone|Occupation|Aadhar no|Gender|Salary`, `Previous School(Yes/No)`, `Previous School Name|Class|Remarks`.
- Fully empty rows are skipped. Row errors: "First name is required"; "Date of birth '<v>' is not a valid date - use DD-MM-YYYY"; class/section "not found" with a "did you mean" suggestion (difflib, cutoff 0.6); "joining class is required"; "No active academic year configured"; "Father name and Father phone are required"; "Address Line 1 is required"; invalid salary text; Pydantic field errors (for example a bad Aadhar); duplicate number or email conflicts from the admission flow.
- Date formats accepted: `DD-MM-YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY` (tried in that order) or an Excel date. Salary: a literal (`below_1l`...) or a numeric amount mapped by bucket: below 100000 below_1l, below 300000 1l_3l, below 500000 3l_5l, below 1000000 5l_10l, otherwise above_10l.
- "Student type": "Pre Primary", "Preprimary", "Primary" (any case, `-`/`_` as space) map to `is_primary = primary` (which makes the admission type pre primary); anything else maps to `not_primary` (regular). Gender defaults: father "Male", mother "Female", guardian "Other". `Previous School(Yes/No)`: yes, y, true, 1.
- Academic year is the tenant's active year. Current class and section default to the joining ones. A guardian row is read only when `Guardian Name` is present.
- Template dropdowns (hidden `Lists` sheet) reflect live class, section, caste and cascading sub caste data; the "Admission no" hover hint shows the next regular and pre primary numbers.

**Error and edge cases.** A whole-file problem is 400; row problems never abort the batch. After a failed row the session rolls back but earlier committed rows stay. Mobile "Auto Fetch" is not offered on web.

**Unit-testable logic.** `_parse_date`, `_map_salary` (bucket boundaries), `_map_yes_no`, `_map_is_primary`, `_clean`, `_build_row_lookup`, `_suggest`, `_sub_caste_range_name`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-10-U01 | `_parse_date` for "25-12-2014", "2014-12-25", "25/12/2014", "12/25/2014", datetime, "", "31-02-2014", "abc" | 2014-12-25 for the first four; datetime date; None; None; None | passing |
| TC-STU-10-U02 | `_map_salary` for "99999", "100000", "299999.99", "300000", "499999", "500000", "999999", "1000000", "1,50,000", "3l_5l", "abc", "" | below_1l, 1l_3l, 1l_3l, 3l_5l, 3l_5l, 5l_10l, 5l_10l, above_10l, "1,50,000" parsed as 150000 -> 1l_3l, "3l_5l", error "Invalid ... Enter a numeric amount or one of: ...", None | passing |
| TC-STU-10-U03 | `_map_is_primary` for "Pre Primary", "pre-primary", "PREPRIMARY", "Primary", "Regular", "", None | primary x4; not_primary x3 | passing |
| TC-STU-10-U04 | `_map_yes_no` for "Yes", "y", "TRUE", "1", "No", None | True x4; False x2 | passing |
| TC-STU-10-U05 | `_build_row_lookup` with header "Date of birth (DD-MM-YYYY)" | Key "Date of birth" present | passing |
| TC-STU-10-U06 | `_suggest("Clas 1", ["Class 1","Class 2"])`; `_suggest("zzz", [...])` | "Class 1"; None | passing |
| TC-STU-10-U07 | `_sub_caste_range_name("Kamma Naidu-2")` | "sub_Kamma_Naidu_2" | passing |
| TC-STU-10-U08 | `_clean` for None, "  ", " x " | None, None, "x" | passing |
| TC-STU-10-A01 | Upload a sheet with 3 valid rows | 200 `{created:[3 items], errors:[], total_rows:3}`; 3 admissions, numbers sequential | passing |
| TC-STU-10-A02 | Sheet with 1 bad row (unknown class "Clas 1") among 3 | 2 created; `errors` has "Row 3: Class 'Clas 1' not found - did you mean 'Class 1'?"; `total_rows` 3 | known defect: STU-BUG-3: bulk upload resolves 'joining section' by name across the whole tenant, so a section name used by m... |
| TC-STU-10-A03 | Missing a required header (remove `Father phone`) | 400 "Missing required column(s): Father phone" | passing |
| TC-STU-10-A04 | Upload a `.csv` and a corrupted `.xlsx` | 400 "File must be an Excel (.xlsx/.xls) file"; 400 "Invalid Excel file: ..." | passing |
| TC-STU-10-A05 | Row errors: no First name; no Father phone; no Address Line 1; invalid DOB text; Aadhar of 11 digits; duplicate Admission no; duplicate father/mother email | One error line per row with the matching message | passing |
| TC-STU-10-A06 | No active academic year | Every row fails "No active academic year configured" | skipped: blocked: needs a tenant without an active academic year, and the active year is a tenant-wide singleton |
| TC-STU-10-A07 | "Student type" "Pre Primary" with blank Admission no | Number `<year>0001` style | passing |
| TC-STU-10-A08 | Empty rows between data rows | Skipped; `total_rows` counts only created + errors | passing |
| TC-STU-10-A09 | Template `include_data=false` | 200, content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, sheets "Student Admission" and hidden "Lists" with live class names | passing |
| TC-STU-10-A10 | Template `include_data=true` with 2 admissions | Rows 2 and 3 filled (Admission no, DOB as DD-MM-YYYY, Student type "Pre Primary" or "Regular") | passing |
| TC-STU-10-A11 | Permission matrix for upload and both templates | Admin 200, Staff 200, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-10-A12 | No token | 401 | passing |
| TC-STU-10-A13 | Tenant isolation: class "Class 1" exists only in tenant B; tenant A upload references it | Row error "Class ... not found" | passing |
| TC-STU-10-A14 | Re-upload the same sheet | Every row fails on duplicate number (if numbers given) or creates new students (if blank) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-10-E01 | P2 | Web | Admin | QA Admin login | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "Bulk Upload".<br>4. Click "Download Template". | Dialog "Bulk Admission Upload" with "Download the template, fill in student rows, then upload the completed sheet."; file bulk_admission_template.xlsx downloads with sheet "Student Admission" | planned |
| TC-STU-10-E02 | P1 | Web | Admin | Template from TC-STU-10-E01 filled with 3 valid rows (First name "QA Bulk 1" to "QA Bulk 3", joining class "Class 2", joining section "2-A", Father name, Father phone, Address Line 1) | 1. Open "Bulk Upload".<br>2. Click "Browse File" and choose the sheet.<br>3. Click "Upload". | Result "3 of 3 admission(s) created" with lines "Row n: QA Bulk n (<number>)"; the table lists the three students after "Close" | passing |
| TC-STU-10-E03 | P2 | Web | Admin | Sheet with 2 valid rows ("QA Bulk 4", "QA Bulk 5") and one row without "Father phone" | 1. Open "Bulk Upload".<br>2. Choose the sheet and click "Upload". | Result "2 of 3 admission(s) created" and "1 row(s) failed" with the error line for that row in red; the two good rows are created | planned |
| TC-STU-10-E04 | P2 | Web | Staff, Teacher | QA Staff and QA Teacher logins | 1. Sign in as Staff and open Students > Admission.<br>2. Sign in as Teacher and open Students > Admission. | Staff sees "Bulk Upload"; Teacher does not | planned |
| TC-STU-10-E05 | P2 | Mobile | Admin | Seeded admissions | 1. Sign in as Admin on mobile.<br>2. Open Students > Admission and tap "Bulk Import".<br>3. Switch on "Auto Fetch Details".<br>4. Tap "Download Pre-filled Template". | Screen "Bulk Import Students"; the button label changes from "Download Blank Template" to "Download Pre-filled Template"; the downloaded file has one row per existing admission (30 seeded plus QA ones) | planned |
| TC-STU-10-E06 | P2 | Mobile | Admin | Sheet with 2 valid rows ("QA Bulk M1", "QA Bulk M2") and 1 invalid row | 1. Open "Bulk Import Students".<br>2. Tap "Tap to select the filled Excel file" and pick the sheet.<br>3. Tap "Upload & Create Admissions". | Toast "Upload Finished With Errors - 2 created, 1 failed. See details below."; "Results" shows chips "2 created" and "3 total rows" and the error line | planned |
| TC-STU-10-E07 | P3 | Mobile | Admin | A .csv file on the device | 1. Open "Bulk Import Students".<br>2. Tap "Tap to select the filled Excel file" and pick the .csv. | Toast "Please select an Excel (.xlsx/.xls) file"; nothing is uploaded | planned |

API tests implemented in: backend/tests/api/students/test_bulk_upload.py

Implemented in: backend/tests/unit/student/test_bulk_upload_helpers.py.

---

## F11 Mark student attendance

**Purpose.** Record present, absent, late, half day or leave for the students of a class and section on a date.

**Roles and permissions.** `student_attendance:create` and `update` (Admin, Staff, Teacher). Teachers can mark any class. `student_attendance:list` is needed to load the roster data. Menu: Students > Attendance.

**Preconditions.** Class and section with admitted students; admission date on or before the attendance date.

**Steps, web.**
1. Students > Attendance (title "Student Attendance", card "Attendance Overview").
2. Choose "Class" ("Select Class"), "Section" ("Select Section", enabled after a class), "Date" (date picker; default today).
3. "Attendance Analysis" tiles Present, Absent, Late, Half Day, Leave, a colour bar with "<n> students total" and the line "<n>% Present" appear; below, "Filter Students" with the box "Search by name or roll no..." (matches the name or the admission number, shown as "Roll No: <admission number>"). Empty states: "No students found for the selected class and section." and "No students match "<text>".".
4. For each student pick a status in the dropdown (Present, Absent, Late, Half Day, Leave). Rows that are not Present can use the "Send Absentee Message" icon (shown only with `communications:create`; on a Present row it is disabled with a tooltip starting "Student is present"). A "Unsaved Changes" badge appears.
5. Click "Save Attendance" (button disabled without changes or without create/update permission) or "Refresh" to reload saved data. Toast "Attendance saved successfully!".

**Steps, mobile.** Students > Attendance: filters "Class", "Section", "Date"; header "Student Attendance" with "Refresh" and "Save Attendance"; "Select a class to view students" before a class is chosen; tiles Present, Absent, Late, Leave and "<n>% Present"; search "Search by name or roll no..."; status dropdown per student (Present, Absent, Late, Leave; no half day). Toast "Saved - Attendance saved successfully" (failure "Failed to save attendance").

**Expected results.** One `student_attendance` row per student per date. Web saves only non-present marks (bulk by-date upsert) and updates existing rows; mobile writes a row for every student including present.

**API endpoints.**
- `POST /student/attendance/` body `{student_id, date, status, remarks?}` (mobile create) returns 201.
- `PATCH /student/attendance/by-date/{date}` body `[{student_id, status, remarks?}]` (web create path) returns the touched rows.
- `GET /students/admission/?class_id=&section_id=&as_of_date=` for the roster (see F06) and `GET /student/attendance/by-date/{date}` for saved marks (F13).

**Rules and validations.**
- Status values (case-insensitive on create, lowercased by the schema): `present`, `absent`, `late`, `half_day`, `leave`. One row per `(student_id, date)` (constraint `uq_student_date`).
- Create: unknown student 404; date after today 400 "Attendance date cannot be in the future"; date before the student's admission date 400 "Attendance cannot be marked before the student's admission date (<date>)"; an existing row 422 "Attendance already marked for this student on this date"; invalid status 422 (schema).
- By-date PATCH: raw dicts, status must already be lowercase and valid (400 "Invalid attendance status '<s>'..."); future date 400 "Cannot update attendance for future dates"; empty list 400 "No attendance updates provided"; items without `student_id` or `status` are skipped silently; students admitted after the date are skipped silently; `remarks` is written only when non-empty; existing rows are updated, others inserted.
- The roster calls send `active_only=true` and page through the list 100 at a time, so every active student of the class loads and inactive students are excluded.

**Error and edge cases.** A non-UUID `student_id` inside the by-date array or an unknown id produces a 500 database error. Marking is never limited to the teacher's own class.

**Unit-testable logic.** Status normalisation (`normalize_status_before_validation`), status set validation, date guards (future, before admission), web summary and percentage `round((present + 0.5 * half_day) / total * 100)`, web save splitting (modified existing -> PATCH, new non-present -> bulk), mobile statusMap defaults.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-11-U01 | Schema with status "Absent", "LATE", "half_day", "holiday" | Lowercased valid values; "holiday" rejected | passing |
| TC-STU-11-U02 | Web percentage for present 8, half_day 2, others 0, total 10 and for total 0 | 90 and 0 | blocked: web percentage is inline in AttendancePage.tsx |
| TC-STU-11-U03 | Web save split: existing unmodified, existing changed to present, new absent, new present | Only the changed existing (PATCH) and the new absent (bulk) are sent | blocked: web save split is inline in AttendancePage.tsx |
| TC-STU-11-U04 | Date guards with today, tomorrow, admission date - 1 day | Accepted, rejected (future), rejected (before admission) | passing |
| TC-STU-11-U05 | Mobile statusMap build: students A, B and a saved record "absent" for A | A absent, B present (default) | blocked: mobile statusMap is built inline in app/students/attendance.tsx |
| TC-STU-11-A01 | Admin creates `present` for a student today | 201 `{id, student_id, date, status:"present", remarks:null}` | passing |
| TC-STU-11-A02 | Create with status "Late" (capital) | 201 stored "late" | passing |
| TC-STU-11-A03 | Create all five statuses on five dates; and "holiday" | 201 each; 422 for "holiday" | passing |
| TC-STU-11-A04 | Create a second row for the same student and date | 422 "Attendance already marked for this student on this date" | passing |
| TC-STU-11-A05 | Create for tomorrow; for the day before the admission date; on the admission date (boundary) | 400; 400; 201 | passing |
| TC-STU-11-A06 | Create for an unknown student id | 404 "Student not found" | passing |
| TC-STU-11-A07 | By-date PATCH with 3 students (one new absent, one existing present -> late, one admitted tomorrow) | 200 returns 2 rows; third skipped silently (an empty remark on a new row is stored as an empty string) | passing |
| TC-STU-11-A08 | By-date PATCH with status "Absent" (capital), empty array, future date | 400 invalid status; 400 "No attendance updates provided"; 400 future | passing |
| TC-STU-11-A09 | By-date PATCH items missing `student_id` or `status` | Skipped without error | passing |
| TC-STU-11-A10 | By-date PATCH with an unknown student id | 500 database error (documented) | passing |
| TC-STU-11-A11 | Create permission matrix | Admin 201, Staff 201, Teacher 201, Student 403, Parent 403 | passing |
| TC-STU-11-A12 | By-date PATCH permission matrix | Admin 200, Staff 200, Teacher 200, Student 403, Parent 403 | passing |
| TC-STU-11-A13 | No token on both endpoints | 401 | passing |
| TC-STU-11-A14 | Tenant isolation: tenant B Admin marks a tenant A student; token A with B header | 404 "Student not found"; 403 | passing |
| TC-STU-11-A15 | Teacher marks a student of a class they do not teach | 201 (no class scoping, documented) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-11-E01 | P1 | Web | Teacher | A QA class with one section and three QA students (QA names) created through the API; no attendance marked today | 1. Sign in as Teacher.<br>2. Open Students > Attendance.<br>3. Select the QA class and section; keep Date today.<br>4. Set the second QA student to Absent and the first to Late.<br>5. Click "Save Attendance".<br>6. Click "Refresh". | Before saving the badge "Unsaved Changes" shows; toast "Attendance saved successfully!"; after Refresh both statuses persist; tiles show Absent 1 and Late 1 and the "<n>% Present" line updates (33% with one Absent, one Late and one Present) | passing |
| TC-STU-11-E02 | P3 | Web | Teacher | Seeded Class 1 / 1-B | 1. Open Students > Attendance and load Class 1 / 1-B.<br>2. Change nothing. | "Save Attendance" is disabled; no "Unsaved Changes" badge | planned |
| TC-STU-11-E03 | P2 | Web | Teacher | Seeded Class 1 / 1-A (only Saanvi Iyer and Kavya Verma), no attendance marked today | 1. Load Class 1 / 1-A for today.<br>2. Set "Saanvi Iyer" to Half Day. | Tiles show Half Day 1 and Present 1; the line reads "75% Present" (half day counts 0.5) | planned |
| TC-STU-11-E04 | P3 | Web | Teacher | Seeded Class 1 / 1-B loaded | 1. Type "Harsha" in "Search by name or roll no...".<br>2. Type "002".<br>3. Type "QA zzz". | Step 1: only Harsha Raju; step 2: only Advik Mehta (matched on "Roll No: <admission number>"); step 3: 'No students match "QA zzz".' | planned |
| TC-STU-11-E05 | P2 | Web | Teacher | Class 2 / 2-A raised above 10 active students with QA admissions (for example TC-STU-10-E02 and TC-STU-10-E03 plus more), and one deactivated QA student in it | 1. Load that class and section for today.<br>2. Count the rows. | Every active student is listed (the roster pages 100 at a time); the inactive student is not listed; "<n> students total" equals the active count | planned |
| TC-STU-11-E06 | P3 | Web | Teacher | TC-STU-04-E01 done ("QA Ravi Rao" admitted today in Class 2 / 2-A) | 1. Load Class 2 / 2-A.<br>2. Set Date to yesterday. | "QA Ravi Rao" is not listed (as_of_date filter); seeded Arjun Yadav and Rahul Menon (admitted 2026-06-10) are listed | planned |
| TC-STU-11-E07 | P1 | Mobile | Teacher | Seeded Class 1 / 1-A (Saanvi Iyer, Kavya Verma); no attendance marked today | 1. Sign in as Teacher on mobile.<br>2. Open Students > Attendance.<br>3. Choose Class "Class 1", Section "1-A", today.<br>4. Set "Saanvi Iyer" to Absent.<br>5. Tap "Save Attendance". | Toast "Saved - Attendance saved successfully"; an attendance row exists for every listed student, including the ones left Present | passing |
| TC-STU-11-E08 | P3 | Mobile | Teacher | Seeded Class 1 / 1-A loaded on mobile | 1. Open the status dropdown of any student. | Options Present, Absent, Late, Leave only (no Half Day) | planned |
| TC-STU-11-E09 | P2 | Web | Student, Parent | Seeded student login 004; seeded parent login venkat.raju@example.com | 1. Sign in with the seeded student login 004 and open Students > Attendance.<br>2. Sign in as venkat.raju@example.com and open Students > Attendance. | Student sees "My Attendance" and Parent sees "Children's Attendance"; neither shows Class, Section, status dropdowns or "Save Attendance" | planned |
| TC-STU-11-E10 | P3 | Web | Admin | TC-STU-11-E01 done (Harsha Raju Absent today in Class 1 / 1-B) | 1. Sign in as Admin and load Class 1 / 1-B.<br>2. Hover the "Send Absentee Message" icon on a Present row.<br>3. Click the icon on the Absent row of Harsha Raju. | Step 2: the icon is disabled with a tooltip starting "Student is present"; step 3: dialog "Send Message" to "Harsha Raju" with the "Student Absentees" template preselected when it exists | planned |

API tests implemented in: backend/tests/api/students/test_attendance.py

Implemented in: backend/tests/unit/student/test_student_attendance.py (U01 schema, U04 add_attendance with a frozen date).

---

## F12 Correct or delete attendance

**Purpose.** Change a saved status or remove a wrong row.

**Roles and permissions.** `PATCH /student/attendance/{attendance_id}` needs `student_attendance:update` (Admin, Staff, Teacher); `DELETE` needs `student_attendance:delete` (Admin only). Both exact-action checks.

**Preconditions.** An attendance row exists.

**Steps, web.** Students > Attendance, open the same class, section and date, change a student's status, "Save Attendance" (existing rows are PATCHed, including back to Present). There is no delete button on web.

**Steps, mobile.** Same screen; existing rows are PATCHed when the status differs. No delete button.

**Expected results.** The row keeps its id and date; status and remarks change. Delete removes the row.

**API endpoints.**
- `PATCH /student/attendance/{attendance_id}` body `{status?, remarks?, date?}` (the update schema accepts `status` and `remarks`; the service also guards a `date` key if present).
- `DELETE /student/attendance/{attendance_id}` returns `{"detail":"Attendance record deleted successfully"}`.
- `PATCH /student/attendance/by-date/{date}` (see F11).

**Rules and validations.** Status must be one of the five values (422 from the schema, 400 from the service guard). Unknown id 404 "Attendance record not found". The path must be a UUID: `my-attendance` and `search` are declared before `/{attendance_id}` so they are not parsed as ids. By-date PATCH cannot clear remarks.

**Error and edge cases.** Web sends `remarks: ""` on PATCH, which stores an empty string. Mobile PATCH sends only `status`.

**Unit-testable logic.** Update field application (`exclude_unset`), status guard.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-12-U01 | `StudentAttendanceUpdate` with only remarks; with status "ABSENT"; with status "x" | Remarks-only accepted; "absent"; "x" rejected | passing |
| TC-STU-12-A01 | PATCH status absent -> present on an existing row | 200; same id; status "present" | passing |
| TC-STU-12-A02 | PATCH remarks only | 200; status unchanged; remarks set | passing |
| TC-STU-12-A03 | PATCH status "holiday" | 422 | passing |
| TC-STU-12-A04 | PATCH unknown id; malformed id "abc" | 404 "Attendance record not found"; 422 | passing |
| TC-STU-12-A05 | DELETE an existing row, then GET it | 200 `{"detail":...}`; GET 404 | passing |
| TC-STU-12-A06 | DELETE unknown id | 404 | passing |
| TC-STU-12-A07 | PATCH permission matrix | Admin 200, Staff 200, Teacher 200, Student 403, Parent 403 | passing |
| TC-STU-12-A08 | DELETE permission matrix | Admin 200; Staff 403; Teacher 403; Student 403; Parent 403 | passing |
| TC-STU-12-A09 | No token on PATCH and DELETE | 401 | passing |
| TC-STU-12-A10 | Tenant isolation: tenant B Admin patches or deletes a tenant A row; token A with B header | 404; 403 | passing |
| TC-STU-12-A11 | Static routes before dynamic: `GET /student/attendance/my-attendance` and `/search` | Not parsed as a UUID (no UUID 422 for these paths) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-12-E01 | P1 | Web | Teacher | TC-STU-11-E01 done (the second QA student Absent today); own QA class and students | 1. Sign in as Teacher.<br>2. Load the QA class and section for today.<br>3. Set the second QA student to Present.<br>4. Click "Save Attendance".<br>5. Click "Refresh". | Toast "Attendance saved successfully!"; after Refresh that student is Present (same row updated, not a second row) | passing |
| TC-STU-12-E02 | P2 | Mobile | Teacher | TC-STU-11-E01 done (Advik Mehta Late today) | 1. Sign in as Teacher on mobile.<br>2. Open Students > Attendance and load Class 1 / 1-B for today.<br>3. Set "Advik Mehta" to Absent.<br>4. Tap "Save Attendance". | Toast "Saved - Attendance saved successfully"; the record changes to Absent; tiles refresh | planned |

API tests implemented in: backend/tests/api/students/test_attendance.py

Implemented in: backend/tests/unit/student/test_student_attendance.py.

---

## F13 Attendance history and percentage

**Purpose.** Review saved attendance for a day, a student or a period, with counts and a percentage.

**Roles and permissions.**
- Staff views and `GET /student/attendance/`, `/search`, `/by-date/{date}`, `/{id}`: exact `student_attendance:list` or `read` (Admin, Staff, Teacher; Student and Parent get 403 under the default catalog).
- `GET /student/attendance/my-attendance`: `check_user_resource_access(student_attendance, read_own)`: Student only.
- `GET /student/attendance/student/{student_id}/filter`: `check_user_resource_access(list)`: Admin, Staff, Teacher any student; Student own only (403 for another id); Parent only linked children (403 otherwise).

**Preconditions.** Attendance rows exist.

**Steps, web.** Students > Attendance. Student: page "My Attendance", card "Filter by Date" ("From", "To", meant to default to the first of the month to today), summary tiles "Total Days, Present, Absent, Late, Half Day, Leave" (shown only when records exist) and list "Attendance Records" (newest first, "No attendance records found for the selected period."). Parent: page "Children's Attendance" for the child selected in the header, card "Filter by Date" (with "No child selected. Use the child switcher in the header above." when no child is selected), list titled "<child>'s Attendance" (or "Attendance"). Staff: the marking view shows saved marks for the chosen date and the percentage.

**Steps, mobile.** Student: "My Attendance" with "Filter by Date" (From, To) and tiles incl. "Total Days", "Half Day"; list "Attendance Records". Parent: month dropdown "Select Month", title "<child>'s Attendance", month summary and the line "<n>% attendance" (green at 75 or more, red below); without a selected child "Please select a student from the header". Staff: roster view.

**Expected results.** Records are listed newest first with date, status and remarks.

**API endpoints.**
- `GET /student/attendance/` all rows (unscoped).
- `GET /student/attendance/search?start_date&end_date&student_name` (dates optional; both needed to filter by range; start after end 400 "Start date cannot be after end date").
- `GET /student/attendance/my-attendance?start_date&end_date` (both required).
- `GET /student/attendance/{attendance_id}`.
- `GET /student/attendance/student/{student_id}/filter?start_date&end_date` (both required; unknown student 404; start after end 400).
- `GET /student/attendance/by-date/{date}` (future date 400 "Cannot retrieve attendance for future dates").

**Rules and validations.**
- One rule everywhere: `(present + 0.5 x half_day) / total records x 100`; late, absent and leave count as zero. Backend helper `app/service/student/attendance_percentage.py` is used by the profile (F18) and the student attendance report; web (`AttendancePage`, `useStudentAttendanceSummary`) and mobile (`src/utils/attendance.ts`, used by the roster and the history screen) compute the same formula client side.
- Static routes (`/search`, `/my-attendance`) are declared before `/{attendance_id}`.
- `GET /` and `/by-date/{date}` return every student's rows to any role with `list`.

**Error and edge cases.** A Parent calling `/my-attendance` gets 403 (no `read_own`). A Student calling `/my-attendance` without dates gets 422. No records: empty list. The web "From" default is built with `toISOString()` from local midnight, so in a timezone ahead of UTC (IST) it shows the last day of the previous month (seen 2026-10-07: "30 Sept 2026"). A Student login without a student record gets 403 from `student/{id}/filter` (the page then shows the empty-records text).

**Unit-testable logic.** The shared percentage rule (backend `attendance_percentage.py`, mobile `src/utils/attendance.ts`); summary counters; date range default (first of month to today); sort by date descending.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-13-U01 | Web staff percentage for present 18, half_day 4, absent 2, total 24 | round((18+2)/24*100) = 83 | blocked: web percentage is inline in AttendancePage.tsx |
| TC-STU-13-U02 | Mobile history percentage for present 10, late 2, absent 3, leave 5, total 20 | round(10/20*100) = 50 (late counts as zero) | passing: mobile/__tests__/students/attendancePercentage.test.ts |
| TC-STU-13-U03 | Mobile roster percentage for present 9, total 12 | 75 | passing: mobile/__tests__/students/attendancePercentage.test.ts |
| TC-STU-13-U04 | Summary counters on records of mixed statuses | total equals number of rows; each status counted once; half_day counted separately | blocked: summary counters are inline in the web and mobile attendance screens |
| TC-STU-13-U05 | Web `currentMonthRange` on 2026-10-02 | start "2026-10-01", end "2026-10-02" | blocked: currentMonthRange is not exported from web AttendancePage.tsx |
| TC-STU-13-A01 | Student `my-attendance` with a month range | 200; only own rows | passing |
| TC-STU-13-A02 | Student `my-attendance` without dates | 422 | passing |
| TC-STU-13-A03 | Parent `my-attendance` and Admin `my-attendance` | 403 | passing |
| TC-STU-13-A04 | Student `student/{own id}/filter`; `student/{other id}/filter` | 200; 403 "You can only access your own attendance records" | passing |
| TC-STU-13-A05 | Parent `student/{linked child}/filter` and `{unlinked child}/filter` | 200; 403 (ownership enforced 2026-10-02) | passing |
| TC-STU-13-A06 | Admin `student/{id}/filter` with start after end; unknown student | 400 "Start date cannot be after end date"; 404 | passing |
| TC-STU-13-A07 | Boundary range: start_date = end_date = a marked day | One row | passing |
| TC-STU-13-A08 | `by-date/{today}` as Teacher; `by-date/{tomorrow}` | 200 with all students' rows; 400 | passing |
| TC-STU-13-A09 | `search` with `student_name=asha`, with a range, and start after end | Filtered rows; filtered rows; 400 | passing |
| TC-STU-13-A10 | `GET /student/attendance/` and `GET /{id}` as Admin; unknown id | 200 list; 200 row; 404 | passing |
| TC-STU-13-A11 | Permission matrix for `GET /`, `/search`, `/by-date`, `/{id}` | Admin, Staff, Teacher 200; Student 403; Parent 403 | passing |
| TC-STU-13-A12 | No token on every endpoint of this feature | 401 | passing |
| TC-STU-13-A13 | Tenant isolation: tenant B sees no tenant A rows; token A with B header | Empty lists; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-13-E01 | P1 | Web | Student | A student created through the API for the test (QA name, own QA class) that has completed first login, with attendance on 2026-09-25, 28, 29, 30 and 2026-10-01 (one each of present, absent, late, half day, leave); grant Student `student_attendance:read_own` and `list_own` first (the test grants and restores them) | 1. Sign in as the QA student.<br>2. Open Students > Attendance.<br>3. Set "From" to 2026-09-25 and "To" to 2026-10-01. | Page "My Attendance", card "Filter by Date" with "From" and "To"; tiles Total Days, Present, Absent, Late, Half Day, Leave with Total Days 5 (the five days created for the test); list "Attendance Records" newest first with date and status | passing |
| TC-STU-13-E02 | P3 | Web | Student | Seeded student login 004 | 1. Open Students > Attendance.<br>2. Set "From" to a date after "To". | No crash; the list shows "No attendance records found for the selected period." (the API answers 400) | planned |
| TC-STU-13-E03 | P2 | Web | Parent | Seeded parent login venkat.raju@example.com (Harsha and Tanvi Raju, seeded attendance) | 1. Sign in as venkat.raju@example.com and set From 2026-09-25, To 2026-10-01.<br>2. Open Students > Attendance.<br>3. Switch the header child selector to the other child. | The list title changes from "Harsha Raju's Attendance" to "Tanvi Raju's Attendance" and the records follow the selected child | planned |
| TC-STU-13-E04 | P3 | Web | Parent | QA Parent login (unlinked) | 1. Sign in with the QA Parent login (unlinked).<br>2. Open Students > Attendance. | "Children's Attendance" with "No child selected. Use the child switcher in the header above." and "No attendance records found for the selected period." (verified 2026-10-07) | planned |
| TC-STU-13-E05 | P2 | Mobile | Parent | Seeded parent login venkat.raju@example.com, Harsha Raju selected | 1. Sign in as venkat.raju@example.com on mobile.<br>2. Open Students > Attendance.<br>3. Choose September 2026 in "Select Month". | Title "Harsha Raju's Attendance", month tiles and the line "<n>% attendance" (green at 75 or more, red below) | planned |
| TC-STU-13-E06 | P2 | Mobile | Student | Seeded student login 004 (seeded attendance) | 1. Sign in with the seeded student login 004 on mobile.<br>2. Open Students > Attendance. | "Filter by Date" with From and To, tiles including "Total Days" and "Half Day", and "Attendance Records" | planned |
| TC-STU-13-E07 | P2 | Web | Admin | TC-STU-11-E01 and TC-STU-12-E01 done | 1. Sign in as Admin.<br>2. Open Students > Attendance and load Class 1 / 1-B for today. | Saved statuses are shown (Harsha Raju Present after TC-STU-12-E01, Advik Mehta Late); the analysis tiles and "<n>% Present" match them | planned |
| TC-STU-13-E08 | P3 | Mobile | Parent | QA Parent login (unlinked) | 1. Sign in with the QA Parent login (unlinked) on mobile.<br>2. Open Students > Attendance. | "Please select a student from the header" | planned |
| TC-STU-13-E09 | P3 | Web | Student | Seeded student login 004; browser timezone IST (UTC+05:30) | 1. Sign in with the seeded student login 004.<br>2. Open Students > Attendance.<br>3. Read the default "From" date. | "From" shows the first day of the current month | blocked: Known gap 23 (From shows the last day of the previous month in IST) |

API tests implemented in: backend/tests/api/students/test_attendance.py

---

## F14 Upload and replace a student document

**Purpose.** Store a document (birth certificate, Aadhar card, etc.) against a student.

**Roles and permissions.** `POST /students/documents/` and `PATCH /students/documents/{id}`: `student_documents:create` / `update` (Admin, Staff). Teacher, Student, Parent get 403 under the default catalog (the Student role has no `create`, so the web "My Documents" upload button fails with 403).

**Preconditions.** Student exists.

**Steps, web.**
1. Open `/students/documentsupload` ("Document Upload"; not in the default menu). The section "Upload New Document" (collapsible) needs `student_documents:create`.
2. Choose "Student *" (picker "Select student"), "Document Type *" (picker "Select document type"; empty because `GET /students/document-types/` is 404), "Browse File *" (Browse; accepts .pdf .jpg .jpeg .png .doc .docx).
3. Click "Upload Document" (label "Uploading...") or "Reset". Success toast "Document uploaded successfully!". Missing fields: toast "Please fill all required fields and select a file".
4. Below, "Uploaded Documents" shows "Select a student above to view their documents" until a student is chosen, then the list or "No documents found for this student". A Teacher sees only this list (no upload card); a Parent gets "Access Denied" "You don't have permission to view student documents.".
5. Students own variant: `/students/mydocuments` "My Documents" with an "Upload Document" header button that opens "Upload New Document" with "Document Type" and "File" (toast "Please select a file and document type" when either is missing). Non-student roles opening this URL see "Loading your documents..." that never ends.

**Steps, mobile.** `documentupload.tsx` ("Upload Document"; guard create or update): "Tap to select document file" (PDF, JPG, PNG only, 5 MB max, messages "File size must be less than 5MB" and "Only PDF, JPG, and PNG files are allowed"), "Document Name *" ("Enter document name"), "Document Type *" chips (Certificate, Medical, Identification, Academic, Other), "Upload Document". Missing file: "Please select a document file"; missing name or type: "Please fill in all required fields". `mydocuments.tsx`: "Upload New Document" modal (type placeholder "e.g. Birth Certificate, ID Proof..."; "Please enter a document type and select a file"). `documents.tsx` (admin, "Documents" with "Filter by Student" "All Students"): calls `GET /students/documents/` without `student_id` (422) and shows "Select a student to view documents"; its type buttons are a stub that only shows "File picker integration needed for device files".

**Expected results.** 201 `StudentDocumentOut {id, student_id, document_type, file_path, upload_date}`. The file is stored as `student_documents/<uuid>.<ext>` relative to the server working directory (not tenant-scoped, not served).

**API endpoints.**
- `POST /students/documents/` multipart `student_id`, `document_type`, `document_file`.
- `PATCH /students/documents/{document_id}` multipart `document_type`, `document_file` (replaces the file; the old file is deleted after commit).

**Rules and validations.**
- Extension in `.pdf .jpg .jpeg .png .docx`; MIME type in `application/pdf`, `image/jpeg`, `image/png`, DOCX type; filename max 255 and no `..`, `/` or `\`; not empty; max 5 MB (5,242,880 bytes allowed, one byte more rejected); `.pdf` must start with `%PDF`. All failures are 400 (validation errors).
- `document_type` is free text, required, unique per student (422 "Document of type '<t>' already exists for this student"). PATCH does not re-check uniqueness and requires both fields again.
- Unknown student 404 "Student not found".
- The web document type dropdown reads `GET /students/document-types/` which does not exist, so it is empty and web upload cannot be completed; mobile hard-codes a type list (Known gaps).

**Error and edge cases.** `.doc` is offered by the web picker but rejected by the API. Duplicate type must be replaced via PATCH or deleted first.

**Unit-testable logic.** The validation chain in `upload_document` / `update_document_file` with a fake `UploadFile`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-14-U01 | Extension check for pdf, jpg, jpeg, png, docx (any case), doc, exe, none | First five accepted; others rejected | passing |
| TC-STU-14-U02 | Filename safety for "a/b.pdf", "a\\b.pdf", "..x.pdf", a 256 character name | All rejected | passing |
| TC-STU-14-U03 | Size boundary 5,242,880 and 5,242,881 bytes; empty file | Accepted; rejected "File too large"; rejected "Empty file not allowed" | passing |
| TC-STU-14-U04 | PDF magic bytes: content "%PDF-1.4" vs "hello" with .pdf name | Accepted; "Invalid PDF file format" | passing |
| TC-STU-14-U05 | Content type "text/plain" with a .pdf name | Rejected "Invalid file type" | passing |
| TC-STU-14-A01 | Admin uploads a small PDF with `document_type` "Birth Certificate" | 201 with id, student_id, document_type, file_path `student_documents/<uuid>.pdf`, upload_date | passing |
| TC-STU-14-A02 | Upload JPG, PNG and DOCX | 201 each | passing |
| TC-STU-14-A03 | Upload `.doc`, `.txt`, a 5 MB + 1 byte file, a fake PDF, an empty file | 400 each with the matching message | skipped: size boundary needs a 5 MB file; |
| TC-STU-14-A04 | Upload the same `document_type` twice for one student; same type for another student | 422 "already exists for this student"; 201 | passing |
| TC-STU-14-A05 | Missing `document_type` or blank "   "; missing file | 422 (required form field) or 400 "Document type is required"; 422 | passing |
| TC-STU-14-A06 | Unknown `student_id` | 404 "Student not found" | passing |
| TC-STU-14-A07 | PATCH with a new file and a new type | 200; new `file_path`; old file deleted from disk | passing |
| TC-STU-14-A08 | PATCH unknown id | 404 "Document not found" | passing |
| TC-STU-14-A09 | Upload permission matrix | Admin 201, Staff 201, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-14-A10 | PATCH permission matrix | Admin 200, Staff 200, Teacher 403, Student 403, Parent 403 | passing |
| TC-STU-14-A11 | No token on both endpoints | 401 | passing |
| TC-STU-14-A12 | Tenant isolation: tenant B Admin uploads for a tenant A student; token A with B header | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-14-E01 | P2 | Web | Admin | TC-STU-03-E01 done; a small PDF | 1. Sign in as Admin.<br>2. Open /students/documentsupload.<br>3. Under "Upload New Document" choose Student "QA Asha Rao".<br>4. Open "Document Type *" and pick a type.<br>5. Click "Browse" and choose the PDF.<br>6. Click "Upload Document". | Toast "Document uploaded successfully!"; the document appears under "Uploaded Documents" for QA Asha Rao | blocked: Known gap 7 (document type list is empty: GET /students/document-types/ is 404) |
| TC-STU-14-E02 | P3 | Web | Admin | QA Admin login | 1. Open /students/documentsupload.<br>2. Click "Upload Document" without choosing anything. | Toast "Please fill all required fields and select a file"; nothing is uploaded | planned |
| TC-STU-14-E03 | P2 | Web | Staff, Teacher | QA Staff and QA Teacher logins | 1. Sign in as Staff and open /students/documentsupload.<br>2. Sign in as Teacher and open /students/documentsupload. | Staff sees the "Upload New Document" card and "Uploaded Documents"; Teacher sees only "Uploaded Documents" ("Select a student above to view their documents") | planned |
| TC-STU-14-E04 | P3 | Mobile | Staff | A 6 MB PDF on the device | 1. Sign in as Staff on mobile.<br>2. Open /students/documentupload ("Upload Document").<br>3. Tap "Tap to select document file" and pick the 6 MB PDF. | Toast "File size must be less than 5MB"; no file is selected | planned |
| TC-STU-14-E05 | P3 | Mobile | Staff | A .docx file on the device | 1. Open "Upload Document" on mobile.<br>2. Tap "Tap to select document file" and pick the .docx. | Toast "Only PDF, JPG, and PNG files are allowed" | planned |
| TC-STU-14-E06 | P3 | Mobile | Student | Seeded student login 004; a small PDF on the device | 1. Sign in with the seeded student login 004 on mobile.<br>2. Open My Documents and tap "Upload New Document".<br>3. Enter type "QA Birth Certificate", pick the PDF and tap "Upload Document". | The upload is refused (403: the Student role has no student_documents:create) and an error toast is shown; nothing is stored | planned |
| TC-STU-14-E07 | P3 | Mobile | Staff | QA Staff login; a small PDF | 1. Open "Upload Document" on mobile.<br>2. Pick the PDF.<br>3. Leave "Document Name *" empty and tap "Upload Document". | Toast "Please fill in all required fields" | planned |
| TC-STU-14-E08 | P3 | Web | Parent | Seeded parent login venkat.raju@example.com | 1. Sign in as venkat.raju@example.com.<br>2. Open /students/documentsupload. | "Access Denied" with "You don't have permission to view student documents." (verified 2026-10-07) | planned |

API tests implemented in: backend/tests/api/students/test_documents.py

Implemented in: backend/tests/unit/student/test_student_documents.py.

---

## F15 List student documents and the merged documents view

**Purpose.** See a student's uploaded documents, or one merged list of documents, certificates and fee receipts.

**Roles and permissions.** `GET /students/documents/`, `/all` need exact `student_documents:list`; `GET /students/documents/{id}` needs `read` (Admin, Staff, Teacher). Student and Parent hold only `list_own`/`list_related`, so they get 403 under the default catalog even though the web page `/students/studentdocuments` is in their menu (Known gaps). Student and Parent are restricted to their own record or linked children even when granted `list`/`read` (fixed 2026-10-02).

**Preconditions.** Documents, certificates or receipts exist.

**Steps, web.** Students > Student Documents (`/students/studentdocuments`, page "Student Documents"):
- Staff view (Admin, Staff, Teacher): "Student" picker ("Select a student") and "Clear"; table "Source | Name / Type | Date" with source badges "Document", "Certificate", "Receipt". Before a choice: "Please select a student to view their documents."; empty: "No documents found for this student." and "Documents uploaded for the selected student will appear here.".
- Student view: card title "Documents - <name> (<admission no> . <class - section>)" (card "My Documents" while loading), table "S.No. | Source | Name / Type | Date", empty text "No documents found." and "Documents issued to you will appear here.". Under the default catalog `/all` answers 403 and the card stays on "Loading documents..." (Known gaps). A Student login without a student record sees "No student record is linked to your account." only when the store has no student id.
- Parent view: "Documents" for the selected child; "No children linked to your account." when none.
- `/students/documentsupload` lists "Uploaded Documents" for a chosen student with row actions "View Document", "Verify Document", "Delete".

**Steps, mobile.** Students > Student Documents (`studentdocuments.tsx`): card "Select Student" with dropdown "Student" ("Select a student") and "Clear", "Please select a student to view their documents." before a choice, cards with a source badge and "View" for uploaded documents. A Parent without a selected child sees "Select a student from the header". `parents/documents.tsx` ("Documents") lists the child's certificates, "No child selected." with "Select a child" otherwise. `mydocuments.tsx` lists a student's own documents ("No Documents Found", "Documents issued to you will appear here.").

**Expected results.** `/all` returns documents (source `document`), certificates received and issued (source `certificate`, with `type_name` and `certificate_category`) and fee receipts (source `receipt`, with `receipt_number`), newest first by `upload_date`.

**API endpoints.**
- `GET /students/documents/?student_id=` (required) returns `list[StudentDocumentOut]`.
- `GET /students/documents/all?student_id=` returns `list[UnifiedDocumentItem]`.
- `GET /students/documents/{document_id}` returns one document.

**Rules and validations.** `student_id` is required (422 when missing; the mobile admin list calls it without an id when "All Students" is chosen, so it fails). Unknown student 404. Sorting by `upload_date` descending.

**Error and edge cases.** Web document "View" builds `<API origin><file_path>`; the file is not served, so it opens a broken URL (F16).

**Unit-testable logic.** Unified list construction and sort: label rules (`type_name` or "Issued Certificate"/"Received Document"), source mapping.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-15-U01 | Unified list build with 1 document, 1 issued certificate without type, 1 receipt, differing dates | 3 items sorted by date descending; certificate label "Issued Certificate" when type missing | passing |
| TC-STU-15-A01 | Admin `GET /` for a student with 2 documents | 200 two items | passing |
| TC-STU-15-A02 | `GET /` without `student_id`; unknown student; malformed id | 422; 404; 422 | passing |
| TC-STU-15-A03 | `GET /all` for a student with a document, a received and an issued certificate and a receipt | 4 items with sources document, certificate x2, receipt; `certificate_category` set on certificates; `receipt_number` on the receipt | skipped: blocked: the receipt source needs a fee payment, which belongs to FEE fixtures |
| TC-STU-15-A04 | `GET /{id}` and unknown id | 200; 404 "Document not found" | passing |
| TC-STU-15-A05 | Permission matrix for `/`, `/all`, `/{id}` | Admin, Staff, Teacher 200; Student 403; Parent 403 | passing |
| TC-STU-15-A06 | Teacher requests another class's student | 200 (no scoping, documented) | passing |
| TC-STU-15-A07 | No token | 401 | passing |
| TC-STU-15-A08 | Tenant isolation: tenant B Admin lists a tenant A student; token A with B header | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-15-E01 | P1 | Web | Admin | Seeded student Karthik Reddy (001) with the uploaded document "Aadhaar Card" | 1. Sign in as Admin.<br>2. Open Students > Student Documents.<br>3. Choose "Karthik Reddy" in "Select a student". | Table "Source, Name / Type, Date" lists "Aadhaar Card" with the badge "Document" and its date (plus any certificate or receipt rows); "Clear" resets the picker to "Please select a student to view their documents." | passing |
| TC-STU-15-E02 | P2 | Web | Student | Seeded student login 001 (Karthik Reddy, document Aadhaar Card) | 1. Sign in with the seeded student login 001.<br>2. Open Students > Student Documents. | Card "Documents - Karthik Reddy (001 . Class 3 - 3-B)" with the student's rows | blocked: Known gap 8 and 23 (documents/all answers 403 for the Student role and the card stays on "Loading documents...") |
| TC-STU-15-E03 | P2 | Web | Parent | Seeded parent login prakash.reddy@example.com (Ananya Reddy with Birth Certificate, Karthik Reddy with Aadhaar Card) | 1. Sign in as prakash.reddy@example.com.<br>2. Open Students > Student Documents.<br>3. Switch the header child selector to the other child. | The "Documents" list refreshes for the selected child; no rows of the other child remain | blocked: Known gap 8 (documents/all needs the exact list grant; Parent holds list_related) |
| TC-STU-15-E04 | P3 | Web | Parent | QA Parent login (unlinked) | 1. Sign in with the QA Parent login (unlinked).<br>2. Open Students > Student Documents. | "No children linked to your account." (verified 2026-10-07) | planned |
| TC-STU-15-E05 | P2 | Mobile | Admin | Seeded student Karthik Reddy (001, document Aadhaar Card) | 1. Sign in as Admin on mobile.<br>2. Open Students > Student Documents.<br>3. Choose "Karthik Reddy" in "Student". | Cards with a source badge for each item; uploaded documents show "View" and a download icon | planned |

API tests implemented in: backend/tests/api/students/test_documents.py

Implemented in: backend/tests/unit/student/test_student_documents.py.

---

## F16 Delete and download a student document

**Purpose.** Remove a document, or open its file.

**Roles and permissions.** `DELETE /students/documents/{id}` needs `student_documents:delete` (Admin only). There is no download endpoint.

**Preconditions.** Document exists.

**Steps, web.** `/students/documentsupload`, select the student, row icon "Delete" (shown only with `student_documents:delete`; dialog "Delete Document?" "Are you sure you want to delete this document? This action cannot be undone." > "Cancel" or "Delete"). Toast "Document deleted successfully!". Row icon "View Document" opens `<API origin><file_path>`; "Verify Document" (dialog "Verify Document", field "Remarks (optional)", button "Verify") calls a missing endpoint (toast "Failed to verify document").

**Steps, mobile.** `studentdocuments.tsx` ("View" and the download icon) and `mydocuments.tsx` (eye and "Download" icons) read `/students/documents/{id}/download`, which does not exist; the error toast is "Failed to download document" or "Failed to process document".

**Expected results.** Delete returns 204 and removes the row, then the file on disk (a failed file removal is only logged).

**API endpoints.** `DELETE /students/documents/{document_id}` returns 204.

**Rules and validations.** Unknown id 404 "Document not found". Missing endpoints used by clients: `GET /students/documents/{id}/download`, `POST /students/documents/{id}/verify`, `/students/document-types/` (all 404).

**Error and edge cases.** Files live in `./student_documents/` which is not mounted, so even a valid path cannot be opened; there is no verification state in the backend.

**Unit-testable logic.** Delete order (DB first, then file) and tolerant file removal.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-16-U01 | Delete with a missing file on disk | Row deleted, no exception (warning only) | passing |
| TC-STU-16-A01 | Admin deletes an existing document | 204; list no longer contains it; file removed | passing |
| TC-STU-16-A02 | Delete unknown id | 404 "Document not found" | passing |
| TC-STU-16-A03 | Delete permission matrix | Admin 204; Staff 403; Teacher 403; Student 403; Parent 403 | passing |
| TC-STU-16-A04 | `GET /students/documents/{id}/download`, `POST /{id}/verify`, `GET /students/document-types/` | 404 / 404 / 404 (documented missing endpoints) | passing |
| TC-STU-16-A05 | No token | 401 | passing |
| TC-STU-16-A06 | Tenant isolation: tenant B Admin deletes a tenant A document; token A with B header | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-16-E01 | P2 | Web | Admin | TC-STU-03-E01 done; a document "QA Doc" uploaded for "QA Asha Rao" through the API (POST /students/documents/); never delete the seeded documents | 1. Sign in as Admin.<br>2. Open /students/documentsupload and choose Student "QA Asha Rao".<br>3. Click "Delete" on the row.<br>4. Click "Delete" in the dialog. | Dialog "Delete Document?" with "Are you sure you want to delete this document? This action cannot be undone."; toast "Document deleted successfully!"; the row disappears | planned |
| TC-STU-16-E02 | P2 | Web | Staff | Seeded document Aadhaar Card of Karthik Reddy (001) | 1. Sign in as Staff.<br>2. Open /students/documentsupload and choose "Karthik Reddy". | The row shows "View Document" and "Verify Document" but no "Delete" icon | planned |
| TC-STU-16-E03 | P3 | Web | Admin | Seeded document Aadhaar Card of Karthik Reddy (001) | 1. Open /students/documentsupload and choose "Karthik Reddy".<br>2. Click "View Document". | The file opens in a new tab | blocked: Known gap 7 (files under ./student_documents are not served; the link is broken) |
| TC-STU-16-E04 | P3 | Mobile | Admin | Seeded document Aadhaar Card of Karthik Reddy (001) | 1. Sign in as Admin on mobile.<br>2. Open Students > Student Documents and choose "Karthik Reddy".<br>3. Tap "View" on the document card. | The file opens | blocked: Known gap 7 (GET /students/documents/{id}/download does not exist; toast "Failed to download document" or "Failed to process document") |

API tests implemented in: backend/tests/api/students/test_documents.py

Implemented in: backend/tests/unit/student/test_student_documents.py.

---

## F17 Student own admission view and parent child admission view

**Purpose.** Let a student see their own admission record and a parent see their children's.

**Roles and permissions.** `GET /students/admission/my-admission` needs `student_admissions:read_own` (Student only; every other role gets 403). `GET /students/admission/my-children-admissions` needs `read_related` (Parent only) and a linked child (else 400). The web page `/students/admission` uses `GET /students/admission/id/{student_id}` (F07) for the selected child. Menu: Students > Admission.

**Preconditions.** A student or parent with an admission or linked child.

**Steps, web.** Student: Students > Admission ("Student Admissions") shows the admission table with a single row and a "View Admission" action (no "New Admission", "Bulk Upload", edit or toggle controls); a Student login without a student record sees "No data". Parent: Students > Admission shows a card "Admission - <child> (#<number>)" with the detail table for the child selected in the header ("Loading admission details..." while loading); "No children linked to your account." or "No child selected. Use the child switcher in the header above." otherwise.

**Steps, mobile.** `myadmission.tsx`: Student (title "My Admission") sees their record in collapsible sections starting with "Admission Details" ("No admission record found." without a student record); Parent (title "Admission") sees the selected child's record (sections for admission, student, parents, address), "Select a child" when none is selected and "No children linked to your account." when no child is linked. Admin, Staff and Teacher get "Access Denied" (title "Admissions").

**Expected results.** Student sees only their own record; Parent only linked children.

**API endpoints.**
- `GET /students/admission/my-admission` returns the caller's admission (400 "Only students can access this endpoint" when no student id).
- `GET /students/admission/my-children-admissions?skip&limit` returns `{items, total_count, has_next, ...}` for linked children (400 "Only parents with children can access this endpoint" otherwise).

**Rules and validations.** Admin, Staff and Teacher cannot call `my-admission` (no `read_own`). `skip >= 0`, `limit` 1..100.

**Error and edge cases.** Parent with no children 400; student without an admission 404.

**Unit-testable logic.** Role detection helpers; scope resolution (`own`, `related`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-17-U01 | Scope resolution for Student (read_own), Parent (read_related), Admin (read) | own, related, all | passing |
| TC-STU-17-A01 | Student `GET my-admission` | 200 own record only | passing |
| TC-STU-17-A02 | Admin, Staff, Teacher, Parent `GET my-admission` | 403 each | passing |
| TC-STU-17-A03 | Parent with two children `GET my-children-admissions` | 200 `items` has exactly the two children; `total_count` 2 | passing |
| TC-STU-17-A04 | Parent with no linked child | 400 "Only parents with children can access this endpoint" | passing |
| TC-STU-17-A05 | Student, Admin, Staff, Teacher `GET my-children-admissions` | 403 each | passing |
| TC-STU-17-A06 | `limit=0` / `limit=101` on my-children-admissions | 422 | passing |
| TC-STU-17-A07 | No token | 401 | passing |
| TC-STU-17-A08 | Tenant isolation: tenant A student token with tenant B header | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-17-E01 | P1 | Web | Student | A student created through the API for the test (QA name, own QA class) that has completed first login; grant Student `student_admissions:read_own` and `list_own` first (the test grants and restores them) | 1. Sign in as the QA student.<br>2. Open Students > Admission.<br>3. Click "View Admission". | One row (the QA student); the dialog "Admission Details - <number>" shows the own record; no "New Admission", "Bulk Upload", "Edit Admission" or toggle icons | passing |
| TC-STU-17-E02 | P2 | Web | Parent | Seeded parent login venkat.raju@example.com | 1. Sign in as venkat.raju@example.com.<br>2. Open Students > Admission.<br>3. Switch the header child selector to the other child. | Card "Admission - <child> (#<number>)" with the detail table of the selected child ("Admission - Harsha Raju (#004)"); after the switch the card shows the other child | planned |
| TC-STU-17-E03 | P2 | Mobile | Student | Seeded student login 004 | 1. Sign in with the seeded student login 004 on mobile.<br>2. Open /students/myadmission. | Screen "My Admission" with the own record in collapsible sections, the first one "Admission Details" open | planned |
| TC-STU-17-E04 | P2 | Mobile | Parent | Seeded parent login venkat.raju@example.com; QA Parent login (unlinked) | 1. Sign in as venkat.raju@example.com on mobile, select Harsha Raju and open /students/myadmission.<br>2. Sign in with the QA Parent login (unlinked) and open /students/myadmission. | Step 1: screen "Admission" with the selected child's record; step 2: "No children linked to your account." (verified 2026-10-07) | planned |
| TC-STU-17-E05 | P3 | Mobile | Admin | QA Admin login | 1. Sign in as Admin on mobile.<br>2. Open /students/myadmission. | "Access Denied" "You don't have permission to view this screen. Please contact your administrator." (verified 2026-10-07) | planned |

API tests implemented in: backend/tests/api/students/test_admission_read.py

Implemented in: backend/tests/unit/student/test_student_misc_services.py (UserContextService._determine_access_scope with a patched permission check).

---

## F18 Student profile

**Purpose.** A student reads their profile and updates their email.

**Roles and permissions.** `GET /profile/student/me` needs `profile:read_own`; `PUT /profile/student/me` needs `profile:update_own` (Student role). Route `/students/profile` (not in the default menu).

**Preconditions.** Logged in as a Student with a student record.

**Steps, web.** Open `/students/profile` ("Student Profile"): cards "Personal Information" (First Name, Last Name, Phone, Date of Birth, Address, Emergency Contact, Blood Group, Email) and "Academic Information" (Admission Number, Roll Number, Class, Section, Academic Year). Click "Edit Email", change "Email" (required, pattern, message "Invalid email address"), "Update" ("Updating...") or "Cancel". A Student without a student record sees "Error loading profile: Student profile not found"; Admin, Staff, Teacher and Parent opening the URL see "Loading student profile..." that never ends.

**Steps, mobile.** `profile.tsx` ("Student Profile"): "Personal Information", "Academic Information", "Address", button to edit with fields "Email", "Phone", "Address" (title "Edit Profile"; failure toast "Failed to update profile"). Without a student: "No profile data available" "Please select a student to view profile" (Parent: title "Child Profile" and "Select a student from the header"). A Parent viewing a child requests `/students/profile/<id>`, which does not exist.

**Expected results.** The backend returns `{student_id, user_id, first_name, last_name, date_of_birth, gender, email, admission_number, class_name, section_name, is_active, profile_photo_url (always null), attendance_percentage, total_certificates, total_documents}`. Only `email` is stored on update (`users.email`); the web and mobile also show fields the API does not return (phone, address, blood group, roll number, academic year) as "N/A".

**API endpoints.** `GET /profile/student/me`; `PUT /profile/student/me` body `{email}`.

**Rules and validations.** `attendance_percentage` = round((present + 0.5 x half_day) / total x 100, 2) over the student's attendance rows (status compared case-insensitively), and null when there are none. Email has no format or uniqueness check on the API.

**Error and edge cases.** A non-student role gets 403 (no `profile:read_own`) or 404 "Student profile not found" when the user has no student row.

**Unit-testable logic.** Percentage calculation (with status case), counts of certificates and documents.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-18-U01 | Percentage with statuses ["present","present","absent"] (lowercase) | 66.67; with a half_day row it counts as 0.5 | passing |
| TC-STU-18-U02 | Percentage with no attendance rows | None | passing |
| TC-STU-18-A01 | Student `GET /profile/student/me` | 200 with the documented fields, `class_name` and `section_name` resolved, `total_certificates` and `total_documents` counts | passing |
| TC-STU-18-A02 | Student with 3 present and 1 absent rows | `attendance_percentage` 75.0 | passing |
| TC-STU-18-A03 | Student `PUT` with a new email | 200; `GET` returns the new email | passing |
| TC-STU-18-A04 | `PUT` with `{}` and with an invalid email string "abc" | 200 unchanged; 200 stored (no validation, documented) | passing |
| TC-STU-18-A05 | Admin, Staff, Teacher, Parent `GET` and `PUT` | 404 `Student profile not found` each (every role holds `profile:read_own` and `update_own`; only a user with a student record gets a profile) | passing |
| TC-STU-18-A06 | No token | 401 | passing |
| TC-STU-18-A07 | Tenant isolation: token A with header B | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-18-E01 | P1 | Web | Student | A student created through the API for the test (QA name, own QA class) that has completed first login | 1. Sign in as the QA student.<br>2. Open /students/profile. | "Student Profile" with cards "Personal Information" (First Name, Last Name, Email and others) and "Academic Information" (the QA student's Admission Number, Class and Section); fields the API does not return show "N/A" | passing |
| TC-STU-18-E02 | P3 | Web | Student | Seeded student login 004 | 1. Open /students/profile.<br>2. Click "Edit Email".<br>3. Enter "abc" and click "Update". | Inline "Invalid email address"; the dialog stays open; nothing is saved | planned |
| TC-STU-18-E03 | P2 | Web | Student | QA Student login (TC-STU-03-E01 done; do not change a seeded student's email) | 1. Open /students/profile and click "Edit Email".<br>2. Enter "qa.asha@example.com" and click "Update". | The dialog closes; the Email row shows "qa.asha@example.com" | planned |
| TC-STU-18-E04 | P3 | Mobile | Student | QA Student login (TC-STU-03-E01 done) | 1. Sign in with the QA Student login on mobile.<br>2. Open /students/profile and tap "Edit Profile".<br>3. Change Email to "qa.asha2@example.com", Phone to "9000000009", Address to "QA Road 2" and save.<br>4. Reopen the profile. | The request sends the three fields; only the email changes (the API stores only users.email) | planned |
| TC-STU-18-E05 | P3 | Web | Admin, Student | QA Admin login; QA Student login (unlinked) | 1. Sign in with the QA Student login (unlinked) and open /students/profile.<br>2. Sign in as Admin and open /students/profile. | Step 1: "Error loading profile: Student profile not found"; step 2: an error or "not a student" message instead of an endless spinner | blocked: Known gap 23 (Admin, Staff, Teacher and Parent stay on "Loading student profile...") |

API tests implemented in: backend/tests/api/students/test_profile_links.py

Implemented in: backend/tests/unit/student/test_student_misc_services.py. The xfail(strict) test asserts the target 66.67; a second test asserts the current 0.0.

---

## F19 Parent child selection

**Purpose.** A parent chooses which child the web and mobile pages show.

**Roles and permissions.** `GET /student-parent-links/my-children` is callable by role `Parent` only (no permission row). Header selector shown only for Parent.

**Preconditions.** Parent linked to one or more children (F04, F20).

**Steps, web.** After login the first child is selected. The header selector "Select student..." (hidden below the md breakpoint) is a searchable list (box "Search students...", name or admission number) of children; picking one sets `selectedStudent` and `studentId`. Pages that follow it: Admission, Attendance ("Children's Attendance"), Student Documents, Student Certificates and the fee pages. The Student Transport page ("Children's Transport") does not use the header selector; it has its own "Select Child" card with a "Child" dropdown.

**Steps, mobile.** `parents/select-child.tsx` ("Select Child", hint "Select which child you want to view information for."): tap a card (name, class - section, admission number); `router.back()` follows. Empty state "No children linked to your account."

**Expected results.** Every parent-facing request carries the selected child's id as a path or query parameter; the backend scopes by that id plus the related-scope check. The `X-Student-ID` header is sent but ignored by the backend.

**API endpoints.** `GET /student-parent-links/my-children` returns `[{id, first_name, last_name, name, is_active, date_of_birth, gender, admission_number, academic_year_id, academic_year, class_id, class_name, section_id, section_name}]` ordered by first and last name, one row per child (latest admission). 403 "Only parents can access this endpoint" for other roles; 404 "Parent profile not found".

**Rules and validations.** Active status comes from the student's user. Class and section come from the **current** class and section of the latest admission.

**Error and edge cases.** A parent with no child gets `[]`; the web shows "No children linked to your account.". Switching the child must not leak the previous child's data (queries are keyed by student id).

**Unit-testable logic.** Mapping of `my-children` items to the client `Student` shape; `selectStudent` store action.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-19-U01 | Web `fetchMyChildren` mapping for an item with name "Asha Rao" and no first_name | first_name "Asha", last_name "Rao" | blocked: fetchMyChildren is not exported from web src/api/auth.ts |
| TC-STU-19-U02 | `selectStudent(child2)` store action | `selectedStudent` and `studentId` equal child2 | passing |
| TC-STU-19-A01 | Parent with 2 children `GET my-children` | 200, 2 rows ordered by name, with class_name and section_name | passing |
| TC-STU-19-A02 | Child with two admissions | One row per student with the latest admission | skipped: blocked: the API cannot create a second admission for an existing student |
| TC-STU-19-A03 | Deactivated child | Row present with `is_active` false | passing |
| TC-STU-19-A04 | Parent with no children | 200 `[]` | passing |
| TC-STU-19-A05 | Admin, Staff, Teacher, Student `GET my-children` | 403 "Only parents can access this endpoint" | passing |
| TC-STU-19-A06 | Parent without a `parents` row | 404 "Parent profile not found" | passing |
| TC-STU-19-A07 | No token | 401 | passing |
| TC-STU-19-A08 | Isolation between parents: parent P1's children are not returned for P2; tenant B token | Only own children; 403 for tenant mismatch | passing |
| TC-STU-19-A09 | Effects: parent with children C1 and C2 calls `GET admission/id/{C1}` (200) and `GET admission/id/{other child}` (404) | Scope follows links | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-19-E01 | P1 | Web | Parent | A parent created through the API for the test (QA name, one QA child in an own QA class) that has completed first login; grant Parent `student_attendance:read_related` and `list_related` first (the test grants and restores them) | 1. Sign in as the QA parent (login = the father email).<br>2. Look at the header selector.<br>3. Open Students > Attendance. | The header selector shows the QA child; the page heading is "Children's Attendance" and the list is titled "<child name>'s Attendance" | passing |
| TC-STU-19-E02 | P2 | Web | Parent | Seeded parent login venkat.raju@example.com | 1. Open the header selector.<br>2. Type "005" in "Search students...".<br>3. Click "Tanvi Raju". | The list narrows by admission number; Tanvi Raju becomes the selected child | planned |
| TC-STU-19-E03 | P2 | Web | Parent | TC-STU-19-E02 done (Tanvi Raju selected); seeded data for both children | 1. Open Students > Admission, Attendance, Student Documents and Student Certificates in turn. | Every page shows Tanvi Raju's data (Class 4 / 4-B, admission 005) and nothing of Harsha Raju | planned |
| TC-STU-19-E04 | P3 | Web | Parent | Seeded parent login satish.mehta@example.com (only child Advik Mehta) | 1. Sign in as satish.mehta@example.com.<br>2. Look at the header. | The selector is shown with Advik Mehta preselected | planned |
| TC-STU-19-E05 | P2 | Mobile | Parent | Seeded parent login venkat.raju@example.com | 1. Sign in as venkat.raju@example.com on mobile.<br>2. Open /parents/select-child ("Select Child").<br>3. Tap the card of Tanvi Raju.<br>4. Open Students > Attendance. | "Select which child you want to view information for." with one card per child (name, class - section, admission number); tapping returns to the previous screen; Attendance shows "Tanvi Raju's Attendance" | planned |
| TC-STU-19-E06 | P3 | Mobile | Parent | QA Parent login (unlinked) | 1. Sign in with the QA Parent login (unlinked) on mobile.<br>2. Open /parents/select-child. | "No children linked to your account." (verified 2026-10-07) | planned |
| TC-STU-19-E07 | P3 | Web | Parent | Seeded parent login venkat.raju@example.com; QA Parent login (unlinked) | 1. Sign in as venkat.raju@example.com and open /students/studenttransport.<br>2. Sign in with the QA Parent login (unlinked) and open the same URL. | Step 1: "Children's Transport" with its own "Select Child" card and a "Child" dropdown defaulting to Harsha Raju, independent of the header selector; step 2: "No children found for this account." | blocked: Known gap 23 (a parent without a parent record sees "Session outdated. Please log out and log back in." instead) |

API tests implemented in: backend/tests/api/students/test_profile_links.py

Implemented in: web/src/__tests__/students/parentChildSelection.test.ts (U02).

---

## F20 Student-parent links (admin API)

**Purpose.** Inspect and manage which parents are linked to which students.

**Roles and permissions.** Resource `parent_management`: create (Admin, Staff), delete (Admin), read (Admin, Staff), list (Admin, Staff). `GET /student-parent-links/parent/{parent_id}/students` lets a Parent read only their own children; other roles need `parent_management:read`. No screen calls most of these endpoints (the web parents master calls two wrong paths; see Known gaps).

**Preconditions.** A student and a parent (parents are created only through admission).

**Steps, web and mobile.** No UI. Links are created by admission (F03, F04). The Masters > Parents page lists parents (`GET /parents/`, owned by Masters) and cannot create them.

**Expected results.** Links connect `students` and `parents` (unique pair).

**API endpoints.**
- `POST /student-parent-links/` body `{student_id, parent_id}` returns 201 `{id, student_id, parent_id}`.
- `DELETE /student-parent-links/student/{student_id}/parent/{parent_id}` returns 204.
- `GET /student-parent-links/student/{student_id}/parents` returns `list[ParentOut]` (permission `parent_management:read`, so Student and Parent get 403).
- `GET /student-parent-links/parent/{parent_id}/students` returns `list[StudentOut]`.
- `GET /student-parent-links/` returns all links.
- `GET /student-parent-links/my-children` (F19).

**Rules and validations.** Duplicate link 400 "Student-parent link already exists"; unknown student 404 "Student not found"; unknown parent 404 "Parent not found"; unlink of a missing pair 404 "Student-parent link not found". A Parent requesting another parent's id gets 403 "You can only view your own children".

**Error and edge cases.** Removing the last link leaves a parent with no children; the parent then sees "No children linked to your account." The service logs debug lines at ERROR level.

**Unit-testable logic.** Duplicate and existence checks with a fake session.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-20-U01 | Link service with an existing pair | Raises 400 "Student-parent link already exists" | passing |
| TC-STU-20-A01 | Admin links an existing parent to a student | 201 with ids | passing |
| TC-STU-20-A02 | Link the same pair again | 400 | passing |
| TC-STU-20-A03 | Link with unknown student; unknown parent | 404 "Student not found"; 404 "Parent not found" | passing |
| TC-STU-20-A04 | Unlink an existing pair; unlink again | 204; 404 | passing |
| TC-STU-20-A05 | `GET student/{id}/parents` | Father, mother (and guardian) as `ParentOut` with `students` list | passing |
| TC-STU-20-A06 | `GET parent/{id}/students` as Parent with own id; with another parent's id | 200; 403 | passing |
| TC-STU-20-A07 | `GET parent/{id}/students` as Admin | 200 list of `StudentOut` with father and mother | passing |
| TC-STU-20-A08 | `GET /` all links as Admin and Staff | 200 | passing |
| TC-STU-20-A09 | Permission matrix: POST (Admin 201, Staff 201, Teacher 403, Student 403, Parent 403); DELETE (Admin 204, Staff 403, others 403); GET student/parents, GET / (Admin 200, Staff 200, Teacher 403, Student 403, Parent 403) | As listed | passing |
| TC-STU-20-A10 | No token on every endpoint | 401 | passing |
| TC-STU-20-A11 | Tenant isolation: tenant B Admin links tenant A ids; token A with B header | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-20-E01 | P3 | Web | Parent | TC-STU-04-E02 done (parent login "<admission number>.father" of "QA No Email"); that link removed with DELETE /student-parent-links/student/{sid}/parent/{pid} | 1. Sign in with that parent login.<br>2. Open Students > Admission. | "No children linked to your account."; no child selector entries | planned |

API tests implemented in: backend/tests/api/students/test_profile_links.py

Implemented in: backend/tests/unit/student/test_student_misc_services.py.

---

## F21 Student transport assignment

**Purpose.** Assign a student to a transport trip and stop with a fee per term, and let students and parents see it.

**Roles and permissions.** Resource `student_transport`: create, update, list (Admin, Staff), delete (Admin). `GET /students/student-transport/student/{student_id}` is decided by role name: Student only their own id, Parent only linked children (otherwise 403), other roles need `student_transport:read` (Admin, Staff; Teacher has none). Menu: Students > Student Transport (hidden on the dashboard).

**Preconditions.** Routes, stops, trips (and optionally pricing plans) from the Transport module (`docs/features/transport.md`).

**Steps, web.** Students > Student Transport. Staff: page "Student Transport" with a search box "Search student, route, stop...", button "Assign Transport" (needs create), table with row actions "Edit" and "Delete". Dialog "Assign Transport" / "Edit Assignment": "Student" ("Select student..."), "Trip" ("Select trip..."), "Stop", "Pricing Plan (optional)", "Fee per Term (rupee sign)" (hints "Auto-filled from stop fee. You can edit it if needed." etc.). Delete dialog "Delete Transport Assignment". Empty table: "No transport assignments found.". Student: "My Transport" with card "Transport Assignment" ("No transport assignment found." when none). Parent: "Children's Transport" with its own "Select Child" card and "Child" dropdown ("Select child"); a Parent login without a parent record sees "Session outdated. Please log out and log back in.". Teacher: "Failed to load transport assignments: <detail>" (403).

**Steps, mobile.** Students > Student Transport (`app/students/transport.tsx`, list "Student Transport Assignments", "Filters" with "Search student, route, stop...", empty "No transport assignments yet"): "Assign Transport" modal ("Student", "Trip", "Stop", "Pricing Plan", fee) with validation toasts "Please select a trip and stop", "Please select a student", "Enter a valid fee amount"; success "Assigned - Transport assignment created successfully"; card actions "Edit" ("Updated - Transport assignment updated successfully") and "Delete" ("Removed - Transport assignment removed"). Student title "My Transport", Parent "Child Transport".

**Expected results.** One assignment per student and trip. The fee defaults from the stop fee when not sent.

**API endpoints.**
- `POST /students/student-transport/` body `{student_id, trip_id, stop_id, fee_per_term?, pricing_id?}` returns 201 with trip (route, vehicle), stop, student and pricing details.
- `GET /students/student-transport/` list (all assignments).
- `GET /students/student-transport/student/{student_id}`.
- `PATCH /students/student-transport/{transport_id}` body `{trip_id?, stop_id?, fee_per_term?, pricing_id?}`.
- `DELETE /students/student-transport/{transport_id}` returns 204.

**Rules and validations.** Unknown student, trip, stop, pricing (inactive or missing) are 404. A student cannot have two assignments for the same trip (422 "Student already has transport assignment for this trip"). On create `fee_per_term` may be omitted: it is taken from the stop's `fees`; if the stop has no fee, 400 "This stop has no default fee - enter the amount manually". A negative fee is 400; `0` is accepted on create but PATCH requires `> 0` (422 from the schema). A student with no assignment gets 404 "No transport assignments found for this student".

**Error and edge cases.** Teacher is denied everywhere. Other fee handling (billing) lives in the Fee module.

**Unit-testable logic.** Fee resolution (explicit, from stop, missing), duplicate rule, update-field validation.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-21-U01 | Fee resolution: explicit 1500 with stop fee 1000; omitted with stop fee 1000; omitted with stop fee None | 1500; 1000.0; error "This stop has no default fee" | passing |
| TC-STU-21-U02 | `StudentTransportUpdate` with fee 0 and -5 | Rejected (gt 0) | passing |
| TC-STU-21-A01 | Admin assigns with all fields | 201 with nested trip, route, stop, student | passing |
| TC-STU-21-A02 | Assign without `fee_per_term` using a stop with fee 1000 | 201 `fee_per_term` 1000; a stop with no fee and no `fee_per_term` is 400 with `no default fee` in `detail.message` | passing |
| TC-STU-21-A03 | Assign twice for the same student and trip | 422 "Student already has transport assignment for this trip" | passing |
| TC-STU-21-A04 | Unknown student, trip, stop, inactive pricing | 404 each | passing |
| TC-STU-21-A05 | Fee boundary on create: 0 and -1 | 422 for 0 and -1 | passing |
| TC-STU-21-A06 | PATCH trip, stop and fee; PATCH fee 0 | 200; 422 | passing |
| TC-STU-21-A07 | PATCH unknown id; DELETE unknown id | 404 each | passing |
| TC-STU-21-A08 | DELETE existing | 204 and GET by student returns 200 with an empty list | passing |
| TC-STU-21-A09 | `GET /` and `GET /student/{id}` as Admin and Staff | 200 | passing |
| TC-STU-21-A10 | Student `GET student/{own id}` and `{other id}` | 200 (if assigned); 403 "You can only view your own transport assignment" | passing |
| TC-STU-21-A11 | Parent `GET student/{linked child}` and `{unlinked}` | 200; 403 "You can only view transport for your own children" | passing |
| TC-STU-21-A12 | Permission matrix for POST, PATCH, GET `/`: Admin 2xx, Staff 2xx, Teacher 403, Student 403, Parent 403; DELETE: Admin 204, others 403; GET by student as Teacher 403 | As listed | passing |
| TC-STU-21-A13 | No token on all endpoints | 401 | passing |
| TC-STU-21-A14 | Tenant isolation: tenant B Admin assigns a tenant A student; token A with B header | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-21-E01 | P1 | Web | Admin | TC-STU-03-E01 done (QA Asha Rao has no transport); a seeded trip exists | 1. Sign in as Admin.<br>2. Open /students/studenttransport.<br>3. Click "Assign Transport".<br>4. Choose Student "QA Asha Rao", a trip (the dropdown shows only "Trip #n" without the route, so pick "Trip #1") and a stop; keep the auto-filled fee.<br>5. Save.<br>6. Click "Edit" on the row, set the fee to 1500 and save.<br>7. Click "Delete" and confirm. | Step 5: the row appears with student, trip, route, stop and "Fee / Term" equal to the stop fee; step 6: fee 1500; step 7: dialog "Delete Transport Assignment" and the row disappears ("No transport assignments found." when it was the last) | known defect: UI-STU-02: choosing a trip in the Assign Transport dialog crashes the page ("Something went wrong!", Select.It... |
| TC-STU-21-E02 | P2 | Web | Student | Seeded student login 004 (Harsha Raju, on Route 2 - Uppal) | 1. Sign in with the seeded student login 004.<br>2. Open /students/studenttransport. | "My Transport" with card "Transport Assignment" showing route "Route 2 - Uppal", timings, vehicle, pickup stop, pricing plan and "Fee per Term" | planned |
| TC-STU-21-E03 | P2 | Web | Parent | Seeded parent login venkat.raju@example.com (Harsha on Route 2 - Uppal, Tanvi on Route 1 - Kukatpally) | 1. Sign in as venkat.raju@example.com.<br>2. Open /students/studenttransport.<br>3. Change "Child" to Tanvi Raju. | "Children's Transport" shows "Harsha Raju's Transport" with Route 2 - Uppal; after the change "Tanvi Raju's Transport" with Route 1 - Kukatpally | planned |
| TC-STU-21-E04 | P3 | Mobile | Admin | QA Admin login | 1. Sign in as Admin on mobile.<br>2. Open /students/transport and tap "Assign Transport".<br>3. Choose a trip and a stop but no student.<br>4. Save. | Toast "Validation - Please select a student"; nothing is created | planned |
| TC-STU-21-E05 | P3 | Web | Teacher | QA Teacher login | 1. Sign in as Teacher.<br>2. Open /students/studenttransport. | "Student Transport" with "Failed to load transport assignments: ..." (403); no "Assign Transport" button (verified 2026-10-07) | planned |

API tests implemented in: backend/tests/api/students/test_transport.py

Implemented in: backend/tests/unit/student/test_student_misc_services.py. U02 is xfail(strict): the Update schema does not enforce gt=0.

---

## F22 Manual SMS triggers (admission confirmation, absence alerts, homework reminders)

**Purpose.** Queue SMS to parents from the student modules.

**Roles and permissions.** `student_admissions:send_sms`, `student_attendance:send_sms`, `student_homework:send_sms`. None of these actions is in the default catalog for any role, so every role gets 403 until granted.

**Preconditions.** Permission granted by an Admin; MSG91 settings and a Celery worker.

**Steps, web and mobile.** The web admission table has a "Send Welcome Message" quick-send button and the web attendance page a "Send Absentee Message" quick-send button; both use the Communication module's quick send (`docs/features/communication.md`), not these endpoints, and both render only with `communications:create` (Admin by default; Staff and Teacher do not see them). The dialog "Send Message" shows "To: <student> - <class> <section>", "Channel" (SMS, WhatsApp, Email), "Template" ("Select template..."), "Preview" and the buttons "Cancel" and "Send Now". Mobile has no quick-send buttons. No client calls the three endpoints below.

**Expected results.** If it worked: rows in the notification queue and a Celery batch.

**API endpoints.**
- `POST /students/admission/send-confirmation` body list of admission ids.
- `POST /student/attendance/send-absence-alerts?attendance_date=&reason=` body list of student ids.
- `POST /students/homework/send-reminders` was removed on 2026-10-02 (the homework router is no longer registered); every role and unauthenticated calls get 404.

**Rules and validations.** The first two import `app.models.student.student_parent_association_model`, which does not exist (the model is in `models/masters/`), so they return 500 once the permission check passes. The homework reminders route no longer exists.

**Error and edge cases.** `attendance_date` is required for absence alerts (422 when missing).

**Unit-testable logic.** Message formatting for absence alerts and reminders (name, date, reason).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STU-22-U01 | Absence message format for "Dear Mrs Rao, your ward Asha Rao was marked absent today, 02-Oct." | Matches the template with reason in parentheses when given | blocked: message is built inline in attendance_endpoints.py after a function-local import that fails (KG-15) |
| TC-STU-22-A01 | Admin calls each of the three endpoints under the default catalog | 403 for send-confirmation and send-absence-alerts (no `send_sms` grant); 404 for homework reminders (route removed 2026-10-02) | passing |
| TC-STU-22-A02 | Grant `student_admissions:send_sms` to Admin, call `send-confirmation` with a valid admission id | 500 (import error, documented defect) | skipped: skipped: after a send_sms grant this endpoint would reach the SMS path, and the suite never sends messages |
| TC-STU-22-A03 | Grant `student_attendance:send_sms`, call `send-absence-alerts` with `attendance_date` | 500 (import error) | skipped: skipped: after a send_sms grant this endpoint would reach the SMS path, and the suite never sends messages |
| TC-STU-22-A04 | `send-absence-alerts` without `attendance_date` | 422 | passing |
| TC-STU-22-A05 | Grant `student_homework:send_sms`, call reminders with an unknown homework id | 200 `{status:"queued", queued_count:0, skipped_count:1}` | skipped: skipped: needs a send_sms grant on the shared Admin role and would reach the Celery queue |
| TC-STU-22-A06 | Staff, Teacher, Student, Parent call each endpoint | 403 each (homework reminders 404: route removed) | passing |
| TC-STU-22-A07 | No token on each endpoint | 401 (homework reminders 404: route removed) | passing |
| TC-STU-22-A08 | Tenant isolation: token A with header B | 403 (homework reminders 404: route removed) | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STU-22-E01 | P2 | Web | Admin | Seeded admissions | 1. Sign in as Admin.<br>2. Open Students > Admission.<br>3. Click "Send Welcome Message" on a row.<br>4. Click "Cancel". | Dialog "Send Message" with "To: <student> - <class> <section>", Channel SMS, WhatsApp, Email, "Template" and "Preview"; no call to /students/admission/send-confirmation; "Cancel" closes it without sending | planned |
| TC-STU-22-E02 | P3 | Web | Admin | Seeded Class 1 / 1-A loaded on Students > Attendance for a date with every student Present | 1. Sign in as Admin.<br>2. Hover the "Send Absentee Message" icon of a Present row. | The icon is disabled with a tooltip starting "Student is present" | planned |
| TC-STU-22-E03 | P3 | Web | Staff, Teacher | QA Staff and QA Teacher logins; seeded Class 1 / 1-A | 1. Sign in as Staff and open Students > Admission and Students > Attendance (load Class 1 / 1-A).<br>2. Repeat as Teacher. | No "Send Welcome Message" and no "Send Absentee Message" icons (both need communications:create) | planned |

API tests implemented in: backend/tests/api/students/test_profile_links.py

---

## Known gaps

Code behaviour that differs from `docs/modules/students.md` or from what a user would expect. Defects found while documenting are also listed so tests can track them.

1. **Error status codes.** `create_validation_error` returns 400 (not 422). Future admission date, future attendance date and "before admission date" attendance are therefore 400; the module doc says 422.
2. **Admission schema vs doc.** Fixed (2026-10-02): `last_name` is now optional and a missing, null or blank value is stored as `""`, as the module doc says. `AdmissionTypeEnum` in `schemas/student/student_schema.py` is `primary|not_primary` (unused for `admission_type`); the real admission type is the `Literal["pre_primary","regular"]`.
3. **Father name not enforced by the API.** `ParentBase.default_name` fills a blank name with the relation label before `StudentCreate` checks it; only father phone is enforced server-side. Web, mobile and bulk upload enforce the name.
4. **Mother object is required** in the payload (`StudentCreate.mother`), although every mother field is optional.
5. **Parent Aadhar** is format-checked (12 digits) by `ParentCreate` on admission. Fixed (2026-10-02): `StudentAdmissionUpdate` (PATCH) now applies the same checks (student and parent Aadhar, APAAR, primary phone, parent email format, salary range), and admission create rejects a guardian that has details but no email instead of silently dropping it.
6. **Photo path.** Photos are stored under `media/<tenant id>/student/photos/` (tenant-scoped), unlike the module doc (`media/student/photos/`). They are still served without a token, but a request with no tenant context (no `cschema` header or token) gets 400.
7. **Student documents are broken end to end for the web upload flow:** the document type dropdown calls the missing `GET /students/document-types/`; View and Download point at files that are not served; Verify calls a missing endpoint; mobile `documents.tsx` upload is a stub and its admin list calls `GET /students/documents/` without the required `student_id`.
8. **Student and Parent get 403 on documents and attendance lists under the default catalog**, because those endpoints check the exact `list`/`read` action while the Student and Parent roles hold only `*_own`/`*_related`. The web pages in their menu (`/students/studentdocuments`, `/students/mydocuments`) therefore fail until the grants are changed or the endpoints use `check_user_resource_access`. The same applies to `GET /students/admission/by-admission/{id}` and the admission-types dropdown.
9. **No ownership check** on `GET /student/attendance/student/{id}/filter` for Parents, and the document endpoints do not check ownership at all. Fixed (2026-10-02): `student/{id}/filter` now returns 403 for a Parent whose children do not include the id; the document list, all and get endpoints call `ensure_student_access` (Student own record, Parent linked child; other roles unchanged).
10. **Profile attendance percentage** was always 0.0. Fixed (2026-10-02): the shared helper compares case-insensitively and counts half days as 0.5. Still open: the web and mobile profile screens show fields the API never returns (phone, address, emergency contact, blood group, roll number, academic year, picture).
11. **Attendance percentage** was computed four different ways. Fixed (2026-10-02): one rule, see F13.
12. **Mobile defects.** `app/students/[id].tsx` is opened with the student id but matches it against the admission id, in the first page of admissions only, so "Student Details" always shows "Student not found"; the Students list card prints the admitted class id (a UUID) instead of the class name; the admission form labelled "Academic Year (Optional)" although the API requires it (fixed 2026-10-02: the label and the step validation now mark it required); the profile screen for a Parent calls the non-existent `GET /students/profile/{id}`; the regular-number placeholder `e.g. 2026001` does not match the `001` format.
13. **Roster cap.** Fixed (2026-10-02): the list endpoint honours `active_only`, and the web and mobile roster calls page 100 at a time, so rosters hold every active student.
14. **DELETE `/students/admission/{admission_id}`**: fixed (2026-10-02), see F09 (shared parents kept, 409 when blocked, 200 on success). **`POST /parents/`** is broken and standalone parents cannot be created. There is no way to add a guardian to an existing admission.
15. **Manual SMS endpoints** `send-confirmation` and `send-absence-alerts` fail on a bad import (500) and no role holds their permissions by default; the homework reminders route was removed on 2026-10-02 (404 for everyone).
16. **Toggle semantics.** The toggle endpoint flips the flag and ignores the request body; two fast clicks undo each other.
17. **Web admission details route** `/students/admission/<admission id>` is not linked from the table (the table uses a modal keyed by student id).
18. **Labels inconsistent between create and edit on web:** "Student Type" (Day Scholar, Hostel) on create versus "Primary Status" (Not Primary, Primary) on edit; both write `is_primary`, which the backend also treats as pre primary in bulk upload. The web create form has no "Primary Phone" input while edit and view do.
19. **Web sends caste and sub caste UUIDs in `caste`/`sub_caste`,** and state UUID in `state`; the view resolves names from the ids. Gender values are `M/F/O` from the clients but `Male/Female/Other` from bulk upload defaults and parent update schema.
20. **Mobile staff attendance has no Half Day option;** web has all five statuses.
21. **Transport page for Parents** uses its own child dropdown instead of the header selector used by every other student page.
22. **Previous school select on web.** Fixed (2026-10-02): the select registers a boolean and the payload builder normalises it, so "Yes" then "No" sends `false` with the "NA" placeholders.
23. **UI states seen on 2026-10-07 (web).** Pages that get a 403 or 404 do not show an error: `/students/studentdocuments` for a Student stays on "Loading documents..."; `/students/mydocuments` for Admin, Staff, Teacher and Parent and `/students/profile` for Admin, Staff, Teacher and Parent stay on their loading text; `/students/certificatetypes` for a Parent shows "No certificate types found." with a "Create First Certificate Type" button; `/students/certificatetemplates` for Staff, Teacher, Student and Parent shows "No templates created yet" with "Load Default Templates", "Create Template" and "Create Your First Template". The Student "My Attendance" "From" date shows the last day of the previous month in IST (F13).
24. UI-STU-01: a new admission with only the Joining Class and Joining Section filled shows N/A for Class and Section in the table (no current class); ticking "current class same as admission" is the workaround.
25. UI-STU-02: Assign Transport on web crashes when a trip is chosen ("Something went wrong!"): the pricing Select has an item with an empty value for the "None" option (same root cause as UI-TRN-01).
