# Expense (EXP)

Expense records school spending. Admins define expense categories, types within a category, and departments; staff record expense transactions (one amount per transaction, optionally built from line items on the client) with a vendor, payment method and reference; transactions above the approval threshold wait for an approver who approves or rejects with a comment; attachments can be stored against a transaction; a hierarchical summary and category, type and trend reports show where the money went; a settings table and an audit trail exist but are mostly inert (settings are never read by the transaction flow and every audit write is disabled in code). Web and mobile both talk to the same `/api/v1/expense/*` endpoints. This page documents what the code and the running apps do on 2026-10-07, and where it disagrees with `docs/modules/expense.md` the code wins and the difference is listed under Known gaps.

_Last verified against code: 2026-10-07_

Conventions: test IDs follow `docs/testing/strategy.md` (`TC-EXP-<FF>-<P><NN>`; U unit, A API, E end to end). UI cases (E) use the manual format (Priority P1 smoke, P2 regression, P3 edge). Their preconditions refer to the seeded manual-test tenant `qa_manual` (`backend/scripts/seed_demo_data.py`): categories Infrastructure, Utilities, Academic Supplies, Transport and Fuel, Events and Functions; 11 types (for example Electricity Bill, Water Bill, Stationery, Fuel); departments Administration, Academics, Transport, Maintenance, Sports; 12 transactions in September 2026 with academic year 2026-2027 (5 approved, 2 rejected, 5 pending, of which only "Chart paper and markers for classrooms" needs no approval). Cases that approve or reject a seeded transaction consume it; reset `qa_manual` (`scripts/qa/setup_manual_tenant.py --reset`) before repeating them. New data a case creates starts with "QA ". Where a UI label or message contains the rupee sign or a dash character it is written here as "Rs" or a hyphen (plain text only), so match by meaning, not by character. Rate limits apply per user (categories/types/departments create 30 per minute, transaction create 50 per minute, approval 20 per minute, export 10 per minute); API tests that loop must stay under them or expect 429.

## Roles

Permissions are `(resource, action)` pairs on the role; the plan layer is not enforced at runtime (`docs/permissions.md`). Default grants from `backend/app/service/tenant/permission_catalog.py` (the QA tenant copies `test_tenant_schema`, so read the real matrix with the login response before asserting a role):

| Role | Expense access in the default catalog |
|---|---|
| Admin | `expense_categories`, `expense_types`, `expense_departments`, `expense_settings`: create, read, update, delete, list. `expense_transactions`: create, read, update, list, approve (no delete action exists). `expense_attachments`: create, read, update, delete. `expense_audit_logs`: read, delete. `expense_reports`: read, list, export. |
| Staff | `expense_categories`, `expense_types`, `expense_departments`: read, list. `expense_transactions`: create, read, list. `expense_attachments`: create, read. Nothing for settings, audit, reports, approve, update. |
| Teacher | None. |
| Student, Parent | None. |

Extra role-name rules inside the code: settings create, delete and reset also require the role name `admin`, `tenant_admin` or `super_admin` (case-insensitive); audit log delete requires the role name `super_admin` or `tenant_admin`, which no tenant role has, so even Admin gets 403 there.

## Feature index

| ID | Title |
|---|---|
| F01 | Expense overview and navigation |
| F02 | Expense categories |
| F03 | Expense types |
| F04 | Expense departments |
| F05 | Expense settings |
| F06 | Create an expense transaction (line items) |
| F07 | List, filter and view transactions |
| F08 | Edit a transaction |
| F09 | Delete a transaction (client action without a backend route) |
| F10 | Attachments |
| F11 | Approval rules, thresholds and status workflow |
| F12 | Pending approvals and approve or reject |
| F13 | Expense summary (Category, Type, Entries) |
| F14 | Expense reports (by category, by type, trend, quick summary, export) |
| F15 | Audit trail |

Menu paths. The Expense menu is tenant data. The QA tenants (`qa_school`, `qa_manual`) and the demo tenant use the demo catalog (`backend/scripts/seed_demo_catalog.py`): Expense with children Expense Categories, Expense Departments, Expense Types, Expense Transactions, Expense Approvals, Expense Reports, Expense Summary, Expense Audit, Expense Settings (verified on screen 2026-10-07). The Teacher role also gets the Expense menu, but every expense page shows Access Denied for it. The legacy test-tenant seed (`backend/scripts/seed_expense_menu_test_tenant.py`) used other labels (Overview, Categories, Types, Transactions, Pending Approvals, Summary, Audit Trail, Settings, Departments). Web routes: `/expense`, `/expense/categories`, `/expense/types`, `/expense/departments`, `/expense/transactions`, `/expense/approvals`, `/expense/summary`, `/expense/reports`, `/expense/audit`, `/expense/settings`. Steps below use the demo catalog labels. On mobile, the Dashboard "Expense" module opens the hub (/expense); Approvals, Reports, Audit and Settings are reached from the navigation drawer (Expense menu) or by URL.

---

## F01 Expense overview and navigation

**Purpose**: Land on one page that shows how many categories, types and transactions exist and links to the main expense screens.

**Roles and permissions**: Web page needs `expense_categories:list` or `expense_transactions:list` (shows "Access Denied" otherwise). Menu entry shown to roles whose `role_menu_permissions` include the Expense node (Admin, Staff by default). Mobile tab `expense` is shown when the user has any of `expense_categories`, `expense_transactions`, `expense_types` (read or list).

**Preconditions**: User logged in; at least one of the listed permissions.

**Steps, web**
1. Open Expense in the sidebar (route `/expense`). Page header "Expense Management", subtitle "Track, approve, and analyse all school expenses in one place".
2. Read the three stat cards: "Expense Categories", "Expense Types", "Total Transactions".
3. Under "Expense Sections", click a card or its "Open" button: Categories, Types, Transactions, Departments, Summary.

**Steps, mobile**
1. On the Dashboard tap the "Expense" module (route /expense). Banner "Expense Management" with subtitle "Track, manage and approve expenses".
2. Read stat cards "Expense Categories", "Expense Types", "Total Transactions".
3. Under "EXPENSE SECTIONS" tap Overview, Categories, Types, Transactions, Departments or Summary. A section without permission shows a lock icon, the text "No access - contact admin" and is disabled.

**Expected results**: Web counts equal the length of the arrays returned by `GET /expense/categories/`, `/types/` and `/transactions/` (each default page is 100 rows, so counts cap at 100). Approvals, Reports, Audit and Settings have no card on either overview; they are reached from the sidebar (web) or the navigation drawer (mobile).

**API endpoints**: `GET /expense/categories/`, `GET /expense/types/`, `GET /expense/transactions/` (all list endpoints, covered in F02, F03, F07).

**Rules and validations**: Counts come from plain arrays. Mobile reads `.total` from the same responses, which does not exist (see Known gaps), so mobile stat cards show 0.

**Error and edge cases**: No permission: web shows "Access Denied" with "You don't have permission to view the expense dashboard." (Teacher still sees the Expense menu entry); on mobile, opening the hub without grants shows every tile except Overview locked. Empty tenant: all counts 0.

**Unit-testable logic**: Count derivation `data?.length ?? 0` (web); navigation card list and permission gating `hasAccess` (mobile).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-01-U01 | Web count helper with `undefined` data for categories, types, transactions | Each count is 0 | blocked: web count derivation is inline in web/src/pages/expense/index.tsx; needs a helper exported |
| TC-EXP-01-U02 | Mobile section gating: `alwaysShow` Overview, others require `hasPermission(resource, 'list')` | Overview enabled for any user; Categories disabled when `expense_categories:list` is missing | blocked: mobile section gating is inline in mobile/app/(tabs)/expense.tsx; needs the helper exported |
| TC-EXP-01-A01 | `GET /expense/transactions/` with 101 transactions and no `limit` | Returns exactly 100 rows (default limit), so the web "Total Transactions" caps at 100 | passing |
| TC-EXP-01-A02 | Admin calls the three list endpoints used by the overview | All return 200 and JSON arrays | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-01-E01 | P1 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions; once QA transactions exist the counts cannot stay at 5, 11 and 12, so assert them relative to the API) | 1. Sign in as Admin.<br>2. Click "Expense" in the sidebar (route /expense).<br>3. Read the stat cards.<br>4. Click "Open" on the "Categories" card. | Header "Expense Management" with subtitle "Track, approve, and analyse all school expenses in one place"; stat cards Expense Categories 5, Expense Types 11, Total Transactions 12; under "Expense Sections" five cards Categories, Types, Transactions, Departments, Summary; step 4 opens /expense/categories. | passing |
| TC-EXP-01-E02 | P2 | Web | Teacher | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Teacher.<br>2. Open /expense (the Expense menu is still listed in the Teacher sidebar). | Panel "Access Denied" with "You don't have permission to view the expense dashboard."; no stat cards. | planned |
| TC-EXP-01-E03 | P2 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Click "Expense" in the sidebar. | Page "Expense Management" renders; the three stat cards show numbers; the five section cards are shown. | planned |
| TC-EXP-01-E04 | P2 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Admin on mobile.<br>2. On the mobile Dashboard tap the "Expense" module. | Banner "Expense Management" with "Track, manage and approve expenses"; stat cards "Expense Categories", "Expense Types", "Total Transactions"; "EXPENSE SECTIONS" lists Overview, Categories, Types, Transactions, Departments, Summary. | planned |
| TC-EXP-01-E05 | P3 | Mobile | Teacher | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Teacher on mobile.<br>2. Open the Expense hub (/expense).<br>3. Tap the "Departments" tile. | Overview is enabled; Categories, Types, Transactions, Departments and Summary show a lock icon and "No access - contact admin"; tapping Departments does not navigate. | planned |
| TC-EXP-01-E06 | P2 | Mobile | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Sign in as Admin on mobile.<br>2. On the mobile Dashboard tap the "Expense" module.<br>3. Read the three stat cards. | Cards show 5, 11 and 12, as on web. | blocked: mobile hub reads .total from plain-array list responses, so the cards always show 0 (Known gaps 12) |

---

## F02 Expense categories

**Purpose**: Maintain the top-level expense groups (for example Infrastructure, Utilities) that expense types belong to.

**Roles and permissions**: `expense_categories:create` (add), `:list` (list page, `GET /`), `:read` (dropdown and get by id), `:update` (edit), `:delete` (deactivate). Admin has all; Staff has read and list only; Teacher, Student, Parent none.

**Preconditions**: Permissions seeded for the tenant and the user logged in again after seeding (clients cache the permission map from the login response).

**Steps, web**
1. Open the Categories page (`/expense/categories`); the card title is "Expense Categories".
2. Click "New Category". Dialog "Create Category": field "Name *" (placeholder "Enter category name", max 100), "Description" (placeholder "Enter category description").
3. Click "Save". The button reads "Saving..." while pending. Toast "Category created successfully". A duplicate name shows the API message as an error toast ("Category with name '<name>' already exists") and the dialog stays open. "Cancel" with typed data asks "Discard changes?" ("Keep Editing", "Discard & Close").
4. Search with the box "Search categories..." (matches name and description). Click the column headers Name, Status or Created to sort (click cycles ascending, descending, none).
5. Row actions are unlabeled icons: pencil for edit (dialog "Edit Category") and trash for delete (confirm dialog "Delete Category": Are you sure you want to delete "<name>"? This may affect existing expense types.; confirm button "Delete"). Toast "Category deleted successfully".

**Steps, mobile**
1. Expense tab, "Categories" tile, screen "Expense Categories". Search box "Search categories...".
2. "New Category": modal "New Category" with "Name *" (placeholder "Enter category name"), "Description" (placeholder "Enter description (optional)"), "Active" switch, "Cancel", "Save". Empty name: toast "Error" "Name is required". Save shows "Category Created" with "<name>" has been saved. (edit: "Category Updated").
3. Card actions "Edit" and "Delete" (shown only with update or delete). Delete confirm title "Delete Category", button "Delete"; success "Deleted" with "<name>" has been deleted.; failure "Delete Failed" "Could not delete category."

**Expected results**: Category stored with `is_active = true`, `org_id` = tenant id; soft delete sets `is_active = false` and hides it from the list (default `active_only=true`) and the dropdown.

**API endpoints**
- `POST /expense/categories/` body `{name (1-100), description (max 300), is_active}` returns 201.
- `GET /expense/categories/?skip=0&limit=100&active_only=true` returns an array (newest first).
- `GET /expense/categories/dropdown` returns `[{id, name}]` sorted by name, active only.
- `GET /expense/categories/{category_id}`.
- `PUT /expense/categories/{category_id}` body: any of name, description, is_active.
- `DELETE /expense/categories/{category_id}` returns the category with `is_active=false`.

**Rules and validations**
- Name unique among active categories only, compared exactly (case-sensitive); a soft-deleted category's name can be reused. Duplicate: 400 with detail `{error_code: DUPLICATE_CATEGORY_NAME, message}`.
- A category can be deleted while it still has active types (the check is commented out); its types stay active.
- Query bounds: `skip >= 0`, `1 <= limit <= 1000`.
- Web form: name required, 2 to 100 characters, description max 500 (the backend allows 300; see Known gaps).

**Error and edge cases**: Unknown id 404 "Expense category not found"; malformed id 422; no token 401; role without grant 403 with "Permission not found in database: <Role> cannot <action> expense_categories". Whitespace-only name passes the backend (no trim) but the web form rejects it.

