# Staff: feature documentation and test specification

Code: `STF`. Test case IDs: `TC-STF-<FF>-<P><NN>` (U unit, A API, E end-to-end UI). Conventions: `docs/testing/strategy.md`, layout: `docs/features/README.md`. Module rules: `docs/modules/staff.md`. Graph view: `docs/graph/views/staff.md`.

_Last verified against code: 2026-10-07_

## Module overview

The Staff module holds the school's employees. Enrolling a staff member creates two rows in one request: a login account (`users`) and an HR record (`staff`) with personal, work-experience, bank, salary and PF fields. Qualifications are kept in a child table, a photo can be attached, and designations (job titles) are a master list that staff point to. Daily staff attendance is stored as exceptions only (a missing row means present). A staff member can view and edit their own email and phone through the self-service profile. Bulk enrollment reads an Excel sheet. All endpoints live under `/api/v1/staff` (`backend/app/api/v1/masters/staff_endpoints.py`) except the self-service profile (`/api/v1/profile/staff/me`) and the first-login password steps (`/api/v1/auth/*`). Nothing in this module talks to an external provider; the two SMS triggers that sit in the staff router (`/staff/send-attendance-summary`, `/staff/send-interview-calls`) are documented in `docs/features/communication.md` (COM F08).

## Roles

Backend grants are live `resource_permissions` rows (`docs/permissions.md`). The table shows the **default seed** in `backend/app/service/tenant/permission_catalog.py` (`ROLE_PERMISSIONS`). The QA tenant (`qa_school`) must be provisioned so that these grants hold, plus the extra grants listed under the table. Each test reads the real grant set from the QA tenant at start-up; the expected statuses below assume the default seed plus the extras.

| Role | `staff` | `designations` | `staff_attendance` | `transport_trips` | `profile` |
|---|---|---|---|---|---|
| Admin | create, read, update, delete, list | create, read, update, delete, list | create, read, update, delete, list | create, read, update, delete, list | not in the default seed |
| Teacher | none | read, list | none | read, list | not in the default seed |
| Staff | read, list | read, list | none | create, read, update, list | not in the default seed |
| Student | none | none | none | none | read_own, update_own |
| Parent | none | none | none | none | none |

Extras the QA tenant needs (not in the default seed): `profile:read_own` and `profile:update_own` for Admin, Teacher and Staff (otherwise `/profile/staff/me` answers 403 for them); `staff_attendance:send_sms` and `staff_enrollment:send_sms` for Admin (COM F08).

Observed on 2026-10-07 (login response). Manual-test tenant `qa_manual` (used by the E cases): the default seed only. Admin holds every action on `staff`, `designations` and `staff_attendance`, but no `profile` and no `send_sms` grant; Staff holds `staff:read,list` and `designations:read,list`; Teacher holds `designations:read,list`; nobody but Student has `profile` actions. API tenant `qa_school`: the same plus `profile:read_own,update_own` for Admin, Staff, Teacher and Parent; still no `send_sms`. The web sidebar for Admin, Staff and Teacher lists Staff with the sub-items "Enrollment", "Designations" and "Staff Attendance"; Student and Parent see only Dashboard, Students, Fee and Exam.

Frontend caps (`web/src/lib/{teacher,staff}PermissionMatrix.ts`, duplicated in `mobile/src/lib/`): Staff is capped to `staff: [read, list]` and `designations: [read, list]`; Teacher to `designations: [read, list]`. `staff_attendance` is not in either matrix, so the backend grant decides. Menus: Admin, Staff and Teacher receive every menu from the seed; Student and Parent receive only the allowlist in `STUDENT_PARENT_MENU_URLS`, which has no `/staff` entry.

Role names are compared case-sensitively (`Admin`, `Teacher`, `Staff`, `Student`, `Parent`).

## Feature index

| ID | Title |
|---|---|
| F01 | Designations |
| F02 | Enroll a staff member (account creation) |
| F03 | First login of a new staff account |
| F04 | Staff qualifications |
| F05 | Staff photo |
| F06 | Staff list, search and detail |
| F07 | Edit, deactivate and delete a staff member |
| F08 | Bulk enrollment from Excel |
| F09 | Drivers list |
| F10 | Mark staff attendance |
| F11 | Staff attendance history and lookup |
| F12 | Staff profile (self-service) |

Common test data.
- API cases (A) run in `qa_school` (`backend/scripts/qa/setup_qa_tenant.py`): default roles, one academic year and one login per role, no school data. They create their own rows (`Principal`, `Teacher`, `Driver`, `Asha Verma`, `Ravi Kumar`, `Meena Rao`) and use a second tenant `qa_school_b` for isolation cases.
- UI cases (E) run in the seeded manual-test tenant `qa_manual` (`backend/scripts/qa/setup_manual_tenant.py`, data from `backend/scripts/seed_demo_data.py`). Seeded staff data: designations Principal (1 staff), Teacher (4), Accountant (1), Clerk (1), Driver (2); 9 active staff, emails `<first>.<last>@example.com`, phones `9000010001` to `9000010009`: Lakshmi Narayana Rao (Principal, Administration), Sunitha Reddy, Venkatesh Kumar, Anjali Sharma, Ravi Teja Naidu (Teacher, Academics, login role Teacher), Padmavathi Devi (Accountant), Suresh Babu (Clerk) (Administration), Ramesh Yadav and Mohan Singh (Driver, Transport); staff attendance exceptions on 2026-09-25, 2026-09-28, 2026-09-29, 2026-09-30 and 2026-10-01. Seeded staff logins use the temporary password and must change it at first login. The QA role logins exist in `qa_manual` too but have no staff row. Do not change seeded rows.
- Cases that create, edit, deactivate or delete use a QA data set the tester creates once as Admin (Staff > Enrollment) and deletes afterwards:
  - Staff `QA Asha Verma` (First Name "QA Asha", Last Name "Verma", Email `qa.asha.verma@qa.example`, Phone `9876510001`, Address "1 QA Street", Designation `Teacher`, Department "Primary").
  - Staff `QA Ravi Kumar` (First Name "QA Ravi", Last Name "Kumar", no email, Phone `9876510002`, Address "2 QA Street", Designation `Driver`).
  - Staff `QA Meena Rao` (First Name "QA Meena", Last Name "Rao", Phone `9876510003`, Address "3 QA Street", "Active Staff Member" unticked).

The temporary password given to new staff accounts is the hardcoded default in `staff_service.create_staff_enrollment`; read it from the code, it is not repeated here. On-screen texts that use a long dash, a middle dot, an ellipsis or the rupee sign are written here with "-", "...", or without the symbol.

---

## F01 Designations

**Purpose.** Maintain the master list of job titles (for example Principal, Teacher, Driver) that staff are assigned to. Titles are unique and cannot be removed while a staff member uses them.

**Roles and permissions.**
- List, dropdown, legacy list: `designations:list`. Get one: `designations:read`. Create: `designations:create`. Edit: `designations:update`. Delete: `designations:delete`.
- Menu: Staff -> Designations for roles holding `designations:list`. Web hub card "Staff Designations" needs `designations:list`. Mobile hub card "Designations" is gated on `staff` list or read (not on `designations`); the buttons inside the screen use `designations` create, update, delete.

**Preconditions.** An authenticated tenant user with one of the grants above. None of the designations exist beforehand; this feature creates them. F02 and F09 depend on it.

**Steps, web.**
1. Open Staff (`/staff`, "Staff Management") and click the card "Staff Designations" (button "Manage Designations"), or use the sidebar Staff > Designations, or go to `/staff/designations` (page title "Staff Designations"). The hub shows only the cards the role may open: Admin sees "Staff Enrollment", "Staff Attendance" and "Staff Designations"; Staff sees Enrollment and Designations; Teacher sees only Designations.
2. The table shows S.No., Title, Staff Count ("N staff member(s)"), Created and Actions. Type in "Search designations..." to filter by title. Click the Title, Staff Count or Created header to sort (asc, desc, off).
3. Click "Add Designation" (or "Create First Designation" on an empty list). In the dialog "Create Designation" fill "Designation Title *" and click "Save". Toast: "Designation created successfully".
4. Click the Edit icon ("Edit Designation"), change the title in the dialog "Edit Designation", click "Save". Toast: "Designation updated successfully".
5. Click the Delete icon ("Delete Designation"). The dialog "Delete Designation" asks for confirmation; click "Delete". Toast: "Designation deleted successfully". If staff still use the title the toast reads "Failed to delete designation: Cannot delete designation '<title>' because it is being used by <n> staff member(s). ...".
6. An empty title shows the toast "Designation title is required" and nothing is sent. Users without `designations:list` see "Access Denied - You don't have permission to view staff designations." Add, Edit and Delete controls are hidden without the matching permission.

**Steps, mobile.**
1. Staff hub (`/staff`) -> card "Designations" ("Configure staff designations & roles") -> screen "Staff Designations" with the count line "<n> designation(s)".
2. Search with "Search designations...". Each card shows the title, "Created: <date>" and "N staff member(s)".
3. Tap "Add Designation"; the modal "Add Designation" has "Title *" (placeholder "Enter designation title"), "Cancel" and "Save". Tap "Save". Toast "Success - Designation created successfully".
4. Pencil icon (accessibility label "Edit") opens the modal "Edit Designation"; trash icon ("Delete") opens the confirm "Delete Designation", then toast "Success - Designation deleted successfully".
5. Without `designations` list or read the screen shows "Access Denied - You don't have permission to view staff designations data".
6. Empty title: toast "Validation Error - Please enter designation title".

**Expected results.** The designation appears in the list with staff count 0 and in `GET /staff/designations/dropdown` (after the dropdown cache, see rules). Edit changes only the title; the staff count follows the number of staff using it. Delete removes the row only when no staff use it.

**API endpoints** (all under `/api/v1/staff`; trailing slash matters on `/designations/`).
- `POST /designations/` body `{title}` -> 201 `DesignationRead {id,title,created_at,updated_at,staff_count}`. Rate limited 30 per minute.
- `GET /designations/?skip=0&limit=10` (`skip>=0`, `1<=limit<=100`) -> `{items[],total_count,has_next}` ordered by title, each item with `staff_count`.
- `GET /designations/dropdown` -> `[{id,title}]` ordered by title. Rate limited 300 per minute.
- `GET /designations/{designation_id}` -> `DesignationRead`.
- `PUT /designations/{designation_id}` body `{title?}` -> `DesignationRead`.
- `DELETE /designations/{designation_id}` -> `{"message": "Designation deleted successfully"}`.
- `GET /designations-legacy` -> `[{id,title}]` (kept for compatibility, `designations:list`).

**Rules and validations.**
1. `title` is required (422 when missing). The backend has no minimum length or trimming: `""` is accepted. The web and mobile forms block an empty or whitespace title.
2. Title is unique per tenant. Both the service check and the database unique constraint are exact, case-sensitive matches, so `Driver` and `driver` can coexist (and both match the drivers list, F09).
3. `title` is `String(100)`; longer values fail at the database.
4. A designation used by any staff row cannot be deleted (400 with the count in the message).
5. List order is by title; `has_next = (skip + limit) < total_count`.
6. The dropdown is cached 300 seconds per tenant per process. Create, update and delete clear it (`invalidate_cache("dropdown", "designations_dropdown")`).
7. Uniqueness and data are per tenant (row-level security).

**Error and edge cases.**
- Duplicate title on create: 400 "Designation title '<t>' already exists" (same as update).
- Unknown or foreign-tenant id: 404 "Designation with id <id> not found". Non-UUID id: 422.
- Title longer than 100 characters: 500 "Error creating designation: ...".
- Missing token: 401. Missing permission: 403.
- Deleting a designation that staff use: 400 "Cannot delete designation '<title>' because it is being used by <n> staff member(s). Please reassign or delete the staff records first."

**Unit-testable logic.** `check_designation_title_unique` (exclude id, message); `DesignationCreate/Update/Read` schemas; pagination `has_next` arithmetic in `get_all_designations`; the in-use guard in `delete_designation`; `cache_dropdown` key per tenant and `invalidate_cache` behaviour for an unknown cache type; web `DesignationsTable` filter and sort (`filteredData`, `sortedData`) once extracted.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-01-U01 | `DesignationCreate()` without `title` | Pydantic ValidationError on `title` | passing |
| TC-STF-01-U02 | `DesignationRead` built without `staff_count` | `staff_count == 0`; missing `created_at` raises ValidationError | passing |
| TC-STF-01-U03 | `check_designation_title_unique(db, "Driver")` with a mocked existing row | raises HTTPException 400, detail "Designation title 'Driver' already exists" | passing |
| TC-STF-01-U04 | `check_designation_title_unique(db, "Driver", exclude_id=<own id>)` | query carries `id != exclude_id`; no exception when the only match is the row itself | passing |
| TC-STF-01-U05 | `has_next` for (skip 0, limit 10, total 10), (0,10,11), (10,10,20), (10,10,21) | false, true, false, true | passing |
| TC-STF-01-U06 | `delete_designation` with a mocked staff count of 3 | raises HTTPException 400 and the detail contains "3 staff member(s)" | passing |
| TC-STF-01-U07 | `create_designation` where the title check raises HTTPException 400 | re-raised as HTTPException 400 "Designation title '<t>' already exists" | passing |
| TC-STF-01-U08 | `create_tenant_cache_key` for the same call with tenant ids A and B | the two keys differ and both contain the tenant id | passing |
| TC-STF-01-U09 | `invalidate_cache("designations_dropdown")` after a cached dropdown entry exists | the entry is still present (unknown cache type); `create_designation` now clears the entry through `invalidate_cache("dropdown", ...)` | passing |
| TC-STF-01-A01 | Admin `POST /staff/designations/` `{title:"Lab Assistant"}` | 201; body has id, title "Lab Assistant", created_at, updated_at, `staff_count` 0 | passing |
| TC-STF-01-A02 | Admin creates the same title twice | second call returns 400 "Designation title '<t>' already exists"; no second row is created | passing |
| TC-STF-01-A03 | Create with `{}` | 422, loc `["body","title"]` | passing |
| TC-STF-01-A04 | Create with a 100-character title | 201 | passing |
| TC-STF-01-A05 | Create with a 101-character title | 500 "Error creating designation"; no row created | passing |
| TC-STF-01-A06 | Create with `{title:""}` | 201 (no backend minimum length); the row is removed in cleanup | passing |
| TC-STF-01-A07 | 12 designations exist; `GET /designations/` | 200; 10 items ordered by title; `total_count` 12; `has_next` true | passing |
| TC-STF-01-A08 | `GET /designations/?skip=10&limit=10` with 12 rows | 2 items; `has_next` false | passing |
| TC-STF-01-A09 | `limit=100` accepted; `limit=101`, `limit=0`, `skip=-1` | 200 for 100; 422 for the other three | passing |
| TC-STF-01-A10 | `staff_count` accuracy: Teacher designation used by 2 staff, Driver by 1, Principal by 0 | counts 2, 1, 0 in the list and in `GET /designations/{id}` | passing |
| TC-STF-01-A11 | `GET /designations/{id}` with an existing id | 200 `DesignationRead` | passing |
| TC-STF-01-A12 | `GET /designations/{random uuid}`; `GET /designations/abc` | 404 "Designation with id <id> not found"; 422 | passing |
| TC-STF-01-A13 | `PUT` rename "Lab Assistant" to "Laboratory Assistant" | 200; title updated; `staff_count` unchanged | passing |
| TC-STF-01-A14 | `PUT` to a title another row already has | 400 "Designation title '<t>' already exists" | passing |
| TC-STF-01-A15 | `PUT` with the unchanged title; `PUT {}` | 200 both; nothing changes | passing |
| TC-STF-01-A16 | `PUT` / `DELETE` on a random uuid | 404 for both | passing |
| TC-STF-01-A17 | `DELETE` an unused designation | 200 `{"message":"Designation deleted successfully"}`; a later GET is 404 | passing |
| TC-STF-01-A18 | `DELETE` a designation assigned to staff | 400 "Cannot delete designation 'Teacher' because it is being used by 2 staff member(s). ..."; row still exists | passing |
| TC-STF-01-A19 | `GET /designations/dropdown` | 200; `[{id,title}]` ordered by title; no `staff_count` | passing |
| TC-STF-01-A20 | Call the dropdown, create a new designation, call the dropdown again within 60 seconds | the new title is present in the second response (cache cleared on create) | passing |
| TC-STF-01-A21 | `GET /designations-legacy` | 200; `[{id,title}]` including every designation | passing |
| TC-STF-01-A22 | Each of the 7 endpoints without an Authorization header | 401 | passing |
| TC-STF-01-A23 | Admin: create, get, update, delete, list, dropdown, legacy | all 2xx | passing |
| TC-STF-01-A24 | Staff role: list, get, dropdown, legacy | 200; `POST`, `PUT`, `DELETE` return 403 | passing |
| TC-STF-01-A25 | Teacher role: same matrix as Staff | list, get, dropdown, legacy 200; create, update, delete 403 | passing |
| TC-STF-01-A26 | Student role on every endpoint | 403 on all 7 | passing |
| TC-STF-01-A27 | Parent role on every endpoint | 403 on all 7 | passing |
| TC-STF-01-A28 | Tenant isolation: designation "Isolation Test" created in `qa_school` | absent from the list and dropdown of `qa_school_b`; the same title can be created in `qa_school_b`; `GET /designations/{id}` from tenant B returns 404 | passing |
| TC-STF-01-A29 | Token of tenant A sent with `cschema: qa_school_b` | 403 | passing |
| TC-STF-01-A30 | 31 creates inside one minute | the 31st returns 429 (limit 30 per minute) | skipped: needs the rate limiter enabled; |
| TC-STF-01-A31 | Create `Lab Tech` and then `lab tech` in the same tenant | both 201 (case-sensitive uniqueness) | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-01-E01 | P1 | Web | Admin | No designation named "QA Store Keeper" exists. | 1. Sign in as Admin.<br>2. Open Staff > Designations.<br>3. Click "Add Designation".<br>4. In "Create Designation" enter "Designation Title *" = "QA Store Keeper".<br>5. Click "Save". | Toast "Designation created successfully"; the dialog closes; a row "QA Store Keeper" appears with Staff Count "0 staff members" and today's Created date. | planned |
| TC-STF-01-E02 | P2 | Web | Admin | TC-STF-01-E01 done. | 1. Sign in as Admin.<br>2. Open Staff > Designations.<br>3. Click "Edit Designation" on the row "QA Store Keeper".<br>4. Change the title to "QA Store Keeper Grade 1".<br>5. Click "Save". | Toast "Designation updated successfully"; the row shows "QA Store Keeper Grade 1"; Staff Count unchanged. | planned |
| TC-STF-01-E03 | P2 | Web | Admin | TC-STF-01-E02 done; the designation is not used by any staff. | 1. Sign in as Admin.<br>2. Open Staff > Designations.<br>3. Click "Delete Designation" on "QA Store Keeper Grade 1".<br>4. In the dialog "Delete Designation" click "Delete". | Toast "Designation deleted successfully"; the row disappears and does not come back after a page reload. | planned |
| TC-STF-01-E04 | P2 | Web | Admin | Seeded designation "Teacher" (used by 4 seeded staff). | 1. Sign in as Admin.<br>2. Open Staff > Designations.<br>3. Click "Delete Designation" on "Teacher".<br>4. Click "Delete". | Toast "Failed to delete designation: Cannot delete designation 'Teacher' because it is being used by <n> staff member(s). ..." (n = the Staff Count shown); the row stays. | planned |
| TC-STF-01-E05 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff > Designations.<br>3. Click "Add Designation".<br>4. Leave "Designation Title *" empty.<br>5. Click "Save". | Toast "Designation title is required"; the dialog stays open; no designation is created. | planned |
| TC-STF-01-E06 | P3 | Web | Admin | Seeded designations (Principal, Teacher, Accountant, Clerk, Driver). | 1. Sign in as Admin.<br>2. Open Staff > Designations.<br>3. Type "dri" in "Search designations...".<br>4. Clear the search.<br>5. Click the "Staff Count" header three times. | Step 3 lists only rows whose title contains "dri" (Driver); step 5 sorts ascending, then descending, then back to the original order. | planned |
| TC-STF-01-E07 | P2 | Web | Staff | Seeded designations. | 1. Sign in as Staff.<br>2. Open Staff > Designations. | The table loads; no "Add Designation" button and no "Edit Designation" or "Delete Designation" icons. | planned |
| TC-STF-01-E08 | P2 | Web | Student | None. | 1. Sign in as Student.<br>2. Check the sidebar.<br>3. Open `/staff/designations` by URL. | The sidebar has no Staff menu; the page shows "Access Denied" and "You don't have permission to view staff designations." Parent: same (verified 2026-10-07). | planned |
| TC-STF-01-E09 | P1 | Mobile | Admin | No designation named "QA Cook" exists. | 1. Sign in as Admin.<br>2. Open the Staff hub.<br>3. Tap "Designations".<br>4. Tap "Add Designation".<br>5. Enter "Title *" = "QA Cook".<br>6. Tap "Save". | Toast "Success - Designation created successfully"; a card "QA Cook" with "0 staff members" appears and the count line increases by one. | planned |
| TC-STF-01-E10 | P2 | Mobile | Admin | TC-STF-01-E09 done. | 1. Sign in as Admin.<br>2. Open Staff hub > Designations.<br>3. Tap the pencil ("Edit") on "QA Cook".<br>4. Change the title to "QA Head Cook" and tap "Save".<br>5. Tap the trash icon ("Delete") on "QA Head Cook".<br>6. Confirm "Delete Designation". | Toast "Success - Designation updated successfully" after step 4; toast "Success - Designation deleted successfully" after step 6; the card is gone. | planned |
| TC-STF-01-E11 | P2 | Mobile | Staff | Seeded designations. | 1. Sign in as Staff.<br>2. Open Staff hub > Designations. | Cards are listed; no "Add Designation" button and no Edit or Delete icons. | planned |
| TC-STF-01-E12 | P3 | Mobile | Student | None. | 1. Sign in as Student.<br>2. Open `/staff` by URL.<br>3. Open `/staff/designations` by URL. | The Staff hub shows only its header with no cards; the designations screen shows "Access Denied - You don't have permission to view staff designations data". | planned |
| TC-STF-01-E13 | P3 | Web | Teacher | Seeded designations. | 1. Sign in as Teacher.<br>2. Open Staff in the sidebar.<br>3. Click "Manage Designations". | The hub shows only the "Staff Designations" card (no Enrollment or Attendance card); the list is read-only. | planned |

