# Masters (MST)

Masters is the tenant reference data that every other module hangs off: academic years, classes and sections, subject categories, subjects, class-subject mappings, parent profiles, location and caste lookups, and the single school-settings row (shown as "School Registration" / "School Settings"). This page documents every feature the way a school admin meets it (set up the year first, then classes, categories, subjects, mappings, then parents, lookups and school identity) and is the specification for the MST test cases. Holidays and the timetable are mounted under the same API prefix but are documented in `docs/features/timetable-calendar.md` (code TTC). Staff, designations and staff attendance are in `docs/features/staff.md` (STF), Roles and Permissions is in `docs/features/tenants-and-admin.md` (TEN), and the transport masters (routes, stops, vehicles, trips) are in `docs/features/transport.md` (TRN). They appear here only as cards on the Masters hub (F15).

_Last verified against code: 2026-10-07_

Module rules, gotchas and code map: `docs/modules/masters.md`. Flows and decisions: `docs/graph/views/masters.md`. Test conventions and IDs: `docs/testing/strategy.md`.

Unit tests (U) implemented in: `backend/tests/unit/masters/test_mst_*.py`, `web/src/__tests__/masters/`, `mobile/__tests__/masters/` (extra ad hoc API tests only). A U row marked blocked needs the named helper exported before it can be tested. Tests whose names end `_defect_kgN` or ` [defect KG-N]` assert today's behaviour of a Known gaps item.

## Roles

Access is decided per resource by the tenant's role grants (`docs/permissions.md`). The grants below are the default seed (`ROLE_PERMISSIONS` in `backend/app/service/tenant/permission_catalog.py`) that the QA tenant `qa_school` is provisioned with. Every MST API test asserts these grants.

| Resource | Admin | Staff | Teacher | Student | Parent |
|---|---|---|---|---|---|
| `academic_years` | create, read, update, delete, list | read, list | read, list | read, list | read, list |
| `classes` | create, read, update, delete, list | read, list | read, list | read, list | read, list |
| `sections` | create only | read, list | read, list | none | none |
| `subject_categories` | create, read, update, delete, list | read, list | read, list | none | none |
| `subjects` | create, read, update, delete, list | read, list | read, list | read, list | read, list |
| `class_subject_mappings` | create, read, update, delete, list | read, list | read, list | none | none |
| `parent_management` | create, read, update, delete, list | create, read, update, list (no delete) | none | none | none |
| `locations` | create, read, update, delete, list | read, list | read, list | none | none |
| `castes` | create, read, update, delete, list | read, list | read, list | none | none |
| `school_settings` | read, update | none | none | none | none |

Menu and screen visibility: Admin, Staff and Teacher receive every Masters menu entry (web sidebar Masters, mobile Home > "Masters" module card); Student and Parent receive only the self-service URL allowlist, so they have no Masters menu on web and no Masters card on the mobile Home screen (their Home shows Students, Exam Management and Fee Management only). Typing a Masters URL still opens the page; screens whose read grant the role holds (academic years, classes, subjects) show data, the others get 403 (web shows an empty table, mobile shows "Failed to load ... data" with "Retry"). On web the Teacher and Staff roles are additionally capped by `teacherPermissionMatrix.ts` and `staffPermissionMatrix.ts` (read and list only on the academic masters).

Seed gaps that affect the UI (see Known gaps): the default Admin grant has `sections:create` but not `sections:read`, `sections:list`, `sections:update` or `sections:delete`, and the web classes page gates the section Edit and Delete buttons on `sections:update` and `sections:delete`.

## Conventions used by the test cases

- API base: `/api/v1`. Phase 2 tests run against `qa_school` on the local test API (`docs/testing/test-environment.md`). The QA baseline holds no master data, so every API test creates its own rows with unique names (prefix `QA-<run id>`) and removes them afterwards.
- UI cases (IDs ending `-E`) run against the seeded manual-test tenant `qa_manual` (`backend/scripts/qa/setup_manual_tenant.py`). Its masters data: one academic year "2026-2027" (2026-06-01 to 2027-03-31, active); classes Nursery, LKG, UKG and Class 1 to Class 5, each with sections such as NUR-A/NUR-B and 1-A/1-B; subject categories Languages, Core Academics, Co-Curricular; ten subjects (English, Hindi, Telugu, Mathematics, Environmental Studies, General Science, Social Studies, Computer Science, Art and Craft, Physical Education) mapped to every section of their classes; 30 students with father and mother parent profiles (for example Venkat Raju and Sirisha Raju, parents of Harsha and Tanvi Raju). It has no castes, no states and no school settings row. Cases that create rows use names starting "QA " and delete them afterwards; do not edit or delete the seeded rows. The QA Admin, Staff and Teacher logins work in `qa_manual`; the QA Student and Parent logins are not linked to a student.
- Role fixtures: Admin, Staff, Teacher, Student, Parent, each with an API-obtained token. A "403" case means status 403 with `detail` starting `Permission not found in database`.
- Request validation (422) runs before the permission check, so role-matrix tests must send valid bodies.
- Create endpoints are rate limited per client IP (`rate_limit_create`: 30 per minute, bulk mappings 10 per minute) and dropdown endpoints 100 per minute. Suites that create many rows must pace themselves or disable the limiter; one dedicated case per feature proves the 429.
- Tenant isolation case pattern: create a row in tenant A (`qa_school`) and a second QA tenant B; the row is invisible to B (list, dropdown, get by id return no row or 404), and a tenant A token with a `cschema` header naming B gets 403.
- Dropdowns and a few list calls are cached in memory for 5 minutes per tenant and process (F15). Tests that edit then re-read a dropdown must expect the invalidation rules documented in F15.
- Backend unit tests (U, `backend/tests/unit/masters/`) use fake sessions and never open a database. Web unit tests use vitest and mobile unit tests use jest. Logic that lives inside a React component and is not exported (called out per feature) must be extracted or exported before it can be unit tested.

## Feature index

| ID | Title |
|---|---|
| F01 | Academic years |
| F02 | Active year and working-year selection |
| F03 | Classes and sections: list, search, sort, export and create |
| F04 | Edit and delete a class |
| F05 | Add, edit and delete sections |
| F06 | Class and section lookups and dropdowns |
| F07 | Subject categories |
| F08 | Subjects |
| F09 | Class-subject mappings: list, edit, delete and single create |
| F10 | Bulk class-subject mappings |
| F11 | Parents |
| F12 | Locations: states, districts and mandals |
| F13 | Castes and sub-castes |
| F14 | School settings (School Registration) |
| F15 | Masters hub, menu entries and dropdown caching |

---

## F01 Academic years

**Purpose.** An admin defines the school years (title, start date, end date, active flag). Classes, subjects, mappings, holidays, fees and admissions are scoped to a year, and only one year can be active.

**Roles and permissions.**
- Create: `academic_years:create`. Edit and activate or deactivate: `academic_years:update`. Deactivate (Delete button) and permanent delete: `academic_years:delete`.
- List: `academic_years:list` (paged list and the web page gate). Single read, `dropdown` and `active`: `academic_years:read`.
- Admin has all five. Staff, Teacher, Student and Parent have read and list only. Menu: Masters > Academic Years (web `/masters/academicyears`), Home > Masters > Academic Years (mobile `/masters/academicyears`).

**Preconditions.** Admin session. No other data is needed to create a year; permanent delete needs a year that no admission, fee class mapping, fee student mapping, fee type, class-subject mapping, class, subject or holiday references.

**Steps, web.**
1. Open Masters > Academic Years. The card "Academic Years" shows the table (columns S.No., ID, Title, Start Date, End Date, Active, Actions), a column-selector button "Filters" (funnel icon), an "Export" menu and an "Add Academic Year" button (only with `academic_years:create`). Row actions are the "Edit" and "Delete" icons (update and delete grants).
2. Search: type in "Search..." (matches any visible column of the rows on the current page only, because the list is server paged; the label "n of m results" appears). Sort: click a column header (first click ascending, second descending, third clears). Page: "Previous" / "Next" and "Rows per page" (5, 10, 20, 50, 100; default 5).
3. Create: click "Add Academic Year", dialog "Add New Academic Year", fill Title (required), Start Date (required), End Date (required), Active (checkbox, checked by default), click "Add Academic Year". Toast "Academic year created!". Failure toast "Failed to create academic year".
4. Edit: click the Edit icon on a row, change Title, Start Date, End Date or the Active checkbox inline, press the green check (or Enter in a text box) to save, the red X (or Escape) to discard. Toast "Academic year updated!". One PUT is sent per changed field.
5. Deactivate: click the trash icon, dialog "Delete Row?" ("Are you sure you want to delete this row? This action cannot be undone.") with Cancel and Delete. Toast "Academic year deleted!". The row stays in the table with an inactive badge (the table loads with `active_only=false`).
6. Export: "Export" > "Export to CSV", "Export to Excel" or "Download Data" produce `academic_years_data.csv`, `academic_years_data.xlsx`, `academic_years_data.json` from the visible columns and filtered rows. Column selector: "Select All" and per-column checkboxes (at least one column always stays).

**Steps, mobile.**
1. Home > Masters > "Academic Years". Header shows "Academic Years" and "n records found", an "Export" button, "Add Academic Year" (with create permission) and "Filters". The list has the columns S.NO., TITLE / DATES (title with start and end date joined by an arrow), ACTIVE (Active or Inactive badge) and ACTIONS (Edit and Delete icons with the grants).
2. Search: "Search..." filters title and the two dates. There is no sort and no paging (all years up to 100 are loaded). Pull down to refresh.
3. Create: "Add Academic Year" opens the modal "Add Academic Year": Title * (placeholder "e.g. 2025-26"), Start Date * and End Date * (text boxes, "YYYY-MM-DD"), Active toggle, buttons "Cancel" and "Create" ("Saving..." while pending). Empty required field: toast "Error - Please fill in all required fields". Success: toast "Created - Academic year has been created."
4. Edit: Edit icon (label "Edit") opens "Edit Academic Year" with the same fields; button "Update"; toast "Updated - Academic year has been updated."
5. Delete: Delete icon opens the confirm "Delete Academic Year" ("Are you sure you want to delete "<title>"?", confirm "Delete"). Toast "Deleted - Academic year has been deleted." The year is deactivated, not removed.
6. Export: "Export" > "Export As": "Export to CSV", "Export to Excel", "Download Data" (web build downloads, native shares through the OS sheet).

**Expected results.** A created year appears in the list with the entered dates; creating or activating a year with Active on leaves it as the only active year; a deleted year shows as inactive and disappears from `GET /masters/academic_years/dropdown` and from `GET /masters/academic_years/active`.

**API endpoints.** Prefix `/api/v1/masters/academic_years`.
- `POST /` body `{title, start_date, end_date, is_active=true}` -> 201 `AcademicYearRead`.
- `GET /` query `skip=0`, `limit=10`, `active_only=true` -> `{items, total_count, has_next}`.
- `GET /dropdown` query `active_only=true` -> `[{id, title}]` ordered by title.
- `GET /active` -> list of active years (up to 100).
- `GET /{academic_year_id}` -> `AcademicYearRead`.
- `PUT /{academic_year_id}` partial body (`title`, `start_date`, `end_date`, `is_active`) -> `AcademicYearRead`.
- `DELETE /{academic_year_id}` -> deactivates, returns the row.
- `DELETE /{academic_year_id}/permanent` -> `{message}` after a dependency check.

**Rules and validations.**
1. `title` is required, at most 50 characters, unique per tenant (database constraint `tenant_id, title`; the service compares exact, case-sensitive text).
2. `start_date` and `end_date` are required ISO dates. `end_date` before `start_date` is rejected (422 on create, 422 or 400 on update, which also compares against the stored date). There is no overlap check.
3. `is_active` defaults to true on create. Creating a year with `is_active=true`, or updating one to `is_active=true`, deactivates every other year in the tenant.
4. `DELETE /{id}` only sets `is_active=false`. Setting the only active year inactive is allowed (no active year then exists).
5. `DELETE /{id}/permanent` is refused (400) while any admission (`academic_year_id` or `admitted_academic_year_id`), fee class mapping, fee student mapping, fee type or class-subject mapping references the year. The message is `Cannot delete academic year '<title>' because it is being used by N record(s): ...`. Classes, subjects and holidays are not in that check, so a year that only they reference fails on the foreign key and returns 400 `Academic Year deletion failed: ...`.
6. The list defaults to `limit=10` and `active_only=true`; management screens must pass `active_only=false`.
7. `has_next` is `(skip + limit) < total_count`.
8. `GET /` and `GET /dropdown` are cached for 5 minutes; create, update, deactivate and permanent delete clear the academic-years cache entries (F15).
9. Rows are tenant scoped by row-level security.

**Error and edge cases.**
- Duplicate title on create: 400 `Academic year already exists`. Duplicate title on update: 400 `Academic Year update failed: ...`.
- `PUT` and `DELETE /{id}` for an unknown id return 400 (the service wraps its own 404 in a generic handler; the message contains `404: Academic Year with id ... not found`). `GET /{id}` and `DELETE /{id}/permanent` return 404.
- Title longer than 50 characters: 400 `Academic Year creation failed: ...` (database length error).
- Missing field or malformed date: 422.
- Web shows only the generic toast text for failures; the backend reason is not displayed. The web total is estimated because the web reads `total` while the API sends `total_count`; the Next button depends on a full page being returned.
- Mobile list uses `limit=100`; the shared year selector (`AcademicYearContext`) and the web store call the list without a limit and so see only the first 10 years (F02).

**Unit-testable logic.**
- `AcademicYearCreate` and `AcademicYearUpdate` validation (required fields, ISO dates, `is_active` default true).
- Service `create_academic_year` with a fake session: duplicate title raises 400; `is_active=true` issues the update that clears other active years; `is_active=false` does not.
- Service `update_academic_year`: only `exclude_unset` fields are applied; activating clears others; an unknown id is returned as a 400 wrapper.
- `delete_academic_year` dependency message builder (counts and wording) with fake counts.
- Pagination arithmetic `has_next`.
- `cache_dropdown` key includes the tenant; `invalidate_cache("dropdown", "academic_years")` removes academic-year keys only.
- Web: `fetchPaginatedAcademicYears` total and `hasMore` estimation; `Table` search, three-state sort and `serialNo` with pagination; `MasterPage` export value builders. Mobile: the title/date filter.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-01-U01 | [backend] `AcademicYearCreate` with only title, start_date, end_date | `is_active` defaults to True; model valid | passing |
| TC-MST-01-U02 | [backend] `AcademicYearCreate` missing `title`, then with `start_date="31-03-2026"` | Both raise validation errors (field `title` required; invalid date) | passing |
| TC-MST-01-U03 | [backend] `create_academic_year` with fake session, existing row has the same title | HTTPException 400 `Academic year already exists`; nothing added | passing |
| TC-MST-01-U04 | [backend] `create_academic_year` with `is_active=True` vs `False` | True: one UPDATE clearing active flags executed before insert; False: no such UPDATE | passing |
| TC-MST-01-U05 | [backend] `update_academic_year` for an id the fake session cannot find | Raises HTTPException 400 whose detail contains `404: Academic Year with id` | passing |
| TC-MST-01-U06 | [backend] `delete_academic_year` with fake counts admissions=2, class_subject=1, others 0 | 400 detail `... being used by 3 record(s): 2 student admission(s), 1 class subject mapping(s)` | passing |
| TC-MST-01-U07 | [backend] `has_next` for (skip=0, limit=5, total=7), (skip=5, limit=5, total=7), (skip=0, limit=10, total=10) | True, False, False | passing |
| TC-MST-01-U08 | [web] `fetchPaginatedAcademicYears` with a response of 5 items and no `total`, limit 5 | `hasMore` true and `total` estimated as skip+items+limit (10) | passing |
| TC-MST-01-U09 | [web] `Table` sort cycle on the Title column | asc, desc, then unsorted original order; numeric-aware compare (`2026-27` after `2025-26`) | blocked: needs the sort helper exported from web/src/components/common/table.tsx (logic is inside the Table component) |
| TC-MST-01-U10 | [mobile] Academic-year filter with query `2026` over title, start_date, end_date | Returns years whose title or either date contains `2026`; empty query returns all | blocked: needs the filter exported from mobile/app/masters/academicyears.tsx (inline useMemo) |
| TC-MST-01-A01 | Admin `POST /masters/academic_years/` `{title:"QA-2031-32", start_date:"2031-04-01", end_date:"2032-03-31", is_active:false}` | 201; body has `id`, same title and dates, `is_active:false` | passing |
| TC-MST-01-A02 | Admin POST omitting `is_active` while another year is active | 201 with `is_active:true`; afterwards `GET /?active_only=false` shows exactly one active year (the new one) | skipped: Creating a year with is_active true (the default) would change the tenant's active year, which the QA rules fo... |
| TC-MST-01-A03 | Admin POST a second year with `is_active:true` | Previously active year now `is_active:false` in `GET /?active_only=false` | skipped: Creating an active year deactivates the baseline year, which the QA rules forbid |
| TC-MST-01-A04 | POST a title that already exists (same case) | 400 `Academic year already exists` | passing |
| TC-MST-01-A05 | POST `QA-2031-32` and `qa-2031-32` | Both succeed (comparison is case-sensitive) | passing |
| TC-MST-01-A06 | POST with missing `title`; POST with `start_date:"not-a-date"` | 422 for each, `detail[].loc` names the field | passing |
| TC-MST-01-A07 | POST title of exactly 50 characters, then 51 characters | 50: 201. 51: 400 detail starts `Academic Year creation failed` | passing |
| TC-MST-01-A08 | POST with `end_date` earlier than `start_date` | 422 | passing |
| TC-MST-01-A09 | `GET /` with no query while 3 years exist and exactly 1 is active | `items` has 1 row (the active one), `total_count` 1, `has_next` false (defaults `active_only=true`, `limit=10`) | passing |
| TC-MST-01-A10 | `GET /?active_only=false&skip=0&limit=5` then `skip=5&limit=5` with 7 years | Page 1: 5 items, `total_count` 7, `has_next` true; page 2: 2 items, `has_next` false | passing |
| TC-MST-01-A11 | `GET /dropdown` and `GET /dropdown?active_only=false` | Items are `{id, title}` ordered by title; second call also lists inactive years | passing |
| TC-MST-01-A12 | `GET /active` | Array of years with `is_active:true` only | passing |
| TC-MST-01-A13 | `GET /{id}` for an existing and a random UUID | 200 `AcademicYearRead`; unknown id 404 detail contains `not found` | passing |
| TC-MST-01-A14 | Admin `PUT /{id}` `{title:"QA-2031-32-B"}` | 200, title changed, dates and `is_active` unchanged | passing |
| TC-MST-01-A15 | `PUT /{id}` `{is_active:true}` on an inactive year | 200; every other year now inactive | skipped: Activating a year deactivates the baseline year, which the QA rules forbid |
| TC-MST-01-A16 | `PUT /{id}` with another year's title | 400 detail starts `Academic Year update failed` | passing |
| TC-MST-01-A17 | `PUT /{random uuid}` | 404 detail starts `Academic Year with id` | passing |
| TC-MST-01-A18 | `DELETE /{id}` on an active year | 200 returns the row with `is_active:false`; still in `GET /?active_only=false`; absent from `GET /dropdown` | passing |
| TC-MST-01-A19 | `DELETE /{random uuid}` | 404 | passing |
| TC-MST-01-A20 | `DELETE /{id}/permanent` on a year with no references | 200 `{message:"Academic Year QA-... deleted successfully"}`; `GET /{id}` then 404 | passing |
| TC-MST-01-A21 | Permanent delete a year that has a class-subject mapping (created through F10 setup) | 400 detail `Cannot delete academic year ... 1 class subject mapping(s)` | passing |
| TC-MST-01-A22 | Permanent delete a year that has only a class (no mapping, admission or fee row) | 400 detail starts `Academic Year deletion failed` (foreign key) | passing |
| TC-MST-01-A23 | Permanent delete a random UUID | 404 | passing |
| TC-MST-01-A24 | Read matrix: `GET /`, `/dropdown`, `/active`, `/{id}` as Admin, Staff, Teacher, Student, Parent | 200 for all five roles | passing |
| TC-MST-01-A25 | Write matrix: POST, PUT, DELETE, DELETE permanent as Staff, Teacher, Student, Parent with valid bodies | 403 `Permission not found in database` for each; Admin 2xx | passing |
| TC-MST-01-A26 | Every endpoint without an Authorization header | 401 | passing |
| TC-MST-01-A27 | Tenant isolation: year created in tenant A | Not in tenant B `GET /`, `/dropdown`; `GET /{id}` with B token 404; A token with `cschema` of B returns 403 | passing |
| TC-MST-01-A28 | Create-and-read cache: POST then immediately `GET /dropdown` | New year present (cache invalidated by create) | passing |
| TC-MST-01-A29 | 31 POSTs from one client within a minute (limiter enabled) | The 31st returns 429 with `RATE_LIMIT_EXCEEDED` | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-01-E01 | P1 | Web | Admin | qa_manual with the seeded year "2026-2027" | 1. Sign in as Admin (organisation qa_manual).<br>2. Open Masters > Academic Years. | Card "Academic Years" with columns S.No., ID, Title, Start Date, End Date, Active, Actions; row "2026-2027", 2026-06-01, 2027-03-31, badge Active; buttons "Filters", "Export", "Add Academic Year"; Edit and Delete icons on the row | planned |
| TC-MST-01-E02 | P3 | Web | Admin | TC-MST-01-E05 done (year "QA 2033-34" exists) | 1. Open Masters > Academic Years.<br>2. Type "QA 2033" in "Search...".<br>3. Clear the search box. | Only "QA 2033-34" remains and "1 of n results" shows (search covers the rows of the current page only); clearing restores all rows | planned |
| TC-MST-01-E03 | P3 | Web | Admin | At least two years exist (TC-MST-01-E05 done) | 1. Open Masters > Academic Years.<br>2. Click the "Title" header three times. | First click ascending, second descending, third back to the original order; the header chevron icon changes each time | planned |
| TC-MST-01-E04 | P3 | Web | Admin | 6 or more years exist (create inactive years "QA 2031-32" to "QA 2036-37" as in TC-MST-01-E05) | 1. Open Masters > Academic Years.<br>2. Check the range text and "Previous".<br>3. Click "Next".<br>4. Set "Rows per page" to 10. | Page 1 shows 5 rows, "Previous" disabled, range "1-5 of ..."; "Next" shows the following rows; with 10 per page all rows show on one page. The total in the range text is estimated (Known gaps 10) | planned |
| TC-MST-01-E05 | P1 | Web | Admin | No year titled "QA 2033-34" | 1. Open Masters > Academic Years.<br>2. Click "Add Academic Year".<br>3. Enter Title "QA 2033-34", Start Date 2033-04-01, End Date 2034-03-31.<br>4. Untick "Active" (keeps "2026-2027" active).<br>5. Click "Add Academic Year". | Toast "Academic year created!"; dialog "Add New Academic Year" closes; row "QA 2033-34" with badge Inactive appears; "2026-2027" stays Active. Cleanup: permanent delete via API `DELETE /masters/academic_years/{id}/permanent` | planned |
| TC-MST-01-E06 | P3 | Web | Admin | None | 1. Click "Add Academic Year".<br>2. Leave Title empty, fill both dates.<br>3. Click "Add Academic Year". | Submit is blocked (required field); no request is sent; dialog stays open | planned |
| TC-MST-01-E07 | P2 | Web | Admin | Seeded year "2026-2027" | 1. Click "Add Academic Year".<br>2. Enter Title "2026-2027", Start Date 2033-04-01, End Date 2034-03-31, untick "Active".<br>3. Click "Add Academic Year". | Toast "Failed to create academic year" (the backend reason is not shown); dialog stays open; no new row | planned |
| TC-MST-01-E08 | P2 | Web | Admin | TC-MST-01-E05 done | 1. Click the Edit icon on row "QA 2033-34".<br>2. Change Title to "QA 2033-34 B".<br>3. Click the green check. | Toast "Academic year updated!"; row shows "QA 2033-34 B" | planned |
| TC-MST-01-E09 | P3 | Web | Admin | TC-MST-01-E05 done | 1. Click the Edit icon on row "QA 2033-34".<br>2. Change Title to "QA changed".<br>3. Click the red X. | No request; the original title stays | planned |
| TC-MST-01-E10 | P3 | Web | Admin | TC-MST-01-E05 done (inactive QA year); "2026-2027" active | 1. Click the Edit icon on the QA year.<br>2. Tick "Active" and click the green check.<br>3. Reload the page.<br>4. Cleanup: edit "2026-2027", tick "Active", save. | After step 3 the QA year is Active and "2026-2027" shows Inactive; after step 4 "2026-2027" is the only active year again | planned |
| TC-MST-01-E11 | P2 | Web | Admin | TC-MST-01-E05 done | 1. Click the trash icon on the QA year.<br>2. In "Delete Row?" click "Cancel".<br>3. Click the trash icon again and click "Delete". | Cancel: nothing changes. Delete: toast "Academic year deleted!"; the row stays with badge Inactive (deactivated, not removed) | planned |
| TC-MST-01-E12 | P3 | Web | Admin | Seeded year | 1. Click "Filters" and keep only Title and Active ticked.<br>2. Click "Export" > "Export to CSV". | File `academic_years_data.csv` downloads with header `Title,Active` and one row per listed year | planned |
| TC-MST-01-E13 | P2 | Web | Teacher | Seeded year | 1. Sign in as Teacher.<br>2. Open Masters > Academic Years. | List visible with "Export"; no "Add Academic Year"; no Edit or Delete icons | planned |
| TC-MST-01-E14 | P2 | Web | Student | Seeded student Advik Mehta (login 002, first-login password change done); seeded parent login venkat.raju@example.com | 1. Sign in as the student.<br>2. Check the sidebar.<br>3. Repeat signed in as the parent. | Sidebar has no "Masters" entry for either role (Student: Dashboard, Students, Fee, Exam) | planned |
| TC-MST-01-E15 | P1 | Mobile | Admin | Seeded year "2026-2027" | 1. Sign in as Admin (organisation qa_manual).<br>2. Tap Home > "Masters" > "Academic Years". | Header "Academic Years", "1 records found" (or the current count), "Export", "Add Academic Year", "Filters"; row "2026-2027" with its two dates and badge Active | planned |
| TC-MST-01-E16 | P3 | Mobile | Admin | TC-MST-01-E18 done | 1. Open Academic Years.<br>2. Type "QA 2034" in "Search...".<br>3. Clear the search. | Only the matching year shows; clearing shows all | planned |
| TC-MST-01-E17 | P3 | Mobile | Admin | None | 1. Tap "Add Academic Year".<br>2. Leave "Title *" empty, fill both dates.<br>3. Tap "Create". | Toast "Error - Please fill in all required fields"; modal stays open | planned |
| TC-MST-01-E18 | P1 | Mobile | Admin | No year "QA 2034-35" | 1. Tap "Add Academic Year".<br>2. Enter Title "QA 2034-35", Start Date "2034-04-01", End Date "2035-03-31".<br>3. Switch "Active" off.<br>4. Tap "Create". | Modal closes; toast "Created - Academic year has been created."; new row with badge Inactive; "2026-2027" stays Active. Cleanup: permanent delete via API | planned |
| TC-MST-01-E19 | P2 | Mobile | Admin | TC-MST-01-E18 done | 1. Tap the Edit icon on "QA 2034-35".<br>2. Change Title to "QA 2034-35 B".<br>3. Tap "Update". | Toast "Updated - Academic year has been updated."; row shows the new title | planned |
| TC-MST-01-E20 | P2 | Mobile | Admin | TC-MST-01-E18 done | 1. Tap the Delete icon on the QA year.<br>2. In "Delete Academic Year" tap "Delete". | Toast "Deleted - Academic year has been deleted."; the row shows Inactive and stays listed | planned |
| TC-MST-01-E21 | P3 | Mobile | Admin | Seeded year | 1. Tap "Export".<br>2. In "Export As" tap "Export to CSV". | On the web build `academic_years_data.csv` downloads; on a device the share sheet opens | planned |
| TC-MST-01-E22 | P2 | Mobile | Teacher | Seeded year | 1. Sign in as Teacher.<br>2. Open Home > Masters > Academic Years.<br>3. Sign in as seeded student Advik Mehta and look at Home. | Teacher: list with "Export", no "Add Academic Year", no Edit or Delete icons. Student: Home shows only Students, Exam Management and Fee Management (no Masters card) | planned |