**Unit-testable logic**: `ExpenseCategoryCreate/Update` schema bounds; duplicate-name check restricted to active rows; update uniqueness excludes the row itself; soft delete; web `validateCategoryForm`.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-02-U01 | `ExpenseCategoryCreate(name="")` and a 101-char name | ValidationError; 100-char name accepted | passing |
| TC-EXP-02-U02 | Description of 300 and 301 characters | 300 accepted; 301 rejected | passing |
| TC-EXP-02-U03 | Service create with an active category "Utilities" present | Raises HTTPException 400 with `error_code DUPLICATE_CATEGORY_NAME` | passing |
| TC-EXP-02-U04 | Service create "Utilities" when the only existing "Utilities" has `is_active=False` | Succeeds (soft-deleted names are reusable) | passing |
| TC-EXP-02-U05 | Service create "utilities" when "Utilities" is active | Succeeds (comparison is case-sensitive) | passing |
| TC-EXP-02-U06 | Service update renaming a category to its own current name | No duplicate error | passing |
| TC-EXP-02-U07 | Service update renaming to the name of another active category | 400 DUPLICATE_CATEGORY_NAME | passing |
| TC-EXP-02-U08 | Service delete on a category that has active types | `is_active` becomes False; no exception | passing |
| TC-EXP-02-U09 | Web `validateCategoryForm`: "" , "A", 101 chars, description 501 chars | Errors "Category name is required", "Category name must be at least 2 characters", "Category name cannot exceed 100 characters", "Description cannot exceed 500 characters"; 100-char name and 500-char description pass | passing |
| TC-EXP-02-A01 | Admin `POST /expense/categories/` name "QA Infra", description "Buildings" | 201; body has id, name, description, `is_active=true`, created_at, updated_at | passing |
| TC-EXP-02-A02 | Create without Authorization header | 401 | passing |
| TC-EXP-02-A03 | Create with missing `name`; with name of 101 chars; with description of 301 chars | 422 each; 100-char name returns 201 | passing |
| TC-EXP-02-A04 | Create the same name twice | Second call 400, `detail.error_code = DUPLICATE_CATEGORY_NAME` | passing |
| TC-EXP-02-A05 | `GET /expense/categories/` after creating 3 | Array containing them, newest first; inactive excluded | passing |
| TC-EXP-02-A06 | `GET /expense/categories/?active_only=false` after deleting one | Deleted category present with `is_active=false` | passing |
| TC-EXP-02-A07 | `GET /expense/categories/?limit=2&skip=1`; `limit=0`; `limit=1001`; `skip=-1` | Page of at most 2 rows; the other three calls 422 | passing |
| TC-EXP-02-A08 | `GET /expense/categories/dropdown` | Array of `{id, name}` ordered by name ascending, active only | passing |
| TC-EXP-02-A09 | `GET /expense/categories/{id}` for an existing, an inactive, an unknown and a malformed id | 200, 200 (inactive still readable), 404 "Expense category not found", 422 | passing |
| TC-EXP-02-A10 | `PUT` name change; `PUT` to a duplicate active name; `PUT` unknown id | 200 with new name; 400 DUPLICATE_CATEGORY_NAME; 404 | passing |
| TC-EXP-02-A11 | `PUT {"is_active": false}` then dropdown | Category missing from dropdown | passing |
| TC-EXP-02-A12 | `DELETE` a category | 200, body `is_active=false`; no longer in list or dropdown | passing |
| TC-EXP-02-A13 | `DELETE` a category that still has an active type | 200; the type still `is_active=true` | passing |
| TC-EXP-02-A14 | Recreate a category with a deleted category's name | 201 | passing |
| TC-EXP-02-A15 | Role matrix `POST` (parametrised) | Admin 201; Staff, Teacher, Student, Parent 403 | passing |
| TC-EXP-02-A16 | Role matrix `GET /` and `GET /dropdown` and `GET /{id}` | Admin 200; Staff 200; Teacher, Student, Parent 403 | passing |
| TC-EXP-02-A17 | Role matrix `PUT` and `DELETE` | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-EXP-02-A18 | Tenant isolation: create in QA tenant A, list and get by id with a tenant B token | Not in B's list; get by id 404 | passing |
| TC-EXP-02-A19 | Token of tenant A with `cschema` header of tenant B | 403 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-02-E01 | P1 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Admin.<br>2. Click "Expense" > "Expense Categories".<br>3. Click "New Category".<br>4. Enter Name "QA Utilities", Description "QA monthly utility bills".<br>5. Click "Save". | Dialog "Create Category" closes; toast "Category created successfully"; row "QA Utilities" with Status Active and today's Created date; stored with is_active true. | passing |
| TC-EXP-02-E02 | P2 | Web | Admin | Seeded category "Utilities" (types Electricity Bill, Water Bill, Internet and Telephone) | 1. Open Expense > Expense Categories.<br>2. Click "New Category".<br>3. Enter Name "Utilities".<br>4. Click "Save". | Error toast "Category with name 'Utilities' already exists"; the dialog stays open; no second row. | planned |
| TC-EXP-02-E03 | P2 | Web | Admin | Category "QA Utilities" exists (TC-EXP-02-E01 done) | 1. Open Expense > Expense Categories.<br>2. Click the pencil icon in the "QA Utilities" row.<br>3. In "Edit Category" change Description to "QA utilities and power".<br>4. Click "Save". | Toast "Category updated successfully"; the row shows the new description. | planned |
| TC-EXP-02-E04 | P2 | Web | Admin | Category "QA Temp Category" exists with no types (create it as in TC-EXP-02-E01) | 1. Open Expense > Expense Categories.<br>2. Click the trash icon in the "QA Temp Category" row.<br>3. Read the confirm dialog.<br>4. Click "Delete". | Dialog "Delete Category" says Are you sure you want to delete "QA Temp Category"? This may affect existing expense types.; after Delete toast "Category deleted successfully" and the row disappears (stored is_active false). | planned |
| TC-EXP-02-E05 | P3 | Web | Admin | Seeded categories Academic Supplies, Events and Functions, Infrastructure, Transport and Fuel, Utilities | 1. Open Expense > Expense Categories.<br>2. Type "Fuel" in "Search categories...".<br>3. Clear the search.<br>4. Click the "Name" column header.<br>5. Click it again. | Step 2 leaves only "Transport and Fuel"; step 4 sorts ascending (Academic Supplies first); step 5 sorts descending (Utilities first, or a later QA name). | planned |
| TC-EXP-02-E06 | P2 | Web | Staff | Seeded category "Utilities" (types Electricity Bill, Water Bill, Internet and Telephone) | 1. Sign in as Staff.<br>2. Open Expense > Expense Categories. | The seeded categories are listed; no "New Category" button; no Actions column. | planned |
| TC-EXP-02-E07 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Categories.<br>2. Click "New Category".<br>3. Enter Name "QA Long Desc" and a 400-character Description.<br>4. Click "Save". | The form accepts it (web limit 500) but the API rejects it (limit 300): error toast, dialog stays open, no row (Known gaps 2). | planned |
| TC-EXP-02-E08 | P1 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Admin on mobile.<br>2. On the mobile Dashboard tap the "Expense" module.<br>3. Tap "Categories".<br>4. Tap "New Category".<br>5. Enter Name "QA Mobile Category".<br>6. Tap "Save". | Toast "Category Created" with ""QA Mobile Category" has been saved."; the card appears with an Active badge. | passing |
| TC-EXP-02-E09 | P3 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Categories on mobile.<br>2. Tap "New Category".<br>3. Leave Name empty.<br>4. Tap "Save". | Toast "Error" with "Name is required"; the modal stays open. | planned |
| TC-EXP-02-E10 | P2 | Mobile | Admin | Category "QA Mobile Category" exists (TC-EXP-02-E08 done) | 1. Open Expense > Categories on mobile.<br>2. Tap "Edit" on "QA Mobile Category", change Description to "QA edited", tap "Save".<br>3. Tap "Delete" on the same card.<br>4. In the "Delete Category" confirm tap "Delete". | Toast "Category Updated" after step 2; toast "Deleted" with ""QA Mobile Category" has been deleted." after step 4; the card disappears. | planned |
| TC-EXP-02-E11 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Categories.<br>2. Click "New Category".<br>3. Enter Name "QA Discard".<br>4. Click "Cancel".<br>5. Click "Keep Editing", then "Cancel" again and "Discard & Close". | Dialog "Discard changes?" with "You have unsaved data in this form. If you close now, all entered data will be lost." and buttons "Keep Editing" and "Discard & Close"; Keep Editing returns to the form; Discard & Close closes it and nothing is saved. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_catalog.py; web/src/__tests__/expense/expenseValidation.test.ts (U09).

---

## F03 Expense types

**Purpose**: Define the specific spend types (Electricity, Water) inside a category; a transaction always points at one type.

**Roles and permissions**: `expense_types:create`, `:list` (list, `GET /`), `:read` (dropdown, get by id), `:update`, `:delete`. Admin all; Staff read and list.

**Preconditions**: At least one active category (F02).

**Steps, web**
1. Open `/expense/types`; card "Expense Types".
2. Click "New Type". Dialog "Create Expense Type" with hint "Expense types must be linked to categories for proper classification": "Name *" (placeholder "Enter type name"), "Category *" (placeholder "Select category"), "Description" (placeholder "Enter type description"). "Save".
3. Filter with "Search types..." and the "All Categories" dropdown; sort by Name, Category, Status, Created.
4. Saving without a category shows the inline message "Category is required". Edit (pencil icon, dialog "Edit Expense Type") or delete (trash icon, confirm "Delete Expense Type": Are you sure you want to delete "<name>"? This may affect existing transactions.).

**Steps, mobile**
1. Expense tab, "Types" tile, screen "Expense Types". "Search types...", category filter "All Categories".
2. "New Type" opens the modal "Create Expense Type" (hint "Expense types must be linked to categories for proper classification"): "Name *", "Category *" (placeholder "Select category"), "Description", "Active". Errors (title "Error") "Name is required", "Category is required". Success "Type Created".
3. "Edit" and "Delete" (confirm title "Delete Type").

**Expected results**: Type stored with `category_id`, `is_active=true`. Delete soft-deactivates only when no transaction ever used the type.

**API endpoints**
- `POST /expense/types/` body `{name (1-100), category_id, description (max 300), is_active}` returns 201.
- `GET /expense/types/?category_id=&skip=&limit=&active_only=true`.
- `GET /expense/types/dropdown?category_id=` returns `[{id, name, category_id}]`.
- `GET /expense/types/{type_id}`; `PUT /expense/types/{type_id}`; `DELETE /expense/types/{type_id}`.

**Rules and validations**
- Category must exist (404 "Expense category not found") and be active (400 `INACTIVE_CATEGORY`) on create, and also when the category is changed on update.
- Name unique within a category, compared exactly and including inactive types (400 `DUPLICATE_TYPE_NAME`); the same name may exist in two categories.
- Delete is refused when any transaction references the type, whatever its status: 400 `TYPE_HAS_TRANSACTIONS` with `details.transaction_count`.

**Error and edge cases**: Unknown type 404 "Expense type not found". Deleting a category does not deactivate its types, so they stay selectable.

**Unit-testable logic**: Create/update category-active guards; duplicate check across inactive rows; transaction-count guard on delete; dropdown filter by category.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-03-U01 | Service create with an inactive category | HTTPException 400 `INACTIVE_CATEGORY` | passing |
| TC-EXP-03-U02 | Service create with an unknown category id | 404 "Expense category not found" | passing |
| TC-EXP-03-U03 | Duplicate type name in the same category where the existing row is inactive | 400 `DUPLICATE_TYPE_NAME` (inactive rows count) | passing |
| TC-EXP-03-U04 | Same type name in a different category | Allowed | passing |
| TC-EXP-03-U05 | Service update moving a type to an inactive category | 400 `INACTIVE_CATEGORY` | passing |
| TC-EXP-03-U06 | Service update changing only the category to one that already has a same-named type | 400 `DUPLICATE_TYPE_NAME` | passing |
| TC-EXP-03-U07 | Service delete when the transaction count is 2 | 400 `TYPE_HAS_TRANSACTIONS`, `details.transaction_count = 2`; type stays active | passing |
| TC-EXP-03-U08 | Web `validateTypeForm`: empty name, empty category, name "A", description 501 | Errors "Type name is required", "Category is required", "Type name must be at least 2 characters", "Description cannot exceed 500 characters" | passing |
| TC-EXP-03-A01 | Admin creates type "Electricity" in an active category | 201 with `category_id`, `is_active=true` | passing |
| TC-EXP-03-A02 | Create without token; with missing `category_id`; name 101 chars; description 301 chars | 401; 422; 422; 422 | passing |
| TC-EXP-03-A03 | Create with an unknown category UUID | 404 | passing |
| TC-EXP-03-A04 | Create in an inactive category | 400 `INACTIVE_CATEGORY` | passing |
| TC-EXP-03-A05 | Create the same name twice in one category | 400 `DUPLICATE_TYPE_NAME` | passing |
| TC-EXP-03-A06 | Create the same name in two categories | Both 201 | passing |
| TC-EXP-03-A07 | `GET /expense/types/?category_id=<c>` | Only types of category c | passing |
| TC-EXP-03-A08 | `GET /expense/types/dropdown?category_id=<c>` | `[{id, name, category_id}]` sorted by name, active only | passing |
| TC-EXP-03-A09 | `GET /expense/types/{id}` existing, unknown, malformed | 200; 404 "Expense type not found"; 422 | passing |
| TC-EXP-03-A10 | `PUT` rename; `PUT` move to another active category; `PUT` to inactive category | 200; 200; 400 | passing |
| TC-EXP-03-A11 | `DELETE` a type with no transactions | 200 with `is_active=false`; gone from list and dropdown | passing |
| TC-EXP-03-A12 | `DELETE` a type that has one transaction (any status) | 400 `TYPE_HAS_TRANSACTIONS`, `transaction_count=1` | passing |
| TC-EXP-03-A13 | Pagination bounds on list: `limit=0`, `limit=1001` | 422 | passing |
| TC-EXP-03-A14 | Role matrix on POST, GET list, GET dropdown, GET by id, PUT, DELETE | Admin all 2xx; Staff 200 on GET list/dropdown/by id and 403 on POST/PUT/DELETE; Teacher, Student, Parent 403 everywhere | passing |
| TC-EXP-03-A15 | Tenant isolation: type created in tenant A, queried with tenant B token | Not listed; by id 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-03-E01 | P1 | Web | Admin | Seeded category "Utilities" (types Electricity Bill, Water Bill, Internet and Telephone) | 1. Open Expense > Expense Types.<br>2. Click "New Type".<br>3. Enter Name "QA Solar Panels".<br>4. Choose Category "Utilities".<br>5. Click "Save". | Toast "Expense type created successfully"; row "QA Solar Panels" shows Category Utilities and Status Active. | passing |
| TC-EXP-03-E02 | P2 | Web | Admin | Seeded category "Utilities" (types Electricity Bill, Water Bill, Internet and Telephone) | 1. Open Expense > Expense Types.<br>2. Open the "All Categories" dropdown.<br>3. Choose "Utilities". | Only Electricity Bill, Water Bill, Internet and Telephone (plus any QA types of Utilities) remain; Fuel and Stationery are hidden. | planned |
| TC-EXP-03-E03 | P2 | Web | Admin | Type "QA Solar Panels" exists with no transactions (TC-EXP-03-E01 done) | 1. Open Expense > Expense Types.<br>2. Click the pencil icon in the "QA Solar Panels" row.<br>3. In "Edit Expense Type" change Name to "QA Solar Power".<br>4. Click "Save". | Toast "Expense type updated successfully"; the row shows "QA Solar Power". | planned |
| TC-EXP-03-E04 | P2 | Web | Admin | Seeded type "Electricity Bill" (category Utilities) with its seeded transaction | 1. Open Expense > Expense Types.<br>2. Click the trash icon in the "Electricity Bill" row.<br>3. In "Delete Expense Type" click "Delete". | Error toast "Cannot delete expense type. It has <n> associated transactions." (n is 1 with only seeded data); the row remains Active. | planned |
| TC-EXP-03-E05 | P2 | Web | Admin | Type "QA Solar Power" exists with no transactions (TC-EXP-03-E03 done) | 1. Open Expense > Expense Types.<br>2. Click the trash icon in the "QA Solar Power" row.<br>3. Read the confirm and click "Delete". | Confirm text Are you sure you want to delete "QA Solar Power"? This may affect existing transactions.; toast "Expense type deleted successfully"; the row disappears. | planned |
| TC-EXP-03-E06 | P2 | Mobile | Admin | Seeded category "Utilities" (types Electricity Bill, Water Bill, Internet and Telephone) | 1. Open Expense > Types on mobile.<br>2. Tap "New Type" (modal "Create Expense Type").<br>3. Enter Name "QA Mobile Type" and tap "Save".<br>4. Choose Category "Utilities" and tap "Save". | Step 3: toast "Error" with "Category is required"; step 4: toast "Type Created" and the card appears. | planned |
| TC-EXP-03-E07 | P3 | Mobile | Admin | Seeded type "Electricity Bill" (category Utilities) with its seeded transaction | 1. Open Expense > Types on mobile.<br>2. Tap "Delete" on "Electricity Bill".<br>3. Confirm "Delete". | Toast "Delete Failed" with "Could not delete expense type."; the card remains. | planned |
| TC-EXP-03-E08 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Types.<br>2. Click "New Type".<br>3. Enter Name "QA No Category" and leave Category empty.<br>4. Click "Save". | Inline message "Category is required" under Category; no request is sent; the dialog stays open. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_catalog.py; web/src/__tests__/expense/expenseValidation.test.ts (U08).

---

## F04 Expense departments

**Purpose**: Maintain the departments (for example Administration, Transport) that an expense can be assigned to and filtered by.

**Roles and permissions**: `expense_departments:create`, `:list`, `:read` (dropdown, get by id), `:update`, `:delete`. Admin all; Staff read and list.

**Preconditions**: Permissions seeded; menu entry present.

**Steps, web**
1. Open `/expense/departments`; card "Expense Departments".
2. "New Department": dialog "Create Department" with "Name *" (placeholder "Enter department name", max 100) and "Description" (max 300). "Save".
3. Row actions "Edit" and "Deactivate" (icons with those titles; confirm "Deactivate Department": Deactivate "<name>"? It will no longer be offered for new expenses; existing expenses keep it.; button "Deactivate", which reads "Deactivateing..." while pending). Toast "Department deactivated". A duplicate name shows the error toast "Department with name '<name>' already exists".
4. The audit page filters transactions by department ("All Departments"); the web transaction form has no department field.

**Steps, mobile**
1. Expense tab, "Departments" tile, screen "Expense Departments", search "Search departments...".
2. "New Department" modal with "Name *" (placeholder "Enter department name") and "Description" (no Active switch); success "Department Created" with "<name>" has been saved.; empty name "Error" "Name is required". Card actions "Edit" and "Deactivate" (confirm "Deactivate Department"; success "Deactivated" with "<name>" has been deactivated.). Empty list: "No departments found". The mobile create and edit transaction screens have a "Department (Optional)" dropdown with "No Department".

**Expected results**: Active department rows offered in the dropdown; deactivated rows are hidden from the dropdown and the default list but remain on old transactions.