Implemented in: backend/tests/unit/staff/test_designations.py.

---

## F02 Enroll a staff member (account creation)

**Purpose.** Register a new employee and create their login account in one step.

**Roles and permissions.**
- `staff:create`. Admin has it in the default seed; Staff, Teacher, Student and Parent do not.
- Menu: Staff -> Staff Enrollment (`/staff/enrollment`, page guarded by `staff:list`). The "Add Staff" and "Bulk Upload" buttons need `staff:create`.

**Preconditions.** A role named exactly `Staff` exists (default when no role is chosen). Optional: designations (F01). The logged-in user holds `staff:create`.

**Steps, web.**
1. Staff -> Enrollment in the sidebar (or the hub card "Staff Enrollment", button "Manage Staff Profiles"; page "Staff Enrollment"). Click "Add Staff".
2. In the dialog "Create Staff Enrollment":
   - Basic Information: optional photo ("Staff Photo", "Choose photo", JPG, PNG or WebP, max 2 MB), "First Name *", "Last Name", "Email", "Phone *", "Gender" (Male, Female, Other), "Date of Birth", "Joining Date", "Qualification", "Experience (Years)", "Address *".
   - "Qualifications" -> "Add Qualification": Level, Degree / Course, Pass-out Year, Percentage / CGPA, University / Board (see F04).
   - Professional Information: "Designation" (searchable, from F01), "Department".
   - Account Information: "Role" (any tenant role; empty means `Staff`), checkbox "Active Staff Member" (default on).
   - Accordions "Work Experience" (Previous Organization, Subjects Dealt, From Date, To Date, Remarks), "Bank Details" (Bank Name, Branch, Account Number, IFSC Code, Account Holder Name, Account Type), "Salary & PF" (Last Drawn Salary, Current Salary, PF Account Number, UAN Number).
3. Click "Save". Client checks run first: "First name is required", "Phone is required", "Please enter a valid email address", "Address is required" (toast "Please fill in the required fields"); phone must be exactly 10 digits ("Phone number must contain digits only", "Number is less than 10 digits - you entered N. Please enter exactly 10 digits", "Number exceeds 10 digits - ..."); UAN "UAN Number must be exactly 12 digits"; PF "Invalid PF Account Number format (e.g. AP/HYD/12345)"; unpaired qualification toast "Qualification Level and Degree / Course must both be filled in, or both left empty".
4. On success the toast reads "Staff enrollment created successfully"; qualifications are posted one by one and the photo is uploaded afterwards (the id does not exist before create). The row appears in the table.

**Steps, mobile.**
1. Staff hub -> "Staff Enrollment" -> "Add Staff" (header button). The sheet "Create Staff Enrollment" has the same sections and labels as web, except: no Role field (always `Staff`), Account Information has only the switch "Active Staff Member" ("Staff member is currently active"), the Joining Date defaults to today, dates are typed as DD/MM/YYYY or picked, date of birth and joining date cannot be in the future, and the photo is chosen with "Upload Photo" at the top of the sheet. Buttons "Cancel" and "Save".
2. Same client validations and messages as web (mobile also reports them as a toast "Validation - Please fill in the required fields.").
3. "Save". Toast "Staff Added - New staff member enrolled successfully." On failure: "Failed - <server detail>".

**Expected results.**
- One `users` row: `username` = email, or the phone number when no email was given; `email` = email or null; `password_hash` of the hardcoded temporary password (never the plain text); `is_active = true`; `role_id` = chosen role or the `Staff` role; `is_first_login = TRUE` (set by a raw SQL update).
- One `staff` row linked by `user_id`, with every supplied field. Response is `StaffEnrollmentOut` with HTTP 200 (not 201), `qualifications: []`, `photo_url: null`, `created_at` and `updated_at` null, salary fields as strings (for example `"50000.00"`).
- The new person can log in (F03).

**API endpoints.**
- `POST /staff/enrollment` body `StaffEnrollmentCreate`: required `first_name`, `phone`, `address`; optional `last_name`, `email`, `gender`, `date_of_birth`, `joining_date`, `qualification`, `experience_years`, `designation_id`, `department`, `is_active`, `role_id`, work fields (`work_org`, `work_from_date`, `work_to_date`, `subjects_dealt`, `work_remarks`), bank fields (`bank_name`, `bank_branch`, `account_number`, `ifsc_code`, `account_holder_name`, `account_type` Savings or Current), `last_drawn_salary`, `current_salary`, `pf_account_number`, `uan_number`. Response `StaffEnrollmentOut`.

**Rules and validations.**
1. Backend required: `first_name`, `phone` (min length 1), `address` (min length 1). A missing or empty value is a 422. Whitespace-only values pass (no trim).
2. `email` is validated as an email (422) when present. Either email or phone is needed for the username (phone is always present, so this never fails in practice).
3. `gender` is a free string converted case-insensitively to `Male`, `Female` or `Other`; anything else is 400 "Invalid gender value: <v>. Must be 'Male', 'Female', or 'Other'".
4. `account_type` must be `Savings` or `Current` (422 otherwise). `is_active` defaults to true.
5. Role: `role_id` when given (any role, including Admin: known privilege escalation); otherwise the role named exactly `Staff`, or 400 "Default 'Staff' role not found. Please provide a role_id."
6. Column limits enforced only by the database: phone 15, first and last name 100, email 100, address 255, department 100, account number 50, IFSC 20, UAN 20, PF 50; salaries `Numeric(10,2)` (maximum 99999999.99). A violation surfaces as 500 "Error creating staff enrollment: ...".
7. Phone length (10 digits), UAN (12 digits), PF format and IFSC case are validated only in the clients.
8. Username uniqueness is per tenant: a duplicate email, or a duplicate phone when no email is given, fails at the first insert. `staff.email` is also unique per tenant. There is no friendly pre-check.
9. The user and staff rows are created in one transaction; any failure rolls both back.
10. `designation_id` and `role_id` are foreign keys: an unknown id fails with 500.

**Error and edge cases.**
- Duplicate email or duplicate phone-as-username: 500 "Error creating staff enrollment: ..." (not 400 or 409). The same also happens when an earlier deleted staff member left an orphaned user (see F07).
- Same email in another tenant is allowed.
- Missing token 401; missing `staff:create` 403.
- Web users who pick the Role "Admin" create an Admin login (privilege escalation, see Known gaps).
- Experience over 50 and salary over 10000000 show inline errors in the clients but do not block saving; the backend accepts them.

**Unit-testable logic.** `StaffEnrollmentCreate` validation (required fields, `min_length`, `EmailStr`, `Literal` account type); gender conversion block of `create_staff_enrollment`; username choice (`email or phone`); that the stored hash is not the plain password and verifies with `verify_password`; `StaffEnrollmentOut` optional timestamps and `photo_url` aliasing from `photo`; client validators `validatePhoneMessage`, `isValidEmail`, PF and UAN regexes (currently local to `StaffEnrollmentTable.tsx` and the mobile screen; export them before unit testing).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-02-U01 | `StaffEnrollmentCreate` without `first_name`, then without `phone`, then without `address` | ValidationError naming the missing field each time | passing |
| TC-STF-02-U02 | `phone=""` and `address=""` | ValidationError (min_length 1) | passing |
| TC-STF-02-U03 | `email="not-an-email"`; `email=None` | ValidationError for the first; the second is valid | passing |
| TC-STF-02-U04 | `account_type="Fixed"`; `"Savings"`; `"Current"` | first invalid; the others valid | passing |
| TC-STF-02-U05 | Gender conversion with `"male"`, `"FEMALE"`, `"Other"`, `"X"` | Male, Female, Other, then HTTPException 400 "Invalid gender value: X. ..." | passing |
| TC-STF-02-U06 | Username selection for (email `a@b.co`, phone `9876500010`) and (no email, same phone) | `a@b.co`; `9876500010` | passing |
| TC-STF-02-U07 | The stored `password_hash` for a new staff account | differs from the plain temporary password and `verify_password(plain, hash)` is true | passing |
| TC-STF-02-U08 | `StaffEnrollmentOut.model_validate` on an ORM row whose `photo` is `/media/t/staff/photos/x.png` | `photo_url` equals that path; `created_at` and `updated_at` are None | passing |
| TC-STF-02-U09 | Web `validatePhoneMessage` for "", "98765", "98765432101", "98765abcde", "9876543210" | "" (optional branch), "Number is less than 10 digits - you entered 5. ...", "Number exceeds 10 digits - you entered 11. ...", "Phone number must contain digits only", "" | blocked: validatePhoneMessage is local to web/src/components/staff/StaffEnrollmentTable.tsx and not exported |
| TC-STF-02-U10 | PF regex with "AP/HYD/12345", "AP-HYD-12345", "AP"; UAN regex with "123456789012", "12345678901", "12345678901a" | valid, invalid, invalid; valid, invalid, invalid | blocked: the PF and UAN regexes are local to web/src/components/staff/StaffEnrollmentTable.tsx and not exported |
| TC-STF-02-U11 | Decimal serialisation of `current_salary=Decimal("50000.00")` in `StaffEnrollmentOut` | JSON string "50000.00" | passing |
| TC-STF-02-A01 | Admin `POST /staff/enrollment` with only `first_name "Kiran"`, `phone "9876500011"`, `address "12 MG Road"` | 200; `qualifications` `[]`; `is_active` true; users row has username `9876500011`, role `Staff`, `is_first_login` true | passing |
| TC-STF-02-A02 | Create with email `kiran.nair@qa.example` and all HR fields (work, bank, salary, PF, UAN `123456789012`) | 200; every field echoed; `current_salary` `"50000.00"`; users.username equals the email | passing |
| TC-STF-02-A03 | Create without `first_name`; without `phone`; without `address` | 422 each; loc names the field; no users row created | passing |
| TC-STF-02-A04 | `phone ""` or `address ""` | 422 | passing |
| TC-STF-02-A05 | `email "kiran@"` | 422 | passing |
| TC-STF-02-A06 | `gender "female"`; `gender "Unknown"` | 200 with gender `Female`; 400 "Invalid gender value: Unknown. Must be 'Male', 'Female', or 'Other'" and no users row left behind | passing |
| TC-STF-02-A07 | `account_type "Fixed"` | 422 | passing |
| TC-STF-02-A08 | `role_id` of the `Teacher` role | 200; users.role_id is the Teacher role | passing |
| TC-STF-02-A09 | `role_id` of the `Admin` role by a user holding only `staff:create` | 200 and an Admin login is created (documents the privilege-escalation gap) | passing |
| TC-STF-02-A10 | Tenant without a role named `Staff`, no `role_id` | 400 "Default 'Staff' role not found. Please provide a role_id." | skipped: the QA tenant has a Staff role and the shared role cannot be removed |
| TC-STF-02-A11 | Unknown `role_id` (random uuid) | 500 "Error creating staff enrollment: ..."; no users or staff row | passing |
| TC-STF-02-A12 | Unknown `designation_id` | 500 "Error creating staff enrollment: ..."; the user row is rolled back too | passing |
| TC-STF-02-A13 | Duplicate email (same email as an existing staff) | 500 "Error creating staff enrollment: ..." and no new rows | passing |
| TC-STF-02-A14 | Two staff without email and the same phone | second call returns 500 (username collision) | passing |
| TC-STF-02-A15 | Same email created in `qa_school` and `qa_school_b` | both 200 (uniqueness is per tenant) | passing |
| TC-STF-02-A16 | Boundary: first_name 100 characters; 101 characters | 200; 500 | passing |
| TC-STF-02-A17 | Boundary: phone 15 characters; 16 characters | 200; 500 (no backend length validation) | passing |
| TC-STF-02-A18 | Boundary: `current_salary 99999999.99`; `100000000` | 200; 500 (numeric overflow) | passing |
| TC-STF-02-A19 | `experience_years -1`; `uan_number "abc"`; `pf_account_number "x"` | all 200 (server does not validate them) | passing |
| TC-STF-02-A20 | Whitespace-only phone `"   "` with no email | 200 and a user with username `"   "` is created (documents the missing trim) | passing |
| TC-STF-02-A21 | Staff role (read, list only) | 403 | passing |
| TC-STF-02-A22 | Teacher, Student and Parent roles | 403 each | passing |
| TC-STF-02-A23 | No Authorization header | 401 | passing |
| TC-STF-02-A24 | Staff created in tenant A | not returned by `GET /staff/enrollments` in tenant B; token A with `cschema` B gives 403 | passing |
| TC-STF-02-A25 | Response shape of a created row | has `id`, `user_id`, `photo_url`, `qualifications`; `created_at` and `updated_at` are null; HTTP status is 200 | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-02-E01 | P1 | Web | Admin | No user with username `9876510011` exists. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "Add Staff".<br>4. Enter First Name "QA Kiran", Phone "9876510011", Address "12 MG Road".<br>5. Click "Save". | Toast "Staff enrollment created successfully"; the dialog closes; a row "QA Kiran" shows Designation "Not Assigned" and Status "Active". Stored: a login with username `9876510011`, role `Staff`, first-login flag set. | planned |
| TC-STF-02-E02 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "Add Staff".<br>4. Click "Save" without entering anything. | Inline "First name is required", "Phone is required", "Address is required"; toast "Please fill in the required fields"; the dialog stays open; nothing is created. | planned |
| TC-STF-02-E03 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. Enter First Name "QA Phone", Address "1 QA Street".<br>4. Enter Phone "98765" and click "Save".<br>5. Change Phone to "98765432101" and click "Save".<br>6. Change Phone to "98765abcde" and click "Save". | Step 4: "Number is less than 10 digits - you entered 5. Please enter exactly 10 digits"; step 5: "Number exceeds 10 digits - ..."; step 6: "Phone number must contain digits only". No staff is created. | planned |
| TC-STF-02-E04 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. Enter First Name "QA Mail", Phone "9876510012", Address "1 QA Street", Email "kiran@".<br>4. Click "Save". | Inline "Please enter a valid email address"; toast "Please fill in the required fields"; nothing is created. | planned |
| TC-STF-02-E05 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. Fill First Name "QA Pf", Phone "9876510013", Address "1 QA Street".<br>4. Open "Salary & PF"; enter UAN Number "12345"; click "Save".<br>5. Set UAN Number "123456789012" and PF Account Number "AP-HYD"; click "Save". | Step 4: toast "UAN Number must be exactly 12 digits"; step 5: toast "Invalid PF Account Number format (e.g. AP/HYD/12345)"; nothing is created. | planned |
| TC-STF-02-E06 | P2 | Web | Admin | Seeded designation "Teacher"; a JPG under 2 MB is available; no staff with email `qa.full@qa.example`. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. "Choose photo" and pick the JPG.<br>4. Enter First Name "QA Full", Last Name "Form", Email "qa.full@qa.example", Phone "9876510014", Gender "Female", Address "4 QA Street".<br>5. "Add Qualification": Level "Graduation (B.Tech / B.Sc / B.Com)", Degree / Course "B.Sc", Pass-out Year 2015.<br>6. Designation "Teacher", Department "Science", Role "Teacher".<br>7. Fill Work Experience (Previous Organization "QA Old School"), Bank Details (Bank Name "QA Bank", Account Type "Savings"), Salary and PF (Current Salary 50000).<br>8. Click "Save".<br>9. Click "View Staff Details" on the new row. | Toast "Staff enrollment created successfully" then "Photo uploaded successfully"; the View dialog "Staff Details: QA Full Form" shows the designation, department, qualification, work, bank and salary values. Signing in as the new user later shows the role Teacher. | planned |
| TC-STF-02-E07 | P3 | Web | Admin | QA data set: QA Asha Verma exists with email `qa.asha.verma@qa.example`. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. Enter First Name "QA Dup", Email "qa.asha.verma@qa.example", Phone "9876510015", Address "1 QA Street".<br>4. Click "Save". | Toast starting "Failed to create staff enrollment:" with the server error; the dialog stays open; no second staff row. | planned |
| TC-STF-02-E08 | P3 | Web | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. Fill First Name "QA Qual", Phone "9876510016", Address "1 QA Street".<br>4. "Add Qualification" and choose only a Level.<br>5. Click "Save". | Toast "Qualification Level and Degree / Course must both be filled in, or both left empty"; nothing is created. | planned |
| TC-STF-02-E09 | P2 | Web | Staff | Seeded staff. | 1. Sign in as Staff.<br>2. Open Staff > Enrollment. | The table loads with "Columns", "Export" and "View Staff Details" only; no "Add Staff", "Bulk Upload", Edit, Delete or Send icons. Teacher: the page shows "Access Denied" and "You don't have permission to view staff enrollment information." (verified 2026-10-07). | planned |
| TC-STF-02-E10 | P1 | Mobile | Admin | No user with username `9876510017` exists. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Tap "Add Staff".<br>4. Enter First Name "QA Mobile", Phone "9876510017", Address "5 QA Street".<br>5. Tap "Save". | Toast "Staff Added - New staff member enrolled successfully."; a card "QA Mobile" with "No Designation" and "Active" appears; the footer count increases by one. | planned |
| TC-STF-02-E11 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment" > "Add Staff".<br>3. Tap "Save" with an empty form. | Inline errors under First Name, Phone and Address; toast "Validation - Please fill in the required fields."; nothing is created. | planned |
| TC-STF-02-E12 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment" > "Add Staff".<br>3. Open the Joining Date picker and try to pick tomorrow.<br>4. Type tomorrow's date as DD/MM/YYYY. | The picker offers no date after today; a typed future date is rejected with an inline error. | planned |
| TC-STF-02-E13 | P2 | Mobile | Admin | TC-STF-02-E10 done. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment" > "Add Staff" and look for a Role field.<br>3. Close the sheet.<br>4. On web, open Administration user management and find the user `9876510017`. | The mobile sheet has no Role field; the user created in TC-STF-02-E10 has the role Staff. | planned |
| TC-STF-02-E14 | P3 | Mobile | Student | None. | 1. Sign in as Student.<br>2. Open `/staff` by URL.<br>3. Open `/staff/enrollment` by URL. | The hub shows no cards; the enrollment screen shows "Access Denied - You don't have permission to view staff enrollment data". | planned |

