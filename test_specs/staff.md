# Staff: feature documentation and test specification

Code: `STF`. Test case IDs: `TC-STF-<FF>-<P><NN>` (U unit, A API, E end-to-end UI). Conventions: `docs/testing/strategy.md`, layout: `docs/features/README.md`. Module rules: `docs/modules/staff.md`. Graph view: `docs/graph/views/staff.md`.

_Last verified against code: 2026-10-02_

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

Common test data (QA tenant `qa_school`, seeded by the test setup): designations `Principal`, `Teacher`, `Driver`; staff `Asha Verma` (Teacher designation, email `asha.verma@qa.example`, phone `9876500001`), `Ravi Kumar` (Driver designation, phone `9876500002`, no email), `Meena Rao` (inactive, `is_active=false`); users for each of the five roles; a second tenant `qa_school_b` for isolation cases. The temporary password given to new staff accounts is the hardcoded default in `staff_service.create_staff_enrollment`; tests read it from the setup output, it is not repeated here.

---

## F01 Designations

**Purpose.** Maintain the master list of job titles (for example Principal, Teacher, Driver) that staff are assigned to. Titles are unique and cannot be removed while a staff member uses them.

**Roles and permissions.**
- List, dropdown, legacy list: `designations:list`. Get one: `designations:read`. Create: `designations:create`. Edit: `designations:update`. Delete: `designations:delete`.
- Menu: Staff -> Designations for roles holding `designations:list`. Web hub card "Staff Designations" needs `designations:list`. Mobile hub card "Designations" is gated on `staff` list or read (not on `designations`); the buttons inside the screen use `designations` create, update, delete.

**Preconditions.** An authenticated tenant user with one of the grants above. None of the designations exist beforehand; this feature creates them. F02 and F09 depend on it.

**Steps, web.**
1. Open Staff (`/staff`, "Staff Management") and click the card "Staff Designations" (button "Manage Designations"), or go to `/staff/designations` (page title "Staff Designations").
2. The table shows S.No., Title, Staff Count ("N staff member(s)"), Created and Actions. Type in "Search designations..." to filter by title. Click the Title, Staff Count or Created header to sort (asc, desc, off).
3. Click "Add Designation" (or "Create First Designation" on an empty list). In the dialog "Create Designation" fill "Designation Title *" and click "Save". Toast: "Designation created successfully".
4. Click the Edit icon ("Edit Designation"), change the title in the dialog "Edit Designation", click "Save". Toast: "Designation updated successfully".
5. Click the Delete icon ("Delete Designation"). The dialog "Delete Designation" asks for confirmation; click "Delete". Toast: "Designation deleted successfully". If staff still use the title the toast reads "Failed to delete designation: Cannot delete designation '<title>' because it is being used by <n> staff member(s). ...".
6. An empty title shows the toast "Designation title is required" and nothing is sent. Users without `designations:list` see "Access Denied". Add, Edit and Delete controls are hidden without the matching permission.

**Steps, mobile.**
1. Staff hub (`/staff`) -> card "Designations" -> screen "Staff Designations".
2. Search with "Search designations...". Each card shows the title, "Created: <date>" and "N staff member(s)".
3. Tap "Add Designation", fill "Title *" (placeholder "Enter designation title"), tap "Save". Toast "Success - Designation created successfully".
4. Pencil icon (accessibility label "Edit") opens "Edit Designation"; trash icon ("Delete") opens a confirm modal, then toast "Designation deleted successfully".
5. Empty title: toast "Validation Error - Please enter designation title".

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
| TC-STF-01-A01 | Admin `POST /staff/designations/` `{title:"Lab Assistant"}` | 201; body has id, title "Lab Assistant", created_at, updated_at, `staff_count` 0 | planned |
| TC-STF-01-A02 | Admin creates the same title twice | second call returns 400 "Designation title '<t>' already exists"; no second row is created | planned |
| TC-STF-01-A03 | Create with `{}` | 422, loc `["body","title"]` | planned |
| TC-STF-01-A04 | Create with a 100-character title | 201 | planned |
| TC-STF-01-A05 | Create with a 101-character title | 500 "Error creating designation"; no row created | planned |
| TC-STF-01-A06 | Create with `{title:""}` | 201 (no backend minimum length); the row is removed in cleanup | planned |
| TC-STF-01-A07 | 12 designations exist; `GET /designations/` | 200; 10 items ordered by title; `total_count` 12; `has_next` true | planned |
| TC-STF-01-A08 | `GET /designations/?skip=10&limit=10` with 12 rows | 2 items; `has_next` false | planned |
| TC-STF-01-A09 | `limit=100` accepted; `limit=101`, `limit=0`, `skip=-1` | 200 for 100; 422 for the other three | planned |
| TC-STF-01-A10 | `staff_count` accuracy: Teacher designation used by 2 staff, Driver by 1, Principal by 0 | counts 2, 1, 0 in the list and in `GET /designations/{id}` | planned |
| TC-STF-01-A11 | `GET /designations/{id}` with an existing id | 200 `DesignationRead` | planned |
| TC-STF-01-A12 | `GET /designations/{random uuid}`; `GET /designations/abc` | 404 "Designation with id <id> not found"; 422 | planned |
| TC-STF-01-A13 | `PUT` rename "Lab Assistant" to "Laboratory Assistant" | 200; title updated; `staff_count` unchanged | planned |
| TC-STF-01-A14 | `PUT` to a title another row already has | 400 "Designation title '<t>' already exists" | planned |
| TC-STF-01-A15 | `PUT` with the unchanged title; `PUT {}` | 200 both; nothing changes | planned |
| TC-STF-01-A16 | `PUT` / `DELETE` on a random uuid | 404 for both | planned |
| TC-STF-01-A17 | `DELETE` an unused designation | 200 `{"message":"Designation deleted successfully"}`; a later GET is 404 | planned |
| TC-STF-01-A18 | `DELETE` a designation assigned to staff | 400 "Cannot delete designation 'Teacher' because it is being used by 2 staff member(s). ..."; row still exists | planned |
| TC-STF-01-A19 | `GET /designations/dropdown` | 200; `[{id,title}]` ordered by title; no `staff_count` | planned |
| TC-STF-01-A20 | Call the dropdown, create a new designation, call the dropdown again within 60 seconds | the new title is present in the second response (cache cleared on create) | planned |
| TC-STF-01-A21 | `GET /designations-legacy` | 200; `[{id,title}]` including every designation | planned |
| TC-STF-01-A22 | Each of the 7 endpoints without an Authorization header | 401 | planned |
| TC-STF-01-A23 | Admin: create, get, update, delete, list, dropdown, legacy | all 2xx | planned |
| TC-STF-01-A24 | Staff role: list, get, dropdown, legacy | 200; `POST`, `PUT`, `DELETE` return 403 | planned |
| TC-STF-01-A25 | Teacher role: same matrix as Staff | list, get, dropdown, legacy 200; create, update, delete 403 | planned |
| TC-STF-01-A26 | Student role on every endpoint | 403 on all 7 | planned |
| TC-STF-01-A27 | Parent role on every endpoint | 403 on all 7 | planned |
| TC-STF-01-A28 | Tenant isolation: designation "Isolation Test" created in `qa_school` | absent from the list and dropdown of `qa_school_b`; the same title can be created in `qa_school_b`; `GET /designations/{id}` from tenant B returns 404 | planned |
| TC-STF-01-A29 | Token of tenant A sent with `cschema: qa_school_b` | 403 | planned |
| TC-STF-01-A30 | 31 creates inside one minute | the 31st returns 429 (limit 30 per minute) | planned |
| TC-STF-01-A31 | Create `Lab Tech` and then `lab tech` in the same tenant | both 201 (case-sensitive uniqueness) | planned |
| TC-STF-01-E01 | Web, Admin: Add Designation "Store Keeper" | toast "Designation created successfully"; row with "0 staff members" appears | planned |
| TC-STF-01-E02 | Web, Admin: edit the title to "Store Keeper Grade 1" | toast "Designation updated successfully"; the row shows the new title | planned |
| TC-STF-01-E03 | Web, Admin: delete an unused designation, confirm | toast "Designation deleted successfully"; row disappears | planned |
| TC-STF-01-E04 | Web, Admin: delete "Teacher" (in use) | toast "Failed to delete designation: Cannot delete designation 'Teacher' because it is being used by ..."; row stays | planned |
| TC-STF-01-E05 | Web: click Save with an empty title | toast "Designation title is required"; no request is sent | planned |
| TC-STF-01-E06 | Web: search "dri" and sort by Staff Count | only "Driver" listed; sort order toggles asc, desc, off | planned |
| TC-STF-01-E07 | Web, Staff role | list visible; no "Add Designation", no Edit or Delete icons | planned |
| TC-STF-01-E08 | Web, Student and Parent | `/staff/designations` shows "Access Denied"; the Staff menu is not shown | planned |
| TC-STF-01-E09 | Mobile, Admin: Staff hub -> Designations -> Add Designation "Cook" | toast "Designation created successfully"; card with "0 staff members" | planned |
| TC-STF-01-E10 | Mobile, Admin: edit then delete with the confirm modal | toasts "Designation updated successfully" then "Designation deleted successfully" | planned |
| TC-STF-01-E11 | Mobile, Staff role | cards visible without Add, Edit or Delete buttons | planned |
| TC-STF-01-E12 | Mobile, Student and Parent | the Staff hub is not reachable from the tabs; opening `/staff/designations` shows no data actions | planned |