**API endpoints**
- `POST /expense/departments/` `{name, description, is_active}` returns 201.
- `GET /expense/departments/?skip=&limit=&active_only=true`; `GET /expense/departments/dropdown`; `GET /expense/departments/{id}`.
- `PUT /expense/departments/{id}`; `DELETE /expense/departments/{id}` (deactivate, returns the row).

**Rules and validations**
- Name unique among active departments, case-insensitive after trimming (400 `DUPLICATE_DEPARTMENT_NAME`); inactive names are reusable. Reactivating or renaming re-runs the check.
- Name 1 to 100 characters, description max 300.
- Delete never checks usage; `department_id` on transactions has no foreign key. Create and update of a transaction check the department exists (404) and is active (400 `INACTIVE_DEPARTMENT`).

**Error and edge cases**: Unknown id 404 "Expense department not found". Reactivating a department whose name now clashes with another active one: 400.

**Unit-testable logic**: `_ensure_unique_active_name` (case-insensitive, trim, exclude self); update re-check only when becoming active or renamed; soft delete.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-04-U01 | `_ensure_unique_active_name("  finance ")` with an active "Finance" | Raises 400 `DUPLICATE_DEPARTMENT_NAME` | passing |
| TC-EXP-04-U02 | Same check where "Finance" is inactive | No error | passing |
| TC-EXP-04-U03 | Update renaming to its own name with different case | No error (self excluded) | passing |
| TC-EXP-04-U04 | Update setting `is_active=True` on an inactive department whose name equals an active one | 400 duplicate | passing |
| TC-EXP-04-U05 | Update of description only on an active department | Duplicate check skipped | passing |
| TC-EXP-04-U06 | Schema bounds: name "" , 101 chars; description 301 chars | Rejected; 100 and 300 accepted | passing |
| TC-EXP-04-A01 | Admin creates department "QA Administration" | 201, `is_active=true` | passing |
| TC-EXP-04-A02 | Create "qa administration" while the first is active | 400 `DUPLICATE_DEPARTMENT_NAME` | passing |
| TC-EXP-04-A03 | Create with empty name; name 101 chars | 422 | passing |
| TC-EXP-04-A04 | `GET /expense/departments/` default and `active_only=false` | Inactive hidden by default, shown with false | passing |
| TC-EXP-04-A05 | `GET /expense/departments/dropdown` | `[{id, name}]` sorted by name, active only | passing |
| TC-EXP-04-A06 | `GET /expense/departments/{id}` existing and unknown | 200; 404 "Expense department not found" | passing |
| TC-EXP-04-A07 | `PUT` rename and description; `PUT` clashing active name | 200; 400 | passing |
| TC-EXP-04-A08 | `DELETE` then dropdown | 200 with `is_active=false`; absent from dropdown | passing |
| TC-EXP-04-A09 | Recreate a deleted department's name | 201 | passing |
| TC-EXP-04-A10 | Role matrix | Admin 2xx on all six endpoints; Staff 200 on GET list, dropdown, by id and 403 on POST, PUT, DELETE; Teacher, Student, Parent 403 | passing |
| TC-EXP-04-A11 | Tenant isolation | Department of tenant A absent for tenant B; by id 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-04-E01 | P1 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Departments.<br>2. Click "New Department".<br>3. Enter Name "QA Hostel", Description "QA hostel running costs".<br>4. Click "Save". | Dialog "Create Department" closes; toast "Department created successfully"; row "QA Hostel" with Status Active next to the seeded Administration, Academics, Transport, Maintenance, Sports. | passing |
| TC-EXP-04-E02 | P2 | Web | Admin | Department "QA Temp Dept" exists (create it as in TC-EXP-04-E01) | 1. Open Expense > Expense Departments.<br>2. Click the "Deactivate" icon in the "QA Temp Dept" row.<br>3. Read the confirm and click "Deactivate". | Confirm "Deactivate Department" with Deactivate "QA Temp Dept"? It will no longer be offered for new expenses; existing expenses keep it.; toast "Department deactivated"; the row leaves the default list. (While pending the button reads "Deactivateing...", cosmetic defect.) | planned |
| TC-EXP-04-E03 | P2 | Web | Admin | Department "QA Hostel" exists (TC-EXP-04-E01 done) | 1. Open Expense > Expense Departments.<br>2. Click the "Edit" icon in the "QA Hostel" row.<br>3. In "Edit Department" change Description to "QA hostel food and repairs".<br>4. Click "Save". | Toast "Department updated successfully"; the row shows the new description. | planned |
| TC-EXP-04-E04 | P2 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Departments on mobile.<br>2. Tap "New Department", enter Name "QA Library", tap "Save".<br>3. Tap "Deactivate" on "QA Library" and confirm "Deactivate". | Toast "Department Created" with ""QA Library" has been saved."; then toast "Deactivated" with ""QA Library" has been deactivated."; the card disappears. | planned |
| TC-EXP-04-E05 | P3 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Departments on mobile.<br>2. Tap "New Department".<br>3. Leave Name empty and tap "Save". | Toast "Error" with "Name is required". | planned |
| TC-EXP-04-E06 | P3 | Web | Admin | Seeded department "Transport" | 1. Open Expense > Expense Departments.<br>2. Click "New Department".<br>3. Enter Name "transport".<br>4. Click "Save". | Error toast "Department with name 'transport' already exists" (case-insensitive check); no second row. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_catalog.py.

---

## F05 Expense settings

**Purpose**: Store key and value policy settings (approval limits, receipt rules). Nothing in the transaction flow reads them today; the screens exist for configuration.

**Roles and permissions**: `expense_settings:create`, `:list`, `:read`, `:update`, `:delete` plus the role-name rule (Admin, tenant admin, super admin) on create, delete and reset. Admin only in the default catalog; Staff and Teacher have no settings grants.

**Preconditions**: `expense_settings` permissions seeded (the expense seed script does not cover settings).

**Steps, web**
1. Open `/expense/settings`. Header "Expense Settings", subtitle "Configure expense management settings and policies".
2. Summary cards "Default Approval", "Auto-Approval Limit", "Receipts Required Over" (read from keys `default_approval_required`, `auto_approval_limit`, `require_receipts_over_amount`).
3. Filter with "Filter by Category" (All Categories, Approval, Workflow, Security, Compliance, Notification, Integration). Table columns Setting, Category, Value, Compliance, Status, Actions.
4. "New Setting": dialog "Create Setting": "Setting Key *" (placeholder "unique_setting_key"), "Setting Name *" (placeholder "Display name"), "Description", "Category *" (defaults to Approval), "Compliance Level" (Standard, High, Critical; defaults to Standard), "Setting Value" with "String Value", "Numeric Value", "Boolean Value", "User Configurable", "Requires Approval". "Save".
5. Row edit (pencil) opens "Edit Setting"; the delete action (a gear icon, hidden for system settings) opens "Delete Setting" confirm (Are you sure you want to delete "<setting name>"?). With no rows the table shows "No settings found" and the cards show "Not set". Staff and Teacher get "Access Denied" with "You don't have permission to view expense settings."

**Steps, mobile**
1. Reached from the navigation drawer (no hub tile). Screen "Expense Settings" with a "Common Settings" card (Default Approval, Auto-Approval Limit, Receipts Required Over; "Not set" when missing) and "No settings configured" when the table is empty. Staff gets "Access Denied" with "You don't have permission to view this screen. Please contact your administrator."
2. Tap the edit icon on a row; modal has "Value" and "Description" (placeholders "Setting value", "Optional description"). Success "Saved" / "Setting updated."; failure "Failed to update setting." Mobile cannot create or delete settings. Edit is shown only with `expense_settings:update`.

**Expected results**: Rows saved in `expense_settings` with one populated value column; `GET /key/{key}/value` returns the value and its type; changing a setting does not change how new transactions are classified.

**API endpoints**
- `POST /expense/settings/` (create, 201); `GET /expense/settings/?category=&active_only=true`; `GET /expense/settings/{id}`.
- `GET /expense/settings/key/{setting_key}/value` returns `{setting_key, value, value_type}` (404 when missing or inactive or all value columns null).
- `PUT /expense/settings/{id}`; `DELETE /expense/settings/{id}` (soft delete, admin roles only).
- `GET /expense/settings/ui/common` returns `{settings: {key: {value, type}}, retrieved_at}` for five fixed keys (`auto_approval_limit`, `require_receipts_over_amount`, `default_approval_required`, `max_file_size_mb`, `allowed_file_types`); `retrieved_at` is the database dialect name, not a time.
- `POST /expense/settings/{id}/reset` returns `{message, setting_id}` and changes nothing.

**Rules and validations**
- `setting_key` 1-100, `setting_name` 1-200, `setting_category` one of approval, workflow, security, compliance, notification, integration (else 422), `compliance_level` one of standard, high, critical, `string_value` max 500, decimals to 2 places.
- `setting_key` unique per tenant: 400 `DUPLICATE_SETTING_KEY`.
- Value type resolution order: string, numeric, integer, boolean, json (first non-null wins; numeric returned as float).
- Update does not accept `setting_key` or `setting_category`; it stamps `last_modified_by_user_id` and role.

**Error and edge cases**: Non-admin role with the create grant gets 403 "Only administrators can create expense settings". Delete and reset likewise.

**Unit-testable logic**: `get_setting_value` type precedence; category and compliance validators; duplicate-key guard.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-05-U01 | `get_setting_value` for a row with `numeric_value=500.00` only | `value=500.0`, `value_type="numeric"` | passing |
| TC-EXP-05-U02 | Row with both `string_value="x"` and `integer_value=3` | `value_type="string"` (string wins) | passing |
| TC-EXP-05-U03 | Row with `boolean_value=False` only | `value=False`, `value_type="boolean"` | passing |
| TC-EXP-05-U04 | Row with all value columns null | Returns None (endpoint 404) | passing |
| TC-EXP-05-U05 | `ExpenseSettingsCreate` with `setting_category="budget"` | ValidationError listing the six allowed values | passing |
| TC-EXP-05-U06 | `compliance_level="extreme"` | ValidationError | passing |
| TC-EXP-05-U07 | `string_value` of 501 characters | ValidationError | passing |
| TC-EXP-05-A01 | Admin `POST /expense/settings/` key `auto_approval_limit`, category approval, `numeric_value=500.00` | 201 with `version=1`, `is_active=true`, `created_by_role="Admin"` | passing |
| TC-EXP-05-A02 | Duplicate `setting_key` | 400 `DUPLICATE_SETTING_KEY` | passing |
| TC-EXP-05-A03 | Invalid category value; invalid compliance level | 422 | passing |
| TC-EXP-05-A04 | `GET /expense/settings/?category=approval`; `?active_only=false` | Filtered, ordered by category then key; inactive only with false | passing |
| TC-EXP-05-A05 | `GET /expense/settings/{id}` existing and unknown | 200; 404 "Expense setting not found" | passing |
| TC-EXP-05-A06 | `GET /expense/settings/key/auto_approval_limit/value` | `{"setting_key":"auto_approval_limit","value":500.0,"value_type":"numeric"}` | passing |
| TC-EXP-05-A07 | `GET .../key/does_not_exist/value` | 404 "Setting with key 'does_not_exist' not found" | passing |
| TC-EXP-05-A08 | `PUT` change `numeric_value` to 750.00 | 200; `last_modified_by_user_id` set; value 750.00 | passing |
| TC-EXP-05-A09 | `DELETE` setting then `GET .../key/.../value` | 200 `is_active=false`; value endpoint 404 | passing |
| TC-EXP-05-A10 | `GET /expense/settings/ui/common` with two of the five keys set | `settings` contains exactly those two with `type`; `retrieved_at` is a string (the dialect name) | passing |
| TC-EXP-05-A11 | `POST /expense/settings/{id}/reset` | 200 `{message: "Setting reset to default value", setting_id}`; the stored value is unchanged | passing |
| TC-EXP-05-A12 | Role matrix: Staff and Teacher on every settings endpoint | 403 | passing |
| TC-EXP-05-A13 | A custom role granted `expense_settings:create` but not named admin | 403 "Only administrators can create expense settings" | skipped: needs a custom role granted expense_settings:create; |
| TC-EXP-05-A14 | Tenant isolation | Setting in tenant A invisible in B; same key can exist in both | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-05-E01 | P1 | Web | Admin | Seeded tenant qa_manual (year 2026-2027); no setting with key qa_limit | 1. Open Expense > Expense Settings.<br>2. Click "New Setting".<br>3. Enter Setting Key "qa_limit", Setting Name "QA limit"; keep Category "Approval" and Compliance Level "Standard".<br>4. Enter Numeric Value 1500.<br>5. Click "Save". | Toast "Settings updated successfully"; row "QA limit" in category Approval with value 1500. | passing |
| TC-EXP-05-E02 | P3 | Web | Admin | Setting "qa_limit" exists (TC-EXP-05-E01 done) | 1. Open Expense > Expense Settings.<br>2. In "Filter by Category" choose "Security". | Only security settings are listed; with none, "No settings found"; QA limit is hidden. | planned |
| TC-EXP-05-E03 | P2 | Web | Admin | Setting "qa_limit" exists (TC-EXP-05-E01 done) | 1. Open Expense > Expense Settings.<br>2. Click the pencil icon in the "QA limit" row.<br>3. In "Edit Setting" change Numeric Value to 1750.<br>4. Click "Save". | Toast "Settings updated successfully"; the row shows 1750. | planned |
| TC-EXP-05-E04 | P2 | Web | Admin | Setting "qa_limit" exists (TC-EXP-05-E01 done) | 1. Open Expense > Expense Settings.<br>2. Click the gear (delete) icon in the "QA limit" row.<br>3. In "Delete Setting" confirm. | Confirm text Are you sure you want to delete "QA limit"?; the row disappears; system settings show no delete icon. | planned |
| TC-EXP-05-E05 | P2 | Mobile | Admin | Setting "qa_limit" exists (TC-EXP-05-E01 done) | 1. Sign in as Admin on mobile.<br>2. Open the drawer and choose Expense > Expense Settings.<br>3. Tap the edit icon on "QA limit".<br>4. Enter Value 1800 and save. | Toast "Saved" with "Setting updated."; the row shows 1800. | planned |
| TC-EXP-05-E06 | P2 | Mobile | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff on mobile.<br>2. Open /expense/settings. | "Access Denied" with "You don't have permission to view this screen. Please contact your administrator." | planned |
| TC-EXP-05-E07 | P2 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Open Expense > Expense Settings. | "Access Denied" with "You don't have permission to view expense settings." | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_catalog.py.

---

## F06 Create an expense transaction (line items)

**Purpose**: Record one expense with its type, amount, date, vendor and payment method; optionally break the amount into line items on the client.

**Roles and permissions**: `expense_transactions:create`. Admin and Staff in the default catalog. Department is optional (`expense_departments` is only checked in the service for existence).

**Preconditions**: An active expense type (F03). Optional active department (F04).

**Steps, web**
1. Open `/expense/transactions` and click "New Transaction". Dialog "Create New Transaction".
2. Fill "Expense Type *" (placeholder "Select expense type"), "Vendor Name *", "Transaction Date *" (defaults to today), "Payment Method *" (Cash, Cheque, Bank Transfer, UPI), "Description *", "Reference Number", "Total Amount".
3. Optional "Transaction Items" section: "Add Item" adds a row with "Item Name", "Unit Price", "Quantity", "Tax Rate (%)" and a read-only "Final Amount"; the trash button removes a row. While items exist, "Total Amount" is read-only and equals the sum of final amounts. There is no discount field on web (the state has `discount_rate`, fixed at 0).
4. Optional "Attachments" with "Upload Files" (multiple); see F10 and Known gaps (the files are not uploaded).
5. Click "Save Transaction" (shows "Saving..."). Missing type, amount 0, vendor or description shows toast "Please fill in all required fields". Success toast "Transaction created successfully".