Implemented in: backend/tests/unit/staff/test_enrollment.py (U01-U08, U11); web cases blocked.

---

## F03 First login of a new staff account

**Purpose.** A newly enrolled staff member signs in with the temporary password and is forced to choose a personal password before getting a session.

**Roles and permissions.** No permission is needed to log in. The forced change applies to roles `Staff`, `Teacher`, `Student` and `Parent` when `users.is_first_login = TRUE`. Admin and custom roles are never forced. Endpoints are owned by the auth module (`docs/features/auth.md`); the cases here cover the enrollment-driven path.

**Preconditions.** A staff member created by F02 (or F08) whose password has not been changed; an academic year exists (login requires `academic_year_id`).

**Steps, web.**
1. Open `/login` ("Welcome!"). Choose the "Academic Year" (for example "2026-2027 (Current)"), enter "Username / Admission Number" (placeholder "Username or Admission Number"; the staff email, or the phone number when there is no email) and "Password" (placeholder "Enter Password"; the temporary password), click "Login".
2. The app opens "Set Your Password". Enter "New Password" (placeholder "Minimum 8 characters") and "Confirm Password" (placeholder "Re-enter your password"), click "Set Password". The web page has no client-side match check; a mismatch is reported by the server ("Passwords do not match").
3. On success the user is signed in and lands on the dashboard. If the change token has expired, is invalid or is missing (for example `/set-password` opened directly) the page shows "Session expired or invalid - Please log in again with your temporary password." with the button "Back to Login".

**Steps, mobile.**
1. Login screen: "Enter organization name" -> "Continue", then "Enter your username" (email or phone), "Enter your password" (the temporary password), "Academic Year", and "Sign In".
2. "Set New Password" ("Please set a new password for your account"): "New Password" (placeholder "Enter new password (min 8 characters)") and "Confirm New Password" (placeholder "Re-enter your new password"), then "Set Password". Client checks show a red banner: "New password is required", "New password must be at least 8 characters", "Please confirm your new password", "New passwords do not match". On success the user is signed in.

**Expected results.** Login with the temporary password returns `{requires_password_change: true, change_password_token, academic_year_*}` and no access token. Set-password returns a full login response (user, role, menu, permissions, `entity_id` = the staff id, access and refresh tokens). `is_first_login` becomes false; the temporary password stops working.

**API endpoints.**
- `POST /auth/login` `{username, password, academic_year_id}` with header `cschema`.
- `POST /auth/staff/set-password` `{change_password_token, new_password (min 8), confirm_password}`.

**Rules and validations.**
1. The change token lives 15 minutes and is valid once (a second use is 400).
2. `new_password` min length 8; `confirm_password` must match (400 "Passwords do not match").
3. Login accepts username, then email, then staff phone (so a phone-only staff member logs in with the phone).
4. `staff.is_active = false` does not block login; only `users.is_active = false` does (401).
5. Editing a staff member's email or phone (F07) does not change the login identifier.

**Error and edge cases.** Wrong password 401 "Invalid Credentials"; inactive user 401; expired or tampered token 401; reused token 400; mismatched passwords 400; password shorter than 8 characters 422; wrong tenant header 404 or 403.

**Unit-testable logic.** Identifier lookup order; `requires_password_change` decision for the role and flag combinations; `SetPasswordRequest` min length; web `SetPasswordPage` token-missing branch.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-03-U01 | `SetPasswordRequest` with `new_password` of 7 and of 8 characters | invalid; valid | passing |
| TC-STF-03-U02 | Role and flag matrix for the forced-change decision: (Staff, true), (Teacher, true), (Admin, true), (Staff, false), (custom role, true) | forced, forced, not forced, not forced, not forced | blocked: the forced-change decision is inline in MultiTenantAuthService.login; extract a helper to test it without the full login chain |
| TC-STF-03-U03 | Web `SetPasswordPage` with an error message containing "expired" | `change_password_token` removed from sessionStorage and the "Session expired or invalid" card shown | blocked: logic is inline in the SetPasswordPage component (needs rendering and sessionStorage) |
| TC-STF-03-A01 | Login as the new staff (email) with the temporary password | 200 `requires_password_change true`, `change_password_token` present, no `access_token` | passing |
| TC-STF-03-A02 | Same with a phone-only staff using the phone number | 200 with `requires_password_change true` | passing |
| TC-STF-03-A03 | `POST /auth/staff/set-password` with a valid token and an 8-character password | 200 full login response; `entity_id` equals the staff id; `role.name` is `Staff` | passing |
| TC-STF-03-A04 | Reuse the same token | 400 | passing |
| TC-STF-03-A05 | Password and confirmation differ | 400 "Passwords do not match" | passing |
| TC-STF-03-A06 | `new_password` of 7 characters | 422 | passing |
| TC-STF-03-A07 | Expired or malformed token | 401 | passing |
| TC-STF-03-A08 | Login again with the new password; with the old temporary password | 200 without `requires_password_change`; 401 | passing |
| TC-STF-03-A09 | Enroll with `role_id` of Admin, then log in with the temporary password | 200 with an access token immediately (Admin is not forced) | passing |
| TC-STF-03-A10 | Set `staff.is_active=false` via PATCH, then log in | login still succeeds (staff flag does not block) | passing |
| TC-STF-03-A11 | Set `users.is_active=false` (admin user management), then log in | 401 | passing |
| TC-STF-03-A12 | Login with the wrong academic year or missing `academic_year_id` | 400 or 422 | passing |
| TC-STF-03-A13 | Tenant isolation: the same email exists in tenant B | login in tenant A with tenant A header never authenticates the tenant B user; header `cschema` of tenant B with tenant A credentials returns 401 | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-03-E01 | P1 | Web | Staff | TC-STF-02-E01 done (QA Kiran, phone `9876510011`, password never changed); signed out. | 1. Open `/login`.<br>2. Choose "Academic Year" "2026-2027 (Current)".<br>3. Enter "Username / Admission Number" = "9876510011" and "Password" = the temporary password.<br>4. Click "Login".<br>5. On "Set Your Password" enter a new password of at least 8 characters in "New Password" and "Confirm Password".<br>6. Click "Set Password". | Step 4 opens "Set Your Password" instead of the dashboard; step 6 signs the user in and opens the dashboard with role Staff. The temporary password no longer works. | planned |
| TC-STF-03-E02 | P3 | Web | Staff | A new staff account whose password was never changed (enroll one as in TC-STF-02-E01 with phone "9876510018"); signed out. | 1. Log in with phone "9876510018" and the temporary password.<br>2. On "Set Your Password" enter two different passwords of 8 or more characters.<br>3. Click "Set Password". | An error banner shows "Passwords do not match"; the user stays on the page and is not signed in. | planned |
| TC-STF-03-E03 | P3 | Web | Staff | Signed out; no pending password change. | 1. Open `/set-password` by URL. | Card "Session expired or invalid" with "Please log in again with your temporary password." and the button "Back to Login" (verified 2026-10-07). | planned |
| TC-STF-03-E04 | P2 | Web | Staff | TC-STF-03-E01 done. | 1. Log out.<br>2. Log in with "9876510011" and the new password. | The dashboard opens directly, without "Set Your Password". | planned |
| TC-STF-03-E05 | P2 | Mobile | Staff | A new staff account whose password was never changed (enroll one with phone "9876510019"). | 1. Open the mobile login.<br>2. Enter the organization name and tap "Continue".<br>3. Enter username "9876510019" and the temporary password; choose the Academic Year.<br>4. Tap "Sign In".<br>5. On "Set New Password" enter a new password twice.<br>6. Tap "Set Password". | Step 4 opens "Set New Password"; step 6 signs the user in; the Staff tab shows only the cards the Staff role may open (Staff Enrollment, Designations). | planned |
| TC-STF-03-E06 | P3 | Mobile | Staff | Same as TC-STF-03-E05, before step 5. | 1. On "Set New Password" enter "short12" in both fields.<br>2. Tap "Set Password".<br>3. Enter two different 8-character passwords and tap "Set Password". | Step 2: banner "New password must be at least 8 characters"; step 3: banner "New passwords do not match"; no request is sent. | planned |

Implemented in: backend/tests/unit/staff/test_enrollment.py (U01).

---

## F04 Staff qualifications

**Purpose.** Record the education history of a staff member: many qualifications per person, each with a level, a degree or course, pass-out year, percentage and university.

**Roles and permissions.**
- Add and edit: `staff:update`. List: `staff:read`. Delete: `staff:delete`.
- Surfaced inside the staff enrollment dialog (Create or Edit) and the View dialog; no separate menu entry.

**Preconditions.** An existing staff member (F02). The user holds the permission for the action.

**Steps, web.**
1. Staff -> Staff Enrollment -> "Add Staff" or the Edit icon ("Edit Staff") of a row.
2. In the section "Qualifications" click "Add Qualification". Each block "Qualification N" has: "Level" (Below Graduation (Inter / Diploma), Graduation (B.Tech / B.Sc / B.Com), Post Graduation (M.Tech / MBA), PhD (Doctorate)), "Degree / Course" (creatable list filtered by level, for example B.Tech, MBA, or type a new value with "Add ..."), "Pass-out Year", "Percentage / CGPA", "University / Board".
3. The trash icon on a block removes it. Click "Save" on the dialog.
4. On create, each filled block is posted after the staff row exists. On edit, removed blocks are deleted, existing blocks are updated and new blocks are added, one request each, after the staff PATCH succeeds. Blocks where both Level and Degree are empty are skipped; one filled and one empty blocks the save with the toast "Qualification Level and Degree / Course must both be filled in, or both left empty".
5. The View dialog ("View Staff Details") lists qualifications with a level badge, name, university, "Year: <y>" and percentage with two decimals.

**Steps, mobile.**
1. Staff hub -> "Staff Enrollment" -> Add Staff or "Edit". Section "Qualifications" with the same fields (Level, Degree / Course, Pass-out Year, Percentage / CGPA, University / Board).
2. On Edit the existing qualifications are loaded with `GET /staff/{id}/qualifications` and can be changed or removed. Failures during the follow-up calls show the toast "Qualifications - Staff saved but some qualifications failed to save. Try again from edit."
3. The View sheet has a "Qualifications" section.

**Expected results.** Rows in `staff_qualifications` linked to the staff member; they are returned inside `GET /staff/enrollment/{id}` and `GET /staff/` and removed when the staff member is deleted (cascade).

**API endpoints.**
- `POST /staff/{staff_id}/qualifications` body `{level, name, passed_out_year?, percentage?, university?}` -> 201 `StaffQualificationOut`.
- `GET /staff/{staff_id}/qualifications` -> list.
- `PUT /staff/{staff_id}/qualifications/{qualification_id}` partial body -> `StaffQualificationOut`.
- `DELETE /staff/{staff_id}/qualifications/{qualification_id}` -> `{"detail": "Qualification deleted successfully"}`.

**Rules and validations.**
1. `level` is one of `Below Graduation`, `Graduation`, `Post Graduation`, `PhD` (422 otherwise). The enum mapping uses `values_callable`, so the database stores the labels.
2. In the create schema `level` and `name` are optional, but both columns are NOT NULL in the database: omitting either ends in an integrity error (not a clean 422).
3. `percentage` is `Numeric(5,2)` (up to 999.99; values above 100 are accepted; 1000 overflows). It is returned as a string such as `"78.50"`.
4. `passed_out_year` is a free integer; the web input uses `min 1950`, `max 2100` only as HTML hints.
5. The qualification must belong to the staff id in the path, otherwise 404.
6. The free-text `staff.qualification` field (comma list in the web form, duplicates removed) is separate from this table.
7. Row-level security keeps qualifications per tenant.

**Error and edge cases.** Unknown staff id on add or list: 404 "Staff not found". Unknown qualification id, or one that belongs to another staff member: 404 "Qualification not found". Invalid level: 422. Missing `level` or `name`: integrity error (the middleware maps `IntegrityError` to 400; record the observed status). Missing token 401, missing permission 403.