Implemented in: backend/tests/unit/staff/test_designations.py.

---

## F02 Enroll a staff member (account creation)

**Purpose.** Register a new employee and create their login account in one step.

**Roles and permissions.**
- `staff:create`. Admin has it in the default seed; Staff, Teacher, Student and Parent do not.
- Menu: Staff -> Staff Enrollment (`/staff/enrollment`, page guarded by `staff:list`). The "Add Staff" and "Bulk Upload" buttons need `staff:create`.

**Preconditions.** A role named exactly `Staff` exists (default when no role is chosen). Optional: designations (F01). The logged-in user holds `staff:create`.

**Steps, web.**
1. Staff -> Staff Enrollment (card "Manage Staff Profiles", page "Staff Enrollment"). Click "Add Staff".
2. In the dialog "Create Staff Enrollment":
   - Basic Information: optional photo ("Staff Photo", "Choose photo", JPG, PNG or WebP, max 2 MB), "First Name *", "Last Name", "Email", "Phone *", "Gender" (Male, Female, Other), "Date of Birth", "Joining Date", "Qualification", "Experience (Years)", "Address *".
   - "Qualifications" -> "Add Qualification": Level, Degree / Course, Pass-out Year, Percentage / CGPA, University / Board (see F04).
   - Professional Information: "Designation" (searchable, from F01), "Department".
   - Account Information: "Role" (any tenant role; empty means `Staff`), checkbox "Active Staff Member" (default on).
   - Accordions "Work Experience" (Previous Organization, Subjects Dealt, From Date, To Date, Remarks), "Bank Details" (Bank Name, Branch, Account Number, IFSC Code, Account Holder Name, Account Type), "Salary & PF" (Last Drawn Salary, Current Salary, PF Account Number, UAN Number).
3. Click "Save". Client checks run first: "First name is required", "Phone is required", "Please enter a valid email address", "Address is required" (toast "Please fill in the required fields"); phone must be exactly 10 digits ("Phone number must contain digits only", "Number is less than 10 digits - you entered N. Please enter exactly 10 digits", "Number exceeds 10 digits - ..."); UAN "UAN Number must be exactly 12 digits"; PF "Invalid PF Account Number format (e.g. AP/HYD/12345)"; unpaired qualification toast "Qualification Level and Degree / Course must both be filled in, or both left empty".
4. On success the toast reads "Staff enrollment created successfully"; qualifications are posted one by one and the photo is uploaded afterwards (the id does not exist before create). The row appears in the table.