**Steps, mobile**
1. Expense tab, "Transactions", "New Transaction". Screen "Create New Transaction".
2. Fields: "Expense Type *", "Total Amount *" (placeholder "Enter amount"; auto-calculated and read-only when items exist; hint "Add items to break down this expense. Amount will be auto-calculated."), "Transaction Items" with "Add Item" ("Item #n", Item name, "Unit Price", "Quantity", "Tax (%)", "Discount (%)", computed amount), "Transaction Date *" (defaults to today), "Description *", "Payment Method *" (defaults to Cash), "Vendor Name *" (placeholder "Enter vendor/supplier name"), "Reference Number (Optional)" (placeholder "Invoice/bill number"), "Department (Optional)" (first choice "No Department").
3. "Attachments" with "Upload Files" (document picker, multiple); each file is uploaded after the transaction is created with document type "invoice".
4. "Save Transaction" ("Saving..."). Validation toasts (title "Error"): "Please select an expense type", "Please enter a valid amount", "Please enter a description", "Please enter vendor name", "Please select a transaction date". Success toast "Created" with "Transaction created successfully." and the screen closes; if an upload fails: "Attachment Upload Failed" with "Transaction saved, but some attachments could not be uploaded...".

**Expected results**: A `pending` transaction with `requires_approval` computed per F11, `created_by_user_id` and role stamped, `version=1`, `org_id` = tenant. Line items are not sent and are not stored (`expense_transaction_items` is never written).

**API endpoints**
- `POST /expense/transactions/` body `{expense_type_id, amount (>= 0, 2 decimals), transaction_date, description (1-500), payment_method, vendor_name (<=200), reference_number (<=100), department_id, academic_year_id, idempotency_key (1-100), requires_approval_override}` returns 201 with the full row.

**Rules and validations**
- `idempotency_key` unique per tenant; duplicate: 400 `DUPLICATE_IDEMPOTENCY_KEY`. Clients generate `txn_<epoch ms>_<random>`.
- Type must exist (404 "Expense type not found") and be active (400 `INACTIVE_EXPENSE_TYPE`). Department must exist and be active.
- `amount` is `Decimal`, `>= 0` and at most 2 decimal places; the column is `Numeric(10,2)`, so values above 99999999.99 fail in the database. Zero is accepted by the API but blocked by both clients.
- `payment_method` is a free string (column length 20); clients send `cash`, `cheque`, `bank_transfer`, `upi`.
- Line item final amount: `unit_price x quantity` plus tax of `tax_rate` percent minus discount of `discount_rate` percent of the same subtotal. Total is the sum of finals (mobile formats to 2 decimals).
- Clients never send `academic_year_id`; the backend sets no default.

**Error and edge cases**: Unknown type 404; inactive type 400; duplicate key 400; negative amount, 3 decimal places, missing fields 422; no token 401; no permission 403. The web required-field check treats amount 0 as missing.

**Unit-testable logic**: Line item calculation (web `updateTransactionItem`, mobile `calculateItemAmount`), total as sum, idempotency key format, create-time guards in `create_transaction`, `ExpenseTransactionCreate` bounds.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-06-U01 | Item unit 250.00, qty 3, tax 18, discount 10 | subtotal 750; tax 135; discount 75; final 810.00 | blocked: line item maths is inline (web updateTransactionItem in pages/expense/transactions.tsx, mobile calculateItemAmount not exported from app/expense/transactions/create.tsx); needs the helper exported |
| TC-EXP-06-U02 | Two items: 810.00 and (99.99, qty 1, tax 0, discount 0) | Total amount 909.99 | blocked: line item maths is inline (web updateTransactionItem in pages/expense/transactions.tsx, mobile calculateItemAmount not exported from app/expense/transactions/create.tsx); needs the helper exported |
| TC-EXP-06-U03 | Item with quantity 0 or empty | Mobile treats quantity as 1 (`parseInt(t) || 1`); web uses `quantity \|\| 1` | blocked: line item maths is inline (web updateTransactionItem in pages/expense/transactions.tsx, mobile calculateItemAmount not exported from app/expense/transactions/create.tsx); needs the helper exported |
| TC-EXP-06-U04 | Remove the only item | Mobile total becomes empty string; web total becomes 0 | blocked: line item maths is inline (web updateTransactionItem in pages/expense/transactions.tsx, mobile calculateItemAmount not exported from app/expense/transactions/create.tsx); needs the helper exported |
| TC-EXP-06-U05 | `ExpenseTransactionCreate` with amount `-0.01`, `1.234`, `0.00` | Rejected, rejected, accepted | passing |
| TC-EXP-06-U06 | Description of 500 and 501 characters; reference_number 101; vendor_name 201 | 500 accepted; others rejected | passing |
| TC-EXP-06-U07 | `idempotency_key` of "" and of 101 characters | Rejected; 100 accepted | passing |
| TC-EXP-06-U08 | Service create with an inactive type | 400 `INACTIVE_EXPENSE_TYPE` | passing |
| TC-EXP-06-U09 | Service create with a duplicate idempotency key | 400 `DUPLICATE_IDEMPOTENCY_KEY` | passing |
| TC-EXP-06-U10 | Service create with an inactive department id | 400 `INACTIVE_DEPARTMENT`; unknown department 404 | passing |
| TC-EXP-06-U11 | Web idempotency key generator | Matches `^txn_\d+_[a-z0-9]+$`; two calls differ | passing |
| TC-EXP-06-A01 | Admin creates a cash 500.00 transaction | 201; `status="pending"`, `requires_approval=false`, `version=1`, `created_by_role="Admin"`, amount string "500.00", `org_id` equals tenant id | passing |
| TC-EXP-06-A02 | Staff creates a transaction | 201 (Staff has `create`) | passing |
| TC-EXP-06-A03 | Teacher, Student, Parent create | 403 | passing |
| TC-EXP-06-A04 | No Authorization header | 401 | passing |
| TC-EXP-06-A05 | Repeat the same body and `idempotency_key` | Second call 400 `DUPLICATE_IDEMPOTENCY_KEY`; only one row exists | passing |
| TC-EXP-06-A06 | Missing `expense_type_id`; missing `idempotency_key`; amount `-1`; amount `10.123` | 422 each | passing |
| TC-EXP-06-A07 | Unknown `expense_type_id` | 404 "Expense type not found" | passing |
| TC-EXP-06-A08 | Type with `is_active=false` | 400 `INACTIVE_EXPENSE_TYPE` | passing |
| TC-EXP-06-A09 | `department_id` of an active department | 201 and the field is echoed | passing |
| TC-EXP-06-A10 | `department_id` unknown; inactive | 404 "Expense department not found"; 400 `INACTIVE_DEPARTMENT` | passing |
| TC-EXP-06-A11 | `amount` 0.00 | 201 (API allows zero) | passing |
| TC-EXP-06-A12 | `amount` 99999999.99 and 100000000.00 | First 201; second fails with a database error response (not 2xx) | passing |
| TC-EXP-06-A13 | `payment_method` "NEFT_TRANSFER_REFERENCE" (23 chars) | Not 2xx (column length 20); documents missing validation | passing |
| TC-EXP-06-A14 | Create without `academic_year_id` then `GET` it | `academic_year_id` is null | passing |
| TC-EXP-06-A15 | Create with a real `academic_year_id` | 201 with the id echoed | passing |
| TC-EXP-06-A16 | Same `idempotency_key` used in tenant B | 201 (uniqueness is per tenant) | passing |
| TC-EXP-06-A17 | Tenant isolation: tenant B token cannot use tenant A's type id | 404 "Expense type not found" | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-06-E01 | P1 | Web | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "New Transaction".<br>3. Choose Expense Type "Electricity Bill", Vendor Name "QA Power Co", keep Transaction Date (today) and Payment Method "Cash".<br>4. Enter Description "QA Electricity bill" and Total Amount 500.<br>5. Click "Save Transaction". | Toast "Transaction created successfully"; the row appears in the All and Pending tabs with a Pending badge and amount Rs 500; stored status pending, requires_approval false. | passing |
| TC-EXP-06-E02 | P2 | Web | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "New Transaction".<br>3. Fill Expense Type "Electricity Bill", Description "QA no vendor", Total Amount 100; leave Vendor Name empty.<br>4. Click "Save Transaction". | Toast "Please fill in all required fields"; the dialog "Create New Transaction" stays open; no request is sent. | planned |
| TC-EXP-06-E03 | P2 | Web | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "New Transaction".<br>3. Click "Add Item"; enter Item Name "QA Cable", Unit Price 250, Quantity 3, Tax Rate (%) 18.<br>4. Click "Add Item"; enter Item Name "QA Switch", Unit Price 99.99, Quantity 1. | Final Amount shows 885.00 and 99.99; Total Amount is read-only and shows 984.99 (web has no discount field). | planned |
| TC-EXP-06-E04 | P3 | Web | Admin | TC-EXP-06-E03 steps done (dialog open with two items) | 1. Click the trash button on the "QA Cable" item. | The item disappears; Total Amount becomes 99.99. | planned |
| TC-EXP-06-E05 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "New Transaction".<br>3. Enter Vendor Name "QA Discard".<br>4. Click "Cancel". | Dialog "Discard changes?" with "Keep Editing" and "Discard & Close"; Discard & Close closes without saving. | planned |
| TC-EXP-06-E06 | P1 | Mobile | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Sign in as Admin on mobile.<br>2. On the mobile Dashboard tap the "Expense" module.<br>3. Tap "Transactions", then "New Transaction".<br>4. Choose Expense Type "Electricity Bill".<br>5. Tap "Add Item": Item name "QA Cable", Unit Price 250, Quantity 3, Tax (%) 18, Discount (%) 10.<br>6. Tap "Add Item": Item name "QA Switch", Unit Price 99.99, Quantity 1.<br>7. Enter Description "QA Mobile bill", Vendor Name "QA Power Co".<br>8. Tap "Save Transaction". | Total Amount shows 909.99 and is read-only; toast "Created" with "Transaction created successfully."; the screen closes and the list shows the new Pending card with Rs 909.99. | passing |
| TC-EXP-06-E07 | P3 | Mobile | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Open Expense > Transactions > "New Transaction" on mobile.<br>2. Choose Expense Type "Electricity Bill", enter Total Amount 0, Description "QA zero", Vendor Name "QA Vendor".<br>3. Tap "Save Transaction". | Toast "Error" with "Please enter a valid amount"; nothing is saved. | planned |
| TC-EXP-06-E08 | P2 | Mobile | Admin | Seeded type "Electricity Bill" (category Utilities); seeded department "Transport" | 1. Open Expense > Transactions > "New Transaction" on mobile.<br>2. Choose Expense Type "Fuel", Total Amount 120, Description "QA bus diesel top-up", Vendor Name "QA Fuel".<br>3. In "Department (Optional)" choose "Transport".<br>4. Tap "Save Transaction". | Toast "Created"; GET /expense/transactions/{id} shows the department_id of Transport. | planned |
| TC-EXP-06-E09 | P2 | Mobile | Admin | Seeded type "Electricity Bill" (category Utilities); a small PDF or image file available to the browser | 1. Open Expense > Transactions > "New Transaction" on mobile.<br>2. Fill Expense Type "Electricity Bill", Total Amount 80, Description "QA with bill", Vendor Name "QA Shop".<br>3. Tap "Upload Files" and pick the file.<br>4. Tap "Save Transaction".<br>5. Open the new transaction. | Toast "Created"; the "Transaction Details" Attachments card lists the file with document type invoice. | planned |
| TC-EXP-06-E10 | P2 | Web | Staff | Seeded type "Electricity Bill" (category Utilities) | 1. Sign in as Staff.<br>2. Click "Expense" in the sidebar, then "Expense Transactions".<br>3. Click "New Transaction"; fill Expense Type "Electricity Bill", Vendor "QA Staff Vendor", Description "QA staff expense", Total Amount 50.<br>4. Click "Save Transaction". | "New Transaction" is visible; toast "Transaction created successfully"; the row is listed (created_by_role Staff). | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_transactions.py; web/src/__tests__/expense/expenseValidation.test.ts (U11).

---

## F07 List, filter and view transactions

**Purpose**: Find transactions by status, type, date and vendor and read their details.

**Roles and permissions**: `expense_transactions:list` (list page, `GET /`), `:read` (view dialog, `GET /{id}`). Admin and Staff.

**Preconditions**: Transactions exist (F06).

**Steps, web**
1. Open `/expense/transactions` (title "Expense Transactions", subtitle "Manage expense transactions with detailed line items and approval workflows").
2. Filters: "All Status" (Pending, Approved, Paid, Cancelled), "All Types", "From Date", "To Date", "Vendor Name". Status and type filters are sent to the API; dates and vendor filter the returned rows in the browser.
3. Tabs "All (n)", "Pending (n)", "Approved (n)", "Paid (n)", "Cancelled (n)" filter the already loaded rows and show counts.
4. Table columns S.No., Date, Vendor, Type, Amount (rupee, Indian grouping, trailing zeros dropped, for example Rs 300.5), Status, Actions (icons titled View, Edit, "Approve or reject", Delete; Staff sees only View).
5. View opens "Transaction Details" with Status, Date, Vendor, Type, Payment Method, Amount, Description.

**Steps, mobile**
1. Expense hub, "Transactions". Filters panel "Filters": "All Status", "All Types", From and To date ("From date (YYYY-MM-DD)", "To date (YYYY-MM-DD)"), "Vendor Name". Tabs All, Pending, Approved, Paid, Cancelled with counts.
2. Each card shows description, vendor and payment method, amount with 2 decimals, status badge, date, and "Ref: <reference>". Tap a card for "Transaction Details" (Description, Expense Type, Payment Method, Reference No, Approved At, Approval Note, Created At, Attachments).

**Expected results**: Newest first. Only `pending` and `approved` (and `rejected`) can occur through the UI; `paid` and `cancelled` tabs are always empty because no endpoint sets those statuses.

**API endpoints**
- `GET /expense/transactions/?skip=0&limit=100&status_filter=&expense_type_id=&department_id=` returns an array ordered by `created_at` descending. `department_id` is accepted but ignored; there are no date parameters.
- `GET /expense/transactions/{transaction_id}` returns the full row.

**Rules and validations**: `limit` 1-1000 (default 100); `status_filter` is an exact match on any string (`rejected` works even though no tab exists for it); `expense_type_id` exact match.

**Error and edge cases**: Unknown id 404 "Expense transaction not found"; malformed id 422; web date filter compares ISO strings, so `from > to` returns nothing.