---

## F02 Active year and working-year selection

**Purpose.** Every user picks an academic year at login; that working year scopes year-bound screens. For a web Admin the chosen year is also made the single active year on the server.

**Roles and permissions.** All roles pick a year at login (`GET /auth/academic-years` is public). The activation call needs `academic_years:update`, which only Admin holds. Reading the list for the in-app year store needs `academic_years:list`.

**Preconditions.** At least one academic year (F01). Login itself is documented in `docs/features/auth.md`.

**Steps, web.**
1. On the login page choose the organisation, enter credentials and select an academic year from the year list.
2. After login the year id is stored in the persisted `academic-year-storage`. When the role is Admin the web client then sends `PUT /masters/academic_years/{id}` with `is_active:true`.
3. Year-bound pages (Classes, Subjects, Class-Subject Mappings, Holidays) read `selectedAcademicYearId` from this store. If the store is empty it falls back to the active year, otherwise the last year in the list.

**Steps, mobile.**
1. Login screen: after the organisation code is accepted, pick an academic year, then sign in.
2. `AcademicYearContext` stores `activeAcademicYearId` (key `@active_academic_year`). It validates the stored id against the loaded years and, if invalid, selects the active year or the first year. Mobile never changes the backend active year.

**Expected results.** After an Admin web login the chosen year is the only year with `is_active:true`. A non-Admin login or a mobile login leaves the backend active year unchanged.

**API endpoints.**
- `GET /api/v1/auth/academic-years` (public, header `cschema`) -> year list for the login form.
- `PUT /api/v1/masters/academic_years/{id}` `{is_active:true}` (web Admin login only).
- `GET /api/v1/masters/academic_years/` and `/active` (year store and context).

**Rules and validations.**
1. One active year per tenant, enforced by the update service (F01 rule 3).
2. The active year is effectively the year the last web Admin logged into.
3. The web store and the mobile context call `GET /masters/academic_years/` without a limit, so only the first 10 years (default `limit=10`, no ordering) can be selected.
4. Selected year ids shorter than 10 characters or equal to `371` are discarded from local storage by the web store.

**Error and edge cases.**
- Non-Admin web login: no activation call, the backend active year is unchanged.
- Stored year id no longer exists: mobile context selects a valid year; web store keeps the stale id until cleared.
- More than 10 years exist: the 11th and later years are not selectable in the web store or the mobile context.

**Unit-testable logic.**
- Web `academicYearStore.fetchAndSetAcademicYears` fallback (active year, else last year) with mocked `fetchAcademicYears`; persisted-id sanity check (`371` and short ids dropped).
- Mobile `AcademicYearContext` validation of the stored id and auto-select order.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-02-U01 | [web] `fetchAndSetAcademicYears` with years `[A inactive, B active, C inactive]` and empty selection | `selectedAcademicYearId` becomes B | passing |
| TC-MST-02-U02 | [web] Same with no active year | Selection becomes the last year in the list | passing |
| TC-MST-02-U03 | [web] Persisted `academic-year-storage` holds id `371` or a 5-character id | Value is removed and selection starts empty | passing |
| TC-MST-02-U04 | [mobile] Context with stored id not in the loaded list | Replaced by the active year, else the first year, and written to AsyncStorage | blocked: logic is inside the AcademicYearContext provider effect (mobile/contexts/AcademicYearContext.tsx); needs a pure resolver exported (components cannot be rendered) |
| TC-MST-02-A01 | `GET /auth/academic-years` with only a `cschema` header | 200 list containing the QA years (id, title) | passing |
| TC-MST-02-A02 | Admin `PUT /masters/academic_years/{B}` `{is_active:true}` with A active | A inactive, B the only active year | skipped: Activating a year changes the tenant's active year, which the QA rules forbid |
| TC-MST-02-A03 | Teacher `PUT` the same | 403 `Permission not found in database`; active year unchanged | passing |
| TC-MST-02-A04 | Create 12 years and call `GET /masters/academic_years/?active_only=false` with no `limit` (as the web store and mobile context do) | 10 items, `total_count` 12, `has_next` true (the client-visible limit) | passing |
| TC-MST-02-A05 | `GET /masters/academic_years/active` after A02 | Exactly one item, B | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-02-E01 | P1 | Web | Admin | Seeded year "2026-2027" (the only year) | 1. Sign out.<br>2. On the login page enter organisation qa_manual, Admin credentials and choose year "2026-2027".<br>3. Open Masters > Subjects. | Login succeeds; the header shows "Year 2026-2027"; `GET /masters/academic_years/active` returns "2026-2027" as the only active year | planned |
| TC-MST-02-E02 | P2 | Web | Teacher | TC-MST-01-E05 done (second, inactive year) | 1. Sign in as Teacher choosing the QA year.<br>2. Open Masters > Classes and Sections.<br>3. Check the active year through the API or as Admin. | Year-bound pages request the QA year; the backend active year is still "2026-2027" (no activation for non-Admin) | planned |
| TC-MST-02-E03 | P2 | Mobile | Admin | TC-MST-01-E18 done (second, inactive year) | 1. Sign in on mobile choosing the QA year.<br>2. Open Home > Masters > Subjects.<br>3. Check the active year as Admin on web. | Mobile screens are scoped to the QA year (Subjects shows no seeded subjects); the backend active year stays "2026-2027" | planned |
| TC-MST-02-E04 | P3 | Web | Admin | 12 or more academic years exist (QA years created as in TC-MST-01-E05) | 1. Sign in as Admin.<br>2. Open Masters > Subjects and inspect the year store (`academic-year-storage`) or the year list request. | The year list call has no `limit`, so only the first 10 years reach the store; years 11 and 12 cannot be selected (documents Known gaps 10). Cleanup: remove the QA years | planned |

---

## F03 Classes and sections: list, search, sort, export and create

**Purpose.** An admin sees every class with its sections and creates a class together with its sections in one step.

**Roles and permissions.**
- List: `classes:list` (page gate, `GET read_all`). Single class: `classes:read`.
- Create class with sections: `classes:create`. The "Add Section" icon on a row needs `sections:create`.
- Admin full; Staff and Teacher read and list; Student and Parent hold `classes:read` and `classes:list` and can call the read endpoints. Menu: Masters > Classes and Sections (web `/masters/classesandsections`), Home > Masters > Classes and Sections (mobile screen "Classes & Sections").

**Preconditions.** An academic year exists (F01) and is selected as the working year.

**Steps, web.**
1. Open Masters > Classes and Sections. The card "Classes & Sections" lists classes with columns Class Name, Class Code, Sections (badge "1 section" or "n sections"), Status, plus S.No., an expand chevron and Actions (icons "Add Section", "Edit Class", "Delete Class" by grant). Buttons: "Columns", "Export", "Add Class & Sections".
2. Search: "Search classes..." matches class name or class code. Sort: click Class Name, Class Code, Sections or Status (asc, desc, clear). Pagination (rows per page 5, 10, 20, 50) appears only when there are more rows than the page size (default 10).
3. Expand a row with the chevron to see its sections ("No sections found" when empty) and the description.
4. Columns: "Columns" > "Select All" and per-column checkboxes. Export: "Export" > "Export to CSV" (`classes_sections_data.csv`) or "Export to Excel" (`classes_sections_data.xlsx`); the Sections cell lists names joined with `;` (CSV) or `, ` (Excel); Status exports as Active or Inactive.
5. Create: "Add Class & Sections" opens a three-step dialog. Step 1 "Enter Class Details": Class Name, Class Code, Active (default checked), buttons "Cancel" and "Next" (disabled until name and code are filled). Step 2 "Add Sections": "Quick Add Sections Alphabetically" with "From:" (default A) and "To:" (default D) and "Generate Sections" (toast "Generated N sections from X to Y"); "Manual Sections" rows (placeholder "Section 1", "Section 2", ...) with + ("Add Section") and x ("Remove Section") buttons (at least one row stays), "Total sections: n". Buttons "Cancel", "Back", "View". Step 3 "Summary" shows Class Name, Class Code, Year (the year id), Active, Sections, buttons "Cancel", "Edit", "Submit". Success toast "Class and sections created successfully!". The class is created in the working year.

**Steps, mobile.**
1. Home > Masters > Classes and Sections. Screen "Classes & Sections" with "n classes" and header icons Columns, Export, Add. Search "Search classes or sections..." matches class name, code or any section name.
2. Cards show the class (S.No., name, "Code: ...", Active/Inactive badge, "n sections") with icons Add (add section), Edit, Delete and an expand chevron; expanding lists the sections with their badges ("No sections - tap + to add one" when empty). The Columns sheet ("Select All") toggles Class Code, Sections and Status. Export sheet "Export As": "Export to CSV", "Export to Excel".
3. Create: the header Add icon opens the same three-step wizard ("Enter Class Details" with Class Name * placeholder "e.g., Class 1", Class Code * placeholder "e.g., C1", Active; "Quick Add Sections Alphabetically", "Generate Sections" (toast "Sections Generated"), "Manual Sections"; Back, View, Edit, Submit). Validation toasts "Validation - Class name is required", "Validation - Class code is required", "Validation - At least one section is required"; without a working year "Error - No active academic year". Success toast "Class and sections created successfully".

**Expected results.** One class row and N section rows (names as entered, all active unless unticked) are stored in a single transaction and appear in the list.

**API endpoints.** Prefix `/api/v1/masters/class_sections`.
- `POST /` body `{name, short_code, academic_year_id, description?, is_active=true, sections:[{name, description?, is_active=true}]}` -> 201 `ClassRead` (class with `sections`).
- `GET /read_all` -> `[ClassRead]` for all classes of the tenant (see rules).
- `GET /by_class_id/{class_id}` -> `ClassRead`.

**Rules and validations.**
1. `name` is required, at most 50 characters, unique per academic year (`tenant_id, academic_year_id, name`). `short_code` is required by the schema and at most 10 characters in the column. `description` at most 100. `academic_year_id` must reference an existing year.
2. Section names are unique within one class (`tenant_id, class_id, name`); the same letters can be reused in other classes.
3. A class may be created without sections (`sections` omitted or empty).
4. `GET /read_all` accepts `academic_year_id` and `active_only` (default false, so management screens still see inactive classes) and returns classes ordered by name with all sections. With zero matching classes it returns an empty list.
5. The wizard letter generator accepts only A-Z with start not after end; manual names are trimmed only for the emptiness check.

**Error and edge cases.**
- Duplicate class name, duplicate section names in the same payload, over-length values or an unknown year: 400 `Error creating class with sections: ...` (database message included).
- Missing `short_code`, `name` or `academic_year_id`: 422.
- A duplicate class name in the same academic year: 400 `Class '<name>' already exists for this academic year`. The same name can be used in another academic year.
- Web validation toasts: "Class name is required", "Class code is required", "Valid academic year is required", "At least one section with name is required", "Start letter must come before end letter", "Please use letters A-Z only".
- Roles without create do not see the add button on web (permission guard) or mobile.

**Unit-testable logic.**
- `ClassCreate` / `SectionCreate` schema (required `short_code`, `is_active` default true, `sections` optional).
- `create_class_with_sections` with a fake session: class then N sections added; exception path rolls back and returns 400.
- Web: `generateSectionsAlphabetically` range and error cases and the table search, sort and pagination slice (extract from `AddClassAndSectionsModal.tsx` and `ClassSectionsTable.tsx`); export row builder.
- Mobile: wizard letter generation and the class/section filter.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-03-U01 | [backend] `ClassCreate` without `short_code` | Validation error for `short_code` | passing |
| TC-MST-03-U02 | [backend] `ClassCreate` minimal valid payload | `is_active` True, `sections` None, `description` None | passing |
| TC-MST-03-U03 | [backend] `create_class_with_sections` with 3 section dicts, fake session | One class and 3 sections added, one commit, cache invalidated for classes and sections | passing |
| TC-MST-03-U04 | [backend] `create_class_with_sections` when the fake session raises on flush | Rollback and HTTPException 400 `Error creating class with sections` | passing |
| TC-MST-03-U05 | [web] Section generator for From `A`, To `D`; then From `D`, To `A`; then `a`..`c` and `1`..`3` | `[A,B,C,D]`; error "Start letter must come before end letter"; lowercase upper-cased to A..C; error "Please use letters A-Z only" | blocked: needs generateSectionsAlphabetically exported from web/src/pages/masters/AddClassAndSectionsModal.tsx |
| TC-MST-03-U06 | [web] Class table search `c1` over name and code, sort by Sections count | Matches name or code case-insensitively; sorts numerically by section count | blocked: needs search and sort helpers exported from web/src/components/masters/classesandsections/ClassSectionsTable.tsx |
| TC-MST-03-U07 | [web] Export builders for a class with sections A and B, inactive | CSV cell `A; B`, Excel cell `A, B`, status `Inactive` | blocked: needs the export row builders exported from web/src/components/masters/classesandsections/ClassSectionsTable.tsx |
| TC-MST-03-U08 | [mobile] Class filter `b` | Returns classes whose name, code or any section name contains `b` | blocked: needs the class filter exported from mobile/app/masters/classesandsections.tsx |
| TC-MST-03-A01 | Admin `POST /masters/class_sections/` `{name:"QA-C1", short_code:"QC1", academic_year_id, sections:[{name:"A"},{name:"B"}]}` | 201; `sections` has 2 items with `class_id` equal to the class id, both `is_active:true` | passing |
| TC-MST-03-A02 | POST without `sections` | 201 with `sections:[]` | passing |
| TC-MST-03-A03 | POST with an existing class name | 400 detail starts `Error creating class with sections` | passing |
| TC-MST-03-A04 | POST with sections `[{name:"A"},{name:"A"}]` | 400 (unique per class); no class row remains | passing |
| TC-MST-03-A05 | POST two classes both with sections A and B | Both 201 (section names repeat across classes) | passing |
| TC-MST-03-A06 | POST with `short_code` omitted, then `name` omitted, then `academic_year_id` omitted | 422 each | passing |
| TC-MST-03-A07 | POST `name` of 50 and 51 characters; `short_code` of 10 and 11 characters | 50 and 10: 201. 51 and 11: 400 | passing |
| TC-MST-03-A08 | POST with a random `academic_year_id` | 400 (foreign key) | passing |
| TC-MST-03-A09 | POST a class named like a class in another academic year | 201 (name is unique per academic year) | passing |
| TC-MST-03-A10 | `GET /read_all` with 2 classes in different years and `academic_year_id` of the first | Both classes returned (year filter ignored) with their sections | passing |
| TC-MST-03-A11 | `GET /read_all` on a tenant with zero classes | 200 `[]` | passing |
| TC-MST-03-A12 | `GET /by_class_id/{id}` for an existing class | 200 `ClassRead` with sections | passing |
| TC-MST-03-A13 | `GET /by_class_id/{random uuid}` | 404 detail `Class not found` | passing |
| TC-MST-03-A14 | Read matrix: `GET /read_all` and `GET /by_class_id/{id}` as Admin, Staff, Teacher, Student, Parent | 200 for all five | passing |
| TC-MST-03-A15 | Write matrix: `POST /` as Staff, Teacher, Student, Parent | 403 for each; Admin 201 | passing |
| TC-MST-03-A16 | No Authorization header on POST and GET | 401 | passing |
| TC-MST-03-A17 | Tenant isolation: class created in tenant A | Absent from tenant B `GET /read_all`; `GET /by_class_id/{id}` with B token returns 404 | passing |
| TC-MST-03-A18 | 31 POSTs within a minute (limiter enabled) | The 31st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-03-E01 | P1 | Web | Admin | Seeded classes Nursery to Class 5 | 1. Sign in as Admin (qa_manual).<br>2. Open Masters > Classes and Sections. | Card "Classes & Sections" lists the 8 classes with codes (NUR, LKG, UKG, C1 to C5), "2 sections" badges and Active status; buttons "Columns", "Export", "Add Class & Sections"; row icons "Add Section", "Edit Class", "Delete Class" | planned |
| TC-MST-03-E02 | P2 | Web | Admin | Seeded classes | 1. Type "Class 1" in "Search classes...". | Only "Class 1" remains; "1 of 8 results" shows | planned |
| TC-MST-03-E03 | P3 | Web | Admin | TC-MST-03-E06 done (QA C9 has 3 sections) | 1. Click the "Sections" header.<br>2. Click it again. | Ascending then descending by section count; QA C9 (3) sorts after or before the 2-section classes | planned |
| TC-MST-03-E04 | P2 | Web | Admin | Seeded classes; TC-MST-03-E07 variant done or any class without sections | 1. Click the expand chevron on "Class 1".<br>2. Expand a class without sections. | Class 1 shows tiles "1-A" and "1-B" with status; the empty class shows "No sections found" | planned |
| TC-MST-03-E05 | P3 | Web | Admin | Seeded classes | 1. Click "Columns".<br>2. Untick "Status".<br>3. Untick every remaining column. | Status column disappears; at least one column always stays visible | planned |
| TC-MST-03-E06 | P1 | Web | Admin | No class "QA C9" in 2026-2027 | 1. Click "Add Class & Sections".<br>2. Enter Class Name "QA C9", Class Code "QC9", click "Next".<br>3. Set "From:" A and "To:" C, click "Generate Sections".<br>4. Click "View".<br>5. Click "Submit". | Toast "Generated 3 sections from A to C"; Summary lists A, B, C; toast "Class and sections created successfully!"; row "QA C9" shows "3 sections". Delete it at the end of the run (TC-MST-04-E04) | planned |
| TC-MST-03-E07 | P3 | Web | Admin | None | 1. Click "Add Class & Sections".<br>2. Enter Class Name "QA C10" and leave Class Code empty. | "Next" stays disabled until both name and code are filled | planned |
| TC-MST-03-E08 | P3 | Web | Admin | None | 1. Open the wizard, fill name and code, click "Next".<br>2. Set "From:" D and "To:" A, click "Generate Sections". | Toast "Start letter must come before end letter"; the section list is unchanged | planned |
| TC-MST-03-E09 | P2 | Web | Admin | Seeded class "Class 1" | 1. Open the wizard with Class Name "Class 1", Class Code "QX1".<br>2. Generate A to B, click "View", click "Submit". | Toast starts "Failed to create class and sections:" with the duplicate reason; no second "Class 1" row (the dialog closes, see Known gaps) | planned |
| TC-MST-03-E10 | P3 | Web | Admin | Seeded classes | 1. Click "Export" > "Export to CSV". | `classes_sections_data.csv` downloads with headers of the visible columns; Sections cells list names joined with `;` | planned |
| TC-MST-03-E11 | P2 | Web | Teacher | Seeded classes | 1. Sign in as Teacher.<br>2. Open Masters > Classes and Sections. | List, "Columns" and "Export" visible; no "Add Class & Sections"; no Add Section, Edit Class or Delete Class icons | planned |
| TC-MST-03-E12 | P1 | Mobile | Admin | Seeded classes | 1. Sign in as Admin (qa_manual).<br>2. Open Home > Masters > Classes and Sections.<br>3. Type "2-A" in "Search classes or sections...".<br>4. Tap the chevron on the card. | "8 classes" before the search; only "Class 2" remains; expanding shows sections 2-A and 2-B with badges | planned |
| TC-MST-03-E13 | P1 | Mobile | Admin | No class "QA C8" | 1. Tap the header Add icon.<br>2. Enter "QA C8" and "QC8", tap "Next".<br>3. Set From A, To B, tap "Generate Sections", tap "View".<br>4. Tap "Submit". | Toast "Sections Generated"; then toast "Class and sections created successfully"; card "QA C8" with "2 sections". Cleanup: delete the class | planned |
| TC-MST-03-E14 | P3 | Mobile | Admin | None | 1. Tap the header Add icon.<br>2. Leave "Class Name *" empty, enter a code, tap "Next". | Toast "Validation - Class name is required" (or "Next" stays disabled); wizard stays on step 1 | planned |
| TC-MST-03-E15 | P3 | Mobile | Admin | Seeded classes | 1. Tap "Columns", untick "Status", close.<br>2. Tap "Export" > "Export to Excel". | Status badges hidden on the cards; `classes_sections_data.xls` downloads on the web build | planned |
| TC-MST-03-E16 | P2 | Mobile | Student | Seeded student Advik Mehta (login 002) and parent venkat.raju@example.com | 1. Sign in as the student and check Home.<br>2. Repeat as the parent. | No "Masters" card on Home for either role | planned |

---

## F04 Edit and delete a class

**Purpose.** An admin renames, recodes, describes or deactivates a class, or removes a class that is not used anywhere.

**Roles and permissions.** Edit: `classes:update` (Edit Class icon). Delete: `classes:delete` (Delete Class icon). Only Admin holds both. Staff, Teacher, Student and Parent see no icons.