**Steps, mobile.**
1. Staff hub -> "Staff Enrollment" -> "Add Staff" (header button). The sheet "Create Staff Enrollment" has the same sections and labels as web, except: no Role field (always `Staff`), the Joining Date defaults to today, dates are typed as DD/MM/YYYY or picked, date of birth and joining date cannot be in the future, and the photo is chosen with "Upload Photo".
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
| TC-STF-02-A01 | Admin `POST /staff/enrollment` with only `first_name "Kiran"`, `phone "9876500011"`, `address "12 MG Road"` | 200; `qualifications` `[]`; `is_active` true; users row has username `9876500011`, role `Staff`, `is_first_login` true | planned |
| TC-STF-02-A02 | Create with email `kiran.nair@qa.example` and all HR fields (work, bank, salary, PF, UAN `123456789012`) | 200; every field echoed; `current_salary` `"50000.00"`; users.username equals the email | planned |
| TC-STF-02-A03 | Create without `first_name`; without `phone`; without `address` | 422 each; loc names the field; no users row created | planned |
| TC-STF-02-A04 | `phone ""` or `address ""` | 422 | planned |
| TC-STF-02-A05 | `email "kiran@"` | 422 | planned |
| TC-STF-02-A06 | `gender "female"`; `gender "Unknown"` | 200 with gender `Female`; 400 "Invalid gender value: Unknown. Must be 'Male', 'Female', or 'Other'" and no users row left behind | planned |
| TC-STF-02-A07 | `account_type "Fixed"` | 422 | planned |
| TC-STF-02-A08 | `role_id` of the `Teacher` role | 200; users.role_id is the Teacher role | planned |
| TC-STF-02-A09 | `role_id` of the `Admin` role by a user holding only `staff:create` | 200 and an Admin login is created (documents the privilege-escalation gap) | planned |
| TC-STF-02-A10 | Tenant without a role named `Staff`, no `role_id` | 400 "Default 'Staff' role not found. Please provide a role_id." | planned |
| TC-STF-02-A11 | Unknown `role_id` (random uuid) | 500 "Error creating staff enrollment: ..."; no users or staff row | planned |
| TC-STF-02-A12 | Unknown `designation_id` | 500 "Error creating staff enrollment: ..."; the user row is rolled back too | planned |
| TC-STF-02-A13 | Duplicate email (same email as an existing staff) | 500 "Error creating staff enrollment: ..." and no new rows | planned |
| TC-STF-02-A14 | Two staff without email and the same phone | second call returns 500 (username collision) | planned |
| TC-STF-02-A15 | Same email created in `qa_school` and `qa_school_b` | both 200 (uniqueness is per tenant) | planned |
| TC-STF-02-A16 | Boundary: first_name 100 characters; 101 characters | 200; 500 | planned |
| TC-STF-02-A17 | Boundary: phone 15 characters; 16 characters | 200; 500 (no backend length validation) | planned |
| TC-STF-02-A18 | Boundary: `current_salary 99999999.99`; `100000000` | 200; 500 (numeric overflow) | planned |
| TC-STF-02-A19 | `experience_years -1`; `uan_number "abc"`; `pf_account_number "x"` | all 200 (server does not validate them) | planned |
| TC-STF-02-A20 | Whitespace-only phone `"   "` with no email | 200 and a user with username `"   "` is created (documents the missing trim) | planned |
| TC-STF-02-A21 | Staff role (read, list only) | 403 | planned |
| TC-STF-02-A22 | Teacher, Student and Parent roles | 403 each | planned |
| TC-STF-02-A23 | No Authorization header | 401 | planned |
| TC-STF-02-A24 | Staff created in tenant A | not returned by `GET /staff/enrollments` in tenant B; token A with `cschema` B gives 403 | planned |
| TC-STF-02-A25 | Response shape of a created row | has `id`, `user_id`, `photo_url`, `qualifications`; `created_at` and `updated_at` are null; HTTP status is 200 | planned |
| TC-STF-02-E01 | Web, Admin: fill the minimum fields (First Name `Kiran`, Phone `9876500012`, Address `12 MG Road`) and Save | toast "Staff enrollment created successfully"; the row shows Kiran with Active status | planned |
| TC-STF-02-E02 | Web: Save with an empty form | inline "First name is required", "Phone is required", "Address is required"; toast "Please fill in the required fields" | planned |
| TC-STF-02-E03 | Web: phone "98765" then "98765432101" then "98765abcde" | the three messages from the rules, no request sent | planned |
| TC-STF-02-E04 | Web: email "kiran@" | inline "Please enter a valid email address"; blocked | planned |
| TC-STF-02-E05 | Web: UAN "12345" and PF "AP-HYD" | toasts "UAN Number must be exactly 12 digits" and "Invalid PF Account Number format (e.g. AP/HYD/12345)" | planned |
| TC-STF-02-E06 | Web: full form with designation, role `Teacher`, work experience, bank details, salary, one qualification and a photo | one toast per step; the View dialog shows every value; the Role is stored | planned |
| TC-STF-02-E07 | Web: enroll with a duplicate email | toast "Failed to create staff enrollment: Error creating staff enrollment: ..."; the dialog stays open | planned |
| TC-STF-02-E08 | Web: unpaired qualification (Level set, Degree empty) | toast "Qualification Level and Degree / Course must both be filled in, or both left empty" | planned |
| TC-STF-02-E09 | Web, Staff and Teacher roles | no "Add Staff" button (Staff sees the list read-only; Teacher sees "Access Denied" because it lacks `staff:list`) | planned |
| TC-STF-02-E10 | Mobile, Admin: Add Staff with the minimum fields | toast "Staff Added - New staff member enrolled successfully."; card appears | planned |
| TC-STF-02-E11 | Mobile: empty form | inline errors; toast "Validation - Please fill in the required fields." | planned |
| TC-STF-02-E12 | Mobile: future joining date | the picker does not allow dates after today | planned |
| TC-STF-02-E13 | Mobile: enroll then check the Role | the new account has the `Staff` role (no role picker exists) | planned |
| TC-STF-02-E14 | Mobile, Student and Parent | no Staff hub or enrollment screen is reachable | planned |

Implemented in: backend/tests/unit/staff/test_enrollment.py (U01-U08, U11); web cases blocked.

---

## F03 First login of a new staff account

**Purpose.** A newly enrolled staff member signs in with the temporary password and is forced to choose a personal password before getting a session.

**Roles and permissions.** No permission is needed to log in. The forced change applies to roles `Staff`, `Teacher`, `Student` and `Parent` when `users.is_first_login = TRUE`. Admin and custom roles are never forced. Endpoints are owned by the auth module (`docs/features/auth.md`); the cases here cover the enrollment-driven path.

**Preconditions.** A staff member created by F02 (or F08) whose password has not been changed; an academic year exists (login requires `academic_year_id`).

**Steps, web.**
1. Open `/login`. Choose the "Academic Year", enter "Username / Admission Number" (the staff email, or the phone number when there is no email) and "Password" (the temporary password), click "Login".
2. The app opens "Set Your Password". Enter "New Password" (placeholder "Minimum 8 characters") and "Confirm Password", click "Set Password".
3. On success the user is signed in and lands on the dashboard. If the change token has expired or is invalid the page shows "Session expired or invalid - Please log in again with your temporary password."

**Steps, mobile.**
1. Login screen: organisation code, academic year, username (email or phone) and the temporary password.
2. "Set New Password" screen: "New Password" (min 8 characters) and "Confirm New Password", then submit. The user is signed in.

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
| TC-STF-03-A01 | Login as the new staff (email) with the temporary password | 200 `requires_password_change true`, `change_password_token` present, no `access_token` | planned |
| TC-STF-03-A02 | Same with a phone-only staff using the phone number | 200 with `requires_password_change true` | planned |
| TC-STF-03-A03 | `POST /auth/staff/set-password` with a valid token and an 8-character password | 200 full login response; `entity_id` equals the staff id; `role.name` is `Staff` | planned |
| TC-STF-03-A04 | Reuse the same token | 400 | planned |
| TC-STF-03-A05 | Password and confirmation differ | 400 "Passwords do not match" | planned |
| TC-STF-03-A06 | `new_password` of 7 characters | 422 | planned |
| TC-STF-03-A07 | Expired or malformed token | 401 | planned |
| TC-STF-03-A08 | Login again with the new password; with the old temporary password | 200 without `requires_password_change`; 401 | planned |
| TC-STF-03-A09 | Enroll with `role_id` of Admin, then log in with the temporary password | 200 with an access token immediately (Admin is not forced) | planned |
| TC-STF-03-A10 | Set `staff.is_active=false` via PATCH, then log in | login still succeeds (staff flag does not block) | planned |
| TC-STF-03-A11 | Set `users.is_active=false` (admin user management), then log in | 401 | planned |
| TC-STF-03-A12 | Login with the wrong academic year or missing `academic_year_id` | 400 or 422 | planned |
| TC-STF-03-A13 | Tenant isolation: the same email exists in tenant B | login in tenant A with tenant A header never authenticates the tenant B user; header `cschema` of tenant B with tenant A credentials returns 401 | planned |
| TC-STF-03-E01 | Web: log in as a new staff member, set a new password | "Set Your Password" appears; after "Set Password" the dashboard opens | planned |
| TC-STF-03-E02 | Web: passwords differ | an error banner shows "Passwords do not match" | planned |
| TC-STF-03-E03 | Web: open `/set-password` directly without a token | "Session expired or invalid" card with a button back to login | planned |
| TC-STF-03-E04 | Web: log out and log in with the new password | dashboard opens directly | planned |
| TC-STF-03-E05 | Mobile: first login and "Set New Password" | signed in; the Staff hub is visible only if the role holds the grants | planned |
| TC-STF-03-E06 | Mobile: password shorter than 8 characters | the screen refuses to submit or the server error is shown | planned |

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
| TC-STF-04-A01 | `POST /staff/{id}/qualifications` `{level:"Graduation", name:"B.Sc", passed_out_year:2015, percentage:78.5, university:"Osmania University"}` | 201; `percentage` "78.50"; `staff_id` equals the path id | planned |
| TC-STF-04-A02 | One add per level value | 201 for all four levels; the list returns them | planned |
| TC-STF-04-A03 | `level:"Masters"` | 422 | planned |
| TC-STF-04-A04 | Body without `level`; body without `name` | not 2xx (integrity error mapped by the middleware, expected 400); no row created | planned |
| TC-STF-04-A05 | Boundary: percentage 100.00, 999.99, 1000 | 201, 201, non-2xx (numeric overflow) | planned |
| TC-STF-04-A06 | Unknown staff id on POST and GET | 404 "Staff not found" | planned |
| TC-STF-04-A07 | `GET /staff/{id}/qualifications` with two rows | 200; two items with the documented fields | planned |
| TC-STF-04-A08 | `PUT` with `{percentage:82}` | 200; only percentage changed | planned |
| TC-STF-04-A09 | `PUT` and `DELETE` using a qualification id that belongs to another staff member | 404 "Qualification not found" | planned |
| TC-STF-04-A10 | `DELETE` own qualification | 200 `{"detail":"Qualification deleted successfully"}`; a later GET no longer lists it | planned |
| TC-STF-04-A11 | Delete the staff member | its qualifications are gone (cascade) | planned |
| TC-STF-04-A12 | Staff role (read, list): GET 200; POST, PUT, DELETE 403 | as stated | planned |
| TC-STF-04-A13 | Teacher, Student, Parent on all four endpoints | 403 | planned |
| TC-STF-04-A14 | Admin on all four endpoints | 2xx | planned |
| TC-STF-04-A15 | No token | 401 on all four | planned |
| TC-STF-04-A16 | Tenant B token on a tenant A staff id | 404 "Staff not found" | planned |
| TC-STF-04-E01 | Web, Admin: add a staff member with two qualifications (Graduation B.Tech 2016 72.5, Post Graduation MBA 2018 68) | both appear in the View dialog with level badges and "72.50%" and "68.00%" | planned |
| TC-STF-04-E02 | Web: edit, remove one block, change the other's percentage, add a new one, Save | the View dialog shows the updated set | planned |
| TC-STF-04-E03 | Web: one block with Level only | toast "Qualification Level and Degree / Course must both be filled in, or both left empty"; nothing saved | planned |
| TC-STF-04-E04 | Web: type a custom degree "D.Pharm" through "Add ..." | the value is saved and shown | planned |
| TC-STF-04-E05 | Mobile: edit a staff member, the existing qualifications load, change one, Save | toast "Updated - Staff member updated successfully."; View sheet reflects it | planned |
| TC-STF-04-E06 | Mobile: add a qualification while the backend rejects it | toast "Qualifications - Staff saved but some qualifications failed to save. Try again from edit." | planned |