**Unit-testable logic**: Tab filtering and counts; web client-side date and vendor filters (case-insensitive contains); status badge mapping; currency formatting.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-07-U01 | Web filter with `date_from="2026-08-01"`, `date_to="2026-08-31"` on rows dated 2026-07-31, 2026-08-01, 2026-08-31, 2026-09-01 | Keeps 08-01 and 08-31 only | blocked: tab, date and vendor filtering and tab counts are inline in web/src/pages/expense/transactions.tsx and mobile/app/expense/transactions.tsx (useMemo); needs the helpers exported |
| TC-EXP-07-U02 | Vendor filter "power" against "QA Power Co" and null vendor | Matches the first; null treated as empty string | blocked: tab, date and vendor filtering and tab counts are inline in web/src/pages/expense/transactions.tsx and mobile/app/expense/transactions.tsx (useMemo); needs the helpers exported |
| TC-EXP-07-U03 | Tab counts for 3 pending, 2 approved, 1 rejected | All (6), Pending (3), Approved (2), Paid (0), Cancelled (0); the rejected row appears only in All | blocked: tab, date and vendor filtering and tab counts are inline in web/src/pages/expense/transactions.tsx and mobile/app/expense/transactions.tsx (useMemo); needs the helpers exported |
| TC-EXP-07-U04 | Mobile `tabCounts` with the same data | Same counts | blocked: tab, date and vendor filtering and tab counts are inline in web/src/pages/expense/transactions.tsx and mobile/app/expense/transactions.tsx (useMemo); needs the helpers exported |
| TC-EXP-07-A01 | `GET /expense/transactions/` after creating 3 | Array of 3, newest first | passing |
| TC-EXP-07-A02 | `?status_filter=pending`; `?status_filter=approved`; `?status_filter=bogus` | Matching rows; matching rows; empty array (no error) | passing |
| TC-EXP-07-A03 | `?expense_type_id=<t>` | Only that type | passing |
| TC-EXP-07-A04 | `?department_id=<d>` | Not filtered (parameter ignored): all rows returned | passing |
| TC-EXP-07-A05 | `?limit=2&skip=1` ; `limit=0`; `limit=1001` | Page of 2; 422; 422 | passing |
| TC-EXP-07-A06 | `GET /expense/transactions/{id}` existing, unknown, malformed | 200 with all documented fields; 404; 422 | passing |
| TC-EXP-07-A07 | Response shape check | `amount` is a decimal string; `approved_*` null on pending; `requires_approval` boolean | passing |
| TC-EXP-07-A08 | Role matrix on list and get | Admin 200; Staff 200; Teacher, Student, Parent 403 | passing |
| TC-EXP-07-A09 | Tenant isolation: list and get with tenant B token | Rows of A absent; get by id 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-07-E01 | P2 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Read the tabs.<br>3. In "All Status" choose "Pending". | Before filtering: All (12), Pending (5), Approved (5), Paid (0), Cancelled (0) (the 2 rejected rows appear only under All); after: only the 5 pending rows, tab counts recomputed from the filtered load. | planned |
| TC-EXP-07-E02 | P2 | Web | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Set "From Date" 2026-09-11 and "To Date" 2026-09-11. | Only "Chart paper and markers for classrooms" (dated 2026-09-11) remains, without a new list request. | planned |
| TC-EXP-07-E03 | P3 | Web | Admin | Seeded transactions with vendor Indian Oil Petrol Bunk | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Type "indian oil" in "Vendor Name". | Only the two diesel rows (12000 and 11500) remain (case-insensitive match). | planned |
| TC-EXP-07-E04 | P1 | Web | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "View" (eye icon) in the "Balaji Book Depot" row. | Dialog "Transaction Details" shows Status Pending, Date, Vendor Balaji Book Depot, Type Stationery, Payment Method Cash, Amount Rs 850, Description Chart paper and markers for classrooms. | passing |
| TC-EXP-07-E05 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click the "Paid (0)" tab.<br>3. Click the "Cancelled (0)" tab. | Both tabs show "No transactions found." (no endpoint sets paid or cancelled). | planned |
| TC-EXP-07-E06 | P2 | Mobile | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Open Expense > Transactions on mobile.<br>2. In "Filters" choose "All Status" > "Pending".<br>3. Enter "2026-09-15" in "From date (YYYY-MM-DD)". | Step 2 lists the 5 pending transactions; step 3 leaves those dated on or after 2026-09-15 (Science lab models and charts, Trophies and medals for Sports Day); tab counts update. | planned |
| TC-EXP-07-E07 | P2 | Mobile | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Open Expense > Transactions on mobile.<br>2. Tap the "Chart paper and markers for classrooms" card. | Screen "Transaction Details" shows Description, Expense Type Stationery, Payment Method, Reference No CASH-0911, Created At and the Attachments card. | planned |

---

## F08 Edit a transaction

**Purpose**: Correct a transaction that has not been approved.

**Roles and permissions**: `expense_transactions:update`. Admin only by default (Staff has no update).

**Preconditions**: An existing transaction whose status is not `approved`.

**Steps, web**
1. On `/expense/transactions` click the row action "Edit" (visible with `update`). Dialog "Edit Transaction" is pre-filled with type, vendor, date, payment method, description, reference number and amount; items are not restored (always empty).
2. Change fields and click "Save Transaction". Toast "Transaction updated successfully".

**Steps, mobile**
1. From the list tap the edit icon (accessibility label "Edit") or on "Transaction Details" tap "Edit Transaction" (shown regardless of permission and status).
2. Edit screen fields as on create; "Save Changes". Success "Transaction updated successfully." Validation toasts begin with "Validation" (type, valid amount, description, vendor name, date).

**Expected results**: Row updated in place; `updated_at` changes; status, `requires_approval`, approval fields and `idempotency_key` are untouched; `version` is not incremented.

**API endpoints**
- `PUT /expense/transactions/{transaction_id}` body: any of `expense_type_id, amount, transaction_date, description, reference_number, payment_method, vendor_name, department_id, academic_year_id` (all optional; unknown keys such as `idempotency_key` are ignored).

**Rules and validations**
- Blocked only when status is `approved`: 400 `TRANSACTION_ALREADY_APPROVED`. `pending`, `rejected`, `paid`, `cancelled` can be edited; a rejected transaction stays rejected.
- `requires_approval` is recalculated on edit of a pending transaction when `amount`, `payment_method` or `requires_approval_override` changes (same rule as create), so raising the amount above 1000.00 queues it for approval and lowering it releases it. `requires_approval_override` is accepted on PUT (null removes the override).
- The new `department_id`, when different, must exist and be active. The new `expense_type_id` is not validated.
- Mobile cannot clear a department (it sends nothing when "No Department" is chosen).

**Error and edge cases**: Unknown id 404; bad body 422; 403 for roles without `update`.

**Unit-testable logic**: Approved guard; `exclude_unset` partial update; no recalculation of `requires_approval`; department check only on change.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-08-U01 | Service update on a pending transaction changing only `description` | Other fields unchanged | passing |
| TC-EXP-08-U02 | Service update on an approved transaction | 400 `TRANSACTION_ALREADY_APPROVED` | passing |
| TC-EXP-08-U03 | Service update of `amount` from 500.00 to 1500.00 on a pending, `requires_approval=false` row | `requires_approval` becomes True | passing |
| TC-EXP-08-U04 | Service update of `amount` from 1500.00 to 100.00 on a flagged row | `requires_approval` becomes False | passing |
| TC-EXP-08-U05 | Service update with the same `department_id` as stored (even if now inactive) | No department check | passing |
| TC-EXP-08-U06 | `ExpenseTransactionUpdate` with `amount=-5` | ValidationError | passing |
| TC-EXP-08-A01 | Admin `PUT` description and vendor on a pending transaction | 200 with new values; `status` still pending; `version` still 1 | passing |
| TC-EXP-08-A02 | `PUT` on an approved transaction | 400 `TRANSACTION_ALREADY_APPROVED` | passing |
| TC-EXP-08-A03 | `PUT` on a rejected transaction | 200; status remains `rejected` | passing |
| TC-EXP-08-A04 | `PUT` amount 500.00 to 1500.00 on a pending exempt row, then `GET /pending/approval` | Row is not in the approval queue (no recalculation) | passing |
| TC-EXP-08-A05 | `PUT` body including `idempotency_key` and `status` | Both ignored; response unchanged for those fields | passing |
| TC-EXP-08-A06 | `PUT` with an inactive `department_id` | 400 `INACTIVE_DEPARTMENT` | passing |
| TC-EXP-08-A07 | `PUT` unknown id; malformed id | 404 "Expense transaction not found"; 422 | passing |
| TC-EXP-08-A08 | Role matrix | Admin 200; Staff 403; Teacher, Student, Parent 403 | passing |
| TC-EXP-08-A09 | Tenant isolation: tenant B token updates tenant A's transaction | 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-08-E01 | P1 | Web | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "Edit" (pencil) in the "QA Power Co" row.<br>3. In "Edit Transaction" change Description to "QA Electricity bill September".<br>4. Click "Save Transaction". | Toast "Transaction updated successfully"; the row and the View dialog show the new description; status still Pending. | passing |
| TC-EXP-08-E02 | P3 | Web | Admin | Seeded approved transaction "Electricity bill for August 2026" (18450.00, vendor TSSPDCL) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "Edit" in the "TSSPDCL" row.<br>3. Change Description to "QA edit attempt" and click "Save Transaction". | The Edit icon is offered on the approved row; save fails with error toast "Cannot update approved transaction"; the row is unchanged (Known gaps 4). | planned |
| TC-EXP-08-E03 | P2 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Click "Expense" in the sidebar, then "Expense Transactions". | Rows show only the "View" action; no Edit, Approve or reject, or Delete icons. | planned |
| TC-EXP-08-E04 | P2 | Mobile | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done) | 1. Open Expense > Transactions on mobile.<br>2. Tap the "QA Electricity bill" card, then "Edit Transaction".<br>3. Change Total Amount to 650.<br>4. Tap "Save Changes". | Toast "Updated" with "Transaction updated successfully."; the list shows Rs 650.00. | planned |
| TC-EXP-08-E05 | P3 | Mobile | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done) | 1. Open the edit screen of "QA Electricity bill" on mobile.<br>2. Clear Vendor Name.<br>3. Tap "Save Changes". | Toast "Validation" with "Please enter a vendor name."; nothing is saved. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_transactions.py.

---

## F09 Delete a transaction (client action without a backend route)

**Purpose**: Both clients offer Delete on a transaction, but the backend has no `DELETE /expense/transactions/{id}`; this feature documents the expected failure so it is not mistaken for a working capability.

**Roles and permissions**: Clients gate the button on `expense_transactions:delete`, which is not in the default catalog, so only a custom grant shows it.

**Preconditions**: A user with a custom `expense_transactions:delete` grant (otherwise the button is hidden).

**Steps, web**
1. On `/expense/transactions` click the trash action ("Delete"). Confirm dialog "Delete Transaction": "Are you sure you want to delete this transaction?" with "Delete".
2. The request fails; the list is unchanged.

**Steps, mobile**
1. In the list tap the trash icon ("Delete"). Confirm "Delete Transaction": "Delete this transaction of <amount>?" with "Delete".
2. Toast "Delete Failed" "Could not delete transaction."

**Expected results**: No row changes. `ExpenseTransactionService.delete_transaction` (which would set `status='deleted'`) is not routed. The `deleted` status is nevertheless excluded by the financial reports.

**API endpoints**: `DELETE /expense/transactions/{transaction_id}` does not exist; because `GET` and `PUT` exist on the same path, FastAPI answers 405 Method Not Allowed.

**Rules and validations**: None server side.

**Error and edge cases**: 405 for any role; 401 without a token is not guaranteed (routing happens before auth), so assert only non-2xx.

**Unit-testable logic**: `delete_transaction` service function: approved guard and `status='deleted'` (unreachable code, test only to lock behaviour before a route is added).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-09-U01 | Service `delete_transaction` on a pending row | Sets `status="deleted"` and returns the success message | passing |
| TC-EXP-09-U02 | Service `delete_transaction` on an approved row | 400 `TRANSACTION_ALREADY_APPROVED` | passing |
| TC-EXP-09-A01 | Admin `DELETE /expense/transactions/{id}` | 405 and the row still exists | passing |
| TC-EXP-09-A02 | Staff, Teacher `DELETE` the same path | Non-2xx (405 or 403) and the row is untouched | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-09-E01 | P3 | Web | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done); a role with a custom expense_transactions:delete grant | 1. Sign in with the custom role.<br>2. Click "Expense" in the sidebar, then "Expense Transactions".<br>3. Click "Delete" (trash) on the "QA Power Co" row.<br>4. In "Delete Transaction" ("Are you sure you want to delete this transaction?") click "Delete". | Expected once routed: the transaction is removed from the list. Today the request fails and the row remains. | blocked: no DELETE /expense/transactions/{id} route (405) and no seeded role holds the delete grant (Known gaps 16) |
| TC-EXP-09-E02 | P3 | Mobile | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done); a role with a custom expense_transactions:delete grant | 1. Sign in with the custom role on mobile.<br>2. Open Expense > Transactions.<br>3. Tap the trash icon on the "QA Electricity bill" card and confirm "Delete". | Expected once routed: toast "Deleted" with "Transaction has been deleted.". Today the toast is "Delete Failed" with "Could not delete transaction." | blocked: no DELETE /expense/transactions/{id} route (405) and no seeded role holds the delete grant (Known gaps 16) |
| TC-EXP-09-E03 | P1 | Web | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Look at the Actions column of the "Balaji Book Depot" row. | Only "View", "Edit" and (pending row) "Approve or reject" icons; no "Delete" icon (the default catalog has no delete action). | passing |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_transactions.py.

---

## F10 Attachments

**Purpose**: Store supporting files (invoice, receipt, bill) against a transaction. Currently only the metadata is stored; the file bytes are discarded.

**Roles and permissions**: `expense_attachments:create` (upload), `:read` (get, list, download), `:update` (metadata), `:delete`. Admin has all four; Staff create and read.

**Preconditions**: An existing transaction.

**Steps, web**
1. In the create or edit dialog use "Upload Files" under "Attachments" (accepts several files; each row shows the file name, a trash button removes it). The chosen files are kept in browser state only and no upload request is made when the transaction is saved (defect, see Known gaps). There is no attachment list, download or delete control on the page.

**Steps, mobile**
1. Create flow: pick files with "Upload Files"; after the transaction is saved each file is uploaded (document type "invoice").
2. On "Transaction Details" the "Attachments" card shows "No attachments yet" or the files (name, document type and size in KB) with a download icon; "Add" (hidden when the status is approved or cancelled) opens "Add Attachment": "Document Type *" (placeholder "e.g. invoice, receipt, quote"), a file picker, "Cancel" and an upload button. Toasts "Uploaded" "Attachment uploaded successfully." or "Upload Failed". Download failure: "Download Failed".

**Expected results**: A row in `expense_attachments` with `original_filename`, `stored_filename = <uuid hex>_<name>`, `file_path="/temp/path"`, `file_size` = byte count, `mime_type="application/octet-stream"`, `file_hash_sha256="temp_hash"`, `virus_scan_status="pending"`, `retention_period_months=84`. Download returns the text `Mock file content for <original_filename>`, not the file.

**API endpoints**
- `POST /expense/attachments/transactions/{transaction_id}/upload?document_type=&department_id=` multipart field `file`; returns 201.
- `GET /expense/attachments/transactions/{transaction_id}/list`; `GET /expense/attachments/{attachment_id}`; `GET /expense/attachments/{attachment_id}/download`.
- `PUT /expense/attachments/{attachment_id}` body `{document_type, is_verified, verification_notes, department_id}`.
- `DELETE /expense/attachments/{attachment_id}` sets `is_archived=true` and returns the row.

**Rules and validations**
- `document_type` is required (query), max 50. Empty file: 400 "Empty file uploaded". More than 10 MB (10485760 bytes): 413 "File size exceeds 10MB limit". No type or extension whitelist.
- The transaction must exist (404 "Expense transaction not found"), whatever its status (approved included).
- Delete does not remove the row; the archived attachment still appears in the list.
- `file_extension` is the text after the last dot, empty when there is no dot.

**Error and edge cases**: Unknown attachment 404 "Expense attachment not found". Upload rate limit 20 per minute.

