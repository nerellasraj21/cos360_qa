# Certificates (CER)

Feature documentation and test specification for the Certificates module. It has two independent subsystems: (A) uploaded certificate files (`student_certificates`: documents the school receives and certificates the school issues as files, plus `certificate_types`) and (B) issuable certificates (HTML templates and certificates generated from them). It covers the admin screens, the student, parent and teacher views, downloads, and the background cleanup of replaced files. Test case IDs use the scheme `TC-CER-<FF>-<P><NN>` from `docs/testing/strategy.md`. Facts were read from the code on 2026-10-02 and the walkthroughs were re-checked against the running web and mobile apps on 2026-10-07; where `docs/modules/certificates.md` disagrees with the code, this page documents the code and lists the difference under "Known gaps".

_Last verified against code: 2026-10-07_

Related: `docs/modules/certificates.md`, `docs/features/students.md` (the merged student documents list includes certificates; student selection; parent child selector), `docs/permissions.md`, `docs/architecture.md` (section 5, local `media/` storage served without auth; section 6, Celery beat).

## Roles

| Role | What it can do in this module (default catalog, `backend/app/service/tenant/permission_catalog.py`, plus the role-name checks in the code) |
|---|---|
| Admin | Everything. Only role that passes the "Admin by role name" checks: upload received documents, issue certificates, the admin lists, the student selector, template create/update/delete and generating certificates. Holds `certificate_types:*`, `student_certificates:*`, `issuable_certificates:*` |
| Staff | `certificate_types:read/list`; `student_certificates:create/read/update/list` (no delete). Because the admin endpoints check the role name, Staff cannot upload, issue, list by category or use the selector (403). Staff can call the legacy `POST /certificates/`, `GET /certificates/`, `GET /certificates/{id}`, `PATCH`, download, `my-child/*` and `types/search` |
| Teacher | `certificate_types:read/list`; `student_certificates:read/list`. Read-only: `GET /certificates/` (any student), `GET /certificates/{id}`, download, `my-child/*`, `types/search` |
| Student | Own scope: `student_certificates:read_own/list_own` (`GET /certificates/my`, `GET /{id}`, download of own files), `certificate_types:read/list` |
| Parent | Related scope: `student_certificates:read_related/list_related` (`my-child/*` for linked children only). No `certificate_types` grant. Parents never upload |

Note on permission checks: most endpoints use `check_role_plan_permission_with_error`, which requires the exact action (`list`, `read`) and ignores `_own`/`_related`; the `my-child/*` endpoints use `check_user_resource_access`, which honours them. The tests assert the default catalog; parametrise if the QA tenant differs.

## Feature index

| ID | Title |
|---|---|
| F01 | Certificate types |
| F02 | Issuable certificate templates |
| F03 | Select a student for certificate work (admin selector) |
| F04 | Upload a received document |
| F05 | Issue a certificate file |
| F06 | Generate a certificate from a template |
| F07 | View a student's certificates (admin lists and metadata) |
| F08 | Update or replace a certificate file |
| F09 | Delete or revoke a certificate |
| F10 | Download a certificate |
| F11 | Student: my certificates |
| F12 | Parent: child certificates |
| F13 | Teacher: read-only student certificates |
| F14 | File audit log and stale file cleanup |

## Conventions for the test tables

- "Default catalog" means the role grants in `permission_catalog.py`. 403 is a permission failure; 401 is no token.
- QA data assumed: tenants `qa_school` (tenant A) and a second tenant B; students in Class 1 / A and Class 2 / A; at least two certificate types ("Bonafide", "Transfer Certificate"); a parent linked to one student and a second parent linked to another; Admin, Staff, Teacher, Student and Parent logins for the QA tenant.
- "Tenant isolation": data from tenant A is invisible in tenant B, and a token for tenant A sent with a `cschema` header for tenant B is 403. Files are stored under `media/<tenant id>/<module>/<student id>/<uuid>.<ext>`.
- Test files: a small valid PDF starting with `%PDF`, a PNG, a DOCX, a text file renamed `.pdf`, a `.exe`, an 11 MB file, a file of exactly 10 MB (10,485,760 bytes).
- Certificate list endpoints return `{items, total, has_next}`; `GET /certificates/types/` returns `{items, total_count, has_next}`.
- Routes of the issuable subsystem and the types routes end with a trailing slash exactly as declared.
- Web screens are in `web/src`, mobile screens in `mobile/app/students`. Seeded menu entries: Students > Student Certificates (`/students/studentcertificates`), Certificate Types (`/students/certificatetypes`), Certificate Templates (`/students/certificatetemplates`). Student and Parent menus contain only "Student Certificates". On mobile the menu entry Student Certificates opens `app/students/studentcertificates.tsx` (role router: Admin view for every role except Student and Parent); `certificates.tsx` is an older admin screen reachable at `/students/certificates`.

### Manual UI test data

UI cases (IDs ending `-E`) use the 8-column layout, the seeded tenant `qa_manual` and the logins described in `docs/features/students.md` ("Manual UI test data"). Seeded data the cases rely on:

- Students: Harsha Raju (004, Class 1 / 1-B; seeded student login 004) and his sister Tanvi Raju (005, Class 4 / 4-B; login 005); seeded parent login venkat.raju@example.com for both. Kavya Verma (006, Class 1 / 1-A).
- Certificate types: Bonafide Certificate, Transfer Certificate, Conduct Certificate, Study Certificate.
- Issuable templates: Bonafide Certificate (blue), Conduct Certificate (green), Study Certificate (orange), Transfer Certificate (red).
- Generated (issuable) certificates: Bonafide for Aarav Gupta and Vihaan Rao, Conduct for Diya Goud and Navya Agarwal, Study for Kavya Verma. No uploaded (received or issued) certificate files are seeded, so Harsha Raju and Tanvi Raju start with "(0 total)".
- Data the cases create: type "QA Bonafide" (TC-CER-01-E01), a received document (TC-CER-04-E01) and an issued certificate (TC-CER-05-E01) for Harsha Raju, "QA " templates. Do not edit, revoke or delete seeded types, templates or generated certificates.
- Test files: a small valid PDF (starts with `%PDF`), a PNG and an 11 MB PDF.

---

## F01 Certificate types

**Purpose.** Maintain the list of certificate types (Bonafide, Transfer Certificate, Birth Certificate, ...) used when uploading or issuing.

**Roles and permissions.** Create, update, delete: `certificate_types:create/update/delete` (Admin only). List, dropdown, get one: `certificate_types:list/read` (Admin, Staff, Teacher, Student; Parent has none). `GET /certificates/types/search` needs `student_certificates:list` (Admin, Staff, Teacher). Menu: Students > Certificate Types (Admin, Staff, Teacher).

**Preconditions.** None.

**Steps, web.**
1. Students > Certificate Types (page "Certificate Types").
2. Use the filter row "Filters": search box "Search name or description..." (client side, name and description), column headers "Name" and "Description" toggle sorting.
3. "Add Certificate Type" (needs create) opens "Create Certificate Type": "Name *" (max 100 characters), "Description" (max 255, optional), "Save". Empty name shows toast "Certificate type name is required". Success toast "Certificate type created successfully".
4. Row actions: Edit ("Edit Certificate Type", dialog "Edit Certificate Type") and Delete ("Delete Certificate Type": "Are you sure you want to delete the certificate type "<name>"? ..." > "Delete"). Toasts "Certificate type updated successfully" and "Certificate type deleted successfully".
5. Empty states: "No certificate types found." with "Create First Certificate Type"; "No certificate types match your search.". Staff, Teacher and Student see the list without "Add Certificate Type", Edit or Delete. A Parent gets 403 from the list call and sees "No certificate types found." with the "Create First Certificate Type" button (not permission-gated). Error toasts show the API detail, for example "Certificate type name '<name>' already exists".

**Steps, mobile.** Students > Certificate Types (`certificatetypes.tsx`): button "Add Certificate Type" opens the form "Type Name *" ("Enter certificate type name") and "Description" with "Add Type" (the button turns into "Cancel"); list cards with "Edit" (modal "Edit Certificate Type") and "Delete" (confirm "Delete Certificate Type" "Are you sure you want to delete this certificate type?"). Toasts "Success - Certificate type created successfully!", "... updated successfully!", "... deleted successfully!"; validation toast "Please enter a certificate type name". The add, edit and delete controls are not permission-gated on mobile (Staff and Teacher see them; the API answers 403).

**Expected results.** The type appears in every type picker (upload, issue, search). Deleting is refused while any student certificate uses it.

**API endpoints.**
- `POST /certificates/types/` body `{name, description?}` returns 201 `{id, name, description}` (rate limited, 30 per minute).
- `GET /certificates/types/?skip=0&limit=10` returns `{items, total_count, has_next}` ordered by name; `skip >= 0`, `limit` 1..100.
- `GET /certificates/types/search?q=&limit=10` returns `[{id, name, description}]` (name ILIKE `%q%`, ordered by name, `limit` 1..100).
- `GET /certificates/types/dropdown` returns `[{id, name}]` ordered by name (cached 300 seconds, rate limited 300 per minute; cache cleared on create, update, delete).
- `GET /certificates/types/{certificate_type_id}`.
- `PUT /certificates/types/{certificate_type_id}` body `{name?, description?}`.
- `DELETE /certificates/types/{certificate_type_id}` returns `{"message":"Certificate type deleted successfully"}`.

**Rules and validations.**
- `name` is unique within the tenant, exact (case-sensitive) match: duplicate is 400 "Certificate type name '<name>' already exists". On update the uniqueness check is skipped when the name is unchanged or empty.
- The API does not enforce a minimum length (an empty name is accepted); the web enforces a non-empty name. DB limits: name 100 characters, description 255; longer values produce a 500 "Error creating certificate type: ...".
- Delete is 400 "Cannot delete certificate type '<name>' because it is being used by <n> student certificate(s). Please reassign or delete the certificates first." while any `student_certificates` row uses the type.
- Always call with the trailing slash for the list: `GET /certificates/types` (no slash) is parsed as `GET /certificates/{certificate_id}` and fails with a UUID 422.
- Create and update use `commit()` then `refresh()` (the repo rule says `flush()` then `select()` then `commit()`).

**Error and edge cases.** Unknown id 404 "Certificate type with id <id> not found". The same name in tenant B is allowed. A type used only by a generated (issuable) certificate is not protected (different table).