Implemented in: backend/tests/unit/staff/test_qualifications_photo.py.

---

## F05 Staff photo

**Purpose.** Attach, replace or remove a photo of a staff member.

**Roles and permissions.** `staff:update` for upload and removal. The photo file itself is served at `/media/...` with no authentication.

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
4. Photos are served without authentication; anyone with the URL can fetch them.
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
| TC-STF-05-A01 | `POST` a 100 KB png | 200 `StaffEnrollmentOut`; `photo_url` matches `/media/<tenant_id>/staff/photos/<id>.png`; the file exists on disk | planned |
| TC-STF-05-A02 | `GET` the returned `photo_url` without an Authorization header | 200 image bytes (public media, documents the privacy gap) | planned |
| TC-STF-05-A03 | `.gif` file; text file renamed `.png` | 400 "Only jpg, png, webp files are allowed"; the renamed text file is accepted (no content check) | planned |
| TC-STF-05-A04 | File of exactly 2097152 bytes; of 2097153 bytes | 200; 400 "File size must not exceed 2 MB" | planned |
| TC-STF-05-A05 | Upload png then jpg for the same staff | the png file is deleted; `photo_url` ends with `.jpg` | planned |
| TC-STF-05-A06 | Upload without the `photo` part | 422 | planned |
| TC-STF-05-A07 | Unknown staff id on POST and DELETE | 404 "Staff not found" | planned |
| TC-STF-05-A08 | `DELETE` with a photo; `DELETE` again | 200 `{"detail":"Staff photo deleted successfully"}`; second returns 404 "No photo to delete" | planned |
| TC-STF-05-A09 | Admin 2xx; Staff, Teacher, Student, Parent roles | 403 for the four non-admin roles on POST and DELETE | planned |
| TC-STF-05-A10 | No token | 401 | planned |
| TC-STF-05-A11 | Photo uploaded in tenant A, staff id used from tenant B | 404 "Staff not found" | planned |
| TC-STF-05-E01 | Web, Admin: edit a staff member, Choose photo (jpg, 200 KB) | toast "Photo uploaded successfully"; the round image shows | planned |
| TC-STF-05-E02 | Web: choose a 3 MB file | toast "Photo must be under 2 MB"; no request | planned |
| TC-STF-05-E03 | Web: Add Staff with a photo | after Save the row's View dialog shows the photo | planned |
| TC-STF-05-E04 | Web: click the red X "Remove photo" on a saved photo | toast "Photo removed successfully"; placeholder icon returns | planned |
| TC-STF-05-E05 | Mobile: Upload Photo on Edit, then Remove | avatar image then initials again | planned |
| TC-STF-05-E06 | Mobile: choose a 3 MB image | toast "Photo Too Large - Photo must be under 2 MB." | planned |

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
3. The View icon ("View Staff Details") opens "Staff Details: <name>" using a fresh `GET /staff/enrollment/{id}`: photo, Basic, Contact, Professional, Account & Status, Qualifications, Work Experience, Bank Details, Salary & PF. "Created" and "Last Updated" show a dash because the table has no timestamps. "Edit Staff" in the footer opens the edit dialog (needs `staff:update`).
4. The Send icon ("Send Welcome/Recruiting Message") on each row is the QuickSend button (COM F04).