**Unit-testable logic.** `QualificationLevelEnum` values and `values_callable` mapping; `StaffQualificationCreate/Update/Out` schemas (percentage `Decimal`, optional fields); web pairing rule (`Boolean(level) !== Boolean(name.trim())`) and the `localQuals`/`removedQualIds` diff logic once extracted; bulk-upload `_map_qualification_level` aliases.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-04-U01 | `QualificationLevelEnum` values | "Below Graduation", "Graduation", "Post Graduation", "PhD" | passing |
| TC-STF-04-U02 | `StaffQualificationCreate(level="Masters")` | ValidationError | passing |
| TC-STF-04-U03 | `StaffQualificationOut` with `percentage=Decimal("78.50")` (the value a `Numeric(5,2)` row returns) | serialises as the string "78.50" | passing |
| TC-STF-04-U04 | Web pairing rule for (level "", name ""), ("Graduation", ""), ("", "B.Tech"), ("PhD", "Ph.D") | not unpaired, unpaired, unpaired, not unpaired | blocked: the pairing rule is inline in StaffEnrollmentTable.tsx |
| TC-STF-04-U05 | `update_staff_qualification` with `{percentage: 80}` only | only `percentage` changes (`exclude_unset`) | passing |
| TC-STF-04-A01 | `POST /staff/{id}/qualifications` `{level:"Graduation", name:"B.Sc", passed_out_year:2015, percentage:78.5, university:"Osmania University"}` | 201; `percentage` "78.50"; `staff_id` equals the path id | passing |
| TC-STF-04-A02 | One add per level value | 201 for all four levels; the list returns them | passing |
| TC-STF-04-A03 | `level:"Masters"` | 422 | passing |
| TC-STF-04-A04 | Body without `level`; body without `name` | not 2xx (integrity error mapped by the middleware, expected 400); no row created | passing |
| TC-STF-04-A05 | Boundary: percentage 100.00, 999.99, 1000 | 201, 201, non-2xx (numeric overflow) | passing |
| TC-STF-04-A06 | Unknown staff id on POST and GET | 404 "Staff not found" | passing |
| TC-STF-04-A07 | `GET /staff/{id}/qualifications` with two rows | 200; two items with the documented fields | passing |
| TC-STF-04-A08 | `PUT` with `{percentage:82}` | 200; only percentage changed | passing |
| TC-STF-04-A09 | `PUT` and `DELETE` using a qualification id that belongs to another staff member | 404 "Qualification not found" | passing |
| TC-STF-04-A10 | `DELETE` own qualification | 200 `{"detail":"Qualification deleted successfully"}`; a later GET no longer lists it | passing |
| TC-STF-04-A11 | Delete the staff member | its qualifications are gone (cascade) | passing |
| TC-STF-04-A12 | Staff role (read, list): GET 200; POST, PUT, DELETE 403 | as stated | passing |
| TC-STF-04-A13 | Teacher, Student, Parent on all four endpoints | 403 | passing |
| TC-STF-04-A14 | Admin on all four endpoints | 2xx | passing |
| TC-STF-04-A15 | No token | 401 on all four | passing |
| TC-STF-04-A16 | Tenant B token on a tenant A staff id | 404 "Staff not found" | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-04-E01 | P1 | Web | Admin | No user with username `9876510020` exists. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. Enter First Name "QA Quals", Phone "9876510020", Address "6 QA Street".<br>4. "Add Qualification": Level "Graduation (B.Tech / B.Sc / B.Com)", Degree / Course "B.Tech", Pass-out Year 2016, Percentage / CGPA 72.5.<br>5. "Add Qualification": Level "Post Graduation (M.Tech / MBA)", Degree / Course "MBA", Pass-out Year 2018, Percentage / CGPA 68.<br>6. Click "Save".<br>7. Click "View Staff Details" on the new row. | Toast "Staff enrollment created successfully"; the View dialog lists both qualifications with level badges, "Year: 2016" and "Year: 2018", and "72.50%" and "68.00%". | planned |
| TC-STF-04-E02 | P2 | Web | Admin | TC-STF-04-E01 done. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment; click "Edit Staff" on "QA Quals".<br>3. Remove the MBA block with its trash icon.<br>4. Change the B.Tech percentage to 75.<br>5. "Add Qualification": Level "PhD (Doctorate)", Degree / Course "Ph.D", Pass-out Year 2022.<br>6. Click "Save".<br>7. Click "View Staff Details". | Toast "Staff enrollment updated successfully"; the View dialog shows B.Tech with "75.00%" and Ph.D; MBA is gone. | planned |
| TC-STF-04-E03 | P3 | Web | Admin | TC-STF-04-E01 done. | 1. Sign in as Admin.<br>2. Open "Edit Staff" on "QA Quals".<br>3. "Add Qualification" and choose only a Level.<br>4. Click "Save". | Toast "Qualification Level and Degree / Course must both be filled in, or both left empty"; nothing is saved (View still shows the old set). | planned |
| TC-STF-04-E04 | P3 | Web | Admin | TC-STF-04-E01 done. | 1. Sign in as Admin.<br>2. Open "Edit Staff" on "QA Quals".<br>3. "Add Qualification": Level "Below Graduation (Inter / Diploma)"; in Degree / Course type "D.Pharm" and pick "Add ...".<br>4. Click "Save".<br>5. Click "View Staff Details". | The qualification "D.Pharm" is saved and shown in the View dialog. | planned |
| TC-STF-04-E05 | P2 | Mobile | Admin | TC-STF-04-E01 done. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Tap "Edit" on "QA Quals".<br>4. Check that the saved qualifications are loaded in "Qualifications".<br>5. Change one Percentage / CGPA to 80.<br>6. Tap "Save".<br>7. Tap "View". | The existing qualifications appear in the edit sheet; toast "Updated - Staff member updated successfully."; the View sheet shows the new percentage. | planned |
| TC-STF-04-E06 | P3 | Mobile | Admin | A way to make the qualification call fail (for example the API stopped after the staff save, or a network block on `/qualifications`). | 1. Sign in as Admin.<br>2. Open "Edit" on a staff card.<br>3. Add a qualification.<br>4. Make the qualification request fail and tap "Save". | Toast "Qualifications - Staff saved but some qualifications failed to save. Try again from edit."; the staff fields are saved. | planned |

Implemented in: backend/tests/unit/staff/test_qualifications_photo.py.

---

## F05 Staff photo

**Purpose.** Attach, replace or remove a photo of a staff member.

**Roles and permissions.** `staff:update` for upload and removal. The photo file itself is served at `/media/...`, but a plain browser request (an `<img>` tag) carries no `cschema` header or token and is rejected with 400 by the tenant middleware (`docs/modules/staff.md`, Known gaps), so saved photos do not render in the clients.

**Preconditions.** An existing staff member. For a new staff member the photo is uploaded in a second call after F02 succeeds.

**Steps, web.**
1. Edit a row ("Edit Staff") or open "Add Staff". The block at the top of the dialog shows a round photo or a placeholder, a "Staff Photo" label ("Change Photo" when editing) and the button "Choose photo" with the hint "JPG, PNG or WebP - max 2 MB".
2. Picking a file larger than 2 MB shows the toast "Photo must be under 2 MB" and nothing is sent. When editing, a valid file is uploaded at once (toast "Photo uploaded successfully"); when creating it is held until "Save".
3. The small red X on the photo ("Remove photo") deletes a saved photo (toast "Photo removed successfully") or discards a pending one.

**Steps, mobile.**
1. Staff Enrollment -> Add Staff or Edit. "Upload Photo" (or "Change Photo") opens the file picker; "Remove" deletes. A photo over 2 MB shows the toast "Photo Too Large - Photo must be under 2 MB."
2. A new staff member's photo is uploaded after the save; failure shows "Photo Upload - Staff saved but photo upload failed. Try again from edit." The View sheet shows the photo or the initials.

**Expected results.** The file is written to `media/<tenant_id>/staff/photos/<staff_id>.<ext>` and `staff.photo` stores `/media/<tenant_id>/staff/photos/<staff_id>.<ext>`; responses expose it as `photo_url`. Clients prefix the API host (the `/api/v1` suffix removed). Replacing with a different extension removes the old file. Delete clears the field and removes the file.

**API endpoints.**
- `POST /staff/enrollment/{staff_id}/photo` multipart field `photo` -> `StaffEnrollmentOut`.
- `DELETE /staff/enrollment/{staff_id}/photo` -> `{"detail": "Staff photo deleted successfully"}`.
- `GET /media/<tenant_id>/staff/photos/<file>` (static, public).

**Rules and validations.**
1. Allowed extensions (case-insensitive): `.jpg`, `.jpeg`, `.png`, `.webp`. Only the file name is checked, not the content type.
2. Maximum 2 MiB: 2097152 bytes is accepted, 2097153 is rejected (400 "File size must not exceed 2 MB"). The extension check runs before the size check.
3. The file name is fixed per staff member, so a re-upload with the same extension keeps the same URL and browsers may show the old image.
4. Photos are not protected by a token, but a request without a `cschema` header gets 400 from the tenant middleware, so a plain `<img>` request fails (see the module doc).
5. Both clients enforce the 2 MB limit before uploading.

**Error and edge cases.** Unknown staff id: 404 "Staff not found". Wrong extension: 400 "Only jpg, png, webp files are allowed". Missing `photo` part: 422. Delete when there is no photo: 404 "No photo to delete". Missing token 401; missing `staff:update` 403.