**Unit-testable logic**: Size and empty checks; stored filename and extension derivation; archive-on-delete.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-10-U01 | Extension derivation for "bill.final.pdf" and "README" | "pdf" and "" | passing |
| TC-EXP-10-U02 | `stored_filename` for "a.pdf" | Equals `<32 hex>_a.pdf` | passing |
| TC-EXP-10-U03 | Size guard with 0 bytes, 10485760 bytes, 10485761 bytes | 400, accepted, 413 | passing |
| TC-EXP-10-U04 | Service `delete_attachment` | Sets `is_archived=True`; row retained | passing |
| TC-EXP-10-A01 | Admin uploads a 1 KB text file with `document_type=invoice` | 201; `file_size=1024`, `file_path="/temp/path"`, `mime_type="application/octet-stream"`, `virus_scan_status="pending"`, `is_verified=false` | passing |
| TC-EXP-10-A02 | Upload without `document_type` | 422 | passing |
| TC-EXP-10-A03 | Upload an empty file | 400 "Empty file uploaded" | passing |
| TC-EXP-10-A04 | Upload exactly 10485760 bytes; then 10485761 bytes | 201; 413 | passing |
| TC-EXP-10-A05 | Upload to an unknown transaction | 404 "Expense transaction not found" | passing |
| TC-EXP-10-A06 | Upload to an approved transaction | 201 (no status guard) | passing |
| TC-EXP-10-A07 | `GET .../transactions/{id}/list` with two uploads | Two rows, newest first; unknown transaction 404 | passing |
| TC-EXP-10-A08 | `GET /expense/attachments/{id}` existing and unknown | 200; 404 | passing |
| TC-EXP-10-A09 | `GET .../{id}/download` | 200 `Content-Disposition: attachment; filename=<original>`; body `Mock file content for <original>` | passing |
| TC-EXP-10-A10 | `PUT` `{"is_verified": true, "verification_notes": "ok"}` | 200 with both fields set | passing |
| TC-EXP-10-A11 | `DELETE` then list | 200 `is_archived=true`; the row is still listed | passing |
| TC-EXP-10-A12 | Role matrix | Admin all 2xx; Staff 201 on upload and 200 on get, list, download, 403 on PUT and DELETE; Teacher, Student, Parent 403 | passing |
| TC-EXP-10-A13 | Tenant isolation | Tenant B token cannot read or download tenant A's attachment (404) | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-10-E01 | P2 | Web | Admin | Seeded type "Electricity Bill" (category Utilities); two small files available | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "New Transaction" and fill all required fields (Description "QA two files").<br>3. Under "Attachments" click "Upload Files" and pick both files.<br>4. Click "Save Transaction".<br>5. Call GET /expense/attachments/transactions/{id}/list. | Expected: both files are uploaded and listed for the transaction. Today the transaction saves but no upload request is sent and the list is empty. | blocked: web create and edit dialogs never upload attachments (Known gaps 3) |
| TC-EXP-10-E02 | P2 | Mobile | Admin | TC-EXP-06-E09 done | 1. Open Expense > Transactions on mobile.<br>2. Tap the "QA with bill" card. | The Attachments card lists the file with type invoice and its size in KB, with a download icon. | planned |
| TC-EXP-10-E03 | P1 | Mobile | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done); a small file available; works only on a native device (on Expo web the picked file is appended to FormData as a plain object and the API returns 422; needs a device check) | 1. Open the "QA Electricity bill" Transaction Details on mobile.<br>2. Tap "Add" on the Attachments card.<br>3. Enter Document Type * "receipt" and pick the file.<br>4. Tap the upload button. | Toast "Uploaded" with "Attachment uploaded successfully."; the file appears in the Attachments card with type receipt. | skipped: Expo web cannot upload: the screen appends the picked file as a plain {uri,name,type} object to FormData (work... |
| TC-EXP-10-E04 | P2 | Mobile | Admin | Seeded approved transaction "Electricity bill for August 2026" (18450.00, vendor TSSPDCL) | 1. Open Expense > Transactions on mobile.<br>2. Tap the "Electricity bill for August 2026" card. | The Attachments card has no "Add" button. | planned |
| TC-EXP-10-E05 | P3 | Mobile | Admin | TC-EXP-10-E03 done | 1. Open the "QA Electricity bill" Transaction Details on mobile.<br>2. Tap the download icon of the receipt. | The request succeeds; the content is the mock text, not the real file (Known gaps 14); no "Download Failed" toast. | planned |
| TC-EXP-10-E06 | P3 | Mobile | Admin | Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done) | 1. Open the "QA Electricity bill" Transaction Details on mobile.<br>2. Tap "Add".<br>3. Leave Document Type empty, pick a file and tap the upload button. | Toast "Validation" with "Please enter a document type"; nothing is uploaded. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_transactions.py.

---

## F11 Approval rules, thresholds and status workflow

**Purpose**: Decide when a transaction needs approval and how its status moves.

**Roles and permissions**: Evaluated on create by `ExpenseTransactionService.create_transaction`; the approve action needs `expense_transactions:approve` (Admin only by default).

**Preconditions**: None (computed on every create).

**Steps, web**: No separate screen. The result is visible as the "Requires Attention" count on the approvals page (F12) and the Pending tab (F07).

**Steps, mobile**: Same (approvals screen stat "Attention").

**Expected results**: Every new transaction has `status="pending"`. The only transitions that exist are `pending` to `approved` and `pending` to `rejected`, both through the approval endpoint and only when `requires_approval` is true. `paid`, `cancelled` and `deleted` are valid string values but no routed code sets them.

**API endpoints**: `POST /expense/transactions/` (create, F06) computes the flag; the transition is `POST /expense/transactions/{id}/approval` (F12).

**Rules and validations**
```
requires_approval = override or amount > Decimal("1000.00") or payment_method.lower() in ["check", "wire_transfer"]
```
- Strictly greater than 1000.00: 1000.00 is exempt, 1000.01 requires approval.
- `requires_approval_override = true` forces approval; `false` exempts the transaction from the amount and payment-method rules; null applies the rules.
- Clients send `cheque` and `bank_transfer`, so the payment-method clause never fires from the UI; only the amount rule and the override do.
- `ExpenseSettings` (for example `auto_approval_limit`) is ignored.
- A transaction that does not require approval stays `pending` forever and cannot be approved (F12).
- `requires_approval` is recalculated on edit of a pending transaction (F08).

**Error and edge cases**: `payment_method` casing is irrelevant (`Check`, `CHECK`). `amount` is compared as a `Decimal`, so 1000.0000001 cannot occur (2 decimal places enforced).

**Unit-testable logic**: The approval predicate (extract it or drive `create_transaction` with a fake session); the status transition table.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-11-U01 | amount 1000.00, cash, no override | `requires_approval=False` | passing |
| TC-EXP-11-U02 | amount 1000.01, cash | True | passing |
| TC-EXP-11-U03 | amount 999.99, upi | False | passing |
| TC-EXP-11-U04 | amount 0.00, cash | False | passing |
| TC-EXP-11-U05 | amount 10.00, payment_method "check" | True | passing |
| TC-EXP-11-U06 | amount 10.00, payment_method "Wire_Transfer" | True (case-insensitive) | passing |
| TC-EXP-11-U07 | amount 10.00, "cheque" | False (spelling used by the clients) | passing |
| TC-EXP-11-U08 | amount 10.00, "bank_transfer" | False | passing |
| TC-EXP-11-U09 | amount 10.00, `requires_approval_override=True` | True | passing |
| TC-EXP-11-U10 | amount 1000.01, `requires_approval_override=False` | False (override false exempts) | passing |
| TC-EXP-11-U11 | Settings row `auto_approval_limit=5000` present, amount 1500.00 | Still True (settings ignored) | passing |
| TC-EXP-11-U12 | Status transition table | Only pending to approved and pending to rejected are reachable | passing |
| TC-EXP-11-A01 | Create cash 1000.00 | `requires_approval=false`, `status=pending` | passing |
| TC-EXP-11-A02 | Create cash 1000.01 | `requires_approval=true`, `status=pending` | passing |
| TC-EXP-11-A03 | Create `payment_method="check"` amount 5.00 | `requires_approval=true` | passing |
| TC-EXP-11-A04 | Create `payment_method="cheque"` amount 5.00 | `requires_approval=false` | passing |
| TC-EXP-11-A05 | Create with `requires_approval_override=true` amount 5.00 | `requires_approval=true`; response echoes `requires_approval_override=true` | passing |
| TC-EXP-11-A06 | Create exempt transaction, then try to approve it | 400 `TRANSACTION_NO_APPROVAL_REQUIRED` (see F12) | passing |
| TC-EXP-11-A07 | After create, status values over time | Never `paid` or `cancelled` through any endpoint | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-11-E01 | P1 | Web | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "New Transaction"; Expense Type "Electricity Bill", Vendor "QA Gen Services", Payment Method "Cash", Description "QA Generator repair", Total Amount 1500.<br>3. Click "Save Transaction".<br>4. Open Expense > Expense Approvals. | The new transaction is listed; "Pending Approvals" and "Requires Attention" each include it; stored requires_approval true. | passing |
| TC-EXP-11-E02 | P2 | Web | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Open Expense > Expense Approvals.<br>2. Click "Expense" in the sidebar, then "Expense Transactions".<br>3. Click the "Pending" tab. | "Chart paper and markers for classrooms" (850.00) is not in the approvals queue but is listed under Pending on the Transactions page. | planned |
| TC-EXP-11-E03 | P2 | Mobile | Admin | Seeded type "Electricity Bill" (category Utilities) | 1. Open Expense > Transactions > "New Transaction" on mobile.<br>2. Fill Expense Type "Electricity Bill", Total Amount 1000.01, Description "QA threshold", Vendor "QA Vendor"; tap "Save Transaction".<br>3. Open the drawer and choose Expense > Expense Approvals. | "QA threshold" is listed; "Attention" counts it. | planned |
| TC-EXP-11-E04 | P3 | Web | Admin | TC-EXP-11-E01 done | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "Paid (0)" and "Cancelled (0)". | Both tabs show "No transactions found." | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_transactions.py.

---

## F12 Pending approvals and approve or reject

**Purpose**: Let an approver review transactions that require approval and approve or reject them with a mandatory comment.

**Roles and permissions**: `expense_transactions:approve` for the decision (`POST .../approval`); `expense_transactions:list` for the queue (`GET /pending/approval`); the web page is guarded by `expense_transactions:approve`; the mobile screen by read or list and shows buttons only with approve. Admin by default.

**Preconditions**: At least one pending transaction with `requires_approval=true` (F11).

**Steps, web**
1. Open the approvals page (`/expense/approvals`, header "Pending Approvals", subtitle "Review and process expense approval requests"). Stat cards "Pending Approvals", "Total Amount" (sum of the listed amounts) and "Requires Attention" (count with `requires_approval`).
2. Search "Search by description, type or status..."; sort by Transaction, Amount, Type, Submitted or Status. Columns S.No., Transaction, Amount, Type (payment method), Submitted (date), Status, Actions.
3. Actions: "View Details" (dialog "Transaction Details", with Approve and Reject buttons), "Approve", "Reject". Each opens a dialog titled "Approve Transaction" or "Reject Transaction": text "Are you sure you want to approve this expense transaction?" (or reject), "Comment *" textarea (placeholder "Enter a comment for approval..." or "...rejection..."), buttons "Cancel" and "Approve Transaction" or "Reject Transaction"; the confirm button stays disabled until the comment is non-empty and shows "Processing..." while pending.
4. Toast "Transaction approved successfully" or "Transaction rejected". The list refetches. Empty queue: heading "All Caught Up!" and "There are no pending expense approvals at this time." Staff and Teacher get "Access Denied" with "You don't have permission to approve expense transactions."
5. The Transactions page also offers "Approve or reject" (shown on every pending row for users with approve) with a dialog "Approve Transaction", "Approval Comment *" (placeholder "Enter approval comment"), buttons "Approve" and "Reject".

**Steps, mobile**
1. Open Expense Approvals from the drawer (title "Expense Approvals"). Stats "Pending", "Total Amount", "Attention". Search "Search by description, vendor or status...".
2. Each item has "Approve" and "Reject" (approve permission only; Staff sees the list without them). The modal "Approve Transaction" or "Reject Transaction" has "Approval Comment *" (placeholder "Enter approve comment" or "Enter reject comment"), "Cancel" and "Approve" or "Reject" ("Processing..." while pending). Empty comment: "Error" "Please enter an approval comment". On success the modal closes without a toast; failure "Failed to approve transaction" (or reject). Empty list: "No pending approvals". "Transaction Details" also shows Approve and Reject for pending transactions; there success shows "Approved" (or "Rejected") with "Transaction has been approved."

**Expected results**: Approve sets `status="approved"`, `approved_by_user_id`, `approved_by_role`, `approved_at` (server time) and `approval_comment`. Reject sets `status="rejected"` with the same stamps. Approved transactions can no longer be edited (F08).

**API endpoints**
- `GET /expense/transactions/pending/approval?skip=&limit=` returns pending rows with `requires_approval=true`, oldest first; `skip` and `limit` are validated (limit 1-500, default 50) but not applied.
- `POST /expense/transactions/{transaction_id}/approval` body `{action: "approve"|"reject", approval_comment (1-500)}` returns the updated row.

**Rules and validations**
- Allowed only when status is `pending` (else 400 `TRANSACTION_NOT_PENDING`, message "Transaction is already <status>") and `requires_approval` is true (else 400 `TRANSACTION_NO_APPROVAL_REQUIRED`). These checks run before the action is validated.
- Any other `action` text: 400 `INVALID_APPROVAL_ACTION`. Empty comment or over 500 characters: 422.
- There is no separation of duties: the creator can approve their own transaction if they hold the permission.
- Single step; no multi-level approval.

**Error and edge cases**: Unknown id 404. Approving twice: second call 400 `TRANSACTION_NOT_PENDING`. Rejected transactions cannot be re-approved. Clients cap neither the 500-character comment length nor show the API message in detail.

**Unit-testable logic**: Decision guards and stamping in `approve_transaction`; queue ordering; web stat aggregation (sum, attention count); search and sort on the queue.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-12-U01 | Service approve on pending+flagged | `status="approved"`, stamps set, comment stored | passing |
| TC-EXP-12-U02 | Service reject on pending+flagged | `status="rejected"`, stamps set | passing |
| TC-EXP-12-U03 | Service approve on a non-pending row | 400 `TRANSACTION_NOT_PENDING` with the current status in the message | passing |
| TC-EXP-12-U04 | Service approve on pending but `requires_approval=False` | 400 `TRANSACTION_NO_APPROVAL_REQUIRED` | passing |
| TC-EXP-12-U05 | Service with `action="cancel"` on a valid row | 400 `INVALID_APPROVAL_ACTION` | passing |
| TC-EXP-12-U06 | Order of checks: `action="cancel"` on an already approved row | Reports `TRANSACTION_NOT_PENDING` first | passing |
| TC-EXP-12-U07 | Schema: comment "" and 501 chars | Rejected; 500 accepted | passing |
| TC-EXP-12-U08 | Web stats for queue amounts 1200.50 and 3000.00 | "Total Amount" 4200.50; "Requires Attention" 2 | blocked: queue stats are inline in web/src/pages/expense/approvals.tsx; needs the helper exported |
| TC-EXP-12-A01 | Admin approves a flagged pending transaction with comment "OK" | 200; `status=approved`, `approved_by_role="Admin"`, `approved_at` not null, `approval_comment="OK"` | passing |
| TC-EXP-12-A02 | Admin rejects a flagged pending transaction | 200; `status=rejected` | passing |
| TC-EXP-12-A03 | Approve the same transaction twice | 400 `TRANSACTION_NOT_PENDING` the second time | passing |
| TC-EXP-12-A04 | Approve a rejected transaction | 400 `TRANSACTION_NOT_PENDING` | passing |
| TC-EXP-12-A05 | Approve a pending but exempt (500.00 cash) transaction | 400 `TRANSACTION_NO_APPROVAL_REQUIRED` | passing |
| TC-EXP-12-A06 | `action="bogus"` | 400 `INVALID_APPROVAL_ACTION` | passing |
| TC-EXP-12-A07 | Empty comment; 501-char comment; missing action | 422 each | passing |
| TC-EXP-12-A08 | Unknown id; malformed id | 404; 422 | passing |
| TC-EXP-12-A09 | `GET /pending/approval` with 2 flagged, 1 exempt, 1 approved | Exactly the 2 flagged pending, oldest first | passing |
| TC-EXP-12-A10 | `GET /pending/approval?limit=1` with 2 queued | Returns both (limit not applied); `limit=0` and `limit=501` return 422 | passing |
| TC-EXP-12-A11 | After approval, `PUT` the transaction | 400 `TRANSACTION_ALREADY_APPROVED` | passing |
| TC-EXP-12-A12 | Role matrix on approve: Admin 200; Staff, Teacher, Student, Parent 403 | As stated | passing |
| TC-EXP-12-A13 | Role matrix on `GET /pending/approval`: Admin 200; Staff 200 (has list); Teacher, Student, Parent 403 | As stated | passing |
| TC-EXP-12-A14 | The creator (Admin) approves their own transaction | 200 (no separation of duties) | passing |
| TC-EXP-12-A15 | Tenant isolation: tenant B approves tenant A's transaction | 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-12-E01 | P1 | Web | Admin | Seeded pending transaction "Broadband plan renewal for office" (1499.00, UPI, vendor ACT Fibernet, requires approval) | 1. Open Expense > Expense Approvals.<br>2. Click "Approve" (title Approve) in the "Broadband plan renewal for office" row.<br>3. In "Approve Transaction" enter Comment * "QA approved".<br>4. Click "Approve Transaction". | Toast "Transaction approved successfully"; the row leaves the queue; Pending Approvals drops by one and Total Amount by 1499; stored status approved with approved_by_role Admin. | passing |
| TC-EXP-12-E02 | P2 | Web | Admin | Seeded pending transaction "Trophies and medals for Sports Day" (6400.00, vendor Champion Sports, requires approval) | 1. Open Expense > Expense Approvals.<br>2. Click "Reject" in the "Trophies and medals for Sports Day" row.<br>3. Enter Comment * "QA rejected, quote too high".<br>4. Click "Reject Transaction".<br>5. Click "Expense" in the sidebar, then "Expense Transactions". | Toast "Transaction rejected"; the row leaves the queue; on Transactions the row shows a Rejected badge. | planned |
| TC-EXP-12-E03 | P3 | Web | Admin | Seeded pending transaction "Science lab models and charts" (22500.00, vendor Scientific Traders, requires approval) | 1. Open Expense > Expense Approvals.<br>2. Click "Approve" in the "Science lab models and charts" row.<br>3. Leave Comment * empty. | "Approve Transaction" stays disabled until a comment is typed; Cancel closes without a change. | planned |
| TC-EXP-12-E04 | P3 | Web | Admin | No pending transaction requires approval (all seeded ones approved or rejected) | 1. Open Expense > Expense Approvals. | Stat cards show 0 and Rs 0.00; heading "All Caught Up!" with "There are no pending expense approvals at this time." | planned |
| TC-EXP-12-E05 | P2 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Open Expense > Expense Approvals. | "Access Denied" with "You don't have permission to approve expense transactions." | planned |
| TC-EXP-12-E06 | P3 | Web | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Click "Expense" in the sidebar, then "Expense Transactions".<br>2. Click "Approve or reject" in the "Balaji Book Depot" row (850.00, exempt).<br>3. Enter Approval Comment * "QA try".<br>4. Click "Approve". | Error toast "This transaction does not require approval"; status stays Pending (the action is offered where it cannot succeed, Known gaps 4). | planned |
| TC-EXP-12-E07 | P1 | Mobile | Admin | Seeded pending transaction "Science lab models and charts" (22500.00, vendor Scientific Traders, requires approval) | 1. Sign in as Admin on mobile.<br>2. Open the drawer and choose Expense > Expense Approvals.<br>3. Tap "Approve" on "Science lab models and charts".<br>4. Enter Approval Comment * "QA mobile approve".<br>5. Tap "Approve". | Modal "Approve Transaction" closes; the card leaves the list and the "Pending" stat drops by one (this screen shows no success toast). | passing |
| TC-EXP-12-E08 | P3 | Mobile | Admin | Seeded pending transaction "Diesel for school buses (September)" (12000.00, vendor Indian Oil Petrol Bunk, requires approval) | 1. Open Expense Approvals on mobile.<br>2. Tap "Reject" on "Diesel for school buses (September)".<br>3. Leave the comment empty and tap "Reject". | Toast "Error" with "Please enter an approval comment"; the modal stays open; nothing changes. | planned |
| TC-EXP-12-E09 | P2 | Mobile | Admin | Seeded pending transaction "Diesel for school buses (September)" (12000.00, vendor Indian Oil Petrol Bunk, requires approval) | 1. Open Expense > Transactions on mobile and tap "Diesel for school buses (September)".<br>2. On "Transaction Details" tap "Approve", enter a comment and confirm "Approve". | Toast "Approved" with "Transaction has been approved."; the status badge shows Approved; the Attachments "Add" button disappears. | planned |
| TC-EXP-12-E10 | P3 | Web | Admin | Pending transaction "QA Generator repair" (TC-EXP-11-E01 done) | 1. Open Expense > Expense Approvals.<br>2. Click "Approve" on "QA Generator repair".<br>3. Paste a 501-character comment.<br>4. Click "Approve Transaction". | Error toast from the 422 response; the row stays in the queue (clients do not cap the comment, Known gaps 5). | planned |
| TC-EXP-12-E11 | P3 | Mobile | Staff | At least one seeded transaction pending approval | 1. Sign in as Staff on mobile.<br>2. Open /expense/approvals. | The list loads with the stats; no "Approve" or "Reject" buttons are shown. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_transactions.py.