**Steps, mobile.**
1. Staff hub -> "Staff Enrollment". Cards list name, designation, department, contact and an Active or Inactive badge; "Search staff..." filters; "Columns" and "Export" (CSV, Excel) mirror the web; the footer shows "N staff member(s)".
2. "View" opens a bottom sheet with the same sections, loaded from `GET /staff/enrollment/{id}`. Pull to refresh reloads.
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
| TC-STF-06-A01 | Admin `GET /staff/enrollments` | 200 array including active and inactive staff; each item has `designation_id`, `qualifications`, `photo_url`; `created_at` null | planned |
| TC-STF-06-A02 | `GET /staff/enrollment/{id}` | 200 `StaffEnrollmentOut` with qualifications and string decimals | planned |
| TC-STF-06-A03 | Unknown id; non-UUID id | 404 "Staff not found"; 422 | planned |
| TC-STF-06-A04 | `GET /staff/` | 200 `[StaffOut]`; items carry `designation_obj {id,title}` and no `designation_id` | planned |
| TC-STF-06-A05 | `GET /staff/?gender=Female`; `?gender=Unknown` | only female staff; 422 | planned |
| TC-STF-06-A06 | `GET /staff/?is_active=true&skip=0&limit=1` | still returns every staff including inactive (parameters ignored) | planned |
| TC-STF-06-A07 | `GET /staff/by-designation?designation_id=<Teacher id>` | only Teacher staff | planned |
| TC-STF-06-A08 | Same call without the parameter; with an unknown valid uuid; with `abc` | all staff; `[]`; 422 | planned |
| TC-STF-06-A09 | Inspect the by-designation response body | does not contain `password_hash` (fixed 2026-10-02) | planned |
| TC-STF-06-A10 | Staff role (read, list): all four endpoints | 200 | planned |
| TC-STF-06-A11 | Teacher, Student, Parent on all four endpoints | 403 | planned |
| TC-STF-06-A12 | No token | 401 on all four | planned |
| TC-STF-06-A13 | Tenant isolation: tenant A staff absent from tenant B on `/enrollments`, `/`, `/by-designation`; detail by id returns 404 in B | as stated | planned |
| TC-STF-06-A14 | Token of tenant A with header `cschema: qa_school_b` | 403 | planned |
| TC-STF-06-E01 | Web, Admin: open Staff Enrollment | rows for the seeded staff; Meena Rao shows "Inactive" | planned |
| TC-STF-06-E02 | Web: search "asha", then "9876500002" | "asha" finds Asha Verma; the phone is not searched (no match) | planned |
| TC-STF-06-E03 | Web: sort by Name three times | ascending, descending, unsorted | planned |
| TC-STF-06-E04 | Web: set Rows per page to 10; Next and Previous | range label and rows update; Previous disabled on page 1 | planned |
| TC-STF-06-E05 | Web: Columns menu, hide Contact | the Contact column disappears; Export to CSV downloads without Email and Phone columns | planned |
| TC-STF-06-E06 | Web: View icon on Asha Verma | dialog "Staff Details: Asha Verma" with Designation "Teacher", Created and Last Updated "-" | planned |
| TC-STF-06-E07 | Web, Staff role | table and View work; Add, Edit, Delete, Bulk Upload not shown | planned |
| TC-STF-06-E08 | Web, Teacher, Student, Parent | `/staff/enrollment` shows "Access Denied" | planned |
| TC-STF-06-E09 | Mobile, Admin: Staff Enrollment list, search "ravi", View | one card; the sheet shows Designation "Driver" | planned |
| TC-STF-06-E10 | Mobile: Export to CSV | file `staff_enrollments_data.csv` is produced (browser download on Expo web) | planned |
| TC-STF-06-E11 | Mobile, Staff role | list and View only; no Add, Edit, Delete, Bulk Upload | planned |
| TC-STF-06-E12 | Mobile: empty tenant | text "No staff members yet" | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01-U02); web cases blocked.

---

## F07 Edit, deactivate and delete a staff member

**Purpose.** Correct a staff record, mark a person inactive, or remove the HR record.

**Roles and permissions.** Edit and deactivate: `staff:update`. Delete: `staff:delete`. Admin only in the default seed.

**Preconditions.** An existing staff member (F02).

**Steps, web.**
1. Staff -> Staff Enrollment -> Edit icon ("Edit Staff") or "Edit Staff" in the View dialog. The dialog "Edit Staff Enrollment" is pre-filled. Change fields (same labels and validations as F02) and "Save". Toast "Staff enrollment updated successfully".
2. To deactivate, untick "Active Staff Member" and Save. The Status column then shows "Inactive". To reactivate tick it again.
3. Delete icon ("Delete Staff") -> dialog "Delete Staff Enrollment" ("This action cannot be undone and will remove all associated attendance records.") -> "Delete". Toast "Staff enrollment deleted successfully".

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
| TC-STF-07-A01 | `PATCH {department:"Science"}` | 200; only `department` changed | planned |
| TC-STF-07-A02 | `PATCH {is_active:false}` | 200 `is_active` false; the row is still in `GET /staff/enrollments` | planned |
| TC-STF-07-A03 | `PATCH {first_name:""}`, `{email:null}`, `{phone:" "}`, `{address:""}` | 422 for each | planned |
| TC-STF-07-A04 | `PATCH {email:"bad"}`, `{gender:"male"}`, `{account_type:"Fixed"}` | 422 for each | planned |
| TC-STF-07-A05 | `PATCH {designation_id: <random uuid>}` | 400 "Data integrity violation - check for duplicate values or invalid references" | planned |
| TC-STF-07-A06 | `PATCH {email: <another staff's email>}` | 400 with the same message | planned |
| TC-STF-07-A07 | `PATCH {role_id: <Admin role>}` | 200; the user's role is unchanged | planned |
| TC-STF-07-A08 | `PATCH {email:"new@qa.example"}` then login with the old email; then with the new email | the old email still logs in; the new email returns 401 (users.username unchanged) | planned |
| TC-STF-07-A09 | `PATCH {last_name:null}` | 200 `last_name` null | planned |
| TC-STF-07-A10 | `PATCH` salary `"60000.50"` as a string and `60000.5` as a number | 200 for both; stored `"60000.50"` | planned |
| TC-STF-07-A11 | `PATCH` on an unknown id | 404 "Staff not found" | planned |
| TC-STF-07-A12 | `DELETE` a staff member with 2 attendance rows and 2 qualifications | 200 `{"detail":"Staff enrollment deleted successfully"}`; GET by id 404; attendance and qualification rows gone | planned |
| TC-STF-07-A13 | After DELETE, log in with the deleted person's email | login still succeeds (orphaned user, documents the gap) | planned |
| TC-STF-07-A14 | After DELETE, enroll the same email again | 500 "Error creating staff enrollment: ..." | planned |
| TC-STF-07-A15 | `DELETE` an unknown id | 404 | planned |
| TC-STF-07-A16 | Staff role (read, list): PATCH and DELETE | 403 | planned |
| TC-STF-07-A17 | Teacher, Student, Parent: PATCH and DELETE | 403 | planned |
| TC-STF-07-A18 | Admin PATCH and DELETE | 2xx | planned |
| TC-STF-07-A19 | No token | 401 | planned |
| TC-STF-07-A20 | Tenant B token PATCH or DELETE on a tenant A id | 404 "Staff not found"; the row is unchanged | planned |
| TC-STF-07-E01 | Web, Admin: edit Asha Verma's department to "Science" | toast "Staff enrollment updated successfully"; the Department column shows Science | planned |
| TC-STF-07-E02 | Web: untick "Active Staff Member", Save | the row's Status is "Inactive" | planned |
| TC-STF-07-E03 | Web: clear the Phone field, Save | inline "Phone is required"; no request | planned |
| TC-STF-07-E04 | Web: change email to one used by another staff | toast "Failed to update staff enrollment: Data integrity violation - check for duplicate values or invalid references" | planned |
| TC-STF-07-E05 | Web: delete a staff member | confirm dialog text mentions attendance records; toast "Staff enrollment deleted successfully"; the row disappears | planned |
| TC-STF-07-E06 | Web: edit, change Role in the dropdown, Save | the request succeeds but the role does not change (verify through the API) | planned |
| TC-STF-07-E07 | Mobile, Admin: edit a card and turn the switch off, Save | toast "Updated - Staff member updated successfully."; badge "Inactive" | planned |
| TC-STF-07-E08 | Mobile: delete via the confirm modal | toast "Deleted - Staff member removed." | planned |
| TC-STF-07-E09 | Mobile, Staff role | no Edit or Delete buttons on the cards | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01-U04).

---

## F08 Bulk enrollment from Excel

**Purpose.** Enroll many staff members at once from a filled spreadsheet.