**Unit-testable logic.** Extension allow-list; size boundary; path construction (`/media/<tenant>/staff/photos/<id>.<ext>`); removal of the old file when the extension changes; client-side 2 MB check (`MAX_PHOTO_BYTES`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-05-U01 | Extension check for `a.JPG`, `a.jpeg`, `a.png`, `a.webp`, `a.gif`, `a` | accepted for the first four; 400 for `.gif` and for no extension | passing |
| TC-STF-05-U02 | Size check with 2097152 and 2097153 bytes | accepted; HTTPException 400 "File size must not exceed 2 MB" | passing |
| TC-STF-05-U03 | Resulting `photo_url` for staff id X, tenant T, file `p.PNG` | `/media/T/staff/photos/X.png` | passing |
| TC-STF-05-U04 | Existing photo `.../X.png`, new upload `X.jpg` | the old file is removed, `photo` is updated | passing |
| TC-STF-05-A01 | `POST` a 100 KB png | 200 `StaffEnrollmentOut`; `photo_url` matches `/media/<tenant_id>/staff/photos/<id>.png`; the file exists on disk | passing |
| TC-STF-05-A02 | `GET` the returned `photo_url` without an Authorization header | 200 image bytes (public media, documents the privacy gap) | known defect: D-STF-04: GET /media/... |
| TC-STF-05-A03 | `.gif` file; text file renamed `.png` | 400 "Only jpg, png, webp files are allowed"; the renamed text file is accepted (no content check) | passing |
| TC-STF-05-A04 | File of exactly 2097152 bytes; of 2097153 bytes | 200; 400 "File size must not exceed 2 MB" | passing |
| TC-STF-05-A05 | Upload png then jpg for the same staff | the png file is deleted; `photo_url` ends with `.jpg` | passing |
| TC-STF-05-A06 | Upload without the `photo` part | 422 | passing |
| TC-STF-05-A07 | Unknown staff id on POST and DELETE | 404 "Staff not found" | passing |
| TC-STF-05-A08 | `DELETE` with a photo; `DELETE` again | 200 `{"detail":"Staff photo deleted successfully"}`; second returns 404 "No photo to delete" | passing |
| TC-STF-05-A09 | Admin 2xx; Staff, Teacher, Student, Parent roles | 403 for the four non-admin roles on POST and DELETE | passing |
| TC-STF-05-A10 | No token | 401 | passing |
| TC-STF-05-A11 | Photo uploaded in tenant A, staff id used from tenant B | 404 "Staff not found" | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-05-E01 | P1 | Web | Admin | QA data set (QA Asha Verma); a JPG of about 200 KB. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment; click "Edit Staff" on "QA Asha Verma".<br>3. Click "Choose photo" and pick the JPG. | Toast "Photo uploaded successfully"; the staff record now has a `photo_url`; the round image shows the photo. | blocked: saved photos do not render because `/media` requests without a cschema header get 400 (docs/modules/staff.md Known gaps) |
| TC-STF-05-E02 | P3 | Web | Admin | QA data set; an image file larger than 2 MB (about 3 MB). | 1. Sign in as Admin.<br>2. Open "Edit Staff" on "QA Asha Verma".<br>3. Click "Choose photo" and pick the 3 MB file. | Toast "Photo must be under 2 MB"; no upload request; the photo is unchanged. | planned |
| TC-STF-05-E03 | P2 | Web | Admin | A JPG under 2 MB; no user with username `9876510021`. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Add Staff".<br>3. "Choose photo" and pick the JPG.<br>4. Enter First Name "QA Photo", Phone "9876510021", Address "7 QA Street".<br>5. Click "Save".<br>6. Click "View Staff Details" on the new row. | Toasts "Staff enrollment created successfully" and "Photo uploaded successfully"; the View dialog shows the photo. | blocked: saved photos do not render because `/media` requests without a cschema header get 400 (docs/modules/staff.md Known gaps) |
| TC-STF-05-E04 | P2 | Web | Admin | TC-STF-05-E01 or TC-STF-05-E03 done (staff with a saved photo). | 1. Sign in as Admin.<br>2. Open "Edit Staff" on that staff member.<br>3. Click the red X ("Remove photo"). | Toast "Photo removed successfully"; the placeholder icon returns; `photo_url` is empty after reload. | planned |
| TC-STF-05-E05 | P2 | Mobile | Admin | QA data set; an image under 2 MB available to the browser. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment"; tap "Edit" on "QA Asha Verma".<br>3. Tap "Upload Photo" and pick the image; tap "Save".<br>4. Tap "Edit" again and tap "Remove"; tap "Save". | After step 3 the avatar shows the photo; after step 4 the initials show again. | blocked: saved photos do not render because `/media` requests without a cschema header get 400 (docs/modules/staff.md Known gaps) |
| TC-STF-05-E06 | P3 | Mobile | Admin | QA data set; an image larger than 2 MB. | 1. Sign in as Admin.<br>2. Open "Edit" on "QA Asha Verma".<br>3. Tap "Upload Photo" and pick the large image. | Toast "Photo Too Large - Photo must be under 2 MB."; nothing is uploaded. | planned |

Implemented in: backend/tests/unit/staff/test_qualifications_photo.py.

---

## F06 Staff list, search and detail

**Purpose.** Find and inspect staff members: a searchable table, a read-only detail view, and filtered lists used by other screens.

**Roles and permissions.**
- Table and `GET /staff/enrollments`, `GET /staff/`, `GET /staff/by-designation`: `staff:list`. Detail `GET /staff/enrollment/{id}`: `staff:read`.
- Web: page `/staff/enrollment` is guarded by `staff:list`; the View icon needs `staff:read`. Mobile hub card needs `staff` list or read.

**Preconditions.** Staff exist (F02). The user holds the grants above (Admin and Staff in the default seed; Teacher has no `staff` grant).

**Steps, web.**
1. Staff -> Staff Enrollment. The table "Staff Enrollment" shows S.No., Name (with a gender badge), Contact (email and phone), Designation (with the free-text qualification), Department and Status (Active or Inactive), and Actions.
2. "Search staff..." filters by name, designation, department or email. The headers Name, Designation and Department sort (asc, desc, off). "Columns" toggles columns (at least one stays). "Export" -> "Export to CSV" or "Export to Excel" writes `staff_enrollments_data.csv` / `.xlsx` for the filtered, sorted rows. Pagination: "Previous", "Next", "Rows per page" 5, 10, 20, 50 (default 5) and a range label.
3. The View icon ("View Staff Details") opens "Staff Details: <name>" using a fresh `GET /staff/enrollment/{id}`: photo, Basic, Contact, Professional, Account & Status, Qualifications, Work Experience, Bank Details, Salary & PF. "Created" and "Last Updated" show a dash because the table has no timestamps. A staff member without a joining date shows "Joining Date: 1/1/1970" (observed 2026-10-07; mobile shows "Not specified"). The footer has "Close" and "Edit Staff" (opens the edit dialog, needs `staff:update`).
4. The Send icon ("Send Welcome/Recruiting Message") on each row is the QuickSend button (COM F04).

**Steps, mobile.**
1. Staff hub -> "Staff Enrollment". Cards list name, designation ("No Designation" when empty), department, contact and an Active or Inactive badge, with the buttons "View", "Edit" and "Delete" (Edit and Delete only with the grants); "Search staff..." filters; "Columns" and "Export" (CSV, Excel) mirror the web; the footer shows "N staff member(s)".
2. "View" opens a bottom sheet with the same sections plus "User ID", loaded from `GET /staff/enrollment/{id}`, and the buttons "Close" and "Edit Staff". Pull to refresh reloads.
3. `app/staff/[id].tsx` (a separate detail screen titled "Staff Detail") exists but no screen navigates to it.

**Expected results.** Lists contain every staff row of the tenant, active and inactive. Clients show only their tenant's staff.

**API endpoints.**
- `GET /staff/enrollments` -> `[StaffEnrollmentOut]` (all rows, no paging).
- `GET /staff/enrollment/{staff_id}` -> `StaffEnrollmentOut` (with `qualifications`, `designation_id`, `photo_url`).
- `GET /staff/?gender=Male|Female|Other` -> `[StaffOut]` (with `designation_obj {id,title}`, `qualifications`, `photo_url`; no `designation_id`). Ignores `is_active`, `skip`, `limit`.
- `GET /staff/by-designation?designation_id=<uuid>` -> staff of that designation, all staff when the parameter is omitted.

**Rules and validations.**
1. Two response shapes: `StaffOut` (list) has `designation_obj` and no `designation_id`; `StaffEnrollmentOut` has `designation_id` and no title. Clients map the right one.
2. `created_at` and `updated_at` are always null.
3. Salary and percentage decimals arrive as strings.
4. `GET /staff/` filters only by gender; `is_active=true` sent by the clients is ignored, so inactive staff are returned and appear in attendance rosters and communication staff pickers.
5. `GET /staff/by-designation` has no response model: it returns the raw ORM rows. Because the `user` relationship is loaded, the nested `user` object includes `password_hash` (defect D-STF-02, verified by encoding a loaded `Staff` with FastAPI's `jsonable_encoder`). Fixed (2026-10-02): the route now declares `response_model=list[StaffOut]`, which has no `user` field.
6. All reads are tenant scoped through row-level security.

**Error and edge cases.** Unknown id on detail: 404 "Staff not found"; non-UUID id: 422. `gender=Unknown`: 422. `designation_id` not a UUID: 422; a valid but unknown id returns `[]`. Teacher, Student and Parent: 403 (default seed). Missing token 401. An empty tenant returns `[]` and the clients show "No staff enrollments found" (web) or "No staff members yet" (mobile).

**Unit-testable logic.** `StaffOut` versus `StaffEnrollmentOut` field sets; `get_staff_list_by_gender` and `get_staff_details_by_designation` statement building; web `filteredData` and `sortedData` (name, designation, department), pagination range text, CSV escaping (`replace(/"/g,'""')`), column toggle keeping at least one column; mobile `filteredStaff`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-06-U01 | Field set of `StaffOut` and `StaffEnrollmentOut` | `StaffOut` has `designation_obj` and not `designation_id`; `StaffEnrollmentOut` the reverse | passing |
| TC-STF-06-U02 | `jsonable_encoder` of a `Staff` object with a loaded `user` (the by-designation path) | encoding the raw ORM row still contains `password_hash`, which is why the route now filters through `StaffOut` | passing (D-STF-02 fixed 2026-10-02) |
| TC-STF-06-U03 | Web `filteredData` for query "dri" over names, designation titles, departments and emails | only matching rows, case-insensitive | blocked: filteredData is inline in StaffEnrollmentTable.tsx |
| TC-STF-06-U04 | Web column toggle: deselect all but one, then try to deselect the last | one column always remains | blocked: column toggle is inline in StaffEnrollmentTable.tsx |
| TC-STF-06-U05 | Web CSV export of a name containing a double quote | quote doubled inside the quoted cell | blocked: CSV export is inline in StaffEnrollmentTable.tsx |
| TC-STF-06-U06 | Pagination range text for 23 rows, page size 5, page 5 | "21-23 of 23" | blocked: range text is inline in StaffEnrollmentTable.tsx |
| TC-STF-06-A01 | Admin `GET /staff/enrollments` | 200 array including active and inactive staff; each item has `designation_id`, `qualifications`, `photo_url`; `created_at` null | passing |
| TC-STF-06-A02 | `GET /staff/enrollment/{id}` | 200 `StaffEnrollmentOut` with qualifications and string decimals | passing |
| TC-STF-06-A03 | Unknown id; non-UUID id | 404 "Staff not found"; 422 | passing |
| TC-STF-06-A04 | `GET /staff/` | 200 `[StaffOut]`; items carry `designation_obj {id,title}` and no `designation_id` | passing |
| TC-STF-06-A05 | `GET /staff/?gender=Female`; `?gender=Unknown` | only female staff; 422 | passing |
| TC-STF-06-A06 | `GET /staff/?is_active=true&skip=0&limit=1` | still returns every staff including inactive (parameters ignored) | passing |
| TC-STF-06-A07 | `GET /staff/by-designation?designation_id=<Teacher id>` | only Teacher staff | passing |
| TC-STF-06-A08 | Same call without the parameter; with an unknown valid uuid; with `abc` | all staff; `[]`; 422 | passing |
| TC-STF-06-A09 | Inspect the by-designation response body | does not contain `password_hash` (fixed 2026-10-02) | passing |
| TC-STF-06-A10 | Staff role (read, list): all four endpoints | 200 | passing |
| TC-STF-06-A11 | Teacher, Student, Parent on all four endpoints | 403 | passing |
| TC-STF-06-A12 | No token | 401 on all four | passing |
| TC-STF-06-A13 | Tenant isolation: tenant A staff absent from tenant B on `/enrollments`, `/`, `/by-designation`; detail by id returns 404 in B | as stated | passing |
| TC-STF-06-A14 | Token of tenant A with header `cschema: qa_school_b` | 403 | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-06-E01 | P1 | Web | Admin | Seeded staff (9 rows); QA Meena Rao from the QA data set (inactive). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Read the first page.<br>4. Type "meena" in "Search staff...". | Columns S.No., Name, Contact, Designation, Department, Status, Actions; page 1 shows Lakshmi Narayana Rao (Principal, Administration, Active) and four more seeded staff with "1-5 of N"; step 4 shows QA Meena Rao with Status "Inactive". | planned |
| TC-STF-06-E02 | P2 | Web | Admin | Seeded staff Sunitha Reddy (phone 9000010002). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Type "sunitha" in "Search staff...".<br>4. Replace it with "9000010002". | Step 3 shows only Sunitha Reddy; step 4 shows no rows (phone is not searched; name, designation, department and email are). | planned |
| TC-STF-06-E03 | P3 | Web | Admin | Seeded staff. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click the "Name" header three times. | Rows sort by name ascending, then descending, then return to the unsorted order. | planned |
| TC-STF-06-E04 | P3 | Web | Admin | Seeded staff (9 rows). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Check the range label.<br>4. Click "Next", then "Previous".<br>5. Set "Rows per page" to 10. | Default 5 rows and the label "1-5 of N"; "Next" shows "6-..." and "Previous" returns; "Previous" is disabled on page 1; 10 rows per page updates the label. | planned |
| TC-STF-06-E05 | P3 | Web | Admin | Seeded staff. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Open "Columns" and untick Contact.<br>4. Open "Export" and click "Export to CSV". | The Contact column disappears; `staff_enrollments_data.csv` downloads without the email and phone columns. | planned |
| TC-STF-06-E06 | P2 | Web | Admin | Seeded staff Sunitha Reddy. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "View Staff Details" on Sunitha Reddy. | Dialog "Staff Details: Sunitha Reddy" with Designation "Teacher", Department "Academics", Bank "State Bank of India", Account Type "Savings", Created "-" and Last Updated "-"; buttons "Close" and "Edit Staff". | planned |
| TC-STF-06-E07 | P2 | Web | Staff | Seeded staff Sunitha Reddy. | 1. Sign in as Staff.<br>2. Open Staff > Enrollment.<br>3. Click "View Staff Details" on Sunitha Reddy. | The table and the View dialog work; no "Add Staff", "Bulk Upload", Edit, Delete or Send icons. | planned |
| TC-STF-06-E08 | P2 | Web | Teacher | None. | 1. Sign in as Teacher.<br>2. Open `/staff/enrollment` by URL. | "Access Denied" and "You don't have permission to view staff enrollment information." Student and Parent: same (verified 2026-10-07). | planned |
| TC-STF-06-E09 | P1 | Mobile | Admin | Seeded staff Ramesh Yadav (Driver). | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Type "ramesh" in "Search staff...".<br>4. Tap "View". | One card (Ramesh Yadav); the sheet shows Designation "Driver", Department "Transport", phone 9000010008 and "Close" and "Edit Staff". | planned |
| TC-STF-06-E10 | P3 | Mobile | Admin | Seeded staff. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Tap "Export" and choose CSV. | A file `staff_enrollments_data.csv` is produced (a browser download on Expo web). | planned |
| TC-STF-06-E11 | P2 | Mobile | Staff | Seeded staff. | 1. Sign in as Staff.<br>2. Open Staff hub > "Staff Enrollment". | Cards with only "View"; no "Add Staff", "Bulk Upload", "Edit" or "Delete" (verified 2026-10-07). | planned |
| TC-STF-06-E12 | P3 | Mobile | Admin | A tenant with no staff rows (`qa_manual` has 9 seeded staff). | 1. Sign in as Admin of that tenant.<br>2. Open Staff hub > "Staff Enrollment". | Text "No staff members yet". | blocked: needs a tenant without staff; qa_manual is seeded and qa_school holds API-run rows |
| TC-STF-06-E13 | P3 | Web | Admin | A staff member without a joining date (for example QA Kiran from TC-STF-02-E01). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "View Staff Details" on that row. | Joining Date shows "Not specified" (as on mobile). Currently shows "1/1/1970" (defect observed 2026-10-07). | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01-U02); web cases blocked.

---

## F07 Edit, deactivate and delete a staff member

**Purpose.** Correct a staff record, mark a person inactive, or remove the HR record.

**Roles and permissions.** Edit and deactivate: `staff:update`. Delete: `staff:delete`. Admin only in the default seed.

**Preconditions.** An existing staff member (F02).

**Steps, web.**
1. Staff -> Staff Enrollment -> Edit icon ("Edit Staff") or "Edit Staff" in the View dialog. The dialog "Edit Staff Enrollment" is pre-filled. Change fields (same labels and validations as F02) and "Save". Toast "Staff enrollment updated successfully".
2. To deactivate, untick "Active Staff Member" and Save. The Status column then shows "Inactive". To reactivate tick it again.
3. Delete icon ("Delete Staff") -> dialog "Delete Staff Enrollment" ("Are you sure you want to delete the enrollment for "<name>"? This action cannot be undone and will remove all associated attendance records.") -> "Cancel" or "Delete". Toast "Staff enrollment deleted successfully".
4. The edit dialog shows the hint "Mobile number is valid" under a valid Phone.

**Steps, mobile.**
1. Staff Enrollment -> card "Edit" -> sheet "Edit Staff Enrollment" (the switch "Active Staff Member" is under Account Information) -> "Save". Toast "Updated - Staff member updated successfully."
2. Card "Delete" -> confirm modal "Delete Staff Member" (`Remove "<name>"?`) -> "Delete". Toast "Deleted - Staff member removed."

**Expected results.**
- Edit updates only the sent fields on the `staff` row. The `users` row is not touched: `users.username`, `users.email` and the role stay as they were.
- Deactivate sets `staff.is_active=false` only; the person can still log in. Inactive staff drop out of the communication targets `all_staff`, `all_users` and `role_based` (COM F02) but stay in every staff list.
- Delete removes the staff row, its attendance rows and its qualifications. The `users` row remains, so the login keeps working and the same email or phone cannot be enrolled again (the create then fails with 500).

**API endpoints.**
- `PATCH /staff/enrollment/{staff_id}` body `StaffEnrollmentUpdate` (all fields optional) -> `StaffEnrollmentOut`.
- `DELETE /staff/enrollment/{staff_id}` -> `{"detail": "Staff enrollment deleted successfully"}`.

**Rules and validations.**
1. Fields sent as `first_name`, `email`, `phone`, `address` cannot be null or blank (422 "<field> is mandatory and cannot be empty"); omitted fields are untouched.
2. `email` must be a valid email; `gender` must be `Male`, `Female` or `Other` (422, case-sensitive here); `account_type` `Savings` or `Current`.
3. `role_id` is not part of the update schema and is silently dropped (the web form sends it; nothing changes).
4. Other optional fields sent as `null` overwrite the stored value with null (`exclude_unset` semantics).
5. A duplicate email or an unknown `designation_id` gives 400 "Data integrity violation - check for duplicate values or invalid references". Database outages give 503.
6. `staff.is_active` and `users.is_active` are independent.
7. `phone` and `email` edits do not update the login identifier (`users.username`).

**Error and edge cases.** Unknown id: 404 "Staff not found" (PATCH and DELETE). Missing token 401; missing permission 403. A staff member referenced elsewhere may make DELETE fail at the database (reported as an error response, not a 404).

**Unit-testable logic.** `_mandatory_fields_cannot_be_cleared` (omitted versus null versus blank); `exclude_unset` application loop; that `role_id` is absent from `StaffEnrollmentUpdate`; web `handleSubmit` payload building (`orUndef`, string to number conversion for salaries, de-duplicated comma qualification text).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-07-U01 | `StaffEnrollmentUpdate()` empty; `(first_name="")`; `(phone=None)`; `(address="  ")` | the first is valid; each of the others raises ValidationError "<field> is mandatory and cannot be empty" | passing |
| TC-STF-07-U02 | `StaffEnrollmentUpdate(role_id=...)` | the field is ignored (not in the model fields) | passing |
| TC-STF-07-U03 | `StaffEnrollmentUpdate(gender="male")`; `("Other")` | invalid (Literal is case-sensitive); valid | passing |
| TC-STF-07-U04 | `model_dump(exclude_unset=True)` for `{last_name: None}` | `{"last_name": None}` is applied, so the stored value is cleared | passing |
| TC-STF-07-U05 | Web `orUndef` for "", "  ", "x" | undefined, undefined, "x" | blocked: orUndef is a closure local to handleSubmit in StaffEnrollmentTable.tsx |
| TC-STF-07-A01 | `PATCH {department:"Science"}` | 200; only `department` changed | passing |
| TC-STF-07-A02 | `PATCH {is_active:false}` | 200 `is_active` false; the row is still in `GET /staff/enrollments` | passing |
| TC-STF-07-A03 | `PATCH {first_name:""}`, `{email:null}`, `{phone:" "}`, `{address:""}` | 422 for each | passing |
| TC-STF-07-A04 | `PATCH {email:"bad"}`, `{gender:"male"}`, `{account_type:"Fixed"}` | 422 for each | passing |
| TC-STF-07-A05 | `PATCH {designation_id: <random uuid>}` | 400 "Data integrity violation - check for duplicate values or invalid references" | passing |
| TC-STF-07-A06 | `PATCH {email: <another staff's email>}` | 400 with the same message | passing |
| TC-STF-07-A07 | `PATCH {role_id: <Admin role>}` | 200; the user's role is unchanged | passing |
| TC-STF-07-A08 | `PATCH {email:"new@qa.example"}` then login with the old email; then with the new email | the old email still logs in; the new email returns 401 (users.username unchanged) | passing |
| TC-STF-07-A09 | `PATCH {last_name:null}` | 200 `last_name` null | passing |
| TC-STF-07-A10 | `PATCH` salary `"60000.50"` as a string and `60000.5` as a number | 200 for both; stored `"60000.50"` | passing |
| TC-STF-07-A11 | `PATCH` on an unknown id | 404 "Staff not found" | passing |
| TC-STF-07-A12 | `DELETE` a staff member with 2 attendance rows and 2 qualifications | 200 `{"detail":"Staff enrollment deleted successfully"}`; GET by id 404; attendance and qualification rows gone | passing |
| TC-STF-07-A13 | After DELETE, log in with the deleted person's email | login still succeeds (orphaned user, documents the gap) | passing |
| TC-STF-07-A14 | After DELETE, enroll the same email again | 500 "Error creating staff enrollment: ..." | passing |
| TC-STF-07-A15 | `DELETE` an unknown id | 404 | passing |
| TC-STF-07-A16 | Staff role (read, list): PATCH and DELETE | 403 | passing |
| TC-STF-07-A17 | Teacher, Student, Parent: PATCH and DELETE | 403 | passing |
| TC-STF-07-A18 | Admin PATCH and DELETE | 2xx | passing |
| TC-STF-07-A19 | No token | 401 | passing |
| TC-STF-07-A20 | Tenant B token PATCH or DELETE on a tenant A id | 404 "Staff not found"; the row is unchanged | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-07-E01 | P1 | Web | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "Edit Staff" on QA Asha Verma.<br>4. In "Edit Staff Enrollment" change Department to "Science".<br>5. Click "Save". | Toast "Staff enrollment updated successfully"; the Department column shows "Science"; other fields unchanged. | planned |
| TC-STF-07-E02 | P2 | Web | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open "Edit Staff" on QA Ravi Kumar.<br>3. Untick "Active Staff Member".<br>4. Click "Save".<br>5. Repeat with the box ticked again. | After step 4 the Status column shows "Inactive"; after step 5 "Active". The person can still log in while inactive. | planned |
| TC-STF-07-E03 | P3 | Web | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open "Edit Staff" on QA Asha Verma.<br>3. Clear the Phone field.<br>4. Click "Save". | Inline "Phone is required"; toast "Please fill in the required fields"; no request; the phone is unchanged. | planned |
| TC-STF-07-E04 | P3 | Web | Admin | QA data set plus a second staff with an email (TC-STF-02-E06 done, `qa.full@qa.example`). | 1. Sign in as Admin.<br>2. Open "Edit Staff" on QA Full Form.<br>3. Change Email to "qa.asha.verma@qa.example".<br>4. Click "Save". | Toast "Failed to update staff enrollment: Data integrity violation - check for duplicate values or invalid references"; the email is unchanged. | planned |
| TC-STF-07-E05 | P1 | Web | Admin | A disposable staff row (TC-STF-02-E01 done, QA Kiran). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "Delete Staff" on QA Kiran.<br>4. Read the dialog and click "Delete". | Dialog "Delete Staff Enrollment" says 'Are you sure you want to delete the enrollment for "QA Kiran"? This action cannot be undone and will remove all associated attendance records.'; toast "Staff enrollment deleted successfully"; the row disappears. The login `9876510011` still exists (known gap). | planned |
| TC-STF-07-E06 | P3 | Web | Admin | QA data set (QA Asha Verma has role Staff). | 1. Sign in as Admin.<br>2. Open "Edit Staff" on QA Asha Verma.<br>3. Change "Role" to "Teacher".<br>4. Click "Save".<br>5. Check the user's role in Administration user management. | Toast "Staff enrollment updated successfully", but the role stays Staff (role_id is dropped on update). | planned |
| TC-STF-07-E07 | P2 | Mobile | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Tap "Edit" on QA Ravi Kumar.<br>4. Turn off "Active Staff Member".<br>5. Tap "Save". | Toast "Updated - Staff member updated successfully."; the card badge shows "Inactive". | planned |
| TC-STF-07-E08 | P2 | Mobile | Admin | A disposable staff row (TC-STF-02-E10 done, QA Mobile). | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Tap "Delete" on QA Mobile.<br>4. Confirm "Delete Staff Member" ('Remove "QA Mobile"?') with "Delete". | Toast "Deleted - Staff member removed."; the card disappears. | planned |
| TC-STF-07-E09 | P2 | Mobile | Staff | Seeded staff. | 1. Sign in as Staff.<br>2. Open Staff hub > "Staff Enrollment". | No "Edit" or "Delete" buttons on the cards (verified 2026-10-07). | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01-U04).

---

## F08 Bulk enrollment from Excel

**Purpose.** Enroll many staff members at once from a filled spreadsheet.

**Roles and permissions.** `staff:create` for both the template download and the upload. Admin only in the default seed. The "Bulk Upload" buttons (web and mobile) are hidden without `staff:create`.

**Preconditions.** Designations and roles referenced by name already exist. A role named `Staff` exists if the Role column is left empty.

**Steps, web.**
1. Staff -> Enrollment -> "Bulk Upload". The dialog "Bulk Staff Upload" says "Download the template, fill in staff rows, then upload the completed sheet." and has "Download Template", "Browse File", "Close" and "Upload".
2. "Download Template" saves `staff_bulk_upload_template.xlsx`. The Designation and Role columns carry dropdowns filled with the tenant's current designations and roles (hidden sheet "Lists"). Mandatory headers: First Name, Phone, Address.
3. "Browse File" selects an `.xlsx` or `.xls` file; "Upload" sends it. The result box shows "<n> of <total> staff member(s) created", a list "Row <r>: <name> (<email>)" and, in red, "<k> row(s) failed" with one message per row.