**Unit-testable logic.** `check_certificate_type_name_unique` (exclude self), delete dependency message, dropdown cache invalidation, web client-side filter and sort.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-01-U01 | Uniqueness check for "Bonafide" when it exists; for "bonafide"; when updating the same row with the same name | 400 "Certificate type name 'Bonafide' already exists"; allowed (exact match); allowed (self excluded) | passing |
| TC-CER-01-U02 | Delete dependency message for 3 certificates using type "Transfer Certificate" | Message contains the type name and "3 student certificate(s)" | passing |
| TC-CER-01-U03 | Update with name "" and with name equal to current | Uniqueness check is skipped in both cases | passing |
| TC-CER-01-U04 | Web filter on "bona" over [Bonafide, Transfer] and sort by name toggled twice | Only Bonafide; ascending then descending order | blocked: web filter and sort are inline in CertificateTypesPage.tsx |
| TC-CER-01-U05 | Dropdown cache invalidated after create, update and delete | Cache key `certificate_types_dropdown` cleared each time | passing |
| TC-CER-01-A01 | Admin creates a type with name and description | 201 `{id, name, description}` | passing |
| TC-CER-01-A02 | Create duplicate name; create the same name in tenant B | 400 "Certificate type name '<n>' already exists"; 201 in tenant B | passing |
| TC-CER-01-A03 | Create without `name`; with a 101 character name; with a 256 character description | 422; 500 "Error creating certificate type: ..." (documented); 500 | passing |
| TC-CER-01-A04 | Create with `name` "" | 201 (API accepts; documented gap) | passing |
| TC-CER-01-A05 | List with 15 types, `limit=10&skip=0` then `skip=10` | 10 items `has_next` true; 5 items `has_next` false; `total_count` 15; ordered by name | passing |
| TC-CER-01-A06 | List `limit=0`, `limit=101`, `skip=-1`; `GET /certificates/types` without slash | 422 each; 422 UUID error for the slashless path | passing |
| TC-CER-01-A07 | Search `q=bon`, `q=` (empty), `limit=100` and `limit=101` | Matching types ordered by name (case-insensitive); all types; 200; 422 | passing |
| TC-CER-01-A08 | Dropdown after creating a new type | New type present immediately (cache invalidated) | passing |
| TC-CER-01-A09 | Get one by id; unknown id; malformed id | 200; 404 "Certificate type with id <id> not found"; 422 | passing |
| TC-CER-01-A10 | PUT rename to an existing name; rename to a free name; description only | 400; 200; 200 (name unchanged) | passing |
| TC-CER-01-A11 | DELETE an unused type; delete a type used by one certificate | 200 `{"message":...}`; 400 with the dependency message | passing |
| TC-CER-01-A12 | Permission matrix: POST, PUT, DELETE | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-CER-01-A13 | Permission matrix: GET list, dropdown, get one | Admin, Staff, Teacher, Student 200; Parent 403 | passing |
| TC-CER-01-A14 | Permission matrix: GET search | Admin, Staff, Teacher 200; Student 403; Parent 403 | passing |
| TC-CER-01-A15 | No token on every endpoint of this feature | 401 | passing |
| TC-CER-01-A16 | Tenant isolation: a type created in tenant A is absent from tenant B list; token A with header B | Absent; 403 | passing |
| TC-CER-01-A17 | Rate limit: 31 creates within a minute | The 31st returns 429 | skipped: skipped: needs the rate limiter, which is disabled in the QA API |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-01-E01 | P1 | Web | Admin | QA Admin login; no type "QA Bonafide" | 1. Sign in as Admin.<br>2. Open Students > Certificate Types.<br>3. Click "Add Certificate Type".<br>4. Enter Name "QA Bonafide" and Description "QA enrollment proof".<br>5. Click "Save". | Dialog "Create Certificate Type"; toast "Certificate type created successfully"; the row "QA Bonafide" with its description appears with an S.No. | passing |
| TC-CER-01-E02 | P3 | Web | Admin | QA Admin login | 1. Open Students > Certificate Types.<br>2. Click "Add Certificate Type".<br>3. Leave Name empty and click "Save". | Toast "Certificate type name is required"; the dialog stays open (verified 2026-10-07) | planned |
| TC-CER-01-E03 | P2 | Web | Admin | TC-CER-01-E01 done | 1. Click "Add Certificate Type".<br>2. Enter Name "QA Bonafide".<br>3. Click "Save". | Error toast "Certificate type name 'QA Bonafide' already exists"; no second row | planned |
| TC-CER-01-E04 | P2 | Web | Admin | TC-CER-01-E01 and TC-CER-04-E01 done (QA Bonafide used by a certificate) | 1. Click "Edit Certificate Type" on "QA Bonafide".<br>2. Change Description to "QA edited" and click "Save".<br>3. Click "Delete Certificate Type" on "QA Bonafide" and click "Delete". | Step 2: toast "Certificate type updated successfully" and the new description; step 3: dialog "Delete Certificate Type" with 'Are you sure you want to delete the certificate type "QA Bonafide"?', then an error toast with "Cannot delete certificate type 'QA Bonafide' because it is being used by 1 student certificate(s)..."; the row stays | planned |
| TC-CER-01-E05 | P3 | Web | Admin | TC-CER-01-E01 done | 1. Type "bona" in "Search name or description...".<br>2. Click the "Name" header twice.<br>3. Type "zzz". | Step 1: only "QA Bonafide" and the seeded "Bonafide Certificate"; step 2: sort arrows toggle ascending then descending; step 3: "No certificate types match your search." | planned |
| TC-CER-01-E06 | P2 | Web | Staff | QA Staff login; seeded types Bonafide Certificate, Transfer Certificate, Conduct Certificate, Study Certificate | 1. Sign in as Staff.<br>2. Open Students > Certificate Types. | List visible; no "Add Certificate Type", Edit or Delete controls (verified 2026-10-07) | planned |
| TC-CER-01-E07 | P2 | Mobile | Admin | QA Admin login | 1. Sign in as Admin on mobile.<br>2. Open Students > Certificate Types and tap "Add Certificate Type".<br>3. Tap "Add Type" with "Type Name *" empty.<br>4. Enter "QA Mobile Type" and tap "Add Type".<br>5. Tap "Edit", change the name to "QA Mobile Type 2" and save.<br>6. Tap "Delete" and confirm. | Step 3: toast "Please enter a certificate type name"; step 4: "Success - Certificate type created successfully!" and the card appears; step 5: "Certificate type updated successfully!"; step 6: confirm "Delete Certificate Type", toast "Certificate type deleted successfully!" and the card disappears | planned |
| TC-CER-01-E08 | P3 | Mobile | Teacher | QA Teacher login | 1. Sign in as Teacher on mobile.<br>2. Open Students > Certificate Types. | The list is read-only: no "Add Certificate Type", Edit or Delete | blocked: Known gap 19 (mobile shows the add, edit and delete controls to every role) |

Implemented in: backend/tests/unit/certificates/test_certificate_types_and_templates.py.

---

## F02 Issuable certificate templates

**Purpose.** Maintain the HTML templates ("Bonafide", "Conduct", "Transfer Certificate") that the generator fills with student data.

**Roles and permissions.** Read: `issuable_certificates:read` (Admin only by default). Create, update and delete require the role name `Admin` (no permission row is checked). Menu: Students > Certificate Templates. The web page has no client-side guard.

**Preconditions.** Tables exist (baseline migration). New tenants get no templates (use "Load Default Templates").

**Steps, web.**
1. Students > Certificate Templates (page content "Certificate Templates").
2. "Load Default Templates" creates six templates one by one: Bonafide Certificate (Class I-X, blue), Permanent Bonafide Certificate (After Class X, green), Conduct Certificate (Class I-X, green), Conduct Certificate - Permanent (After Class X, green), Transfer Certificate (Before Class X, orange), Transfer Certificate - Permanent (After Class X, red). Toast "Default templates added successfully".
3. "Create Template": "Create New Template" form with "Template Name *" ("e.g., Bonafide Certificate"), "Color Theme" (Blue, Green, Red, Orange), "Certificate Content *" in the editor (toolbar Bold, Italic, Underline, alignment, lists, "Normal"/"Heading 1-3", "Insert Variable"), buttons "Create Template" / "Cancel". Inline errors "Template name is required" and "HTML template is required". Toast `Template "<name>" created successfully`.
4. Template cards show name, theme badge, "Created: <date>", "Variables: <n> fields" and "Status:" with a badge (Active or Inactive). Buttons: "Preview" (dialog "<name> - Preview"), "Edit" ("Edit Template", button "Update Template", toast `Template "<name>" updated successfully`), trash icon (dialog "Delete Template?" "Are you sure you want to delete <name>? This cannot be undone." > "Delete", toast "Template deleted successfully").
5. Empty state "No templates created yet" with "Create Your First Template". The same empty state, with "Load Default Templates" and "Create Template", is shown to Staff, Teacher, Student and Parent, whose list call returns 403 (no error is shown).
6. Editor variable menu (placeholders): school_logo, school_name, student_name, admission_number, dob, gender, aadhar_number, apaar_number, class_name, section, academic_year, father_name, mother_name, guardian_details, guardian_name, guardian_phone, guardian_relation, date_of_joining, date_of_leaving, date_of_joining_class, date_of_leaving_class, issue_date, gender_he_she, gender_his_her.

**Steps, mobile.** Students > Certificate Templates (`certificatetemplates.tsx`): list "Templates" with "Create"; cards with "Preview" (plain text), "Edit", delete; form "Create Template" / "Edit Template" with "Template Name *", "Color Theme", "Certificate Content *" and "Insert variable:". Validation toasts "Template name is required." and "Certificate content is required."; success "Created - Template "<name>" created successfully."; delete confirm "Delete Template?". Empty state "No templates created yet" with "Create Your First Template". The screen is gated on resources `certificate_types` and `student_certificates`, not `issuable_certificates`, so a Teacher opens it and sees the empty state (403).

**Expected results.** Templates are stored with `variables_used` (comma separated placeholder names) and `is_active = "True"`. Only active templates are listed.

**API endpoints.**
- `GET /issuable-certificates/templates/` active templates (list of `{id, name, html_template, color_theme, variables_used, is_active, created_at, updated_at}`), unordered.
- `GET /issuable-certificates/templates/{template_id}/` (returns inactive templates as well).
- `POST /issuable-certificates/templates/` body `{name (1..255), html_template (min 1), color_theme (default "blue")}` returns 201.
- `PUT /issuable-certificates/templates/{template_id}/` body `{name?, html_template?, color_theme?, is_active?}`.
- `DELETE /issuable-certificates/templates/{template_id}/` returns 204 (soft delete: `is_active = "False"`).

**Rules and validations.**
- `variables_used` is filled by the regex `\{\{(\w+)\}\}`: names of letters, digits and underscore only, duplicates removed, in no guaranteed order. `{{ name }}` (with spaces) and `{{first-name}}` are not recognised. On update it is recomputed only when `html_template` is sent.
- `color_theme` is not validated by the API (the web restricts to blue, green, red, orange).
- Non-Admin write attempts get 403 "Only Admin can create certificate templates" / "update" / "delete". The role name is matched exactly: a role named `admin` (lowercase) is refused.
- Unknown id 404 "Template not found". Deleting an already inactive template still returns 204.
- `is_active` is a string column: create writes `"True"`; queries compare `lower(is_active) == "true"`. The web status badge and generator filter compare `=== "True"`.

**Error and edge cases.** Staff and Teacher get 403 on the read endpoints (no `issuable_certificates` grant) so the Certificate Templates page shows an error for them. The default template seed scripts target per-tenant schemas and are obsolete.