---

## F13 Expense summary (Category, Type, Entries)

**Purpose**: See all spending grouped Category to Type to entries, with subtotals and a grand total.

**Roles and permissions**: `expense_transactions:list` (web page and endpoint). Admin and Staff.

**Preconditions**: Transactions exist; optional academic year for the filter.

**Steps, web**
1. Open `/expense/summary`. Header "Expense Summary", subtitle "Category-wise breakdown of all expenses with type-level details and totals".
2. Choose "Academic Year:" ("All Years" or a year). There are no date or status controls. Search box "Search by category, type, description or vendor...".
3. Read cards "Grand Total", "Categories", "Total Entries", then each category block (with "Category Total:"), type blocks with the entries table (Description, Date, Vendor, Method, Status, Amount) and "Type Total:". Footer "Grand Total". Empty state "No Expense Data" or "No Results Found".

**Steps, mobile**
1. Open Expense then "Summary" (title "Expense Summary"). Academic year picker ("All Years"), cards "Grand Total", "Categories", "Total Entries", category sections "Category Total:", "No types in this category".
2. The screen does not call `GET /expense/summary/`. It lists every category from `GET /expense/categories/?active_only=false` (inactive ones included) and takes the amounts from the by-category and by-type reports (every status counts); the year picker filters the reports by the year's start and end dates. Its totals can therefore differ from web (Known gaps 19).

**Expected results**: Totals are sums of the entry amounts. The default view includes every status except `cancelled` (so `pending` and `rejected` are counted).

**API endpoints**
- `GET /expense/summary/?academic_year_id=&start_date=&end_date=&status_filter=` returns `{categories: [{category_id, category_name, category_description, types: [{type_id, type_name, type_description, entries: [{id, amount, description, transaction_date, payment_method, vendor_name, status, reference_number}], type_total, entry_count}], category_total, entry_count}], grand_total, total_entries, academic_year_id, academic_year_title, start_date, end_date, generated_at}`.

**Rules and validations**
- Only active categories and, inside them, active types are included; transactions of inactive types or categories vanish from the summary.
- Categories ordered by name, types by name, entries by date descending.
- `status_filter` replaces the default exclusion (for example `approved` returns only approved); without it `status != 'cancelled'`.
- Dates inclusive. An unknown `academic_year_id` returns `academic_year_title=null` and no error. Rows created from the UI have a null academic year, so a year filter excludes them.
- Amounts are decimal strings.

**Error and edge cases**: Empty tenant returns `categories: []`, `grand_total: "0"`. Category with no types returns an empty `types` list.

**Unit-testable logic**: Subtotal and grand total arithmetic; default status exclusion; filter composition; ordering.

**Test cases**

Fixture used below (all in one tenant, categories active): Utilities has types Electricity (entries 1200.00 approved dated 2026-08-15, 300.50 pending dated 2026-08-20) and Water (150.25 pending dated 2026-09-05); Infrastructure has type Repairs (5000.00 rejected dated 2026-09-10); one cancelled entry of 99.99 under Electricity. The Repairs entry becomes `rejected` through the approval endpoint (5000.00 requires approval); the cancelled entry has to be inserted directly in the test database because no endpoint sets `cancelled`.

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-13-U01 | Totals for the fixture with no filter | Electricity 1500.50 (2), Water 150.25 (1), Utilities 1650.75 (3), Repairs 5000.00 (1), Infrastructure 5000.00 (1), grand_total 6650.75, total_entries 4 (cancelled excluded) | passing |
| TC-EXP-13-U02 | `status_filter="approved"` | grand_total 1200.00, total_entries 1 | passing |
| TC-EXP-13-U03 | `status_filter="cancelled"` | grand_total 99.99, total_entries 1 (default exclusion replaced) | passing |
| TC-EXP-13-U04 | `start_date=2026-09-01`, `end_date=2026-09-30` | Entries 150.25 and 5000.00; grand_total 5150.25 | passing |
| TC-EXP-13-U05 | Boundary: `end_date=2026-08-15` | Includes the 2026-08-15 entry (inclusive) | passing |
| TC-EXP-13-U06 | Entry ordering inside a type | Newest `transaction_date` first | passing |
| TC-EXP-13-U07 | Empty database | `categories=[]`, `grand_total=0`, `total_entries=0` | passing |
| TC-EXP-13-A01 | `GET /expense/summary/` for the fixture | Matches U01 and every entry has the documented fields | passing |
| TC-EXP-13-A02 | `?status_filter=approved` and `?status_filter=pending` | 1200.00 and 450.75 (300.50 + 150.25) | passing |
| TC-EXP-13-A03 | Date range filter as in U04 | grand_total "5150.25" | passing |
| TC-EXP-13-A04 | `?academic_year_id=<valid year>` where no transaction has that year | `categories` listed with zero totals; `academic_year_title` set | passing |
| TC-EXP-13-A05 | `?academic_year_id=<unknown uuid>` | 200 with `academic_year_title=null` | passing |
| TC-EXP-13-A06 | Create a transaction with an `academic_year_id`, then filter by that year | Only that transaction counted | passing |
| TC-EXP-13-A07 | Deactivate the Water type | Its 150.25 disappears from the summary | passing |
| TC-EXP-13-A08 | Malformed `start_date` ("2026-13-45") | 422 | passing |
| TC-EXP-13-A09 | Role matrix | Admin 200; Staff 200; Teacher, Student, Parent 403 | passing |
| TC-EXP-13-A10 | Tenant isolation | Tenant B summary excludes tenant A's categories and entries | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-13-E01 | P1 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions; once QA transactions exist the totals cannot stay at Rs 2,09,949.00 and 12 entries, so assert them relative to the API) | 1. Open Expense > Expense Summary.<br>2. Read the cards and the "Utilities" block. | Cards Grand Total Rs 2,09,949.00, Categories 5, Total Entries 12; Utilities shows Electricity Bill 18,450.00, Water Bill 3,200.00, Internet and Telephone 1,499.00 with "Type Total:" each and "Category Total:" 23,149.00; the footer Grand Total equals the card. | passing |
| TC-EXP-13-E02 | P2 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions); Transaction "QA Electricity bill" (500.00, cash, vendor QA Power Co, pending) exists (TC-EXP-06-E01 done) | 1. Open Expense > Expense Summary.<br>2. In "Academic Year:" choose "2026-2027". | Totals re-fetch; the 12 seeded rows (which carry the year) stay, but QA Electricity bill (created from the UI, no academic year) drops out (module rule 7). | planned |
| TC-EXP-13-E03 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Summary.<br>2. Type "Diesel" in "Search by category, type, description or vendor...". | Only Transport and Fuel > Fuel with the two diesel entries remains. | planned |
| TC-EXP-13-E04 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Summary.<br>2. Type "QA no such expense" in the search box. | Empty state "No Results Found" ("No Expense Data" appears only when the tenant has no expenses at all). | planned |
| TC-EXP-13-E05 | P2 | Mobile | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Open Expense > Summary on mobile.<br>2. Compare Grand Total and the Utilities section with the web page. | Expected: the same totals as web. Today the screen lists every category, inactive ones included, and takes amounts from the reports, so totals can differ. | blocked: mobile summary is built from categories and the by-category and by-type reports, not GET /expense/summary (Known gaps 19) |
| TC-EXP-13-E06 | P3 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Open Expense > Expense Summary. | The summary renders with the same totals as for Admin. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_reporting.py (aggregation arithmetic from mocked rows; filter predicates asserted on the compiled SQL).

---

## F14 Expense reports (by category, by type, trend, quick summary, export)

**Purpose**: Analyse spend by category, by type or by month over a date range.

**Roles and permissions**: `expense_reports:read` for the four read endpoints, `expense_reports:export` for export. Web page guard is `expense_reports:list` (differs from the API). Admin by default; Staff has none.

**Preconditions**: Transactions exist.

**Steps, web**
1. Open `/expense/reports` (header "Expense Reports", subtitle "Generate and analyze expense reports"). The tenant must have a menu entry for it (demo catalog: "Expense Reports") or the URL is typed.
2. In "Report Configuration" choose "Report Type" (By Category, By Type, Trend Analysis), "Start Date" and "End Date" (default last 30 days; start cannot pass end). Click "Generate Report".
3. The page loads the report for the default range on open. Tables: "Category Breakdown" (Category, Total Amount, Transactions, Average, % of Total), "Type Breakdown" (Type, Category, Total Amount, Transactions, Average), "Monthly Trends" (Month, Total Amount, Transactions, Average per Transaction), with summary cards (Total Amount, Total Transactions, Categories, Expense Types, Period, Data Points; the Categories card shows 0 because `categories_count` is always 0). There is no export button. Staff gets "Access Denied" with "You don't have permission to view expense reports."

**Steps, mobile**
1. Open Expense Reports from the drawer (title "Expense Reports"). "Date Range" with start and end date, "Apply", quick "Last 30 Days", the line "Showing: <start> to <end>", tabs "By Category", "By Type", "Trend" and cards Total Amount, Total Transactions, Average per Transaction, Categories; error "Start date must be on or before the end date". Section titles "Category Breakdown", "Type Breakdown", "Monthly Trends". "Retry" on failure. No export.

**Expected results**: Reports include every status (including rejected and pending); there is no default status exclusion.

**API endpoints**
- `GET /expense/reports/by-category?start_date=&end_date=&category_ids=&type_ids=&status_filter=&department_id=&min_amount=&max_amount=` returns `{summary, categories: [{category_id, category_name, total_amount, transaction_count, average_amount, percentage_of_total}], generated_at, generated_by}`.
- `GET /expense/reports/by-type?...` returns `{summary, types: [{type_id, type_name, category_name, total_amount, transaction_count, average_amount}], ...}`.
- `GET /expense/reports/trend?...` (no amount filters) returns `{summary, monthly_trends: [{month "YYYY-MM", total_amount, transaction_count, average_per_transaction}], ...}`.
- `GET /expense/reports/summary?period_days=30` returns `{period_days, total_amount, total_transactions, average_transaction, top_categories (first 5), generated_at}`; `period_days` 1-365.
- `POST /expense/reports/export` body `{report_type, export_format (csv|excel|pdf|json), filters, include_details}` returns a mock `{export_id: 12345678-1234-5678-9012-123456789012, status: "pending", ...}`.
- `GET /expense/reports/export/{export_id}/status` returns a mock with `status="completed"` and a `file_url` that does not exist.

**Rules and validations**
- `percentage_of_total = category total / grand total x 100`, rounded to 2 places; 0 when the grand total is 0.
- `average_transaction` = total / count, rounded to 2 places; 0 when count is 0. Category and type averages are the database average.
- Summary period: `start_date = today - (period_days - 1)`, `end_date = today`; `report_period = "Custom (<start> to <end>)"` when both dates are given. Without dates the summary dates default to the first of the current month and today.
- Filters: date range inclusive; `category_ids` and `type_ids` accept repeated parameters; `min_amount` and `max_amount` must be `>= 0` (0 is ignored as "no filter").
- Department scoping: a role not named admin, tenant admin or super admin is restricted to rows with a null department unless it filters by department; the access token carries no department claim, so this applies to every non-Admin role (latent, since only Admin has report access by default).
- `categories_count` and `departments_count` in the summary are always 0.
- Export is a stub: it does not read `filters`, ignores the format and generates no file. Mobile posts to `/expense/reports` (no `/export`), which does not exist.

**Error and edge cases**: No data returns empty lists and zero totals (`generated_by` is the username). `period_days=0` or 366: 422. A non-existent category id in `category_ids` returns empty results.

**Unit-testable logic**: Percentage and average arithmetic and rounding; summary date window; filter builder; month grouping and formatting; top-5 slice.

**Test cases**