**Steps, mobile.**
1. Staff Enrollment -> "Bulk Upload" -> screen "Bulk Staff Upload". Step 1 "Download Template" ("Get the Excel template with the required column headers (First Name, Phone, and Address are mandatory).", button "Download Template"; on a device it opens the share sheet, on Expo web it downloads). Step 2 "Upload Filled File" ("Each row is validated and created independently - valid rows are created even if others fail."): tap "Tap to select the filled Excel file", then "Upload"; "Close" leaves. Without `staff:create` the screen shows "Access Denied - You don't have permission to view this screen. Please contact your administrator."
2. Toast "Upload Complete - <n> of <total> staff created successfully." or "Upload Finished With Errors - <n> created, <k> failed. See details below." Result chips show "<n> created", "<k> failed", "<t> total rows" and each error line.

**Expected results.** Each valid row becomes a staff member through the same path as F02 (user, staff row, hardcoded temporary password, `is_first_login`). Rows fail independently; earlier rows stay committed. The optional qualification columns create one qualification row.

**API endpoints.**
- `GET /staff/enrollment/bulk-upload/template` -> xlsx stream, header `Content-Disposition: attachment; filename=staff_bulk_upload_template.xlsx`.
- `POST /staff/enrollment/bulk-upload` multipart field `file` -> `{created:[{row,staff_id,name,email}], errors:["Row N: ..."], total_rows}`.

**Rules and validations.**
1. File name must end in `.xlsx` or `.xls` (400 "File must be an Excel (.xlsx/.xls) file"); unreadable content gives 400 "Invalid Excel file: ...".
2. The sheet named "Staff Admission" is read; if it is missing the active sheet is used. Row 1 is the header (names are trimmed). A missing First Name, Phone or Address header gives 400 "Missing required column(s): ...". Fully blank rows are skipped and not counted.
3. Per row: First Name, Phone and Address are required ("First Name is required", "Phone is required", "Address is required"). Email is optional; when present a duplicate in `users` (email or username) or `staff` fails the row ("A user with email '<e>' already exists" or "A staff member with email '<e>' already exists").
4. Designation and Role are matched by name, case-insensitively: "Designation '<x>' not found", "Role '<x>' not found". An empty Role cell means the `Staff` role. Any tenant role can be named (privilege escalation gap).
5. Qualification: Qualification Level and Degree/Course must be given together ("Qualification Level and Degree/Course must be provided together"); level accepts `Below Graduation`, `Graduation`, `Post Graduation`, `PhD` and the aliases in `QUALIFICATION_LEVEL_ALIASES`; otherwise "Invalid Qualification Level '<x>'. Must be one of: Below Graduation, Graduation, Post Graduation, PhD".
6. Dates accept `DD-MM-YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY` (tried in that order, so `03/04/2026` is 3 April); an unparseable date becomes empty without an error. Numbers (Experience, Pass-out year) and decimals (salary, percentage, thousands commas removed) that cannot be parsed become empty. An account type other than Savings or Current becomes empty.
7. Schema rules from `StaffEnrollmentCreate` still apply: a bad email gives "Row N: email - <pydantic message>", a bad gender gives "Row N: Invalid gender value: ...".
8. Columns read: First Name, Last Name, Email, Phone, Gender, Date of birth, Joining Date, Qualification, Experience, Address, Qualification Level, Degree/Course, Pass-out year, Percentage/CGPA, University/Board, Designation, Department, Role, Previous organization, Subjects dealt, From date, To date, Remarks, Bank Name, Branch, Account number, IFSC Code, Account Holder Name, Account type, Last Drawn Salary, PF Account Number, UAN Number. Current salary is not read. The template also has an "S.no" column that is ignored.
9. Username and uniqueness rules are those of F02: a duplicate phone for a row with no email fails with "Row N: Error creating staff enrollment: ...".
10. There is no row count limit.

**Error and edge cases.** Wrong extension, corrupt file, missing mandatory header: 400 and nothing is created. Empty sheet: 200 with `created: []`, `errors: []`, `total_rows: 0`. Template file missing on the server: 404 "Bulk upload template not found". Missing token 401; missing `staff:create` 403.

**Unit-testable logic.** `_clean`, `_parse_date` (four formats, datetime and date objects, garbage), `_parse_int`, `_parse_decimal`, `_map_account_type`, `_map_qualification_level`, `_build_row_lookup`, `_add_dropdown_list`, header validation, and `parse_and_bulk_create_staff_enrollments` with a mocked `create_staff_enrollment` and an in-memory workbook.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-08-U01 | `_parse_date` for "25-12-2020", "2020-12-25", "25/12/2020", "12/25/2020", "03/04/2026", "garbage", None, a datetime | 2020-12-25 for the first four; 3 April 2026 for the fifth; None; None; the date of the datetime | passing |
| TC-STF-08-U02 | `_parse_int` for "5", "5.0", "abc", ""; `_parse_decimal` for "1,50,000.50", "x" | 5, 5, None, None; Decimal("150000.50"), None | passing |
| TC-STF-08-U03 | `_map_account_type` for "savings", "CURRENT", "Fixed", "" | "Savings", "Current", None, None | passing |
| TC-STF-08-U04 | `_map_qualification_level` for "post-graduation", "PhD", "Masters" | post_graduation, phd, raises `_RowError` listing the valid values | passing |
| TC-STF-08-U05 | `_build_row_lookup` with header cells including trailing spaces ("PF Account Number ") | keys are trimmed | passing |
| TC-STF-08-U06 | Workbook without the "Staff Admission" sheet but with correct headers on the active sheet | parsed from the active sheet | passing |
| TC-STF-08-U07 | Workbook missing the "Phone" header | HTTPException 400 "Missing required column(s): Phone" | passing |
| TC-STF-08-U08 | Rows: valid, blank, missing Address, valid (mocked create) | `created` 2, `errors` ["Row 4: Address is required"], `total_rows` 3 | passing |
| TC-STF-08-U09 | `generate_blank_staff_template` with designations ["Driver","Teacher"] and roles ["Admin","Staff"] | hidden sheet "Lists" holds both columns and list validations are attached to Designation and Role | passing |
| TC-STF-08-A01 | `GET /staff/enrollment/bulk-upload/template` as Admin | 200; content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; opens with sheet "Staff Admission" and 33 header cells | passing |
| TC-STF-08-A02 | Template after creating designation "Cook" | the Designation dropdown list contains "Cook" | passing |
| TC-STF-08-A03 | Upload 3 valid rows (one with a qualification, one with Role "Teacher", one with Designation "Driver") | 200 `created` length 3, `errors` [], `total_rows` 3; each staff has the right role, designation and qualification | passing |
| TC-STF-08-A04 | Upload 1 valid row, 1 duplicate email, 1 unknown designation, 1 missing phone | 200; `created` 1; errors "Row 3: A user with email '...' already exists", "Row 4: Designation 'X' not found", "Row 5: Phone is required"; `total_rows` 4 | passing |
| TC-STF-08-A05 | Row with Role "Nonexistent" | error "Row N: Role 'Nonexistent' not found" | passing |
| TC-STF-08-A06 | Row with Qualification Level only | error "Row N: Qualification Level and Degree/Course must be provided together" | passing |
| TC-STF-08-A07 | Row with Qualification Level "Masters" | error "Row N: Invalid Qualification Level 'Masters'. Must be one of: ..." | passing |
| TC-STF-08-A08 | Row with email "bad"; row with Gender "X" | errors "Row N: email - ..." and "Row N: Invalid gender value: X. ..." | passing |
| TC-STF-08-A09 | Two rows in one file with the same email | first created; second fails with "A user with email ... already exists" | passing |
| TC-STF-08-A10 | Two phone-only rows with the same phone | first created; second error starts "Row N: Error creating staff enrollment" | passing |
| TC-STF-08-A11 | Upload `staff.csv` or `staff.txt` | 400 "File must be an Excel (.xlsx/.xls) file" | passing |
| TC-STF-08-A12 | Upload a `.xlsx` file with garbage bytes | 400 "Invalid Excel file: ..." | passing |
| TC-STF-08-A13 | Sheet without the Address header | 400 "Missing required column(s): Address" | passing |
| TC-STF-08-A14 | Header-only sheet | 200 `{created:[],errors:[],total_rows:0}` | passing |
| TC-STF-08-A15 | Date of birth cells "25-12-1990" and an Excel date cell | both stored as 1990-12-25 | passing |
| TC-STF-08-A16 | Rows created by upload log in with the temporary password and must change it | as F03 | passing |
| TC-STF-08-A17 | Staff, Teacher, Student, Parent on both endpoints | 403 | passing |
| TC-STF-08-A18 | No token | 401 on both | passing |
| TC-STF-08-A19 | Upload in tenant A; tenant B lists staff | none of the new staff visible; a Designation that exists only in tenant B fails with "not found" in tenant A | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-08-E01 | P2 | Web | Admin | Seeded designations. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment.<br>3. Click "Bulk Upload".<br>4. Click "Download Template".<br>5. Open the file. | `staff_bulk_upload_template.xlsx` downloads; sheet "Staff Admission" with the headers; the Designation dropdown lists the seeded designations (Accountant, Clerk, Driver, Principal, Teacher) and the Role dropdown lists the tenant roles. | planned |
| TC-STF-08-E02 | P1 | Web | Admin | A filled template with 2 valid rows: "QA Bulk One" (Phone 9876510031, Address "8 QA Street", Email qa.bulk1@qa.example) and "QA Bulk Two" (Phone 9876510032, Address "9 QA Street", Email qa.bulk2@qa.example). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Bulk Upload".<br>3. Click "Browse File" and pick the file.<br>4. Click "Upload".<br>5. Click "Close". | Result "2 of 2 staff member(s) created" with lines "Row 2: QA Bulk One (qa.bulk1@qa.example)" and "Row 3: QA Bulk Two (qa.bulk2@qa.example)"; the table lists both after closing. | planned |
| TC-STF-08-E03 | P2 | Web | Admin | A filled template with one valid row ("QA Bulk Three", Phone 9876510033, Address "10 QA Street") and one row without Address ("QA Bulk Bad", Phone 9876510034). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Bulk Upload".<br>3. "Browse File", pick the file, click "Upload". | "1 of 2 staff member(s) created" and, in red, "1 row(s) failed" with "Row 3: Address is required". | planned |
| TC-STF-08-E04 | P3 | Web | Admin | A `.pdf` file. | 1. Sign in as Admin.<br>2. Open Staff > Enrollment > "Bulk Upload".<br>3. Click "Browse File". | The picker filters to `.xlsx,.xls`; if the PDF is forced (file type "All files"), the upload fails with the error "File must be an Excel (.xlsx/.xls) file". | planned |
| TC-STF-08-E05 | P2 | Web | Staff | None. | 1. Sign in as Staff.<br>2. Open Staff > Enrollment. | No "Bulk Upload" button (verified 2026-10-07). | planned |
| TC-STF-08-E06 | P1 | Mobile | Admin | The 2-row file from TC-STF-08-E02 with new phones and emails (9876510035, 9876510036; qa.bulk5@qa.example, qa.bulk6@qa.example) available to the browser. | 1. Sign in as Admin.<br>2. Open Staff hub > "Staff Enrollment" > "Bulk Upload".<br>3. Tap "Tap to select the filled Excel file" and pick the file.<br>4. Tap "Upload". | Toast "Upload Complete - 2 of 2 staff created successfully."; chips "2 created", "0 failed", "2 total rows". | planned |
| TC-STF-08-E07 | P2 | Mobile | Admin | A file with one valid row (new phone 9876510037) and one row without Phone. | 1. Sign in as Admin.<br>2. Open "Bulk Upload".<br>3. Pick the file and tap "Upload". | Toast "Upload Finished With Errors - 1 created, 1 failed. See details below."; chips "1 created", "1 failed", "2 total rows"; the line "Row 3: Phone is required" is listed. | planned |
| TC-STF-08-E08 | P2 | Mobile | Staff | None. | 1. Sign in as Staff.<br>2. Open Staff hub > "Staff Enrollment".<br>3. Open `/staff/bulk-upload` by URL. | No "Bulk Upload" button; the screen shows "Access Denied - You don't have permission to view this screen. Please contact your administrator." (verified 2026-10-07). | planned |

Implemented in: backend/tests/unit/staff/test_bulk_upload.py.

---

## F09 Drivers list

**Purpose.** Provide the list of staff who are drivers, for the transport module's trip and driver assignment.

**Roles and permissions.** `transport_trips:read` (not a `staff` permission). Default seed: Admin, Teacher and Staff have it; Student and Parent do not.

**Preconditions.** Staff whose designation title is `driver` (F01 creates the designation, F02 assigns it).

**Steps, web.** There is no Staff screen for this list. The transport trip pages call `GET /staff/drivers` (web `api/masters/trips.ts`, `getAllDrivers`) to fill the driver selector. See `docs/features/transport.md`.

**Steps, mobile.** No mobile screen in the staff module uses it. (Transport screens are documented in `docs/features/transport.md`.)

**Expected results.** An array with one entry per staff member whose designation title equals `driver` ignoring case. Inactive staff are included.

**API endpoints.**
- `GET /staff/drivers` -> `[{full_name, user_id}]`.

**Rules and validations.**
1. Match is `Designation.title ILIKE 'driver'`, so `Driver`, `DRIVER` and `driver` match; `Bus Driver` and `Drivers` do not.
2. The service builds `{id: user_id, full_name, user_id, staff_id}`, but the route's `DriverOut` response model keeps only `full_name` and `user_id`, so `id` and `staff_id` are not returned. Consumers must use `user_id` (transport assigns drivers by user id).
3. `full_name` is `"<first> <last>"` with the trailing blank trimmed when there is no last name.
4. Staff without a designation are never drivers.

**Error and edge cases.** No drivers: `[]`. Missing token 401; missing `transport_trips:read` 403. Deleting a designation that drivers use is blocked (F01), so the list cannot silently empty.

**Unit-testable logic.** `get_all_drivers_list` mapping and name trimming; `DriverOut` field filtering; the case-insensitive match.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-09-U01 | `get_all_drivers_list` with a mocked driver without last name | `full_name` has no trailing space; the service dict has `id == user_id` | passing |
| TC-STF-09-U02 | `DriverOut.model_validate` on the service dict | only `full_name` and `user_id` remain | passing |
| TC-STF-09-A01 | Staff `Ravi Kumar` (designation `Driver`) exists; Admin `GET /staff/drivers` | 200; contains `{full_name:"Ravi Kumar", user_id:<his user id>}` | passing |
| TC-STF-09-A02 | Response keys | exactly `full_name` and `user_id` (no `id`, no `staff_id`) | passing |
| TC-STF-09-A03 | Designations `driver`, `DRIVER`, `Bus Driver` each with one staff member | the first two are listed; `Bus Driver` is not | passing |
| TC-STF-09-A04 | Inactive driver | still listed | passing |
| TC-STF-09-A05 | Tenant with no driver designation | 200 `[]` | passing |
| TC-STF-09-A06 | Admin, Teacher, Staff roles | 200 for all three | passing |
| TC-STF-09-A07 | Student and Parent | 403 | passing |
| TC-STF-09-A08 | No token | 401 | passing |
| TC-STF-09-A09 | Tenant isolation: tenant A drivers not visible with a tenant B token | `[]` in B | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-09-E01 | P1 | Web | Admin | Seeded drivers Ramesh Yadav and Mohan Singh (designation Driver); seeded trips and vehicles. | 1. Sign in as Admin.<br>2. Open the trips page (`/masters/trips`) and start adding a trip.<br>3. Open the driver selector.<br>4. Cancel without saving. | The selector offers "Ramesh Yadav" and "Mohan Singh" and no non-driver staff. | planned |
| TC-STF-09-E02 | P2 | Web | Admin | QA data set (QA Ravi Kumar, designation Driver). | 1. Sign in as Admin.<br>2. Open Staff > Enrollment; "Edit Staff" on QA Ravi Kumar.<br>3. Clear "Designation" and click "Save".<br>4. Reopen the trip form driver selector.<br>5. Set the designation back to "Driver". | After step 4 "QA Ravi Kumar" is no longer offered; after step 5 he is offered again. | planned |

Implemented in: backend/tests/unit/staff/test_attendance_drivers_profile.py (U01), backend/tests/unit/staff/test_staff_schemas.py (U02).

---

## F10 Mark staff attendance

**Purpose.** Record, daily, which staff members were absent, late, on half day or on leave. Present is the default and is stored as no row.

**Roles and permissions.**
- Single create: `staff_attendance:create`. Edit: `staff_attendance:update`. Switching back to present deletes the row: `staff_attendance:delete`. Bulk upsert by date: `staff_attendance:update`.
- The roster itself comes from `GET /staff/`, which needs `staff:list`.
- Default seed: Admin only. Web hub card "Staff Attendance" needs `staff_attendance:read`; the page has no page-level guard; the "Save Attendance" button and the status dropdowns appear only with `create` or `update`.

**Preconditions.** Staff exist (F02). The user holds the permissions above. Attendance cannot be marked before the date exists in the UI; the web date picker has no limits, the mobile screen blocks future dates.

**Steps, web.**
1. Staff -> Staff Attendance in the sidebar, the hub card "Staff Attendance" (button "Manage Attendance"), or `/staff/attendance` (page "Staff Attendance", card "Attendance Overview").
2. Pick the "Date" (default today, shown as "07 Oct 2026"). The summary shows "Attendance Analysis", "<n>% Present", the counters PRESENT, ABSENT, LATE, HALF DAY and "<n> staff total"; the list "Filter Staff" shows each staff member with a coloured status chip, email and department.
3. Change a row's status with its dropdown (Present, Absent, Late, Half Day). Changed rows are tracked and the badge "Unsaved Changes" appears; "Save Attendance" is disabled until something changed. "Search by name, email, or department..." filters the roster ("<shown> of <total>"). "Refresh" reloads the day's data.
4. Click "Save Attendance". Only modified rows are sent, in parallel: present to non-present with no row creates, non-present to non-present updates, non-present back to present deletes. Toast "Attendance saved successfully!"; a failure shows the first error message and no indication of which calls failed.
5. The Send icon on a non-present row is QuickSend with template "Staff Attendance" (COM F04); it is disabled for present staff (tooltip "Staff is present - no notification needed").
6. The page has no page-level guard. A role without `staff_attendance` grants (Staff, Teacher, Student, Parent in QA) can open the URL: the hub hides the card, the page shows no status dropdowns and no "Save Attendance", and the roster stays on "Loading staff..." (Staff, Student) or shows "No staff members found." (Teacher, Parent) (observed 2026-10-07).