**Roles and permissions.** `staff:create` for both the template download and the upload. Admin only in the default seed. The "Bulk Upload" buttons (web and mobile) are hidden without `staff:create`.

**Preconditions.** Designations and roles referenced by name already exist. A role named `Staff` exists if the Role column is left empty.

**Steps, web.**
1. Staff -> Staff Enrollment -> "Bulk Upload". The dialog "Bulk Staff Upload" says "Download the template, fill in staff rows, then upload the completed sheet."
2. "Download Template" saves `staff_bulk_upload_template.xlsx`. The Designation and Role columns carry dropdowns filled with the tenant's current designations and roles (hidden sheet "Lists"). Mandatory headers: First Name, Phone, Address.
3. "Browse File" selects an `.xlsx` or `.xls` file; "Upload" sends it. The result box shows "<n> of <total> staff member(s) created", a list "Row <r>: <name> (<email>)" and, in red, "<k> row(s) failed" with one message per row.

**Steps, mobile.**
1. Staff Enrollment -> "Bulk Upload" -> screen "Bulk Staff Upload". Step 1 "Download Template" (on a device it opens the share sheet; on Expo web it downloads). Step 2 "Upload Filled File": tap "Tap to select the filled Excel file", then "Upload".
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
| TC-STF-08-A01 | `GET /staff/enrollment/bulk-upload/template` as Admin | 200; content type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; opens with sheet "Staff Admission" and 33 header cells | planned |
| TC-STF-08-A02 | Template after creating designation "Cook" | the Designation dropdown list contains "Cook" | planned |
| TC-STF-08-A03 | Upload 3 valid rows (one with a qualification, one with Role "Teacher", one with Designation "Driver") | 200 `created` length 3, `errors` [], `total_rows` 3; each staff has the right role, designation and qualification | planned |
| TC-STF-08-A04 | Upload 1 valid row, 1 duplicate email, 1 unknown designation, 1 missing phone | 200; `created` 1; errors "Row 3: A user with email '...' already exists", "Row 4: Designation 'X' not found", "Row 5: Phone is required"; `total_rows` 4 | planned |
| TC-STF-08-A05 | Row with Role "Nonexistent" | error "Row N: Role 'Nonexistent' not found" | planned |
| TC-STF-08-A06 | Row with Qualification Level only | error "Row N: Qualification Level and Degree/Course must be provided together" | planned |
| TC-STF-08-A07 | Row with Qualification Level "Masters" | error "Row N: Invalid Qualification Level 'Masters'. Must be one of: ..." | planned |
| TC-STF-08-A08 | Row with email "bad"; row with Gender "X" | errors "Row N: email - ..." and "Row N: Invalid gender value: X. ..." | planned |
| TC-STF-08-A09 | Two rows in one file with the same email | first created; second fails with "A user with email ... already exists" | planned |
| TC-STF-08-A10 | Two phone-only rows with the same phone | first created; second error starts "Row N: Error creating staff enrollment" | planned |
| TC-STF-08-A11 | Upload `staff.csv` or `staff.txt` | 400 "File must be an Excel (.xlsx/.xls) file" | planned |
| TC-STF-08-A12 | Upload a `.xlsx` file with garbage bytes | 400 "Invalid Excel file: ..." | planned |
| TC-STF-08-A13 | Sheet without the Address header | 400 "Missing required column(s): Address" | planned |
| TC-STF-08-A14 | Header-only sheet | 200 `{created:[],errors:[],total_rows:0}` | planned |
| TC-STF-08-A15 | Date of birth cells "25-12-1990" and an Excel date cell | both stored as 1990-12-25 | planned |
| TC-STF-08-A16 | Rows created by upload log in with the temporary password and must change it | as F03 | planned |
| TC-STF-08-A17 | Staff, Teacher, Student, Parent on both endpoints | 403 | planned |
| TC-STF-08-A18 | No token | 401 on both | planned |
| TC-STF-08-A19 | Upload in tenant A; tenant B lists staff | none of the new staff visible; a Designation that exists only in tenant B fails with "not found" in tenant A | planned |
| TC-STF-08-E01 | Web, Admin: Bulk Upload dialog, Download Template | file `staff_bulk_upload_template.xlsx` downloads | planned |
| TC-STF-08-E02 | Web: upload a sheet with 2 valid rows | result "2 of 2 staff member(s) created" and two "Row n: name (email)" lines; the table shows the new staff after closing | planned |
| TC-STF-08-E03 | Web: upload a sheet with one bad row | "1 of 2 staff member(s) created" and "1 row(s) failed" with the message | planned |
| TC-STF-08-E04 | Web: try a `.pdf` file | the file picker offers only `.xlsx,.xls`; a forced upload shows the server error toast | planned |
| TC-STF-08-E05 | Web, Staff role | no "Bulk Upload" button | planned |
| TC-STF-08-E06 | Mobile, Admin: Bulk Upload, pick a valid file, Upload | toast "Upload Complete - 2 of 2 staff created successfully."; chips "2 created", "0 failed", "2 total rows" | planned |
| TC-STF-08-E07 | Mobile: file with one failing row | toast "Upload Finished With Errors - 1 created, 1 failed. See details below."; the error line is listed | planned |
| TC-STF-08-E08 | Mobile, Staff role | the Bulk Upload toolbar button is hidden; opening `/staff/bulk-upload` shows the access-denied panel | planned |

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
| TC-STF-09-A01 | Staff `Ravi Kumar` (designation `Driver`) exists; Admin `GET /staff/drivers` | 200; contains `{full_name:"Ravi Kumar", user_id:<his user id>}` | planned |
| TC-STF-09-A02 | Response keys | exactly `full_name` and `user_id` (no `id`, no `staff_id`) | planned |
| TC-STF-09-A03 | Designations `driver`, `DRIVER`, `Bus Driver` each with one staff member | the first two are listed; `Bus Driver` is not | planned |
| TC-STF-09-A04 | Inactive driver | still listed | planned |
| TC-STF-09-A05 | Tenant with no driver designation | 200 `[]` | planned |
| TC-STF-09-A06 | Admin, Teacher, Staff roles | 200 for all three | planned |
| TC-STF-09-A07 | Student and Parent | 403 | planned |
| TC-STF-09-A08 | No token | 401 | planned |
| TC-STF-09-A09 | Tenant isolation: tenant A drivers not visible with a tenant B token | `[]` in B | planned |
| TC-STF-09-E01 | Web, Admin: transport trip form driver selector | contains "Ravi Kumar"; saving a trip stores his `user_id` | planned |
| TC-STF-09-E02 | Web: remove the Driver designation from Ravi (edit staff, clear designation) and reopen the selector | "Ravi Kumar" is no longer offered | planned |

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
1. Staff -> "Manage Attendance" card or `/staff/attendance` (page "Staff Attendance", card "Attendance Overview").
2. Pick the "Date" (default today). The summary shows "Attendance Analysis", "<n>% Present" and counters Present, Absent, Late, Half Day; the list shows each staff member with a coloured status chip, email and department.
3. Change a row's status with its dropdown (Present, Absent, Late, Half Day). Changed rows are tracked and the badge "Unsaved Changes" appears. "Search by name, email, or department..." filters the roster. "Refresh" reloads the day's data.
4. Click "Save Attendance". Only modified rows are sent, in parallel: present to non-present with no row creates, non-present to non-present updates, non-present back to present deletes. Toast "Attendance saved successfully!"; a failure shows the first error message and no indication of which calls failed.
5. The Send icon on a non-present row is QuickSend with template "Staff Attendance" (COM F04); it is disabled for present staff.