**Unit-testable logic.** `extract_variables`; soft delete; active filter; web `DEFAULT_TEMPLATES` (6 entries, themes); web template form schema (zod: name min 1, html min 1, theme enum).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-02-U01 | `extract_variables` on "{{student_name}} {{dob}} {{student_name}}" | Set {"student_name","dob"} (compare as a set; duplicates removed) | passing |
| TC-CER-02-U02 | `extract_variables` on "{{ name }}", "{{first-name}}", "{name}", "" | No names found in any case | passing |
| TC-CER-02-U03 | `variables_used` join for ["a","b"] and for [] | "a,b" (any order) and None | passing |
| TC-CER-02-U04 | Active filter on rows with is_active "True", "true", "False" | First two included, last excluded | passing |
| TC-CER-02-U05 | Web `DEFAULT_TEMPLATES` | 6 entries with the names and themes listed above; each html_template non-empty | passing |
| TC-CER-02-U06 | Web zod schema with name "", html "", theme "purple" | Three errors (name, html, theme) | blocked: templateSchema is a local const in web TemplateManager.tsx, not exported |
| TC-CER-02-A01 | Admin creates a template with two placeholders | 201; `variables_used` lists both; `is_active` "True"; `color_theme` "blue" when omitted | passing |
| TC-CER-02-A02 | Create with empty name, empty html, name of 256 characters | 422 each | passing |
| TC-CER-02-A03 | Create with `color_theme` "purple" | 201 (not validated; documented) | passing |
| TC-CER-02-A04 | `GET /templates/` after creating two templates and soft deleting one | 200 with the active one only | passing |
| TC-CER-02-A05 | `GET /templates/{id}/` for an active, a soft deleted and an unknown template | 200; 200 (inactive returned); 404 "Template not found" | passing |
| TC-CER-02-A06 | PUT with new html | `variables_used` recomputed; name and theme unchanged | passing |
| TC-CER-02-A07 | PUT with only `name`; with `color_theme` "red" | `variables_used` unchanged; theme updated | passing |
| TC-CER-02-A08 | PUT `is_active` false, then `GET /templates/` | Template no longer listed (verify stored string casing) | known defect: CER-BUG-1: PUT /issuable-certificates/templates/{id}/ with is_active true/false returns 500 (boolean bound to ... |
| TC-CER-02-A09 | PUT unknown id; DELETE unknown id | 404 "Template not found" | passing |
| TC-CER-02-A10 | DELETE an active template; delete it again | 204; 204; still readable by id with `is_active` "False" | passing |
| TC-CER-02-A11 | Write permission matrix (POST, PUT, DELETE) | Admin 2xx; Staff, Teacher, Student, Parent 403 with the "Only Admin can ..." message | passing |
| TC-CER-02-A12 | Read permission matrix (GET list, GET one) | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-CER-02-A13 | A user with a role named "admin" (lowercase) | 403 on write endpoints (exact role name) | skipped: blocked: needs a custom role named admin and a user in it; |
| TC-CER-02-A14 | No token on all five endpoints | 401 | passing |
| TC-CER-02-A15 | Tenant isolation: templates from tenant A absent in tenant B; token A with header B | Empty list; 403 | passing |
| TC-CER-02-A16 | `GET /issuable-certificates/templates` without the trailing slash | 307 redirect to the slash form (FastAPI default); the slash form returns 200 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-02-E01 | P1 | Web | Admin | qa_manual with its four seeded templates (Bonafide Certificate, Conduct Certificate, Study Certificate, Transfer Certificate); the six defaults not loaded yet (loading defaults is tenant-wide, so it can be done once per tenant) | 1. Sign in as Admin.<br>2. Open Students > Certificate Templates.<br>3. Click "Load Default Templates". | Toast "Default templates added successfully"; six cards are added next to the four seeded ones (Bonafide Certificate (Class I-X); Permanent Bonafide Certificate (After Class X); Conduct Certificate (Class I-X); Conduct Certificate - Permanent (After Class X); Transfer Certificate (Before Class X); Transfer Certificate - Permanent (After Class X)), each "Status: Active" | passing |
| TC-CER-02-E02 | P1 | Web | Admin | QA Admin login | 1. Open Students > Certificate Templates.<br>2. Click "Create Template".<br>3. Enter Template Name "QA Custom Bonafide", Color Theme "Green".<br>4. Type "This is to certify that " in the content, then use "Insert Variable" to add student_name and class_name.<br>5. Click "Create Template". | Toast 'Template "QA Custom Bonafide" created successfully'; the card shows theme green and "Variables: 2 fields" | passing |
| TC-CER-02-E03 | P2 | Web | Admin | TC-CER-02-E02 done | 1. Click "Preview" on "QA Custom Bonafide".<br>2. Close the dialog. | Dialog "QA Custom Bonafide - Preview" with the rendered HTML (placeholders shown as written) | planned |
| TC-CER-02-E04 | P2 | Web | Admin | TC-CER-02-E02 done | 1. Click "Edit" on "QA Custom Bonafide".<br>2. Change the name to "QA Custom Bonafide 2".<br>3. Click "Update Template". | Form "Edit Template"; toast 'Template "QA Custom Bonafide 2" updated successfully'; the card shows the new name and "Status: Active" (check the badge: an "true"/"True" casing change shows "Inactive") | planned |
| TC-CER-02-E05 | P2 | Web | Admin | TC-CER-02-E04 done | 1. Click the trash icon on "QA Custom Bonafide 2".<br>2. Click "Delete". | Dialog "Delete Template?" with "Are you sure you want to delete QA Custom Bonafide 2? This cannot be undone."; toast "Template deleted successfully"; the card disappears | planned |
| TC-CER-02-E06 | P3 | Web | Admin | QA Admin login | 1. Click "Create Template".<br>2. Leave Template Name and content empty.<br>3. Click "Create Template". | Inline "Template name is required" and "HTML template is required"; nothing is created | planned |
| TC-CER-02-E07 | P3 | Web | Staff | QA Staff login; seeded templates exist | 1. Sign in as Staff.<br>2. Open Students > Certificate Templates. | An access or error message; no create controls (the list call returns 403) | blocked: Known gap 19 (shows "No templates created yet" with "Load Default Templates" and "Create Template") |
| TC-CER-02-E08 | P2 | Mobile | Admin | QA Admin login | 1. Sign in as Admin on mobile.<br>2. Open Students > Certificate Templates and tap "Create".<br>3. Enter "Template Name *" "QA Mobile Template", leave "Certificate Content *" empty and save.<br>4. Enter content "QA text {{student_name}}" and save.<br>5. Tap "Preview", then "Edit", change the name and save. | Step 3: toast "Certificate content is required."; step 4: 'Created - Template "QA Mobile Template" created successfully.' and the card shows "1 variables"; step 5: plain-text preview, then the list shows the new name | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_types_and_templates.py; web/src/__tests__/certificates/defaultTemplates.test.ts (U05). U04 asserts the compiled query contains lower(is_active) = true.

---

## F03 Select a student for certificate work (admin selector)

**Purpose.** Pick the student for whom certificates are uploaded, issued or generated, by class, section and student, or by search.

**Roles and permissions.** `GET /certificates/selector/*` are Admin only by role name plus `student_certificates:list`. Menu: Students > Student Certificates.

**Preconditions.** Classes, sections and admitted students.

**Steps, web.**
1. Students > Student Certificates (Admin sees the page "Student Certificates").
2. Card "Filters": search box "Search by name, admission no..." (client side over the students dropdown; the result list shows name and admission number, "No students found" when nothing matches); select "Class" ("Select class"); after a class, "Section" (default "All sections") and "Student" (placeholder "Select student", options "<name> (<admission no>)", "No students found" when empty). "Clear" resets everything.
3. The selection is kept in session storage (`cert_page_selection`) so a refresh restores it. After a student is chosen the line "Selected: <name> - <admission no>" is shown, followed by the upload card (F04) and the certificate table (F07). Staff opening this page get 403 from `selector/classes`, so "Class" stays empty.

**Steps, mobile.** `studentcertificates.tsx` (menu Student Certificates, Admin view): "Filters" with "Clear", search box "Search by name, admission no...", "Class" ("Select class"), "Section" ("All sections"), "Student"; "Select a student above to view their certificates" before a choice. `certificates.tsx`: "Select Student" with "Class *", "Section", "Student *" dropdowns.

**Expected results.** The chosen student drives the upload cards and the certificate table.

**API endpoints.**
- `GET /certificates/selector/classes` returns `[{id, name}]` for active classes ordered by name.
- `GET /certificates/selector/sections?class_id=` returns `[{id, name}]` ordered by name (`class_id` required).
- `GET /certificates/selector/students?class_id=&section_id=` returns `[{student_id, full_name, admission_no}]` for admissions whose **current** class (and optional section) match, ordered by first and last name; includes inactive students.

**Rules and validations.** Role must be exactly `Admin` (403 "Only Admin can access the student selector"). `class_id` must be a UUID (422).

**Error and edge cases.** A class with no students returns `[]`. Staff holding every certificate permission still gets 403. The web search uses the students dropdown endpoint (`students:list`).

**Unit-testable logic.** Web search filter (name or admission number, case-insensitive); restoring the selection from session storage; `section "__all__"` maps to no section.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-03-U01 | Web search filter on "ash" over [Asha Rao (001), Ravi (002)] and on "002" | Asha Rao; Ravi | blocked: search filter, section handler and session restore are inline in the web selector components |
| TC-CER-03-U02 | Section handler with "__all__" and with an id | Empty section id; the id | blocked: search filter, section handler and session restore are inline in the web selector components |
| TC-CER-03-U03 | Session storage restore with invalid JSON | Falls back to an empty selection without throwing | blocked: search filter, section handler and session restore are inline in the web selector components |
| TC-CER-03-A01 | Admin `GET selector/classes` | 200 active classes ordered by name | passing |
| TC-CER-03-A02 | `selector/sections?class_id=<Class 1>`; without `class_id`; with a malformed id | Sections of the class; 422; 422 | passing |
| TC-CER-03-A03 | `selector/students` with class only and with class and section | All students of the class; only that section | passing |
| TC-CER-03-A04 | Class without students | 200 `[]` | passing |
| TC-CER-03-A05 | A deactivated student in the class | Included in the result | passing |
| TC-CER-03-A06 | Permission matrix on all three endpoints | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-CER-03-A07 | No token | 401 | passing |
| TC-CER-03-A08 | Tenant isolation: tenant B Admin sees only tenant B classes and students; token A with header B | Separate data; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-03-E01 | P1 | Web | Admin | Seeded student Harsha Raju (004, Class 1 / 1-B) | 1. Sign in as Admin.<br>2. Open Students > Student Certificates.<br>3. Select Class "Class 1", Section "1-B".<br>4. Select Student "Harsha Raju (004)". | "Selected: Harsha Raju - 004" appears; the card "Upload for Harsha Raju" with "Received Document" and "Issue Certificate" and the table "Certificates - Harsha Raju (<n> total)" are shown (verified with sample data 2026-10-07) | passing |
| TC-CER-03-E02 | P2 | Web | Admin | Seeded student Harsha Raju (004, Class 1 / 1-B) | 1. Open Students > Student Certificates.<br>2. Type "Harsha" in "Search by name, admission no...".<br>3. Click the result "Harsha Raju". | Harsha Raju is selected ("Selected: ..." line); the Class and Section selects are cleared | planned |
| TC-CER-03-E03 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Press F5 to reload the page. | The same class, section and student stay selected (session storage) | planned |
| TC-CER-03-E04 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Click "Clear". | Search, class, section and student reset; the upload card and the table are hidden | planned |
| TC-CER-03-E05 | P3 | Web | Admin | A class "QA Empty Class" with no students, created in Masters > Classes (every seeded class has students) | 1. Select Class "QA Empty Class". | The "Student" select shows "No students found" and nothing can be chosen | planned |
| TC-CER-03-E06 | P2 | Mobile | Admin | Seeded student Harsha Raju (004, Class 1 / 1-B) | 1. Sign in as Admin on mobile.<br>2. Open Students > Student Certificates.<br>3. Choose Class "Class 1", Section "1-B", Student "Harsha Raju". | The tabs "Received Document" and "Issue Certificate" and the student's certificate list appear | planned |
| TC-CER-03-E07 | P3 | Web | Staff | QA Staff login | 1. Sign in as Staff.<br>2. Open Students > Student Certificates. | A clear message that the page is for Admin (or a read-only view) | blocked: Known gap 10 and 19 (admin page with an empty "Class" select, 403 on selector/classes, no message) |

---

## F04 Upload a received document

**Purpose.** Store a document the school collected from the family (previous TC, birth certificate) against a student.

**Roles and permissions.** `POST /certificates/received`: role `Admin` by name and `student_certificates:create`. The web upload card is shown only when the user holds `issuable_certificates:create`. Parents and students never upload.

**Preconditions.** A student (F03) and a certificate type (F01).

**Steps, web.**
1. Students > Student Certificates, select a student (F03).
2. Card "Upload for <name>", tab "Received Document".
3. Fill "Certificate Type *" ("Select type"), "Document File *" (PDF/JPG/PNG/DOCX, max 10 MB), optional "Remarks" (placeholder "Optional remarks (max 255 characters)", input capped at 255).
4. Click "Upload Document" ("Uploading...") or "Reset". Missing data: toast "Student, certificate type, and file are required". Success toast "Document uploaded successfully!"; failure "Failed to upload document: <detail>".

**Steps, mobile.** Admin view of Student Certificates (`studentcertificates.tsx`): tab "Received Document": "Certificate Type *" ("Select type"), "Document File *", "Remarks" ("Optional remarks (max 255 characters)"), upload button and "Reset". Toasts "Error - Student, certificate type, and file are required" and "Uploaded - Document uploaded successfully". The older `certificates.tsx` uses "Required - Please select student, certificate type and a file" and "Uploaded - Received document uploaded successfully".

**Expected results.** 201 `CertificateRead`: `certificate_category` "received", `issue_date` null, `file_path` `<tenant id>/received_docs/<student id>/<uuid>.<ext>`, `type_name` from the type. A `file_audit_log` row (action `upload`) is written. The row appears in the table and in the student's merged documents list.

**API endpoints.** `POST /certificates/received` multipart `student_id`, `certificate_type_id`, `remarks?`, `file`.

**Rules and validations.**
- Order of checks: role, permission, student exists (404 "Student with id <id> not found"), type exists (404 "Certificate type with id <id> not found"), then the file.
- File: extension in `.pdf .jpg .jpeg .png .docx` (400 "File extension '<ext>' not allowed. Allowed: ..."); filename without `..`, `/`, `\` (400 "Filename contains invalid characters"); not empty (400 "File is empty"); at most 10 MB, 10,485,760 bytes accepted (413 "File size exceeds maximum allowed (10 MB)"); `.pdf` must start with `%PDF` (400 "PDF file is corrupted or not a valid PDF"). A MIME type that differs from the extension is only logged. The original filename is discarded.
- `remarks`: at most 255 characters (the column size); longer text is 422 "Remarks must be at most 255 characters" before any file is stored. The clients cap the field at 255.
- The file is written to disk before the database insert; a database failure leaves the file behind.

**Error and edge cases.** A Staff user with every `student_certificates` permission still gets 403 "Only Admin can upload received documents". Missing `file` 422.

**Unit-testable logic.** `FileManager.upload_file` validations (extension, filename safety, size boundary, empty, PDF magic, file key format), `MIME_TO_EXT` mapping, role gate.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-04-U01 | `upload_file` extension check: .pdf, .JPG, .jpeg, .png, .docx, .exe, .doc, no extension | First five accepted; others 400 | passing |
| TC-CER-04-U02 | Filename safety for "a..b.pdf", "x/y.pdf", "x\\y.pdf", "ok.pdf" | First three rejected; last accepted | passing |
| TC-CER-04-U03 | Size boundary: 10,485,760 and 10,485,761 bytes; 0 bytes | Accepted; 413; 400 "File is empty" | passing |
| TC-CER-04-U04 | PDF magic: "%PDF-1.7..." vs "not a pdf" named .pdf | Accepted; 400 | passing |
| TC-CER-04-U05 | MIME mismatch: content type image/png with a .pdf name | Accepted (warning logged only) | passing |
| TC-CER-04-U06 | File key format | `<tenant id>/received_docs/<student id>/<uuid>.<ext>` with a lowercase extension | passing |
| TC-CER-04-A01 | Admin uploads a PDF with remarks | 201; category "received", `issue_date` null, `type_name` set, `file_path` matches the key format; file exists under `media/` | passing |
| TC-CER-04-A02 | Upload PNG and DOCX | 201 each | passing |
| TC-CER-04-A03 | Upload .exe; a text file named .pdf; an 11 MB file; an empty file; a file named "a/b.pdf" | 400 "not allowed"; 400 "corrupted"; 413; 400 "File is empty"; 400 invalid characters | skipped: size boundaries need 10 MB and 11 MB files; |
| TC-CER-04-A04 | Upload exactly 10 MB | 201 | skipped: size boundaries need 10 MB and 11 MB files; |
| TC-CER-04-A05 | Unknown student id; unknown type id | 404 "Student with id ... not found"; 404 "Certificate type with id ... not found" | passing |
| TC-CER-04-A06 | Missing `student_id`, `certificate_type_id` or `file` | 422 each | passing |
| TC-CER-04-A07 | Remarks of 255 and 256 characters | 201; 422 | passing |
| TC-CER-04-A08 | Audit: after a successful upload | `file_audit_log` row with action "upload", the actor id and role "Admin", `student_id`, `certificate_id`, the file key | skipped: blocked: no endpoint exposes file_audit_log and the suite may not read the database directly |
| TC-CER-04-A09 | Permission matrix | Admin 201; Staff 403 "Only Admin can upload received documents"; Teacher 403; Student 403; Parent 403 | passing |
| TC-CER-04-A10 | No token | 401 | passing |
| TC-CER-04-A11 | Tenant isolation: tenant B Admin uploads for a tenant A student; token A with header B | 404 student; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-04-E01 | P1 | Web | Admin | TC-CER-01-E01 and TC-CER-03-E01 done; a small PDF | 1. In "Upload for Harsha Raju" keep the tab "Received Document".<br>2. Choose "Certificate Type *" "QA Bonafide".<br>3. Choose the PDF in "Document File *".<br>4. Enter Remarks "QA received copy".<br>5. Click "Upload Document". | Toast "Document uploaded successfully!"; the table gains a row "QA Bonafide", Issue Date "-", Remarks "QA received copy", badge "Uploaded"; the count "(n total)" goes up by one | passing |
| TC-CER-04-E02 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Keep "Received Document".<br>2. Click "Upload Document" without type or file. | Toast "Student, certificate type, and file are required" (verified 2026-10-07) | planned |
| TC-CER-04-E03 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Choose a type, a file and Remarks "QA reset".<br>2. Click "Reset". | Type, file and remarks are cleared | planned |
| TC-CER-04-E04 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Paste a 300 character text into "Remarks". | The field stops at 255 characters (placeholder "Optional remarks (max 255 characters)") | planned |
| TC-CER-04-E05 | P2 | Web | Staff | QA Staff login | 1. Sign in as Staff.<br>2. Open Students > Student Certificates. | No upload card (Staff lacks issuable_certificates:create); the selector and table calls answer 403 | planned |
| TC-CER-04-E06 | P2 | Mobile | Admin | TC-CER-01-E01 done; a small PDF on the device | 1. Sign in as Admin on mobile.<br>2. Open Students > Student Certificates and choose Class 1 / 1-B / Harsha Raju.<br>3. In "Received Document" choose "QA Bonafide", pick the PDF.<br>4. Tap the upload button. | Toast "Uploaded - Document uploaded successfully"; the list refreshes with the new item | planned |
| TC-CER-04-E07 | P3 | Web | Admin | TC-CER-03-E01 done; an 11 MB PDF | 1. Choose "QA Bonafide" and the 11 MB file.<br>2. Click "Upload Document". | Error toast "Failed to upload document: File size exceeds maximum allowed (10 MB)"; no row is added | planned |

Implemented in: backend/tests/unit/certificates/test_file_manager.py.

---

## F05 Issue a certificate file

**Purpose.** Record a certificate that the school issues to a student by uploading the signed file.

**Roles and permissions.** `POST /certificates/issued`: role `Admin` by name and `student_certificates:create`. The legacy `POST /certificates/` needs only `student_certificates:create` (Admin, Staff).

**Preconditions.** A student and a certificate type.

**Steps, web.**
1. Students > Student Certificates, select a student, tab "Issue Certificate", sub-tab "Upload Certificate File".
2. Fill "Certificate Type *", "Issue Date *" ("Pick a date"), "Certificate File *" (PDF/JPG/PNG/DOCX, max 10 MB), optional "Remarks".
3. Click "Issue Certificate" ("Issuing...") or "Reset". Missing data: toast "Certificate type, issue date, and file are required". Success toast "Certificate issued successfully!".

**Steps, mobile.** Admin view, tab "Issue Certificate", sub-tab "Upload File": "Certificate Type *", "Issue Date *" ("YYYY-MM-DD"), "Certificate File *", "Remarks", "Issue Certificate" ("Issuing...") and "Reset"; toasts "Issued - Certificate issued successfully" and "Error - Certificate type, issue date, and file are required". The older screen `certificateupload.tsx` ("Upload Certificate": "Tap to select certificate file", "Certificate Name *", "Certificate Type *", "Select Student *", "Issue Date", "Description") calls the legacy `POST /certificates/` with the field `file` (fixed 2026-10-02); success toast "Certificate Uploaded - Certificate uploaded successfully!", missing data "Please fill in all required fields" or "Please select a certificate file". Teacher and Staff get "Access Denied" on that screen.

**Expected results.** 201 `CertificateRead` with `certificate_category` "issued", `issue_date` as sent, `file_path` `<tenant id>/issued_certs/<student id>/<uuid>.<ext>`. Audit row "upload".

**API endpoints.**
- `POST /certificates/issued` multipart `student_id`, `certificate_type_id`, `issue_date` (required), `remarks?`, `file`.
- `POST /certificates/` (legacy) multipart `student_id`, `certificate_type_id`, `issue_date?` (defaults to today), `remarks?`, `file`; creates a row with category **received** and stores it under `certificates/<student id>/`.

**Rules and validations.** Same student, type and file validations as F04. `issue_date` is a required date (422 when missing or invalid; any date, including future, is accepted). The category of the legacy endpoint is always "received" even though it carries an issue date. The signature fields (`issued_by_name`, `issuer_signature_path`) exist but no endpoint writes them.

**Error and edge cases.** Staff gets 403 "Only Admin can issue certificates" on `/issued` but can use the legacy endpoint. Web hook `useCreateCertificate` and mobile `certificateupload.tsx` now send the file as `file` (Known gaps 7); a call with `certificate_file` is still 422.

**Unit-testable logic.** Issue date parsing; category assignment per endpoint; file key module folder (`issued_certs` vs `certificates`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-05-U01 | Category and module folder per endpoint: `/issued`, `/received`, legacy `/` | issued/issued_certs; received/received_docs; received/certificates | passing |
| TC-CER-05-U02 | `issue_date` values "2026-10-02", "02-10-2026", "" | Parsed; 422; 422 | passing |
| TC-CER-05-A01 | Admin issues a certificate with a PDF and `issue_date` 2026-10-02 | 201; category "issued"; `issue_date` "2026-10-02"; key under `issued_certs` | passing |
| TC-CER-05-A02 | Issue without `issue_date`; with an invalid date; with a future date | 422; 422; 201 | passing |
| TC-CER-05-A03 | Same file validation matrix as F04 (extension, size 10 MB boundary, PDF magic, empty, filename) | Same results as TC-CER-04 | passing |
| TC-CER-05-A04 | Unknown student; unknown type | 404 each with the F04 messages | passing |
| TC-CER-05-A05 | Legacy `POST /` with field `file` as Admin and as Staff | 201 category "received" with `issue_date` = today when omitted; Staff also 201 | passing |
| TC-CER-05-A06 | Legacy `POST /` with the file under `certificate_file` (as the web hook and the mobile screen send it) | 422 (file missing) | passing |
| TC-CER-05-A07 | Permission matrix for `/issued` | Admin 201; Staff 403 "Only Admin can issue certificates"; Teacher, Student, Parent 403 | passing |
| TC-CER-05-A08 | Permission matrix for legacy `POST /` | Admin 201; Staff 201; Teacher 403; Student 403; Parent 403 | passing |
| TC-CER-05-A09 | Audit row for an issued certificate | Action "upload", actor role "Admin" | skipped: blocked: no endpoint exposes file_audit_log and the suite may not read the database directly |
| TC-CER-05-A10 | No token on both endpoints | 401 | passing |
| TC-CER-05-A11 | Tenant isolation as in F04 | 404 student; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-05-E01 | P1 | Web | Admin | TC-CER-01-E01 and TC-CER-03-E01 done; a small PDF | 1. Click "Issue Certificate" in the upload card (sub-tab "Upload Certificate File").<br>2. Choose "QA Bonafide", Issue Date today and the PDF.<br>3. Click "Issue Certificate". | Toast "Certificate issued successfully!"; a row with today's Issue Date and badge "Uploaded" appears | passing |
| TC-CER-05-E02 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Open "Issue Certificate".<br>2. Choose a type and a file, leave "Issue Date *" empty.<br>3. Click "Issue Certificate". | Toast "Certificate type, issue date, and file are required" | planned |
| TC-CER-05-E03 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Open "Issue Certificate", fill type, date, file and remarks.<br>2. Click "Reset". | All fields are cleared | planned |
| TC-CER-05-E04 | P1 | Mobile | Admin | TC-CER-01-E01 done; a small PDF on the device | 1. Open Students > Student Certificates on mobile and choose Harsha Raju.<br>2. Tap "Issue Certificate", keep "Upload File".<br>3. Choose "QA Bonafide", Issue Date (YYYY-MM-DD) today, the PDF.<br>4. Tap "Issue Certificate". | Toast "Issued - Certificate issued successfully"; the list refreshes with the new item | known defect: UI-CER-01: mobile Issue Certificate with an attached file fails with the error toast "Value error, Expected Up... |
| TC-CER-05-E05 | P3 | Mobile | Admin | TC-CER-01-E01 done; Seeded student Harsha Raju (004, Class 1 / 1-B); a small PDF | 1. Sign in as Admin on mobile.<br>2. Open /students/certificateupload ("Upload Certificate").<br>3. Pick the PDF, enter Certificate Name "QA Legacy", choose "QA Bonafide" and student Harsha Raju.<br>4. Tap "Upload Certificate". | Toast "Certificate Uploaded - Certificate uploaded successfully!" (the screen now sends the field file); the certificate appears for Harsha Raju as a received item | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_service.py (U02 uses a pydantic date adapter equal to the FastAPI Form date parsing).

---

## F06 Generate a certificate from a template

**Purpose.** Produce a certificate for a student from a template, with the student's data filled in, optionally edited, then saved and printed.

**Roles and permissions.** `POST /issuable-certificates/generate/`: role `Admin` by name (no permission row). Reading templates and generated certificates needs `issuable_certificates:read`; deleting a generated certificate needs `issuable_certificates:delete`. The web generator is inside the Admin upload card.

**Preconditions.** At least one active template (F02) and a selected student (F03).

**Steps, web.**
1. Students > Student Certificates, select a student, tab "Issue Certificate", sub-tab "Generate Issuable".
2. Card "Select Certificate Template": choose from the list (placeholder "Select certificate type (Bonafide, TC, Conduct, etc.)"); "Manage Templates" opens `/students/certificatetemplates`.
3. Fill "School Name" ("Enter school name") and "School Logo URL" ("https://yourschool.com/logo.png"); the hint reads "The school name and logo URL appear in all certificates and are saved for next time." (kept in the browser's local storage under `cert_school_name` and `cert_logo_url`, with a logo preview).
4. Card "Certificate Preview": the template is shown with placeholders filled by the browser. "Edit Content" switches to an editor (with "Reset to Original"); "View Preview" returns.
5. "Save & Print" saves through the API then opens the print dialog; "Print Only" prints without saving. Toasts "Please select a template and student" and "Certificate saved successfully".

**Steps, mobile.** Admin view, tab "Issue Certificate" > "Generate Issuable": template dropdown "Select a template" with "Manage Templates" ("No certificate templates found. Tap "Manage Templates" above to create one." when none), optional remarks ("Optional remarks (max 255 characters)"), "Generate Certificate" ("Generating...") and "Reset". Toast "Generated - Certificate generated successfully!" (failure "Failed to generate certificate: <detail>"; "Could not load student details for the template" when the admission cannot be read). Generated items show in the student's list with the badge "Generated" and the text "Generated from template".

**Expected results.** A `generated_certificates` row with the HTML exactly as sent, `issued_by` = the Admin's user id, `is_active` "True". The server does not fill placeholders and does not create a PDF. Placeholders are replaced by the web client: school_logo, school_name, student_name ("first last"), admission_number, dob (en-IN date), gender (M/F -> Male/Female), aadhar_number, apaar_number, class_name and section (from the current class and section), academic_year (header academic year title, else the current year), father_name, mother_name, guardian_name, guardian_phone, guardian_relation, guardian_details ("name | (relation) | Ph: phone"), date_of_joining (admission date), issue_date (today, en-IN), gender_he_she (He or She), gender_his_her (His or Her); `date_of_leaving`, `date_of_joining_class` and `date_of_leaving_class` are replaced by empty text. The mobile client fills the student, parent and date placeholders from the admission (`src/utils/certificateTemplate.ts`, fixed 2026-10-02); `school_name`, `school_logo`, class, section and the leaving dates stay unfilled.

**API endpoints.**
- `POST /issuable-certificates/generate/` body `{student_id, template_id, edited_html (min 1), remarks? (max 500)}` returns 201 `{id, student_id, template_id, html_content, issued_date, issued_by, remarks, is_active, created_at, updated_at}`.
- `GET /issuable-certificates/issued/?student_id=` returns the student's active generated certificates (unpaginated).
- `GET /issuable-certificates/issued/{certificate_id}/`.
- `DELETE /issuable-certificates/issued/{certificate_id}/` soft deletes (204).

**Rules and validations.** Unknown `template_id` 404 "Template not found"; an inactive template is 400 "Template is inactive"; an unknown `student_id` (not in the tenant's `students`) is 404 "Student not found". Empty `edited_html` is 422. Remarks over 500 characters 422. Unknown generated id 404 "Certificate not found". Generated certificates do not appear in `GET /certificates/*`, the student's documents list, the student view or the parent view. Generate follows flush, select, commit.

**Error and edge cases.** A non-Admin gets 403 "Only Admin can generate certificates". `GET /issued/` without `student_id` is 422. The web "Save & Print" prints even if the user cancels the dialog; saving happens first.

**Unit-testable logic.** Web placeholder replacement (`filledHtml`): all occurrences replaced, unknown placeholders left, gender normalisation (m, male, f, female), guardian details formatting, empty leaving dates, class and section resolution; `generate_certificate` stores the HTML untouched.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-06-U01 | Placeholder fill: "{{student_name}} and {{student_name}}" for "Asha Rao" | Both replaced: "Asha Rao and Asha Rao" | blocked: filledHtml is a useMemo inside web IssuableCertificateGenerator.tsx, not exported |
| TC-CER-06-U02 | Unknown "{{foo}}" in the template | Left unchanged | blocked: filledHtml is a useMemo inside web IssuableCertificateGenerator.tsx, not exported |
| TC-CER-06-U03 | Gender normalisation for "m", "Male", "f", "female", "O", None | "Male", "Male", "Female", "Female", "O", "" ; pronouns He/His for non female, She/Her for Female | blocked: filledHtml is a useMemo inside web IssuableCertificateGenerator.tsx, not exported |
| TC-CER-06-U04 | `guardian_details` for name "Raj", relation "Uncle", phone "9876543210"; and for no guardian | `"Raj | (Uncle) | Ph: 9876543210"`; "" | blocked: filledHtml is a useMemo inside web IssuableCertificateGenerator.tsx, not exported |
| TC-CER-06-U05 | `date_of_leaving`, `date_of_joining_class`, `date_of_leaving_class` | Replaced by "" | blocked: filledHtml is a useMemo inside web IssuableCertificateGenerator.tsx, not exported |
| TC-CER-06-U06 | `academic_year` with title "2026-27" and without a title | "2026-27"; current year string | blocked: filledHtml is a useMemo inside web IssuableCertificateGenerator.tsx, not exported |
| TC-CER-06-U07 | `generate_certificate` with a fake session | Stored `html_content` equals `edited_html` byte for byte; `is_active` "True"; `issued_by` = caller; inactive template 400; unknown student 404 | passing |
| TC-CER-06-A01 | Admin generates with a valid template and student | 201; `html_content` unchanged; `issued_by` = Admin id; `is_active` "True" | passing |
| TC-CER-06-A02 | Generate with empty `edited_html`; remarks of 500 and 501 characters | 422; 201; 422 | passing |
| TC-CER-06-A03 | Unknown `template_id`; malformed ids | 404 "Template not found"; 422 | passing |
| TC-CER-06-A04 | Random `student_id` that does not exist | 404 "Student not found" | passing |
| TC-CER-06-A05 | Generate with an inactive template | 400 "Template is inactive" | passing |
| TC-CER-06-A06 | `GET /issued/?student_id=` after two generations and one delete | One active certificate returned | passing |
| TC-CER-06-A07 | `GET /issued/` without `student_id`; `GET /issued/{id}/` known and unknown | 422; 200; 404 "Certificate not found" | passing |
| TC-CER-06-A08 | `DELETE /issued/{id}/` then `GET /issued/{id}/` | 204; GET still 200 with `is_active` "False"; list no longer includes it | passing |
| TC-CER-06-A09 | Generated certificate is not in `GET /certificates/by-student/{id}`, `GET /certificates/my` or `GET /students/documents/all` | Absent in all | passing |
| TC-CER-06-A10 | Permission matrix: generate | Admin 201; Staff, Teacher, Student, Parent 403 "Only Admin can generate certificates" | passing |
| TC-CER-06-A11 | Permission matrix: GET issued list and by id | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-CER-06-A12 | Permission matrix: DELETE issued | Admin 204; Staff, Teacher, Student, Parent 403 | passing |
| TC-CER-06-A13 | No token on all four endpoints | 401 | passing |
| TC-CER-06-A14 | Tenant isolation: tenant B Admin generates with a tenant A template id; token A with header B | 404 "Template not found"; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-06-E01 | P1 | Web | Admin | Seeded template "Bonafide Certificate"; TC-CER-03-E01 done | 1. Click "Issue Certificate", then "Generate Issuable".<br>2. Choose "Bonafide Certificate" in "Select certificate type (Bonafide, TC, Conduct, etc.)". | "Certificate Preview" shows "Harsha Raju", Admission No. 004, Class "Class 1" and section "1-B", the academic year and today's date; the school name comes from "School Name" | passing |
| TC-CER-06-E02 | P3 | Web | Admin | TC-CER-06-E01 state | 1. Enter School Name "QA School" and School Logo URL "https://example.com/qa-logo.png".<br>2. Reload the page and reopen "Generate Issuable". | Both values are kept (local storage) and the preview uses "QA School" | planned |
| TC-CER-06-E03 | P2 | Web | Admin | TC-CER-06-E01 state | 1. Click "Edit Content".<br>2. Add the text "QA edited line".<br>3. Click "Save & Print". | Toast "Certificate saved successfully"; the print dialog opens; the stored certificate contains "QA edited line" | planned |
| TC-CER-06-E04 | P3 | Web | Admin | TC-CER-06-E01 state | 1. Click "Edit Content" and change the text.<br>2. Click "Reset to Original".<br>3. Click "View Preview". | The content returns to the filled template | planned |
| TC-CER-06-E05 | P3 | Web | Admin | TC-CER-03-E01 done | 1. Open "Generate Issuable" without choosing a template.<br>2. Choose a template and click "Print Only". | Step 1: no preview and no print buttons; step 2: the print dialog opens and nothing is saved | planned |
| TC-CER-06-E06 | P3 | Web | Admin | A tenant with no active template: qa_manual seeds four, so use a tenant provisioned with setup_manual_tenant.py --no-seed plus one admitted "QA " student; never delete the seeded templates | 1. Open "Generate Issuable" for that student. | The card shows "No certificate templates available" | planned |
| TC-CER-06-E07 | P2 | Mobile | Admin | Seeded templates; seeded student Harsha Raju (004) | 1. Open Students > Student Certificates on mobile and choose Harsha Raju.<br>2. Tap "Issue Certificate", then "Generate Issuable".<br>3. Choose a template in "Select a template".<br>4. Tap "Generate Certificate". | Toast "Generated - Certificate generated successfully!"; an item with badge "Generated" and "Generated from template" appears; the stored HTML has the student and parent values filled, while school name, class and section stay as placeholders | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_types_and_templates.py (U07).

---

## F07 View a student's certificates (admin lists and metadata)

**Purpose.** Admins see every certificate of a selected student (and system-wide lists) and read a certificate's metadata.

**Roles and permissions.** `GET /certificates/received`, `/issued`, `/by-student/{id}`: role `Admin` by name plus `student_certificates:list`. `GET /certificates/`: `student_certificates:list` (Admin, Staff, Teacher). `GET /certificates/{id}`: `student_certificates:read` (Student: `read_own`) - Admin, Staff, Teacher, Student; Parent has no plain `read` (403).

**Preconditions.** Certificates exist.

**Steps, web.** Students > Student Certificates, select a student (F03). Card "Certificates - <name> (<n> total)" ("Loading certificates..." while loading): columns "S.No.", "Certificate Type", "Issue Date", "Remarks", "File" (badge "Uploaded" or "No file"), "Actions" (download icon "Download"). Empty: "No certificates found.". The table loads `GET /certificates/by-student/{id}`. There is no delete or edit control and no category column or tab.

**Steps, mobile.** Admin view lists the selected student's certificates as cards with a serial number, a source badge (Issued, Received, Generated), type name, date, remarks, "Download" (or "No File") and "Revoke" (F09); empty "No certificates found for this student" (`studentcertificates.tsx`) or "No certificates for this student" (`certificates.tsx`). Because list items carry no category, every uploaded item is labelled "Issued".

**Expected results.** Newest first (`created_at` descending), `items`, `total`, `has_next`. List items omit `certificate_category` (only create responses carry it).

**API endpoints.**
- `GET /certificates/?student_id=&certificate_type_id=&skip=0&limit=50`.
- `GET /certificates/received` and `GET /certificates/issued` with the same query parameters.
- `GET /certificates/by-student/{student_id}?skip&limit`.
- `GET /certificates/{certificate_id}` returns `CertificateRead` (without `certificate_category`).

**Rules and validations.**
- `received` and `issued` do **not** filter by category: both return the same mix of received and issued rows.
- `skip` and `limit` have no bounds validation: `skip=-1` makes the database reject the offset (500 "Error listing certificates: ..."); `limit=0` returns no items; `has_next = skip + limit < total`.
- `certificate_type_id` filters by type. Unknown student in `by-student` returns an empty list (no 404).
- `GET /certificates/{id}`: unknown id 404 "Certificate with id <id> not found". A Student (`read_own`) can read only their own certificates and a Parent (`read_related`) only a linked child's; other ids give 403 (fixed 2026-10-02).

**Error and edge cases.** Staff gets 403 on `received`, `issued`, `by-student` (role name check) but can use `GET /certificates/?student_id=`. Teacher also uses the plain list (F13).

**Unit-testable logic.** `list_certificates` filtering, ordering, `has_next`, item mapping (`type_name` empty string when the type is missing).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-07-U01 | `has_next` for (skip 0, limit 50, total 50), (0, 50, 51), (50, 50, 100) | false, true, false | passing |
| TC-CER-07-U02 | Item mapping for a certificate whose type was removed | `type_name` "" and `certificate_type_id` null | passing |
| TC-CER-07-U03 | Order of three rows with different `created_at` | Newest first | passing |
| TC-CER-07-A01 | Admin `GET /certificates/by-student/{id}` with 2 received and 1 issued | 200; 3 items; `total` 3; `has_next` false; no `certificate_category` in items | passing |
| TC-CER-07-A02 | `GET /certificates/received` and `/issued` | Both return the same 3 rows (no category filter; documented gap) | passing |
| TC-CER-07-A03 | `GET /certificates/` with `student_id` and with `certificate_type_id` | Filtered rows | passing |
| TC-CER-07-A04 | Pagination: 60 rows, `limit=50` then `skip=50` | 50 items `has_next` true; 10 items `has_next` false | passing |
| TC-CER-07-A05 | `skip=-1`; `limit=0` | 500 "Error listing certificates"; 200 with `items: []` | passing |
| TC-CER-07-A06 | `by-student` for an unknown student id | 200 empty list | passing |
| TC-CER-07-A07 | `GET /certificates/{id}` known; unknown; malformed | 200 with fields; 404 "Certificate with id <id> not found"; 422 | passing |
| TC-CER-07-A08 | Student reads another student's certificate by id | 403 (fixed 2026-10-02) | passing |
| TC-CER-07-A09 | Permission matrix: `received`, `issued`, `by-student` | Admin 200; Staff 403; Teacher 403; Student 403; Parent 403 | passing |
| TC-CER-07-A10 | Permission matrix: `GET /certificates/` | Admin, Staff, Teacher 200; Student 403; Parent 403 | passing |
| TC-CER-07-A11 | Permission matrix: `GET /certificates/{id}` | Admin, Staff, Teacher, Student 200; Parent 403 | passing |
| TC-CER-07-A12 | No token on every endpoint | 401 | passing |
| TC-CER-07-A13 | Tenant isolation: tenant B Admin lists; token A with header B | Tenant A rows absent; 403 | passing |
| TC-CER-07-A14 | Route order: `GET /certificates/my`, `/received`, `/selector/classes` | Not parsed as a certificate id | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-07-E01 | P1 | Web | Admin | TC-CER-04-E01 and TC-CER-05-E01 done | 1. Sign in as Admin.<br>2. Open Students > Student Certificates and select Harsha Raju. | Table "Certificates - Harsha Raju (2 total)" with both rows, newest first, badge "Uploaded", dates formatted, a "Download" icon per row | passing |
| TC-CER-07-E02 | P3 | Web | Admin | Seeded student Tanvi Raju (005), no uploaded certificates | 1. Select Tanvi Raju on Student Certificates. | "(0 total)" and "No certificates found." | planned |
| TC-CER-07-E03 | P3 | Web | Admin | A certificate row whose file_path is null | 1. Select that student on Student Certificates. | The File column shows "No file" and no download icon | blocked: no UI or API path creates a certificate without a file (every upload requires one) |
| TC-CER-07-E04 | P2 | Mobile | Admin | TC-CER-04-E01 done | 1. Sign in as Admin on mobile.<br>2. Open Students > Student Certificates and choose Harsha Raju.<br>3. Choose Tanvi Raju.<br>4. Choose Kavya Verma (006, Class 1 / 1-A). | Step 2: cards with a serial number, source badge, type, date and "Download"; step 3: "No certificates found for this student"; step 4: the seeded generated "Study Certificate" with the badge "Generated" and "Generated from template" | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_service.py.

---

## F08 Update or replace a certificate file

**Purpose.** Correct a certificate's type, date or remarks, or replace its file.

**Roles and permissions.** `PATCH /certificates/{id}`: `student_certificates:update` (Admin, Staff). Not limited to the role name Admin.

**Preconditions.** An existing certificate.

**Steps, web and mobile.** No screen calls this endpoint (the web hook `useUpdateCertificate` exists but is unused and sends the file under the wrong field name). Use the API.

**Expected results.** Only sent fields change. A new file is stored under `<tenant id>/certificates/<student id>/<uuid>.<ext>`; the old file moves to `media/stale/<old key>` and a `stale_file_registry` row is created with `expires_at` = now + 10 days. An audit row "update" is written. Response is `CertificateRead` (no category).

**API endpoints.** `PATCH /certificates/{certificate_id}` multipart `certificate_type_id?`, `issue_date?`, `remarks?`, `file?`.

**Rules and validations.** File validation as in F04 (applied only when a file is sent). Unknown certificate 404 "Certificate with id <id> not found". `certificate_type_id` is not checked for existence: an unknown id fails on the foreign key with 500 "Error updating certificate: ...". The replacement file goes to the generic `certificates` folder even for received or issued rows.

**Error and edge cases.** A failing upload leaves the old file untouched. Fields sent as empty strings: `remarks` "" is stored as empty.

**Unit-testable logic.** Field application order, stale registry expiry (`timedelta(days=10)`), `move_to_stale` key (`stale/<old key>`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-08-U01 | `move_to_stale("t/received_docs/s/x.pdf", t)` | Returns "stale/t/received_docs/s/x.pdf"; file moved when present, no error when absent | passing |
| TC-CER-08-U02 | Stale registry expiry | `expires_at` - now is 10 days (within a second) | passing |
| TC-CER-08-U03 | Update with only remarks | Type, date and file unchanged | passing |
| TC-CER-08-A01 | Admin PATCHes remarks and issue date | 200; changed fields updated; `updated_at` newer | passing |
| TC-CER-08-A02 | PATCH with a new file | 200; new `file_path`; old file under `media/stale/...`; registry row with `expires_at` about 10 days ahead; audit row "update" | skipped: blocked: the stale registry row and the audit row are not exposed by any endpoint |
| TC-CER-08-A03 | PATCH with an invalid file (.exe, 11 MB, fake PDF) | 400 / 413 / 400; the row and old file unchanged | passing |
| TC-CER-08-A04 | PATCH with an unknown `certificate_type_id` | 404 "Certificate type with id <id> not found"; no file is stored | passing |
| TC-CER-08-A05 | PATCH unknown certificate id | 404 "Certificate with id <id> not found" | passing |
| TC-CER-08-A06 | PATCH with no fields | 200 unchanged | passing |
| TC-CER-08-A07 | Permission matrix | Admin 200; Staff 200; Teacher 403; Student 403; Parent 403 | passing |
| TC-CER-08-A08 | No token | 401 | passing |
| TC-CER-08-A09 | Tenant isolation: tenant B Admin patches a tenant A certificate; token A with header B | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-08-E01 | P3 | Web | Admin | TC-CER-04-E01 done | 1. On web, select Harsha Raju on Student Certificates and look for an edit or replace control.<br>2. On mobile, open the same student and look at the card actions. | No edit or replace control exists on either app (PATCH /certificates/{id} has no UI) | planned |

Implemented in: backend/tests/unit/certificates/test_file_manager.py (U01) and test_certificate_service.py (U02, U03).

---

## F09 Delete or revoke a certificate

**Purpose.** Remove a wrongly uploaded certificate (or revoke one) while keeping its file for 10 days.

**Roles and permissions.** `DELETE /certificates/{id}`: `student_certificates:delete` (Admin only). `DELETE /issuable-certificates/issued/{id}/`: `issuable_certificates:delete` (Admin). Mobile shows "Revoke" only with the delete permission.

**Preconditions.** An existing certificate.

**Steps, web.** No delete control in the certificate table (the page has an unused delete dialog state). Hooks `useDeleteCertificate` and `useDeleteIssuableCertificate` exist without UI.

**Steps, mobile.** Admin view (`studentcertificates.tsx`), card button "Revoke" (red; "Revoking..."; shown only with `student_certificates:delete`): modal "Revoke Certificate" "Revoke this certificate? This cannot be undone." > "Revoke". Toast "Revoked - Certificate revoked successfully" or "Error - Failed to revoke certificate". Generated items call `DELETE /issuable-certificates/issued/{id}/`; uploaded and issued items call `DELETE /certificates/{id}`.

**Expected results.** The database row is hard-deleted; the file moves to `media/stale/<key>`; a `stale_file_registry` row (`expires_at` = now + 10 days) and an audit row "delete" are written. The daily job (F14) removes the file after expiry.

**API endpoints.** `DELETE /certificates/{certificate_id}` returns 204. `DELETE /issuable-certificates/issued/{id}/` (F06).

**Rules and validations.** Unknown id 404 "Certificate with id <id> not found". A row with no file skips the stale step. The registry and audit rows are written in the same transaction as the delete.

**Error and edge cases.** The file move happens before the commit; a commit failure leaves the file in stale. After deletion the certificate disappears from the student's and parent's views and from the merged documents list.

**Unit-testable logic.** Delete flow with a fake session and file manager (order: move, registry, audit, delete).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-09-U01 | Delete flow with a certificate with a file | Calls move_to_stale, adds a registry row (10 days), adds an audit row "delete" with the old key, deletes the row | passing |
| TC-CER-09-U02 | Delete flow with `file_path` None | No stale step; audit and delete still happen | passing |
| TC-CER-09-A01 | Admin deletes a certificate | 204; `GET /certificates/{id}` 404; file now under `media/stale/<key>`; registry row exists; audit row "delete" | skipped: blocked: the stale registry rows and the file audit log are not exposed by any endpoint |
| TC-CER-09-A02 | Delete the same id twice | 204 then 404 "Certificate with id <id> not found" | passing |
| TC-CER-09-A03 | Delete a certificate whose file is already missing on disk | 204 (no error) | passing |
| TC-CER-09-A04 | After deletion, student `my`, parent `my-child` and `students/documents/all` | Certificate absent everywhere | passing |
| TC-CER-09-A05 | Deleting a type that was used only by the deleted certificate | Type deletion now succeeds | passing |
| TC-CER-09-A06 | Permission matrix | Admin 204; Staff 403; Teacher 403; Student 403; Parent 403 | passing |
| TC-CER-09-A07 | No token | 401 | passing |
| TC-CER-09-A08 | Tenant isolation: tenant B Admin deletes a tenant A certificate; token A with header B | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-09-E01 | P3 | Web | Admin | TC-CER-04-E01 done | 1. Select Harsha Raju on Student Certificates.<br>2. Look at the Actions column. | Only the download icon; no delete control | planned |
| TC-CER-09-E02 | P2 | Mobile | Admin | TC-CER-04-E01 done | 1. Open Students > Student Certificates on mobile and choose Harsha Raju.<br>2. Tap "Revoke" on the received item.<br>3. Tap "Revoke" in the modal. | Modal "Revoke Certificate" with "Revoke this certificate? This cannot be undone."; toast "Revoked - Certificate revoked successfully"; the card disappears | planned |
| TC-CER-09-E03 | P2 | Mobile | Admin | TC-CER-06-E07 done (never revoke the seeded generated certificates) | 1. Tap "Revoke" on the "Generated" item and confirm. | Toast "Revoked - Certificate revoked successfully" (issuable delete endpoint); the item disappears | planned |
| TC-CER-09-E04 | P3 | Mobile | Teacher | QA Teacher login | 1. Sign in as Teacher on mobile.<br>2. Open Students > Student Certificates. | No "Revoke" control anywhere (Teacher has no delete permission; the admin lists also answer 403) | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_service.py.

---

## F10 Download a certificate

**Purpose.** Open or save a certificate file.

**Roles and permissions.** `GET /certificates/{id}/download`: `student_certificates:read` (a Student uses `read_own`): Admin, Staff, Teacher; Student for own files; Parent uses `read_related` and may download a linked child's certificates (fixed 2026-10-02: the parent entity is resolved from the user id).

**Preconditions.** A certificate with a file.

**Steps, web.** Click the download icon in the certificate table (Admin "Download", Student/Parent/Teacher "Download Certificate"). The browser opens the file in a new tab at `<API origin><presigned_url>`. Failure toast "Failed to get download link: <message>".

**Steps, mobile.** "Download" on a card: opens `Linking.openURL(presigned_url)`; because the URL is relative (`/media/...`) it does not open (Known gaps). Toasts "No Download Link - No download link available", "Could not get download link" (`studentcertificates.tsx`), "Failed to download certificate" (`mycertificates.tsx`).

**Expected results.** 200 `{presigned_url: "/media/<tenant id>/<module>/<student id>/<uuid>.<ext>", expires_in_seconds: 900, certificate_id}` (`filename` null). The URL never expires and the file is publicly readable. An audit row "download" is written.

**API endpoints.** `GET /certificates/{certificate_id}/download`.

**Rules and validations.**
- Unknown id 404 "Certificate with id <id> not found".
- Admin, Staff, Teacher: any certificate. Student: only if `students.user_id` equals the caller (else 403 "You do not have permission to download this certificate"). Parent: allowed when a `StudentParentLink` joins the parent entity (resolved from the user id) to the certificate's student, else 403; any other role 403 "You do not have permission to download certificates".
- A certificate with no `file_path` returns `/media/None`.
- Clients must prefix the API origin (the web pages do; mobile does not).

**Error and edge cases.** The `media/` mount serves files without authentication, so the file link works for anyone who has it, even after the certificate row is deleted until the file is removed.

**Unit-testable logic.** `download_certificate` role matrix with fake sessions; web URL builder (`startsWith("http")` else prefix origin); `generate_presigned_url` returns `/media/<key>`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-10-U01 | `generate_presigned_url("t/issued_certs/s/x.pdf")` | "/media/t/issued_certs/s/x.pdf" | passing |
| TC-CER-10-U02 | RBAC with fake data: Admin, Staff, Teacher, Student owner, Student other, Parent linked, unknown role | Allowed x4; 403; 403 (parent id compared with user id); 403 | passing |
| TC-CER-10-U03 | Web URL builder for "/media/a.pdf", "https://cdn/x.pdf" | `<origin>/media/a.pdf`; unchanged | blocked: URL builder is inline in the web certificate pages |
| TC-CER-10-A01 | Admin downloads an issued certificate | 200 with `presigned_url` "/media/...", `expires_in_seconds` 900, `certificate_id`; audit row "download" | skipped: blocked: the audit row written by a download is not exposed by any endpoint |
| TC-CER-10-A02 | `GET <origin><presigned_url>` without a token | 200 with the file bytes (public media; documents the exposure) | known defect: TEN-MEDIA-CSCHEMA: /media/<tenant>/... |
| TC-CER-10-A03 | Staff and Teacher download any certificate | 200 each | passing |
| TC-CER-10-A04 | Student downloads own; another student's | 200; 403 "You do not have permission to download this certificate" | passing |
| TC-CER-10-A05 | Parent downloads a linked child's certificate | 200 (fixed 2026-10-02) | passing |
| TC-CER-10-A06 | Unknown id; malformed id | 404 "Certificate with id <id> not found"; 422 | passing |
| TC-CER-10-A07 | Permission matrix on the endpoint | Admin 200; Staff 200; Teacher 200; Student 200 own only; Parent 403 | passing |
| TC-CER-10-A08 | No token | 401 | passing |
| TC-CER-10-A09 | Tenant isolation: tenant B Admin downloads a tenant A certificate; token A with header B | 404; 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-10-E01 | P2 | Web | Admin | TC-CER-05-E01 done | 1. Select Harsha Raju on Student Certificates.<br>2. Click "Download" on the issued row. | A new tab opens the PDF at <API origin>/media/... | blocked: Known gap 16 and docs/modules/certificates.md rule 3 (a plain /media link without a tenant header or token gets 400 in strict tenant mode) |
| TC-CER-10-E02 | P2 | Web | Student | Seeded student login 004; TC-CER-05-E01 done | 1. Sign in with the seeded student login 004.<br>2. Open Students > Student Certificates.<br>3. Click "Download Certificate" on a row. | A new tab opens the file (origin prefixed) | blocked: docs/modules/certificates.md rule 3 (plain /media link gets 400 in strict tenant mode) |
| TC-CER-10-E03 | P2 | Web | Parent | Seeded parent login venkat.raju@example.com with Harsha Raju selected; TC-CER-05-E01 done | 1. Sign in as venkat.raju@example.com.<br>2. Open Students > Student Certificates.<br>3. Click "Download Certificate". | The download link is returned and opens the file | blocked: docs/modules/certificates.md rule 3 (plain /media link gets 400 in strict tenant mode) |
| TC-CER-10-E04 | P3 | Mobile | Student | Seeded student login 004; TC-CER-05-E01 done | 1. Sign in with the seeded student login 004 on mobile.<br>2. Open Students > Student Certificates.<br>3. Tap the download button. | The file opens | blocked: Known gap 2 (mobile opens the relative /media URL) |

Implemented in: backend/tests/unit/certificates/test_file_manager.py (U01) and test_certificate_service.py (U02; the linked Parent case is covered with a found link row, and the KG-5 comparison of parent id to user id is asserted from the query parameters).

---

## F11 Student: my certificates

**Purpose.** A student sees their own certificates and downloads them.

**Roles and permissions.** `GET /certificates/my`: `student_certificates:list_own` (Student only; Admin, Staff, Teacher, Parent get 403). The student is resolved from the token (`students.user_id`). Menu: Students > Student Certificates (route `/students/studentcertificates`, also `/students/mycertificates`).

**Preconditions.** The student has certificates.

**Steps, web.** Log in as a Student, Students > Student Certificates opens "My Certificates" ("Loading your certificates..." while loading): card "Certificates (<n> total)" with columns "S.No.", "Certificate Type", "Issue Date", "Remarks", "File", "Download". Empty: "No certificates found." and "Certificates issued to you will appear here.". Download icon "Download Certificate".

**Steps, mobile.** Students > Student Certificates (`studentcertificates.tsx`, read-only list for the Student role) or `/students/mycertificates` (`mycertificates.tsx`, title "My Certificates"): cards with type, date, remarks, badge "Uploaded" or "No file" and a download button. Without a student record: "Failed to load certificates" / "Please select a student to view certificates".

**Expected results.** Only the caller's rows, newest first, received and issued together (no category separation), without generated (issuable) certificates.

**API endpoints.** `GET /certificates/my?skip&limit` returns `{items, total, has_next}`; a user with no student record gets `{items: [], total: 0, has_next: false}`.

**Rules and validations.** No category filter. `skip` and `limit` unvalidated as in F07.

**Error and edge cases.** Student role without a `students` row returns an empty page. Admin gets 403 (no `list_own`).

**Unit-testable logic.** Student resolution from user id; empty result when no student.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-11-U01 | Student resolution when no student has the user id | Returns `{items: [], total: 0, has_next: false}` | passing |
| TC-CER-11-A01 | Student with 2 certificates (one received, one issued) `GET /my` | 200; both rows; `total` 2; only the caller's | passing |
| TC-CER-11-A02 | Two students each with certificates | Each only sees their own | passing |
| TC-CER-11-A03 | Pagination `limit=1&skip=0` and `skip=1` | One item each; `has_next` true then false | passing |
| TC-CER-11-A04 | Student without a student record | 200 empty page | passing |
| TC-CER-11-A05 | Permission matrix | Student 200; Admin, Staff, Teacher, Parent 403 | passing |
| TC-CER-11-A06 | No token | 401 | passing |
| TC-CER-11-A07 | Tenant isolation: token A with header B | 403 | passing |
| TC-CER-11-A08 | A generated (issuable) certificate for the student | Not returned by `/my` | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-11-E01 | P1 | Web | Student | A student created through the API for the test (QA name, own QA class) that has completed first login, with two certificates (TC-CER-04-E01 and TC-CER-05-E01 done); grant Student `student_certificates:read_own` and `list_own` first (the test grants and restores them) | 1. Sign in as the QA student.<br>2. Open Students > Student Certificates. | Page "My Certificates", card "Certificates (2 total)" with only the QA student's rows; columns S.No., Certificate Type, Issue Date, Remarks, File, Download | passing |
| TC-CER-11-E02 | P3 | Web | Student | Seeded student login 005 (Tanvi Raju, no uploaded certificates) | 1. Sign in with the seeded student login 005.<br>2. Open Students > Student Certificates. | "Certificates (0 total)", "No certificates found." and "Certificates issued to you will appear here." (verified 2026-10-07) | planned |
| TC-CER-11-E03 | P2 | Web | Student | Seeded student login 004; TC-CER-05-E01 done | 1. Open Students > Student Certificates.<br>2. Click "Download Certificate". | The file opens in a new tab | blocked: docs/modules/certificates.md rule 3 (plain /media link gets 400 in strict tenant mode) |
| TC-CER-11-E04 | P2 | Mobile | Student | Seeded student login 004; TC-CER-04-E01 done | 1. Sign in with the seeded student login 004 on mobile.<br>2. Open /students/mycertificates. | "My Certificates" with cards (type, date, remarks), badge "Uploaded" and a download button | planned |
| TC-CER-11-E05 | P3 | Web | Student | Seeded student login 005 | 1. Sign in with the seeded student login 005.<br>2. Expand "Students" in the sidebar. | No "Certificate Types" or "Certificate Templates" entries | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_endpoint_guards.py.

---

## F12 Parent: child certificates

**Purpose.** A parent sees the certificates of their linked children.

**Roles and permissions.** `GET /certificates/my-child/{student_id}`, `/received`, `/issued`: `check_user_resource_access(student_certificates, list)` (Parent `list_related`; Admin, Staff, Teacher `list`). A Parent must also be linked to the student (explicit check, 403). The child comes from the header child selector (`docs/features/students.md` F19). Parents never upload.

**Preconditions.** A linked child with certificates.

**Steps, web.** Log in as a Parent, Students > Student Certificates opens "Certificates" for the selected child: title "Certificates - <first> <last> (<class> - <section>)" with "(<n> total)"; same columns as F11 with a download icon; empty "No certificates found."; "No children linked to your account." when none.

**Steps, mobile.** Students > Student Certificates (`studentcertificates.tsx`, parent list for the selected child) or `/students/mycertificates` (title "Child Certificates"): requires a selected child ("Select a student from the header"). Parents also have `parents/documents.tsx` ("Documents") listing the child's certificates ("No child selected." with "Select a child" when none).

**Expected results.** Rows of the selected child only.

**API endpoints.**
- `GET /certificates/my-child/{student_id}` (all kinds).
- `GET /certificates/my-child/{student_id}/received`.
- `GET /certificates/my-child/{student_id}/issued` (also lets a Student read their own; another student's id is 403 "You can only view your own certificates").

**Rules and validations.** Parent not linked: 403 "You are not the parent of this student"; parent without a `parents` row: 403 "Parent profile not found". The three routes return the same unfiltered mix. A Student calling `my-child/{id}` or `my-child/{id}/received` for another student gets 403 (fixed 2026-10-02).

**Error and edge cases.** Admin, Staff and Teacher can use these routes for any student (no link check for them).

**Unit-testable logic.** Parent link check with fake rows; student ownership check for `/issued`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-12-U01 | Link check for (parent, linked student) and (parent, unlinked student) | Allowed; 403 "You are not the parent of this student" | passing |
| TC-CER-12-U02 | `/issued` ownership for Student owner and other | Allowed; 403 | passing |
| TC-CER-12-A01 | Parent `GET my-child/{linked child}` | 200 child's certificates | passing |
| TC-CER-12-A02 | Parent `GET my-child/{unlinked child}` | 403 "You are not the parent of this student" | passing |
| TC-CER-12-A03 | Parent calls `/received` and `/issued` for a linked child | 200; both return the same mix | passing |
| TC-CER-12-A04 | Parent without a parent row | 403 "Parent profile not found" | passing |
| TC-CER-12-A05 | Two parents, each linked to a different child | Each sees only their own child's rows | passing |
| TC-CER-12-A06 | Student `/issued` for own id and another id | 200; 403 "You can only view your own certificates" | passing |
| TC-CER-12-A07 | Student calls the base route for another student's id | 403 (fixed 2026-10-02) | passing |
| TC-CER-12-A08 | Admin, Staff, Teacher call `my-child/{any id}` | 200 | passing |
| TC-CER-12-A09 | Parent tries `POST /certificates/received`, `/issued`, `PATCH`, `DELETE` | 403 each | passing |
| TC-CER-12-A10 | No token | 401 | passing |
| TC-CER-12-A11 | Tenant isolation: token A with header B; a parent of tenant B querying a tenant A child id | 403; 403 "not the parent" | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-12-E01 | P1 | Web | Parent | A parent created through the API for the test (QA name, one QA child in an own QA class) that has completed first login, with the child selected; TC-CER-04-E01 done; grant Parent `student_certificates:read_related` and `list_related` first (the test grants and restores them) | 1. Sign in as the QA parent.<br>2. Open Students > Student Certificates. | Page "Certificates" with the title "Certificates - <child name> (<QA class> - <QA section>)" and "(n total)"; only that child's rows | passing |
| TC-CER-12-E02 | P2 | Web | Parent | TC-CER-12-E01 state; Tanvi Raju has no certificates | 1. Switch the header child selector to Tanvi Raju. | The table reloads and shows "No certificates found." | planned |
| TC-CER-12-E03 | P3 | Web | Parent | QA Parent login (unlinked) | 1. Sign in with the QA Parent login (unlinked).<br>2. Open Students > Student Certificates. | "No children linked to your account." (verified 2026-10-07) | planned |
| TC-CER-12-E04 | P3 | Web | Parent | TC-CER-12-E01 state | 1. Look for upload, edit or delete controls. | None; only "Download Certificate" icons | planned |
| TC-CER-12-E05 | P3 | Mobile | Parent | Seeded parent login venkat.raju@example.com with no child selected | 1. Sign in as venkat.raju@example.com on mobile without choosing a child.<br>2. Open Students > Student Certificates. | "Select a student from the header" | planned |
| TC-CER-12-E06 | P2 | Mobile | Parent | Seeded parent login venkat.raju@example.com; Harsha Raju selected; TC-CER-04-E01 done | 1. Open /students/mycertificates on mobile. | Title "Child Certificates" with Harsha Raju's certificates | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_endpoint_guards.py.

---

## F13 Teacher: read-only student certificates

**Purpose.** Teachers look up any student's certificates and download them.

**Roles and permissions.** `student_certificates:list`/`read` (Teacher holds both): `GET /certificates/?student_id=`, `GET /certificates/{id}`, download, `my-child/*`, `types/search`. Teachers cannot upload, issue, update, delete or use the selector. Not limited to their classes (no teacher-class table).

**Preconditions.** Students with certificates.

**Steps, web.** Teacher: Students > Student Certificates opens "Student Certificates" with the card "Select Student" (picker "Select a student", "Clear"), then "Certificates for <name>" with a table "Certificate Type | Issue Date | Remarks | File | Actions" and the download icon "Download Certificate"; empty text "No certificates found for this student." and, before choosing, "Please select a student to view their certificates.".

**Steps, mobile.** The Teacher falls through to the admin view, whose endpoints are Admin-only: `selector/classes` and `issuable-certificates/templates/` answer 403, "Class" stays empty and the screen shows "Select a student above to view their certificates" (Known gaps).

**Expected results.** Web: the chosen student's certificates; mobile: errors.

**API endpoints.** `GET /certificates/?student_id=` (F07), `GET /certificates/{id}`, download (F10), dropdown `GET /students/admission/students/dropdown` (`students:list`).

**Rules and validations.** Same as F07 and F10.

**Error and edge cases.** A Teacher calling `selector/*`, `received`, `issued`, `by-student/*` gets 403.

**Unit-testable logic.** Web role routing in `CertificatePage` (student -> My Certificates, parent -> Parent page, teacher -> read-only page, anything else -> admin page).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-13-U01 | `CertificatePage` routing for roles student, parent, teacher, admin, staff, accountant | My Certificates, Parent page, Teacher page, admin page, admin page, admin page | blocked: role routing is inline in the CertificatePage component (needs rendering) |
| TC-CER-13-A01 | Teacher `GET /certificates/?student_id=` | 200 for any student | passing |
| TC-CER-13-A02 | Teacher `GET /certificates/{id}` and download | 200 each | passing |
| TC-CER-13-A03 | Teacher calls `selector/classes`, `received`, `issued`, `by-student/{id}` | 403 each | passing |
| TC-CER-13-A04 | Teacher calls POST `/received`, `/issued`, `/`, PATCH, DELETE | 403 each | passing |
| TC-CER-13-A05 | Teacher `types/search?q=bon` | 200 | passing |
| TC-CER-13-A06 | No token | 401 | passing |
| TC-CER-13-A07 | Tenant isolation: token A with header B | 403 | passing |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-13-E01 | P1 | Web | Teacher | A student created through the API for the test (QA name, own QA class) with two certificates (TC-CER-04-E01 done) | 1. Sign in as Teacher.<br>2. Open Students > Student Certificates.<br>3. Choose the QA student in "Select a student". | "Certificates for <QA student name>" with columns Certificate Type, Issue Date, Remarks, File, Actions and "Download Certificate" icons; no upload card | passing |
| TC-CER-13-E02 | P3 | Web | Teacher | QA Teacher login | 1. Open Students > Student Certificates. | Card "Select Student" and "Please select a student to view their certificates." (verified 2026-10-07) | planned |
| TC-CER-13-E03 | P2 | Web | Teacher | TC-CER-05-E01 done | 1. Choose Harsha Raju.<br>2. Click "Download Certificate". | The file opens in a new tab | blocked: docs/modules/certificates.md rule 3 (plain /media link gets 400 in strict tenant mode) |
| TC-CER-13-E04 | P3 | Mobile | Teacher | TC-CER-04-E01 done | 1. Sign in as Teacher on mobile.<br>2. Open Students > Student Certificates. | A read-only list of a chosen student's certificates | blocked: Known gap 10 (Teacher gets the admin view; selector/classes is 403 and no student can be chosen) |

---

## F14 File audit log and stale file cleanup

**Purpose.** Keep a record of file actions and delete replaced or removed files after a grace period.

**Roles and permissions.** Background job only; no user interface and no endpoint reads the audit log.

**Preconditions.** Celery worker and beat running (`backend/scripts/start_celery_worker.py`); Redis.

**Steps, web and mobile.** None.

**Expected results.** Every upload, update, delete and download writes a `file_audit_log` row (`actor_id`, `actor_role`, `student_id`, `certificate_id`, `action` of upload, update, delete or download, `s3_key`, `tenant_schema` = tenant id, `created_at`). Replaced and deleted files are moved to `media/stale/<key>` with a `stale_file_registry` row (`expires_at` = now + 10 days). The task `cleanup_stale_files` runs daily at 02:00 UTC (expires after one hour if not picked up) and, for every active tenant, deletes up to 100 expired files per run (rows with `expires_at < now`) and their registry rows; a file that is already gone only logs a warning and the registry row is still removed.

**API endpoints.** None.

**Rules and validations.** Per-tenant sessions are used (one commit per tenant); a failure in one tenant is logged and the others continue. Unexpired entries are untouched.

**Error and edge cases.** More than 100 expired files in a tenant need several runs. The audit table grows without limit.

**Unit-testable logic.** Audit row construction; expiry selection (`expires_at < now`, limit 100); idempotent delete of an already missing file; per-tenant error isolation.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-CER-14-U01 | `_log_audit` for action "upload" with a given actor and key | A `FileAuditLog` with the same values and `tenant_schema` equal to the tenant id is added | passing |
| TC-CER-14-U02 | Cleanup selection with entries expiring yesterday, today (future) and 150 expired entries | Only expired ones, at most 100 per run | passing |
| TC-CER-14-U03 | Cleanup when the file is already missing | Registry row still deleted; no exception | passing |
| TC-CER-14-U04 | Cleanup when deleting one tenant raises | Other tenants are still processed; error logged | passing |
| TC-CER-14-U05 | Beat schedule | Task name "cleanup_stale_files", crontab hour 2 minute 0, expires 3600 seconds | passing |
| TC-CER-14-A01 | After upload, update, download and delete of one certificate | Four audit rows with actions upload, update, download, delete in order | skipped: blocked: the stale registry rows and the file audit log are not exposed by any endpoint |
| TC-CER-14-A02 | Replace a file (PATCH) and set the registry `expires_at` in the past, run the cleanup | Stale file removed from `media/stale/` and registry row deleted | skipped: blocked: audit rows and stale registry rows are not exposed by any endpoint, and the cleanup task needs a Cele... |
| TC-CER-14-A03 | Registry row with a future `expires_at`, run the cleanup | File and row remain | skipped: blocked: audit rows and stale registry rows are not exposed by any endpoint, and the cleanup task needs a Cele... |
| TC-CER-14-A04 | Two tenants each with an expired entry, run the cleanup | Both cleaned, each in its own tenant context | skipped: blocked: audit rows and stale registry rows are not exposed by any endpoint, and the cleanup task needs a Cele... |
| TC-CER-14-A05 | Audit rows of tenant A are not visible from tenant B sessions | Row level security hides them | skipped: blocked: audit rows and stale registry rows are not exposed by any endpoint, and the cleanup task needs a Cele... |

UI test cases:

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-CER-14-E01 | P3 | Web | Admin | TC-CER-04-E01 done | 1. Select Harsha Raju on Student Certificates and confirm the "Uploaded" row.<br>2. Check the file_audit_log row through the API test TC-CER-04-A08. | No screen exists for the audit log or stale cleanup; the row is visible in the table and the audit row exists | planned |

Implemented in: backend/tests/unit/certificates/test_certificate_service.py (U01) and test_stale_cleanup_task.py (U02-U05; U02 asserts the SQL text because the filter runs in the database).

---

## Known gaps

Code behaviour that differs from `docs/modules/certificates.md`, plus defects found while documenting.

1. **Tenant folder.** The module doc says a missing `cschema` falls back to `little_bunny`. The code now takes the folder from `get_tenant_id_from_request` (the tenant id; a missing tenant is 400 "Tenant could not be determined") and files live under `media/<tenant id>/...`. The doc's gotcha 8 is stale.
2. **Download URL on web.** The module doc says the web Student, Parent and Teacher pages use the relative URL. In the code all web pages (`MyCertificatesPage`, `ParentCertificatePage`, `StudentCertificatesPage`, `CertificateUploadPage`) prefix the API origin. Only mobile (`Linking.openURL(presigned_url)`) still opens the relative path.
3. **Default templates.** The web "Load Default Templates" creates six templates, not three (Bonafide, Permanent Bonafide, Conduct, Permanent Conduct, Transfer, Permanent Transfer). The web generator takes "School Name" and "School Logo URL" from inputs stored in local storage; the doc's "hardcoded Your School Name" is stale.
4. **Category filter missing** (still open: no web or mobile screen sends a category, so it was not added) on `received`, `issued` and every `my-child` route, and list and detail items omit `certificate_category` (set only on create responses). The legacy `POST /certificates/` always stores "received" even though it takes an `issue_date`.
5. **Parent cannot read or download.** `GET /certificates/{id}` and download need plain `read`, which Parent lacks (403), and the download ownership code compares `parent_id` with the user id (always 403). Fixed (2026-10-02): both endpoints use `read_related` for Parent and check the linked child.
6. **No ownership check** on `GET /certificates/{id}` (any Student with `read_own` reads any certificate) and on `my-child/{id}` and `/received` for the Student role. Fixed (2026-10-02).
7. **Wrong multipart field.** Fixed (2026-10-02): web hooks and mobile `certificateupload.tsx` now send `file` (mobile sends `remarks`). Previously web `useCreateCertificate`/`useUpdateCertificate` and mobile `certificateupload.tsx` send `certificate_file` (and mobile sends `description`); the API expects `file`, so legacy create fails with 422 and PATCH ignores the file. No screen calls PATCH.
8. **Remarks length.** Fixed (2026-10-02): the service rejects remarks over 255 characters with 422 (the column size), the request schemas use 255 and the web and mobile fields are capped at 255. No migration needed.
9. **Update with an unknown `certificate_type_id`** Fixed (2026-10-02): 404, checked before any file is stored.
10. **Admin-only by role name.** Staff with all certificate permissions gets 403 on upload, issue, category lists, by-student and the selector, yet the web routes Staff to the admin page; the web upload card is gated by `issuable_certificates:create` (not `student_certificates:create`). Mobile sends Teachers to the admin view where every call is 403. Mobile Certificate Types and Templates screens are gated on `certificate_types` and `student_certificates` rather than `issuable_certificates`.
11. **Mobile defects.** "Revoke" on a Generated item called `DELETE /certificates/{id}` with a generated certificate id (404) and "Generate Certificate" sent the raw template (both fixed 2026-10-02: revoke uses the issuable endpoint, and generate fills the student, parent and date placeholders from the admission; school name and logo stay as placeholders for manual edit); relative download URL; all non generated items are labelled "Issued" because list items carry no category.
12. **Issuable subsystem.** `generated_certificates.student_id` has no foreign key but is now validated against the tenant's students and inactive templates are rejected (fixed 2026-10-02); `GET /issued/` is unpaginated; `variables_used` order is not stable; `is_active` is a string and the web badge compares `=== "True"` (an updated template can show as Inactive; update with a boolean should be verified); no PDF, signature or QR; generated certificates are invisible to students and parents.
13. **`commit()` then `refresh()`** in `generate_certificate` and in certificate type create and update: fixed (2026-10-02), now flush, select, commit. Template create/update still use the old pattern.
14. **Unbounded paging.** Certificate lists accept any `skip` and `limit` (a negative `skip` is a 500). Types list is bounded (`skip >= 0`, `limit` 1..100) and loads all rows to count them.
15. **A null `file_path`** downloads as `/media/None` (no guard). Files are written before the database insert and are not removed if the insert fails.
16. **Files are public.** `media/` is served without authentication, so every certificate and stale file is readable by anyone with the URL; `presigned_url` never expires.
17. **Unsafe scripts.** `setup_issuable_certificates.py` and the older seed scripts target per-tenant schemas and use an unquoted schema argument and a placeholder `DATABASE_URL`; new tenants get no templates and no `issuable_certificates` grants beyond Admin.
18. **Malformed `sub` claim** gives 500 rather than 401 on endpoints that call `UUID(current_user["sub"])`.
19. **UI states seen on 2026-10-07.** Web: a 403 on the template list (Staff, Teacher, Student, Parent) shows "No templates created yet" with "Load Default Templates", "Create Template" and "Create Your First Template"; a 403 on the type list (Parent) shows "No certificate types found." with "Create First Certificate Type"; Staff on Student Certificates get the admin page with an empty "Class" select (403 on `selector/classes`) and no message. Mobile: Certificate Types shows "Add Certificate Type", Edit and Delete to every role; Teacher and Staff land on the admin Student Certificates view (403).
20. UI-CER-01: on Expo web the mobile Issue Certificate with an attached file fails with "Value error, Expected UploadFile, received: <class 'str'>" because the picked file is sent as a string; same family as the mobile expense attachment upload. Check on a native device.