**Steps, mobile.**
1. Staff hub -> "Attendance" ("Mark & view staff daily attendance"; screen "Staff Attendance"). Use the arrows or tap the date (shown as "Wed, 7 Oct, 2026") to choose a day ("Future Date - Read Only" appears for future days and disables editing). "Refresh" reloads.
2. The cards "Attendance Analysis" (PRESENT, ABSENT, LATE, HALF DAY, "<n> staff total") and the roster with a status dropdown per row; a "Modified" badge marks changed rows. "Columns (<shown>/5)" toggles Email, Department, Status, Modified. "Search by name, email, or department...". Without `staff_attendance` the screen shows "Access Denied - You don't have permission to view staff attendance".
3. "Save Attendance (<n>)" opens the confirm "Save Attendance?" ("You are about to save attendance changes for <n> staff member(s) on <date>. Continue?"), then "Save". Success toast "Success - Attendance updated successfully". With failures: "Partial Save - <title>" with the counts; failed rows stay pending.

**Expected results.** One `staff_attendance` row per `(staff_id, date)` for every non-present status; present means the row is absent. The roster defaults to present for staff without a row. Remarks are not editable in either client (web sends an empty remark, mobile keeps the stored one).

**API endpoints.**
- `POST /staff/attendance` body `{staff_id, date, status, remarks?}` -> `StaffAttendanceOut {id,staff_id,date,status,remarks}`.
- `PATCH /staff/attendance/{attendance_id}` body `{status?, remarks?}` -> `StaffAttendanceOut`.
- `DELETE /staff/attendance/{attendance_id}` -> `{"detail": "Staff attendance deleted successfully"}`.
- `PATCH /staff/attendance/by-date/{attendance_date}` body `[{staff_id, status, remarks?}]` -> updated rows (a bulk upsert; no client calls it).
- Read endpoints used by the screens are in F11; the roster is `GET /staff/` (F06).

**Rules and validations.**
1. Statuses are `present`, `absent`, `late`, `half_day`, `leave` in lowercase; `"Present"` is a 422. The clients offer only the first four (no `leave`).
2. `(staff_id, date)` is unique. A second `POST` for the same pair violates the constraint and returns 500; `PATCH` or the by-date upsert must be used instead.
3. `POST` has no future-date guard and no joining-date guard. The by-date `PATCH` rejects future dates (400 "Cannot update attendance for future dates") and an empty list (400 "No attendance updates provided"); entries missing `staff_id` or `status` are skipped; an invalid status gives 400 "Invalid attendance status '<s>'. Must be one of: present, absent, late, half_day, leave"; `remarks` are updated only when non-empty.
4. An unknown `staff_id` violates the foreign key and returns 500.
5. "Present" in the clients deletes the existing row, so a marker without `staff_attendance:delete` partially fails.
6. The roster ignores `is_active`, so inactive staff appear and are counted in the percentage.
7. The summary percentage is `round(present / total_staff * 100)`, where present counts staff without an exception row.
8. Data is per tenant.

**Error and edge cases.** Unknown attendance id on PATCH or DELETE: 404 "Attendance record not found". Duplicate create: 500 "Error creating staff attendance: ...". Network and permission failures are shown by toast (web: the first rejected message; mobile: typed titles such as "Permission Denied", "Not Found"). A role without `staff:list` gets an empty or failing roster even if it holds attendance grants.

**Unit-testable logic.** `StaffAttendanceCreate/Update` and `AttendanceStatusEnum` (lowercase only); `update_staff_attendance_by_date` branches (future date, empty list, skipped entries, invalid status, upsert versus create, remarks rule); web `handleAttendanceChange` modified flag, the `toCreate/toUpdate/toDelete` partition in `handleSave`, summary counters and percentage; mobile `doSaveAttendance` partial-failure bookkeeping, `isFutureDate` and `getAttendanceErrorInfo`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-10-U01 | `StaffAttendanceCreate(status="Present")` and `("present")`, `("leave")`, `("holiday")` | invalid (case-sensitive); valid; valid; invalid | passing |
| TC-STF-10-U02 | `update_staff_attendance_by_date` with a future date | HTTPException 400 "Cannot update attendance for future dates" | passing |
| TC-STF-10-U03 | Same with an empty list | HTTPException 400 "No attendance updates provided" | passing |
| TC-STF-10-U04 | Same with an entry whose status is "sick" | HTTPException 400 "Invalid attendance status 'sick'. Must be one of: present, absent, late, half_day, leave" | passing |
| TC-STF-10-U05 | Same with entries lacking `staff_id` or `status` | skipped without error | passing |
| TC-STF-10-U06 | By-date upsert where one row exists and one does not (mocked db) | the existing row's status changes, a new `StaffAttendance` is added; `remarks` untouched when empty | passing |
| TC-STF-10-U07 | Web `handleAttendanceChange`: existing absent set to present; no row set to absent; no row set to present | modified true, true, false | blocked: handleAttendanceChange is inline in web/src/components/staff/StaffAttendanceTable.tsx |
| TC-STF-10-U08 | Web partition for [absent(new), late(existing, changed to absent), absent(existing, changed to present)] | one create, one update, one delete | blocked: the create/update/delete partition is inline in web/src/components/staff/StaffAttendanceTable.tsx |
| TC-STF-10-U09 | Web percentage for 8 staff of whom 2 non-present, and for 0 staff | 75 and 0 | blocked: the percentage calculation is inline in web/src/components/staff/StaffAttendanceTable.tsx |
| TC-STF-10-U10 | Mobile `isFutureDate` for tomorrow and for today | true; false | blocked: isFutureDate is local to mobile/app/staff/attendance.tsx and not exported |
| TC-STF-10-U11 | Mobile `getAttendanceErrorInfo` for status 403, 404, 422, 429, 503 and a network error | titles Permission Denied, Not Found, Validation Failed, Too Many Requests, Server Error, Network Error | blocked: getAttendanceErrorInfo is local to mobile/app/staff/attendance.tsx and not exported |
| TC-STF-10-A01 | Admin `POST /staff/attendance` `{staff_id, date:"2026-10-01", status:"absent"}` | 200 `StaffAttendanceOut` with `status` absent, `remarks` null | passing |
| TC-STF-10-A02 | One create per status absent, late, half_day, leave | 200 for all (on different dates) | passing |
| TC-STF-10-A03 | `status:"Present"`; `status:"holiday"`; missing `date`; missing `staff_id` | 422 each | passing |
| TC-STF-10-A04 | Second `POST` for the same staff and date | 500 "Error creating staff attendance: ..." (unique `uq_staff_date`); the original row unchanged | passing |
| TC-STF-10-A05 | `POST` for an unknown `staff_id` | 500 | passing |
| TC-STF-10-A06 | `POST` with a date next year | 200 (no future guard) | passing |
| TC-STF-10-A07 | `PATCH /staff/attendance/{id}` `{status:"late", remarks:"Bus delay"}` | 200 with both values | passing |
| TC-STF-10-A08 | `PATCH` with `{status:"Late"}` | 422 | passing |
| TC-STF-10-A09 | `PATCH` and `DELETE` on a random uuid | 404 "Attendance record not found" | passing |
| TC-STF-10-A10 | `DELETE` an existing row | 200 `{"detail":"Staff attendance deleted successfully"}`; the staff member is present again for that date | passing |
| TC-STF-10-A11 | By-date `PATCH` for today with two entries (one new absent, one existing changed to late) | 200 list of 2 rows with the new statuses | passing |
| TC-STF-10-A12 | By-date `PATCH` for tomorrow; with `[]`; with status "sick" | 400 "Cannot update attendance for future dates"; 400 "No attendance updates provided"; 400 "Invalid attendance status 'sick'. ..." | passing |
| TC-STF-10-A13 | By-date `PATCH` with an unknown `staff_id` | 500 "Error updating staff attendance by date: ..."; no partial rows persisted | passing |
| TC-STF-10-A14 | By-date `PATCH` with an invalid date segment `2026-13-01` | 422 | passing |
| TC-STF-10-A15 | Staff role (no `staff_attendance` grant) on POST, PATCH, DELETE, by-date PATCH | 403 each | passing |
| TC-STF-10-A16 | A custom role holding only `staff_attendance:create`: POST 200; PATCH 403; DELETE 403 | as stated (actions are independent) | passing |
| TC-STF-10-A17 | Teacher, Student, Parent on all four write endpoints | 403 | passing |
| TC-STF-10-A18 | No token | 401 on all four | passing |
| TC-STF-10-A19 | Tenant isolation: attendance created in tenant A for a tenant A staff id; tenant B `PATCH` on that attendance id | 404 "Attendance record not found" | passing |
| TC-STF-10-A20 | Token tenant A with `cschema: qa_school_b` | 403 | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-10-E01 | P2 | Web | Admin | QA data set; no attendance rows for today. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance.<br>3. Keep "Date" on today. | Every staff member (active and inactive) shows Present; "Attendance Analysis" shows "100% Present" with ABSENT, LATE and HALF DAY at 0; "Save Attendance" is disabled. | planned |
| TC-STF-10-E02 | P1 | Web | Admin | QA data set; no attendance rows for today for QA Asha Verma and QA Ravi Kumar. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance (today).<br>3. Set QA Asha Verma to "Absent".<br>4. Set QA Ravi Kumar to "Late".<br>5. Click "Save Attendance".<br>6. Click "Refresh". | "Unsaved Changes" appears after step 3; toast "Attendance saved successfully!"; ABSENT 1 and LATE 1; after Refresh both statuses persist. | planned |
| TC-STF-10-E03 | P2 | Web | Admin | TC-STF-10-E02 done. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance (today).<br>3. Set QA Asha Verma back to "Present".<br>4. Click "Save Attendance".<br>5. Click "Refresh". | Toast "Attendance saved successfully!"; after Refresh she is Present (her attendance row was deleted). | planned |
| TC-STF-10-E04 | P3 | Web | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance.<br>3. Change any status (do not save).<br>4. Change "Date" to yesterday. | The "Unsaved Changes" badge clears; yesterday's own statuses load; the unsaved change is discarded. | planned |
| TC-STF-10-E05 | P3 | Web | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance.<br>3. Type "qa ravi" in "Search by name, email, or department...". | Only QA Ravi Kumar is listed with the count "1 of N". | planned |
| TC-STF-10-E06 | P3 | Web | Admin | A custom role with `staff:list` and `staff_attendance:list,read` but no `create` or `update`, and a user with that role. | 1. Sign in as that user.<br>2. Open `/staff/attendance`. | Statuses are shown as plain chips without dropdowns; no "Save Attendance" button. | planned |
| TC-STF-10-E07 | P3 | Web | Admin | A custom role with `staff:list` and `staff_attendance:create,update,list,read` but no `delete`; QA Asha Verma Absent today. | 1. Sign in as a user with that role.<br>2. Open `/staff/attendance`.<br>3. Set QA Asha Verma to "Present".<br>4. Click "Save Attendance".<br>5. Click "Refresh". | An error toast appears; after Refresh she is still Absent (Present means delete, rule 5). | planned |
| TC-STF-10-E08 | P2 | Web | Staff | None. | 1. Sign in as Staff.<br>2. Open Staff in the sidebar.<br>3. Open `/staff/attendance` by URL. | The hub has no "Staff Attendance" card; the page loads without status dropdowns or "Save Attendance" and the roster stays on "Loading staff..." (no page guard, observed 2026-10-07). | planned |
| TC-STF-10-E09 | P2 | Web | Admin | QA data set; QA Asha Verma Absent today; template "Staff Attendance" loaded (Communication > Templates > "Load Default Templates"). | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance.<br>3. Hover the Send icon of a Present row.<br>4. Click the Send icon of QA Asha Verma.<br>5. Click "Cancel". | Step 3: icon disabled with the tooltip "Staff is present - no notification needed"; step 4 opens "Send Message" with "To: QA Asha Verma" and the template "Staff Attendance" preselected. Do not click "Send Now". | planned |
| TC-STF-10-E10 | P1 | Mobile | Admin | QA data set; QA Ravi Kumar Present today. | 1. Sign in as Admin.<br>2. Open Staff hub > "Attendance".<br>3. Set QA Ravi Kumar to "Absent".<br>4. Tap "Save Attendance (1)".<br>5. In "Save Attendance?" tap "Save". | The row shows "Modified"; the confirm reads "You are about to save attendance changes for 1 staff member on <date>. Continue?"; toast "Success - Attendance updated successfully"; ABSENT shows 1. | planned |
| TC-STF-10-E11 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff hub > "Attendance".<br>3. Tap the next-day arrow once. | The label "Future Date - Read Only" appears and the status dropdowns are disabled. | planned |
| TC-STF-10-E12 | P3 | Mobile | Admin | None. | 1. Sign in as Admin.<br>2. Open Staff hub > "Attendance".<br>3. Tap "Save Attendance" without changing anything. | Toast "No Changes - No attendance changes to save". | planned |
| TC-STF-10-E13 | P3 | Mobile | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open Staff hub > "Attendance".<br>3. Open "Columns (5/5)" and untick Email. | The label becomes "Columns (4/5)" and the email text disappears from the rows. | planned |
| TC-STF-10-E14 | P2 | Mobile | Staff | None. | 1. Sign in as Staff.<br>2. Open the Staff hub.<br>3. Open `/staff/attendance` by URL. | The hub has no "Attendance" card; the screen shows "Access Denied - You don't have permission to view staff attendance" (verified 2026-10-07). | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01), backend/tests/unit/staff/test_attendance_drivers_profile.py (U02-U06).

---

## F11 Staff attendance history and lookup

**Purpose.** Read attendance records: a day's records, a date range, one staff member's history, or a single record.

**Roles and permissions.** List endpoints (`/attendance`, `/attendance/by-date/{date}`, `/{staff_id}/attendance/filter`): `staff_attendance:list`. Single record `/attendance/{id}`: `staff_attendance:read`. Default seed: Admin only. There is no "my attendance" endpoint for staff; a staff member can see attendance only if the role holds `staff_attendance:list`.

**Preconditions.** Attendance rows exist (F10).

**Steps, web.**
1. The day view is the same screen as F10 (`/staff/attendance`): changing the "Date" loads `GET /staff/attendance/by-date/<date>` and shows each staff member with the stored status.
2. There is no routed per-staff history screen. Component `StaffAttendanceTable` (list with filters, edit and delete) exists only on the unrouted page `pages/masters/staff.tsx`. Summaries and exports are in the Reports module (`/reports/attendance/staff`, RPT docs).

**Steps, mobile.**
1. Staff -> Attendance. The day is loaded with `GET /staff/attendance?start_date=<d>&end_date=<d>`; the arrows or the date picker move between days.
2. There is no per-staff history screen.

**Expected results.** Responses list `StaffAttendanceOut` rows only for staff and days with exceptions.

**API endpoints.**
- `GET /staff/attendance?start_date=&end_date=&name=` -> `[StaffAttendanceOut]`.
- `GET /staff/attendance/by-date/{attendance_date}` -> `[StaffAttendanceOut]`.
- `GET /staff/{staff_id}/attendance/filter?start_date=&end_date=` -> `[StaffAttendanceOut]`.
- `GET /staff/attendance/{attendance_id}` -> `StaffAttendanceOut`.

**Rules and validations.**
1. `GET /staff/attendance` filters by date only when **both** `start_date` and `end_date` are given (inclusive); with one of them the filter is ignored and every row is returned. `name` is a case-insensitive contains match on the first name only.
2. `/{staff_id}/attendance/filter` accepts `start_date`, `end_date` or both independently; an unknown staff id returns `[]`, not 404.
3. `by-date` returns rows for exactly that date. Dates must be ISO `YYYY-MM-DD` (422 otherwise).
4. Row order is not specified.
5. Nothing here paginates; the mobile client sends `skip` and `limit`, which the backend ignores.

**Error and edge cases.** Unknown attendance id: 404 "Staff attendance record not found". Invalid date or UUID formats: 422. Missing token 401; missing permission 403. Days with no exceptions return `[]`.