**Steps, mobile.**
1. Staff hub -> "Attendance" (screen "Staff Attendance"). Use the arrows or tap the date to choose a day (`Future Date - Read Only` appears for future days and disables editing).
2. The cards "Attendance Analysis" (PRESENT, ABSENT, LATE, HALF DAY) and the roster with a status dropdown per row; a "Modified" badge marks changed rows. "Columns" toggles Email, Department, Status, Modified. "Search by name, email, or department...".
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
| TC-STF-10-A01 | Admin `POST /staff/attendance` `{staff_id, date:"2026-10-01", status:"absent"}` | 200 `StaffAttendanceOut` with `status` absent, `remarks` null | planned |
| TC-STF-10-A02 | One create per status absent, late, half_day, leave | 200 for all (on different dates) | planned |
| TC-STF-10-A03 | `status:"Present"`; `status:"holiday"`; missing `date`; missing `staff_id` | 422 each | planned |
| TC-STF-10-A04 | Second `POST` for the same staff and date | 500 "Error creating staff attendance: ..." (unique `uq_staff_date`); the original row unchanged | planned |
| TC-STF-10-A05 | `POST` for an unknown `staff_id` | 500 | planned |
| TC-STF-10-A06 | `POST` with a date next year | 200 (no future guard) | planned |
| TC-STF-10-A07 | `PATCH /staff/attendance/{id}` `{status:"late", remarks:"Bus delay"}` | 200 with both values | planned |
| TC-STF-10-A08 | `PATCH` with `{status:"Late"}` | 422 | planned |
| TC-STF-10-A09 | `PATCH` and `DELETE` on a random uuid | 404 "Attendance record not found" | planned |
| TC-STF-10-A10 | `DELETE` an existing row | 200 `{"detail":"Staff attendance deleted successfully"}`; the staff member is present again for that date | planned |
| TC-STF-10-A11 | By-date `PATCH` for today with two entries (one new absent, one existing changed to late) | 200 list of 2 rows with the new statuses | planned |
| TC-STF-10-A12 | By-date `PATCH` for tomorrow; with `[]`; with status "sick" | 400 "Cannot update attendance for future dates"; 400 "No attendance updates provided"; 400 "Invalid attendance status 'sick'. ..." | planned |
| TC-STF-10-A13 | By-date `PATCH` with an unknown `staff_id` | 500 "Error updating staff attendance by date: ..."; no partial rows persisted | planned |
| TC-STF-10-A14 | By-date `PATCH` with an invalid date segment `2026-13-01` | 422 | planned |
| TC-STF-10-A15 | Staff role (no `staff_attendance` grant) on POST, PATCH, DELETE, by-date PATCH | 403 each | planned |
| TC-STF-10-A16 | A custom role holding only `staff_attendance:create`: POST 200; PATCH 403; DELETE 403 | as stated (actions are independent) | planned |
| TC-STF-10-A17 | Teacher, Student, Parent on all four write endpoints | 403 | planned |
| TC-STF-10-A18 | No token | 401 on all four | planned |
| TC-STF-10-A19 | Tenant isolation: attendance created in tenant A for a tenant A staff id; tenant B `PATCH` on that attendance id | 404 "Attendance record not found" | planned |
| TC-STF-10-A20 | Token tenant A with `cschema: qa_school_b` | 403 | planned |
| TC-STF-10-E01 | Web, Admin: open `/staff/attendance` for today | every active seeded staff shows Present; analysis shows "100% Present" | planned |
| TC-STF-10-E02 | Web: set Asha Verma to Absent and Ravi Kumar to Late, Save Attendance | toast "Attendance saved successfully!"; counters Absent 1, Late 1; after Refresh the statuses persist | planned |
| TC-STF-10-E03 | Web: set Asha back to Present, Save | row deleted; after Refresh she is Present (requires `staff_attendance:delete`) | planned |
| TC-STF-10-E04 | Web: change a status and navigate by changing the date | the unsaved badge clears and the new date loads its own rows | planned |
| TC-STF-10-E05 | Web: search "ravi" | only Ravi Kumar listed; "1 of N" count shown | planned |
| TC-STF-10-E06 | Web, a role with `staff_attendance:list` but not `create`/`update` | statuses are plain text; no Save button | planned |
| TC-STF-10-E07 | Web, an Admin without `staff_attendance:delete` switches an absent row to present and saves | the save fails with a toast and the row remains absent after Refresh (documents rule 5) | planned |
| TC-STF-10-E08 | Web, Staff role (no attendance grant) | the hub hides the "Staff Attendance" card; the page's data calls return 403 | planned |
| TC-STF-10-E09 | Web: the Send icon on an absent row | opens "Send Message" for that staff (COM F04); the icon is disabled for present rows | planned |
| TC-STF-10-E10 | Mobile, Admin: Staff -> Attendance, set a staff member Absent, Save Attendance (1) and confirm | toast "Success - Attendance updated successfully"; Absent counter 1 | planned |
| TC-STF-10-E11 | Mobile: go to tomorrow with the arrows | label "Future Date - Read Only"; dropdowns disabled | planned |
| TC-STF-10-E12 | Mobile: Save with no changes | toast "No Changes - No attendance changes to save" | planned |
| TC-STF-10-E13 | Mobile: Columns, deselect Email | the Email text disappears from rows | planned |
| TC-STF-10-E14 | Mobile, Staff role | the hub card "Attendance" is hidden; opening the route shows access denied | planned |

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
| TC-STF-11-A01 | Rows: Asha absent on 2026-10-01, Ravi late on 2026-10-01, Asha half_day on 2026-10-02. `GET /staff/attendance/by-date/2026-10-01` | 200; exactly two rows | planned |
| TC-STF-11-A02 | `GET /staff/attendance?start_date=2026-10-01&end_date=2026-10-02` | 200; three rows (inclusive bounds) | planned |
| TC-STF-11-A03 | `GET /staff/attendance?start_date=2026-10-02` (end missing) | 200; all three rows (filter ignored) | planned |
| TC-STF-11-A04 | `GET /staff/attendance?name=ash` with both dates | only Asha's rows | planned |
| TC-STF-11-A05 | `GET /staff/{Asha}/attendance/filter?start_date=2026-10-02` | one row (2026-10-02) | planned |
| TC-STF-11-A06 | `GET /staff/{Asha}/attendance/filter` without dates | both of Asha's rows | planned |
| TC-STF-11-A07 | `GET /staff/{random uuid}/attendance/filter` | 200 `[]` | planned |
| TC-STF-11-A08 | `GET /staff/attendance/{id}` for an existing row; for a random uuid | 200 row; 404 "Staff attendance record not found" | planned |
| TC-STF-11-A09 | `GET /staff/attendance/by-date/2026-13-45`; `.../abc`; filter with `start_date=x` | 422 for each | planned |
| TC-STF-11-A10 | A day without exceptions | 200 `[]` | planned |
| TC-STF-11-A11 | Response fields | each item has `id`, `staff_id`, `date` (ISO), `status`, `remarks` | planned |
| TC-STF-11-A12 | Admin on all four endpoints | 200 | planned |
| TC-STF-11-A13 | Staff, Teacher, Student, Parent on all four | 403 | planned |
| TC-STF-11-A14 | A custom role with only `staff_attendance:list`: list endpoints 200, `/attendance/{id}` 403 | `read` and `list` are independent | planned |
| TC-STF-11-A15 | No token | 401 on all four | planned |
| TC-STF-11-A16 | Tenant isolation: tenant B calls the four endpoints for tenant A data | `[]` for lists, 404 for the single record | planned |
| TC-STF-11-E01 | Web, Admin: set Asha absent, save, change the date away and back | Asha is Absent again (loaded from by-date) | planned |
| TC-STF-11-E02 | Web: yesterday's date with no rows | everyone Present, 100% | planned |
| TC-STF-11-E03 | Web, Admin: navigate Reports for staff attendance (`/reports/attendance/staff`) | the absent record is visible there (cross-check with RPT) | planned |
| TC-STF-11-E04 | Mobile, Admin: day with Asha absent | Absent counter 1; Asha's dropdown shows Absent | planned |
| TC-STF-11-E05 | Mobile: previous-day arrow, then next-day arrow | the data refreshes each time and returns to the original state | planned |

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
3. When the API returns 403 or 404 the page shows "My Profile" with "Account Information": Username, Email, Role, Academic Year.