Fixture: same as F13 (without the cancelled row it totals 6650.75 for four non-cancelled rows; the cancelled 99.99 row is also included by reports because reports have no default status exclusion, giving 6750.74 over five rows). For percentage tests use the four-row variant noted in each case.

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-14-U01 | Percentages for Utilities 1650.75 and Infrastructure 5000.00 of 6650.75 | 24.82 and 75.18 | passing |
| TC-EXP-14-U02 | Percentage when grand total is 0 | 0 for every category | passing |
| TC-EXP-14-U03 | `average_transaction` for 6650.75 over 4 | 1662.69 (1662.6875 rounded to 2 places) | passing |
| TC-EXP-14-U04 | `average_transaction` with 0 transactions | 0.00 | passing |
| TC-EXP-14-U05 | Summary date window for `period_days=30` on 2026-10-02 | start 2026-09-03, end 2026-10-02 | passing |
| TC-EXP-14-U06 | Summary date window for `period_days=1` | start equals end equals today | passing |
| TC-EXP-14-U07 | `report_period` text with both dates | "Custom (2026-08-01 to 2026-08-31)" | passing |
| TC-EXP-14-U08 | Filter builder with `min_amount=0` | No amount predicate added | passing |
| TC-EXP-14-U09 | Department scoping for role "Staff" without a department id | Adds `department_id IS NULL` | passing |
| TC-EXP-14-U10 | Department scoping for role "admin" (any case) | No scoping predicate | passing |
| TC-EXP-14-U11 | Month key formatting of 2026-08-15 | "2026-08" | passing |
| TC-EXP-14-A01 | `GET /expense/reports/by-category` (four-row fixture, no filters) | Categories ordered by total descending: Infrastructure 5000.00 (1, avg 5000.00, 75.18) then Utilities 1650.75 (3, avg 550.25, 24.82); summary total 6650.75, 4 transactions, average 1662.69 | passing |
| TC-EXP-14-A02 | `GET /expense/reports/by-type` | Repairs 5000.00, Electricity 1500.50 (2), Water 150.25 (1), each with its `category_name` | passing |
| TC-EXP-14-A03 | `GET /expense/reports/trend` | `monthly_trends` "2026-08" total 1500.50 (2, avg 750.25) and "2026-09" total 5150.25 (2, avg about 2575.125); summary total 6650.75 | passing |
| TC-EXP-14-A04 | `?start_date=2026-09-01&end_date=2026-09-30` on by-category | Utilities 150.25 (1) and Infrastructure 5000.00 (1) | passing |
| TC-EXP-14-A05 | `?status_filter=approved` | Only the 1200.00 entry | passing |
| TC-EXP-14-A06 | `?min_amount=1000&max_amount=2000` | Only the 1200.00 entry; `min_amount=-1` returns 422 | passing |
| TC-EXP-14-A07 | Repeated `category_ids=<id>` parameters | Only those categories | passing |
| TC-EXP-14-A08 | `?department_id=<d>` | Only that department's rows | passing |
| TC-EXP-14-A09 | `GET /expense/reports/summary?period_days=30` | `period_days=30`, totals for the last 30 days, `top_categories` at most 5 items | passing |
| TC-EXP-14-A10 | `summary?period_days=0` and `366` | 422 | passing |
| TC-EXP-14-A11 | Empty tenant | by-category `categories=[]`, summary totals 0, no error | passing |
| TC-EXP-14-A12 | `POST /expense/reports/export` `{report_type:"category", export_format:"csv", filters:{}}` | 200 with the fixed `export_id`, `status="pending"`, `export_format="csv"`; no file produced | passing |
| TC-EXP-14-A13 | `POST` export with `export_format="xlsx"` | 422 (allowed values are csv, excel, pdf, json) | passing |
| TC-EXP-14-A14 | `GET /expense/reports/export/{any uuid}/status` | 200 `status="completed"` with a `file_url` that returns 404 when requested | passing |
| TC-EXP-14-A15 | Role matrix: read endpoints | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-EXP-14-A16 | Role matrix: export | Admin 200; others 403 | passing |
| TC-EXP-14-A17 | Tenant isolation | Tenant B reports exclude tenant A's transactions | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-14-E01 | P1 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Open Expense > Expense Reports.<br>2. Keep Report Type "By Category"; set Start Date 2026-09-01 and End Date 2026-09-30.<br>3. Click "Generate Report". | Total Amount Rs 2,09,949.00 and Total Transactions 12 (every status counts); "Category Breakdown" lists the 5 seeded categories with Total Amount, Transactions, Average and "% of Total" (Infrastructure 80,750.00 first); the "Categories" card shows 0 (Known gaps 8). | passing |
| TC-EXP-14-E02 | P2 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Open Expense > Expense Reports.<br>2. Choose Report Type "Trend Analysis", Start Date 2026-09-01, End Date 2026-09-30.<br>3. Click "Generate Report". | "Monthly Trends" shows one row 2026-09 with Total Amount 2,09,949.00 and Transactions 12. | planned |
| TC-EXP-14-E03 | P3 | Web | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense > Expense Reports.<br>2. Open the Start Date picker and try a date after End Date. | Dates after End Date cannot be picked (min and max bounds). | planned |
| TC-EXP-14-E04 | P3 | Web | Admin | A custom role with expense_reports:list but not read, and a user in it (Administration > Roles) | 1. Sign in as that user.<br>2. Open /expense/reports.<br>3. Click "Generate Report". | The page renders but every report call returns 403 and an error is shown (guard and API disagree, Known gaps 8). | planned |
| TC-EXP-14-E05 | P2 | Mobile | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Open the drawer and choose Expense > Expense Reports.<br>2. Set the Date Range 2026-09-01 to 2026-09-30 and tap "Apply".<br>3. Tap "By Category", "By Type" and "Trend" in turn. | "Showing: 1 Sept 2026 to 30 Sept 2026"; cards Total Amount Rs 2,09,949.00, Total Transactions 12, Average per Transaction, Categories; sections "Category Breakdown", "Type Breakdown", "Monthly Trends" with data. "Last 30 Days" resets the range. | planned |
| TC-EXP-14-E06 | P3 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense Reports on mobile.<br>2. Set the start date after the end date.<br>3. Tap "Apply". | Message "Start date must be on or before the end date"; the report is not reloaded. | planned |
| TC-EXP-14-E07 | P2 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Open Expense > Expense Reports. | "Access Denied" with "You don't have permission to view expense reports." | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_reporting.py.

---

## F15 Audit trail

**Purpose**: Review who did what to expenses. The screens and read endpoints work, but no audit row is ever written, so the trail is always empty.

**Roles and permissions**: `expense_audit_logs:read` for all read endpoints, `expense_audit_logs:delete` plus the role-name rule for delete. Admin has read and delete in the catalog; delete still returns 403 for role "Admin".

**Preconditions**: `expense_audit_logs` permissions seeded (the expense seed script does not cover them).

**Steps, web**
1. Open `/expense/audit` (header "Expense Audit & Compliance"). Tabs "Overview", "Transaction Audit", "Audit Logs".
2. Overview shows "Total Transactions" ("Under audit") and "Audit Summary" with "Select a transaction to view detailed audit information". The "Transaction Audit" tab holds "Transaction Selection" with search "Search transactions...", a department dropdown ("All Departments") and a table (S.No., Description, Amount, Department, Status, Actions with "View Audit").
3. After "View Audit" the Audit Logs tab shows counters "Total Logs", "Creation", "Updates", "Approvals" and either entries or "No audit logs found for this transaction". Before selecting: "Select a Transaction" with "Choose a transaction from the "Transaction Audit" tab to view its audit logs". Staff gets "Access Denied" with "You don't have permission to view expense audit logs."

**Steps, mobile**
1. Open Expense Audit from the drawer (screen title "Expense Audit Trail"). Search "Search by action, user or notes", category chips All, Transaction, Attachment, Category, Type, and a calendar button ("Select date") that opens "From" and "To" ("YYYY-MM-DD") with "Clear". Empty state "No audit logs found"; "Retry" on error.

**Expected results**: Because every `create_audit_log` call is commented out (categories, types, transactions, attachments) and approvals do not log, lists are empty after any write. The `ExpenseAuditLog` table and read paths are ready.

**API endpoints**
- `GET /expense/audit/logs?skip=&limit=&transaction_id=&action=&action_category=&actor_user_id=` (limit 1-500, default 50), newest first.
- `GET /expense/audit/logs/{audit_log_id}`.
- `GET /expense/audit/transactions/{transaction_id}/logs?skip=&limit=`; no check that the transaction exists.
- `GET /expense/audit/transactions/{transaction_id}/summary` returns `{transaction_id, total_entries, action_breakdown, first_entry, last_entry, unique_actors}`; the route is defined twice and only the first definition answers.
- `DELETE /expense/audit/logs/{audit_log_id}` hard delete.

**Rules and validations**: Delete requires the role name `super_admin` or `tenant_admin` in the service (403 "Only administrators can delete audit logs"); the check runs before the lookup, so an unknown id also returns 403 for Admin.

**Error and edge cases**: Unknown log id 404 "Audit log not found" (for roles that pass). Summary for a transaction with no logs: `total_entries=0`, `action_breakdown={}`, `first_entry=null`, `last_entry=null`, `unique_actors=0`.

**Unit-testable logic**: Summary aggregation (counts per action, first and last entry from newest-first ordering, unique actor count) with synthetic logs; `create_audit_log` builds an entry and swallows errors (cannot be reached from endpoints); delete role gate.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-EXP-15-U01 | Summary aggregation for logs [create, update, update] by two actors | `total_entries=3`, `action_breakdown={"create":1,"update":2}`, `unique_actors=2`, `first_entry` = oldest, `last_entry` = newest | passing |
| TC-EXP-15-U02 | Summary with no logs | Zeros and nulls as documented | passing |
| TC-EXP-15-U03 | `create_audit_log` with a failing flush | Logs a warning and returns the unsaved object without raising | passing |
| TC-EXP-15-U04 | `delete_audit_log` as role "Admin", "super_admin", "tenant_admin" | 403, allowed, allowed | passing |
| TC-EXP-15-A01 | After creating a category, a type and a transaction, `GET /expense/audit/logs` | `[]` (writes are disabled) | passing |
| TC-EXP-15-A02 | `GET /expense/audit/logs?action=create&limit=500` and `limit=501` | 200 empty; 422 | passing |
| TC-EXP-15-A03 | `GET /expense/audit/logs/{random uuid}` | 404 "Audit log not found" | passing |
| TC-EXP-15-A04 | `GET /expense/audit/transactions/{id}/logs` for an existing and a nonexistent transaction | `[]` for both (no existence check) | passing |
| TC-EXP-15-A05 | `GET /expense/audit/transactions/{id}/summary` | `{transaction_id, total_entries: 0, action_breakdown: {}, first_entry: null, last_entry: null, unique_actors: 0}` | passing |
| TC-EXP-15-A06 | `DELETE /expense/audit/logs/{random uuid}` as Admin | 403 "Only administrators can delete audit logs" | passing |
| TC-EXP-15-A07 | Insert an audit row directly, then `GET /logs` and `GET /logs/{id}` | Row returned with all schema fields (verifies the read path for when writes are enabled) | skipped: needs a direct database insert of an audit row; |
| TC-EXP-15-A08 | Role matrix on all read endpoints | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-EXP-15-A09 | Tenant isolation | An audit row of tenant A is invisible to tenant B | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-EXP-15-E01 | P1 | Web | Admin | Seeded pending transaction "Chart paper and markers for classrooms" (850.00, cash, vendor Balaji Book Depot, type Stationery, no approval needed) | 1. Open Expense > Expense Audit.<br>2. Click the "Transaction Audit" tab.<br>3. Click "View Audit" on "Chart paper and markers for classrooms".<br>4. Read the counters under the table on the "Transaction Audit" tab (they are not on the "Audit Logs" tab). | Counters "Total Logs", "Creation", "Updates", "Approvals" (under the table on the Transaction Audit tab) show 0 and "No audit logs found for this transaction" (audit writes are disabled, Known gaps 11). | known defect: UI-EXP-01: the audit summary counters (Total Logs, Creation, Updates, Approvals) render blank instead of 0 bec... |
| TC-EXP-15-E02 | P3 | Web | Admin | qa_manual with only the seeded expense data (5 categories, 11 types, 5 departments, 12 transactions) | 1. Open Expense > Expense Audit > "Transaction Audit".<br>2. Type "Diesel" in "Search transactions...".<br>3. Clear it and choose "Transport" in "All Departments". | Step 2 leaves the two diesel rows; step 3 leaves the rows of department Transport (the two diesel rows and Brake pad replacement for School Bus 1). | planned |
| TC-EXP-15-E03 | P2 | Web | Staff | Seeded tenant qa_manual (year 2026-2027) | 1. Sign in as Staff.<br>2. Open Expense > Expense Audit. | "Access Denied" with "You don't have permission to view expense audit logs." | planned |
| TC-EXP-15-E04 | P2 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open the drawer and choose Expense > Expense Audit. | Screen "Expense Audit Trail" with chips All, Transaction, Attachment, Category, Type and "No audit logs found". | planned |
| TC-EXP-15-E05 | P3 | Mobile | Admin | Seeded tenant qa_manual (year 2026-2027) | 1. Open Expense Audit Trail on mobile.<br>2. Type "create" in "Search by action, user or notes".<br>3. Tap the calendar button ("Select date") and enter From "2026-10-01". | The empty state remains; no error; "Clear" appears next to the dates. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/expense/test_phase1_expense_reporting.py.

---

## Known gaps

Differences between `docs/modules/expense.md` (or the UI) and the code, and defects found while reading it. Add test results against these in the Status column of the cases above.

1. Category uniqueness is enforced only among active categories (soft-deleted names can be reused) and type names inside a category including inactive types, which blocks reusing the name of a deleted type; the module doc now says so. Renaming-by-moving a type to another category now re-runs the name check (fixed 2026-10-02).
2. The web Categories and Types forms allow descriptions up to 500 characters; the backend allows 300 and returns 422 for 301 to 500 (departments are consistent at 300). Web requires names of at least 2 characters; the backend accepts 1.
3. Web attachments in the create or edit dialog are never uploaded; `useUploadExpenseAttachment` is imported but not called. The web page also has no list, download or delete control for attachments. Mobile uploads after create and can add and download later.
4. Web "Approve or reject" is shown for every pending row, and the web and mobile Edit actions are shown for approved transactions; the API rejects both (`TRANSACTION_NO_APPROVAL_REQUIRED`, `TRANSACTION_ALREADY_APPROVED`).
5. Approval comment: the clients do not limit it to 500 characters (API returns 422).
6. `GET /expense/transactions/` accepts `department_id` and ignores it; `/pending/approval` accepts `skip` and `limit` and ignores them; the web date and vendor filters run in the browser on the returned page only.
7. Fixed (2026-10-02): `requires_approval_override=false` now exempts a transaction and `requires_approval` is recalculated on edit of a pending transaction. Settings are still never consulted (see F11, F08).
8. Reports: web page guard is `expense_reports:list` but all report endpoints check `read`; no default status exclusion (rejected and pending are counted) while the summary excludes only cancelled; `categories_count` and `departments_count` are always 0; export and export status are mocks (`status="pending"` on request, `"completed"` always on status check) and the mobile export path `/expense/reports` does not exist.
9. Report department scoping uses `current_user.get("department_id")`, but tenant tokens carry no such claim, so any non-Admin role with report access would see only transactions without a department.
10. Settings: `POST .../reset` is a stub; `GET .../ui/common` returns the database dialect name in `retrieved_at`; mobile cannot create or delete settings; the web delete action uses a gear icon and has no label.
11. Audit: every write path is disabled ("temporarily disabled" comments in the category, type, transaction and attachment services) so the trail is empty; delete is a hard delete gated by role names no tenant role has (Admin gets 403 though the catalog grants `expense_audit_logs:delete`); `/transactions/{id}/summary` is defined twice.
12. Mobile hub stat cards read `.total` from list endpoints that return plain arrays, so they show 0. The mobile hub also has no tile for Approvals, Reports, Audit or Settings.
13. `payment_method` is not validated (free text, column length 20). `amount` of 0 is accepted by the API but rejected by both clients.
14. Attachments are metadata only: `file_path="/temp/path"`, fixed MIME type and hash, mock download body, delete only archives, no status guard on upload.
15. The module doc states the mobile clients call without trailing slashes and that the export call differs; this was not re-verified beyond the export path.
16. No delete endpoint for transactions (F09); `paid`, `cancelled` and `deleted` statuses are unreachable, so the Paid and Cancelled tabs are always empty. `rejected` has no tab or filter option.
17. Web transaction form has no department field and no discount field; mobile has both.
18. Expense menu labels differ between the legacy test-tenant seed and the demo catalog (which the QA tenants use). The Teacher role is given the Expense menu although it has no expense grants, so every page it opens shows Access Denied.
19. Mobile Expense Summary does not use `GET /expense/summary/`: it lists all categories including inactive (deleted) ones and sums the report endpoints, which count every status and filter the year by date range, so its totals differ from web (seen 2026-10-07: a deleted category was listed).
20. Web cosmetic defects seen 2026-10-07: the department Deactivate button reads "Deactivateing..." while pending; a duplicate category name shows the same error toast twice.
21. UI-EXP-01: the Transaction Audit summary counters are blank because the web reads `total_logs`, `creation_logs`, `update_logs` and `approval_logs` while the live endpoint returns `total_entries` and `action_breakdown`.
22. Mobile attachment upload (TC-EXP-10-E03): on Expo web the picked file is appended to FormData as a plain object and the API returns 422; it works only on native, so it needs a device check (same family as UI-CER-01).