**Unit-testable logic.** `get_all_staff_attendance` (both-dates rule, name filter), `get_attendance_for_staff` (one-sided ranges), `get_staff_attendance_by_date`; web `useStaffAttendanceByDate`; mobile `attendanceMap` construction.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-11-U01 | `get_all_staff_attendance` with only `start_date` | no date condition is applied (returns all rows) | passing |
| TC-STF-11-U02 | `get_attendance_for_staff` with only `end_date` | adds `date <= end_date` | passing |
| TC-STF-11-U03 | Name filter `"as"` | statement joins `Staff` and uses `ilike('%as%')` on `first_name` | passing |
| TC-STF-11-U04 | Mobile `attendanceMap` for two rows with the same staff id | the last row wins | blocked: attendanceMap is a useMemo local to mobile/app/staff/attendance.tsx and not exported |
| TC-STF-11-A01 | Rows: Asha absent on 2026-10-01, Ravi late on 2026-10-01, Asha half_day on 2026-10-02. `GET /staff/attendance/by-date/2026-10-01` | 200; exactly two rows | passing |
| TC-STF-11-A02 | `GET /staff/attendance?start_date=2026-10-01&end_date=2026-10-02` | 200; three rows (inclusive bounds) | passing |
| TC-STF-11-A03 | `GET /staff/attendance?start_date=2026-10-02` (end missing) | 200; all three rows (filter ignored) | passing |
| TC-STF-11-A04 | `GET /staff/attendance?name=ash` with both dates | only Asha's rows | passing |
| TC-STF-11-A05 | `GET /staff/{Asha}/attendance/filter?start_date=2026-10-02` | one row (2026-10-02) | passing |
| TC-STF-11-A06 | `GET /staff/{Asha}/attendance/filter` without dates | both of Asha's rows | passing |
| TC-STF-11-A07 | `GET /staff/{random uuid}/attendance/filter` | 200 `[]` | passing |
| TC-STF-11-A08 | `GET /staff/attendance/{id}` for an existing row; for a random uuid | 200 row; 404 "Staff attendance record not found" | passing |
| TC-STF-11-A09 | `GET /staff/attendance/by-date/2026-13-45`; `.../abc`; filter with `start_date=x` | 422 for each | passing |
| TC-STF-11-A10 | A day without exceptions | 200 `[]` | passing |
| TC-STF-11-A11 | Response fields | each item has `id`, `staff_id`, `date` (ISO), `status`, `remarks` | passing |
| TC-STF-11-A12 | Admin on all four endpoints | 200 | passing |
| TC-STF-11-A13 | Staff, Teacher, Student, Parent on all four | 403 | passing |
| TC-STF-11-A14 | A custom role with only `staff_attendance:list`: list endpoints 200, `/attendance/{id}` 403 | `read` and `list` are independent | passing |
| TC-STF-11-A15 | No token | 401 on all four | passing |
| TC-STF-11-A16 | Tenant isolation: tenant B calls the four endpoints for tenant A data | `[]` for lists, 404 for the single record | passing |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-11-E01 | P1 | Web | Admin | QA data set. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance (today).<br>3. Set QA Asha Verma to "Absent" and click "Save Attendance".<br>4. Change "Date" to yesterday.<br>5. Change "Date" back to today. | After step 5 QA Asha Verma shows Absent again (loaded from the stored row). | planned |
| TC-STF-11-E02 | P3 | Web | Admin | A past date with no attendance rows (for example 2026-09-01). | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance.<br>3. Pick that date. | Everyone shows Present and the analysis shows "100% Present". | planned |
| TC-STF-11-E03 | P3 | Web | Admin | TC-STF-11-E01 done. | 1. Sign in as Admin.<br>2. Open the staff attendance report (`/reports/attendance/staff`, see the reports doc).<br>3. Filter to today. | The absence of QA Asha Verma is listed. | planned |
| TC-STF-11-E04 | P2 | Mobile | Admin | TC-STF-11-E01 done (QA Asha Verma Absent today). | 1. Sign in as Admin.<br>2. Open Staff hub > "Attendance" (today). | ABSENT shows at least 1 and QA Asha Verma's dropdown shows Absent. | planned |
| TC-STF-11-E05 | P3 | Mobile | Admin | TC-STF-11-E04 done. | 1. Sign in as Admin.<br>2. Open Staff hub > "Attendance".<br>3. Tap the previous-day arrow.<br>4. Tap the next-day arrow. | Step 3 loads yesterday's statuses; step 4 returns to today with QA Asha Verma Absent again. | planned |
| TC-STF-11-E06 | P2 | Web | Admin | Seeded staff attendance on 2026-09-29. | 1. Sign in as Admin.<br>2. Open Staff > Staff Attendance.<br>3. Set "Date" to 29 Sep 2026. | The seeded exceptions for that day load (some staff Absent, Late or Half Day); the counters and "<n>% Present" match the rows. Do not save changes to seeded days. | planned |

Implemented in: backend/tests/unit/staff/test_attendance_drivers_profile.py (U01-U03).

---

## F12 Staff profile (self-service)

**Purpose.** Let a signed-in staff member (and teacher or admin who has a staff record) view their own details and change their own email and phone.

**Roles and permissions.**
- View: `profile:read_own`. Edit: `profile:update_own`. Neither is in the default seed for Admin, Teacher or Staff (only Student has them); the QA tenant grants them (see Roles). The checks resolve scope through `check_user_resource_access`.
- Web: route `/profile` renders the staff profile for every role except student and parent; `/staff/profile` renders it directly. The edit button needs `profile:update_own`.
- Mobile: `app/profile.tsx` uses the staff profile for role names staff, teacher and admin; the dedicated screen `app/staff/profile.tsx` is guarded by `staff` read or list and shows its edit button only with `staff:update` (a stricter, different rule).

**Preconditions.** The user has a linked `staff` row (users created by F02 do; an Admin created by provisioning usually does not).

**Steps, web.**
1. Open the profile page (`/profile` from the user menu, or `/staff/profile`). Page "Staff Profile": photo placeholder, card "Personal Information" with First Name, Last Name, Designation, Employee ID, Date of Joining, Status, Email, Phone.
2. Click "Edit Email & Phone". In the dialog "Edit Email & Phone" change "Email" (required, `name@host` pattern: "Invalid email address") and "Phone" (required, exactly 10 digits: "Phone must be 10 digits") and click "Update". Toast "Staff profile updated successfully!".
3. When the API returns 403 or 404 the page shows "My Profile" with "Account Information": Username, Email, Role, Academic Year. This is what the five QA logins see, because none of them has a staff row (verified 2026-10-07). Any other error shows "Your profile could not be loaded right now. Please try again later."

**Steps, mobile.**
1. Profile (bottom tab "Profile") for staff, teacher or admin roles: "Staff Profile" with First Name, Last Name, Email, Phone and a section "Employment Information" (Employee ID, Designation, Date of Joining, Status). A user without a staff row (the QA logins) sees "Profile" with "Account Information" (Username, Email, Role) and "Logout" instead.
2. The separate screen `/staff/profile` shows "Staff Profile" with "Personal Information" and "Employment Information". For a user without a staff row it shows every field as "Not provided" or "Not assigned" and Status "Inactive" instead of an error (observed 2026-10-07). Student and Parent get "Access Denied - You don't have permission to view staff profile data".
3. The pencil button switches Email and Phone to inputs; "Save Changes" validates (email must contain "@": "Please enter a valid email address"; phone at least 10 characters: "Please enter a valid phone number") and shows "Success - Profile updated successfully". "Cancel" discards.

**Expected results.** The response is `{staff_id, user_id, first_name, last_name, email, phone, designation, employee_id, date_of_joining, is_active, profile_photo_url}`. `employee_id` and `profile_photo_url` are always null. Each view and each update writes a `profile_audit_logs` row. An update changes `staff.email` and `staff.phone` only (not `users.email` or `users.username`).

**API endpoints.**
- `GET /profile/staff/me` -> `StaffProfileOut`.
- `PUT /profile/staff/me` body `{email?, phone?}` -> `StaffProfileOut`.
- Related (auth module): `POST /profile/change-password` (`profile:update_own`), see `docs/features/auth.md`.

**Rules and validations.**
1. The profile is found by `Staff.user_id == current user`; no staff row gives 404 "Staff profile not found".
2. Only non-null `email` and `phone` are applied; there is no format validation on the server (plain strings). The clients validate (web: phone exactly 10 digits; mobile: at least 10 characters).
3. **Defect D-STF-03 (fixed 2026-10-05):** `get_profile` used to read `designation_obj.name` and answered 500 for any staff member with a designation; it now reads `designation_obj.title`, so the designation title is returned.
4. A duplicate `staff.email` on update violates the unique constraint (error response).
5. Audit rows are written on every GET.

**Error and edge cases.** No staff row (for example the provisioning Admin): 404 "Staff profile not found" and the web page falls back to Account Information. Missing grant: 403 `{"error":"permission_denied", ...}`. Missing token 401. Student with `profile:read_own` but no staff row: 404.

**Unit-testable logic.** `StaffProfileOut`/`StaffProfileUpdate` schemas; update only-non-null logic and change tracking; designation mapping (the `name` versus `title` bug); web form rules (`/^\S+@\S+$/i`, `/^\d{10}$/`) and mobile `handleSave` checks.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-STF-12-U01 | `StaffProfileUpdate()` and `StaffProfileUpdate(email="x")` | both valid (no format validation) | passing |
| TC-STF-12-U02 | `StaffProfileService.get_profile` with a staff mock whose `designation_obj` is a `Designation(title="Teacher")` | expected `designation == "Teacher"`; currently raises AttributeError on `.name` (D-STF-03) | xfail: D-STF-03 (strict, target behaviour asserted) |
| TC-STF-12-U03 | `get_profile` with `designation_obj=None` | returns `designation None`, `employee_id None`, `profile_photo_url None` | passing |
| TC-STF-12-U04 | `update_profile` with `{email: None, phone: "9000000000"}` | only phone changes; `changes` contains only `phone` | passing |
| TC-STF-12-U05 | Web email regex for "a@b", "a b@c.d", ""; phone regex for "9876543210", "98765", "98765432101" | valid, invalid, invalid; valid, invalid, invalid | blocked: the regexes are inline in the web profile page form rules |
| TC-STF-12-U06 | Mobile `handleSave` for email "abc" and phone "12345" | validation errors before any request | blocked: handleSave is inline in the mobile profile screen |
| TC-STF-12-A01 | Staff user without a designation, `GET /profile/staff/me` | 200 with the documented fields; `employee_id` null | passing |
| TC-STF-12-A02 | Staff user with designation Teacher, `GET /profile/staff/me` | 200 with `designation` equal to the designation title | passing |
| TC-STF-12-A03 | `PUT {email:"asha.new@qa.example", phone:"9000000001"}` (no designation) | 200; `GET /staff/enrollment/{id}` shows the new values; `users.username` is unchanged | passing |
| TC-STF-12-A04 | `PUT` for a staff user with a designation | 200; the change is stored | passing |
| TC-STF-12-A05 | `PUT {}` | 200; nothing changes | passing |
| TC-STF-12-A06 | `PUT {email:"not-an-email"}` | 200 (no server validation, documents the gap) | passing |
| TC-STF-12-A07 | `PUT {email:<another staff's email>}` | error response (unique violation) and no change | passing |
| TC-STF-12-A08 | Admin user with no staff row | 404 "Staff profile not found" | passing |
| TC-STF-12-A09 | Role without `profile:read_own` (default-seed Staff) | 403 with `error: permission_denied` | failing |
| TC-STF-12-A10 | Role with `read_own` but not `update_own`: GET 200, PUT 403 | as stated | passing |
| TC-STF-12-A11 | Student and Parent roles | Student 404 (no staff row) when granted; Parent 403 | passing |
| TC-STF-12-A12 | No token | 401 | passing |
| TC-STF-12-A13 | User of tenant B calling `/profile/staff/me` with tenant A header | 403; each user only sees their own row | passing |
| TC-STF-12-A14 | Each GET adds a `profile_audit_logs` row (DB assertion) | count increases by one per GET | skipped: asserts profile_audit_logs rows in the database; |

UI test cases (manual format).

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-STF-12-E01 | P1 | Web | Staff | Seeded staff login Padmavathi Devi (Accountant) with the first-login password change done; the Staff role holds `profile:read_own`. | 1. Sign in as Padmavathi Devi.<br>2. Open `/profile` from the user menu. | "Staff Profile" with First Name "Padmavathi", Last Name "Devi", Designation "Accountant", Employee ID "N/A", Date of Joining, Status "Active", Email "padmavathi.devi@example.com", Phone "9000010006". | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E02 | P2 | Web | Staff | QA Asha Verma (QA data set) signed in after her first-login change; the Staff role holds both `profile` actions. | 1. Sign in as QA Asha Verma.<br>2. Open `/profile`.<br>3. Click "Edit Email & Phone".<br>4. Enter Email "qa.asha.new@qa.example" and Phone "9876510041".<br>5. Click "Update". | Toast "Staff profile updated successfully!"; the page shows the new values; her login name is unchanged. | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E03 | P3 | Web | Staff | Same as TC-STF-12-E02. | 1. Open `/profile` and click "Edit Email & Phone".<br>2. Enter Phone "98765".<br>3. Click "Update". | "Phone must be 10 digits"; no request; the dialog stays open. | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E04 | P3 | Web | Staff | Same as TC-STF-12-E02. | 1. Open `/profile` and click "Edit Email & Phone".<br>2. Enter Email "abc".<br>3. Click "Update". | "Invalid email address"; no request. | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E05 | P2 | Web | Admin | QA Admin login in qa_manual (no staff row, no profile grant). | 1. Sign in as Admin.<br>2. Open `/profile`. | "My Profile" with "Account Information": Username, Email, Role "Admin", Academic Year "2026-2027". Staff and Teacher: same with their role (verified 2026-10-07). | planned |
| TC-STF-12-E06 | P3 | Web | Staff | A staff user with a designation. | 1. Sign in as that user.<br>2. Open `/profile`. | (Case written for D-STF-03.) | obsolete: D-STF-03 fixed 2026-10-05, the designation title is now returned; covered by TC-STF-12-E01 |
| TC-STF-12-E07 | P3 | Web | Staff | A role with `profile:read_own` but not `profile:update_own`, and a staff user with that role. | 1. Sign in as that user.<br>2. Open `/profile`. | The profile shows without the "Edit Email & Phone" button. | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E08 | P2 | Mobile | Staff | Same as TC-STF-12-E02. | 1. Sign in as QA Asha Verma on mobile.<br>2. Open the Profile tab.<br>3. Tap the pencil.<br>4. Change Email and Phone.<br>5. Tap "Save Changes". | Toast "Success - Profile updated successfully"; the new values show. | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E09 | P3 | Mobile | Staff | Same as TC-STF-12-E02. | 1. Open the Profile tab and tap the pencil.<br>2. Enter Phone "12345".<br>3. Tap "Save Changes". | Toast "Validation Error - Please enter a valid phone number"; no request. | blocked: qa_manual grants no profile:read_own or profile:update_own to Admin, Staff or Teacher (default seed), so /profile/staff/me answers 403 and the page falls back to My Profile |
| TC-STF-12-E10 | P2 | Mobile | Staff | QA Staff login (no staff row). | 1. Sign in as Staff.<br>2. Open `/staff/profile` by URL.<br>3. Open the Profile tab. | Step 2: "Staff Profile" without a pencil edit button (needs `staff:update`); for a user without a staff row it currently shows "Not provided" fields and Status "Inactive" instead of an error (defect observed 2026-10-07). Step 3: "Profile" with "Account Information" and "Logout". | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01), backend/tests/unit/staff/test_attendance_drivers_profile.py (U02-U04).

---

## Known gaps

Findings from reading the code (module doc `docs/modules/staff.md` and the code agree unless stated).

**Defects**
- D-STF-01: Fixed (2026-10-02): a duplicate designation title on create returns 400 and the dropdown cache is cleared by create, update and delete.
- D-STF-02: `GET /staff/by-designation` has no `response_model` and serialises the raw ORM rows, including the loaded `user` relationship with `password_hash`. Verified by encoding a `Staff` object with a loaded `user` through FastAPI's `jsonable_encoder`; not confirmed against a live database. Fixed (2026-10-02): `response_model=list[StaffOut]` added.
- D-STF-03 (fixed 2026-10-05, `designation_obj.title` is now read): `GET` and `PUT /profile/staff/me` returned 500 for any staff member who had a designation (`designation_obj.name` does not exist; the column is `title`). `PUT` still saves the change before failing.
- The default seed (`permission_catalog.py`) gives no `profile:read_own` or `profile:update_own` to Admin, Teacher or Staff, so the staff profile is 403 on a freshly provisioned tenant; it also has no `send_sms` grants.

**UI defects observed on 2026-10-07**
- Web View dialog shows "Joining Date: 1/1/1970" when the joining date is empty (TC-STF-06-E13).
- Saved staff photos never render on web or mobile: the `<img>` request to `/media/...` gets 400 "Tenant must be specified via 'cschema' header" (TC-STF-05-E01, E03, E05 blocked).
- Web `/staff/attendance` has no page guard: Staff and Student see the summary and a roster stuck on "Loading staff..."; Teacher and Parent see "No staff members found." (TC-STF-10-E08).
- Mobile `/staff/profile` for a user without a staff row shows empty fields and Status "Inactive" instead of an error (TC-STF-12-E10).

**Doc versus code differences (code behaviour is documented above)**
- `docs/modules/staff.md` says `GET /staff/drivers` returns `id = user_id`; the response model keeps only `full_name` and `user_id`.
- The module doc says photos are stored at `media/staff/photos/{staff_id}.{ext}`; the code stores them under `media/<tenant_id>/staff/photos/`.
- The module doc says the bulk sheet must be named `Staff Admission`; the code falls back to the active sheet when that name is missing.
- The docstring of the bulk endpoint lists Email as mandatory; the code requires only First Name, Phone and Address.

**Known behaviours kept from the module doc**
- Privilege escalation: anyone with `staff:create` can create a login with any role (including Admin) through `role_id` or the bulk Role column.
- `PATCH /staff/enrollment/{id}` never updates the login (`users.username`, role); `role_id` is dropped.
- Deleting a staff member leaves the `users` row (login still works; re-enrolling the same email fails with 500).
- `staff.is_active` and `users.is_active` are not synchronised; `GET /staff/` ignores `is_active`, `skip`, `limit`; `GET /staff/enrollments` is unpaginated.
- Attendance: duplicate `POST` returns 500, no future-date or joining-date guard on `POST`, the clients offer no `leave`, and "present" deletes the row (needs `staff_attendance:delete`). `GET /staff/attendance` ignores a lone `start_date` or `end_date`.
- `StaffEnrollmentOut.created_at` and `updated_at` are always null.
- Server-side validation is missing for phone length and digits, UAN, PF, IFSC, whitespace-only values, designation title length and emptiness, and qualification `level`/`name` (database NOT NULL only).
- Mobile `app/staff/[id].tsx` is unreferenced and shows "No designation" and an empty Employee ID because `StaffEnrollmentOut` has neither `designation_obj` nor `employee_id`. Mobile forms send `esi_number` and `employee_id`, which the backend drops. The web page `pages/masters/staff.tsx` with the attendance table is not routed.
- The Staff hub card "Designations" on mobile checks `staff`, not `designations`.
- Photos are served publicly with no authentication.
- The SMS triggers `/staff/send-attendance-summary` and `/staff/send-interview-calls` have no client; see COM F08.