**Preconditions.** A class exists (F03). To delete successfully the class and its sections must not be referenced by admissions, fee class mappings, fee student mappings, class-subject mappings or section timetables.

**Steps, web.**
1. Masters > Classes and Sections. On a class row click the Edit icon (title "Edit Class"). Dialog "Edit Class": Class Name, Class Code, Description, Active ("Class is active"). Buttons "Cancel" and "Update Class" ("Updating..."). Empty name or code: toast "Class name is required" or "Class code is required". Success: toast "Class and sections updated successfully!". Failure: toast "Failed to update class and sections: <reason>".
2. Click the Delete icon (title "Delete Class"). Dialog "Confirm Deletion": "Are you sure you want to delete class "<name>"?", then, when the class has sections, the warning "This class has N sections. Deletion will fail if any section or class has linked student admissions, fee mappings, or subject mappings. Deactivate instead if records exist.", then "This action cannot be undone." Buttons "Cancel" and "Delete" ("Deleting..."). Success: toast "Class and sections deleted successfully!". Failure: toast "Failed to delete class and sections: <reason>".

**Steps, mobile.**
1. Home > Masters > Classes and Sections. On a class card tap the Edit icon: modal "Edit Class" (Class Name * "e.g., Class 1", Class Code "e.g., C1", Description "Optional description...", Active "Class is active"), buttons "Cancel" and "Update Class". Toast "Class updated successfully".
2. Tap the Delete icon: confirm "Delete Class" ("Delete "<name>"? This will also delete all associated sections. This action cannot be undone."). Toast "Class deleted successfully"; failure toast "Delete Failed" with the reason.

**Expected results.** Edited fields are saved and sections are untouched. A deleted class and all its sections are hard-deleted. A deactivated class disappears from the active class dropdown but remains in the full list.

**API endpoints.** Prefix `/api/v1/masters/class_sections`.
- `PUT /{class_id}` body `{name?, short_code?, description?, is_active?, academic_year_id, sections?}` -> 200 `{message:"Class and sections updated successfully"}`.
- `DELETE /{class_id}` -> 204 (no body).

**Rules and validations.**
1. `academic_year_id` has no default in `ClassUpdate`: it must be present in the body (it may be sent as the existing year id). Omitting it is a 422; sending `null` fails the database NOT NULL rule with 400.
2. Never send `sections` on a class update. When `sections` is present the service deletes every section of the class and inserts new rows with new ids, which breaks references or fails on the foreign key. Edit sections one at a time (F05).
3. `PUT` applies only fields that were sent (`exclude_unset`).
4. Class delete is refused (400) when any of these reference it: admissions on the class (`admitted_class_id` or `current_class_id`), fee class mappings, fee student mappings, class-subject mappings, or, for its sections, admissions, fee student mappings or timetables. Message: `Cannot delete class '<name>' because it is being used by N record(s): ...` with counts per kind (`section-related record(s)` for the section checks).
5. When no dependency exists the sections are deleted first, then the class; class and sections caches are cleared.
6. The web update goes through `PUT /{id}` without `sections`; the web never sends `sections` on edit.

**Error and edge cases.**
- Unknown class id on `PUT`: 400 `Error fetching classes with sections: 404: Class not found` (the service wraps all errors; message text is misleading). On `DELETE`: 404.
- Duplicate class name in the target academic year on `PUT`: 400 `Class '<name>' already exists for this academic year`.
- Class in use: 400 with the used-by message; nothing is deleted.
- `short_code` longer than 10 characters: 400.
- Roles without update or delete get 403 on the API; the UI hides the icons.

**Unit-testable logic.**
- `ClassUpdate` schema: `academic_year_id` required, all others optional; `sections` optional.
- `update_class_with_sections` with a fake session: only sent fields set; with `sections` present delete then add are executed (documents the destructive path).
- `delete_class_with_sections` dependency summing and message formatting with fake counts; no dependency path deletes sections then class.
- Web `EditClassModal` validation (name and code required) and payload shape (no `sections` key).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-04-U01 | [backend] `ClassUpdate` without `academic_year_id` | Validation error (field required) | passing |
| TC-MST-04-U02 | [backend] `ClassUpdate(academic_year_id=None)` | Valid; field is None; other fields unset | passing |
| TC-MST-04-U03 | [backend] `update_class_with_sections` with `exclude_unset` payload `{name:"X", academic_year_id}` | Only `name` and `academic_year_id` set on the model; no section statements | passing |
| TC-MST-04-U04 | [backend] Same with `sections=[{name:"A"}]` | A DELETE of the class sections and one new section add are issued | passing |
| TC-MST-04-U05 | [backend] `delete_class_with_sections` fake counts: admissions 1, subject mappings 2, section timetables 1 | 400 detail `... being used by 4 record(s): 1 student admission(s), 2 subject mapping(s), 1 section-related record(s)` | passing |
| TC-MST-04-U06 | [backend] `delete_class_with_sections` with all counts 0 | Sections deleted, class deleted, one commit, caches invalidated | passing |
| TC-MST-04-U07 | [web] `EditClassModal` submit with empty code | Toast "Class code is required"; `onSubmit` not called | blocked: needs the validation helper exported from web/src/components/masters/classesandsections/EditClassModal.tsx |
| TC-MST-04-U08 | [web] `EditClassModal` submit valid | `onSubmit(classId, {name, short_code, description, is_active, academic_year_id})` with no `sections` | blocked: needs the payload builder exported from web/src/components/masters/classesandsections/EditClassModal.tsx |
| TC-MST-04-A01 | Admin `PUT /{id}` `{name:"QA-C1-R", academic_year_id:<same>}` | 200 `{message:"Class and sections updated successfully"}`; GET shows new name and unchanged sections | passing |
| TC-MST-04-A02 | `PUT /{id}` `{is_active:false, academic_year_id}` | 200; class absent from `GET /dropdown`; still in `GET /read_all` | passing |
| TC-MST-04-A03 | `PUT /{id}` omitting `academic_year_id` | 422 | passing |
| TC-MST-04-A04 | `PUT /{id}` with `academic_year_id:null` | 400 (database NOT NULL) | passing |
| TC-MST-04-A05 | `PUT /{id}` renaming to another class's name | 400 | passing |
| TC-MST-04-A06 | `PUT /{id}` with `sections:[{name:"Z"}]` on a class with no dependants | 200; sections replaced and section ids differ from before (destructive behaviour) | passing |
| TC-MST-04-A07 | `PUT /{id}` with `sections` on a class whose section has a class-subject mapping | 400; original section ids and the mapping still exist | passing |
| TC-MST-04-A08 | `PUT /{random uuid}` | 404 detail `Class not found` | passing |
| TC-MST-04-A09 | `DELETE /{id}` on a class with 2 sections and no references | 204; class and both sections gone (`GET /by_class_id/{id}` and `GET /sections/{sid}` return 404) | passing |
| TC-MST-04-A10 | `DELETE /{id}` on a class with a class-subject mapping | 400 detail contains `being used by 1 record(s): 1 subject mapping(s)`; class intact | passing |
| TC-MST-04-A11 | `DELETE /{id}` on a class whose section has a timetable | 400 detail contains `section-related record(s)`; after `DELETE /students/timetable/frontend/{section}` the delete succeeds | passing |
| TC-MST-04-A12 | `DELETE /{random uuid}` | 404 | passing |
| TC-MST-04-A13 | Write matrix: PUT and DELETE as Staff, Teacher, Student, Parent | 403 for each; Admin 200 and 204 | passing |
| TC-MST-04-A14 | No Authorization header on PUT and DELETE | 401 | passing |
| TC-MST-04-A15 | Tenant isolation: tenant B token on `PUT` and `DELETE` of tenant A's class | PUT 404; DELETE 404; the row is unchanged | passing |
| TC-MST-04-A16 | Delete a class, then `GET /dropdown` and `/class-list` immediately | Class absent (cache invalidated by delete) | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-04-E01 | P1 | Web | Admin | TC-MST-03-E06 done (QA C9) | 1. Click "Edit Class" on "QA C9".<br>2. Change Class Name to "QA C9 R".<br>3. Click "Update Class". | Toast "Class and sections updated successfully!"; row shows "QA C9 R"; still "3 sections" | planned |
| TC-MST-04-E02 | P3 | Web | Admin | TC-MST-03-E06 done | 1. Click "Edit Class" on the QA class.<br>2. Clear "Class Code".<br>3. Click "Update Class". | Submit blocked by the required field or toast "Class code is required"; dialog stays open; no request | planned |
| TC-MST-04-E03 | P2 | Web | Admin | TC-MST-03-E06 done | 1. Click "Edit Class" on the QA class.<br>2. Untick "Class is active", click "Update Class".<br>3. Open Timetable and open "Select Class". | Status badge shows inactive; the QA class is not offered in "Select Class". Cleanup: tick Active again | planned |
| TC-MST-04-E04 | P2 | Web | Admin | QA class from TC-MST-03-E06 with no mappings left (TC-MST-09-E06 cleanup done) | 1. Click "Delete Class" on the QA class.<br>2. Read the dialog.<br>3. Click "Delete". | "Confirm Deletion" shows "This class has 3 sections. Deletion will fail if ..."; toast "Class and sections deleted successfully!"; row gone | planned |
| TC-MST-04-E05 | P2 | Web | Admin | QA class with a subject mapping (TC-MST-10-E01 done) | 1. Click "Delete Class" on the QA class.<br>2. Click "Delete". | Toast "Failed to delete class and sections: Cannot delete class 'QA C9' because it is being used by N record(s): ... subject mapping(s)"; row remains | planned |
| TC-MST-04-E06 | P3 | Web | Admin | Seeded class "Class 1" | 1. Click "Delete Class" on "Class 1".<br>2. Click "Cancel". | Dialog closes; nothing deleted | planned |
| TC-MST-04-E07 | P1 | Mobile | Admin | TC-MST-03-E13 done (QA C8) | 1. Tap the Edit icon on "QA C8".<br>2. Change "Class Name *" to "QA C8 R".<br>3. Tap "Update Class". | Toast "Class updated successfully"; card shows "QA C8 R" | planned |
| TC-MST-04-E08 | P2 | Mobile | Admin | QA C8 with no mappings | 1. Tap the Delete icon on the QA class.<br>2. In "Delete Class" tap "Delete". | Confirm text "Delete "QA C8 R"? This will also delete all associated sections. This action cannot be undone."; toast "Class deleted successfully"; card gone | planned |
| TC-MST-04-E09 | P2 | Mobile | Admin | QA class with a subject mapping (TC-MST-10-E09 done) | 1. Tap the Delete icon on that class.<br>2. Tap "Delete". | Toast "Delete Failed" with the used-by message; card remains | planned |
| TC-MST-04-E10 | P2 | Web | Teacher | Seeded classes | 1. Sign in as Teacher.<br>2. Open Masters > Classes and Sections and expand "Class 1". | No "Edit Class" or "Delete Class" icons on rows; no section icons | planned |
| TC-MST-04-E11 | P2 | Mobile | Teacher | Seeded classes | 1. Sign in as Teacher.<br>2. Open Home > Masters > Classes and Sections and expand "Class 1". | No Add, Edit or Delete icons on cards or section rows | planned |

---

## F05 Add, edit and delete sections

**Purpose.** An admin adds sections to an existing class, renames or deactivates a section, or removes an unused section.

**Roles and permissions.** Add: `sections:create`. Edit: `classes:update` on the API (the web Edit Section button checks `sections:update`; the mobile Edit icon checks `classes:update`). Delete: `classes:delete` on the API (the web button checks `sections:delete`; mobile checks `classes:delete`). Read one section: `classes:read`. The default Admin grant has `sections:create` only (Known gaps), so on web a default Admin sees the "Add Section" icon but no section Edit or Delete icons; on mobile the Admin sees all three.

**Preconditions.** A class exists (F03).

**Steps, web.**
1. Masters > Classes and Sections. Click the Plus icon on a class row (title "Add Section"). Dialog "Add Sections to <class>": "Quick Add Alphabetically" with "From:" (A) and "To:" (D) and "Generate" (replaces the list, toast "Generated N sections"), the hint "Creates sections A-D (e.g., A, B, C, D)", then "Sections": one box per row (placeholder "Section name (e.g., A)", "(e.g., B)", ...) with "Add row" (+) and "Remove row" (x) buttons, and "Total: n section(s)". Buttons "Cancel" and "Add N Section(s)" (disabled while every box is empty; "Adding..." while pending). Names that already exist in the class (case-insensitive, trimmed) are skipped: all duplicates: error toast "Sections already exist: A, B" (singular "Section already exist: A" for one name), nothing is sent; some duplicates: warning "Skipped duplicate sections: ..." (singular "Skipped duplicate section: A") and the rest are sent. Success toast "3 sections added successfully!" ("1 section added successfully!" for one); failure "Failed to add sections: <reason>".
2. Expand the class row; on a section tile click Edit (title "Edit Section", shown only with `sections:update`). Dialog "Edit Section" with "Class: <class>", field "Section Name" (placeholder "e.g., A, B, C") and "Section is active"; buttons "Cancel" and "Update Section" ("Saving..."). Empty name: toast "Section name is required". Success toast "Section updated successfully!".
3. Click Delete (title "Delete Section", shown only with `sections:delete`): dialog "Confirm Deletion", "Are you sure you want to delete section "<name>"? This action cannot be undone.", "Delete". Success toast "Section deleted successfully!". Failure toast "Failed to delete section: <reason>".

**Steps, mobile.**
1. Home > Masters > Classes and Sections. The Add icon on a class card (label "Add") opens the modal "Add New Section" ("Class: <class>", "Section Name *" placeholder "e.g., A, B, C", "Section is active", buttons "Cancel" and "Add Section"). Empty name: toast "Validation - Section name is required". Note: the add call is rejected by the API today (Known gaps), so the result is an error toast "Create Failed" with the 422 reason.
2. Expand the card; the Edit icon on a section row opens "Edit Section" with "Update Section"; toast "Section updated successfully". Delete icon: confirm "Delete Section" ("Delete section "<name>"? This action cannot be undone.", button "Delete"); toast "Section deleted successfully"; failure toast "Delete Failed" with the reason.

**Expected results.** New sections belong to the chosen class and are active unless unticked; edits change only the sent fields; a deleted section row is removed (hard delete). Existing sections keep their ids.

**API endpoints.** Prefix `/api/v1/masters/class_sections`.
- `POST /{class_id}/sections` body is a JSON array `[{name, description?, is_active=true}]` -> 201 `[SectionOut]`.
- `GET /sections/{section_id}` -> `SectionOut`.
- `PUT /sections/{section_id}` body `{id, name?, description?, is_active?}` -> `SectionOut`.
- `DELETE /sections/{section_id}` -> 200 `{message:"Section deleted successfully"}`.

**Rules and validations.**
1. Add takes a list; a single object is a 422. An empty list returns 201 `[]`.
2. Section `name` is required, at most 50 characters and unique within the class; `description` at most 50.
3. `SectionUpdate.id` has no default and must be present in the body (null is allowed); the endpoint ignores it. Sent `null` values are skipped by the service, so a field cannot be cleared to null.
4. Delete is a hard delete; if admissions, fee mappings, class-subject mappings or a timetable reference the section the database refuses and the API returns 400 `Cannot delete this section because it is referenced by other records (...). Deactivate it instead.`
5. Adding sections clears the sections dropdown cache. Updating or deleting a section does not, so dropdowns can be stale for up to 5 minutes (F15).
6. Only the paths `/sections/{id}` exist for single-section calls; `/{class_id}/sections/{section_id}` returns 404 or 405.

**Error and edge cases.**
- Unknown class on add: 404 `Class not found`. Duplicate name (existing or inside the payload): 400 `Error adding sections: ...`.
- Unknown section: `GET`, `PUT` and `DELETE` return 404.
- Renaming to a name already used in the same class: 400 `A section with this name already exists in the class`.
- Web add dialog strips duplicates client-side; mobile sends a single object and fails validation.

**Unit-testable logic.**
- `SectionCreate` and `SectionUpdate` schemas (`id` required but nullable; `name` max handled by DB).
- `add_sections_to_class`: not found raises 404; each dict becomes a Section with `is_active` default True; empty list returns `[]`.
- `update_section` ignores None values; `delete_section` FK error message mapping (message contains `foreign key` or `violates` produces the 400 text).
- Web `handleAddSections` duplicate filter (case-insensitive, trimmed) and the generator.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-05-U01 | [backend] `SectionUpdate` body without `id` | Validation error for `id` | passing |
| TC-MST-05-U02 | [backend] `SectionUpdate(id=None, name="B")` | Valid | passing |
| TC-MST-05-U03 | [backend] `add_sections_to_class` with fake session, class missing | HTTPException 404 `Class not found` | passing |
| TC-MST-05-U04 | [backend] `add_sections_to_class(class, [])` | Returns `[]` after commit; no section added | passing |
| TC-MST-05-U05 | [backend] `update_section` with `{name:None, is_active:False}` | Only `is_active` changes; name untouched | passing |
| TC-MST-05-U06 | [backend] `delete_section` when the commit raises an error containing `violates foreign key` | HTTPException 400 with the `Deactivate it instead` text | passing |
| TC-MST-05-U07 | [web] `handleAddSections` with existing `a, B` and new `A, c` | `A` reported duplicate, only `c` sent | blocked: needs handleAddSections duplicate logic exported from web/src/pages/masters/classesandsections.tsx |
| TC-MST-05-A01 | Admin `POST /{class}/sections` `[{name:"C"},{name:"D"}]` | 201 two `SectionOut` with `class_id` of the class, `is_active:true` | passing |
| TC-MST-05-A02 | POST `[]` | 201 `[]` | passing |
| TC-MST-05-A03 | POST a single object `{name:"E"}` instead of a list | 422 | passing |
| TC-MST-05-A04 | POST a name that already exists in the class; then the same name twice in one payload | 400 `Error adding sections: ...` each time; no partial rows | passing |
| TC-MST-05-A05 | POST to a random class id | 404 `Class not found` | passing |
| TC-MST-05-A06 | POST name of 50 and 51 characters | 50: 201. 51: 400 | passing |
| TC-MST-05-A07 | `GET /sections/{id}` | 200 `SectionOut` with `created_at`, `updated_at`, `class_id` | passing |
| TC-MST-05-A08 | `GET /sections/{random uuid}` | 404 detail `Section not found` | passing |
| TC-MST-05-A09 | `PUT /sections/{id}` `{id:null, name:"A2", is_active:false}` | 200; name and flag changed | passing |
| TC-MST-05-A10 | `PUT /sections/{id}` without `id` in body | 422 | passing |
| TC-MST-05-A11 | `PUT /sections/{id}` `{id:null, description:null}` after setting a description | 200; description unchanged (null ignored) | passing |
| TC-MST-05-A12 | `PUT /sections/{id}` renaming to a sibling's name | 400 `A section with this name already exists in the class` | passing |
| TC-MST-05-A13 | `PUT /sections/{random uuid}` | 404 detail `Section not found` | passing |
| TC-MST-05-A14 | `DELETE /sections/{id}` for an unreferenced section | 200 `{message:"Section deleted successfully"}`; `GET` then 404 | passing |
| TC-MST-05-A15 | `DELETE /sections/{id}` for a section with a class-subject mapping | 400 detail starts `Cannot delete this section because it is referenced`; section intact | passing |
| TC-MST-05-A16 | `DELETE /sections/{random uuid}` | 404 | passing |
| TC-MST-05-A17 | `PUT` or `DELETE` on `/{class_id}/sections/{section_id}` | 404 or 405 (path does not exist) | passing |
| TC-MST-05-A18 | Role matrix on add: Staff, Teacher, Student, Parent `POST /{class}/sections` | 403 each; Admin 201 | passing |
| TC-MST-05-A19 | Role matrix on `GET /sections/{id}`: all five roles | 200 (needs `classes:read`) | passing |
| TC-MST-05-A20 | Role matrix on `PUT` and `DELETE /sections/{id}`: Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-MST-05-A21 | No Authorization header on all four endpoints | 401 | passing |
| TC-MST-05-A22 | Tenant isolation: tenant B token on tenant A's section (GET, PUT, DELETE) | GET, PUT and DELETE 404; row untouched; POST to tenant A's class id with B token returns 404 | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-05-E01 | P1 | Web | Admin | TC-MST-03-E06 done (QA C9 with A, B, C) | 1. Click "Add Section" on "QA C9".<br>2. Set "From:" D, "To:" E, click "Generate".<br>3. Click "Add 2 Section(s)". | Toast "Generated 2 sections"; toast "2 sections added successfully!"; row shows "5 sections" | planned |
| TC-MST-05-E02 | P2 | Web | Admin | QA C9 with A and B | 1. Click "Add Section" on "QA C9".<br>2. Type "A" in the first box, click "Add row", type "b".<br>3. Click "Add 2 Section(s)". | Error toast "Sections already exist: A, b"; no request sent | planned |
| TC-MST-05-E03 | P2 | Web | Admin | QA C9 with A | 1. Click "Add Section" on "QA C9".<br>2. Enter "A" and, in a new row, "F".<br>3. Click "Add 2 Section(s)". | Warning "Skipped duplicate section: A"; toast "1 section added successfully!"; F added | planned |
| TC-MST-05-E04 | P2 | Web | Admin | QA C9 with section A | 1. Expand "QA C9".<br>2. Click "Edit Section" on A, rename to "A2", untick "Section is active".<br>3. Click "Update Section". | Toast "Section updated successfully!"; tile shows A2 inactive | blocked: default Admin lacks sections:update, so the web Edit Section icon is hidden (Known gaps 4) |
| TC-MST-05-E05 | P3 | Web | Admin | QA C9 | 1. Click "Edit Section" on a section.<br>2. Clear "Section Name", click "Update Section". | Toast "Section name is required" | blocked: default Admin lacks sections:update (Known gaps 4) |
| TC-MST-05-E06 | P2 | Web | Admin | QA C9 with an unreferenced section | 1. Click "Delete Section" on it.<br>2. Click "Delete". | Toast "Section deleted successfully!"; tile gone | blocked: default Admin lacks sections:delete, so the icon is hidden (Known gaps 4) |
| TC-MST-05-E07 | P3 | Web | Admin | QA C9 section with a mapping | 1. Click "Delete Section" on it.<br>2. Click "Delete". | Toast "Failed to delete section: Cannot delete this section ... Deactivate it instead." | blocked: default Admin lacks sections:delete (Known gaps 4) |
| TC-MST-05-E08 | P2 | Web | Admin | Default-seeded Admin role; seeded "Class 1" | 1. Open Masters > Classes and Sections.<br>2. Expand "Class 1". | Tiles 1-A and 1-B show no Edit Section or Delete Section icons, while the class row shows "Add Section" (records Known gaps 4) | planned |
| TC-MST-05-E09 | P1 | Mobile | Admin | TC-MST-03-E13 done (QA C8 with A, B) | 1. Expand "QA C8".<br>2. Tap Edit on section A, change "Section Name *" to "A2".<br>3. Tap "Update Section". | Toast "Section updated successfully"; row shows A2 | planned |
| TC-MST-05-E10 | P2 | Mobile | Admin | QA C8 with an unreferenced section | 1. Tap Delete on that section row.<br>2. In "Delete Section" tap "Delete". | Toast "Section deleted successfully"; row gone | planned |
| TC-MST-05-E11 | P2 | Mobile | Admin | QA C8 | 1. Tap the Add icon on the "QA C8" card.<br>2. Enter "G" in "Section Name *".<br>3. Tap "Add Section". | Section G is added and listed | blocked: mobile add-section sends a single object and the API returns 422 "Create Failed" (Known gaps 6) |
| TC-MST-05-E12 | P3 | Mobile | Admin | Any class | 1. Tap the Add icon on a class card.<br>2. Leave "Section Name *" empty, tap "Add Section". | Toast "Validation - Section name is required"; modal "Add New Section" stays | planned |
| TC-MST-05-E13 | P2 | Web | Teacher | Seeded classes | 1. Sign in as Teacher.<br>2. Expand "Class 1". | No "Add Section", "Edit Section" or "Delete Section" icons | planned |

---

## F06 Class and section lookups and dropdowns

**Purpose.** Other screens (timetable, class-subject mappings, fees, exams, admissions) pick a class then a section. These read-only endpoints feed those pickers.

**Roles and permissions.** All endpoints below need `classes:list`. Admin, Staff, Teacher, Student and Parent all hold it. There is no screen of its own; the pickers appear on the timetable editor (TTC), the class-subject mapping modal (F10) and other modules.