**Steps, mobile.**
1. Profile (from the app menu) for staff, teacher or admin roles: "Staff Profile" with First Name, Last Name, Email, Phone and a section "Employment Information" (Employee ID, Designation, Date of Joining, Status).
2. The pencil button switches Email and Phone to inputs; "Save Changes" validates (email must contain "@": "Please enter a valid email address"; phone at least 10 characters: "Please enter a valid phone number") and shows "Success - Profile updated successfully". "Cancel" discards.

**Expected results.** The response is `{staff_id, user_id, first_name, last_name, email, phone, designation, employee_id, date_of_joining, is_active, profile_photo_url}`. `employee_id` and `profile_photo_url` are always null. Each view and each update writes a `profile_audit_logs` row. An update changes `staff.email` and `staff.phone` only (not `users.email` or `users.username`).

**API endpoints.**
- `GET /profile/staff/me` -> `StaffProfileOut`.
- `PUT /profile/staff/me` body `{email?, phone?}` -> `StaffProfileOut`.
- Related (auth module): `POST /profile/change-password` (`profile:update_own`), see `docs/features/auth.md`.

**Rules and validations.**
1. The profile is found by `Staff.user_id == current user`; no staff row gives 404 "Staff profile not found".
2. Only non-null `email` and `phone` are applied; there is no format validation on the server (plain strings). The clients validate (web: phone exactly 10 digits; mobile: at least 10 characters).
3. **Defect D-STF-03:** when the staff member has a designation, `get_profile` reads `designation_obj.name`, but `Designation` has only `title`, so the call raises AttributeError and the response is 500. Because `PUT` runs `get_profile` after committing the change, the new email and phone are saved but the client receives a 500. The profile works only for staff with no designation.
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
| TC-STF-12-A01 | Staff user without a designation, `GET /profile/staff/me` | 200 with the documented fields; `employee_id` null | planned |
| TC-STF-12-A02 | Staff user with designation Teacher, `GET /profile/staff/me` | expected 200 with `designation "Teacher"`; currently 500 (D-STF-03) | planned |
| TC-STF-12-A03 | `PUT {email:"asha.new@qa.example", phone:"9000000001"}` (no designation) | 200; `GET /staff/enrollment/{id}` shows the new values; `users.username` is unchanged | planned |
| TC-STF-12-A04 | `PUT` for a staff user with a designation | currently 500 but the change is stored (D-STF-03) | planned |
| TC-STF-12-A05 | `PUT {}` | 200; nothing changes | planned |
| TC-STF-12-A06 | `PUT {email:"not-an-email"}` | 200 (no server validation, documents the gap) | planned |
| TC-STF-12-A07 | `PUT {email:<another staff's email>}` | error response (unique violation) and no change | planned |
| TC-STF-12-A08 | Admin user with no staff row | 404 "Staff profile not found" | planned |
| TC-STF-12-A09 | Role without `profile:read_own` (default-seed Staff) | 403 with `error: permission_denied` | planned |
| TC-STF-12-A10 | Role with `read_own` but not `update_own`: GET 200, PUT 403 | as stated | planned |
| TC-STF-12-A11 | Student and Parent roles | Student 404 (no staff row) when granted; Parent 403 | planned |
| TC-STF-12-A12 | No token | 401 | planned |
| TC-STF-12-A13 | User of tenant B calling `/profile/staff/me` with tenant A header | 403; each user only sees their own row | planned |
| TC-STF-12-A14 | Each GET adds a `profile_audit_logs` row (DB assertion) | count increases by one per GET | planned |
| TC-STF-12-E01 | Web, Staff user without a designation: open `/profile` | "Staff Profile" shows First Name, Last Name, Designation "N/A", Employee ID "N/A", Date of Joining, Status "Active", Email, Phone | planned |
| TC-STF-12-E02 | Web: Edit Email & Phone with valid values, Update | toast "Staff profile updated successfully!"; the page shows the new values | planned |
| TC-STF-12-E03 | Web: phone "98765" | "Phone must be 10 digits"; no request | planned |
| TC-STF-12-E04 | Web: email "abc" | "Invalid email address" | planned |
| TC-STF-12-E05 | Web: a user whose role has no staff row (provisioning Admin) | "My Profile" with Account Information (Username, Email, Role, Academic Year) | planned |
| TC-STF-12-E06 | Web: user with a designation opens the profile | the page shows "Your profile could not be loaded right now. Please try again later." until D-STF-03 is fixed | planned |
| TC-STF-12-E07 | Web, a role lacking `profile:update_own` | the "Edit Email & Phone" button is hidden | planned |
| TC-STF-12-E08 | Mobile: Profile as a staff user, edit email and phone, Save Changes | toast "Success - Profile updated successfully" | planned |
| TC-STF-12-E09 | Mobile: phone "12345" | toast "Validation Error - Please enter a valid phone number" | planned |
| TC-STF-12-E10 | Mobile: Staff role on `/staff/profile` | the screen shows data but the pencil edit button is absent (guarded by `staff:update`, which the Staff role lacks) | planned |

Implemented in: backend/tests/unit/staff/test_staff_schemas.py (U01), backend/tests/unit/staff/test_attendance_drivers_profile.py (U02-U04).

---

## Known gaps

Findings from reading the code (module doc `docs/modules/staff.md` and the code agree unless stated).

**Defects**
- D-STF-01: Fixed (2026-10-02): a duplicate designation title on create returns 400 and the dropdown cache is cleared by create, update and delete.
- D-STF-02: `GET /staff/by-designation` has no `response_model` and serialises the raw ORM rows, including the loaded `user` relationship with `password_hash`. Verified by encoding a `Staff` object with a loaded `user` through FastAPI's `jsonable_encoder`; not confirmed against a live database. Fixed (2026-10-02): `response_model=list[StaffOut]` added.
- D-STF-03: `GET` and `PUT /profile/staff/me` return 500 for any staff member who has a designation (`designation_obj.name` does not exist; the column is `title`). `PUT` still saves the change before failing.
- The default seed (`permission_catalog.py`) gives no `profile:read_own` or `profile:update_own` to Admin, Teacher or Staff, so the staff profile is 403 on a freshly provisioned tenant; it also has no `send_sms` grants.

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