**Preconditions.** Classes and sections exist (F03).

**Steps, web.** Example screen: sidebar "Timetable" (`/TimeTable`, page "Time Table Management") shows "Select Class" and "Select Section" with the hint "Please select a class and section to view or create a timetable". The shared `ClassesDropdown` calls `GET /dropdown`; `SectionsByClassDropdown` calls `GET /by_class_id/{class_id}/sections` through the `useSectionsByClassId` hook. Choosing a class loads that class's sections; changing the class clears the section.

**Steps, mobile.** The class list picker uses `GET /class-list`, sections use `GET /by_class_id/{id}/sections`; the pickers are custom dropdowns that need non-empty labels.

**Expected results.** The dropdown lists only active classes (and only active sections for a class) ordered by name; list endpoints return every row.

**API endpoints.** Prefix `/api/v1/masters/class_sections`.
- `GET /dropdown?active_only=true` -> `[{id, name}]` ordered by name.
- `GET /by_class_id/{class_id}/sections` -> active sections `[{id, name}]` ordered by name.
- `GET /class-list` -> `[ClassOut]` all classes. `GET /section-list` -> `[SectionOut]` all sections.
- `GET /class-section-list` -> `[{section_id, class_section_name}]`, label `<class name> - <section name>`, ordered by class id then section name.
- `GET /sections-by-class-name?class_name=` -> `[SectionOut]` of the first class with that name.
- `GET /by-class-section?class_name=&section_name=` -> students whose current class and section match (Students module data).

**Rules and validations.**
1. `dropdown` filters `is_active` on the class; the sections dropdown filters `is_active` on the section only.
2. `class-list`, `section-list`, `dropdown`, `by_class_id/{id}/sections` and `sections-by-class-name` are cached for 5 minutes per tenant and arguments; class create, update and delete and section add clear them, section update and delete do not.
3. `class_name` is required for `sections-by-class-name`; unknown class returns 404 `Class not found`. `by-class-section` needs both names; unknown section returns 404 `Section not found for given class`.
4. An unknown `class_id` in `by_class_id/{id}/sections` returns `[]` (200).
5. Dropdown rate limit is 100 per minute.

**Error and edge cases.**
- Inactive classes are missing from `dropdown` but present in `class-list`.
- Mobile dropdown search crashes if an option label is undefined; clients must map `label: item.name || ''`.
- Cached results can lag direct database changes and section renames by up to 5 minutes.

**Unit-testable logic.**
- `cache_dropdown` key construction including tenant id and arguments; `invalidate_cache("dropdown","classes")` and `("dropdown","sections")` matching keys of `get_classes_dropdown`, `get_all_classes_data`, `get_sections_by_class_id`, `get_all_sections_data`.
- `get_class_section_list` label formatting with fake rows.
- Mobile and web option mappers (`label: x.name || ''`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-06-U01 | [backend] `get_class_section_list` with fake sections of class `Class 1` named A and B | Labels `Class 1 - A`, `Class 1 - B` with section ids | passing |
| TC-MST-06-U02 | [backend] `cache_dropdown` called twice with the same args and fake session tenant | Second call returns the cached object; a different tenant id misses | passing |
| TC-MST-06-U03 | [backend] `invalidate_cache("dropdown","classes")` after caching `get_classes_dropdown` and `get_subjects_dropdown` | Class keys removed; subject keys kept | passing |
| TC-MST-06-U04 | [mobile] Option mapper with `{name: undefined}` | Produces `label ''`, never undefined | blocked: no option mapper exists in mobile code; mobile/src/api/masters.ts returns dropdown data unchanged |
| TC-MST-06-A01 | `GET /dropdown` with one active and one inactive class | Only the active class `{id, name}`; ordered by name | passing |
| TC-MST-06-A02 | `GET /dropdown?active_only=false` | Both classes | passing |
| TC-MST-06-A03 | `GET /by_class_id/{id}/sections` with sections A (active), B (inactive) | `[A]` only, ordered by name | passing |
| TC-MST-06-A04 | `GET /by_class_id/{random uuid}/sections` | 200 `[]` | passing |
| TC-MST-06-A05 | `GET /class-list` | All classes including inactive, each with `id,name,short_code,is_active,academic_year_id,created_at,updated_at` | passing |
| TC-MST-06-A06 | `GET /section-list` | All sections of all classes with `class_id` | passing |
| TC-MST-06-A07 | `GET /class-section-list` | Items `{section_id, class_section_name:"<class> - <section>"}` | passing |
| TC-MST-06-A08 | `GET /sections-by-class-name?class_name=<name>`; unknown name; missing param | Sections list; 404 `Class not found`; 422 | passing |
| TC-MST-06-A09 | `GET /by-class-section?class_name=&section_name=` valid; unknown class; unknown section | 200 student list (possibly empty); 404 `Class not found`; 404 `Section not found for given class` | passing |
| TC-MST-06-A10 | Role matrix: all seven GET endpoints as Admin, Staff, Teacher, Student, Parent | 200 for all five roles | passing |
| TC-MST-06-A11 | No Authorization header on each endpoint | 401 | passing |
| TC-MST-06-A12 | Tenant isolation: tenant B's `dropdown`, `class-list`, `section-list`, `class-section-list` | Contain none of tenant A's classes or sections | passing |
| TC-MST-06-A13 | Create a class then immediately call `dropdown` and `class-list` | New class present (create invalidates) | passing |
| TC-MST-06-A14 | `PUT /sections/{id}` rename, then `GET /by_class_id/{class}/sections` within 5 minutes | Old name still returned (no invalidation on section update); records current behaviour | passing |
| TC-MST-06-A15 | 101 dropdown calls within a minute (limiter enabled) | The 101st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-06-E01 | P1 | Web | Admin | Seeded classes; one QA class made inactive (TC-MST-04-E03 step 2) | 1. Open sidebar "Timetable".<br>2. Open "Select Class". | Only active classes, ordered by name; the inactive QA class is absent | planned |
| TC-MST-06-E02 | P2 | Web | Admin | Seeded classes | 1. On Timetable check "Select Section" before choosing a class.<br>2. Choose "Class 1" in "Select Class".<br>3. Open "Select Section". | Section is disabled until a class is chosen; then lists 1-A and 1-B | planned |
| TC-MST-06-E03 | P3 | Web | Admin | Seeded classes | 1. Choose "Class 1" and "1-A".<br>2. Change the class to "Class 2". | The section selection clears | planned |
| TC-MST-06-E04 | P2 | Mobile | Admin | Seeded classes | 1. Open Home > Masters > Timetable Management (or `/masters/timetable`).<br>2. Pick "Class 1", then look at the section choices. | The class list, then sections 1-A and 1-B of the chosen class | planned |

---

## F07 Subject categories

**Purpose.** An admin keeps a flat, tenant-wide list of category names (for example Languages, Sciences) that subjects are grouped under.

**Roles and permissions.** Create: `subject_categories:create`. Edit: `subject_categories:update`. Delete: `subject_categories:delete`. List and dropdown: `subject_categories:list`. Single read: `subject_categories:read`. Admin has all; Staff and Teacher read and list; Student and Parent have none. Menu: Masters > Subject Categories (web `/masters/subjectcategories`), Home > Masters > Subject Categories (mobile).

**Preconditions.** None.

**Steps, web.**
1. Masters > Subject Categories. Card "Subject Categories" with column Name, S.No. and Actions; buttons: column selector "Filters", "Export" and "Add Subject Categories". Search "Search..." (filters only the rows of the current page), sort by Name, "Previous"/"Next" and "Rows per page" (default 5, server paged).
2. Add: click "Add Subject Categories", dialog "Add Subject Categories", field "Category Name" (required), buttons "Cancel" and "Add Subject Categories". Toast "Subject category created successfully!". Failure toast "Failed to create subject category: <reason>".
3. Edit: Edit icon, change Name inline, green check. Toast "Subject category updated successfully!".
4. Delete: trash icon, dialog "Delete Row?", Delete. Toast "Subject category deleted successfully!". Failure toast "Failed to delete subject category: Cannot delete category '<name>' because it is being used by N subject(s)...".
5. Export > "Export to CSV", "Export to Excel", "Download Data" (`subject_categories_data.*`). Categories can also be created inline from the subject form (F08).

**Steps, mobile.**
1. Home > Masters > Subject Categories. Header "Subject Categories" with "n categories", "Export", "Add Subject Categories" and "Filters". Search "Search categories...".
2. Add or Edit: modal "Add Subject Categories" with field "Category Name *" (placeholder "Enter category name"), "Cancel" and the save button ("Add Subject Categories" when adding). Empty name: toast "Error - Category name is required". Toasts "Category Created - Subject category created successfully.", "Category Updated", "Category Deleted"; failures "Create Failed", "Update Failed", "Delete Failed" with the reason.
3. Delete icon: confirm "Delete Subject Category" ("Are you sure you want to delete "<name>"?"). Export sheet "Export As" with CSV, Excel and Download Data.

**Expected results.** Names are listed alphabetically from the server; a created category is immediately available in the category dropdown; a category used by subjects cannot be deleted.

**API endpoints.**
- `POST /api/v1/masters/subject_categories/categories` `{name}` -> 200 `{id, name}`.
- `GET /categories?skip=0&limit=50` -> `{items:[{id,name}], total_count, has_next}` ordered by name.
- `GET /categories/dropdown` -> `[{id, name}]` ordered by name.
- `GET /categories/{category_id}` -> `{id, name}`.
- `PUT /categories/{category_id}` `{name}` -> `{id, name}`.
- `DELETE /categories/{category_id}` -> 200 `{message:"Subject category deleted successfully"}`.
- Alias: `POST /api/v1/subject-categories` -> 201 and `GET /api/v1/subject-categories` (same body and list as the main routes; no PUT or DELETE).

**Rules and validations.**
1. `name` is required, trimmed, 1 to 100 characters (an empty or whitespace-only name is rejected with 422 on create and update), unique per tenant, compared exactly (case-sensitive: `Science` and `science` are different).
2. List `skip >= 0`, `limit` 1 to 1000 (default 50); outside these bounds 422.
3. Update checks uniqueness only when the name changes; the unchanged name is accepted.
4. Delete is a hard delete, refused with 400 while any subject (any year) uses the category.
5. Create, update and delete clear the categories dropdown cache.
6. `GET /masters/subjects/categories` returns the plain list of `{id, name}` (up to 1000 categories); the dropdown remains the preferred read.

**Error and edge cases.**
- Duplicate create: 400 `Category already exists`. Duplicate rename: 400 `Subject category name '<name>' already exists`.
- Name over 100 characters: 400 `Subject category creation failed: ...`.
- Unknown id: 404 `Subject category with id <id> not found` on get, update and delete.
- Student and Parent get 403 on every category endpoint.
- Web shows the backend reason in the toast; mobile shows it in the error toast.

**Unit-testable logic.**
- `SubjectCategoryCreate` and `SubjectCategoryUpdate` schemas.
- `create_subject_category` duplicate detection (exact match) and `check_subject_category_name_unique` exclusion of the same id.
- `delete_subject_category` in-use message with fake counts; `has_next` arithmetic for the list.
- Web `fetchSubjectCategories` response normalisation (array, `items`, `total_count`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-07-U01 | [backend] `SubjectCategoryCreate` without `name` | Validation error | passing |
| TC-MST-07-U02 | [backend] `create_subject_category` when a fake row with the same name exists | HTTPException 400 `Category already exists` | passing |
| TC-MST-07-U03 | [backend] `check_subject_category_name_unique(name, exclude_id=same id)` | No error when only the same row has that name | passing |
| TC-MST-07-U04 | [backend] `delete_subject_category` with 3 subjects using it | 400 `Cannot delete category '<name>' because it is being used by 3 subject(s)...` | passing |
| TC-MST-07-U05 | [backend] list `has_next` for (0,50,120), (100,50,120) | True, False | passing |
| TC-MST-07-U06 | [web] `fetchSubjectCategories` given a plain array, `{items,total_count}` and `{data,count}` shapes | Each normalised to `{items,total}` | passing |
| TC-MST-07-A01 | Admin `POST /categories` `{name:"QA-Sciences"}` | 200 `{id,name}` | passing |
| TC-MST-07-A02 | Admin `POST /api/v1/subject-categories` `{name:"QA-Arts"}` | 201 `{id,name}` | passing |
| TC-MST-07-A03 | POST an existing name | 400 `Category already exists` | passing |
| TC-MST-07-A04 | POST `QA-Sciences` and `qa-sciences` | Both 200 (case-sensitive) | passing |
| TC-MST-07-A05 | POST name of 100 and 101 characters | 100: 200. 101: 400 `Subject category creation failed` | passing |
| TC-MST-07-A06 | POST `{}` and `{name:123}` | 422 | passing |
| TC-MST-07-A07 | POST `{name:""}` and `{name:"   "}` | 422 | passing |
| TC-MST-07-A08 | With 3 categories: `GET /categories` default, `?skip=0&limit=1`, `?skip=2&limit=1` | Default: 3 items ordered by name, `total_count` 3. Second: 1 item, `has_next` true. Third: 1 item, `has_next` false | passing |
| TC-MST-07-A09 | `GET /categories?limit=0`, `?limit=1001`, `?skip=-1` | 422 each | passing |
| TC-MST-07-A10 | `GET /api/v1/subject-categories?limit=2` | Same shape as the main list | passing |
| TC-MST-07-A11 | `GET /categories/dropdown` | `[{id,name}]` ordered by name; contains a category created moments ago | passing |
| TC-MST-07-A12 | `GET /categories/{id}` valid and random uuid | 200; 404 `Subject category with id ... not found` | passing |
| TC-MST-07-A13 | `PUT /categories/{id}` `{name:"QA-Sciences-2"}` | 200 with new name | passing |
| TC-MST-07-A14 | `PUT` with the unchanged name; with another category's name | 200; 400 `Subject category name '<name>' already exists` | passing |
| TC-MST-07-A15 | `PUT /categories/{random uuid}` | 404 | passing |
| TC-MST-07-A16 | `DELETE /categories/{id}` unused | 200 `{message:"Subject category deleted successfully"}`; GET then 404 | passing |
| TC-MST-07-A17 | `DELETE` a category used by a subject (F08) | 400 detail contains `being used by 1 subject(s)`; category intact | passing |
| TC-MST-07-A18 | `DELETE /categories/{random uuid}` | 404 | passing |
| TC-MST-07-A19 | `GET /masters/subjects/categories` | 200 plain array of `{id, name}` | passing |
| TC-MST-07-A20 | Read matrix: list, dropdown, get as Admin, Staff, Teacher | 200 | passing |
| TC-MST-07-A21 | Read matrix: the same calls as Student and Parent | 403 each (no grant) | passing |
| TC-MST-07-A22 | Write matrix: POST, PUT, DELETE as Staff and Teacher | 403 each; Admin 2xx | passing |
| TC-MST-07-A23 | No Authorization header on all endpoints including the alias | 401 | passing |
| TC-MST-07-A24 | Tenant isolation: category created in tenant A | Absent from tenant B list and dropdown; B can create the same name; GET with B token 404 | passing |
| TC-MST-07-A25 | 31 POSTs within a minute (limiter enabled) | The 31st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-07-E01 | P2 | Web | Admin | Seeded categories Languages, Core Academics, Co-Curricular | 1. Sign in as Admin (qa_manual).<br>2. Open Masters > Subject Categories. | Card "Subject Categories" with column Name, the three seeded rows, "Rows per page" 5, buttons "Filters", "Export", "Add Subject Categories" | planned |
| TC-MST-07-E02 | P1 | Web | Admin | No category "QA Languages" | 1. Click "Add Subject Categories".<br>2. Enter "QA Languages" in "Category Name".<br>3. Click "Add Subject Categories". | Toast "Subject category created successfully!"; row appears | planned |
| TC-MST-07-E03 | P2 | Web | Admin | Seeded category "Languages" | 1. Click "Add Subject Categories".<br>2. Enter "Languages", submit. | Toast "Failed to create subject category: Category already exists" | planned |
| TC-MST-07-E04 | P2 | Web | Admin | TC-MST-07-E02 done | 1. Click the Edit icon on "QA Languages".<br>2. Change the name to "QA Languages 2", press the green check. | Toast "Subject category updated successfully!"; row renamed | planned |
| TC-MST-07-E05 | P2 | Web | Admin | TC-MST-07-E04 done, category unused | 1. Click the trash icon on "QA Languages 2".<br>2. In "Delete Row?" click "Delete". | Toast "Subject category deleted successfully!"; row gone | planned |
| TC-MST-07-E06 | P2 | Web | Admin | Seeded "Languages" used by English, Hindi, Telugu | 1. Click the trash icon on "Languages".<br>2. Click "Delete". | Toast "Failed to delete subject category: Cannot delete category 'Languages' because it is being used by 3 subject(s)..."; row remains | planned |
| TC-MST-07-E07 | P3 | Web | Admin | Seeded categories | 1. Type "Core" in "Search...".<br>2. Click the "Name" header twice.<br>3. Change "Rows per page" to 10. | Filter (current page only), sort order and paging behave as in F01 | planned |
| TC-MST-07-E08 | P3 | Web | Admin | Seeded categories | 1. Click "Export" > "Export to CSV". | `subject_categories_data.csv` downloads with header `Name` | planned |
| TC-MST-07-E09 | P2 | Web | Teacher | Seeded categories | 1. Sign in as Teacher.<br>2. Open Masters > Subject Categories. | Rows and "Export" visible; no add button, no Edit or trash icons | planned |
| TC-MST-07-E10 | P1 | Mobile | Admin | No category "QA Humanities" | 1. Open Home > Masters > Subject Categories, tap "Add Subject Categories".<br>2. Enter "QA Humanities", tap "Add Subject Categories".<br>3. Edit it to "QA Humanities 2" and save.<br>4. Delete it and confirm in "Delete Subject Category". | Toasts "Category Created", "Category Updated", "Category Deleted"; the count updates each time | planned |
| TC-MST-07-E11 | P3 | Mobile | Admin | None | 1. Tap "Add Subject Categories".<br>2. Leave "Category Name *" empty and save. | Toast "Error - Category name is required" | planned |
| TC-MST-07-E12 | P2 | Mobile | Student | Seeded student Advik Mehta (login 002) | 1. Sign in as the student.<br>2. Open `/masters/subjectcategories` by URL. | No Masters card on Home; the screen shows "Error", "Failed to load subject categories data" and "Retry" (403) | planned |

---

## F08 Subjects

**Purpose.** An admin defines the subjects taught in an academic year with a name, an optional short code and a required category.

**Roles and permissions.** Create: `subjects:create`. Edit: `subjects:update`. Delete (deactivate): `subjects:delete`. Lists, paginated list, dropdown, by-year and by-category reads: `subjects:list`. Single read: `subjects:read`. Admin all; Staff, Teacher, Student and Parent hold read and list. The inline category "+" needs `subject_categories:create`. Menu: Masters > Subjects (web `/masters/subjects`), Home > Masters > Subjects (mobile).

**Preconditions.** An academic year (F01) and at least one subject category (F07).

**Steps, web.**
1. Masters > Subjects. Card "Subjects": columns S.No., Name, Category, Short Code, Active, Actions; column selector "Filters", "Export" and "Add Subject". Search "Search...", sortable columns, "Previous"/"Next", "Rows per page" (default 5; paging is client-side over the full list; each page is shown sorted by category name). The list is not filtered by year on web.
2. Add: "Add Subject" opens "Add New Subject": Subject Name (required), Category (required; a category dropdown "Select Category" with a "+" button, tooltip "Create new category", that opens a popover "Create New Category" with "Category Name", "Cancel" and "Create"; the new category is auto-selected), Short Code, Active (default checked). Submit "Add Subject". The subject is created in the selected working year. Toast "Subject created successfully!". Failure toast "Failed to create subject: <reason>".
3. Edit inline: Edit icon, change Name, Category (dropdown plus "+"), Short Code, Active; green check. Toast "Subject updated successfully!".
4. Delete: trash icon, "Delete Row?", Delete. Toast "Subject deleted successfully!" (the subject is deactivated and stays listed as inactive).
5. Export to CSV, Excel or Download Data.

**Steps, mobile.**
1. Home > Masters > Subjects. Header "Subjects" with "n subjects", "Export", "Add Subject"; "Filters" (column toggles, "Select All"); search "Search subjects...". The list is scoped to the working year (`academic_year_id`) and shows name, code, category, a "Practical" line when the stored flag is set, and Active/Inactive badge.
2. Add or Edit: modal "Add New Subject" with "Subject Name *" ("Enter subject name"), "Category" (dropdown "Select Category" plus an "Add" button that opens a category modal with "Category Name *" "Enter category name"), "Short Code" ("Enter short code (optional)"), "Active", "Cancel" and the save button ("Add Subject" when adding). Empty name: toast "Error - Subject name is required". Toasts "Subject Created", "Subject Updated", "Subject Deleted" and "Category Created"; failures "Create Failed", "Update Failed", "Delete Failed" with the reason.
3. Delete icon: confirm "Delete Subject" ("Are you sure you want to delete "<name>"?"). The mobile form does not require a category before submit; the API then rejects it.

**Expected results.** A created subject carries its category object, year and active flag; a deleted subject has `is_active:false` and drops out of default lists, dropdowns and the timetable subject picker.

**API endpoints.** Prefix `/api/v1/masters/subjects`.
- `POST /` `{name, category_id, academic_year_id, short_code?, is_active=true}` -> 200 `SubjectRead` (includes `category:{id,name}`).
- `GET /` query `active_only=true`, `academic_year_id?` -> plain array of up to 1000 subjects (`skip` and `limit` are not accepted).
- `GET /paginated` query `skip=0`, `limit=100`, `active_only=true`, `academic_year_id?` -> `{items, total_count, has_next}`.
- `GET /dropdown` query `active_only=true` -> `[{id,name}]` ordered by name.
- `GET /by-academic-year/{year_id}` -> active subjects of that year.
- `GET /categories/{category_id}/subjects` and `/categories/{category_id}/subjects/dropdown` -> active subjects of a category.
- `GET /{subject_id}` -> `SubjectRead`; `PUT /{subject_id}` partial -> `SubjectRead`; `DELETE /{subject_id}` -> 204 (deactivate).
- `GET /categories` is defective (F07 rule 6).

**Rules and validations.**
1. `name` required (1 to 50 characters; blank or whitespace-only is rejected), `short_code` optional at most 10 characters (both match the columns; longer values are 422 from the schema, and 400 from the service guard), `category_id` required (UUID), `academic_year_id` required.
2. Duplicate name or duplicate short code inside the same academic year: 422 `BUSINESS_RULE_ERROR`. The name check compares the trimmed text, but the stored name is not trimmed.
3. Name and short code are unique per academic year (`tenant_id, academic_year_id, name` in the database, plus the service checks), so the same name can be reused in another year.
4. Update checks name uniqueness in the target year and returns 400 `Subject with name '<name>' already exists for this academic year`; unknown subject on update or delete is 404. Setting `category_id` to null is stored and then breaks every subject response (`category` is required in `SubjectRead`) with 500.
5. `DELETE` is a soft deactivate and is idempotent (second call still 204).
6. `GET /` returns at most 1000 rows; `/paginated` limit must be 1 to 1000 (outside: 400) and `skip` not negative (400).
7. Only create clears the subjects dropdown cache; update and deactivate do not (F15). The mobile `is_practical` and `description` fields are sent but ignored.

**Error and edge cases.**
- Unknown id: `GET` 404 (`Subject not found`), `PUT` 400 `Subject update failed.`, `DELETE` 400 `Subject deactivation failed.`.
- Unknown `category_id` or `academic_year_id` on create: 500 `DATABASE_ERROR` (foreign key).
- Missing `category_id`: 422.
- Student and Parent can read subjects but not create, edit or delete.

**Unit-testable logic.**
- `SubjectCreate` and `SubjectUpdate` schemas; `SubjectRead` requires a category.
- `create_subject` with a fake session: blank name 400, name 101 characters 400, code 21 characters 400, duplicate name 422, duplicate code 422, success returns subject with category loaded and clears the cache.
- `get_all_subjects` validation: `skip < 0` and `limit` 0 or 1001 produce 400; `has_next`.
- `deactivate_subject` sets `is_active=False` and is idempotent.
- Web `fetchSubjects` mapping (`short_code` to `code`, `category` to `subject_category`, `category_id` to `subject_category_id`) and the payload rename to `category_id`; `useSubjectsPaginated` client-side slice and `hasMore`.
- Mobile subject filter by name.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-08-U01 | [backend] `SubjectCreate` without `category_id` | Validation error | passing |
| TC-MST-08-U02 | [backend] `create_subject` name `"   "` | HTTPException 400 detail message `Subject name is required` | passing |
| TC-MST-08-U03 | [backend] `SubjectCreate` with name of 51 characters, code of 11 characters, empty name; `create_subject` guard with the same lengths | Schema: ValidationError each. Service guard: 400 `Subject name cannot exceed 50 characters`; 400 `Subject code cannot exceed 10 characters` | passing |
| TC-MST-08-U04 | [backend] `create_subject` when a fake row has the same trimmed name in the same year | 422 `BUSINESS_RULE_ERROR` rule `unique_subject_name_per_year` | passing |
| TC-MST-08-U05 | [backend] Same for the short code | 422 rule `unique_subject_code_per_year` | passing |
| TC-MST-08-U06 | [backend] `get_all_subjects(skip=-1)`, `(limit=0)`, `(limit=1001)` | Each raises 400 validation error | passing |
| TC-MST-08-U07 | [backend] `deactivate_subject` on an already inactive fake subject | Stays inactive; no error | passing |
| TC-MST-08-U08 | [web] `fetchSubjects` with backend item `{short_code:"MAT", category:{id,name}, category_id}` | `code:"MAT"`, `subject_category:{id,name}`, `subject_category_id` set | passing |
| TC-MST-08-U09 | [web] `createSubject` payload from `{subject_category_id:"c1"}` | Request body has `category_id:"c1"` and no `subject_category_id` | passing |
| TC-MST-08-U10 | [web] `useSubjectsPaginated` with 12 items, page 1, size 5 | Items 6 to 10, `hasMore` true; page 2 returns items 11 to 12, `hasMore` false | passing |
| TC-MST-08-A01 | Admin `POST /masters/subjects/` `{name:"QA-Maths", short_code:"QMA", category_id, academic_year_id}` | 200; body has `category:{id,name}`, `is_active:true` | passing |
| TC-MST-08-A02 | POST the same name in the same year | 422 `detail.error_code` `BUSINESS_RULE_ERROR` | passing |
| TC-MST-08-A03 | POST a different name with the same `short_code` in the same year | 422 `BUSINESS_RULE_ERROR` | passing |
| TC-MST-08-A04 | POST the same name in a second academic year | 200 (name is unique per academic year) | passing |
| TC-MST-08-A05 | POST name `"   "` | 400 `VALIDATION_ERROR` | passing |
| TC-MST-08-A06 | POST name of 50, 51 and 101 characters | 50: 200. 51 and 101: 422 | passing |
| TC-MST-08-A07 | POST `short_code` of 10, 11 and 21 characters | 10: 200. 11 and 21: 422 | passing |
| TC-MST-08-A08 | POST without `category_id`; with a random `category_id`; with a random `academic_year_id` | 422; 500 `DATABASE_ERROR`; 500 `DATABASE_ERROR` | passing |
| TC-MST-08-A09 | `GET /` default with one active and one deactivated subject created by the test | Plain array (not an object) containing the active subject and not the deactivated one | passing |
| TC-MST-08-A10 | `GET /?active_only=false&academic_year_id=<year>` | Both subjects of that year; none from other years | passing |
| TC-MST-08-A11 | `GET /paginated?skip=0&limit=1` then `skip=1&limit=1` with 2 subjects | `total_count` 2, `has_next` true then false | passing |
| TC-MST-08-A12 | `GET /paginated?limit=1001`, `?limit=0`, `?skip=-1` | 400 `VALIDATION_ERROR` each | passing |
| TC-MST-08-A13 | `GET /dropdown`, `GET /by-academic-year/{year}` | `[{id,name}]` ordered by name; active subjects of that year only | passing |
| TC-MST-08-A14 | `GET /categories/{cat}/subjects` and `/subjects/dropdown` | Active subjects of the category (full objects; `{id,name}`) | passing |
| TC-MST-08-A15 | `GET /{id}` valid and random uuid | 200 with category; 404 `NOT_FOUND_ERROR` | passing |
| TC-MST-08-A16 | `PUT /{id}` `{name:"QA-Maths-2", is_active:false}` | 200; name and flag changed; category retained | passing |
| TC-MST-08-A17 | `PUT /{id}` with another subject's name | 400 `Subject update failed.` | passing |
| TC-MST-08-A18 | `PUT /{random uuid}` | 404 | passing |
| TC-MST-08-A19 | `DELETE /{id}` twice | 204 both times; `GET /{id}` shows `is_active:false`; absent from `GET /` and `/dropdown` | passing |
| TC-MST-08-A20 | `DELETE /{random uuid}` | 404 | passing |
| TC-MST-08-A21 | `GET /categories` | 200 plain array of `{id, name}` | passing |
| TC-MST-08-A22 | Read matrix: `GET /`, `/paginated`, `/dropdown`, `/{id}` as all five roles | 200 for all five | passing |
| TC-MST-08-A23 | Write matrix: POST, PUT, DELETE as Staff, Teacher, Student, Parent | 403 each; Admin 2xx | passing |
| TC-MST-08-A24 | No Authorization header on every endpoint | 401 | passing |
| TC-MST-08-A25 | Tenant isolation: subject created in tenant A | Absent from tenant B `GET /`, `/dropdown`; `GET /{id}` with B token 404; B may create the same name | passing |
| TC-MST-08-A26 | Create then immediately `GET /dropdown`; update a subject name then `GET /dropdown` within 5 minutes | New subject present; renamed subject still shows the old name (no invalidation on update) | passing |
| TC-MST-08-A27 | 31 POSTs within a minute (limiter enabled) | The 31st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-08-E01 | P2 | Web | Admin | Seeded 10 subjects | 1. Sign in as Admin (qa_manual).<br>2. Open Masters > Subjects. | Table with Name, Category, Short Code, Active; seeded rows such as English (Languages, ENG); rows of a page grouped by category name | planned |
| TC-MST-08-E02 | P1 | Web | Admin | No subject "QA Physics" in 2026-2027 | 1. Click "Add Subject".<br>2. Enter Subject Name "QA Physics", choose Category "Co-Curricular", Short Code "QPH".<br>3. Click "Add Subject". | Toast "Subject created successfully!"; row appears Active. Note: subjects are only deactivated, so the row stays (inactive) after cleanup | planned |
| TC-MST-08-E03 | P2 | Web | Admin | No category "QA Electives" | 1. Click "Add Subject".<br>2. Click "+" (tooltip "Create new category").<br>3. In "Create New Category" enter "QA Electives", click "Create". | Toast "Subject category created successfully!"; popover closes; "QA Electives" is selected. Cleanup: delete the category if no subject uses it | planned |
| TC-MST-08-E04 | P3 | Web | Admin | None | 1. Click "Add Subject".<br>2. Enter "QA NoCat", leave "Select Category".<br>3. Click "Add Subject". | Request rejected (422); toast starts "Failed to create subject:"; no row added | planned |
| TC-MST-08-E05 | P2 | Web | Admin | Seeded "Mathematics" | 1. Click "Add Subject".<br>2. Enter "Mathematics", category "Core Academics", code "QMX".<br>3. Click "Add Subject". | Toast "Failed to create subject: ..." with the duplicate-name reason; no row added | planned |
| TC-MST-08-E06 | P2 | Web | Admin | TC-MST-08-E02 done | 1. Click the Edit icon on "QA Physics".<br>2. Change name to "QA Physics 2" and code to "QPH2".<br>3. Press the green check. | Toast "Subject updated successfully!"; row updated | planned |
| TC-MST-08-E07 | P2 | Web | Admin | TC-MST-08-E02 done | 1. Click the trash icon on the QA subject.<br>2. Click "Delete" in "Delete Row?". | Toast "Subject deleted successfully!"; the row stays with badge Inactive | planned |
| TC-MST-08-E08 | P3 | Web | Admin | Seeded subjects | 1. Type "Math" in "Search...".<br>2. Click the "Name" header.<br>3. Set "Rows per page" to 10. | Filter, sort and paging behave as in F01 | planned |
| TC-MST-08-E09 | P2 | Web | Teacher | Seeded subjects; seeded student Advik Mehta | 1. Sign in as Teacher, open Masters > Subjects.<br>2. Sign in as the student and check the sidebar. | Teacher: list and "Export" only, no "Add Subject", no Edit or trash icons. Student: no Masters entry | planned |
| TC-MST-08-E10 | P1 | Mobile | Admin | No subject "QA Chem" | 1. Open Home > Masters > Subjects, tap "Add Subject".<br>2. Enter "QA Chem", choose "Core Academics", Short Code "QCH".<br>3. Tap "Add Subject". | Toast "Subject Created"; card shows "Code: QCH" and "Category: Core Academics" | planned |
| TC-MST-08-E11 | P3 | Mobile | Admin | None | 1. Tap "Add Subject".<br>2. Leave "Subject Name *" empty and save. | Toast "Error - Subject name is required" | planned |
| TC-MST-08-E12 | P3 | Mobile | Admin | None | 1. Tap "Add Subject".<br>2. Enter "QA NoCat M", leave "Select Category", save. | Toast "Create Failed" (API rejects the missing category) | planned |
| TC-MST-08-E13 | P2 | Mobile | Admin | No category "QA Arts" | 1. Tap "Add Subject".<br>2. Tap the "Add" button next to Category.<br>3. Enter "QA Arts" in "Category Name *" and save. | Toast "Category Created"; "QA Arts" is offered in the Category dropdown. Cleanup: delete it on Subject Categories | planned |
| TC-MST-08-E14 | P2 | Mobile | Admin | TC-MST-08-E10 done | 1. Tap Edit on "QA Chem", change the code to "QCH2", save.<br>2. Tap Delete on it and confirm "Delete". | Toasts "Subject Updated" then "Subject Deleted"; the card shows Inactive; the list holds only 2026-2027 subjects | planned |
| TC-MST-08-E15 | P3 | Mobile | Admin | Seeded subjects | 1. Type "Science" in "Search subjects...".<br>2. Open "Filters" and untick Category. | Only General Science and Computer Science remain; the "Category:" line is hidden | planned |

---

## F09 Class-subject mappings: list, edit, delete and single create

**Purpose.** A mapping says that a class and section study a subject in an academic year, with an order and an "exclude from marks" flag. This feature covers listing, inline edit, delete, the read endpoints other modules use, and the single-row create endpoint. Bulk creation from the UI is F10.

**Roles and permissions.** Create: `class_subject_mappings:create`. Edit: `class_subject_mappings:update`. Delete: `class_subject_mappings:delete`. Paged list and dropdown: `class_subject_mappings:list`. Single read, `by-class` and `by-classes`: `class_subject_mappings:read`. Admin all; Staff and Teacher read and list; Student and Parent none. Menu: Masters > Class Subject Mappings (web `/masters/classsubjectmappings`), Home > Masters > Class Subject Mappings (mobile).

**Preconditions.** Academic year, class with sections, subjects (F01, F03, F08).

**Steps, web.**
1. Masters > Class Subject Mappings. Card "Class-Subject Mappings" lists mappings of the working year (including inactive) with columns Class, Section ("All" when the mapping has no section), Subject, Exclude from Marks (Yes or No), Order, Active, S.No. and Actions. Buttons: column selector "Filters", "Export", "Add Class-Subject Mappings" (F10). Search "Search..." (filters only the rows of the current page), sortable headers, server paging ("Previous", "Next", "Rows per page", default 5).
2. Edit inline: Edit icon; Exclude from Marks (checkbox), Order (text box) and Active (checkbox) are editable; Class, Section and Subject are read-only. Green check saves. Toast "Class-subject mapping updated successfully!" or "Failed to update mapping: <reason>".
3. Delete: trash icon, "Delete Row?", Delete. Toast "Class-subject mapping deleted successfully!". The row is removed (hard delete).
4. Export to CSV, Excel or Download Data.

**Steps, mobile.**
1. Home > Masters > Class Subject Mappings. Header "Class Subject Mappings", subtitle "Map subjects to classes and manage settings", button "Add Subject Mapping" and "n mappings" (mappings of the working year). Cards show the subject name, "Class: ...", "Section: ...", badges Active or Inactive, "Excl. Marks" and "Order: n". Search "Search by class, section or subject..."; the "Filters" icon opens "Show Fields" with "Select All"; the "Export" icon opens "Export As" (Export to CSV, Export to Excel, Download Data).
2. Edit icon opens "Edit Mapping": Order ("e.g. 1"), "Exclude from Marks", "Active", buttons "Cancel" and "Save Changes". Success toast "Mapping updated successfully"; failure toast "Update Failed".
3. Delete icon opens the confirm "Remove Mapping" ("Remove "<subject>" from the class?", button "Remove"); success toast "Removed - Subject mapping has been removed." Failure toast "Remove Failed".

**Expected results.** Edits change only the three editable flags; deleted rows are gone; consumers read the active mappings: the timetable subject picker (TTC) and exam subject configuration (`by-classes`).

**API endpoints.** Prefix `/api/v1/masters/class-subject-mappings`.
- `POST /` `{class_id, section_id?, subject_id, academic_year_id, exclude_marks=false, order?, is_active=true}` -> 201 `ClassSubjectMapRead`.
- `GET /` query `skip=0`, `limit=100` (1 to 1000), `class_id?`, `section_id?`, `academic_year_id?`, `active_only=true` -> `{items, total_count, has_next}` ordered by class, section, order.
- `GET /by-class/{class_id}` query `section_id?`, `academic_year_id?`, `active_only=true` -> list ordered by `order` (nulls first).
- `GET /by-classes?class_ids=<id>&class_ids=<id>` query `academic_year_id?`, `active_only=true` -> object keyed by class id.
- `GET /dropdown` query `class_id?`, `section_id?`, `academic_year_id?` -> active mappings `{id, class_name, section_name, subject_name, exclude_marks, order}`.
- `GET /{mapping_id}`; `PUT /{mapping_id}` partial; `DELETE /{mapping_id}` -> 204.

**Rules and validations.**
1. `ClassSubjectMapRead` carries `class_name`, `section_name`, `subject_name`, `academic_year_name`; `section_name` is null for class-level rows.
2. Unique indexes on (class, section, subject, year), and on (class, subject, year) where the section is null (migration 0007), reject a duplicate single `POST /` with 409. The single create does not check that the section belongs to the class or that the subject belongs to the year. A null `section_id` creates a class-level row that the timetable picker treats as "all sections".
3. `GET /dropdown` returns class-level rows with `section_name: null` (module doc rule 10).
4. Without `section_id`, `by-class` and `by-classes` return one row per section mapping, so a subject repeats; consumers must de-duplicate by `subject_id`.
5. List and read filters default to `active_only=true`; management screens pass `active_only=false`.
6. Update accepts any subset of fields, including ids; an invalid foreign key returns 400.
7. The web inline edit sends the whole row; an emptied Order text box sends `""` and is rejected with 422.

**Error and edge cases.**
- Single create failure (bad id, FK): 400 `Class-subject mapping creation failed.`. Update failure: 400 `Update failed`. Delete failure: 400 `Delete failed`.
- Unknown id: `GET`, `PUT`, `DELETE` return 404 `Class-subject mapping not found`.
- `by-classes` without `class_ids`: 422; an unknown class id yields an empty list under its key.
- Student and Parent get 403 for every endpoint.

**Unit-testable logic.**
- `ClassSubjectMapCreate`, `ClassSubjectMapUpdate` schemas (defaults `exclude_marks` False, `is_active` True, `order` None).
- `_mapping_to_read_dict` name fields when relationships are missing.
- `get_class_subject_mappings_by_classes` grouping (includes empty lists for requested classes with no rows) with fake rows; `has_next`.
- `get_class_subject_mappings_dropdown` shape; documents the null-section failure by constructing `ClassSubjectMapDropdown(section_name=None)`.
- Web: `fetchClassSubjectMappings` normalisation of `total_count`; inline edit payload; mobile mapping filter by class, section or subject.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-09-U01 | [backend] `ClassSubjectMapCreate` with the four required ids only | `exclude_marks` False, `is_active` True, `order` None, `section_id` None | passing |
| TC-MST-09-U02 | [backend] `ClassSubjectMapDropdown(section_name=None, ...)` | Validation error (documents the dropdown defect) | passing |
| TC-MST-09-U03 | [backend] `_mapping_to_read_dict` on a fake mapping with no section | `section_name` None; class, subject and year names filled | passing |
| TC-MST-09-U04 | [backend] `get_class_subject_mappings_by_classes([c1,c2])` with rows only for c1 | Result has keys for both ids; c2 maps to `[]` | passing |
| TC-MST-09-U05 | [backend] `get_class_subject_mappings_by_classes([])` | Returns `{}` without querying | passing |
| TC-MST-09-U06 | [web] `fetchClassSubjectMappings` with `{items,total_count}` and with a plain array | `{items,total}` using `total_count`; array length as total | passing |
| TC-MST-09-U07 | [mobile] Mapping filter `math` over class, section and subject names | Rows whose any of the three names contains `math` | blocked: needs the mapping filter exported from mobile/app/masters/classsubjectmappings.tsx |
| TC-MST-09-A01 | Admin `POST /` with class, section, subject, year, `order:1`, `exclude_marks:true` | 201 body with `class_name`, `section_name`, `subject_name`, `academic_year_name`, flags as sent | passing |
| TC-MST-09-A02 | POST without `section_id` | 201 with `section_id:null`, `section_name:null` | passing |
| TC-MST-09-A03 | POST the identical mapping twice | First 201; second 409 | passing |
| TC-MST-09-A04 | POST with a random `subject_id`; with a missing `class_id` | 400 `Class-subject mapping creation failed.`; 422 | passing |
| TC-MST-09-A05 | `GET /` default with 3 mappings (1 inactive) | `{items,total_count,has_next}`; only active rows; ordered by class then section then order | passing |
| TC-MST-09-A06 | `GET /?active_only=false&class_id=&section_id=&academic_year_id=` | Filters combine; inactive included | passing |
| TC-MST-09-A07 | `GET /?limit=0`, `?limit=1001`, `?skip=-1` | 422 each | passing |
| TC-MST-09-A08 | `GET /?skip=0&limit=2` then `skip=2&limit=2` with 3 rows | `total_count` 3; `has_next` true then false | passing |
| TC-MST-09-A09 | `GET /by-class/{class}` with 2 sections mapped to the same subject | Two rows for that subject (repeat); sorted by `order` with nulls first | passing |
| TC-MST-09-A10 | `GET /by-class/{class}?section_id=<s>&academic_year_id=<y>&active_only=false` | Only that section's rows including inactive | passing |
| TC-MST-09-A11 | `GET /by-classes?class_ids=<c1>&class_ids=<c2>` where c2 has no mapping | Object with both keys; c2 is `[]` | passing |
| TC-MST-09-A12 | `GET /by-classes` without `class_ids` | 422 | passing |
| TC-MST-09-A13 | `GET /dropdown` with all mappings sectioned | `[{id,class_name,section_name,subject_name,exclude_marks,order}]` of active rows | passing |
| TC-MST-09-A14 | `GET /dropdown` after creating a mapping with null section (A02) | 200 | passing |
| TC-MST-09-A15 | `GET /{id}` valid and random uuid | 200; 404 `Class-subject mapping not found` | passing |
| TC-MST-09-A16 | `PUT /{id}` `{exclude_marks:false, order:5, is_active:false}` | 200 with those values; names unchanged | passing |
| TC-MST-09-A17 | `PUT /{id}` with `subject_id` set to a random uuid | 400 `Update failed` | passing |
| TC-MST-09-A18 | `PUT /{random uuid}` and `DELETE /{random uuid}` | 404 each | passing |
| TC-MST-09-A19 | `DELETE /{id}` | 204; `GET /{id}` then 404 | passing |
| TC-MST-09-A20 | Read matrix: `GET /`, `/by-class/{c}`, `/by-classes`, `/dropdown`, `/{id}` as Admin, Staff, Teacher | 200 | passing |
| TC-MST-09-A21 | Same reads as Student and Parent | 403 each | passing |
| TC-MST-09-A22 | Write matrix: POST, PUT, DELETE as Staff, Teacher, Student, Parent | 403 each; Admin 2xx | passing |
| TC-MST-09-A23 | No Authorization header on every endpoint | 401 | passing |
| TC-MST-09-A24 | Tenant isolation: tenant B calls `GET /`, `/by-class/{A's class}`, `/{A's id}` | Empty lists; `by-classes` keys with empty lists; `GET /{id}` 404 | passing |
| TC-MST-09-A25 | 31 single POSTs within a minute (limiter enabled) | The 31st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-09-E01 | P1 | Web | Admin | Seeded mappings for 2026-2027 | 1. Sign in as Admin (qa_manual).<br>2. Open Masters > Class Subject Mappings. | Card "Class-Subject Mappings" with Class, Section, Subject, Exclude from Marks, Order, Active; seeded rows such as Class 1 / 1-A / English / No / 1 / Active | planned |
| TC-MST-09-E02 | P3 | Web | Admin | Seeded mappings | 1. Type "English" in "Search...".<br>2. Click the "Class" header.<br>3. Set "Rows per page" to 20. | Filter (current page only), sort and server paging behave as in F01 | planned |
| TC-MST-09-E03 | P2 | Web | Admin | TC-MST-10-E01 done (QA C9 mappings) | 1. Search the QA class mapping row, click its Edit icon.<br>2. Tick "Exclude from Marks", set Order "3".<br>3. Press the green check. | Toast "Class-subject mapping updated successfully!"; row shows Yes and 3 | planned |
| TC-MST-09-E04 | P3 | Web | Admin | TC-MST-10-E01 done | 1. Edit a QA mapping row.<br>2. Clear "Order" and press the green check. | Toast "Failed to update mapping: ..." (422); row unchanged | planned |
| TC-MST-09-E05 | P2 | Web | Admin | TC-MST-10-E01 done | 1. Edit a QA mapping row, untick "Active", save.<br>2. Open Timetable, choose the QA class and a section, open the subject picker. | Row shows Inactive; that subject is not offered for the QA class | planned |
| TC-MST-09-E06 | P2 | Web | Admin | TC-MST-10-E01 done | 1. Click the trash icon on each QA mapping row.<br>2. Click "Delete" in "Delete Row?". | Toast "Class-subject mapping deleted successfully!"; rows gone (hard delete) | planned |
| TC-MST-09-E07 | P2 | Web | Teacher | Seeded mappings | 1. Sign in as Teacher.<br>2. Open Masters > Class Subject Mappings. | List and "Export" only; no "Add Class-Subject Mappings", no Edit or trash icons | planned |
| TC-MST-09-E08 | P1 | Mobile | Admin | Seeded mappings | 1. Open Home > Masters > Class Subject Mappings.<br>2. Type "Class 3" in "Search by class, section or subject...". | Subtitle "Map subjects to classes and manage settings", "n mappings"; only Class 3 cards remain (subject, "Class: Class 3", "Section: 3-A" or "3-B", Active, "Order: n") | planned |
| TC-MST-09-E09 | P2 | Mobile | Admin | TC-MST-10-E09 done (QA class mappings) | 1. Tap Edit on a QA mapping card.<br>2. In "Edit Mapping" set Order "2", turn on "Exclude from Marks".<br>3. Tap "Save Changes". | Toast "Mapping updated successfully"; card shows "Order: 2" and "Excl. Marks" | planned |
| TC-MST-09-E10 | P2 | Mobile | Admin | TC-MST-10-E09 done | 1. Tap Delete on a QA mapping card.<br>2. In "Remove Mapping" tap "Remove". | Toast "Removed - Subject mapping has been removed."; card gone | planned |
| TC-MST-09-E11 | P3 | Mobile | Admin | Seeded mappings | 1. Tap the "Filters" icon.<br>2. In "Show Fields" untick Section. | The "Section:" line is hidden on every card | planned |
| TC-MST-09-E12 | P2 | Mobile | Student | Seeded student Advik Mehta (login 002) | 1. Sign in as the student.<br>2. Check Home; open `/masters/classsubjectmappings` by URL. | No Masters card; the screen loads no mappings (403) | planned |

---

## F10 Bulk class-subject mappings

**Purpose.** An admin maps several subjects to one class and one, several or all of its sections in one action, setting each subject's order, exclude-marks flag and active flag.

**Roles and permissions.** `class_subject_mappings:create` (Admin only). Menu: the "Add Class-Subject Mappings" button on Masters > Class Subject Mappings (web), "Add Subject Mapping" on the mobile screen.

**Preconditions.** An academic year selected, a class with active sections, and subjects (F01, F03, F08).

**Steps, web.**
1. On Class Subject Mappings click "Add Class-Subject Mappings". Dialog "Add Class-Subject Mappings".
2. "Class": choose from "Select Class" (active classes). A "Sections" multi-select appears ("Select one or more sections", first option "All Sections"). Choosing "All Sections" replaces any other selection. A blue note shows "Mappings will be created for 2 selected sections" ("1 selected section" for one); for All Sections an amber warning "This will apply mappings to all 2 sections in <class>".
3. "Subjects": multi-select "Select multiple subjects..." (already chosen subjects are removed from the list; the options are all subjects returned by the API). A table "Selected Subjects Settings" lists each subject with Order (number, minimum 1, auto-numbered), Exclude Marks (checkbox), Active (checkbox, default on) and a Remove (trash) button.
4. Buttons "Cancel" and "Add N Mappings" ("Add 0 Mappings" when nothing is chosen, "Add 1 Mapping" for one; "Adding..." while pending; disabled until a class, at least one section and at least one subject are chosen and a working year exists). One bulk request is sent per selected section, or a single request without `section_id` for All Sections. The toast shows the API message (for example "Successfully processed class-subject mappings: 3 created, 0 updated, 0 deactivated"); the dialog closes after the last request. Closing with unsaved choices asks "Discard changes?".

**Steps, mobile.**
1. Tap "Add Subject Mapping". Sheet "Add Subject Mappings" (subtitle "<class> . n selected"): a class selector "Select Class" (empty state "Select a Class - Choose a class above to see its sections and available subjects."); after a class is chosen a section selector that reads "All Sections" by default and opens "Select Sections" with "Done" (empty selection means all sections; it then reads the section name or "n sections selected"); a list of the subjects not yet mapped to that class ("All subjects mapped - All available subjects are already mapped to this class." when none), and per selected subject Order (placeholder "Auto"), "Exclude from Marks" and "Active". The add button "Add (n)" appears only when the class has unmapped subjects and is disabled until a subject is ticked.
2. Success toast "Subjects Added - N subject(s) mapped to class." or "... mapped to N sections."; failure "Add Failed". The "Select a Class - Please select a class before adding subjects." toast exists in code but cannot be reached, because the add button is hidden until a class is chosen.

**Expected results.** For each processed section the sent subjects exist as mappings with the given order and flags; mappings of that class, section and year whose subject was not sent are left unchanged.

**API endpoints.**
- `POST /api/v1/masters/class-subject-mappings/bulk` `{class_id, section_id?, academic_year_id, subjects:[{subject_id, order?, exclude_marks=false, is_active=true}]}` -> 201 `{success, message, created_count, updated_count, deactivated_count, sections_processed, mappings:[ClassSubjectMapRead]}`.

**Rules and validations.**
1. The call adds or updates the listed subjects only: existing mappings of the section (same class, section and year) that are not in `subjects[]` are left as they are. `deactivated_count` is always 0 and is kept for compatibility. An empty `subjects` list changes nothing. Removal is done per row (update `is_active` or delete).
2. Subjects already mapped are updated (order, flags, active) and counted in `updated_count`; new ones are created and counted in `created_count`; unknown `subject_id` values are skipped silently and not counted.
3. `section_id` omitted or null applies to every active section of the class (`sections_processed` is that count); if the class has no active section the call is 404 `No active sections found for this class`.
4. With a `section_id` it must belong to the class, else 404 `Section not found or does not belong to the specified class`. Unknown class: 404 `Class not found`; unknown year: 404 `Academic year not found`.
5. The same `subject_id` listed twice in one request is collapsed (the last entry wins), so one row is created. Subject year is not validated against `academic_year_id`. A unique index on `(tenant_id, class_id, section_id, subject_id, academic_year_id)` (and a class-wide one where `section_id` is null) prevents duplicate rows; a duplicate single create returns 409.
6. Everything runs in one transaction and rolls back on any error (400 `Bulk operation failed: ...`).
7. Rate limit 10 per minute per client IP.
8. Both web and mobile add dialogs send only the newly chosen subjects, which is now safe because other mappings of the section are no longer deactivated.

**Error and edge cases.**
- Missing `class_id`, `academic_year_id` or `subjects`: 422. Invalid uuid: 422.
- Wrong role: 403.
- Web sends concurrent requests for multiple sections; one failure shows a toast per failure while others may succeed.

**Unit-testable logic.**
- `_process_section_mappings` with fake existing rows: counts for create, update, deactivate; skipped unknown subject; duplicate subject in payload; empty payload.
- `bulk_create_or_update_class_subject_mappings` section resolution: explicit section, null section fan-out, no active sections, section of another class; message strings.
- `ClassSubjectMapBulkCreate` schema and `SubjectMappingItem` defaults.
- Web modal: order auto-numbering, remove re-numbers, "All Sections" exclusivity, submit-disabled rule, per-section request fan-out; mobile `handleBulkAdd` payload.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-10-U01 | [backend] `_process_section_mappings` with no existing rows and 2 known subjects | `created_count` 2, `updated_count` 0, `deactivated_count` 0 | passing |
| TC-MST-10-U02 | [backend] Existing active mapping for subject S1; payload `[S2]` | S2 created, S1 stays active: created 1, deactivated 0 | passing |
| TC-MST-10-U03 | [backend] Existing inactive mapping for S1; payload `[S1 is_active true]` | Reactivated and counted as updated 1 | passing |
| TC-MST-10-U04 | [backend] Payload contains a subject id the fake session does not know | Skipped; not counted; no error | passing |
| TC-MST-10-U05 | [backend] Payload lists S3 twice (S3 new) | One new row created | passing |
| TC-MST-10-U06 | [backend] `bulk_...` with `section_id=None` and 3 active fake sections | `sections_processed` 3; message `... for 3 sections: ...` | passing |
| TC-MST-10-U07 | [backend] `bulk_...` null section and zero active sections; section of another class | 404 `No active sections found for this class`; 404 `Section not found or does not belong to the specified class` | passing |
| TC-MST-10-U08 | [backend] `ClassSubjectMapBulkCreate` without `subjects` | Validation error | passing |
| TC-MST-10-U09 | [web] Modal subject selection of 3 subjects then removing the 2nd | Orders become 1 and 2; `isFormValid` false until class, section and subject chosen | blocked: needs the selection logic exported from web/src/components/masters/classsubjectmappings/AddBulkClassSubjectMappingsModal.tsx |
| TC-MST-10-U10 | [web] Selecting "All Sections" with sections A and B selected | Selection becomes only "All Sections"; submit sends `section_id` undefined once | blocked: needs the All Sections logic exported from web/src/components/masters/classsubjectmappings/AddBulkClassSubjectMappingsModal.tsx |
| TC-MST-10-U11 | [mobile] `handleBulkAdd` with empty section selection and 2 subjects | One request with `section_id` undefined and 2 subject items (order numbers from the inputs) | blocked: needs handleBulkAdd payload builder exported from mobile/app/masters/classsubjectmappings.tsx |
| TC-MST-10-A01 | Admin `POST /bulk` with class, section A, year, subjects S1 (order 1) and S2 (order 2, exclude_marks true) | 201; `created_count` 2, `updated_count` 0, `deactivated_count` 0, `sections_processed` 1; `mappings` has 2 items with names | passing |
| TC-MST-10-A02 | POST again with S1 order 5 and S3 | `updated_count` 1 (S1), `created_count` 1 (S3), `deactivated_count` 0; S2 stays `is_active:true` | passing |
| TC-MST-10-A03 | POST with `subjects:[]` | 201; nothing changes; `mappings:[]` | passing |
| TC-MST-10-A04 | POST with `section_id` null on a class with sections A, B active and C inactive | `sections_processed` 2; mappings only for A and B; C gets none | passing |
| TC-MST-10-A05 | POST with null section on a class with no active section | 404 `No active sections found for this class` | passing |
| TC-MST-10-A06 | POST with a section of another class | 404 `Section not found or does not belong to the specified class` | passing |
| TC-MST-10-A07 | POST with a random `class_id`; with a random `academic_year_id` | 404 `Class not found`; 404 `Academic year not found` | passing |
| TC-MST-10-A08 | POST with an unknown subject id plus one valid subject | 201; `created_count` 1; unknown id skipped | passing |
| TC-MST-10-A09 | POST with the same new subject twice | `created_count` 2; two rows for that subject (documents the defect) | passing |
| TC-MST-10-A10 | POST missing `class_id`, `academic_year_id`, `subjects`; invalid uuid in `subject_id` | 422 each | passing |
| TC-MST-10-A11 | `by-class` after A01 and A02 | Active rows reflect the latest request (S1, S3); order values as sent | passing |
| TC-MST-10-A12 | Role matrix: POST as Staff, Teacher, Student, Parent | 403 each; Admin 201 | passing |
| TC-MST-10-A13 | No Authorization header | 401 | passing |
| TC-MST-10-A14 | Tenant isolation: tenant B posts with tenant A's class id | 404 `Class not found`; no rows created in A | passing |
| TC-MST-10-A15 | 11 POSTs within a minute (limiter enabled) | The 11th returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-10-E01 | P1 | Web | Admin | TC-MST-03-E06 done (QA C9 with sections A, B, C, no mappings) | 1. On Class Subject Mappings click "Add Class-Subject Mappings".<br>2. Select Class "QA C9", Sections "All Sections".<br>3. Select Subjects "Mathematics" and "English".<br>4. Click "Add 2 Mappings". | Amber note "This will apply mappings to all 3 sections in QA C9"; toast "Successfully processed class-subject mappings ..." (3 sections); rows for A, B and C appear with orders 1 and 2 | planned |
| TC-MST-10-E02 | P2 | Web | Admin | QA C9 without mappings (or after TC-MST-09-E06) | 1. Open the dialog, select "QA C9".<br>2. Select sections "A" and "B".<br>3. Select "Hindi", click "Add 1 Mapping". | Blue note "Mappings will be created for 2 selected sections"; two requests; rows only for A and B | planned |
| TC-MST-10-E03 | P3 | Web | Admin | QA C9 | 1. Open the dialog, select "QA C9", sections "A" and "B".<br>2. Select "All Sections". | The selection collapses to "All Sections" only | planned |
| TC-MST-10-E04 | P3 | Web | Admin | QA C9 | 1. Open the dialog and watch the submit button while choosing class, section and subject in turn. | "Add 0 Mappings" is disabled until a class, a section and at least one subject are chosen | planned |
| TC-MST-10-E05 | P3 | Web | Admin | QA C9 | 1. Select class, "All Sections" and subjects "English", "Hindi", "Telugu".<br>2. Remove "Hindi" with its trash button.<br>3. Untick "Active" for Telugu.<br>4. Click "Add 2 Mappings". | Orders renumber to 1 and 2 after the removal; after submit Telugu rows show Inactive | planned |
| TC-MST-10-E06 | P2 | Web | Admin | TC-MST-10-E01 done (Mathematics and English on QA C9) | 1. Open the dialog, select "QA C9", section "A".<br>2. Select only "Social Studies", submit. | Section A now has Mathematics, English and Social Studies all active (bulk add does not deactivate others) | planned |
| TC-MST-10-E07 | P3 | Web | Admin | None | 1. Open the dialog and select a class.<br>2. Click "Cancel". | "Discard changes?" guard appears; confirming closes the dialog with nothing saved | planned |
| TC-MST-10-E08 | P2 | Web | Teacher | Seeded mappings | 1. Sign in as Teacher.<br>2. Open Masters > Class Subject Mappings. | No "Add Class-Subject Mappings" button | planned |
| TC-MST-10-E09 | P1 | Mobile | Admin | TC-MST-03-E13 done (QA C8 with sections A, B, no mappings) | 1. Tap "Add Subject Mapping".<br>2. Tap "Select Class", pick "QA C8"; leave the section selector on "All Sections".<br>3. Tick "Mathematics" and "English".<br>4. Tap "Add (2)". | Toast "Subjects Added - 2 subject(s) mapped to 2 sections."; cards appear for A and B | planned |
| TC-MST-10-E10 | P3 | Mobile | Admin | None | 1. Tap "Add Subject Mapping" without choosing a class. | The sheet shows "Select a Class" and no add button | obsolete: the add button is hidden until a class is chosen, so the "Select a Class" toast cannot be reached; see TC-MST-10-E13 |
| TC-MST-10-E11 | P3 | Mobile | Admin | Seeded "Class 1" (8 of 10 subjects mapped) | 1. Tap "Add Subject Mapping", pick "Class 1". | Only General Science and Social Studies are listed. For a class with every subject mapped the sheet shows "All subjects mapped" | planned |
| TC-MST-10-E12 | P2 | Mobile | Admin | QA C8 with sections A and B, "Hindi" unmapped | 1. Tap "Add Subject Mapping", pick "QA C8".<br>2. Open the section selector, select A and B in "Select Sections", tap "Done".<br>3. Tick "Hindi", tap "Add (1)". | Selector reads "2 sections selected"; toast "Subjects Added - 1 subject(s) mapped to 2 sections."; two new cards | planned |
| TC-MST-10-E13 | P3 | Mobile | Admin | None | 1. Tap "Add Subject Mapping".<br>2. Look for an add button before choosing a class. | Empty state "Select a Class - Choose a class above to see its sections and available subjects."; no add button until a class with unmapped subjects is chosen | planned |

---

## F11 Parents

**Purpose.** An admin or staff member views, searches, edits and deletes parent and guardian profiles and sees which students each parent is linked to. Parent profiles are normally created through student admission (Students module).

**Roles and permissions.** Create: `parent_management:create`. List, search and salary-range list: `parent_management:list` (the salary dropdown needs only a valid login). Single read: `parent_management:read`. Edit: `parent_management:update`. Delete: `parent_management:delete`. Admin all; Staff create, read, update and list (no delete); Teacher, Student and Parent none. Menu: Masters > Parents (web `/masters/parents`), Home > Masters > Parents (mobile `/masters/parents`; the seeded menu has a Parents card).

**Preconditions.** Parent rows exist (from admission or a database fixture); each parent row needs a linked user account.

**Steps, web.**
1. Masters > Parents. Page header "Parent Management" ("Manage parent profiles and their relationships with students") with a "Parent Portal Access" note and the table "Parent Profiles". Columns S.No., Name (gender under the name), Contact (email and phone), Relationship (Father, Mother or Guardian badge), Occupation ("-" when empty), Students ("1 student" or "n students") and Actions (icons "Edit Parent", "Delete Parent"; shown only with update or delete permission). Search "Search parents..." (name, email, phone, occupation, relationship) and sort on Name, Relationship and Occupation. There is no paging (first 100 parents). Empty state "No parent profiles found." with "Create First Parent Profile" for roles with create.
2. "Add Parent" (create permission): dialog "Create Parent Profile" with Full Name * ("Enter parent's full name"), Email ("Enter email address"), Phone ("Enter phone number"), Occupation ("Enter occupation/profession"), Aadhar Number ("Enter 12-digit Aadhar number"), Gender ("Select gender"), Relationship to Student * (default Father; Father, Mother, Guardian); buttons "Cancel" and "Save". Empty name: toast "Parent name is required"; no email and no phone: toast "Email or phone is required to create the parent login" (the value becomes the parent's login; the API creates the parent user with the default first-login password). Success toast "Parent profile created successfully"; failure "Failed to create parent profile: <reason>".
3. Edit Parent: dialog "Edit Parent Profile", same fields prefilled, "Save". Empty optional fields are not sent. Toast "Parent profile updated successfully". Validation toast "Parent name is required".
4. Delete Parent: dialog "Delete Parent Profile" ("Are you sure you want to delete the profile for "<name>"? This action cannot be undone and will remove all student associations."), "Cancel" and "Delete". Toast "Parent profile deleted successfully".

**Steps, mobile.**
1. Home > Masters > Parents. Header "Parents" with "n registered parents". Cards with initials, S.No., name, relationship badge, phone, email, occupation and the linked student names ("No linked students"). Search "Search by name, email or phone...". Header add icon (label "Add"), Edit and Delete icons per card, and empty-state button "Add Parent".
2. Modal "Add Parent" fields: Full Name ("Parent's full name"), Relationship to Student * (default Father; Father, Mother, Guardian), Gender ("Select gender"), Email ("email@example.com"), Phone ("Phone number"), Occupation ("e.g. Engineer"), Aadhar Number ("12-digit Aadhar number"), Annual Income ("Select income range": Below 1 lakh, 1 to 3 lakhs, 3 to 5 lakhs, 5 to 10 lakhs, Above 10 lakhs). Save button "Add Parent" or "Save Changes". Validation toasts "Validation - Enter a valid email address", "Validation - Aadhar number must be 12 digits" and, on add, "Validation - Email or phone is required to create the parent login". Toasts "Parent Added - The parent profile was created", "Parent Updated - The parent profile was saved", "Parent Deleted - The parent profile was removed"; failures "Create Failed", "Update Failed", "Delete Failed" with the reason. Delete confirm "Delete Parent".

**Expected results.** Lists show parents ordered by name with their linked students. Edit changes only sent fields. Delete removes the parent and its student links but not the students.

**API endpoints.** Prefix `/api/v1/parents`.
- `POST /` `{name?, email?, phone?, occupation?, aadhar_number?, gender?, relation_to_student, salary_range?}` -> intended 201 `ParentOut`.
- `GET /` query `skip=0`, `limit=100` (1 to 1000) -> `{items, total_count, has_next, skip, limit}`.
- `GET /search` query `search_query?`, `email?`, `phone?`, `relation_to_student?`, `skip=0`, `limit=10` (1 to 100).
- `GET /{parent_id}` -> `ParentOut` with `students:[{id, first_name, last_name}]`.
- `PATCH /{parent_id}` partial -> `ParentOut`. `DELETE /{parent_id}` -> 204.
- `GET /salary-ranges/dropdown` -> `[{value, label, display}]` for `below_1l`, `1l_3l`, `3l_5l`, `5l_10l`, `above_10l` (fixed list, login only).

**Rules and validations.**
1. `POST /` creates the parent and its login in one transaction: a `Parent` role user with username = email (else phone), `is_first_login` true and the default parent password (same convention as the admission flow). Email or phone is required (400). A username or email already in use is 409. The body takes no `user_id`.
2. `ParentCreate` validation: `relation_to_student` required and one of Father, Mother, Guardian; `salary_range` one of the five values; `aadhar_number` exactly 12 digits when present; email must be valid; a blank `name` is replaced by the relation label.
3. `ParentUpdate` allows `gender` of Male, Female or Other only, `relation_to_student` and `salary_range` from the same sets, a valid email, and applies no Aadhar validator (a value longer than 12 characters fails at the database with 500).
4. Search filters are combined with OR, not AND (`search_query` over name, email and phone with case-insensitive contains; `email` and `phone` contains; `relation_to_student` exact). Results are ordered by name.
5. Delete cascades to `student_parent_links` only.
6. Web Edit no longer asks for a User ID and sends only non-empty fields.

**Error and edge cases.**
- Unknown id: `GET`, `PATCH`, `DELETE` return 404 `Parent not found`.
- Invalid email, relation, gender, salary range: 422.
- Teacher, Student and Parent get 403 on every parent endpoint except the salary dropdown.
- Staff delete: 403 on the API; the web hides the delete icon.

**Unit-testable logic.**
- `ParentBase` validators: `aadhar_number` (11 digits, 12 digits, letters), `relation_to_student` literal, blank-name default, `salary_range` literal.
- `ParentUpdate` literals and absence of the Aadhar rule.
- `ParentOut.from_orm_with_students` student mapping and `salary_range` None.
- `search_parents` filter composition (OR) with a fake session; `has_next` and `skip/limit` echo.
- Web `ParentsTable` search and sort; mobile `buildPayload` (omits empty fields) and `parentLabel` fallback to the relation.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-11-U01 | [backend] `ParentCreate(relation_to_student="Father", aadhar_number="123456789012")` | Valid | passing |
| TC-MST-11-U02 | [backend] `aadhar_number` of `"12345678901"` and `"12345678901a"` | Validation error `Must be a 12-digit number` each | passing |
| TC-MST-11-U03 | [backend] `ParentCreate` with `name=""` and `relation_to_student="Mother"` | `name` becomes `Mother` | passing |
| TC-MST-11-U04 | [backend] `ParentCreate(relation_to_student="Uncle")`; `salary_range="2l_4l"`; `email="bad"` | Validation error each | passing |
| TC-MST-11-U05 | [backend] `ParentUpdate(gender="Male")` vs `gender="M"` | Valid; error | passing |
| TC-MST-11-U06 | [backend] `ParentUpdate(aadhar_number="1")` | Valid (no validator on update) | passing |
| TC-MST-11-U07 | [backend] `ParentOut.from_orm_with_students` with 2 linked fake students and empty `salary_range` | `students` has 2 entries with first and last name; `salary_range` None | passing |
| TC-MST-11-U08 | [backend] `search_parents(email="a", relation_to_student="Father")` with a fake session | Generated filter is an AND of the two conditions | passing |
| TC-MST-11-U09 | [web] `ParentsTable` search `eng` over name, email, phone, occupation, relation | Case-insensitive match across the five fields; sort on Relationship ascending | blocked: needs search and sort helpers exported from web/src/components/masters/parents/ParentsTable.tsx |
| TC-MST-11-U10 | [mobile] `buildPayload` with only relation and phone filled | Payload `{relation_to_student, phone}`; no empty strings | blocked: needs buildPayload exported from mobile/app/masters/parents.tsx |
| TC-MST-11-A01 | Admin `POST /parents/` with a valid body (email or phone) | 201 `ParentOut`; a Parent-role user exists with `is_first_login` true | passing |
| TC-MST-11-A02 | POST with invalid `relation_to_student`, `aadhar_number` of 11 digits, `email` `"x"` | 422 each (validation precedes the database) | passing |
| TC-MST-11-A03 | `GET /` default with 3 parent fixtures | Shape `{items,total_count,has_next,skip,limit}`; ordered by name; each item has `students` | passing |
| TC-MST-11-A04 | `GET /?skip=0&limit=2` then `skip=2&limit=2` | `has_next` true then false | passing |
| TC-MST-11-A05 | `GET /?limit=0`, `?limit=1001`, `?skip=-1` | 422 each | passing |
| TC-MST-11-A06 | `GET /search?search_query=ravi` | Parents whose name, email or phone contains `ravi`, case-insensitive | passing |
| TC-MST-11-A07 | `GET /search?relation_to_student=Mother` | Only mothers (exact match) | passing |
| TC-MST-11-A08 | `GET /search?email=a@x.com&relation_to_student=Father` | Parents matching email AND relation | passing |
| TC-MST-11-A09 | `GET /search?limit=100` and `?limit=101` | 200; 422 | passing |
| TC-MST-11-A10 | `GET /{id}` valid with linked student; random uuid | 200 with `students`; 404 `Parent not found` | passing |
| TC-MST-11-A11 | `PATCH /{id}` `{occupation:"Engineer", salary_range:"3l_5l"}` | 200; fields changed; others unchanged | passing |
| TC-MST-11-A12 | `PATCH` with `gender:"M"`, `email:""`, `relation_to_student:"Uncle"`, `salary_range:"x"` | 422 each | passing |
| TC-MST-11-A13 | `PATCH` with `aadhar_number` of 13 characters | 500 detail starts `Error updating parent` | passing |
| TC-MST-11-A14 | `PATCH /{random uuid}` | 404 | passing |
| TC-MST-11-A15 | `DELETE /{id}` of a parent linked to a student | 204; links removed; the student still exists | passing |
| TC-MST-11-A16 | `DELETE /{random uuid}` | 404 | passing |
| TC-MST-11-A17 | `GET /salary-ranges/dropdown` as every role | 200 for all five roles; 5 items with `value`, `label`, `display` in the order below_1l, 1l_3l, 3l_5l, 5l_10l, above_10l | passing |
| TC-MST-11-A18 | Role matrix: list, search, get, patch as Admin and Staff | 200 | passing |
| TC-MST-11-A19 | Role matrix: `DELETE` as Staff | 403; Admin 204 | passing |
| TC-MST-11-A20 | Role matrix: all endpoints except salary dropdown as Teacher, Student, Parent | 403 each | passing |
| TC-MST-11-A21 | No Authorization header on every endpoint including the salary dropdown | 401 | passing |
| TC-MST-11-A22 | Tenant isolation: tenant B on `GET /`, `/search`, `/{A's id}`, `PATCH`, `DELETE` | Empty lists; 404; row unchanged | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-11-E01 | P1 | Web | Admin | Seeded parent profiles (father and mother of each seeded student) | 1. Sign in as Admin (qa_manual).<br>2. Open Masters > Parents. | Header "Parent Management", table "Parent Profiles"; rows such as "Venkat Raju" (Male, venkat.raju@example.com, Father, Bank Officer, "2 students") | planned |
| TC-MST-11-E02 | P2 | Web | Admin | Seeded parents | 1. Type "9000100012" in "Search parents...".<br>2. Clear it and click the "Name" header twice. | Only Venkat Raju remains; the name order toggles | planned |
| TC-MST-11-E03 | P2 | Web | Admin | No user "qa.parent1@example.com" | 1. Click "Add Parent".<br>2. Enter Full Name "QA Parent One", Email "qa.parent1@example.com", Relationship "Father".<br>3. Click "Save". | Toast "Parent profile created successfully"; row appears with "0 students" (a Parent login is created) | planned |
| TC-MST-11-E04 | P3 | Web | Admin | None | 1. Click "Add Parent".<br>2. Leave Full Name empty, enter an email.<br>3. Click "Save". | Toast "Parent name is required"; dialog stays | planned |
| TC-MST-11-E05 | P2 | Web | Admin | TC-MST-11-E03 done | 1. Click "Edit Parent" on "QA Parent One".<br>2. Set Occupation "Engineer".<br>3. Click "Save". | Toast "Parent profile updated successfully"; Occupation shows Engineer | planned |
| TC-MST-11-E06 | P3 | Web | Admin | A parent "QA Parent Two" created with phone only (Add Parent with Phone "9000999001", no email) | 1. Click "Edit Parent" on "QA Parent Two".<br>2. Change Occupation, click "Save". | Saves without error (the empty email is not sent) | planned |
| TC-MST-11-E07 | P2 | Web | Admin | TC-MST-11-E03 done | 1. Click "Delete Parent" on "QA Parent One".<br>2. Click "Delete". | Dialog "Delete Parent Profile" names the parent; toast "Parent profile deleted successfully"; row gone | planned |
| TC-MST-11-E08 | P2 | Web | Staff | Seeded parents | 1. Sign in as Staff.<br>2. Open Masters > Parents. | "Add Parent" and "Edit Parent" visible; no "Delete Parent" icon | planned |
| TC-MST-11-E09 | P2 | Web | Teacher | Seeded parents | 1. Sign in as Teacher.<br>2. Open Masters > Parents. | Page opens, list calls return 403, table shows "No parent profiles found." with no Add button | planned |
| TC-MST-11-E10 | P1 | Mobile | Admin | Seeded parents | 1. Open Home > Masters > Parents.<br>2. Type "venkat.raju" in "Search by name, email or phone...". | "n registered parents"; the Venkat Raju card shows Father, phone, email, Bank Officer and Harsha and Tanvi as linked students | planned |
| TC-MST-11-E11 | P3 | Mobile | Admin | None | 1. Tap the Add icon.<br>2. Enter Full Name "QA M Parent", Email "bad".<br>3. Tap "Add Parent". | Toast "Validation - Enter a valid email address" | planned |
| TC-MST-11-E12 | P3 | Mobile | Admin | None | 1. Tap the Add icon.<br>2. Enter a valid email and Aadhar "12345678901".<br>3. Tap "Add Parent". | Toast "Validation - Aadhar number must be 12 digits" | planned |
| TC-MST-11-E13 | P2 | Mobile | Admin | No user "qa.mparent@example.com" | 1. Tap the Add icon.<br>2. Enter Full Name "QA M Parent", Relationship "Mother", Email "qa.mparent@example.com".<br>3. Tap "Add Parent". | Toast "Parent Added - The parent profile was created"; card appears with "No linked students" | planned |
| TC-MST-11-E14 | P2 | Mobile | Admin | TC-MST-11-E13 done | 1. Tap Edit on "QA M Parent".<br>2. Set Annual Income "3 to 5 lakhs", tap "Save Changes".<br>3. Reopen Edit. | Toast "Parent Updated - The parent profile was saved"; the range is still selected | planned |
| TC-MST-11-E15 | P2 | Mobile | Admin | TC-MST-11-E13 done | 1. Tap Delete on "QA M Parent".<br>2. Confirm in "Delete Parent". | Toast "Parent Deleted - The parent profile was removed"; card gone | planned |
| TC-MST-11-E16 | P3 | Mobile | Admin | None | 1. Tap the Add icon.<br>2. Enter only Full Name "QA M Parent 3" (no email, no phone), tap "Add Parent". | Toast "Validation - Email or phone is required to create the parent login" | planned |

---

## F12 Locations: states, districts and mandals

**Purpose.** States, districts and mandals form the cascading address dropdowns (state, then district, then mandal) used by the student admission form. The three tables are shared by all tenants.

**Roles and permissions.** Create: `locations:create`. Update: `locations:update`. Delete: `locations:delete`. List endpoints (`GET /states`): `locations:list`. Dropdowns, child lists and single reads: `locations:read`. Admin all; Staff and Teacher read and list; Student and Parent none.

**Preconditions.** Location data seeded once per deployment by `POST /api/v1/auth/seed/location-data` (public, idempotent), or created through the API.

**Steps, web.** There is no management screen. The admission form (Students > Admission, address step) has "State (Optional)", "District (Optional)" (placeholder "-- Select District --") and "Mandal (Optional)" ("-- Select Mandal --") and calls the three dropdown endpoints; choosing a state loads its districts, choosing a district loads its mandals, and changing a parent clears the children. With no seeded states the State list is empty.

**Steps, mobile.** The admission form uses the same cascade. A separate screen `app/masters/locations.tsx` (title "Locations") exists but calls a flat `/masters/locations/` that the API does not have (see Known gaps): it shows "0 locations" and "No Locations Found - Add your first location to get started". It is reachable by route and, only when the backend menu has not loaded, from the Masters hub fallback list; the seeded menu has no Locations entry.

**Expected results.** Dropdown endpoints return active rows ordered by name; a state with districts or a district with mandals cannot be deleted.

**API endpoints.** Prefix `/api/v1/masters/locations`.
- States: `POST /states` `{name, code?, is_active=true}` (201); `GET /states` query `skip=0`, `limit=100` (1 to 1000), `active_only=false` -> `{items,total_count,has_next}`; `GET /states/dropdown` query `active_only=true` -> `[{id,name,code}]`; `GET /states/{id}`; `PUT /states/{id}`; `DELETE /states/{id}`.
- Districts: `GET /states/{state_id}/districts` (all, optional `active_only=false`); `GET /states/{state_id}/districts/dropdown` -> `[{id,name,code,state_id}]`; `POST /districts` `{state_id, name, code?, is_active}` (201); `GET /districts/{id}`; `PUT /districts/{id}`; `DELETE /districts/{id}`.
- Mandals: `GET /districts/{district_id}/mandals`; `GET /districts/{district_id}/mandals/dropdown` -> `[{id,name,district_id}]`; `POST /mandals` `{district_id, name, is_active}` (201); `GET /mandals/{id}`; `PUT /mandals/{id}`; `DELETE /mandals/{id}`.
- Seed: `POST /api/v1/auth/seed/location-data` (no authentication) -> 201.

**Rules and validations.**
1. State `name` is unique across the platform (exact match): duplicate create or rename returns 400 `State name '<name>' already exists`. District and mandal names are not checked for duplicates.
2. `name` is at most 100 characters, `code` at most 20; mandals have no `code`.
3. Creating a district needs an existing state (404 `State with id ... not found`); creating a mandal needs an existing district; re-parenting on update checks the new parent.
4. Delete of a state with districts: 400 `Cannot delete state '<name>' because it has N district(s). Please delete districts first.`; district with mandals: 400 `... N mandal(s). Please delete mandals first.`; mandal: no check.
5. These tables live in the shared public schema (no `tenant_id`); a state created by one tenant is visible to all tenants.
6. Dropdowns are cached for 5 minutes per tenant and arguments; the invalidation calls on create, update and delete are no-ops (they pass a pattern as the cache type), so changes show after the TTL.
7. The seed is idempotent (existing rows are skipped) and loads five states (Andhra Pradesh, Telangana, Karnataka, Tamil Nadu, Maharashtra) with their districts and mandals.

**Error and edge cases.**
- Unknown id: 404 `... with id <id> not found` on get, update and delete; `GET /states/{unknown}/districts` and `GET /districts/{unknown}/mandals` return 404 while the `/dropdown` variants return `[]`.
- Server errors are returned as 500 with the exception text in `detail`.
- Student and Parent: 403 on every endpoint.

**Unit-testable logic.**
- `StateCreate`, `DistrictCreate`, `MandalCreate` schema defaults (`is_active` True, `code` None).
- `check_state_name_unique` (exclude id), `delete_state` and `delete_district` dependency messages with fake counts.
- `get_all_states` paging arithmetic (`has_next`).
- Cache decorator: location dropdown cached per tenant; the no-op invalidation (documents staleness).
- Web and mobile cascade clearing (changing state clears district and mandal) and the mobile Locations screen flat API call.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-12-U01 | [backend] `StateCreate(name="X")` | `is_active` True, `code` None | passing |
| TC-MST-12-U02 | [backend] `check_state_name_unique` with a fake row of the same name, and with `exclude_id` equal to that row | 400 `State name 'X' already exists`; no error | passing |
| TC-MST-12-U03 | [backend] `delete_state` with 2 fake districts; `delete_district` with 3 fake mandals | 400 messages ending `delete districts first.` and `delete mandals first.` | passing |
| TC-MST-12-U04 | [backend] `get_all_states` `has_next` for (skip 0, limit 100, 150 rows) | True | passing |
| TC-MST-12-U05 | [backend] Call `invalidate_cache("states_dropdown")` after caching a states dropdown | Cached value remains (unknown cache type, no-op) | passing |
| TC-MST-12-U06 | [web] State cascade handler with state changed from S1 to S2 | District and mandal values reset to empty | blocked: needs the state cascade handler exported (inline in the web location form components) |
| TC-MST-12-A01 | Admin `POST /states` `{name:"QA-State", code:"QS"}` | 201 `{id,name,code,is_active:true}` | passing |
| TC-MST-12-A02 | POST a duplicate state name; rename another state to it | 400 `State name 'QA-State' already exists` each | passing |
| TC-MST-12-A03 | `GET /states` default and `?active_only=true&limit=1` | `{items,total_count,has_next}` ordered by name; second only active, 1 item | passing |
| TC-MST-12-A04 | `GET /states?limit=0`, `?limit=1001`, `?skip=-1` | 422 each | passing |
| TC-MST-12-A05 | `GET /states/dropdown` with one active, one inactive state | Active only `{id,name,code}`; `?active_only=false` both | passing |
| TC-MST-12-A06 | `GET /states/{id}`, random uuid | 200; 404 `State with id ... not found` | passing |
| TC-MST-12-A07 | `PUT /states/{id}` `{name:"QA-State-2", is_active:false}` | 200 with changes | passing |
| TC-MST-12-A08 | `DELETE /states/{id}` with no districts; with districts | 200 `{message:"State deleted successfully"}`; 400 `... has 1 district(s)` | passing |
| TC-MST-12-A09 | `POST /districts` `{state_id, name:"QA-District"}`; with a random `state_id` | 201; 404 `State with id ... not found` | passing |
| TC-MST-12-A10 | `GET /states/{id}/districts`, `/districts/dropdown`; with a random state id | Lists (dropdown items include `state_id`); 404 for the list and `[]` for the dropdown | passing |
| TC-MST-12-A11 | `GET /districts/{id}`, `PUT /districts/{id}` re-parent to another state, `PUT` re-parent to a random state | 200; 200 with new `state_id`; 404 | passing |
| TC-MST-12-A12 | `DELETE /districts/{id}` with mandals; without | 400 `... has N mandal(s)`; 200 `{message:"District deleted successfully"}` | passing |
| TC-MST-12-A13 | `POST /mandals` `{district_id, name:"QA-Mandal"}`; random `district_id` | 201; 404 | passing |
| TC-MST-12-A14 | `GET /districts/{id}/mandals`, `/mandals/dropdown`; random district | Lists (dropdown items include `district_id`); 404 and `[]` | passing |
| TC-MST-12-A15 | `GET`, `PUT`, `DELETE /mandals/{id}` valid and random uuid | 200 and 200 `{message:"Mandal deleted successfully"}`; 404 each | passing |
| TC-MST-12-A16 | Read matrix: states list, all dropdowns, all gets as Admin, Staff, Teacher | 200 | passing |
| TC-MST-12-A17 | Same reads as Student and Parent | 403 each | passing |
| TC-MST-12-A18 | Write matrix: POST, PUT, DELETE on states, districts, mandals as Staff, Teacher, Student, Parent | 403 each; Admin 2xx | passing |
| TC-MST-12-A19 | No Authorization header on every endpoint | 401 | passing |
| TC-MST-12-A20 | Shared data: state created via tenant A | Visible in tenant B `GET /states` and dropdown (no tenant scoping) | passing |
| TC-MST-12-A21 | Create a state then call the states dropdown after an earlier call within 5 minutes | New state missing until the TTL expires (invalidation is a no-op; documents current behaviour) | passing |
| TC-MST-12-A22 | `POST /auth/seed/location-data` without a token, twice, on an empty location table | 201 both times; first run reports `total_states` 5, the repeat reports `total_states` 0 | skipped: The seed writes five states with districts and mandals into the shared location tables used by every tenant an... |
| TC-MST-12-A23 | 31 POSTs within a minute (limiter enabled) | The 31st returns 429 | skipped: The test API runs with rate limiting disabled, so the 429 cannot be produced |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-12-E01 | P1 | Web | Admin | Location seed run once (`POST /api/v1/auth/seed/location-data`); qa_manual has no states before that | 1. Open Students > Admission and start a new admission.<br>2. On the address step open "State (Optional)" and choose "Telangana".<br>3. Open "District (Optional)". | District lists Telangana districts only; "Mandal (Optional)" stays empty until a district is chosen | planned |
| TC-MST-12-E02 | P2 | Web | Admin | Location seed run | 1. Choose a state, a district and a mandal.<br>2. Change the state to "Karnataka". | District and mandal clear | planned |
| TC-MST-12-E03 | P2 | Mobile | Admin | Location seed run | 1. Open the mobile admission form address fields.<br>2. Choose state, district, mandal; change the state. | Same cascade and clearing as web | planned |
| TC-MST-12-E04 | P3 | Mobile | Admin | None | 1. Open `/masters/locations` by URL. | Screen "Locations" with "0 locations" and "No Locations Found - Add your first location to get started" (the flat list call returns 404) | blocked: mobile Locations screen calls a missing endpoint (Known gaps 14); this step only records it |
| TC-MST-12-E05 | P3 | Mobile | Admin | None | 1. On `/masters/locations` add a location "QA Loc" and save. | Location is created and listed | blocked: the flat create endpoint does not exist, the save shows "Create Failed" (Known gaps 14) |
| TC-MST-12-E06 | P3 | Mobile | Admin | None | 1. On `/masters/locations` open add, leave the name empty, save. | Toast "Validation - Location name is required" | planned |

---

## F13 Castes and sub-castes

**Purpose.** Castes and their sub-castes are per-school lookup lists that feed the admission form's caste then sub-caste dropdowns. An admin seeds the defaults once and can extend or edit them through the API.

**Roles and permissions.** Create: `castes:create`. Update: `castes:update`. Delete: `castes:delete`. Paged list: `castes:list`. Dropdowns, sub-caste lists and single reads: `castes:read`. Admin all; Staff and Teacher read and list; Student and Parent none. The seed endpoint requires the role name `Admin`.

**Preconditions.** The tenant seed has been run (`POST /api/v1/auth/seed/caste-data`) or castes were created through the API; an empty dropdown means the seed was never run.

**Steps, web.** No management screen. The admission form (Students > Admission, student step, fields "Caste (Optional)" and "Sub Caste (Optional)") loads `GET /masters/castes/dropdown`, then `GET /masters/castes/{id}/sub-castes/dropdown` when a caste is chosen; changing the caste clears the sub-caste.

**Steps, mobile.** The admission form uses `castesApi.getCastesDropdown` and `getSubCastesDropdown` with the same cascade. There is no mobile management screen.

**Expected results.** Dropdowns list active castes and the chosen caste's active sub-castes. The seed creates five castes with 18 sub-castes in total.

**API endpoints.** Prefix `/api/v1/masters/castes`.
- `POST /` `{name, code?, is_active=true}` (201). `GET /` query `skip=0`, `limit=100` (1 to 1000), `active_only=false` -> `{items,total_count,has_next}`. `GET /dropdown` query `active_only=true` -> `[{id,name,code}]`. `GET /{caste_id}`, `PUT /{caste_id}`, `DELETE /{caste_id}`.
- `POST /sub-castes` `{caste_id, name, code?, is_active}` (201). `GET /{caste_id}/sub-castes` (all, `active_only=false`). `GET /{caste_id}/sub-castes/dropdown` -> `[{id,name,code,caste_id}]`. `GET /sub-castes/{id}`, `PUT /sub-castes/{id}`, `DELETE /sub-castes/{id}`.
- `POST /api/v1/auth/seed/caste-data` (Admin) -> 201 with `details.castes_created` and `sub_castes_created`.

**Rules and validations.**
1. Caste `name` is unique per tenant (database constraint and service check): 400 `Caste name '<name>' already exists` on create and rename. Sub-caste names are not checked for duplicates.
2. `name` at most 100, `code` at most 20.
3. A sub-caste needs an existing caste (404 `Caste with id ... not found`); updating `caste_id` checks the new parent.
4. Deleting a caste is refused while students use it (400 `... being used by N student(s)...`) or it has sub-castes (400 `... has N sub-caste(s). Please delete sub-castes first.`). Deleting a sub-caste is refused while students use it.
5. The seed adds General (General), OBC (OBC-A, OBC-B, OBC-C, OBC-D), SC (Adi Andhra, Adi Dravida, Mala, Madiga, Chamar, Pasi), ST (Chenchu, Konda Reddy, Koya, Gond, Bhil, Santhal) and EWS (EWS). Codes are the first three letters upper-cased. It skips rows that exist, so re-running creates nothing and never re-enables a deactivated row.
6. Dropdown invalidation on writes is a no-op; changes appear after the 5-minute cache TTL.

**Error and edge cases.**
- Unknown ids: 404 `Caste with id ... not found` or `Sub-caste with id ... not found`.
- Seed as a non-Admin role: 403 `Only administrators can seed data`.
- Student and Parent: 403 on every endpoint.

**Unit-testable logic.**
- `CasteCreate` and `SubCasteCreate` schemas.
- `check_caste_name_unique` with exclude id; `delete_caste` dependency messages (students, sub-castes) and `delete_sub_caste` student check, with fake counts.
- Seed data builder: 5 castes, 18 sub-castes, code derivation (`name[:3].upper()`; sub-castes shorter than 3 characters use the whole name upper-cased).
- Web and mobile cascade clearing.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-13-U01 | [backend] `CasteCreate(name="X")` | `is_active` True, `code` None | passing |
| TC-MST-13-U02 | [backend] `check_caste_name_unique` with a fake duplicate; with `exclude_id` equal to it | 400 `Caste name 'X' already exists`; no error | passing |
| TC-MST-13-U03 | [backend] `delete_caste` with 2 fake students; then 0 students and 3 sub-castes | 400 `... being used by 2 student(s)`; 400 `... has 3 sub-caste(s)` | passing |
| TC-MST-13-U04 | [backend] Seed data structure | 5 castes and 18 sub-castes; code for `General` is `GEN`, for `SC` is `SC` | passing |
| TC-MST-13-U05 | [web] Caste cascade handler when caste changes | Sub-caste value resets to empty | blocked: needs the caste cascade handler exported (inline in the web admission form components) |
| TC-MST-13-A01 | Admin `POST /api/v1/auth/seed/caste-data` on a tenant without castes | 201; `castes_created` lists 5 names; `sub_castes_created` has 18 entries | passing |
| TC-MST-13-A02 | Run the seed a second time | 201; both lists empty | passing |
| TC-MST-13-A03 | Seed as Staff, Teacher, Student, Parent; without a token | 403 `Only administrators can seed data` for each role; 401 without a token | passing |
| TC-MST-13-A04 | Admin `POST /` `{name:"QA-Caste", code:"QC"}` | 201 `{id,name,code,is_active:true}` | passing |
| TC-MST-13-A05 | POST a duplicate caste name; rename another caste to it | 400 `Caste name 'QA-Caste' already exists` each | passing |
| TC-MST-13-A06 | `GET /` default, `?active_only=true`, `?limit=0`, `?limit=1001` | Paged object; active filter honoured; 422 for the bounds | passing |
| TC-MST-13-A07 | `GET /dropdown` with one inactive caste | Active castes `{id,name,code}`; `?active_only=false` includes it | passing |
| TC-MST-13-A08 | `GET /{id}`, `PUT /{id}`, random uuid | 200; 200 updated; 404 `Caste with id ... not found` | passing |
| TC-MST-13-A09 | `POST /sub-castes` `{caste_id, name:"QA-Sub"}`; random `caste_id` | 201; 404 | passing |
| TC-MST-13-A10 | POST two sub-castes with the same name under one caste | Both 201 (no duplicate check) | passing |
| TC-MST-13-A11 | `GET /{caste}/sub-castes` and `/sub-castes/dropdown` | All rows (`active_only=false` default) and active `{id,name,code,caste_id}` | passing |
| TC-MST-13-A12 | `GET /sub-castes/{id}`, `PUT /sub-castes/{id}` re-parent to another caste and to a random caste | 200; 200; 404 | passing |
| TC-MST-13-A13 | `DELETE /{caste}` with sub-castes; after deleting them | 400 `... has N sub-caste(s)`; 200 `{message:"Caste deleted successfully"}` | passing |
| TC-MST-13-A14 | `DELETE /{caste}` for a caste used by a student (fixture) | 400 `... being used by 1 student(s)`; caste intact | passing |
| TC-MST-13-A15 | `DELETE /sub-castes/{id}` unused; random uuid | 200 `{message:"Sub-caste deleted successfully"}`; 404 | passing |
| TC-MST-13-A16 | Read matrix: list, dropdowns, gets as Admin, Staff, Teacher | 200 | passing |
| TC-MST-13-A17 | Same reads as Student and Parent | 403 each | passing |
| TC-MST-13-A18 | Write matrix: POST, PUT, DELETE for castes and sub-castes as Staff, Teacher, Student, Parent | 403 each; Admin 2xx | passing |
| TC-MST-13-A19 | No Authorization header on every endpoint | 401 | passing |
| TC-MST-13-A20 | Tenant isolation: castes seeded in tenant A | Absent from tenant B `GET /`, `/dropdown`; B can create `General` | passing |
| TC-MST-13-A21 | Create a caste after an earlier dropdown call within 5 minutes | Caste missing from the dropdown until the TTL expires (documents the no-op invalidation) | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-13-E01 | P1 | Web | Admin | Caste seed run as Admin in qa_manual (`POST /api/v1/auth/seed/caste-data`) | 1. Open Students > Admission and start a new admission.<br>2. Open "Caste (Optional)". | Lists General, OBC, SC, ST, EWS | planned |
| TC-MST-13-E02 | P2 | Web | Admin | Caste seed run | 1. Choose "SC" and open "Sub Caste (Optional)".<br>2. Choose a sub-caste, then change the caste to "ST". | SC lists Adi Andhra, Adi Dravida, Mala, Madiga, Chamar, Pasi; changing the caste clears the sub-caste | planned |
| TC-MST-13-E03 | P3 | Web | Admin | qa_manual before the caste seed (the current state) | 1. Open a new admission and open "Caste (Optional)". | The list is empty | planned |
| TC-MST-13-E04 | P2 | Mobile | Admin | Caste seed run | 1. Open the mobile admission form.<br>2. Choose a caste, then a sub-caste, then change the caste. | Same lists and clearing as web | planned |

---

## F14 School settings (School Registration)

**Purpose.** An admin records the school's name, contacts, address, board, academic-year label, logo and principal signature. There is exactly one settings row per tenant.

**Roles and permissions.** Read: `school_settings:read`. Save and upload: `school_settings:update`. Only Admin holds both. Menu: web sidebar Administration > School Settings (`/settings/school`) in the seeded catalog, or "School Registration" under Masters when the client injects it (not injected for the Teacher and Student roles, nor when the backend menu already has `/settings/school`, as in the seeded catalog). The seeded menu gives Administration > School Settings to Staff and Teacher too, so they can open the page but every call returns 403. Mobile: Home > Administration > School Settings (`/admin/school-settings`, gated on `school_settings:read`; for roles without it the card reads "No access - contact admin" and the route shows "Access Denied").

**Preconditions.** Admin session. Until the first save `GET /school-settings` returns 404, which both clients treat as "not configured".

**Steps, web.**
1. Open Administration > School Settings. Header "School Settings" with subtitle "Manage school registration and identity information" and an amber badge "Not configured yet" while no row exists.
2. "Basic Information": School Name ("e.g. Greenfield High School"), Contact No. ("9900099000", 10 digits), Alt. Contact No. ("9999900000", 10 digits), School Email ("school@example.com"), School Board (select "Select Board" with CBSE, ICSE, State Board, IGCSE, IB, Custom; choosing Custom shows "Custom Board Name" with "Enter board name"), Academic Year (placeholder "2026-27"), Installation Date. "Address": Street Address, City, District, State, PIN Code (6 digits), Country (prefilled "India").
3. Click "Save Settings" ("Saving..."). Toast "School settings saved successfully" or "Failed to save school settings". Field errors: "Must be exactly 10 digits", "Invalid email address", "Must be exactly 6 digits".
4. "School Logo" and "Principal Signature" boxes (hint "JPG, PNG, WebP, Max 2 MB"): "Upload" opens a file picker (jpg, jpeg, png, webp, maximum 2 MB). Toasts "School logo uploaded successfully" / "Failed to upload school logo" and "Principal signature uploaded successfully" / "Failed to upload signature". The preview shows the stored image.

**Steps, mobile.**
1. Home > Administration > School Settings. Screen "School Settings" with "Branding" (School Logo, Principal Signature pickers), "Basic Information" (School Name *, Contact Number, Alternate Contact Number, School Email, School Board, Academic Year, Installation Date "YYYY-MM-DD") and "Address" (Address, City, District, State, Pin Code, Country).
2. "Save Settings" ("Saving..."). Empty name: toast "Error - School name is required". Success "Saved - School settings have been updated."; failure "Save Failed". Image uploads: toasts "Uploaded - School logo has been updated." and "Uploaded - Principal signature has been updated."; failures "Upload Failed".

**Expected results.** The row is created on first save and updated afterwards; the stored image URLs start with `/media/<tenant id>/school/images/` (logo) or `/media/<tenant id>/school/signatures/` (signature) and the images render.

**API endpoints.** Prefix `/api/v1/school-settings` (no trailing slash).
- `GET ""` -> `SchoolSettingsRead` or 404 `School settings not configured yet.`
- `PUT ""` `{school_name?, contact_no?, alt_contact_no?, school_email?, address?, city?, state?, district?, pin_code?, country?, academic_year?, installation_date?, school_board?}` -> `SchoolSettingsRead`.
- `POST /upload-image` multipart field `photo` -> `SchoolSettingsRead` with `image_url`.
- `POST /upload-signature` multipart field `photo` -> `SchoolSettingsRead` with `principal_signature_url`.

**Rules and validations.**
1. `PUT` is a full replace of the text and date fields: any omitted field is stored as null (the web sends empty values as null, the mobile client sends empty strings). The image URLs change only through the upload endpoints. First `PUT` creates the row (upsert).
2. The API has no format validation of its own. Column lengths: name 255, contacts 20, email 255, address 500, city, state, district, country, board 100, pin code 10, academic year 50; longer values fail with 500 `An error occurred while saving school settings.`. The 10-digit, 6-digit and email rules are client-side only.
3. Uploads accept the extensions `.jpg`, `.jpeg`, `.png`, `.webp` only (case-insensitive, by file name): otherwise 400 `Only jpg, png, webp files are allowed`. A file larger than 2 MiB (2,097,152 bytes) is 400 `File size must not exceed 2 MB`; exactly 2,097,152 bytes is accepted. A missing `photo` part is 422.
4. A file is stored as `media/<tenant id>/school/images/school_image_url.<ext>` or `media/<tenant id>/school/signatures/school_principal_signature_url.<ext>` (fixed name per field and extension, so a re-upload with the same extension overwrites; a different extension leaves the old file behind). If no row exists the upload creates one holding only the URL.
5. A caller with no grant gets 403; uploads need `update`.

**Error and edge cases.**
- Web and mobile treat 404 on load as null (blank form).
- Image extension is checked, not the content.
- `PUT` followed by a read in the same request uses `commit` then `refresh` (against the repo rule) but works.
- Teacher, Staff, Student and Parent: 403 on all four endpoints. On web the seeded Administration menu still lists School Settings for Staff and Teacher (the page opens with "Not configured yet" and a blank form); Student and Parent have no entry.

**Unit-testable logic.**
- `SchoolSettingsUpdate` schema (all optional; `installation_date` must be a valid date).
- `upsert_settings` with a fake session: creates when none, replaces fields (omitted become None) when one exists, leaves image URLs alone.
- `_upload_file`: extension allow-list, size boundary (2 MiB and 2 MiB + 1), saved path and URL string including the tenant id, creation of a row when none exists.
- Web zod schema (10 digits, 6 digits, email) and `onSubmit` null mapping; custom board handling.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-14-U01 | [backend] `SchoolSettingsUpdate()` with no fields | Valid; all None | passing |
| TC-MST-14-U02 | [backend] `SchoolSettingsUpdate(installation_date="2026-13-40")` | Validation error | passing |
| TC-MST-14-U03 | [backend] `upsert_settings` on an existing fake row with payload `{school_name:"A"}` | `school_name` "A"; every other text field set to None; `image_url` unchanged | passing |
| TC-MST-14-U04 | [backend] `_upload_file` with `logo.gif`; with `logo.PNG` | 400 `Only jpg, png, webp files are allowed`; accepted | passing |
| TC-MST-14-U05 | [backend] `_upload_file` with 2,097,152 bytes and 2,097,153 bytes | Accepted; 400 `File size must not exceed 2 MB` | passing |
| TC-MST-14-U06 | [backend] `_upload_file` field `image_url`, tenant id T, extension `.png` | File at `media/T/school/images/school_image_url.png`; URL `/media/T/school/images/school_image_url.png` | passing |
| TC-MST-14-U07 | [web] zod schema with contact `12345`, pin `12`, email `a@b` | Errors "Must be exactly 10 digits", "Must be exactly 6 digits", "Invalid email address" | blocked: needs the zod schema exported from web/src/pages/settings/SchoolSettings.tsx |
| TC-MST-14-U08 | [web] Submit mapping with empty strings and board `Custom` plus custom text `Open Board` | Empty values sent as null; `school_board` sent as `Open Board` | blocked: needs the submit mapping exported from web/src/pages/settings/SchoolSettings.tsx |
| TC-MST-14-A01 | Admin `GET /school-settings` on a fresh tenant | 404 `School settings not configured yet.` | passing |
| TC-MST-14-A02 | Admin `PUT` with name, contact, board `CBSE`, pin `503001` | 200 `SchoolSettingsRead` with `id`; follow-up GET returns the same | passing |
| TC-MST-14-A03 | `PUT` again with only `{school_name:"B"}` | 200; `school_name` "B"; contact, board and pin null (full replace) | passing |
| TC-MST-14-A04 | `PUT` with a 256-character `school_name` | 500 `An error occurred while saving school settings.` | passing |
| TC-MST-14-A05 | `PUT {}` | 200; all text fields null | passing |
| TC-MST-14-A06 | `POST /upload-image` with a 10 KB `logo.png` | 200; `image_url` starts `/media/<tenant id>/school/images/`; the URL serves the bytes | known defect: TEN-MEDIA-CSCHEMA: /media/<tenant>/... |
| TC-MST-14-A07 | `POST /upload-signature` with a `.webp` file | 200; `principal_signature_url` starts `/media/<tenant id>/school/signatures/` | passing |
| TC-MST-14-A08 | Upload `notes.pdf`; `logo.gif` | 400 `Only jpg, png, webp files are allowed` each | passing |
| TC-MST-14-A09 | Upload exactly 2,097,152 bytes and 2,097,153 bytes | 200; 400 `File size must not exceed 2 MB` | passing |
| TC-MST-14-A10 | Upload without the `photo` part | 422 | passing |
| TC-MST-14-A11 | Upload on a tenant with no settings row | 200; row created holding only the URL; `school_name` null | skipped: qa_school_b already holds a settings row, so the create-on-upload path cannot be reached |
| TC-MST-14-A12 | Upload a `.png` then a `.jpg` for the logo | Second URL ends `.jpg`; first file still exists on disk (documents leftover) | known defect: TEN-MEDIA-CSCHEMA: /media/<tenant>/... |
| TC-MST-14-A13 | `PUT` after an upload | `image_url` unchanged | passing |
| TC-MST-14-A14 | Role matrix: `GET`, `PUT`, both uploads as Staff, Teacher, Student, Parent | 403 each; Admin 200 | passing |
| TC-MST-14-A15 | No Authorization header on all four endpoints | 401 | passing |
| TC-MST-14-A16 | Tenant isolation: tenant B `GET` after tenant A saved; both tenants upload a logo | B gets 404 (or its own row); files and URLs are in separate `media/<tenant id>/` folders | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-14-E01 | P2 | Web | Admin | School settings never saved in qa_manual (`GET /school-settings` is 404, the current state) | 1. Sign in as Admin.<br>2. Open Administration > School Settings. | Badge "Not configured yet"; empty fields; Country shows "India" | planned |
| TC-MST-14-E02 | P1 | Web | Admin | TC-MST-14-E01 state | 1. Enter School Name "QA School", Contact No. "9900099000", School Board "CBSE", PIN Code "503001".<br>2. Click "Save Settings".<br>3. Reload the page. | Toast "School settings saved successfully"; the badge disappears; values persist | planned |
| TC-MST-14-E03 | P2 | Web | Admin | None | 1. Enter Contact No. "12345", PIN Code "12", School Email "bad".<br>2. Click "Save Settings". | Inline errors "Must be exactly 10 digits", "Must be exactly 6 digits", "Invalid email address"; no request | planned |
| TC-MST-14-E04 | P3 | Web | Admin | None | 1. Choose School Board "Custom", type "QA Open Board" in "Custom Board Name".<br>2. Click "Save Settings" and reload. | The select shows Custom with "QA Open Board" | planned |
| TC-MST-14-E05 | P2 | Web | Admin | A png under 2 MB | 1. Under "School Logo" click "Upload" and choose the png. | Toast "School logo uploaded successfully"; the preview shows the image (may stay blank, Known gaps in the module doc: media URLs need auth) | planned |
| TC-MST-14-E06 | P3 | Web | Admin | A 3 MB png | 1. Under "Principal Signature" click "Upload" and choose it. | Toast "Failed to upload signature"; preview unchanged | planned |
| TC-MST-14-E07 | P3 | Web | Admin | A pdf file | 1. Under "School Logo" click "Upload", switch the picker to all files, choose the pdf. | Toast "Failed to upload school logo" | planned |
| TC-MST-14-E08 | P2 | Web | Teacher | Seeded student Advik Mehta for the second check | 1. Sign in as Teacher, open Administration > School Settings.<br>2. Click "Save Settings".<br>3. Sign in as the student and check the sidebar. | Teacher: form opens with "Not configured yet" and no data (read 403); Save shows "Failed to save school settings". Student: no Administration entry | planned |
| TC-MST-14-E09 | P3 | Mobile | Admin | None | 1. Open Home > Administration > School Settings.<br>2. Clear "School Name *" and tap "Save Settings". | Toast "Error - School name is required" | planned |
| TC-MST-14-E10 | P1 | Mobile | Admin | None | 1. Open School Settings.<br>2. Enter School Name "QA School M", Contact Number "9900099001".<br>3. Tap "Save Settings", leave and reopen the screen. | Toast "Saved - School settings have been updated."; values persist | planned |
| TC-MST-14-E11 | P3 | Mobile | Admin | An image on the device | 1. Tap the "School Logo" picker and choose the image. | Toast "Uploaded - School logo has been updated." and preview | planned |
| TC-MST-14-E12 | P2 | Mobile | Teacher | None | 1. Sign in as Teacher, open Home > Administration.<br>2. Open `/admin/school-settings` by URL. | The School Settings card reads "No access - contact admin"; the route shows "Access Denied" | planned |

---

## F15 Masters hub, menu entries and dropdown caching

**Purpose.** The Masters hub lists the master screens the user is allowed to open, and the shared dropdown endpoints behind every picker are cached in memory so repeated reads are cheap. This feature documents both, because the cache explains when edits appear in pickers.

**Roles and permissions.** The hub shows the children of the "Masters" menu node granted to the role's menu (Admin, Staff and Teacher: all; Student and Parent: none, no Masters entry). Cached dropdown endpoints need the permission of their feature (F01, F06 to F08, F12, F13). Salary ranges and admission types are fixed lists.

**Preconditions.** Logged in with a role that has the Masters menu; the tenant menu catalog is seeded.

**Steps, web.** Sidebar > Masters opens `/masters`: header "Masters Dashboard" with subtitle "Configure and manage all master data for the school system", section "Masters Sections", one card per Masters child in the backend menu (seeded catalog: Academic Years, Classes and Sections, Subject Categories, Subjects, Class Subject Mappings, Holidays, Parents, Roles and Permissions), each with a description (known names use fixed text, others "Manage <name in lower case>"). Clicking a card with a path navigates to it; cards without a path are dimmed.

**Steps, mobile.** Home > "Masters" module card opens the hub (`/masters`): a banner "Masters Dashboard" ("Configure and manage all master data for the school system") and the label "MASTERS SECTIONS" with a two-column grid of cards (icon, name, description, arrow). Cards come from the backend menu; before the menu loads, a fallback list (Academic Years, Classes & Sections, Staff Management, Subject Categories, Subjects, Class Subject Mappings, Parents, Holidays, Timetable Management, Locations, Roles & Permissions) is filtered by `read` or `list` permission on each card's resource. With the seeded menu the cards are the same eight as on web. Student and Parent have no Masters card on Home.

**Expected results.** Each role sees only the cards its menu grants; navigation lands on the matching screen. After an edit, a dropdown shows the change at once only when the write invalidates the cache; otherwise within 5 minutes.

**API endpoints.** Cached reads: `GET /masters/academic_years/` and `/dropdown`, `GET /masters/class_sections/dropdown`, `class-list`, `section-list`, `by_class_id/{id}/sections`, `sections-by-class-name`, `GET /masters/subjects/dropdown`, `/categories/{id}/subjects[/dropdown]`, `GET /masters/subject_categories/categories/dropdown`, `GET /masters/holidays/dropdown`, the location and caste dropdowns. Fixed lists: `GET /parents/salary-ranges/dropdown` (F11) and `GET /students/admission/admission-types/dropdown` (Students module).

**Rules and validations.**
1. The cache is a per-process `TTLCache` (max 1000 entries, 300 seconds). The key is `dropdown_<function name>:<tenant id>:<hash of arguments>`, so tenants never share entries. Other workers keep their own copy and can serve stale data until expiry.
2. `invalidate_cache("dropdown", "<pattern>")` removes keys that contain the pattern. Writes that invalidate: academic years (create, update, deactivate, permanent delete), classes (create, update, delete: classes and sections), sections (add only), subjects (create only), subject categories (create, update, delete), holidays (create, update, activate, deactivate).
3. Writes that do not invalidate: section update and delete, subject update and deactivate, and all location and caste writes (their calls pass the pattern as the cache type, so they do nothing).
4. Dropdown items are `{id, name}` (academic years `{id, title}`, locations also `code`, `state_id` or `district_id`); fixed lists return `{value, label}` (salary ranges also `display`).
5. Mobile dropdown search crashes if any option label is undefined; clients map `label: x.name || ''`. Web dropdown `value` accepts a string, number or undefined, never null.
6. Cards on the web hub use `menuItems` from the login response; menu changes need a re-login.

**Error and edge cases.**
- No Masters node in the menu (Student, Parent): no web sidebar entry and no mobile Home card; typed URLs open the pages, which show data where the role has a read grant and 403 errors elsewhere.
- Hub card without a `path` is not clickable.
- A stale dropdown after a section rename or subject edit clears itself after 5 minutes or on the next invalidating write of the same kind.

**Unit-testable logic.**
- `cache_dropdown`: hit and miss, TTL expiry, tenant separation (key includes tenant), key stability for equal arguments.
- `invalidate_cache`: pattern removal, tenant-filtered removal, full clear, unknown cache type (warning, no removal).
- Web `descriptionMap` lookup with fallback text; mobile hub card source selection (backend children vs permission-filtered fallback).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-MST-15-U01 | [backend] Call a `cache_dropdown` function twice with the same fake session and args | Second call served from cache (function body runs once) | passing |
| TC-MST-15-U02 | [backend] Same call with a fake session whose `info["tenant_id"]` differs | Cache miss; separate entries per tenant | passing |
| TC-MST-15-U03 | [backend] Entry older than the TTL (patch time) | Recomputed | passing |
| TC-MST-15-U04 | [backend] `invalidate_cache("dropdown","classes")` with class and subject keys cached | Only keys containing `classes` removed | passing |
| TC-MST-15-U05 | [backend] `invalidate_cache("dropdown", tenant="t1")` | Only keys containing `:t1:` removed | passing |
| TC-MST-15-U06 | [backend] `invalidate_cache("states_dropdown")` | Logs unknown type; nothing removed | passing |
| TC-MST-15-U07 | [web] Hub description lookup for `Subjects` and for `Classes and Sections` | Fixed text "Define subjects and subject details"; fallback "Manage classes and sections" | blocked: needs descriptionMap exported from web/src/routes/_app/masters/index.tsx |
| TC-MST-15-U08 | [mobile] Hub source with an empty backend menu and a role with `read` on `academic_years` only | Fallback list contains only "Academic Years" | blocked: needs the fallback list builder exported from mobile/app/(tabs)/masters.tsx |
| TC-MST-15-A01 | Create an academic year, class, subject, category and holiday, each followed immediately by its dropdown | Each dropdown shows the new row (invalidation works) | passing |
| TC-MST-15-A02 | Rename a subject (`PUT`) then read `GET /masters/subjects/dropdown` | Old name until TTL (no invalidation) | passing |
| TC-MST-15-A03 | Deactivate a subject then `GET /masters/subjects/dropdown` | Subject still listed until TTL | passing |
| TC-MST-15-A04 | Add a section then `GET /by_class_id/{id}/sections`; rename a section then read again | New section present; renamed section stale | passing |
| TC-MST-15-A05 | Tenant separation: create `QA-X` subject in tenant A, read dropdown in tenant B twice | Never contains `QA-X` | passing |
| TC-MST-15-A06 | `GET /parents/salary-ranges/dropdown` repeated | Identical fixed list, not affected by cache or tenant | passing |
| TC-MST-15-A07 | Dropdown items shape: academic years, classes, sections, subjects, categories, holidays | Academic years `{id,title}`; the rest `{id,name}` | passing |

UI test cases (manual and automated, tenant `qa_manual`):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-MST-15-E01 | P1 | Web | Admin | Seeded menu catalog | 1. Sign in as Admin.<br>2. Open `/masters` (sidebar Masters). | "Masters Dashboard", "MASTERS SECTIONS" and cards Academic Years, Classes and Sections, Subject Categories, Subjects, Class Subject Mappings, Holidays, Parents, Roles and Permissions, each with its description | planned |
| TC-MST-15-E02 | P2 | Web | Admin | None | 1. On `/masters` click the "Subjects" card. | Navigates to `/masters/subjects` | planned |
| TC-MST-15-E03 | P2 | Web | Teacher | None | 1. Sign in as Teacher, open `/masters`.<br>2. Repeat as Staff. | The same eight cards (menu grant) | planned |
| TC-MST-15-E04 | P2 | Web | Student | Seeded student Advik Mehta (002) and parent venkat.raju@example.com | 1. Sign in as each and check the sidebar. | No "Masters" sidebar entry | planned |
| TC-MST-15-E05 | P1 | Mobile | Admin | Seeded menu catalog | 1. Sign in as Admin, tap the "Masters" card on Home. | Banner "Masters Dashboard", label "MASTERS SECTIONS", one card per Masters child (same eight as web) | planned |
| TC-MST-15-E06 | P2 | Mobile | Admin | None | 1. On the hub tap "Academic Years". | Opens the Academic Years screen | planned |
| TC-MST-15-E07 | P2 | Mobile | Student | Seeded student Advik Mehta (002) and parent venkat.raju@example.com | 1. Sign in as each and look at Home. | No Masters card (only Students, Exam Management, Fee Management) | planned |

---

## Known gaps

Defects and doc/code mismatches found while writing this page (the code behaviour is what the test cases above assert). Each should be tracked in `docs/modules/masters.md` when fixed or accepted.

1. **`POST /parents/` cannot create a parent.** Fixed (2026-10-02): the endpoint now creates the linked Parent-role user (username email else phone, first-login flag, default parent password) and the parent in one transaction; duplicates are 409, missing email and phone is 400. Web Add and Edit no longer ask for a User ID and no longer send an empty email; mobile Add requires email or phone.
2. **Class and subject names cannot be reused across academic years.** Fixed (2026-10-02): uniqueness is now `(tenant_id, academic_year_id, name)` on classes and subjects (migration 0006), the services check duplicates per year. Name lookups that take only a class name (`sections-by-class-name`, `by-class-section`) now match the first class of that name across years.
3. **Subject length checks do not match the columns.** Fixed (2026-10-02): schema and service now enforce name 1 to 50 and short code at most 10.
4. **Seed gap for sections.** The default Admin grant has `sections:create` only. The web class page gates section Edit and Delete on `sections:update` and `sections:delete`, so those buttons are hidden for a default-seeded Admin (the API itself uses `classes:update` and `classes:delete`).
5. **Not-found handling is inconsistent.** Fixed (2026-10-02): academic year, class, section, subject and holiday services re-raise their 404 instead of wrapping it as 400 or 500.
6. **Mobile add-section posts a single object** to an endpoint that expects a list, so it always fails with 422.
7. **Bulk class-subject mapping replaces the set.** Fixed (2026-10-02): the bulk call only adds or updates the listed subjects and no longer deactivates the others; duplicate ids in a request are collapsed; migration 0007 adds unique indexes on (class, section, subject, year) and removes existing duplicate rows.
8. **`GET /masters/subjects/categories` returns 500** (response model mismatch). Fixed (2026-10-02): returns the plain list of `{id, name}`. `GET /subjects/by-academic-year/{id}` had the same defect and is fixed too.
9. **`GET /masters/class_sections/read_all` ignores `academic_year_id` and `active_only`**, returns 400 when empty. Fixed (2026-10-02): both filters are honoured (`active_only` defaults to false) and an empty result is `[]`.
10. **Year list limit.** The web store and the mobile `AcademicYearContext` call the academic year list without a limit (default 10, unordered), so more than 10 years cannot all be selected. The web academic year table also reads `total` while the API returns `total_count`.
11. **No date or length validation** on academic years and holidays, subject categories accept empty names. Fixed (2026-10-02): end before start is rejected for academic years and holidays, holiday colour must be `#rrggbb`, category names are trimmed and non-empty. Year overlap is still not checked.
12. **School settings uploads are tenant-scoped now.** The module doc says the upload path is not tenant-scoped; the code writes under `media/<tenant id>/school/...`. The doc should be corrected. A re-upload with a different extension leaves the previous file on disk.
13. **Parent search filters are ORed**, so combining `email` and `relation_to_student` widens instead of narrowing the result. Fixed (2026-10-02): filters are combined with AND.
14. **Mobile Locations screen is broken** (calls a flat `/masters/locations/` the API does not have) and has no menu entry in the seeded catalog.
15. **Dropdown cache invalidation gaps** for section update and delete, subject update and deactivate, and all caste and location writes.
16. **Doc update needed for permission aliases.** The module doc states the mobile screens gate on `timetables` and `holidays`; the mobile code uses `timetable_management` and `holiday_management` (correct). The web calendar still gates on `holidays` (see `docs/features/timetable-calendar.md`).
17. **Create endpoints are rate limited per client IP** (30 per minute, bulk mappings 10), which affects automated suites that create data quickly.
18. **Web search on server-paged master tables covers the current page only** (Academic Years, Subject Categories, Class Subject Mappings): a row on another page is reported as "0 of 5 results" / "No results found" until "Rows per page" is raised. Observed 2026-10-07.
19. **Mobile add-mapping "Select a Class" toast is unreachable**: the add button only appears after a class with unmapped subjects is chosen, so the validation in `handleBulkAdd` never fires (TC-MST-10-E10 obsolete).
