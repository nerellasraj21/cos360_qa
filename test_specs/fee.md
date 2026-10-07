# Fee: feature documentation and test specification

Module code: `FEE`. Conventions and test ID scheme: `docs/testing/strategy.md`. Section layout: `docs/features/README.md`. Module rules and gotchas: `docs/modules/fee.md`. Flows and decisions: `docs/graph/views/fee.md`.

_Last verified against code: 2026-10-07_ (backend `backend/app/api/v1/fee`, `backend/app/service/fee`, `backend/app/service/reports/fee_report_service.py`, web `web/src/pages/fee` and `web/src/components/fee`, mobile `mobile/app/fees`). Where `docs/modules/fee.md` and the code disagree, this page documents the code and lists the difference under "Known gaps" at the end.

## Module overview

The Fee module lets a school define what it charges and collect it. Per academic year an administrator creates fee categories, fee types (each tied to one fee term, a schedule of due dates), terms and installment dates, class fee mappings (the fee for a class, optionally mandatory) and student fee mappings (what a student actually owes, split equally across the term dates). Staff then search a student, read the fee summary, record a payment (cash, UPI, bank transfer, cheque, DD or card) with an optional parent SMS, and the system issues a numbered receipt with an integrity hash and an on-demand PDF. Concessions reduce what a student owes for one fee type, old fees carry dues from earlier years, refunds go through request, approve or reject, then process, and reports cover collection, pending fees and fee structure. Students and parents get read-only self-service views of fees, receipts and transactions. All amounts are `Numeric(10,2)` and travel as JSON strings.

## Roles

Grants below are the default seed in `backend/app/service/tenant/permission_catalog.py`. The QA tenant (`qa_school`) copies grants from the test tenant, so phase 2 and 3 tests must read the seeded grants first (`docs/testing/test-environment.md`) and treat a mismatch as a precondition failure, not a product defect. The plan layer is not enforced at runtime (`docs/permissions.md`).

| Role | Default fee grants | UI notes |
|---|---|---|
| Admin | All fee resources: `fee_categories`, `fee_types`, `fee_terms`, `fee_class_mappings`, `fee_class_mapping_term_amounts`, `fee_student_mappings` (create, read, update, delete, list); `fee_transactions` (create, read, update, list); `fee_receipts` (create, read, update, list); `fee_refunds` (create, read, list, approve, process); `fee_collection` (create, read, list); `fee_concessions` and `fee_old` (create, read, update, delete, list); `fee_reports` (read, export). No `fee_collection:send_sms` in the default seed | Sees the Fee dashboard and every submenu |
| Staff | Read and list on categories, types, terms, class mappings and class term amounts; create, read, update, list on student mappings and transactions; create, read, list on receipts and refunds; `fee_reports` read and export. No `fee_collection`, `fee_concessions`, `fee_old`, delete, approve or process | Web and mobile role matrices (`staffPermissionMatrix.ts`) cap the same set for the listed resources; unlisted resources fall through to the backend grant |
| Teacher | None | Web `routes/_app/fee.tsx` and mobile Fee hub redirect the role away from every fee page |
| Student | `fee_receipts` read_own, list_own; `fee_transactions` read_own, list_own. No `fee_collection` grant | Menu: Fee > My Receipts, My Transactions (injected by `menuUtils.ts`) |
| Parent | `fee_transactions` read_related; `fee_receipts` read_related; `fee_collection` read_related | Same two menu entries; child switcher in the header |

Scope rules for self-service endpoints (`check_user_resource_access`): the first match of `<action>_own`, `<action>_related`, `<action>` decides the scope; a targeted id outside the scope returns 404, a denied scope returns 403 with `detail.error = "permission_denied"`.

## Feature index

| ID | Title |
|---|---|
| F01 | Fee categories |
| F02 | Fee types |
| F03 | Fee terms and installment dates |
| F04 | Class fee mappings (including mandatory fees) |
| F05 | Class mapping term amounts |
| F06 | Student fee mappings |
| F07 | Concessions |
| F08 | Old fees |
| F09 | Student search, fee summary, terms due and fee history |
| F10 | Fee payment (collection) |
| F11 | Receipts |
| F12 | Transactions |
| F13 | Refunds |
| F14 | Fee SMS (due reminder and receipt resend) |
| F15 | Fee reports |
| F16 | Student and parent self-service |
| F17 | Fee hub, navigation and route guards |

## Common conventions

- Base path `/api/v1`; every path below is relative to it. All endpoints except the health checks need a bearer token. The tenant comes from the token `tenant_id` claim; a `cschema` header that names another tenant gets 403. Without a token the response is 401.
- Missing permission: 403 `Permission not found in database: ...` from `check_role_plan_permission_with_error`, or 403 `permission_denied` from `check_user_resource_access`.
- Money: Decimal fields serialise as strings (`"2000.00"`). Tests must compare as Decimal, never as float.
- Rate limits: category and type create 30 per minute; transaction create 20 per minute; concession, old fee, collection endpoints and most reads 200 per minute (`rate_limit_api`); reports and refunds have none. A rate-limit test is out of scope for the functional suite.
- Academic year: web and mobile fill `academic_year_id` from the header academic year selector. Creates throw "Academic year is required" on web when none is selected.
- UI test cases (IDs ending `-E<NN>`) run in the seeded manual-test tenant `qa_manual` (`docs/testing/test-environment.md`). Its fee data: categories "Academic Fees" and "Facility Fees"; terms "Three Terms" (15 Jun 2026, 15 Oct 2026, 15 Jan 2027), "Annual" (30 Jun 2026) and "Half Yearly" (15 Jun 2026, 1 Dec 2026); types Tuition Fee, Admission Fee and Books and Stationery (Academic Fees) and Activity Fee (Facility Fees); class mappings for every class and type with term amounts (Tuition Fee and Admission Fee mandatory); student mappings, 24 completed payments (cash, UPI, bank transfer), one Tuition Fee concession of 2,000.00 on Ananya Reddy (20260002, NUR-A), a pending 1,000.00 refund for Aarav Gupta (20260001, NUR-B) and a processed 500.00 refund for Ananya Reddy. Students used below: Karthik Reddy (001, Class 3 / 3-B), Advik Mehta (002, 1-B), Saanvi Iyer (003, 1-A), Harsha Raju (004, 1-B), Tanvi Raju (005, 4-B), Kavya Verma (006, 1-A, nothing paid). Admin, Staff and Teacher cases use the QA logins; the QA Student and Parent logins are not linked to a student, so Student and Parent cases use a seeded student login (the admission number) or a seeded parent login. Data created by a case is named "QA ..." and is deleted afterwards where the app allows it (payments cannot be deleted). Figures quoted from the seed hold until a case changes them.
- Identifiers used in test data below: "year Y1" is the QA academic year, "term Q4" a fee term with 4 dates 2026-06-10, 2026-09-10, 2026-12-10, 2027-03-10, "term T3" a fee term with 3 dates 2026-06-10, 2026-09-10, 2026-12-10, "Tuition" a fee type on Q4, "Lab" a fee type on T3.

## Calculation reference (single source for the unit tests)

All calculations are in `fee_collection_service.py`, `fee_student_mapping_service.py`, `fee_concession_service.py`, `fee_old_service.py`, `fee_transaction_service.py`, `fee_refund_service.py`, `fee_receipt_service.py` and `fee_report_service.py`.

| Name | Exact rule in code |
|---|---|
| Assigned fee | `fee_student_mappings.total_fee` for (student, fee type, year) |
| Concession amount | Sum of `fee_concessions.concession_amount` where `is_active` is true for (student, fee type, year). Revoked rows are ignored |
| Payable (fee_after_concession) | `max(assigned - concession, 0)` |
| Paid | Sum of `fee_transaction_items.amount_paid` over transactions with `status = completed`, same student, year and fee type. Pending, cancelled and bounced transactions never count. Refunds are never subtracted |
| Paid in the summary with an as-of date | Same, additionally `transaction_date <= as_of_date 23:59:59.999999`. Assigned and concession amounts are never date-filtered |
| Due | `max(payable - paid, 0)`. An overpayment is silently clamped to 0 |
| Grand totals | Sums of the per-fee-type values. In the concession summary `grand_total_fee_after_concession = grand_assigned - grand_concession` (no per-row clamp) |
| Old fee pending | `sum(original_amount - paid_amount)` over `fee_old` rows with `is_settled = false`, all years |
| Total due used by payment | `sum over fee types of max(payable - paid, 0)` plus old fee pending. A payment above it is rejected |
| Student term amount | `total_fee / number_of_term_dates` as a Python Decimal, stored into `Numeric(10,2)`; PostgreSQL rounds a tie away from zero. The shares can sum to more or less than `total_fee` (1000 over 3 gives 333.33 x 3 = 999.99; 1000.01 over 2 gives 500.01 x 2 = 1000.02) |
| Term outstanding (payment, outstanding-fees) | `term_amount - sum(amount_paid of completed items for that term_date_id)`. Concessions are not applied to term amounts |
| Payment allocation (explicit `fee_items`) | Each requested fee type is checked against its own outstanding (`payable - paid`), then its amount is spread over the mapping's term amounts in the relationship order, each term capped at its own outstanding. A positive remainder after the last term fails with 400 |
| Payment allocation (no `fee_items`) | Fee types ordered by `fee_type_id`; each takes `min(remaining, outstanding)`; terms filled as above; a remainder goes to unsettled old fees ordered by `academic_year_label` then `fee_type_name` |
| Terms due | For each student term amount with due date `<= as_of_date`: `pending = max(term_amount - paid_for_that_term_date, 0)`, pending 0 rows are omitted. `current_month_terms` have due date `>=` first day of the as-of month, the rest are `overdue_terms`. Concessions are ignored |
| Outstanding items (transactions endpoints) | Per term amount: `term_amount - paid`, shown when `> 0`. No concession, no old fees |
| Refund available | `transaction.total_amount - sum(refund_amount of refunds with status approved or processed)`. Pending refunds do not count |
| Old fee outstanding | `max(original_amount - paid_amount, 0)`; `is_settled` is a separate flag that does not change `paid_amount` |
| Receipt number | `REC-YYMM-` plus four digits; highest existing number for the current month plus 1; sequence restarts each month |
| Transaction number | `TXN` + `YYYYMMDD` + 8 uppercase hex characters |
| Refund number | `RFD` + `YYYYMMDD` + 6 uppercase hex characters |
| Collection percentage (report) | `round(total_collected / total_due * 100, 2)`, 0.0 when `total_due` is 0 |
| Days overdue (pending report) | `(today - due_date).days` when `due_date < today`, else null |

Worked examples used by the test cases:

| Case | Inputs | Result |
|---|---|---|
| W1 plain | Tuition assigned 12000, no concession, paid 0 | payable 12000, due 12000 |
| W2 concession and payment | Tuition assigned 12000, concession 2000, completed payment 4000 | payable 10000, paid 4000, due 6000 |
| W3 overpayment clamp | Lab assigned 3000, concession 1000, completed payments 2500 | payable 2000, paid 2500, due 0 |
| W4 uneven split | Lab 1000 over T3 | term amounts 333.33, 333.33, 333.33 (sum 999.99), due 1000 |
| W5 uneven split pay full explicit | W4 student, `fee_items` Lab 1000 | 400 `Amount for 'Lab' exceeds the scheduled term amounts by 0.01; check the term-wise fee setup` |
| W6 uneven split pay full auto | W4 student, `amount_to_pay` 1000, no `fee_items` | 200, transaction total 999.99, summary due 0.01 afterwards |
| W7 leftover 0.01 | After W6, `amount_to_pay` 0.01 | 400 `No outstanding fees to pay` |
| W8 terms due | Tuition 3000 per term, term 1 paid 3000, as_of 2026-09-15 | term 06-10 omitted (pending 0), term 09-10 in `current_month_terms` pending 3000, term 12-10 not listed. Concession ignored |
| W9 cumulative concession | Assigned 3000; concession +1000, +1500, then +600 | totals 1000, 2500, then 400 (`3100.00` exceeds `3000.00`) |
| W10 refund limit | Transaction 5000, approved or processed refunds 3000, request 2500 | 400 `Refund amount 2500 exceeds available amount 2000.00`; request 2000 accepted |
| W11 old fee | Original 1500, paid 600 | outstanding 900, not settled; paid 1500 gives outstanding 0 and settled |
| W12 collection percentage | Collected 7500, due 10000 | 75.0 |

---

## F01 Fee categories

**Purpose.** Group fee types (for example Tuition, Transport) per academic year so the school can organise and report on them.

**Roles and permissions.** `fee_categories:create`, `read`, `update`, `delete`, `list`. Default seed: Admin all five; Staff read and list. Web menu: Fee > Fee Categories (injected for admin-type roles); mobile: Fee hub tile "Fee Categories". Expanding a category to see its types also needs `fee_types:list`; the "+" Manage Fee Types button needs `fee_types` create, update or delete.

**Preconditions.** An academic year exists (Masters module) and is selected in the header selector.

**Steps, web.**
1. Open Fee > Fee Categories (`/fee/categories`, page title "Fee Categories Management").
2. Click "Add Category" (or "Create First Category" on an empty list). The "Create Fee Category" dialog opens.
3. Enter "Category Name *" (placeholder "Enter category name"), tick or untick "Active", click "Save" (toast "Fee category created successfully").
4. To edit, click the pencil "Edit Category", change the fields in "Edit Fee Category", click "Save".
5. To delete, click the trash "Delete Category", confirm "Delete" in "Delete Fee Category".
6. The "Fee Types" column shows "N fee type(s)"; the row chevron expands the types. Click "+" ("Manage Fee Types") to open "Manage Fee Types - <category>" ("Add Fee Type", empty text "No fee types found for this category.") and add, edit or delete types for that category (see F02).
7. Narrow the list with "Search categories..." and the status select (All Status, Active, Inactive). The list header reads "Showing X-Y of N categories".

**Steps, mobile.**
1. Open the Home "Fee Management" card > "Fee Categories" (`/fees/categories`).
2. Use "Search categories..." and the "All Status" filter. Tap "Add Category" (form "Add Fee Category": "Category Name *", "Active", "Cancel", "Save"), enter "Enter category name", save. Success toast "Created" / "Fee category created successfully" (mobile toasts have a title and a message).
3. Edit or delete from the row. Delete failure shows "Delete Failed" with the server message (for example when fee types exist).
4. Within a category, add a fee type (fields "Enter fee type name", "Select fee term", "Select status"); required-field toasts are "Category name is required", "Fee type name is required", "Please select a fee term".

**Expected results.** A row is stored in `fee_categories` with `academic_year_id`; the list shows it with the academic year title. Deleting a category with no types removes the row. The category and type dropdown caches are invalidated on create, update and delete.

**API endpoints.**
- `GET /fee/categories/health`: `{status, module: "fee_categories", timestamp}`.
- `POST /fee/categories/`: body `category_name`, `category_status` (default `active`), `academic_year_id`. 201 with `FeeCategoryRead` (`id`, `category_name`, `category_status`, `academic_year_id`, `academic_year_title`).
- `GET /fee/categories/`: query `limit` (1-500, default 50), `offset`. Returns a plain array. No academic year or status filter.
- `GET /fee/categories/dropdown`: query `academic_year_id` optional. `[{id, category_name}]` ordered by name, cached 300 s.
- `GET /fee/categories/{fee_category_id}`, `PUT /fee/categories/{fee_category_id}` (all fields optional), `DELETE /fee/categories/{fee_category_id}` (200 with the deleted category).

**Rules and validations.**
- Name unique per academic year (exact match, case sensitive): 400 `Category name '<name>' already exists for this academic year`. On update the check runs when name or year is sent.
- The academic year must exist: 404 `Academic year with id <id> not found`.
- `category_status` has no validator in the backend (any string up to 20 characters); web sends `active` or `inactive`.
- Delete is blocked while fee types reference the category: 400 `Cannot delete fee category '<name>' because it is being used by N fee type(s). Please reassign or delete the fee types first.`
- Name column length 100.

**Error and edge cases.** Duplicate name in another year is allowed. Unknown id: 404 `Fee category with id <id> not found`. A malformed UUID path: 422. `limit` 0 or 501: 422. Creating from web without a selected year: the page throws "Academic year is required". Query params `skip` and `academic_year_id` sent by web are ignored by the list endpoint (see Known gaps K01).

**Unit-testable logic.** `check_category_name_unique` (exclude-self on update, year scoping); `FeeCategoryCreate` defaults; delete dependency check.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-01-U01 | `FeeCategoryCreate` with only `category_name` and `academic_year_id` | `category_status` defaults to `active` | passing |
| TC-FEE-01-U02 | `check_category_name_unique` with an existing row of the same name and year | Raises 400 with the "already exists for this academic year" message | passing |
| TC-FEE-01-U03 | `check_category_name_unique` with `exclude_id` equal to the existing row | No error (update keeps its own name) | passing |
| TC-FEE-01-U04 | `check_category_name_unique` same name, different year | No error | passing |
| TC-FEE-01-U05 | `FeeCategoryUpdate` with every field null | Valid; service changes nothing | passing |
| TC-FEE-01-A01 | Admin `POST /fee/categories/` name "QA Tuition" year Y1 | 201; `category_status` active; `academic_year_title` equals the year title | passing |
| TC-FEE-01-A02 | Admin POST the same name and year twice | Second call 400 `Category name 'QA Tuition' already exists for this academic year` | passing |
| TC-FEE-01-A03 | Admin POST the same name in a second academic year | 201 | passing |
| TC-FEE-01-A04 | POST with a random UUID as `academic_year_id` | 404 `Academic year with id ... not found` | passing |
| TC-FEE-01-A05 | POST with missing `category_name`; POST with `academic_year_id` not a UUID | 422 both | passing |
| TC-FEE-01-A06 | `GET /fee/categories/?limit=2&offset=0` then `offset=2` | Arrays of at most 2; second page holds different rows | passing |
| TC-FEE-01-A07 | `GET /fee/categories/?limit=0` and `limit=501` | 422 | passing |
| TC-FEE-01-A08 | `GET /fee/categories/dropdown?academic_year_id=Y1` | Only Y1 categories, ordered by `category_name`, fields `id` and `category_name` only | passing |
| TC-FEE-01-A09 | Create a category, call dropdown, create another, call dropdown again | The new category appears immediately (cache invalidated) | passing |
| TC-FEE-01-A10 | `GET /fee/categories/{id}` existing and unknown id | 200 with `academic_year_title`; unknown 404 `Fee category with id ... not found` | known defect: FEE-B01: GET /fee/categories/{unknown id} returns 500 because get_fee_category_by_id swallows its own 404 |
| TC-FEE-01-A11 | `PUT` rename to a name used by another category of the same year | 400 `Category name already exists for this academic year` | passing |
| TC-FEE-01-A12 | `PUT` rename to its own current name; `PUT` status `inactive` | 200 both; status persisted | passing |
| TC-FEE-01-A13 | `PUT` moves the category to a second year where the same name exists | 400 duplicate | passing |
| TC-FEE-01-A14 | `DELETE` a category with no types | 200 returns the deleted category; follow-up GET is 404 | known defect: FEE-B01: GET /fee/categories/{deleted id} returns 500 instead of 404 |
| TC-FEE-01-A15 | `DELETE` a category that has one fee type | 400 `Cannot delete fee category '<name>' because it is being used by 1 fee type(s)...` and the row remains | passing |
| TC-FEE-01-A16 | `GET /fee/categories/health` | 200 `{status: "healthy", module: "fee_categories"}` | passing |
| TC-FEE-01-A17 | Role matrix: create, update, delete as Admin, Staff, Teacher, Student, Parent | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-01-A18 | Role matrix: list, read, dropdown | Admin and Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-01-A19 | Any endpoint without a token | 401 | passing |
| TC-FEE-01-A20 | Tenant isolation: category created in the QA tenant read by a token of another tenant; QA token with `cschema` of another tenant | Not visible (404 or empty list); header mismatch 403 | known defect: FEE-B01: cross-tenant GET /fee/categories/{id} returns 500 instead of 404 |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-01-E01 | P1 | Web | Admin | Academic year 2026-2027 selected in the header. No category named "QA Sports" exists | 1. Sign in as Admin.<br>2. Open Fee > Fee Categories.<br>3. Click "Add Category".<br>4. Enter Category Name "QA Sports" and leave "Active" ticked.<br>5. Click "Save". | Toast "Fee category created successfully"; row "QA Sports" with an Active badge and "0 fee types"; stored with academic year 2026-2027 | passing |
| TC-FEE-01-E02 | P3 | Web | Admin | TC-FEE-01-E01 done | 1. Open Fee > Fee Categories.<br>2. Click "Add Category".<br>3. Enter Category Name "QA Sports".<br>4. Click "Save". | Error toast `Category name 'QA Sports' already exists for this academic year`; no second row | planned |
| TC-FEE-01-E03 | P2 | Web | Admin | TC-FEE-01-E01 done | 1. Open Fee > Fee Categories.<br>2. Click "Edit Category" on "QA Sports".<br>3. Untick "Active".<br>4. Click "Save".<br>5. Choose "Inactive" in the status filter. | Toast "Fee category updated successfully"; badge Inactive; the Inactive filter lists "QA Sports"; reset to Active afterwards | planned |
| TC-FEE-01-E04 | P2 | Web | Admin | A category "QA Temp" created through "Add Category" with no fee types | 1. Open Fee > Fee Categories.<br>2. Click "Delete Category" on "QA Temp".<br>3. Click "Delete" in "Delete Fee Category". | Toast "Fee category deleted successfully"; row removed | planned |
| TC-FEE-01-E05 | P2 | Web | Admin | TC-FEE-02-E01 done ("QA Lab" belongs to "QA Sports") | 1. Open Fee > Fee Categories.<br>2. Click "Delete Category" on "QA Sports".<br>3. Click "Delete". | Error toast `Cannot delete fee category 'QA Sports' because it is being used by 1 fee type(s)...`; row stays | planned |
| TC-FEE-01-E06 | P3 | Web | Admin | Seeded categories "Academic Fees" and "Facility Fees" exist | 1. Open Fee > Fee Categories.<br>2. Type "Acad" in "Search categories...".<br>3. Clear the search. | Only "Academic Fees" is listed while filtered; the full list returns after clearing | planned |
| TC-FEE-01-E07 | P2 | Web | Staff | Seeded categories exist | 1. Sign in as Staff.<br>2. Open Fee > Fee Categories. | List and filters visible; no "Add Category", "Edit Category", "Delete Category" or "Manage Fee Types" buttons | planned |
| TC-FEE-01-E08 | P2 | Mobile | Admin | Signed in to organisation qa_manual | 1. Open the Fee Management card, then "Fee Categories".<br>2. Tap "Add Category".<br>3. Enter "QA Mobile Cat" in "Enter category name".<br>4. Tap "Save".<br>5. Delete "QA Mobile Cat" from its row and confirm. | Toasts "Fee category created successfully" then "Fee category deleted successfully"; the row appears then disappears | planned |
| TC-FEE-01-E09 | P3 | Mobile | Admin | TC-FEE-02-E01 done | 1. Open Fee Categories.<br>2. Delete "QA Sports" and confirm. | Toast "Delete Failed" with the server "being used by 1 fee type(s)" message; row stays | planned |

API tests implemented in: backend/tests/api/fee/test_fee_categories_types.py

Implemented in: backend/tests/unit/fee/test_fee_category_type_rules.py (phase 1 unit cases).

---

## F02 Fee types

**Purpose.** Define each chargeable item (Tuition, Lab, Transport) inside a category and bind it to the fee term that holds its due dates.

**Roles and permissions.** `fee_types:create`, `read`, `update`, `delete`, `list`; the form also lists `fee_categories` and `fee_terms`. Default seed: Admin all; Staff read and list. Menu: Fee > Fee Types (web `/fee/types`), mobile tile "Fee Types" (`/fees/types`).

**Preconditions.** A fee category (F01) and a fee term with dates (F03) exist for the year.

**Steps, web.**
1. Open Fee > Fee Types (title "Fee Types Management").
2. Click "Add New Type" (or "Create First Type"). Dialog "Create New Fee Type".
3. Fill "Type Name" (placeholder "e.g., Tuition Fee, Transport Fee"), "Fee Category" ("Select fee category"), "Fee Term" ("Select fee term"; options read like "Quarterly (4 installments)"), and the "Active" switch. Click "Create Type" ("Update Type" when editing).
4. Edit with the pencil "Edit Fee Type" (dialog "Edit Fee Type"); delete with the trash "Delete Fee Type" and confirm "Delete".
5. Search "Search by name, category or term...", sort by Type Name, Category, Term or Status, change "Rows per page".

**Steps, mobile.** Fee hub > "Fee Types" (`/fees/types`): "Search by name, category or term...", add or edit form with "e.g., Tuition Fee, Transport Fee", "Select fee category", "Select fee term"; required toasts "Type name is required", "Fee category is required", "Fee term is required". Types can also be added from the category screen (F01).

**Expected results.** `fee_types` row with category, term and year; the list shows category name, term name (and its dates through the read model).

**API endpoints.**
- `GET /fee/types/health`.
- `POST /fee/types/`: `type_name`, `fee_category_id`, `fee_term_id`, `academic_year_id`, `fee_status` (`active` or `inactive`, default `active`). 201 `FeeTypeRead` (adds `fee_category_name`, `fee_term_name`, `academic_year_name`, `fee_term_dates`).
- `GET /fee/types/`: `limit` (1-500), `offset`; array, no filters.
- `GET /fee/types/dropdown`: query `fee_category_id` optional; `[{id, type_name}]`, cached 300 s.
- `GET /fee/types/{id}`, `PUT /fee/types/{id}`, `DELETE /fee/types/{id}`.

**Rules and validations.**
- `fee_status` must be `active` or `inactive`: 422 otherwise.
- Name unique per category (not per year): 400 `Fee type name '<name>' already exists for this fee category`.
- Category, term and academic year must exist: 404 `Fee category with id ... not found`, `Fee term with id ... not found`, `Academic year with id ... not found`.
- The type's academic year is not cross-checked against the category's or the term's year.
- Delete is blocked while class mappings or student mappings reference the type: 400 `Cannot delete fee type '<name>' because it is being used by N record(s): X fee class mapping(s), Y fee student mapping(s). Please reassign or delete the dependent records first.`
- Changing a type's `fee_term_id` does not rebuild existing student term amounts.

**Error and edge cases.** Same name in two categories is allowed. Type name longer than 100 characters fails at the database (500). `GET /fee/types/dropdown?fee_category_id=<uuid>` filters by category (K02 fixed).

**Unit-testable logic.** `FeeTypeBase.validate_fee_status`; `check_type_name_unique` (category scoping, exclude-self); delete dependency counting and message format.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-02-U01 | `FeeTypeCreate` with `fee_status="archived"` | ValidationError `fee_status must be either "active" or "inactive"` | passing |
| TC-FEE-02-U02 | `FeeTypeUpdate` with `fee_status=None` | Valid | passing |
| TC-FEE-02-U03 | `check_type_name_unique` same name, same category | Raises 400 | passing |
| TC-FEE-02-U04 | `check_type_name_unique` same name, other category | No error | passing |
| TC-FEE-02-U05 | Delete message builder with 2 class mappings and 3 student mappings | Message lists `2 fee class mapping(s), 3 fee student mapping(s)` and total 5 records | passing |
| TC-FEE-02-A01 | Admin `POST /fee/types/` Tuition in category C1 bound to term Q4 | 201; `fee_term_dates` has 4 dates; names resolved | passing |
| TC-FEE-02-A02 | POST the same name in the same category | 400 `Fee type name 'Tuition' already exists for this fee category` | passing |
| TC-FEE-02-A03 | POST the same name in another category | 201 | passing |
| TC-FEE-02-A04 | POST with unknown category, unknown term, unknown year (three calls) | 404 with the matching message each time | passing |
| TC-FEE-02-A05 | POST `fee_status="paused"` | 422 | passing |
| TC-FEE-02-A06 | POST missing `fee_term_id` | 422 | passing |
| TC-FEE-02-A07 | `GET /fee/types/` with `limit=2&offset=2` | Plain array of at most 2 with relationship names filled | passing |
| TC-FEE-02-A08 | `GET /fee/types/dropdown` (no filter) | Array of `{id, type_name}` | passing |
| TC-FEE-02-A09 | `GET /fee/types/dropdown?fee_category_id=C1` | 200 with only C1 types | passing |
| TC-FEE-02-A10 | `GET /fee/types/{id}` existing and unknown | 200 and 404 | known defect: FEE-B02: GET /fee/types/{unknown id} returns 500 because get_fee_type_by_id swallows its own 404 |
| TC-FEE-02-A11 | `PUT` change `fee_term_id` to T3 | 200; `fee_term_dates` now 3; existing student term amounts unchanged | known defect: FEE-B03: PUT /fee/types/{id} response carries the old term name and dates after fee_term_id changes (a followi... |
| TC-FEE-02-A12 | `PUT` rename to a sibling name in the same category | 400 duplicate | passing |
| TC-FEE-02-A13 | `DELETE` a type with no mappings | 200; GET afterwards 404 | known defect: FEE-B02: GET /fee/types/{deleted id} returns 500 instead of 404 |
| TC-FEE-02-A14 | `DELETE` a type used by one class mapping and one student mapping | 400 with the dependency message; row remains | passing |
| TC-FEE-02-A15 | `GET /fee/types/health` | 200 `module: "fee_types"` | passing |
| TC-FEE-02-A16 | Role matrix create, update, delete | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-02-A17 | Role matrix list, read, dropdown | Admin, Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-02-A18 | No token; token of tenant A with `cschema` of tenant B | 401; 403 | passing |
| TC-FEE-02-A19 | Type created in tenant A is absent from tenant B list and `GET /{id}` returns 404 in tenant B | Isolation holds | known defect: FEE-B02: cross-tenant GET /fee/types/{id} returns 500 instead of 404 |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-02-E01 | P1 | Web | Admin | TC-FEE-01-E01 and TC-FEE-03-E01 done | 1. Open Fee > Fee Types.<br>2. Click "Add New Type".<br>3. Enter Type Name "QA Lab".<br>4. Choose Fee Category "QA Sports" and Fee Term "QA Quarterly".<br>5. Click "Create Type". | Toast "Fee type created successfully"; row "QA Lab" shows "QA Sports", "QA Quarterly" and Active | passing |
| TC-FEE-02-E02 | P3 | Web | Admin | TC-FEE-02-E01 done | 1. Click "Add New Type".<br>2. Enter "QA Lab", category "QA Sports", term "QA Quarterly".<br>3. Click "Create Type". | Error toast `Fee type name 'QA Lab' already exists for this fee category`; no new row | planned |
| TC-FEE-02-E03 | P2 | Web | Admin | TC-FEE-02-E01 done | 1. Click "Edit Fee Type" on "QA Lab".<br>2. Turn the "Active" switch off.<br>3. Click "Update Type". | Toast "Fee type updated successfully"; status Inactive; switch back on afterwards | planned |
| TC-FEE-02-E04 | P2 | Web | Admin | TC-FEE-06-E01 done ("QA Lab" mapped to Kavya Verma) | 1. Click "Delete Fee Type" on "QA Lab".<br>2. Click "Delete". | Error toast `Cannot delete fee type 'QA Lab' because it is being used by ... record(s)...`; row stays | planned |
| TC-FEE-02-E05 | P2 | Web | Admin | TC-FEE-01-E01 done; seeded term "Annual" | 1. Open Fee > Fee Categories.<br>2. Click "Manage Fee Types" (+) on "QA Sports".<br>3. Click "Add Fee Type".<br>4. Enter "QA Kit", choose term "Annual", save.<br>5. Close the dialog. | "QA Kit" is listed in "Manage Fee Types - QA Sports"; the row shows "2 fee types" | planned |
| TC-FEE-02-E06 | P3 | Mobile | Admin | TC-FEE-01-E01 done | 1. Open Fee Types.<br>2. Tap "Add New Type".<br>3. Enter "QA Mobile Type", choose category "QA Sports", no term.<br>4. Tap save. | Toast "Fee term is required"; nothing created | planned |
| TC-FEE-02-E07 | P2 | Mobile | Admin | TC-FEE-01-E01 and TC-FEE-03-E01 done | 1. Open Fee Types.<br>2. Tap "Add New Type", enter "QA Mobile Type", category "QA Sports", term "QA Quarterly", save.<br>3. Delete "QA Mobile Type" and confirm. | Toasts "Fee type created successfully" then "Fee type deleted successfully" | planned |

API tests implemented in: backend/tests/api/fee/test_fee_categories_types.py

Implemented in: backend/tests/unit/fee/test_fee_category_type_rules.py (phase 1 unit cases).

---

## F03 Fee terms and installment dates

**Purpose.** A fee term is a payment schedule: a name, a number of installments and exactly that many due dates. Fee types point at a term, and every student's term amounts are created per date.

**Roles and permissions.** `fee_terms:create`, `read`, `update`, `delete`, `list`. Default seed: Admin all; Staff read and list. Menu: Fee > Fee Terms (web `/fee/terms`), mobile tile "Fee Terms" (`/fees/terms`).

**Preconditions.** An academic year exists and is selected.

**Steps, web.**
1. Open Fee > Fee Terms (title "Fee Terms Management", subtitle "Configure fee terms and payment schedules for different fee structures"; a card shows "Academic Year: <title>", the year's date range and an "Active Year" badge; the list card is "Fee Terms & Payment Schedules" with "Search by term name...").
2. Click "Add New Term" (or "Create First Term"). Dialog "Create New Fee Term".
3. Enter "Term Name" (placeholder "e.g., Quarterly, Monthly, Annual"), "Number of Terms" (1 to 12 in the form), the "Active" switch.
4. Under "Payment Dates" pick a date in the date input ("Select date") and click "Add Date" (empty text "No payment dates added yet. Add dates above."); the table lists "Installment" and "Due Date" rows with edit and delete buttons. The form refuses to submit unless exactly "Number of Terms" dates exist: `You must add exactly N payment date(s) (currently M added)`.
5. Click "Create Term" ("Update Term" when editing). Toast "Fee term created successfully". The list shows "Number of Terms" (for example "4 terms") and "Payment Schedule" (for example "Jun 10 - Mar 10 (4 dates)").
6. Edit through "Edit Fee Term" (dialog "Edit Fee Term"); delete through "Delete Fee Term". The "Payment Dates" button opens a read-only "Manage Payment Dates - <term>" view ("Payment Schedule Configuration", "N/N configured", rows "Installment 1..n", "Due Date", status Configured, a note to use "Edit"; "Close"); dates are changed through Edit.

**Steps, mobile.** Fee hub > "Fee Terms" (`/fees/terms`): the list shows each term with "Payment Dates", "Edit" and "Delete"; "Add Fee Term" opens the form "Add Fee Term" with "e.g., Quarterly, Monthly, Annual", "Enter number of terms", "Active", "Payment Dates" with a date picker and "Add Date", and "Create Term". Toasts (title / message): "Term Created" / "Fee term created successfully"; errors "Term name is required", "Academic year is required", "Number of terms must be at least 1", "Due date for Term N is required", "Number of term dates must equal number of terms". Delete failure toast "Delete Failed" with the server message (fallback "Cannot delete this term - it may be linked to active fee types").

**Expected results.** One `fee_terms` row and `number_of_terms` rows in `fee_term_dates`. Dates are returned in the term payload (`fee_term_dates`: `id`, `term_id`, `fee_term_date`).

**API endpoints.**
- `POST /fee/terms/`: `term_name` (max 50 in the database), `term_status` (default `active`), `number_of_terms`, `academic_year_id`, `fee_term_dates[{fee_term_date}]`. 201.
- `GET /fee/terms/`: `limit`, `offset`; array, no year filter, no ordering.
- `GET /fee/terms/dropdown`: active terms ordered by name, `[{id, term_name, number_of_terms}]`.
- `GET /fee/terms/{id}`; `GET /fee/terms/{id}/dates` returns `[{id, fee_term_date}]` ordered by date.
- `PUT /fee/terms/{id}`: any of `term_name`, `term_status`, `number_of_terms`, `academic_year_id`, `fee_term_dates`.
- `DELETE /fee/terms/{id}` (cascades its dates); `DELETE /fee/terms/dates/{fee_term_date_id}` deletes one date (200 `{message: "Fee term date deleted successfully"}`).
- `GET /fee/terms/health`.

**Rules and validations.**
- On create the date count must equal `number_of_terms` and dates must be unique. These are Pydantic validators, so a violation returns 422 (`Number of fee term dates (N) must match number_of_terms (M)` or `Duplicate fee term dates are not allowed`); the service-level 400 versions are not reachable on create.
- On update, when `fee_term_dates` is sent without `number_of_terms`, the count is compared with the stored `number_of_terms` in the service (400 with the same text). A new `number_of_terms` without dates only changes the number.
- Dates are updated in place: existing rows and the new dates are both sorted ascending and zipped, so the `term_date_id` values used by transaction items and term amounts stay valid. A smaller count deletes the extra rows (fails when referenced); a larger count adds rows. The update does not rebuild existing student term amounts.
- Academic year must exist (404). The dropdown shows only terms with `term_status = active`.
- Delete is blocked while fee types use the term: 400 `Cannot delete fee term '<name>' because it is being used by N fee type(s). Please reassign or delete the fee types first.`
- No name uniqueness check. `number_of_terms` has no backend range check (0 and 0 dates passes; web allows 1 to 12).

**Error and edge cases.** Deleting a date or a term whose dates are referenced by term amounts or transaction items fails at the database and returns 500. A term with 0 installments makes later student mapping creation fail (division by zero). A term name longer than 50 characters fails at the database.

**Unit-testable logic.** `FeeTermCreate` model validator (count) and field validator (duplicates); `update_fee_term_with_dates` sort-and-zip in-place update, extra-date deletion and addition; dropdown active filter.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-03-U01 | `FeeTermCreate` with `number_of_terms=4` and 3 dates | ValidationError `Number of fee term dates (3) must match number_of_terms (4)` | passing |
| TC-FEE-03-U02 | `FeeTermCreate` with 2 identical dates and `number_of_terms=2` | ValidationError `Duplicate fee term dates are not allowed` | passing |
| TC-FEE-03-U03 | `FeeTermUpdate` with dates but no `number_of_terms` | Model validator passes (service performs the check) | passing |
| TC-FEE-03-U04 | `FeeTermUpdate` with `number_of_terms=3` and 4 dates | ValidationError (count mismatch) | passing |
| TC-FEE-03-U05 | In-place update with equal counts, new dates [2026-07-01, 2026-10-01] over existing [2026-06-10, 2026-09-10] | Same two row ids kept, dates replaced in sorted order | passing |
| TC-FEE-03-U06 | In-place update shrinking 4 dates to 3 | Latest existing row (by sorted order) is deleted, the first three rows keep their ids with the new dates | passing |
| TC-FEE-03-U07 | In-place update growing 2 dates to 3 | Two rows updated, one new row added | passing |
| TC-FEE-03-A01 | Admin `POST /fee/terms/` "Quarterly", 4, four distinct dates | 201; response lists 4 dates with ids | passing |
| TC-FEE-03-A02 | POST with 3 dates and `number_of_terms=4` | 422 | passing |
| TC-FEE-03-A03 | POST with a repeated date | 422 | passing |
| TC-FEE-03-A04 | POST with unknown `academic_year_id` | 404 `Academic year with id ... not found` | passing |
| TC-FEE-03-A05 | POST `number_of_terms=0` with an empty date list | 201 (no backend range check); documented hazard for F06 | passing |
| TC-FEE-03-A06 | `GET /fee/terms/` with `limit` and `offset` | Plain array; terms include `fee_term_dates` | passing |
| TC-FEE-03-A07 | `GET /fee/terms/dropdown` after setting one term inactive | Inactive term absent; items have `id`, `term_name`, `number_of_terms` | passing |
| TC-FEE-03-A08 | `GET /fee/terms/{id}` and `GET /fee/terms/{id}/dates` | Dates ordered ascending; unknown id 404 `Fee term with id ... not found` | passing |
| TC-FEE-03-A09 | `PUT` change dates keeping the count; compare date ids before and after | Same ids, new dates (in-place update) | passing |
| TC-FEE-03-A10 | `PUT` `fee_term_dates` of 2 dates on a stored 4-date term, no `number_of_terms` | 400 `Number of fee term dates (2) must match number_of_terms (4)` | passing |
| TC-FEE-03-A11 | `PUT` `number_of_terms=3` with 3 dates on a term whose 4th date is referenced by a student term amount | 500 (delete of referenced date fails); term unchanged | passing |
| TC-FEE-03-A12 | `PUT` `term_status=inactive` | 200; dropdown no longer lists it | passing |
| TC-FEE-03-A13 | `DELETE /fee/terms/{id}` on an unused term | 200 returns the term; dates gone | passing |
| TC-FEE-03-A14 | `DELETE /fee/terms/{id}` on a term used by a fee type | 400 `Cannot delete fee term '<name>' because it is being used by 1 fee type(s)...` | passing |
| TC-FEE-03-A15 | `DELETE /fee/terms/dates/{id}` on an unreferenced date; unknown date id | 200 message; 404 `Fee term date with id ... not found` | passing |
| TC-FEE-03-A16 | `GET /fee/terms/health` | 200 `module: "fee_terms"` | passing |
| TC-FEE-03-A17 | Role matrix create, update, delete (term and date) | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-03-A18 | Role matrix list, read, dates, dropdown | Admin, Staff 200; others 403 | passing |
| TC-FEE-03-A19 | No token; cross-tenant header mismatch; tenant B cannot read tenant A term | 401; 403; 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-03-E01 | P1 | Web | Admin | Academic year 2026-2027 selected; skipped when the tenant already holds 50 or more fee terms (the web Fee Terms list loads only the first 50, so the new term is not shown) | 1. Open Fee > Fee Terms.<br>2. Click "Add New Term".<br>3. Enter Term Name "QA Quarterly", Number of Terms 4.<br>4. Pick 2026-06-10 in "Select date" and click "Add Date"; repeat for 2026-09-10, 2026-12-10, 2027-03-10.<br>5. Click "Create Term". | Toast "Fee term created successfully"; row "QA Quarterly", "4 terms", Payment Schedule "Jun 10 - Mar 10 (4 dates)", Active | passing |
| TC-FEE-03-E02 | P3 | Web | Admin | None | 1. Click "Add New Term".<br>2. Enter "QA Short", Number of Terms 3.<br>3. Add two dates.<br>4. Click "Create Term". | Error `You must add exactly 3 payment dates (currently 2 added)`; nothing saved | planned |
| TC-FEE-03-E03 | P2 | Web | Admin | TC-FEE-03-E01 done | 1. Click "Edit Fee Term" on "QA Quarterly".<br>2. Change installment 4 to 2027-03-15.<br>3. Click "Update Term".<br>4. Click "Payment Dates" on the row. | Toast "Fee term updated successfully"; "Manage Payment Dates - QA Quarterly" lists Installment 4 "Mar 15, 2027" | planned |
| TC-FEE-03-E04 | P2 | Web | Admin | TC-FEE-02-E01 done ("QA Lab" uses "QA Quarterly") | 1. Click "Delete Fee Term" on "QA Quarterly".<br>2. Confirm. | Error toast `Cannot delete fee term 'QA Quarterly' because it is being used by 1 fee type(s)...`; row stays | planned |
| TC-FEE-03-E05 | P3 | Web | Admin | Seeded term "Three Terms" | 1. Click "Payment Dates" on "Three Terms".<br>2. Read the dialog.<br>3. Click "Close". | "Manage Payment Dates - Three Terms", "3/3 configured", Installment 1 to 3 (Jun 15, 2026; Oct 15, 2026; Jan 15, 2027) with status Configured and the note to use "Edit"; dialog closes | planned |
| TC-FEE-03-E06 | P2 | Web | Staff | Seeded terms | 1. Sign in as Staff.<br>2. Open Fee > Fee Terms. | List visible; no "Add New Term", no Actions column (no edit or delete) | planned |
| TC-FEE-03-E07 | P2 | Mobile | Admin | None | 1. Open Fee Terms.<br>2. Tap "Add Fee Term".<br>3. Enter "QA Mobile Term", "Enter number of terms" 2.<br>4. Add dates 2026-07-01 and 2026-11-01 with "Add Date".<br>5. Tap "Create Term". | Toast "Fee term created successfully"; card "QA Mobile Term" with "2 terms" | planned |
| TC-FEE-03-E08 | P3 | Mobile | Admin | None | 1. Tap "Add Fee Term".<br>2. Enter "QA Mobile Bad", 3 terms, add only one date.<br>3. Tap "Create Term". | Toast "Number of term dates must equal number of terms"; nothing saved | planned |

API tests implemented in: backend/tests/api/fee/test_fee_terms.py

Implemented in: backend/tests/unit/fee/test_fee_term_mapping_rules.py (phase 1 unit cases).

---

## F04 Class fee mappings (including mandatory fees)

**Purpose.** Set what a fee type costs for a class in a year. A mapping flagged mandatory (`all_by_default`) is copied to every student of the class automatically, now and on future admissions.

**Roles and permissions.** `fee_class_mappings:create`, `read`, `update`, `delete`, `list` (toggle mandatory needs `update`). Default seed: Admin all; Staff read and list. Student mappings created by the mandatory flag are written by the same call regardless of the caller's `fee_student_mappings` grant. Menu: Fee > Fee Mappings > "Class Mappings" tab (web `/fee/mappings`); mobile tile "Fee Mappings" (tab "Class Mappings") or "Class Mappings" screen `/fees/class-mappings`.

**Preconditions.** A fee type (F02) exists; classes exist; for mandatory fees, students admitted to the class with a section and an admission number.

**Steps, web.**
1. Open Fee > Fee Mappings and choose the "Class Mappings" tab.
2. Click "Add Mapping" (or "Create First Mapping"). Dialog "Create Fee Mapping".
3. Choose "Fee Type *" ("Select fee type"), "Class *" ("Select class"), type "Total Fee *" ("Enter total fee"), optionally tick "Mandatory fee (apply to all students in this class)". Click "Save".
4. Toast "Fee class mapping created successfully". With Mandatory ticked, after the save the page also bulk-creates student mappings for every enrolled student section by section and toasts `Fee applied to X of Y students in this class.`
5. In the table (columns Class, Fee Type, Total Fee, Term Distribution, Mandatory, Actions) click the Mandatory badge ("Mandatory" or "Optional") to toggle; turning it on repeats the bulk apply. Edit sends only `total_fee` and `all_by_default` (dialog "Edit Fee Mapping"); delete confirms in "Delete Fee Mapping". The calculator button "Manage Term Amounts" opens F05. Search "Search by class, fee type, or amount...".
6. Validation toasts: `Please select both fee type and class`, `Total fee must be greater than 0`, `Please select an academic year`.

**Steps, mobile.** Fee hub > "Fee Mappings" > tab "Class Mappings", or the "Fee Term Amounts" tile (same tab). "Add Mapping" (empty state "No fee class mappings found"); fields "Select class", "Select fee type", "Enter total fee"; toasts "Mapping Created", "Mapping Updated" (edit works since K05 was fixed), mandatory toggle `Marked Mandatory` / `Applying this fee to all students in the class...` followed by "Fee Applied", delete "Mapping Deleted" / "Fee class mapping deleted successfully".

**Expected results.** One `fee_class_mappings` row per (class, fee type, year). When mandatory is on, one `fee_student_mappings` row (with equal-split `fee_student_map_term_amounts`) per admitted student who lacks one for that fee type and year.

**API endpoints.**
- `POST /fee/class-mappings/`: `class_id`, `fee_type_id`, `total_fee`, `academic_year_id`, `all_by_default` (false). 201 `FeeClassMappingRead` (adds `class_name`, `fee_type_name`, `academic_year_name`, `class_fee_mapping_terms`).
- `POST /fee/class-mappings/bulk`: `class_ids[]` (non-empty, no duplicates), `fee_type_id`, `total_fee`, `academic_year_id`, `all_by_default`. 201 `{success_count, total_count, created_mappings, errors[{class_id, class_name, error, error_code}], message}`; error codes `CLASS_NOT_FOUND`, `DUPLICATE_MAPPING`, `VALIDATION_ERROR`, `SYSTEM_ERROR`.
- `GET /fee/class-mappings/`: filters `class_id`, `fee_type_id`, `all_by_default`, `limit`, `offset`; no year filter.
- `GET /fee/class-mappings/{id}`; `PUT /fee/class-mappings/{id}`; `PATCH /fee/class-mappings/{id}/toggle-mandatory`; `DELETE /fee/class-mappings/{id}`; `GET /fee/class-mappings/health`.

**Rules and validations.**
- `total_fee >= 0` (0 allowed). Class, fee type and year must exist (404). Unique per (class, fee type, year): 400 `Fee class mapping already exists for this combination of class, fee type, and academic year`.
- Mandatory on create, update (false to true) or toggle (to true) runs `auto_map_students_for_class_mapping`: every admission with `current_class_id` equal to the class and `academic_year_id` equal to the year; admissions without `current_section_id` or `admission_number` are skipped; students that already have a mapping for that fee type and year are skipped; the new student mapping copies `total_fee` and gets an equal split over the fee type's term dates. Turning mandatory off, or changing `total_fee` later, never touches existing student mappings.
- New admissions apply every mandatory mapping of their class and year (`auto_apply_mandatory_fees_to_admission`); a failure there is logged and swallowed so admission still succeeds. It returns 0 when class, year, section or admission number is missing.
- Bulk create is per class: valid classes are committed, failed ones reported in `errors`; a missing fee type or year fails the whole call.
- Class term amounts are a display template; the summary and payment never read them.
- `FeeClassMappingUpdate` types `class_id`, `fee_type_id` and `academic_year_id` as UUIDs and the uniqueness check accepts them (K05 fixed).
- `GET /fee/class-mappings/?fee_type_id=<uuid>` filters by fee type (K05 fixed).

**Error and edge cases.** Delete is a hard delete with no payment check; its class term amounts are deleted with it (ORM cascade). Deleting a mapping never removes student mappings made from it. A class with 0 students and mandatory on succeeds with 0 student mappings. A fee type whose term has 0 dates makes the auto-map fail for each student.

**Unit-testable logic.** `auto_map_students_for_class_mapping` and `auto_apply_mandatory_fees_to_admission` (skip rules, no duplicates, count); `check_mapping_unique`; bulk error-code mapping; `FeeClassMappingBulkCreate` validators; `toggle_class_mapping_mandatory` flag flip.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-04-U01 | `FeeClassMappingCreate` with `total_fee=-1` | ValidationError `total_fee must be non-negative` | passing |
| TC-FEE-04-U02 | `FeeClassMappingBulkCreate` with `class_ids=[]` | ValidationError `at least one class_id is required` | passing |
| TC-FEE-04-U03 | `FeeClassMappingBulkCreate` with a repeated class id | ValidationError `duplicate class_ids are not allowed` | passing |
| TC-FEE-04-U04 | Auto-map with 3 admissions: one without section, one with an existing mapping, one valid | Returns 1; only the valid student gets a row | passing |
| TC-FEE-04-U05 | Auto-apply for an admission with no `admission_number` | Returns 0, no rows | passing |
| TC-FEE-04-U06 | Auto-apply with two mandatory mappings (Tuition 12000, Lab 1000) and one already mapped | Creates only the missing one; returns 1 | passing |
| TC-FEE-04-U07 | Bulk error code selection: 404 gives `CLASS_NOT_FOUND`; 400 containing "already exists" gives `DUPLICATE_MAPPING`; other 400 gives `VALIDATION_ERROR` | Codes as stated | passing |
| TC-FEE-04-U08 | Auto-map copies `total_fee` 12000 over Q4 | 4 student term amounts of 3000.00 | passing |
| TC-FEE-04-A01 | Admin `POST /fee/class-mappings/` class C1, Tuition, 12000, `all_by_default=false` | 201; names resolved; `class_fee_mapping_terms` empty | passing |
| TC-FEE-04-A02 | POST the same (class, type, year) again | 400 `Fee class mapping already exists...` | passing |
| TC-FEE-04-A03 | POST with `total_fee` 0 | 201 (zero allowed) | passing |
| TC-FEE-04-A04 | POST with negative `total_fee` | 422 | passing |
| TC-FEE-04-A05 | POST with unknown class, unknown type, unknown year (three calls) | 404 `Class with id ...`, `Fee type with id ...`, `Academic year with id ...` | passing |
| TC-FEE-04-A06 | POST `all_by_default=true` for a class with 2 admitted students (section and admission number set) | 201; both students now have a student mapping for the type with total 12000.00 and 4 term amounts | passing |
| TC-FEE-04-A07 | `PATCH /{id}/toggle-mandatory` on an optional mapping, then again | First call `all_by_default=true` and students mapped; second call false and the student mappings remain | passing |
| TC-FEE-04-A08 | `PUT` `all_by_default=true` on an optional mapping | Students mapped once; repeating the PUT creates no duplicates | passing |
| TC-FEE-04-A09 | `PUT` `total_fee=13000` after students were mapped | Class mapping 13000; student mappings stay 12000 | passing |
| TC-FEE-04-A10 | `PUT` with `fee_type_id` (UUID) | 200 with the new type | passing |
| TC-FEE-04-A11 | `PUT` with `class_id` as a UUID string | 422 (field typed as integer) | passing |
| TC-FEE-04-A12 | `POST /fee/class-mappings/bulk` with 3 classes, one already mapped | 201; `success_count=2`, `total_count=3`, one `DUPLICATE_MAPPING` error, message `Successfully created 2 out of 3 fee class mappings. 1 failed.` | passing |
| TC-FEE-04-A13 | Bulk with an unknown class id among valid ones | That class reported `CLASS_NOT_FOUND`; others created | passing |
| TC-FEE-04-A14 | Bulk with an unknown `fee_type_id` | 404 `Fee type with id ... not found`; nothing created | passing |
| TC-FEE-04-A15 | `GET /fee/class-mappings/` filters `class_id`, `all_by_default=true`, `limit`, `offset` | Filtered arrays; items carry term amounts | passing |
| TC-FEE-04-A16 | `GET /fee/class-mappings/?fee_type_id=<uuid>` | 200 filtered | passing |
| TC-FEE-04-A17 | `GET /fee/class-mappings/{id}` existing and unknown | 200; 404 `Fee class mapping with id ... not found` | known defect: FEE-B04: GET /fee/class-mappings/{unknown id} returns 500 because the service swallows its own 404 |
| TC-FEE-04-A18 | `DELETE` a mapping; its student mappings | 200; student mappings still exist | passing |
| TC-FEE-04-A19 | `GET /fee/class-mappings/health` | 200 `module: "fee_class_mappings"` | passing |
| TC-FEE-04-A20 | Role matrix create, update, toggle, delete, bulk | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-04-A21 | Role matrix list and read | Admin, Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-04-A22 | No token; cross-tenant header; tenant B list excludes tenant A mappings | 401; 403; empty | known defect: FEE-B04: cross-tenant GET /fee/class-mappings/{id} returns 500 instead of 404 |
| TC-FEE-04-A23 | Admission created after a mandatory mapping exists (via the admission endpoint) | New student gets the student mapping and term amounts automatically | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-04-E01 | P1 | Web | Admin | TC-FEE-02-E01 done; seeded class Class 5 | 1. Open Fee > Fee Mappings.<br>2. Choose the "Class Mappings" tab.<br>3. Click "Add Mapping".<br>4. Choose Fee Type "QA Lab", Class "Class 5", Total Fee 12000; leave "Mandatory fee" unticked.<br>5. Click "Save". | Toast "Fee class mapping created successfully"; row Class 5, QA Lab, 12,000, Term Distribution "Not Set", badge "Optional" | passing |
| TC-FEE-04-E02 | P1 | Web | Admin | TC-FEE-02-E05 done ("QA Kit"); an own QA class with one QA student | 1. Class Mappings tab, "Add Mapping".<br>2. Fee Type "QA Kit", Class = the own QA class, Total Fee 500, tick "Mandatory fee (apply to all students in this class)".<br>3. Click "Save".<br>4. Open Fee Collection for a QA student created through the API in that QA class. | Toast `Fee applied to X of Y students in this class.`; the QA student's Fee Summary lists "QA Kit" 500.00. Clean up: delete the created student mappings and the class mapping | known defect: UI-FEE-01: mandatory class mapping toast says "Fee applied to 0 of 1 students" although the fee was applied (t... |
| TC-FEE-04-E03 | P2 | Web | Admin | TC-FEE-04-E01 done | 1. Class Mappings tab.<br>2. Click the "Optional" badge on Class 5 / QA Lab. | Badge becomes "Mandatory"; toast `Fee applied to X of Y students in this class.`; Class 5 students now have "QA Lab" | planned |
| TC-FEE-04-E04 | P3 | Web | Admin | TC-FEE-02-E01 done | 1. Click "Add Mapping".<br>2. Choose QA Lab and Class 3, Total Fee 0.<br>3. Click "Save". | Toast `Total fee must be greater than 0`; nothing saved | planned |
| TC-FEE-04-E05 | P3 | Web | Admin | Seeded mapping Class 1 / Tuition Fee | 1. Click "Add Mapping".<br>2. Choose Tuition Fee, Class 1, Total Fee 1000.<br>3. Click "Save". | Error toast `Fee class mapping already exists for this combination of class, fee type, and academic year` | planned |
| TC-FEE-04-E06 | P2 | Web | Admin | TC-FEE-04-E03 done | 1. Edit Class 5 / QA Lab, Total Fee 13000, save.<br>2. Open the "Student Mappings" tab and filter Fee Type "QA Lab". | Toast "Fee class mapping updated successfully"; class row 13,000; student mappings still 12,000 | planned |
| TC-FEE-04-E07 | P2 | Web | Admin | TC-FEE-04-E01 done | 1. Click delete on Class 5 / QA Lab.<br>2. Confirm in "Delete Fee Mapping". | Toast "Fee class mapping deleted successfully"; row removed; student mappings made from it remain | planned |
| TC-FEE-04-E08 | P2 | Web | Staff | Seeded class mappings | 1. Sign in as Staff.<br>2. Open Fee > Fee Mappings > "Class Mappings". | Read-only: no "Add Mapping", no edit, delete or toggle controls; class and fee type names shown | planned |
| TC-FEE-04-E09 | P2 | Mobile | Admin | TC-FEE-02-E01 done | 1. Open Fee Mappings > "Class Mappings" (or the Class Mappings screen).<br>2. Tap "Add Mapping", choose Class 3, QA Lab, 900, save.<br>3. Toggle mandatory on that card. | Toasts "Mapping Created" then "Marked Mandatory" (Applying this fee to all students in the class...) and a "Fee Applied" toast | planned |
| TC-FEE-04-E10 | P3 | Mobile | Admin | TC-FEE-04-E09 done | 1. Edit the Class 3 / QA Lab mapping.<br>2. Change the total to 950 and save. | Toast "Mapping Updated" (Fee class mapping updated successfully); card shows 950 | planned |

API tests implemented in: backend/tests/api/fee/test_fee_class_mappings.py

Implemented in: backend/tests/unit/fee/test_fee_term_mapping_rules.py (phase 1 unit cases).

---

## F05 Class mapping term amounts

**Purpose.** Record, for each due date of a class mapping, how much of the class total falls on that date. This is a display and template layer: student term amounts are always an equal split and the summary and payment never read it.

**Roles and permissions.** `fee_class_mapping_term_amounts:create`, `read`, `update`, `delete`, `list`. Default seed: Admin all; Staff read and list. Menu: Fee > Fee Term Amounts (web redirects `/fee/term-amounts` to `/fee/mappings#class-mappings-term-amounts`, which opens the Class Mappings tab and highlights the first row); mobile tile "Fee Term Amounts" (`/fees/mappings?tab=class-mappings`).

**Preconditions.** A class mapping (F04) whose fee type has a fee term with dates.

**Steps, web.**
1. Fee > Fee Mappings > "Class Mappings", click the calculator button "Manage Term Amounts" in a row. The dialog "Manage Term Amounts" shows Fee Type, Total Amount, Number of Terms and Term Structure.
2. Choose "Equal Distribution" (divides the total evenly) or "Manual Entry"; type an "Amount" per installment. The footer shows "Total Term Amount", "Difference" and a Valid or Invalid marker.
3. Click "Save Term Amounts". The page refuses to save unless the number of terms matches and the amounts sum to the total (`Term amounts must sum to the total fee amount`).

**Steps, mobile.** Class Mappings screen, open a mapping's term amounts, enter an amount per term, save: toast "Term amounts saved successfully".

**Expected results.** `fee_class_map_term_amounts` rows, one per term date, each with `term_id` and `term_date_id`. The Class Mappings table shows Term Distribution "Complete (N terms)", "Not Set", or `Mismatch: <difference>`.

**API endpoints.** Prefix `/fee/class-mapping-term-amounts`.
- `POST /`: `{fee_class_mapping_id, term_amounts:[{term_date_id, term_amount}]}` returns 201 with the created list.
- `PUT /`: `{fee_class_mapping_id, term_amounts:[{id?, term_date_id, term_amount}]}` (an item without `id` is created).
- `DELETE /`: body `{term_amount_ids:[...]}` returns `{message: "Successfully deleted N term amount(s)"}`.
- `GET /by-mapping/{class_mapping_id}`; `GET /` with `class_mapping_id`, `fee_term_id`, `limit` (default 100, max 500), `offset`; `GET /{term_amount_id}`; `GET /health`.

**Rules and validations.**
- `term_amount > 0` (zero is rejected with 422 `term_amount must be positive`); the list must not be empty.
- The count of amounts must equal the number of dates of the fee type's term: 400 `Number of term amounts (N) must match number of term dates (M)`.
- The sum must equal the mapping `total_fee` exactly (Decimal equality): 400 `Sum of term amounts (X) must equal total fee (Y) in the fee class mapping`. Web checks with a tolerance of 0.01 and Equal Distribution can produce unrounded values (for example 333.3333 x 3), which the backend rejects; manual entry must sum exactly.
- Each `term_date_id` must belong to the fee type's term and be unique inside the request: 400 `Term date <id> not found or doesn't belong to term <name>` or `Duplicate term_date_id <id> in request`.
- Unique per (mapping, term date) in the database: 400 `Term amount already exists for this fee class mapping and term date combination`.
- On update, an `id` that is not one of the mapping's amounts: 404 `Term amount with id <id> not found`. The count and sum checks use only the amounts sent in the request.
- `FeeClassMappingTermAmountUpdate` requires `term_date_id`; sending only `term_id` gives 422.
- Fee type without a term: 400 `Associated fee term not found`.

**Error and edge cases.** A student mapping created later ignores these amounts. Changing the fee term dates (F03) keeps `term_date_id` valid because dates are updated in place. Deleting amounts one by one leaves the mapping showing "Not Set".

**Unit-testable logic.** `validate_term_count`, `validate_total_amount_matches` (exact Decimal equality), schema validators `validate_term_amount` and non-empty lists, update with and without `id`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-05-U01 | `validate_total_amount_matches` mapping 1000.00 with 333.33, 333.33, 333.33 | Raises 400 `Sum of term amounts (999.99) must equal total fee (1000.00)...` | passing |
| TC-FEE-05-U02 | `validate_total_amount_matches` 3000.00 with 1000, 1000, 1000 | Passes | passing |
| TC-FEE-05-U03 | `FeeClassMappingTermAmountBase` with `term_amount=0` and with `-5` | ValidationError `term_amount must be positive` | passing |
| TC-FEE-05-U04 | `FeeClassMappingTermAmountBulkCreate` with `term_amounts=[]` | ValidationError `term_amounts list cannot be empty` | passing |
| TC-FEE-05-U05 | `FeeClassMappingTermAmountBulkDelete` with `term_amount_ids=[]` | ValidationError `term_amount_ids list cannot be empty` | passing |
| TC-FEE-05-U06 | `validate_term_count` with 3 amounts and a term of 4 dates | Raises 400 `Number of term amounts (3) must match number of term dates (4)` | passing |
| TC-FEE-05-U07 | Web equal distribution of 1000 over 3 (333.3333333) | Frontend tolerance passes, backend equality fails (documents the gap K06) | passing (backend half asserts the exact-sum failure, defect K06; web tolerance half is inline in TermAmountModal.tsx and not covered) |
| TC-FEE-05-A01 | `POST /fee/class-mapping-term-amounts/` for a 12000 Tuition mapping with four 3000 amounts | 201; four rows; each carries `term_date_id`, `term_id`, `term_name`, `term_date` | passing |
| TC-FEE-05-A02 | POST with amounts 3000, 3000, 3000, 2999 | 400 `Sum of term amounts (11999) must equal total fee (12000.00)...` | passing |
| TC-FEE-05-A03 | POST with 3 amounts for a 4-date term | 400 count mismatch | passing |
| TC-FEE-05-A04 | POST with a `term_date_id` from another term | 400 `Term date ... not found or doesn't belong to term Quarterly` | passing |
| TC-FEE-05-A05 | POST the same `term_date_id` twice in one request | 400 `Duplicate term_date_id ... in request` | passing |
| TC-FEE-05-A06 | POST the same set again for the same mapping | 400 `Term amount already exists for this fee class mapping and term date combination` | passing |
| TC-FEE-05-A07 | POST with `term_amount` 0 | 422 | passing |
| TC-FEE-05-A08 | POST for an unknown mapping id | 404 `Fee class mapping with id ... not found` | passing |
| TC-FEE-05-A09 | `PUT /` with ids and new amounts 4000, 4000, 2000, 2000 | 200; amounts replaced; sum 12000 | passing |
| TC-FEE-05-A10 | `PUT /` with an unknown amount id | 404 `Term amount with id ... not found` | passing |
| TC-FEE-05-A11 | `PUT /` item without `id` | A new row is created and the request is validated as a whole | passing |
| TC-FEE-05-A12 | `PUT /` item with `term_id` only | 422 (`term_date_id` required) | passing |
| TC-FEE-05-A13 | `GET /by-mapping/{id}`, `GET /` with `class_mapping_id` and `fee_term_id`, `GET /{id}` | Ordered and filtered arrays; unknown id 404 `Term amount with id ... not found` | known defect: FEE-B06: GET by-mapping, list and single term-amount reads return term_date null (only create/update fill it) |
| TC-FEE-05-A14 | `DELETE /` with two ids | 200 message `Successfully deleted 2 term amount(s)` | passing |
| TC-FEE-05-A15 | `GET /fee/class-mapping-term-amounts/health` | 200 | passing |
| TC-FEE-05-A16 | Role matrix create, update, delete | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-05-A17 | Role matrix read, list, by-mapping | Admin, Staff 200; others 403 | passing |
| TC-FEE-05-A18 | No token; cross-tenant header; tenant isolation | 401; 403; hidden | passing |
| TC-FEE-05-A19 | Student mapping created after saving class term amounts | Student term amounts still an equal split, not copied from these rows | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-05-E01 | P1 | Web | Admin | TC-FEE-04-E01 done (12000 on 4-date "QA Quarterly") | 1. Class Mappings tab.<br>2. Click "Manage Term Amounts" on Class 5 / QA Lab.<br>3. Click "Equal Distribution".<br>4. Click "Save Term Amounts". | Toast "Term amounts created successfully"; four 3,000.00 rows; Term Distribution "Complete (4 terms)" | passing |
| TC-FEE-05-E02 | P2 | Web | Admin | TC-FEE-05-E01 done | 1. Open "Manage Term Amounts" again.<br>2. Choose "Manual Entry" and enter 5000, 3000, 2000, 2000.<br>3. Click "Save Term Amounts". | Difference 0 and Valid before saving; toast "Term amounts updated successfully" | planned |
| TC-FEE-05-E03 | P3 | Web | Admin | TC-FEE-05-E01 done | 1. Open "Manage Term Amounts".<br>2. Manual Entry 5000, 3000, 2000, 1000.<br>3. Click "Save Term Amounts". | Invalid marker; toast `Term amounts must sum to the total fee amount`; nothing saved | planned |
| TC-FEE-05-E04 | P3 | Web | Admin | Seeded class mappings | 1. Open `/fee/term-amounts` (or the "Term Amounts" sidebar entry). | Lands on `/fee/mappings#class-mappings-term-amounts` with the Class Mappings tab open and the first row highlighted | planned |
| TC-FEE-05-E05 | P3 | Web | Staff | Seeded mapping Class 1 / Tuition Fee with term amounts | 1. Sign in as Staff.<br>2. Class Mappings tab, open "Manage Term Amounts" on Class 1 / Tuition Fee. | Amounts read-only; no distribution buttons and no "Save Term Amounts" | planned |
| TC-FEE-05-E06 | P2 | Mobile | Admin | TC-FEE-04-E09 done (900 on 4 dates) | 1. Class Mappings screen.<br>2. Open term amounts for Class 3 / QA Lab.<br>3. Enter 225 for each term and save. | Toast "Saved" (Term amounts saved successfully) | planned |

API tests implemented in: backend/tests/api/fee/test_fee_term_amounts.py

Implemented in: backend/tests/unit/fee/test_fee_term_mapping_rules.py (phase 1 unit cases).

---

## F06 Student fee mappings

**Purpose.** Assign fee types to individual students. This is the table the summary and payment read: what the student actually owes, split into one term amount per due date.

**Roles and permissions.** `fee_student_mappings:create`, `read`, `update`, `delete`, `list`. Default seed: Admin all; Staff create, read, update, list (no delete, so Staff cannot unassign). Menu: Fee > Fee Mappings > tabs "Student Mappings" and "Assign Student Fees"; mobile Fee hub > "Fee Mappings" or screens `/fees/student-mappings` and `/fees/assign-student-fees`.

**Preconditions.** Student with an admission (admission number, class, section), fee type with a term that has dates, and the academic year. Automatic path: a mandatory class mapping (F04) exists before or after the admission.

**Steps, web.**
1. Fee > Fee Mappings opens on the "Student Mappings" tab (tabs in order: "Student Mappings", "Assign Student Fees", "Class Mappings"; heading "Fee Student Mappings"). Filters: "Search by student name, admission number, or fee type...", "Filter by class", "Filter by section", "Filter by fee type" (All Classes, All Sections, All Fee Types). Columns Student, Class & Section, Fee Type, Total Fee, Actions.
2. "Create Mapping": dialog "Create Fee Student Mapping" with Student, Admission Number (auto-filled), Class, Section, Address (auto-filled), Fee Type, "Total Fee" with the rupee symbol in brackets; for a Transport fee type the amount fills from Bus, Trip and Stop selections ("Stop Fee"). Button "Create Mapping" ("Update Mapping" when editing).
3. "Bulk Create": dialog "Bulk Create Fee Student Mappings": Class, Section, Fee Type, "Total Fee", Students multi-select; button "Create Mappings (N students)"; a "Bulk Creation Result" card lists successes and "Errors".
4. Edit with "Edit Mapping" (dialog "Edit Fee Student Mapping"); delete with "Delete Mapping" and the dialog "Delete Fee Student Mapping".
5. "Assign Student Fees" tab: choose Class, Section and Student ("Search by name or admission no..."; until then "Select a student above to manage their fee assignments."); the page lists "Mandatory Fees", "Non-Mandatory Fees" and "Transport Fee" from the class mappings with a per-row "Assign" button or Assigned badge; unassigning deletes the student mapping.

**Steps, mobile.** "Student Mappings" screen (search "Search by student, class or fee type...", add form, bulk form "Select students", delete); "Assign Student Fees" screen (class, section, "Search by name or admission no...", assign or remove per fee). Toasts: "Mapping Created", "Bulk Mappings Created", "Mapping Updated", "Mapping Deleted", "Fee Assigned", "Fee Removed"; required-field toasts "Student is required", "Total fee must be greater than 0", "At least one student must be selected".

**Expected results.** One `fee_student_mappings` row per (student, fee type, year) and N `fee_student_map_term_amounts` rows, one per term date of the fee type's term, each `total_fee / N` (rounded by the database to 2 decimals). The student's Fee Summary (F09) lists the fee type.

**API endpoints.** Prefix `/fee/student-mappings`.
- `POST /`: `student_id`, `student_admission_num`, `class_id`, `section_id`, `fee_type_id`, `total_fee`, `academic_year_id`. 201 with `student_details`, `fee_type_name`, `student_fee_mapping_terms`.
- `POST /bulk`: `student_ids[]` (non-empty, unique), `class_id`, `section_id`, `fee_type_id`, `total_fee`, `academic_year_id`. 201 `{success_count, total_count, created_mappings, errors[{student_id, student_name, student_admission_num, error, error_code}], message}`.
- `GET /` filters `student_id`, `class_id`, `section_id`, `fee_type_id`, `academic_year_id`, `limit`, `offset`; `GET /{id}`; `PUT /{id}`; `DELETE /{id}`; `GET /health`.

**Rules and validations.**
- `total_fee >= 0`. Student, admission number (global), class, section, fee type, year must exist (404). Unique per (student, fee type, year): 400 `Fee student mapping already exists for this combination of student, fee type, and academic year`.
- The fee type must have a term: 400 `Fee type has no associated fee term`; term dates count must equal `number_of_terms` else 500 `Data inconsistency: Fee term has N terms but M dates`; a term with 0 installments makes the split fail (500).
- Term amounts are created by `create_term_amounts`: dates ordered ascending, `amount = total_fee / number_of_dates` (see calculation reference and W4).
- `PUT` with `total_fee` deletes all existing term amounts of the mapping and recreates them (equal split). Concessions keep their stored `assigned_fee`; paid history is untouched.
- Bulk: each student must have an admission (any); the admission number is taken from it, the class and section from the request (no check that the student belongs to them). Failures are per student (`STUDENT_NOT_FOUND`, `DUPLICATE_MAPPING`, `VALIDATION_ERROR`, `SYSTEM_ERROR`); successes are committed.
- The list endpoint returns light rows: `fee_type_name`, `academic_year_name`, `student_details` null and `student_fee_mapping_terms` empty. Use `GET /{id}` for the full view.
- Delete is a hard delete with no payment check; a mapping that has a concession cannot be deleted (foreign key, 500); transaction items survive but drop out of the summary.
- Class mapping total changes never propagate (F04).

**Error and edge cases.** Duplicate in bulk reported per student. The mandatory-fee automatic path skips students without section or admission number. Transport fee types are assigned with the stop fee as `total_fee`.

**Unit-testable logic.** `create_term_amounts` (equal split, ordering, rounding, inconsistency error); `check_mapping_unique`; `FeeStudentMappingBulkCreate` validators; bulk error-code mapping; update-recreates-term-amounts.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-06-U01 | `create_term_amounts` total 12000.00 over 4 dates | Four amounts of 3000.00 ordered by date ascending | passing |
| TC-FEE-06-U02 | `create_term_amounts` total 1000.00 over 3 dates | Three Decimal shares of 333.3333... that persist as 333.33 (sum 999.99) | passing |
| TC-FEE-06-U03 | `create_term_amounts` total 1000.01 over 2 dates | Each share 500.005 persists as 500.01 (sum 1000.02) | passing |
| TC-FEE-06-U04 | `create_term_amounts` total 100.00 over 8 dates | 12.50 each exactly | passing |
| TC-FEE-06-U05 | `create_term_amounts` when the term row count differs from `number_of_terms` | 500 `Data inconsistency: Fee term has 4 terms but 3 dates` | passing |
| TC-FEE-06-U06 | `get_fee_terms_for_type` for a type without a term | 400 `Fee type has no associated fee term` | passing |
| TC-FEE-06-U07 | `FeeStudentMappingBulkCreate` with duplicate student ids | ValidationError `duplicate student_ids are not allowed` | passing |
| TC-FEE-06-U08 | `FeeStudentMapTermAmountCreate` with `term_amount=-1` | ValidationError (non-negative) | passing |
| TC-FEE-06-U09 | `check_mapping_unique` with `exclude_id` equal to the existing mapping | No error | passing |
| TC-FEE-06-A01 | Admin `POST /fee/student-mappings/` student S1, Tuition, 12000 | 201; `student_fee_mapping_terms` has 4 items of "3000.00" for the Q4 dates | known defect: FEE-B07: student fee mapping term amounts always carry term_date null (POST and GET), although the schema fiel... |
| TC-FEE-06-A02 | POST a Lab mapping of 1000 on T3 | 3 term amounts of "333.33" | passing |
| TC-FEE-06-A03 | POST the same (student, type, year) twice | 400 `Fee student mapping already exists...` | passing |
| TC-FEE-06-A04 | POST with an unknown admission number | 404 `Admission with number ... not found` | passing |
| TC-FEE-06-A05 | POST with unknown student, class, section, type, year (five calls) | 404 for each with the matching message | passing |
| TC-FEE-06-A06 | POST negative `total_fee` | 422 | passing |
| TC-FEE-06-A07 | POST `total_fee=0` | 201; term amounts "0.00" | passing |
| TC-FEE-06-A08 | `POST /bulk` for 3 students, one already mapped | 201; `success_count=2`, one `DUPLICATE_MAPPING`; message `Successfully created 2 out of 3 fee student mappings. 1 failed.` | passing |
| TC-FEE-06-A09 | Bulk with a student that has no admission | Error `STUDENT_NOT_FOUND` for that student; others created | passing |
| TC-FEE-06-A10 | Bulk where all fail | `success_count=0`, message `Failed to create any fee student mappings. All N attempts failed.` | passing |
| TC-FEE-06-A11 | Bulk with an unknown class, section, type or year | 404 for the whole call; nothing created | passing |
| TC-FEE-06-A12 | `GET /` filtered by `student_id` and `academic_year_id` | Light rows; `student_details` null, `student_fee_mapping_terms` empty | passing |
| TC-FEE-06-A13 | `GET /{id}` | Full payload with `student_details` (name, class, section) and term amounts | passing |
| TC-FEE-06-A14 | `PUT /{id}` `total_fee=6000` | Old term amounts replaced by four "1500.00"; mapping total 6000.00 | passing |
| TC-FEE-06-A15 | `PUT /{id}` change `fee_type_id` to a type the student already has | 400 duplicate | passing |
| TC-FEE-06-A16 | `DELETE /{id}` without a concession | 200; GET afterwards 404; summary no longer lists the fee | known defect: FEE-B05: GET /fee/student-mappings/{deleted or unknown id} returns 500 instead of 404 |
| TC-FEE-06-A17 | `DELETE /{id}` for a mapping that has a concession | 500 (foreign key); mapping remains | passing |
| TC-FEE-06-A18 | After a payment, `DELETE` the mapping | 200; the payment still exists in transactions but the summary excludes that fee type | passing |
| TC-FEE-06-A19 | `GET /fee/student-mappings/health` | 200 | passing |
| TC-FEE-06-A20 | Role matrix create, update, bulk | Admin and Staff 2xx; Teacher, Student, Parent 403 | passing |
| TC-FEE-06-A21 | Role matrix delete | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-06-A22 | Role matrix list and read | Admin, Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-06-A23 | No token; cross-tenant header; tenant B sees none of tenant A's mappings | 401; 403; empty | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-06-E01 | P1 | Web | Admin | TC-FEE-02-E01 done; a QA student created through the API in an own QA class | 1. Open Fee > Fee Mappings (Student Mappings tab).<br>2. Click "Create Mapping".<br>3. Choose the QA student (Admission Number and Address fill), its QA class and section, Fee Type "QA Lab".<br>4. Enter Total Fee 1200.<br>5. Click "Create Mapping". | Toast "Fee student mapping created successfully"; row appears; the QA student's Fee Summary lists QA Lab, Actual Amount 1,200.00 | passing |
| TC-FEE-06-E02 | P2 | Web | Admin | TC-FEE-02-E05 done | 1. Click "Bulk Create".<br>2. Choose Class "Class 2", Section "2-A", Fee Type "QA Kit", Total Fee 300.<br>3. Select 3 students.<br>4. Click "Create Mappings (3 students)". | Toast "Successfully created 3 out of 3 mappings"; "Bulk Creation Result" lists 3 successes | planned |
| TC-FEE-06-E03 | P3 | Web | Admin | TC-FEE-06-E02 done | 1. "Bulk Create" again for Class 2 / 2-A, QA Kit, 300.<br>2. Select the same 3 students plus one more.<br>3. Click "Create Mappings (4 students)". | Toast "Successfully created 1 out of 4 mappings"; the result card lists 3 errors (DUPLICATE_MAPPING) | planned |
| TC-FEE-06-E04 | P2 | Web | Admin | TC-FEE-06-E01 done | 1. Click "Edit Mapping" on Kavya Verma / QA Lab.<br>2. Change Total Fee to 600.<br>3. Click "Update Mapping". | Toast "Fee student mapping updated successfully"; row 600; Fee Summary shows 600.00 | planned |
| TC-FEE-06-E05 | P2 | Web | Admin | TC-FEE-06-E02 done | 1. Click "Delete Mapping" on one QA Kit row.<br>2. Confirm in "Delete Fee Student Mapping". | Toast "Fee student mapping deleted successfully"; row removed | planned |
| TC-FEE-06-E06 | P2 | Web | Admin | Seeded student Advik Mehta (002, 1-B); TC-FEE-02-E05 done and a class mapping Class 1 / QA Kit (optional) exists | 1. Choose the "Assign Student Fees" tab.<br>2. Choose Class "Class 1", Section "1-B", Student "Advik Mehta".<br>3. Click "Assign" on QA Kit under "Non-Mandatory Fees".<br>4. Click it again to unassign. | Row shows Assigned, then returns to Assign; the student mapping is created and then deleted | planned |
| TC-FEE-06-E07 | P3 | Web | Staff | Seeded student Advik Mehta with the seeded Activity Fee assigned | 1. Sign in as Staff.<br>2. "Assign Student Fees" tab, Class 1, 1-B, Advik Mehta.<br>3. Try to unassign Activity Fee. | Toast "You don't have permission to remove fee assignments"; mapping stays | planned |
| TC-FEE-06-E08 | P3 | Web | Admin | Seeded student mappings | 1. Student Mappings tab.<br>2. Choose Class "Class 1", Section "1-A", Fee Type "Tuition Fee". | Only Class 1 / 1-A Tuition Fee rows (for example Saanvi Iyer, Kavya Verma) | planned |
| TC-FEE-06-E09 | P2 | Mobile | Admin | TC-FEE-02-E01 done | 1. Open the Student Mappings screen.<br>2. Tap "Create Mapping": Kavya Verma, Class 1, 1-A, QA Lab, 500, save.<br>3. Delete that mapping. | Toasts "Mapping Created" then "Mapping Deleted" | planned |
| TC-FEE-06-E10 | P2 | Mobile | Admin | As TC-FEE-06-E06 | 1. Open Assign Student Fees.<br>2. Choose Class 1, 1-B, Advik Mehta.<br>3. Assign QA Kit, then remove it. | Toasts "Fee Assigned" then "Fee Removed" | planned |
| TC-FEE-06-E11 | P2 | Web | Admin | A mandatory class mapping exists for the class (seeded Tuition Fee and Admission Fee are mandatory for every class) | 1. Admit a new student "QA Admit Student" into Class 2 / 2-B with an admission number and section (Students > Admission).<br>2. Open Fee > Fee Collection and open that student. | Fee Summary already lists Tuition Fee and Admission Fee | planned |

API tests implemented in: backend/tests/api/fee/test_fee_student_mappings.py

Implemented in: backend/tests/unit/fee/test_fee_term_mapping_rules.py (phase 1 unit cases).

---

## F07 Concessions

**Purpose.** Reduce what one student owes for one fee type in one year (a scholarship, sibling discount, staff ward discount). The approver is only an audit label.

**Roles and permissions.** `fee_concessions:create` (bulk apply), `read` (summary, history, single), `update`, `delete` (revoke), `list` (granted but not checked by these endpoints). Default seed: Admin only; Staff has no grant. Web: Fee > Fee Collection > student > "Concessions" tab (UI checks `fee_concessions` create, update, delete). Mobile: Fee Collection > student > "Concessions" tab.

**Preconditions.** The student has a student fee mapping (F06) for the fee type and year.

**Steps, web.**
1. Fee > Fee Collection, search and open a student, choose the "Concessions" tab.
2. In "Apply Concessions" the table lists every assigned fee type: S.No., Fee Type, Assigned, Due Amount, Due Date, Settled, "Concession Amt", "Reason (min 5 chars)", "Approved By" (Owner, Principal, Management, Correspondent). A row with an existing concession shows the placeholder "Add more..." because a new amount is added on top.
3. Type an amount (the input is capped at the row's Due Amount; a larger number toasts `Concession for <type> cannot exceed the due amount of <amount>.` and is reset), a reason of at least 5 characters, choose the approver, then click "Save All Concessions". Only complete rows are sent; incomplete rows are reported by toast (`Skipped N incomplete row(s): ...`); with no valid row the toast is `Enter a concession amount, a reason (min 5 characters), and select an approver before saving.` A successful save toasts "Concessions saved successfully". The footer shows "Grand Total", the concession total and "After Concession: <amount>".
4. Open the collapsible "Concession History" (Date, Fee Type, Amount, Reason, Approver, Recorded By, Actions with "Edit" and "Delete"). Edit opens "Edit Concession" (Concession Amount, "Reason (min 5 characters)", "Approved By", "Save"); the delete icon opens "Revoke Concession" with "Revoke". Toasts "Concession updated successfully" and "Concession revoked successfully".

**Steps, mobile.** Collection > student > "Concessions" ("Apply Concessions", "Save All Concessions"): per fee type card with Assigned, Due and due date, "Concession Amt" ("Add more..." with "+<amount> applied" when one exists, or "0.00"), "Approved By", "Reason (min 5 chars)"; a "Grand Total" block (Assigned, Concession, After Concession); history list with "Edit Concession" and "Revoke Concession" modals; "No concession history found." when empty.

**Expected results.** A `fee_concessions` row per (student, fee type, year) (unique, including revoked rows). Summary and payment totals use the active amount. The Fee Summary "Payable Amount" and "Due" change immediately.

**API endpoints.**
- `POST /fee/concessions/bulk`: `{student_id, academic_year_id, concessions:[{fee_type_id, concession_amount, reason, approved_by}]}`; 201 list of `FeeConcessionRead` (`id`, `student_id`, `fee_type_id`, `fee_type_name`, `assigned_fee`, `concession_amount`, `reason`, `approved_by`, `is_active`, `created_at`).
- `GET /fee/concessions/student/{student_id}?academic_year_id=` returns `ConcessionSummaryResponse` (`items[{fee_type_id, fee_type_name, assigned_fee, concession_amount, due_amount, due_date, is_settled, reason, approved_by}]`, `grand_total_assigned`, `grand_total_concession`, `grand_total_fee_after_concession`).
- `GET /fee/concessions/history/{student_id}?academic_year_id=` returns `[{id, date_applied, fee_type_name, amount, reason, approver, recorded_by_staff_name}]` newest first, including revoked rows.
- `GET /fee/concessions/{id}`; `PUT /fee/concessions/{id}` with `concession_amount`, `reason`, `approved_by` (all optional); `DELETE /fee/concessions/{id}` returns `{detail: "Concession revoked", concession_id}`.

**Rules and validations.**
- `concession_amount > 0` with at most 2 decimals and 10 digits; `reason` 5 to 500 characters; at least one concession in the list (422 otherwise). `approved_by` must be `owner`, `principal`, `management` or `correspondent`: 400 `Invalid approver '<value>'. Must be one of: ...` (checked after the mapping lookup).
- A student mapping must exist: 404 `Fee mapping not found for fee_type_id=<id>`.
- Bulk is cumulative: the new amount is added to the existing active amount (W9). The total may not exceed the mapping `total_fee`: 400 `Concession amount <total> (previous <p> + new <n>) exceeds assigned fee <total_fee> for fee_type_id=<id>`. A total equal to `total_fee` is allowed (payable 0).
- A revoked row is reactivated by the next bulk call: amount reset to 0.00, `assigned_fee` refreshed from the mapping, then the new amount added.
- The backend does not compare the concession with what is already paid; the web caps new entries at the row's Due Amount. A backend-accepted concession larger than the remaining due only produces a due of 0 (W3).
- `PUT` replaces the amount (not cumulative) and fails when it exceeds the stored `assigned_fee`: 400 `Concession amount cannot exceed assigned fee <assigned_fee>`. It works on revoked rows without reactivating them. An invalid approver gives 400 `Invalid approver '<value>'`.
- `DELETE` is a soft revoke (`is_active=false`), repeatable without error. The concession amount is never applied to term amounts.
- Bulk fails as a whole when one row fails: nothing is committed.
- Audit rows are attempted through `_write_audit_log` into a table that does not exist, so nothing is recorded (Known gaps K10).

**Error and edge cases.** Summary for an unknown student: 404 `Student not found`; unknown year returns an empty `academic_year`. `recorded_by_staff_name` and `recorded_by_user_name` are always null. A concession on a fee type paid in full is allowed by the backend.

**Unit-testable logic.** Cumulative addition and cap (`create_bulk_concessions`), reactivation reset, summary arithmetic (`fee_after_concession`, `due_amount`, `is_settled`, grand totals without clamp), `FeeConcessionItemCreate` validators.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-07-U01 | `FeeConcessionItemCreate` with amount 0, -1 and 10.001 | ValidationError for each (gt 0, 2 decimals) | passing |
| TC-FEE-07-U02 | Reason lengths 4, 5, 500, 501 | 4 and 501 rejected; 5 and 500 accepted | passing |
| TC-FEE-07-U03 | `FeeConcessionBulkCreate` with an empty `concessions` list | ValidationError (min length 1) | passing |
| TC-FEE-07-U04 | Cumulative rule W9 with fake mapping 3000: +1000, +1500 | Totals 1000 then 2500 | passing |
| TC-FEE-07-U05 | Cumulative rule W9 third call +600 | 400 message with `3100.00 (previous 2500.00 + new 600) exceeds assigned fee 3000.00` | passing |
| TC-FEE-07-U06 | New amount equal to the remaining room (2500 + 500 on 3000) | Accepted; total 3000.00 | passing |
| TC-FEE-07-U07 | Reactivation of a revoked row with new amount 500 | `is_active` true, amount 500.00 (reset to 0 then +500), `assigned_fee` equals the current mapping total | passing |
| TC-FEE-07-U08 | Summary arithmetic: assigned 3000, concession 1000, paid 2500 | `due_amount` 0, `is_settled` true; grand totals: assigned 3000, concession 1000, after concession 2000 | passing |
| TC-FEE-07-U09 | Summary with Tuition (assigned 12000, concession 2000) and Lab (assigned 1000, concession 1000) | `grand_total_assigned` 13000, `grand_total_concession` 3000, `grand_total_fee_after_concession` 10000 (assigned minus concession, no per-row clamp) | passing |
| TC-FEE-07-U10 | Approver validation with `Owner`, `owner`, `trustee` | Only the lowercase four are valid; others 400 | passing |
| TC-FEE-07-A01 | Admin `POST /bulk` Tuition 2000, reason "Sibling discount", `principal` | 201; `assigned_fee` "12000.00", `concession_amount` "2000.00", `is_active` true | passing |
| TC-FEE-07-A02 | After A01, Fee Summary (F09) | `fee_after_concession` "10000.00"; due reduced by 2000 | passing |
| TC-FEE-07-A03 | Second bulk +1000 for the same fee type | Same row; `concession_amount` "3000.00" | passing |
| TC-FEE-07-A04 | Bulk that pushes the total above 12000 | 400 `Concession amount ... exceeds assigned fee 12000.00 for fee_type_id=...`; amount unchanged | passing |
| TC-FEE-07-A05 | Bulk with amount equal to the full fee 12000 on a fresh mapping | 201; summary payable "0.00" | passing |
| TC-FEE-07-A06 | Bulk with an unmapped fee type | 404 `Fee mapping not found for fee_type_id=...` | passing |
| TC-FEE-07-A07 | Bulk with `approved_by="trustee"` | 400 `Invalid approver 'trustee'. Must be one of: ...` | passing |
| TC-FEE-07-A08 | Bulk with reason "abcd" | 422 | passing |
| TC-FEE-07-A09 | Bulk with two rows where the second is invalid | Whole request fails; the first row is not stored | passing |
| TC-FEE-07-A10 | Bulk with `concession_amount` 100.555 | 422 | passing |
| TC-FEE-07-A11 | `GET /student/{id}?academic_year_id=Y1` after A03 | `items` carry `concession_amount`, `due_amount`, `due_date` equal to the latest term date, `is_settled` false; grand totals consistent | passing |
| TC-FEE-07-A12 | `GET /student/{id}` without `academic_year_id` | 422 | passing |
| TC-FEE-07-A13 | `GET /student/{unknown}` | 404 `Student not found` | passing |
| TC-FEE-07-A14 | `GET /history/{id}?academic_year_id=Y1` | Newest first; one row per concession record including revoked ones | passing |
| TC-FEE-07-A15 | `GET /{id}` existing and unknown | 200 with `fee_type_name`; unknown 404 `Concession not found` | passing |
| TC-FEE-07-A16 | `PUT /{id}` amount 1500 (replace) | 200; amount "1500.00" (not added to the previous value) | passing |
| TC-FEE-07-A17 | `PUT /{id}` amount above the stored `assigned_fee` | 400 `Concession amount cannot exceed assigned fee 12000.00` | passing |
| TC-FEE-07-A18 | `PUT /{id}` reason and approver only | 200; `concession_amount` unchanged at 2000.00; `reason` and `approved_by` updated; a `PUT` with `approved_by` alone is 400 | passing |
| TC-FEE-07-A19 | `DELETE /{id}` | 200 `{detail: "Concession revoked", concession_id}`; `is_active` false; summary concession 0; due restored | passing |
| TC-FEE-07-A20 | `DELETE` twice | Both 200 | passing |
| TC-FEE-07-A21 | After revoke, bulk +500 | Reactivated row; amount "500.00" (not previous plus 500) | passing |
| TC-FEE-07-A22 | Pay a fee type after a concession (F10) | Payment limit equals payable minus paid, not assigned minus paid | passing |
| TC-FEE-07-A23 | Role matrix: bulk (create), put (update), delete | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-07-A24 | Role matrix: summary, history, single (read) | Admin 200; others 403 | passing |
| TC-FEE-07-A25 | Parent token on a linked child's summary | 403 (no `fee_concessions` grant; only `fee_collection:read_related` exists) | passing |
| TC-FEE-07-A26 | No token; cross-tenant header; tenant B cannot read tenant A concession by id | 401; 403; 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-07-E01 | P1 | Web | Admin | Seeded student Kavya Verma (006): Tuition Fee 27,000.00, no concession | 1. Open Fee > Fee Collection, search "006", open Kavya Verma.<br>2. Choose "Concessions".<br>3. On Tuition Fee enter Concession Amt 2000, Reason "QA sibling discount", Approved By "Principal".<br>4. Click "Save All Concessions". | Toast "Concessions saved successfully"; Fee Summary Payable Amount 25,000.00 for Tuition Fee | known defect: UI-FEE-03: after "Save All Concessions" the Fee Summary tab keeps the old Payable Amount 27,000.00 until the p... |
| TC-FEE-07-E02 | P3 | Web | Admin | Kavya Verma open on Concessions | 1. Enter Concession Amt 99999 on Activity Fee (due 2,000.00). | Toast `Concession for Activity Fee cannot exceed the due amount of ...2,000.00.`; input reset to the due | planned |
| TC-FEE-07-E03 | P3 | Web | Admin | Kavya Verma open on Concessions | 1. Enter 100 on Books and Stationery, leave Reason empty.<br>2. Click "Save All Concessions". | Toast `Enter a concession amount, a reason (min 5 characters), and select an approver before saving.`; nothing saved | planned |
| TC-FEE-07-E04 | P2 | Web | Admin | Seeded student Ananya Reddy (20260002, NUR-A) with the seeded 2,000.00 Tuition Fee concession | 1. Open Ananya Reddy, "Concessions".<br>2. On Tuition Fee (placeholder "Add more...") enter 500, reason "QA extra discount", approver "Management".<br>3. Click "Save All Concessions". | Concession History gains an entry; Tuition Fee payable drops by a further 500.00 (total concession 2,500.00) | planned |
| TC-FEE-07-E05 | P2 | Web | Admin | TC-FEE-07-E01 done | 1. Open "Concession History".<br>2. Click "Edit" on the QA entry.<br>3. Change the amount to 1500 and click "Save". | Toast "Concession updated successfully"; Tuition Fee payable 25,500.00 | planned |
| TC-FEE-07-E06 | P2 | Web | Admin | TC-FEE-07-E01 done | 1. In "Concession History" click "Delete" on the QA entry.<br>2. Click "Revoke" in "Revoke Concession". | Toast "Concession revoked successfully"; Tuition Fee payable back to 27,000.00 | planned |
| TC-FEE-07-E07 | P2 | Web | Staff | Seeded student Kavya Verma | 1. Sign in as Staff.<br>2. Open Kavya Verma, "Concessions". | No editable inputs and no "Save All Concessions" (Staff has no `fee_concessions` grant) | planned |
| TC-FEE-07-E08 | P2 | Mobile | Admin | Seeded student Kavya Verma | 1. Fee Collection, search "006", open Kavya Verma.<br>2. "Concessions": Tuition Fee 1000, approver, reason "QA mobile discount", save.<br>3. Revoke it from the history. | Fee Summary Payable drops by 1,000.00 then returns; Grand Total row shows the concession | planned |

API tests implemented in: backend/tests/api/fee/test_fee_concessions.py

Implemented in: backend/tests/unit/fee/test_fee_concession_rules.py (phase 1 unit cases).

---

## F08 Old fees

**Purpose.** Track dues from earlier years either by carrying forward unpaid current-system fees or by entering them by hand for schools new to the system. Old fees stay on their own tab and are never mixed into this year's per-fee-type dues, but they are included in the total a payment may collect.

**Roles and permissions.** `fee_old:create` (manual entry, carry forward), `list` (student list), `read` (single), `update` (edit paid amount, settle), `delete`. Default seed: Admin only. Web: Fee Collection > student > "Old Fees" tab (UI checks `fee_old` create, update, delete). Mobile has the tab but its API paths are wrong (Known gaps K07).

**Preconditions.** A student with an admission. Carry forward needs fee mappings in the source year.

**Steps, web.**
1. Open the student's "Old Fees" tab (empty text "No old fee records found."). The "Old Fee Records" table has S.No., Academic Year, Fee Type, Source (Manual or Carry Forward), Original, Paid, Outstanding, Settled, Receipt, Actions.
2. "Add Manual Entry" opens "Add Old Fee Entry": "Academic Year Label *" (for example 2024-25), "Fee Type Name *", "Original Amount *", "Paid Amount", "Receipt Number", "Remarks"; button "Add Entry".
3. "Carry Forward" opens "Carry Forward Old Fees": choose "Source Academic Year" ("Select previous year"); the "Target Academic Year" (read-only) shows the selected year; the note reads "This will copy all unpaid fee items from the source year as old fee records in the current year."; button "Carry Forward".
4. Edit (pencil) opens "Edit Old Fee": "Paid Amount", "Paid Date", "Receipt Number", "Remarks", "Save". The "S" button ("Mark as Settled") opens the dialog "Mark as Settled" with "Settle". The trash button (shown only for non-settled manual entries) opens "Delete Old Fee Entry".
5. The Fee Summary tab shows a badge "Old Fee Pending: <amount> - View" that jumps to this tab.

**Steps, mobile.** Collection > student > "Old Fees": buttons "Add Manual Entry" (fields amount and "Description (optional)") and "Carry Forward" ("Source Academic Year", "Select previous year"). The screen calls `/fee/old/...` and sends different field names, so every action fails (K07).

**Expected results.** `fee_old` rows. Summary `old_fee_pending_amount` equals `sum(original - paid)` of unsettled rows (W11).

**API endpoints.** Prefix `/fee/old-fees`.
- `POST /`: `student_id`, `academic_year_label` (max 20), `fee_type_name` (max 100), `original_amount` (> 0), `paid_amount` (>= 0, default 0), `receipt_manual`, `remarks`. 201 `FeeOldRead`.
- `POST /carry-forward`: `{student_id, source_academic_year_id, target_academic_year_id}`; 200 list of created rows (possibly empty).
- `GET /student/{student_id}?current_year_id=` returns `FeeOldSummaryResponse` (`items`, `grand_total_original`, `grand_total_paid`, `grand_total_outstanding`).
- `GET /{id}`; `PUT /{id}` (`paid_amount`, `paid_date`, `receipt_manual`, `remarks`); `PATCH /{id}/settle` returns `{detail: "Old fee marked as settled", old_fee_id}`; `DELETE /{id}` returns `{detail: "Old fee record deleted", old_fee_id}`.

**Rules and validations.**
- Manual entry: the student must have an admission (404 `Student admission not found`); the same (student, `academic_year_label`, `fee_type_name`) twice gives 400 `Old fee record for <label> / <name> already exists for this student`; `paid_amount > original_amount` is 422 (`paid_amount cannot exceed original_amount`); `is_settled` is true when paid is at least original. `source` is `manual_entry`.
- Carry forward: once per (student, source year): a second run gives 400 `Old fees already carried forward for this student and source academic year` (only when rows were created before). For each source-year mapping it creates a row with `original_amount = total_fee - paid` (paid is completed items only; concessions ignored) when that is greater than 0, `source = auto_carryforward`, `current_academic_year_id = target`. Nothing outstanding returns `[]`.
- Edit: `paid_amount > original_amount` gives 400 `paid_amount cannot exceed original_amount`; `is_settled` is recomputed from the new paid amount (so lowering the paid amount re-opens a settled row); other fields only update when sent.
- Settle sets `is_settled = true` and nothing else: `paid_amount` is unchanged and the row's `outstanding` field still shows `original - paid`; the summary and payment exclude settled rows.
- Delete only works for `manual_entry` rows (settled or not): 400 `Only manually entered old fees can be deleted. Auto carry-forward records cannot be deleted.`
- `outstanding = max(original - paid, 0)`.
- The web list passes `current_year_id`, which filters on `current_academic_year_id`; manual entries have that column null, so the web tab does not show them (Known gaps K08).
- Old fees are only reduced by `/fee/collection/pay` without `fee_items` (F10); the clients always send `fee_items`, so they record old fee payments by editing `paid_amount`.

**Error and edge cases.** Unknown ids give 404 `Old fee record not found`; list for an unknown student gives 404 `Student not found`. A negative paid amount is 422. Carry forward with the same source and target year is not rejected.

**Unit-testable logic.** `_to_read` outstanding clamp; carry-forward arithmetic (`total_fee - paid`, skip zero or negative); auto-settle; `FeeOldManualCreate` validators; delete-source rule.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-08-U01 | `_to_read` original 1500, paid 600 | outstanding "900.00" | passing |
| TC-FEE-08-U02 | `_to_read` original 1500, paid 1500 and paid 1600 (legacy bad data) | outstanding 0.00 in both (clamped) | passing |
| TC-FEE-08-U03 | `FeeOldManualCreate` with `paid_amount` 1600 over `original_amount` 1500 | ValidationError `paid_amount cannot exceed original_amount` | passing |
| TC-FEE-08-U04 | `FeeOldManualCreate` with `original_amount` 0 | ValidationError (gt 0) | passing |
| TC-FEE-08-U05 | `FeeOldManualCreate` with a 21 character label | ValidationError (max 20) | passing |
| TC-FEE-08-U06 | Carry-forward arithmetic: mapping 12000, completed paid 9000 | Row original 3000.00 | passing |
| TC-FEE-08-U07 | Carry-forward arithmetic: mapping 12000, paid 12000 | No row | passing |
| TC-FEE-08-U08 | Carry-forward arithmetic with a concession 2000 and paid 9000 | Row original 3000.00 (concession ignored; documents K09) | passing (asserts current behaviour, defect K09) |
| TC-FEE-08-U09 | `update_old_fee` paid 1500 on original 1500, then paid 1000 | settled true, then settled false | passing |
| TC-FEE-08-U10 | `delete_old_fee` on `auto_carryforward` | 400 with the manual-only message | passing |
| TC-FEE-08-A01 | Admin `POST /fee/old-fees/` label "2024-25", "Tuition Fee", original 1500, paid 600 | 201; `outstanding` "900.00"; `is_settled` false; `source` manual_entry | passing |
| TC-FEE-08-A02 | POST with paid equal to original | 201; `is_settled` true | passing |
| TC-FEE-08-A03 | POST the same student, label and fee type again | 400 `Old fee record for 2024-25 / Tuition Fee already exists for this student` | passing |
| TC-FEE-08-A04 | POST for a student without an admission | 404 `Student admission not found` | passing |
| TC-FEE-08-A05 | POST paid above original | 422 | passing |
| TC-FEE-08-A06 | `POST /carry-forward` for a student with Tuition 12000 paid 9000 and Lab 1000 paid 1000 in source year | 200; one row (Tuition, "3000.00", `auto_carryforward`) | passing |
| TC-FEE-08-A07 | Repeat the carry forward | 400 `Old fees already carried forward for this student and source academic year` | passing |
| TC-FEE-08-A08 | Carry forward for a student with everything paid | 200 `[]`; a later retry is not blocked | passing |
| TC-FEE-08-A09 | `GET /student/{id}` with and without `current_year_id` | Without the filter all rows; with the filter only rows whose `current_academic_year_id` matches (manual rows excluded); ordered by label descending; grand totals sum the rows | passing |
| TC-FEE-08-A10 | `GET /student/{unknown}` | 404 `Student not found` | passing |
| TC-FEE-08-A11 | `GET /{id}` existing and unknown | 200; 404 `Old fee record not found` | passing |
| TC-FEE-08-A12 | `PUT /{id}` `paid_amount` 1500 on original 1500 with `paid_date` | `is_settled` true; `paid_date` stored | passing |
| TC-FEE-08-A13 | `PUT /{id}` paid above original | 400 `paid_amount cannot exceed original_amount` | passing |
| TC-FEE-08-A14 | `PUT /{id}` only `remarks` | Other fields unchanged | passing |
| TC-FEE-08-A15 | `PATCH /{id}/settle` on a row with paid 600 of 1500 | 200; `is_settled` true; row `outstanding` still "900.00"; student summary `old_fee_pending_amount` no longer includes it | passing |
| TC-FEE-08-A16 | `DELETE /{id}` manual row; carry-forward row | 200; 400 manual-only message | passing |
| TC-FEE-08-A17 | Student summary `old_fee_pending_amount` with two unsettled rows (900 and 400) and one settled row | "1300.00" | passing |
| TC-FEE-08-A18 | Payment above this-year due but within this-year plus old fee, no `fee_items` (F10) | Remainder reduces old fees ordered by label then fee type name; `paid_date` today; `receipt_system` set | passing |
| TC-FEE-08-A19 | Role matrix create, carry-forward, put, settle, delete | Admin 2xx; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-08-A20 | Role matrix list and read | Admin 200; others 403 | passing |
| TC-FEE-08-A21 | No token; cross-tenant header; tenant B cannot read tenant A old fee | 401; 403; 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-08-E01 | P1 | Web | Admin | Seeded student Kavya Verma has no old fee records | 1. Open Kavya Verma, "Old Fees".<br>2. Click "Add Manual Entry".<br>3. Enter Academic Year Label "2024-25", Fee Type Name "QA Old Tuition", Original Amount 1500, Paid Amount 600.<br>4. Click "Add Entry". | Toast "Old fee entry added successfully"; Fee Summary badge "Old Fee Pending: 900.00 - View"; the row is missing from the tab (K08) | blocked: K08 (manual entries are filtered out of the web Old Fees tab) |
| TC-FEE-08-E02 | P3 | Web | Admin | A student with fee mappings in an earlier academic year (none in the seed) | 1. Open the student, "Old Fees".<br>2. Click "Carry Forward".<br>3. Choose the "Source Academic Year".<br>4. Click "Carry Forward". | Rows with Source "Carry Forward"; the Old Fee Pending badge increases | blocked: no seeded data in an earlier academic year |
| TC-FEE-08-E03 | P2 | Web | Admin | TC-FEE-08-E01 done and the row visible | 1. Click Edit on the row.<br>2. Set Paid Amount 1500.<br>3. Click "Save". | Toast "Old fee updated successfully"; Settled on; Outstanding 0.00 | blocked: K08 |
| TC-FEE-08-E04 | P2 | Web | Admin | TC-FEE-08-E01 done and the row visible | 1. Click "Mark as Settled".<br>2. Click "Settle". | Toast "Old fee marked as settled"; Settled on; the Old Fee Pending badge drops | blocked: K08 |
| TC-FEE-08-E05 | P2 | Web | Admin | TC-FEE-08-E01 done and the row visible | 1. Click the delete icon.<br>2. Confirm in "Delete Old Fee Entry". | Toast "Old fee entry deleted"; row removed | blocked: K08 |
| TC-FEE-08-E06 | P3 | Web | Admin | TC-FEE-08-E01 done | 1. "Add Manual Entry" again with "2024-25" and "QA Old Tuition".<br>2. Click "Add Entry". | Error toast `Old fee record for 2024-25 / QA Old Tuition already exists for this student` | planned |
| TC-FEE-08-E07 | P3 | Web | Staff | Seeded student Kavya Verma | 1. Sign in as Staff.<br>2. Open Kavya Verma, "Old Fees". | No "Add Manual Entry" or "Carry Forward" buttons | planned |
| TC-FEE-08-E08 | P3 | Mobile | Admin | Seeded student Kavya Verma | 1. Open Kavya Verma, "Old Fees".<br>2. Tap "Add Manual Entry", enter an amount, save. | Entry saved and listed | blocked: K07 (mobile calls /fee/old/... and wrong field names) |

API tests implemented in: backend/tests/api/fee/test_fee_old_fees.py

Implemented in: backend/tests/unit/fee/test_fee_old_rules.py (phase 1 unit cases).

---

## F09 Student search, fee summary, terms due and fee history

**Purpose.** Let staff find a student and see exactly what the student was assigned, what was conceded, what was paid and what is still due, with the installment schedule and payment history.

**Roles and permissions.** `fee_collection:list` (search), `fee_collection:read` (summary, terms due, history). Default seed: Admin only (QA grants may add Staff). Web: Fee > Fee Collection (`/fee/collection`, then `/fee/collection/<studentId>`). Mobile: Fee hub tile "Fee Collection" (`/fees/collection`, then `/fees/collection/<studentId>`). Student and parent roles that open the same URL get their own self-service page (F16).

**Preconditions.** Student with admission (class, section) and student fee mappings (F06) for the year.

**Steps, web.**
1. Open Fee > Fee Collection (title "Fee Collection", subtitle "Search students and manage fee payments").
2. Type in "Search by name, admission no, mobile, city..." and optionally pick "Class" and "Section"; click "Search" (disabled until a filter is set) or press Enter; "Clear" resets. Results: S.No., Student, Admission No., Class-Section ("<class>-<section>"), Parent (all linked parents, comma separated); 5 rows per page with Previous and Next and "Rows per page".
3. Click a row. The page shows "Manage fee for <name>", the admission badge, a close button "Go back" and the tabs "Fee Summary", "Fee Payment", "Concessions", "Old Fees", "Fee History" (bottom navigation on narrow screens).
4. "Fee Summary" shows the card "Fee Summary" with "As of <YYYY-MM-DD> - AY: <year>" and a "Send SMS" button (F14), the table (S.No., Fee Type, Actual Amount, Payable Amount, Paid, Due, Last Paid, Receipt #, Remarks) with a "Grand Total" row, mandatory fees sorted first, the badge "Old Fee Pending: <amount> - View" and the collapsible "Term-wise Installment Schedule", open by default (Inst No., Fee Type, Pay Term, Inst Amount, Paid Amount, Due Date, Due Amount, Status Paid or Pending; per-type totals). The schedule applies a concession first-in-first-out to the earliest installments for display only. The summary request carries no as-of date, so the server uses today.
5. "Fee History" ("Fee Payment History") lists S.No., Date, Receipt No, Amount Paid, Payment Method, Fee Types Paid and a download icon "Download Receipt PDF"; total row "Total Paid". Empty text "No payment records found for this academic year."

**Steps, mobile.** Fee Collection screen ("Search students and manage fee payments"): "Search by name, admission no, mobile...", "All Classes", "All Sections", "Search", "Clear"; empty hint "Search and select a student to view their fee details"; a result row opens the detail screen (student name, admission number, class and section) with the same five tabs. Fee Summary shows "As of <date> - AY: <year>", per fee type Actual, Payable, Paid and Due, a "Grand Total" row and "Term-wise Installment Schedule"; Fee History's empty text is "No payment records found for this academic year."

**Expected results.** Read-only views. No data changes.

**API endpoints.** Prefix `/fee/collection`.
- `GET /search-student?q=&class_id=&section_id=`: `q` at least 2 characters. Up to 20 rows `{student_id, admission_number, first_name, last_name, class_id, class_name, section_id, section_name, parent_name, mobile_number, photo_url}`.
- `GET /summary/{student_id}?academic_year_id=&as_of_date=`: `FeeSummaryResponse` (`items[{s_no, fee_type_id, fee_type_name, assigned_fee, fee_after_concession, paid_amount, due_amount, last_paid_date, last_receipt_number, remarks}]`, `grand_total_assigned`, `grand_total_fee`, `grand_total_paid`, `grand_total_due`, `old_fee_pending_amount`).
- `GET /terms-due/{student_id}?academic_year_id=&as_of_date=` (`as_of_date` required): `current_month_terms`, `overdue_terms` (items with `due_date`, `term_amount`, `paid_amount`, `pending_amount`), `total_current_month_pending`, `total_overdue_pending`, `grand_total_pending`, `selected_month` (for example "September 2026").
- `GET /history/{student_id}?academic_year_id=`: completed transactions newest first with `receipt_id`, `receipt_number`, `fee_types_paid[{fee_type_id, fee_type_name, amount_paid}]`, `total_paid`.

**Rules and validations.**
- Search: with no `q`, class or section the call returns 400 `At least one search parameter is required`; `q` shorter than 2 characters is 422. `q` is matched with `ILIKE %q%` (OR) on admission number, parent phone, first name, last name, "first last", city, address line 1 and 2; class and section are AND filters. `%` and `_` in `q` act as wildcards. Parents are aggregated per student (`string_agg distinct`).
- Summary calculations follow the calculation reference: payable, paid (completed only, `transaction_date <=` end of the as-of day), due clamped at 0, grand totals, old fee pending (all years, unsettled). Assigned and concession values are not date-filtered; the as-of date only limits payments (W1, W2, W3).
- `last_paid_date` and `last_receipt_number` come from the latest completed transaction with an item of that fee type up to the as-of date.
- A student with no fee mappings returns an empty `items` list with zero totals. Unknown student: 404 `Student not found`; no admission: 404 `Admission not found for student`. A student with more than one admission row makes `scalar_one_or_none` raise and returns 500.
- Terms due follow W8: only term amounts due on or before the as-of date, pending after completed payments by term date, concessions ignored.
- History shows only `completed` transactions; `receipt_id` and `receipt_number` are null when no receipt exists.
- `academic_year_id` is required on every endpoint here (422 when missing).

**Error and edge cases.** Refunds never reduce Paid. A completed transaction dated after the as-of date is excluded from Paid and from last-paid fields. Old fee pending is the same value regardless of the year selected.

**Unit-testable logic.** Summary per-fee-type arithmetic and grand totals; as-of boundary (`datetime.combine(as_of, max time)`); terms-due classification into current month and overdue; search query builder (OR across columns, AND for class and section, limit 20); history ordering and totals.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-09-U01 | Summary arithmetic W1 (12000, none, 0) | assigned 12000, payable 12000, paid 0, due 12000 | passing |
| TC-FEE-09-U02 | Summary arithmetic W2 (12000, concession 2000, paid 4000) | payable 10000, due 6000 | passing |
| TC-FEE-09-U03 | Summary arithmetic W3 (3000, concession 1000, paid 2500) | payable 2000, due 0 (clamped) | passing |
| TC-FEE-09-U04 | Concession larger than assigned (3500 on 3000, legacy data) | payable 0, due 0 | passing |
| TC-FEE-09-U05 | Grand totals for Tuition (12000/10000/4000/6000) plus Lab (1000/1000/0/1000) | assigned 13000, fee 11000, paid 4000, due 7000 | passing |
| TC-FEE-09-U06 | As-of boundary: payment at 2026-09-15 23:59:59 with as-of 2026-09-15 and another at 2026-09-16 00:00:00 | First counted, second excluded | passing (asserts the bound end-of-day parameter) |
| TC-FEE-09-U07 | Only `completed` transactions counted: pending 1000, bounced 500, cancelled 300, completed 200 | paid 200 | passing (asserts the completed filter parameter; the SUM runs in SQL) |
| TC-FEE-09-U08 | Terms due W8 (term 3000 each, term 1 paid 3000, as-of 2026-09-15) | `current_month_terms` 1 item pending 3000; `overdue_terms` empty; total 3000 | passing |
| TC-FEE-09-U09 | Terms due with term 1 paid only 1000, as-of 2026-09-15 | Term 06-10 appears in `overdue_terms` with pending 2000; term 09-10 current 3000; grand 5000 | passing |
| TC-FEE-09-U10 | Terms due with as-of 2026-06-10 (equal to the first due date) | Term 06-10 included in `current_month_terms` | passing |
| TC-FEE-09-U11 | Terms due ignores a 2000 concession | Pending amounts unchanged | passing |
| TC-FEE-09-U12 | `selected_month` for 2026-09-15 | "September 2026" | passing |
| TC-FEE-09-U13 | Search builder with `q="ra"`, class set, section unset | OR group on 8 columns AND class filter; limit 20 | passing |
| TC-FEE-09-U14 | Search with no parameters | Raises 400 `At least one search parameter is required` | passing |
| TC-FEE-09-U15 | Old fee pending: unsettled 900 and 400, settled 500 | 1300.00 | passing (asserts the query shape and passthrough; the SUM runs in SQL) |
| TC-FEE-09-A01 | Admin `GET /search-student?q=<admission number>` | One student row with parent name and mobile aggregated | passing |
| TC-FEE-09-A02 | Search by first name fragment, mobile fragment, city, address fragment (four calls) | Each returns the student | passing |
| TC-FEE-09-A03 | Search with `class_id` and `section_id` only | Students of that section, at most 20 | passing |
| TC-FEE-09-A04 | Search with `q=a` | 422 (min length 2) | passing |
| TC-FEE-09-A05 | Search with no parameters | 400 `At least one search parameter is required` | passing |
| TC-FEE-09-A06 | `GET /summary/{id}?academic_year_id=Y1` for the W2 fixture | Items and totals per W2; decimals as strings | passing |
| TC-FEE-09-A07 | Summary with `as_of_date` before the payment date | `paid_amount` 0 and `last_paid_date` null | passing |
| TC-FEE-09-A08 | Summary without `academic_year_id` | 422 | passing |
| TC-FEE-09-A09 | Summary for an unknown student; for a student with no admission | 404 `Student not found`; 404 `Admission not found for student` | passing |
| TC-FEE-09-A10 | Summary for a student with no mappings | 200, empty items, totals "0.00" | passing |
| TC-FEE-09-A11 | Summary `old_fee_pending_amount` with an unsettled old fee of 900 | "900.00" | passing |
| TC-FEE-09-A12 | `GET /terms-due/{id}?academic_year_id&as_of_date=2026-09-15` for W8 | Lists per W8; `selected_month` "September 2026" | passing |
| TC-FEE-09-A13 | Terms due without `as_of_date` | 422 | passing |
| TC-FEE-09-A14 | Terms due for a student with a pending (uncleared) cheque payment | Pending cheque not counted as paid | passing |
| TC-FEE-09-A15 | `GET /history/{id}?academic_year_id=Y1` with two completed and one pending cheque transaction | Two items newest first; `total_paid` equals their sum; pending excluded | passing |
| TC-FEE-09-A16 | History item for a completed transaction without a receipt row | `receipt_id` and `receipt_number` null | passing |
| TC-FEE-09-A17 | Role matrix on search (list) and summary, terms-due, history (read) | Admin 200; Staff, Teacher, Student, Parent 403 with the default seed | passing |
| TC-FEE-09-A18 | Parent token calls `GET /summary/{child}` | 403 (needs `fee_collection:read`, which Parent only holds as `read_related`) | passing |
| TC-FEE-09-A19 | Tenant isolation: tenant A student id queried with tenant B token | 404 `Student not found` | passing |
| TC-FEE-09-A20 | No token | 401 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-09-E01 | P1 | Web | Admin | Seeded student Karthik Reddy (001, Class 3 / 3-B) | 1. Open Fee > Fee Collection.<br>2. Type "001" in "Search by name, admission no, mobile, city..." and press Enter.<br>3. Click the Karthik Reddy row (the search lists it beyond page 1 and the list shows 5 rows per page, so page forward). | "Manage fee for Karthik Reddy", admission badge 001, tabs "Fee Summary", "Fee Payment", "Concessions", "Old Fees", "Fee History" | passing |
| TC-FEE-09-E02 | P3 | Web | Admin | None | 1. Open Fee > Fee Collection with all filters empty.<br>2. Choose a Class. | "Search" disabled while all filters are empty; enabled after a class is chosen | planned |
| TC-FEE-09-E03 | P3 | Web | Admin | None | 1. Search "zzzqqq". | Text "No students found. Try adjusting your search criteria." | planned |
| TC-FEE-09-E04 | P1 | Web | Admin | Seeded student Ananya Reddy (20260002): Tuition Fee 18,000 with 2,000 concession and 6,000 paid | 1. Open Ananya Reddy from Fee Collection.<br>2. Read the "Fee Summary" table. | Tuition Fee: Actual Amount 18,000.00, Payable Amount 16,000.00, Paid 6,000.00, Due 10,000.00; "As of <today> - AY: 2026-2027"; Grand Total row equals the sum of rows | passing |
| TC-FEE-09-E05 | P2 | Web | Admin | As TC-FEE-09-E04 | 1. Read "Term-wise Installment Schedule" (open by default). | Tuition Fee rows for 15 Jun 2026, 15 Oct 2026, 15 Jan 2027; the 2,000.00 concession is taken from the earliest instalments' Due Amount; Status Paid or Pending | planned |
| TC-FEE-09-E06 | P3 | Web | Admin | TC-FEE-08-E01 done for Kavya Verma | 1. Open Kavya Verma, "Fee Summary".<br>2. Click "View" on the "Old Fee Pending" badge. | Badge shows 900.00; click opens the "Old Fees" tab | planned |
| TC-FEE-09-E07 | P2 | Web | Admin | Seeded student Karthik Reddy with seeded completed payments | 1. Open Karthik Reddy, "Fee History".<br>2. Click "Download Receipt PDF" on a row. | Rows with Date, Receipt No (REC-2610-...), Amount Paid, Payment Method, Fee Types Paid; "Total Paid"; toast "Receipt downloaded" and a PDF file | planned |
| TC-FEE-09-E08 | P3 | Web | Admin | Seeded student Kavya Verma (no payments) | 1. Open Kavya Verma, "Fee History". | "No payment records found for this academic year." | planned |
| TC-FEE-09-E09 | P2 | Mobile | Admin | As TC-FEE-09-E04 | 1. Open the Fee Management card, then "Fee Collection".<br>2. Search "20260002", tap Search, open Ananya Reddy.<br>3. Read "Fee Summary". | Same figures as TC-FEE-09-E04 (Actual 18,000.00, Payable 16,000.00, Paid 6,000.00, Due 10,000.00) | planned |

API tests implemented in: backend/tests/api/fee/test_fee_collection_summary.py

Implemented in: backend/tests/unit/fee/test_fee_summary_rules.py (phase 1 unit cases).

---

## F10 Fee payment (collection)

**Purpose.** Record a payment against a student's fees. One call creates the transaction and its term-level items, issues a receipt (when the payment is completed) and optionally sends a parent SMS.

**Roles and permissions.** API: `fee_collection:create` (`POST /fee/collection/pay`). Web UI gate: `fee_transactions:create` (the Payment tab disables inputs without it); the two grants differ, so a user can pass the UI gate and still get a 403 from the API. Default seed: Admin only for the API call. Menu: Fee > Fee Collection > student > "Fee Payment" tab (web) and the same tab on mobile. A default Staff user can open the student page but the Fee Summary shows `Permission not found in database: Staff cannot read fee_collection. Contact administrator to configure permissions.` and the Payment tab stays at "Loading installments..." (K23).

**Preconditions.** The student has fee mappings with term amounts (F06) and an outstanding balance; for SMS, a parent with a phone number.

**Steps, web.**
1. Open the student's "Fee Payment" tab. The card "Total Due Amount" shows the summary's `grand_total_due`.
2. Choose "Payment Up To" ("Select installment...", one option per due date, labelled "<term name> (<d Mon yyyy>)", for example "Three Terms (15 Oct 2026)"); until then "Fee Heads" reads `Select a "Payment Up To" date above to see fee heads.` The table "Fees Due Up To <date>" lists each fee type with pending installments up to that date, reduced by the fee type's concession (S.No., Particulars, Actual Amount, Received Amount).
3. Type the "Received Amount" per fee type (blank by default; the input is limited to the row amount and a larger value toasts `Amount should not exceed <amount> for <fee type>` and is clamped). "Collect Payment" stays disabled until the total received is above 0.
4. In the card "Collect Payment": "Receipt Number *" (provisional, for example `RCP-260616-0930`, sent but ignored by the server), "Payment Method *" (Cash, UPI, Cheque, Bank Transfer, Demand Draft), then the method fields: UPI shows "UPI Reference *" (max 30); Cheque shows "Cheque Number *", "Bank Name *", "Cheque Date *"; Demand Draft shows "DD Number *", "Bank Name *", "DD Date *" (date input limited to today plus 90 days); Bank Transfer shows "Bank Reference *" (max 30). Optional "Remarks"; switches "Send SMS" (on by default) and "Print Duplicate" (off).
5. Click "Collect Payment", confirm "Confirm Payment" ("Collect <amount> from <student> via <method>?") with "Confirm".
6. The dialog "Payment Recorded" shows Transaction #, Receipt #, Amount Paid, Payment Method, SMS Status and the "Items Paid" table; buttons "Send Receipt SMS", "Download Receipt", "Close". For cheque or DD the dialog instead shows `Cheque/DD pending clearance - receipt will be generated once the instrument clears.` and no receipt. Closing returns to "Fee Summary".

**Steps, mobile.** Same flow in the "Fee Payment" tab: "Total Due Amount", "Payment Up To", per fee type "Received" amounts, "Receipt Number *", "Payment Method *" (Cash, UPI, Cheque, Bank Transfer, Demand Draft), "UPI Reference / Transaction ID", "Bank Reference / UTR Number", "Cheque / DD Number *", "Bank Name *", "Cheque / DD Date * (YYYY-MM-DD)", "Remarks (optional)", "Send SMS", "Print Duplicate"; success modal "Payment Recorded" with "Download Receipt" and "Done".

**Expected results.** A `fee_transactions` row (`TXN` number, `completed` for cash, UPI, bank transfer and card; `pending` with `cheque_status = pending` for cheque and DD), items per (fee type, term date), and for completed payments a `fee_receipts` row (number `REC-YYMM-NNNN`, content hash) with `receipt_generated = true`. The summary and the history change only for completed payments.

**API endpoints.** `POST /fee/collection/pay`. Body: `student_id`, `academic_year_id`, `amount_to_pay` (> 0, 10 digits, 2 decimals), `fee_items[{fee_type_id, amount}]` (optional), `payment_method` (`cash`, `cheque`, `bank_transfer`, `upi`, `dd`, `card`), `upi_reference` (max 30), `bank_reference` (max 30), `cheque_number` (max 20), `cheque_bank` (max 100), `cheque_date`, `send_sms` (true), `print_duplicate` (false), `remarks`. Response: `transaction_id`, `transaction_number`, `receipt_id`, `receipt_number`, `amount_paid`, `payment_method`, `sms_status` (`sent`, `failed`, `skipped`), `items_paid[{fee_type_id, fee_type_name, amount_paid}]`.

**Rules and validations.**
- Schema (422): `amount_to_pay > 0` with at most 2 decimals; `fee_items` must not be an empty list, must not repeat a fee type, and must sum exactly to `amount_to_pay`; UPI needs `upi_reference`; bank transfer needs `bank_reference`; cheque and DD need `cheque_number`, `cheque_bank` and `cheque_date`; any `cheque_date` more than 90 days after today is rejected (today plus 90 passes, plus 91 fails; past dates pass); cash and card need nothing.
- Service: no mappings gives 404 `No fee mappings found for this student and academic year`; no admission 404 `Student admission not found`; total due (calculation reference) at most 0 gives 400 `No outstanding dues for this student`; `amount_to_pay` above total due (this-year dues after concession and payments, plus unsettled old fees) gives 400 `Amount <x> exceeds total due <y>`.
- With `fee_items`: a fee type not mapped gives 400 `Fee type <id> is not mapped to this student for this academic year`; a fee type with no outstanding gives 400 `'<name>' has no outstanding due; nothing to pay for this fee type`; an amount above that fee type's outstanding gives 400 `Amount <a> for '<name>' exceeds its outstanding due <o>`; a remainder the term amounts cannot absorb gives 400 `Amount for '<name>' exceeds the scheduled term amounts by <r>; check the term-wise fee setup` (W5). Old fees are never paid in this mode.
- Without `fee_items` (legacy): top-down allocation by `fee_type_id` order, remainder to unsettled old fees (W6, W7); a payment that allocates nothing gives 400 `No outstanding fees to pay`. The transaction total is the sum of allocated items, which can be less than `amount_to_pay` (W6).
- Term allocation walks `mapping.term_amounts` in relationship order (no explicit ORDER BY); with the rows inserted by `create_term_amounts` this is date order, but the order is not guaranteed by a query (K04).
- Cheque and DD: `status=pending`, `cheque_status=pending`, no receipt (`receipt_number` is "" and `receipt_id` repeats `transaction_id` in the response), no SMS (`sms_status` `skipped`); the payment does not reduce due until the status becomes completed (F12). In the legacy mode old fees are updated immediately even for cheques (K11).
- Completed payments: receipt via `generate_receipt_number` and `generate_content_hash`; `print_duplicate=true` stores `is_reprinted=true` and `reprint_count=1`.
- SMS runs after the commit and never affects the payment; `sms_status` is `skipped` when `send_sms` is false, the payment is pending, or no parent phone exists, `failed` when the provider call or lookup fails.
- Any unexpected error returns 500 `Payment failed: <ExceptionType>: <message>`.
- Payments for one student are serialised by a transaction-scoped advisory lock. An optional `idempotency_key` (max 64) makes a repeat return the original transaction, receipt and items without creating a second one; without a key, repeating the request while dues remain creates a second transaction and receipt (K12 fixed).

**Error and edge cases.** Paying exactly the due is allowed (W1: 12000 due, pay 12000, due becomes 0). Paying 0.01 above the due fails. A second identical full payment after the first fails with `No outstanding dues for this student`. A pending cheque of the full due does not block a second payment of the same amount.

**Unit-testable logic.** `FeePaymentRequest` validators (items sum, duplicates, empty list, conditional references, 90-day cheque rule); allocation walk (explicit and legacy); `_compute_total_due`; transaction and receipt number formats; SMS status selection.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-10-U01 | `FeePaymentRequest` with `fee_items` summing 3000 and `amount_to_pay` 3500 | ValidationError `Sum of fee_items (3000.00) must equal amount_to_pay (3500.00)` | passing |
| TC-FEE-10-U02 | `fee_items=[]` | ValidationError `fee_items cannot be an empty list; omit it to auto-distribute` | passing |
| TC-FEE-10-U03 | `fee_items` with the same fee type twice | ValidationError `Duplicate fee_type_id in fee_items: <id>` | passing |
| TC-FEE-10-U04 | `amount_to_pay` 0, -1, 100.005 | ValidationError for each | passing |
| TC-FEE-10-U05 | UPI without `upi_reference` | ValidationError `upi_reference is required when payment_method is 'upi'` | passing |
| TC-FEE-10-U06 | Bank transfer without `bank_reference` | ValidationError `bank_reference is required when payment_method is 'bank_transfer'` | passing |
| TC-FEE-10-U07 | Cheque missing number, bank or date (three cases) | ValidationError naming the missing field | passing |
| TC-FEE-10-U08 | DD with number, bank, date today plus 90 | Valid | passing |
| TC-FEE-10-U09 | Cheque date today plus 91 | ValidationError `cheque_date cannot be more than 90 days in the future` | passing |
| TC-FEE-10-U10 | Cheque date yesterday | Valid (no lower bound) | passing |
| TC-FEE-10-U11 | Cash with `cheque_date` today plus 91 | ValidationError (90-day rule applies to any method) | passing |
| TC-FEE-10-U12 | Cash and card with no references | Valid | passing |
| TC-FEE-10-U13 | `upi_reference` of 31 characters | ValidationError (max 30) | passing |
| TC-FEE-10-U14 | `_compute_total_due` with the W2 Tuition fixture plus the W3 Lab fixture | Tuition 6000 + Lab 0 = 6000 | passing |
| TC-FEE-10-U15 | Explicit allocation: Tuition 12000 over four 3000 terms, request 4000 | Items: term1 3000, term2 1000 | passing |
| TC-FEE-10-U16 | Explicit allocation with term1 already paid 3000, request 4000 | Items: term2 3000, term3 1000 | passing |
| TC-FEE-10-U17 | Explicit W5 (Lab 333.33 x 3, request 1000) | HTTPException 400 with `exceeds the scheduled term amounts by 0.01` | passing |
| TC-FEE-10-U18 | Legacy allocation W6 (same fixture) | Allocated 999.99, no exception, leftover discarded | passing |
| TC-FEE-10-U19 | Legacy allocation then remainder to old fees: this-year due 1000, old fee 500, pay 1200 | 1000 to fees, 200 to the old fee (paid 200, not settled) | passing |
| TC-FEE-10-U20 | Old fee settlement on payment: old fee 500 outstanding, remainder 500 | `paid_amount` 500, `is_settled` true | passing |
| TC-FEE-10-U21 | Transaction number format | Matches `^TXN\d{8}[0-9A-F]{8}$` | passing |
| TC-FEE-10-U22 | Receipt number generator with last `REC-2610-0009` | `REC-2610-0010`; with none this month `REC-2610-0001` | passing |
| TC-FEE-10-U23 | SMS status: `send_sms=false`; pending cheque; no parent; no phone; provider exception | `skipped`, `skipped`, `skipped`, `skipped`, `failed` | passing |
| TC-FEE-10-A01 | Admin pays Tuition 3000 cash with `fee_items` for the W1 student | 200; transaction `completed`; one item (term 1, 3000.00); receipt number matches `REC-YYMM-NNNN`; summary due 9000 | passing |
| TC-FEE-10-A02 | Pay the exact full due (12000) with `fee_items` | 200; summary due 0 | passing |
| TC-FEE-10-A03 | Pay 12000.01 against due 12000 | 400 `Amount 12000.01 exceeds total due 12000.00` | passing |
| TC-FEE-10-A04 | Pay when the due is 0 | 400 `No outstanding dues for this student` | passing |
| TC-FEE-10-A05 | Fixture Tuition outstanding 3000 and Lab outstanding 1000; `fee_items` Tuition 3500, `amount_to_pay` 3500 | Total due 4000 passes; 400 `Amount 3500 for 'Tuition' exceeds its outstanding due 3000.00` | passing |
| TC-FEE-10-A06 | `fee_items` for a fee type the student is not mapped to | 400 `Fee type <id> is not mapped to this student for this academic year` | passing |
| TC-FEE-10-A07 | `fee_items` for a fee type already paid in full | 400 `'<name>' has no outstanding due; nothing to pay for this fee type` | passing |
| TC-FEE-10-A08 | W5 over HTTP: Lab 1000 explicit | 400 `Amount for 'Lab' exceeds the scheduled term amounts by 0.01; check the term-wise fee setup` | passing |
| TC-FEE-10-A09 | W6 over HTTP: Lab 1000 without `fee_items` | 200; `amount_paid` "999.99"; summary Lab due "0.01" | passing |
| TC-FEE-10-A10 | W7 over HTTP: then pay 0.01 | 400 `No outstanding fees to pay` | passing |
| TC-FEE-10-A11 | Concession respected: W2 fixture (payable 10000), pay `fee_items` Tuition 10000 less 4000 already paid, i.e. 6000 | 200; summary due 0 | passing |
| TC-FEE-10-A12 | Concession respected: pay Tuition 6000.01 on the W2 fixture | 400 total due or per-type outstanding message | passing |
| TC-FEE-10-A13 | Pay without `fee_items`, amount above this-year due, student has old fees 900 | 200; this-year fees fully paid, remainder reduces the old fee; item name `Old: <fee type> (<label>)` | passing |
| TC-FEE-10-A14 | Payment UPI with `upi_reference` | 200; transaction stores `upi_reference`; receipt `payment_reference` shows it | passing |
| TC-FEE-10-A15 | Payment UPI without reference | 422 | passing |
| TC-FEE-10-A16 | Payment bank transfer with and without `bank_reference` | 200 with; 422 without | passing |
| TC-FEE-10-A17 | Payment by card with no reference | 200; transaction `payment_method` card | passing |
| TC-FEE-10-A18 | Payment by cheque (number, bank, date today) | 200; `receipt_number` ""; `sms_status` skipped; transaction `pending`, `cheque_status` pending; summary due unchanged | passing |
| TC-FEE-10-A19 | Payment by DD | Same as A18; receipt reference later shows `DD: <number>` after clearance | passing |
| TC-FEE-10-A20 | Cheque dated today plus 91 days; today plus 90 days | 422; 200 | passing |
| TC-FEE-10-A21 | `print_duplicate=true` on a completed payment | Receipt `is_reprinted` true, `reprint_count` 1 | passing |
| TC-FEE-10-A22 | `send_sms=false` | `sms_status` skipped | passing |
| TC-FEE-10-A23 | `send_sms=true` for a student whose parent has no phone | `sms_status` skipped; payment still 200 | skipped: admission requires a parent phone, so a parent without a phone cannot be created and send_sms=true would reach... |
| TC-FEE-10-A24 | Student with no fee mappings | 404 `No fee mappings found for this student and academic year` | passing |
| TC-FEE-10-A25 | Student without admission | 404 `Student admission not found` | passing |
| TC-FEE-10-A26 | Duplicate payment: send the identical request twice for a student with due 12000, amount 3000 | Without `idempotency_key`: both 200, two transactions and two receipts, due 6000. With the same `idempotency_key`: the second 200 returns the original transaction and receipt, due 9000, one history item. A key over 64 characters is 422 | passing |
| TC-FEE-10-A27 | Duplicate payment exceeding what remains: send the identical full-due request twice | First 200; second 400 `No outstanding dues for this student` | passing |
| TC-FEE-10-A28 | Pending cheque for the full due, then a cash payment for the full due | Both accepted (pending cheque is not counted); documents the exposure | passing |
| TC-FEE-10-A29 | Two concurrent identical full-due requests (parallel) | One 200 and one 400 (advisory lock; K12 fixed) | passing |
| TC-FEE-10-A30 | Receipt number sequencing: three completed payments in one month | `REC-YYMM-0001`, `-0002`, `-0003` (when the month had none) | passing |
| TC-FEE-10-A31 | Client sends an extra `receipt_number` field | Ignored; the server number is returned | passing |
| TC-FEE-10-A32 | Unknown `payment_method` ("wallet") | 422 | passing |
| TC-FEE-10-A33 | Refund (F13) processed afterwards | Summary Paid unchanged (refunds never subtracted) | passing |
| TC-FEE-10-A34 | Role matrix `POST /pay` | Admin 200; Staff, Teacher, Student, Parent 403 with the default seed | passing |
| TC-FEE-10-A35 | No token; cross-tenant header; tenant B token paying a tenant A student id | 401; 403; 404 `No fee mappings found...` | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-10-E01 | P2 | Web | Admin | A student created through the API for the test (QA name, own QA class) with a QA fee mapped, nothing paid | 1. Open the QA student, "Fee Payment".<br>2. Open "Payment Up To" and choose the "Three Terms (15 Oct 2026)" entry. | "Fees Due Up To 15 Oct 2026" lists each fee type with its pending amount up to that date; Received Amount inputs empty; "Collect Payment" disabled | planned |
| TC-FEE-10-E02 | P1 | Web | Admin | As TC-FEE-10-E01 | 1. Choose "Payment Up To" "Three Terms (15 Oct 2026)".<br>2. Enter Received Amount 3000 for Tuition Fee.<br>3. Keep Payment Method "Cash" and switch "Send SMS" off (the switch defaults on).<br>4. Click "Collect Payment" and then "Confirm". | Dialog "Payment Recorded" with Transaction # (rendered "Transaction #:TXN...", no space), Receipt # (REC-YYMM-NNNN), Items Paid Tuition Fee 3,000.00; after "Close" the Fee Summary shows Tuition Fee Paid 3,000.00 | passing |
| TC-FEE-10-E03 | P3 | Web | Admin | As TC-FEE-10-E01 | 1. Choose a "Payment Up To" date.<br>2. Enter a Received Amount above the row amount. | Toast `Amount should not exceed ... for Tuition Fee`; value clamped to the row amount | planned |
| TC-FEE-10-E04 | P3 | Web | Admin | As TC-FEE-10-E01 | 1. Enter 100 for Tuition Fee.<br>2. Choose Payment Method "UPI", leave "UPI Reference *" empty.<br>3. Click "Collect Payment". | Inline error "UPI reference is required"; no request sent | planned |
| TC-FEE-10-E05 | P1 | Web | Admin | As TC-FEE-10-E01 | 1. Enter 500 for Activity Fee.<br>2. Choose "Cheque", fill Cheque Number "QA480001", Bank Name "QA Bank", Cheque Date today.<br>3. Switch "Send SMS" off (it defaults on).<br>4. Click "Collect Payment", then "Confirm". | Success dialog shows `Cheque/DD pending clearance - receipt will be generated once the instrument clears.` (the app uses an em dash, not a hyphen) and no receipt buttons; Fee Summary Paid unchanged | passing |
| TC-FEE-10-E06 | P3 | Web | Admin | As TC-FEE-10-E01 | 1. Choose "Cheque", set Cheque Date 91 days ahead.<br>2. Click "Collect Payment". | Inline error `Cheque/DD date cannot be more than 90 days in the future` | planned |
| TC-FEE-10-E07 | P3 | Web | Admin | As TC-FEE-10-E01 | 1. Enter 100, choose "Bank Transfer", leave "Bank Reference *" empty.<br>2. Click "Collect Payment". | Inline error "Bank reference is required" | planned |
| TC-FEE-10-E08 | P2 | Web | Admin | TC-FEE-10-E02 dialog open | 1. Click "Download Receipt". | Toast "Receipt downloaded"; a PDF named after the receipt number | planned |
| TC-FEE-10-E09 | P3 | Web | Teacher | None | 1. Sign in as Teacher.<br>2. Open `/fee/collection` by URL. | Redirected to the Dashboard (Teacher has no fee access, so the Payment tab notice "You don't have permission to collect fee payments. Contact an administrator for access." cannot be reached with the default roles) | planned |
| TC-FEE-10-E10 | P3 | Web | Admin | As TC-FEE-10-E01 | 1. Choose a "Payment Up To" date and leave all Received Amounts empty. | "Collect Payment" stays disabled | planned |
| TC-FEE-10-E11 | P2 | Web | Admin | Seeded student Ananya Reddy (Tuition concession 2,000.00) | 1. Open "Fee Payment".<br>2. Choose "Payment Up To" "Three Terms (15 Jan 2027)".<br>3. Read the Tuition Fee row. | Actual Amount is the pending amount net of the concession (10,000.00 when nothing else was paid since the seed) | planned |
| TC-FEE-10-E12 | P3 | Web | Admin | Two browser sessions on Kavya Verma's Payment tab | 1. In session 1 pay the full Activity Fee.<br>2. In session 2 try to pay Activity Fee again without reloading. | Red banner with the backend message (for example `'Activity Fee' has no outstanding due; nothing to pay for this fee type`); no success dialog | planned |
| TC-FEE-10-E13 | P2 | Mobile | Admin | Seeded student Kavya Verma | 1. Open Kavya Verma, "Fee Payment".<br>2. Choose "Payment Up To", enter 200 for Activity Fee, Cash.<br>3. Tap "Collect Payment" and confirm.<br>4. Tap "Download Receipt", then "Done". | Modal "Payment Recorded"; the receipt opens or shares; Done closes the modal | planned |
| TC-FEE-10-E14 | P3 | Mobile | Admin | Seeded student Kavya Verma | 1. "Fee Payment", enter 100, method "Cheque", fill the number and date but no "Bank Name *".<br>2. Tap "Collect Payment". | Required-field error; no request sent | planned |
| TC-FEE-10-E15 | P3 | Web | Staff | Seeded student Kavya Verma | 1. Sign in as Staff.<br>2. Open Kavya Verma from Fee Collection. | Fee Summary shows "Permission not found in database: Staff cannot read fee_collection. Contact administrator to configure permissions."; the Payment tab stays at "Loading installments..." (Staff has no `fee_collection` grant, K23) | planned |

API tests implemented in: backend/tests/api/fee/test_fee_payment.py

Implemented in: backend/tests/unit/fee/test_fee_payment_rules.py (phase 1 unit cases).

---

## F11 Receipts

**Purpose.** Issue, find, print and verify numbered payment receipts. Each receipt carries a SHA-256 hash of its rendered content, a reprint counter and a PDF produced on demand.

**Roles and permissions.** `fee_receipts:create` (generate), `read` (single, by number, content, verify, PDF), `list` (search), `update` (reprint, renumber). Default seed: Admin all four; Staff create, read, list (no reprint or renumber). Student `read_own` and `list_own`; Parent `read_related` (F16). Menu: Fee > Fee Receipts (web `/fee/receipts`, page needs `fee_receipts:list`); mobile tile "Fee Receipts" (`/fees/receipts`).

**Preconditions.** A completed transaction (F10 or F12). Payments by cheque or DD have no receipt until the transaction is marked completed (F12), after which the receipt must be generated explicitly.

**Steps, web.**
1. Open Fee > Fee Receipts (heading "Fee Receipt Management").
2. To issue a receipt manually click "Generate Receipt", pick the transaction in "Select Transaction" ("Choose a transaction..."; the list holds completed transactions of the selected year without a receipt), click "Generate Receipt".
3. Find receipts with "Receipt Number" ("Search by receipt number"), "Student ID" ("Filter by student ID"), "Date From", "Date To". The "Recent Receipts" table lists S.No., Receipt Number, Student, Generated At, Status (Original or Reprinted with the count), Actions (eye icon).
4. Pick a receipt in "Select Receipt" ("Choose a receipt...") to see "Receipt Details" (Receipt Number, Status with "Prints: N", Student, Academic Year, Class & Section, Generated At, Remarks) and the buttons "View Content", "Verify Integrity", "Reprint Receipt" (only with `fee_receipts:update`) and "Download PDF".
5. "View Content" shows "Receipt Content": Transaction Number, Payment Method, Total Amount, Payment Reference, Collected By, "Fee Breakdown" (Fee Type, Term, Amount).
6. "Verify Integrity" shows "Receipt is valid and untampered" or "Receipt integrity compromised" with the stored and current hashes and the verification date.
7. "Reprint Receipt" increments the count and opens "Reprint Receipt" ("Choose how you'd like to receive the reprinted copy") with "Print" (opens the PDF and prints) and "Download PDF".

**Steps, mobile.** Fee Receipts screen: admins see "Generate" (modal "Generate New Receipt", "Select a completed transaction without a receipt."), "Search & Management" (Receipt Number, "Student (name / admission)", Date From, Date To, "Clear filters"), "Select Receipt", then "Receipt Details", "Receipt Content", "Download PDF", "Reprint Receipt" and a verify action. Parents see the same screen scoped to the selected child ("No child selected." until one is chosen).

**Expected results.** `fee_receipts` row, `fee_transactions.receipt_generated = true`, `receipt_hash` equal to the receipt's `content_hash`. The PDF downloads as `<receipt number>.pdf`.

**API endpoints.** Prefix `/fee/receipts` unless noted.
- `POST /generate/{transaction_id}`: 201 `FeeReceiptRead` (`id`, `receipt_number`, `fee_transaction_id`, `student_name`, `student_admission_num`, `class_section`, `academic_year`, `content_hash`, `pdf_file_path`, `is_reprinted`, `reprint_count`, `generated_by_user_id`, `remarks`, `generated_at`).
- `GET /`: `student_id`, `receipt_number` (contains, case-insensitive), `date_from`, `date_to` (on `generated_at`), `limit` (1-500), `offset`; newest first.
- `GET /{id}`; `GET /number/{receipt_number}`; `GET /{id}/content` (`ReceiptContent`).
- `PATCH /{id}/number` body `{receipt_number}`; `POST /{id}/reprint`; `GET /{id}/verify` returns `{receipt_id, receipt_number, is_valid, stored_hash, current_hash, verification_date}`; `GET /health`.
- `GET /fee/collection/receipts/{receipt_id}/pdf` (permission `fee_receipts:read` with own or related scope): `application/pdf`, `Content-Disposition: attachment; filename="<number>.pdf"`.

**Rules and validations.**
- Generate: unknown transaction 404 `Transaction with ID <id> not found`; non-completed 400 `Cannot generate receipt for non-completed transaction`; existing receipt 400 `Receipt already exists for this transaction`; the admission matching the transaction's student and admission number must exist (404 `Student admission not found`).
- Number: `REC-YYMM-NNNN`, current maximum for the month plus 1, restarting each month (W-table). The maximum is found by string order over the month's prefix and is protected only by the unique constraint, so simultaneous issues can collide (K12).
- Hash: SHA-256 of the sorted-key JSON of `ReceiptContent` (Decimal as string, datetime as ISO, UUID as string) including the receipt number, student name, class-section, year title, collector name, payment reference and items. Renaming the student, moving the class, or renumbering the receipt changes the rendered content, so verify returns `is_valid=false` without tampering.
- Content details: `class_section` is `"<class> - <section>"` (class only without a section); `payment_reference` is the UPI reference, `Cheque: <no>`, `DD: <no>`, the bank reference, or null for cash and card; collector name comes from the staff row of `collected_by_user_id` (fallback "Staff"), with the designation when present; `school_name` and `school_address` are the fixed placeholders "School Name" and "School Address".
- Receipts written by `/pay` store empty `class_section` and `academic_year`; every read fills them from live data without changing the stored row.
- Items list the term-level payments of the transaction only. A legacy-mode payment that also reduced old fees (F10) has a receipt total larger than the sum of its items.
- Renumber: new number must be unique (400 `Receipt number '<n>' is already in use`); the same number is a no-op; any string is accepted (no format or length check beyond the 50-character column). Numbering ignores non-numeric suffixes with the current month's prefix (K15 fixed), takes an advisory lock and skips numbers already used.
- Reprint: sets `is_reprinted=true` and adds 1 to `reprint_count`; works for any receipt.
- Verify for an unknown receipt returns 404 (K16 fixed).
- PDF for own or related scope: the receipt's transaction student must be the caller (own) or one of the caller's children (related); otherwise 404 `Receipt not found`. PDF layout: school name and address, "FEE RECEIPT", Receipt No, Date (dd-Mon-yyyy), Student, Admission No, Class / Section, Academic Year, Payment Mode (upper case), Reference, a table of S.No., Fee Type, Term, Amount with a Total row, optional remarks, "Collected by: <name> (<designation>)", "Staff Signature" and "Principal / Management".

**Error and edge cases.** Receipt search with `date_from` after `date_to`: 400 `date_from must be before or equal to date_to`. Download for a receipt with a missing transaction or admission returns 404 or 500 depending on the missing row.

**Unit-testable logic.** `generate_receipt_number`; `generate_content_hash` (key order independence, Decimal and datetime serialisation); `get_receipt_content` mapping (payment reference per method, class-section format, collector fallback); `_enrich_receipt_fields` (fills empties without mutating the ORM object); `generate_receipt_pdf` returns PDF bytes; verify flat shape.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-11-U01 | `generate_receipt_number` with no receipts in the month 2610 | `REC-2610-0001` | passing |
| TC-FEE-11-U02 | Last receipt `REC-2610-0009` | `REC-2610-0010` | passing |
| TC-FEE-11-U03 | Last receipt `REC-2609-0042` while generating in 2610 | `REC-2610-0001` (month restart) | passing |
| TC-FEE-11-U04 | Last receipt `REC-2610-ABC` | `REC-2610-0001` (non-numeric suffix ignored; K15 fixed) | passing |
| TC-FEE-11-U05 | `generate_content_hash` with the same dict in two key orders | Identical 64 character hex digests | passing |
| TC-FEE-11-U06 | Hash of `{total_amount: Decimal("3000.00")}` vs `Decimal("3000.0")` | Different digests (string form is hashed) | passing |
| TC-FEE-11-U07 | Hash changes when `receipt_number` or `student_name` changes | Digest differs | passing |
| TC-FEE-11-U08 | `payment_reference` for upi, cheque, dd, bank_transfer, cash, card | UPI ref, `Cheque: CH1`, `DD: DD1`, bank ref, null, null | passing |
| TC-FEE-11-U09 | `class_section` with class "Class 5" and section "A"; without a section | `Class 5 - A`; `Class 5` | passing |
| TC-FEE-11-U10 | Collector without a staff row | `collected_by_user` "Staff", designation null | passing |
| TC-FEE-11-U11 | `_enrich_receipt_fields` on a stored receipt with empty `class_section` and `academic_year` | Returned model filled; ORM object attributes still empty | passing |
| TC-FEE-11-U12 | `generate_receipt_pdf` for a content with 2 items and remarks | Returns bytes beginning `%PDF`; no exception | passing |
| TC-FEE-11-U13 | Verify result shape | Keys `receipt_id`, `receipt_number`, `is_valid`, `stored_hash`, `current_hash`, `verification_date` only | passing |
| TC-FEE-11-A01 | `POST /generate/{id}` for a completed transaction without a receipt | 201; number `REC-YYMM-NNNN`; transaction `receipt_generated` true | passing |
| TC-FEE-11-A02 | Generate twice for the same transaction | Second 400 `Receipt already exists for this transaction` | passing |
| TC-FEE-11-A03 | Generate for a pending cheque transaction | 400 `Cannot generate receipt for non-completed transaction` | passing |
| TC-FEE-11-A04 | Generate for an unknown transaction | 404 `Transaction with ID ... not found` | passing |
| TC-FEE-11-A05 | Cheque flow: pay by cheque, PUT status completed and cheque cleared (F12), then generate | 201; no receipt existed before this call | passing |
| TC-FEE-11-A06 | `GET /{id}` for a receipt written by `/pay` | `class_section` and `academic_year` filled | passing |
| TC-FEE-11-A07 | `GET /number/{number}` existing and unknown | 200; 404 `Receipt with number ... not found` | passing |
| TC-FEE-11-A08 | `GET /{id}` unknown | 404 `Receipt with ID ... not found` | passing |
| TC-FEE-11-A09 | `GET /{id}/content` | Items with fee type, term and amount; `payment_reference` per method; placeholders "School Name", "School Address" | passing |
| TC-FEE-11-A10 | `GET /` with `receipt_number=0001` | Matching receipts only (contains, case-insensitive) | passing |
| TC-FEE-11-A11 | `GET /` with `student_id` and a date range | Only that student's receipts in range, newest first | passing |
| TC-FEE-11-A12 | `GET /` with `date_from` after `date_to` | 400 `date_from must be before or equal to date_to` | passing |
| TC-FEE-11-A13 | `GET /` with `limit=501` | 422 | passing |
| TC-FEE-11-A14 | `GET /{id}/verify` for an untouched receipt | `is_valid` true; stored and current hashes equal | passing |
| TC-FEE-11-A15 | Rename the student, then verify | `is_valid` false; hashes differ | passing |
| TC-FEE-11-A16 | Renumber the receipt, then verify | `is_valid` false | passing |
| TC-FEE-11-A17 | Verify an unknown id | 404 | passing |
| TC-FEE-11-A18 | `PATCH /{id}/number` to a free number | 200 with the new number | passing |
| TC-FEE-11-A19 | `PATCH /{id}/number` to a number used by another receipt | 400 `Receipt number '<n>' is already in use` | passing |
| TC-FEE-11-A20 | `PATCH /{id}/number` to its own number | 200 unchanged | passing |
| TC-FEE-11-A21 | Renumber to `REC-YYMM-ABC` (current month), then pay or generate another receipt | Next issue is `REC-YYMM-0001` or the next numeric suffix | passing |
| TC-FEE-11-A22 | `POST /{id}/reprint` twice | `is_reprinted` true; `reprint_count` 1 then 2 | passing |
| TC-FEE-11-A23 | Reprint an unknown id | 404 `Receipt with ID ... not found` | passing |
| TC-FEE-11-A24 | `GET /fee/collection/receipts/{id}/pdf` as Admin | 200 `application/pdf`; header filename `<number>.pdf`; body starts `%PDF` | passing |
| TC-FEE-11-A25 | PDF as Student for own receipt; for another student's receipt | 200; 404 `Receipt not found` | passing |
| TC-FEE-11-A26 | PDF as Parent for a linked child's receipt; for an unrelated child's receipt | 200; 404 | passing |
| TC-FEE-11-A27 | PDF for an unknown receipt id | 404 `Receipt with ID ... not found` | passing |
| TC-FEE-11-A28 | Legacy payment that reduced an old fee (F10) then fetch content | Items sum is less than `total_amount` (documents the edge) | passing |
| TC-FEE-11-A29 | `GET /fee/receipts/health` | 200 `module: "fee_receipts"` | passing |
| TC-FEE-11-A30 | Role matrix generate (create) | Admin, Staff 201; Teacher, Student, Parent 403 | passing |
| TC-FEE-11-A31 | Role matrix reprint and renumber (update) | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-11-A32 | Role matrix get, number, content, verify (read) and search (list) | Admin, Staff 200; Teacher, Student, Parent 403 (Student and Parent only through the scoped endpoints, F16) | passing |
| TC-FEE-11-A33 | No token; cross-tenant header; tenant B cannot read tenant A receipt by id or number | 401; 403; 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-11-E01 | P1 | Web | Admin | TC-FEE-10-E02 done (or any receipt created for the test) | 1. Open Fee > Fee Receipts.<br>2. Pick the receipt in "Select Receipt". | "Receipt Details" shows Status Original, no "Prints" badge (it appears only after a reprint), Student, Academic Year 2026-2027, Class & Section, Generated At | passing |
| TC-FEE-11-E02 | P2 | Web | Admin | TC-FEE-12-E05 done (cheque marked completed, no receipt) | 1. Click "Generate Receipt".<br>2. Choose the transaction in "Select Transaction".<br>3. Click "Generate Receipt". | Toast "Receipt generated successfully"; the receipt appears in "Recent Receipts" | planned |
| TC-FEE-11-E03 | P2 | Web | Admin | A seeded UPI receipt selected | 1. Click "View Content". | "Receipt Content" shows Transaction Number, Payment Method, Total Amount, Payment Reference (the UPI26... reference), Collected By and "Fee Breakdown" matching the payment items | planned |
| TC-FEE-11-E04 | P2 | Web | Admin | A seeded receipt selected | 1. Click "Verify Integrity". | Alert "Receipt is valid and untampered" with equal stored and current hashes | planned |
| TC-FEE-11-E05 | P3 | Web | Admin | A QA-admitted student with a paid receipt whose first name is then changed (do not rename seeded students) | 1. Select that receipt.<br>2. Click "Verify Integrity". | Alert "Receipt integrity compromised" with different hashes | planned |
| TC-FEE-11-E06 | P2 | Web | Admin | A seeded receipt selected | 1. Click "Reprint Receipt".<br>2. Click "Download PDF" in "Reprint Receipt". | Status Reprinted, "Prints: 1"; PDF downloads | planned |
| TC-FEE-11-E07 | P1 | Web | Admin | A seeded receipt selected | 1. Click "Download PDF". | File `<receipt number>.pdf` downloads; toast "Receipt PDF downloaded" | passing |
| TC-FEE-11-E08 | P3 | Web | Admin | Seeded receipts REC-2610-0001 to REC-2610-0024 | 1. Type "0002" in "Search by receipt number".<br>2. Clear it and set Date From and Date To to today. | Recent Receipts filters to numbers containing 0002, then to today's receipts | planned |
| TC-FEE-11-E09 | P3 | Web | Staff | Seeded receipts | 1. Sign in as Staff.<br>2. Open Fee Receipts and select a receipt. | "Reprint Receipt" absent; "View Content", "Verify Integrity", "Download PDF" present | planned |
| TC-FEE-11-E10 | P2 | Mobile | Admin | Seeded receipts | 1. Open "Fee Receipts".<br>2. Pick a receipt in "Select Receipt".<br>3. Tap "Download PDF". | The PDF opens or shares; no "Unable to download receipt" toast | planned |
| TC-FEE-11-E11 | P3 | Mobile | Admin | A completed transaction without a receipt (TC-FEE-12-E05 done) | 1. Tap "Generate".<br>2. Pick the transaction and confirm. | Toast "Receipt Generated" (Receipt generated successfully) | planned |

API tests implemented in: backend/tests/api/fee/test_fee_receipts.py, backend/tests/api/fee/test_fee_self_service.py

Implemented in: backend/tests/unit/fee/test_fee_receipt_sms_rules.py (phase 1 unit cases).

---

## F12 Transactions

**Purpose.** List and inspect every payment, move a payment through its statuses (clearing or bouncing a cheque, cancelling a pending payment), and record a payment by explicit term items through the older "New Transaction" form.

**Roles and permissions.** `fee_transactions:create`, `read`, `update`, `list`. Default seed: Admin and Staff all four. Web: page `/fee/transactions` (needs `fee_transactions:list`), reached from the sidebar entry Fee > Fee Transactions (from the backend menu); the Fee dashboard has no card for it. Mobile: screen `/fees/transactions` (no hub tile).

**Preconditions.** Payments exist (F10). For "New Transaction", the student has mappings with term amounts.

**Steps, web.**
1. Open Fee > Fee Transactions (`/fee/transactions`, card "Fee Transactions"). Filters: "Student" ("Select student..."), "Payment Method" (All methods, Cash, UPI, Cheque, Bank Transfer), "Status" (All statuses, Completed, Pending, Cancelled, Bounced), "From Date", "To Date", "Apply Date Filter" and "Clear All Filters". Selecting a student also shows "Outstanding Fees" with "Total Outstanding", "N fee items" and "View History", which opens "Transaction History" ("Complete payment history for the selected student", "Payment Timeline").
2. The table shows S.No., Transaction #, Student, Total Amount, Payment Method, Status, Date and Actions (eye button "View").
3. "View" opens "Transaction Details" (status badge, number and date, Total Amount, "Student Information", "Transaction Information", "Payment Details") with actions: "Generate Receipt" (completed without a receipt, needs `update`), "Mark Completed" and "Cancel Transaction" (pending, needs `update`). There is no control for bouncing or for the cheque status.
4. "New Transaction" (needs `create`) opens "Create New Transaction" ("Record a new fee payment transaction"): "Student *", "Admission Number", "Payment Method *" (Cash, UPI, Cheque, Bank Transfer), the method field ("UPI Reference *", "Cheque Number *" or "Bank Reference *"), "Total Amount" (calculated, "Total is automatically calculated from transaction items"), "Transaction Items" with "Add Item" (empty text `No transaction items added. Click "Add Item" to get started.`) (per item "Fee Type *", "Fee Term *", "Payment Date *", "Amount Due *", "Amount Paid *", "Description"), "Remarks", "Create Transaction". The web payload omits `cheque_date`, `cheque_bank` and `bank_name`, which the API requires for cheque and bank transfer (K13).

**Steps, mobile.** `/fees/transactions` ("Fee Transactions"): filters "All Students", "All Statuses" (All Statuses, Paid, Pending, Partial, Cancelled: derived labels shown on the cards, not the backend statuses), "From Date" and "To Date" (YYYY-MM-DD); "Add Transaction" opens a multi-step form (Student, Admission Number, Payment Method with UPI Reference, Cheque Number, Cheque Date, Bank Name, Bank Reference, Transaction Date, Collected By, items with Fee Type, Fee Term Date, Amount Due, Amount Paid, Description, Remarks; buttons Previous, Next); an outstanding-fees modal shows "No outstanding fees found" when empty; update and "Generate" receipt actions use `update`.

**Expected results.** Transactions listed newest first. A status change updates the row and is visible in the summary (only `completed` counts).

**API endpoints.** Prefix `/fee/transactions`.
- `POST /` (201, 20 per minute): `student_id`, `student_admission_num`, `academic_year_id`, `total_amount`, `payment_method` (`cash`, `upi`, `cheque`, `bank_transfer`), method fields, `remarks`, `transaction_items[{fee_type_id, term_date_id, amount_due, amount_paid, description}]`.
- `GET /`: `student_id`, `academic_year_id`, `payment_method`, `status`, `has_receipt`, `date_from`, `date_to`, `limit` (1-500), `offset`; 60 per minute.
- `GET /{id}`; `PUT /{id}` body `{status, cheque_status, approved_by_user_id, remarks}`.
- `GET /student/{student_id}/outstanding?academic_year_id=` (`OutstandingFeeSummary`); `GET /student/{student_id}/history?academic_year_id=&limit=`; `GET /transaction-number/{transaction_number}`; `GET /health`.
- Self-service endpoints of this router are in F16.

**Rules and validations.**
- Create (schema): `payment_method` is one of cash, upi, cheque, bank_transfer (422 otherwise; `dd` and `card` are not accepted here); `total_amount > 0`; at least one item; each `amount_due > 0`, `amount_paid > 0` and `amount_paid <= amount_due` (client supplied); the sum of item amounts must match `total_amount` within 0.01; UPI needs `upi_reference`; cheque needs number, date and bank; bank transfer needs `bank_reference` and `bank_name` (all 422).
- Create (service): the admission must match the student and number (404, detail object with `message`); the student must have mappings in the year (404 `Student has no fee structure configured for academic year <id>`); each item must hit an existing mapping and term amount (404); `outstanding = term_amount - completed paid for that term date`; an `amount_paid` above it is a business-rule error. An `amount_paid` above the outstanding returns 400 with the outstanding amount, and items for the same term date are checked cumulatively so they cannot overpay together (K14 fixed). The same error path covers the total-mismatch check. An optional `idempotency_key` replays the original transaction.
- Cheque creates `pending` with `cheque_status=pending`; every other method creates `completed` and a receipt is generated after the commit (a failure is only logged). Concessions and old fees are ignored by this endpoint.
- Status update (`STATUS_TRANSITIONS`): `pending` to `completed`, `cancelled` or `bounced`; `completed` to `bounced` only; `cancelled` and `bounced` are final. Any other change: 400 `Cannot change status from <old> to <new>.` with ` Completed payments are reversed through refunds.` appended for completed. `bounced` is only allowed for cheque and DD: 400 `Only cheque and DD payments can bounce`.
- Cheque status (`CHEQUE_STATUS_TRANSITIONS`): none to pending, cleared or bounced; `pending` to `cleared` or `bounced`; `cleared` to `bounced`; `bounced` final. It applies only to cheque and DD (400 `Cheque status applies only to cheque and DD payments`); an invalid move gives 400 `Cannot change cheque status from <old> to <new>`; `cheque_status=bounced` requires `status=bounced` in the same request (400 `A bounced cheque needs the transaction status set to bounced as well`).
- A status update never creates a receipt, so a cleared cheque needs "Generate Receipt" (F11). Bouncing a completed payment removes it from Paid; its receipt stays.
- Unknown transaction: 404 `Transaction with ID <id> not found` on update; `GET /{id}` returns a 404 detail object `Transaction not found`.
- List: `date_from` after `date_to` gives 400; `date_to` is compared as given, so a date-only value means midnight and excludes that day's payments. `has_receipt` filters on `receipt_generated`. A `status` or `payment_method` outside the enums is 422 (the method enum includes `dd` and `card`).
- `GET /transaction-number/{n}` looks the number up in the query; 404 when absent (K17 fixed).
- Outstanding items are per term amount (`term_amount - completed paid`) shown when above 0; no concessions or old fees; `total_outstanding` is their sum.

**Error and edge cases.** Marking a cheque completed without `cheque_status` leaves `cheque_status=pending`. Cancelling a pending cheque keeps `cheque_status=pending`. Transactions of other tenants are invisible by row-level security.

**Unit-testable logic.** `STATUS_TRANSITIONS` and `CHEQUE_STATUS_TRANSITIONS` (full matrices), bounce-only-for-cheque rule, bounced cheque pairing, `FeeTransactionBase` and `FeeTransactionItemBase` validators, 0.01 total tolerance, `calculate_outstanding_fees`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-12-U01 | Status matrix, cheque payment: pending to completed, cancelled, bounced | All three allowed | passing |
| TC-FEE-12-U02 | Status matrix: completed to bounced (cheque) | Allowed | passing |
| TC-FEE-12-U03 | Status matrix: completed to cancelled, completed to pending | 400 `Cannot change status from completed to cancelled. Completed payments are reversed through refunds.` (and to pending) | passing |
| TC-FEE-12-U04 | Status matrix: cancelled to completed, bounced to completed, cancelled to pending | 400 `Cannot change status from <old> to <new>.` | passing |
| TC-FEE-12-U05 | Status pending to bounced for a cash payment | 400 `Only cheque and DD payments can bounce` | passing |
| TC-FEE-12-U06 | Same status as stored (completed to completed) | No transition check; fields such as remarks update | passing |
| TC-FEE-12-U07 | Cheque status matrix: none to pending, cleared, bounced; pending to cleared, bounced; cleared to bounced | All allowed | passing |
| TC-FEE-12-U08 | Cheque status: cleared to pending; bounced to cleared | 400 `Cannot change cheque status from <old> to <new>` for each | passing |
| TC-FEE-12-U09 | `cheque_status=bounced` with status unchanged `pending` | 400 `A bounced cheque needs the transaction status set to bounced as well` | passing |
| TC-FEE-12-U10 | `cheque_status=cleared` on a cash transaction | 400 `Cheque status applies only to cheque and DD payments` | passing |
| TC-FEE-12-U11 | `FeeTransactionBase` UPI without reference; cheque missing bank; bank transfer missing `bank_name` | ValidationError for each | passing |
| TC-FEE-12-U12 | `FeeTransactionItemBase` `amount_paid` 3000.01 over `amount_due` 3000 | ValidationError `Amount paid cannot exceed amount due` | passing |
| TC-FEE-12-U13 | `FeeTransactionCreate` total 3000 with items 1500 + 1499.99 (diff 0.01) and 1499.98 (diff 0.02) | Accepted; rejected | passing |
| TC-FEE-12-U14 | `FeeTransactionBase` `payment_method="dd"` and `"card"` | ValidationError (Literal of four) | passing |
| TC-FEE-12-U15 | Outstanding calculation: term 3000, paid 1000 | outstanding 2000, item listed; term fully paid not listed; `total_outstanding` sums | passing |
| TC-FEE-12-U16 | Transaction number generator format | `TXN` + date + 8 hex, unique per call | passing |
| TC-FEE-12-A01 | Admin `POST /` cash, one item (term 1 of Tuition, due 3000, paid 3000) | 201; `completed`; `receipt_number` set; `receipt_generated` true | known defect: FEE-B09: POST /fee/transactions/ for a completed method (cash, upi, bank_transfer) returns 500 MissingGreenlet... |
| TC-FEE-12-A02 | POST by cheque with number, date, bank | 201; `pending`; `cheque_status` pending; no receipt number | passing |
| TC-FEE-12-A03 | POST UPI without reference; bank transfer without `bank_name`; cheque without bank | 422 each | known defect: FEE-B09: POST /fee/transactions/ for upi and bank_transfer returns 500 MissingGreenlet after commit |
| TC-FEE-12-A04 | POST items whose sum differs from `total_amount` by 0.02 | 422 | passing |
| TC-FEE-12-A05 | POST `amount_paid` above the term outstanding (3000 paid already, pay 100) | 400 with the outstanding amount | passing |
| TC-FEE-12-A06 | POST for a student with no mappings in the year | 404 with message `Student has no fee structure configured for academic year <id>` | passing |
| TC-FEE-12-A07 | POST with an admission number that does not belong to the student | 404 `Student with ID ... and admission number ... not found` | passing |
| TC-FEE-12-A08 | POST with an unknown `term_date_id` | 404 `Term amount not found for term date <id>` | passing |
| TC-FEE-12-A09 | POST two items for the same term date, each within the outstanding but together above it | 400 (cumulative check; K14 fixed) | passing |
| TC-FEE-12-A10 | POST `payment_method="dd"` | 422 | passing |
| TC-FEE-12-A11 | `GET /` filters `student_id`, `academic_year_id`, `payment_method=cash`, `status=completed`, `has_receipt=true` | Only matching rows, newest first, each with items and `receipt_number` | passing |
| TC-FEE-12-A12 | `GET /?status=paid` | 422 (not a status) | passing |
| TC-FEE-12-A13 | `GET /` with `date_from` after `date_to` | 400 `date_from must be before or equal to date_to` | passing |
| TC-FEE-12-A14 | `GET /?date_to=<today>` (date only) | Payments made today are excluded (midnight comparison) | passing |
| TC-FEE-12-A15 | `GET /?limit=0` and `limit=501` | 422 | passing |
| TC-FEE-12-A16 | `GET /{id}` existing; unknown | 200 with `student_full_name`, items, `receipt_number`; 404 `Transaction not found` | passing |
| TC-FEE-12-A17 | `PUT /{id}` cheque: pending to completed with `cheque_status=cleared` | 200; both updated; summary Paid now includes the amount | passing |
| TC-FEE-12-A18 | `PUT /{id}` cheque: pending to bounced with `cheque_status=bounced` | 200; final; summary unchanged | passing |
| TC-FEE-12-A19 | `PUT /{id}` completed cheque to bounced with `cheque_status=bounced` | 200; Paid decreases; receipt remains | passing |
| TC-FEE-12-A20 | `PUT /{id}` pending cash to cancelled | 200 | passing |
| TC-FEE-12-A21 | `PUT /{id}` invalid moves (completed to cancelled; cancelled to completed; cash to bounced; `cheque_status=bounced` alone) | 400 with the messages in the rules | passing |
| TC-FEE-12-A22 | `PUT /{id}` with `approved_by_user_id` and `remarks` | Stored and returned | passing |
| TC-FEE-12-A23 | `PUT` unknown id | 404 `Transaction with ID ... not found` | passing |
| TC-FEE-12-A24 | `PUT` with `status="done"` | 422 | passing |
| TC-FEE-12-A25 | Mark a cheque completed then check receipts | No receipt yet (`receipt_generated` false) until F11 generate | passing |
| TC-FEE-12-A26 | `GET /student/{id}/outstanding?academic_year_id=Y1` for W2 fixture | Per term items with `amount_due`, `amount_paid`, `outstanding_amount`; no concession effect | passing |
| TC-FEE-12-A27 | `GET /student/{id}/history?academic_year_id=Y1&limit=1` | One item with `fee_types_paid` names and `receipt_generated` | passing |
| TC-FEE-12-A28 | `GET /transaction-number/{n}` for the newest transaction; for an older one | 200 for both | passing |
| TC-FEE-12-A29 | `GET /fee/transactions/health` | 200 `module: "fee_transactions"` | passing |
| TC-FEE-12-A30 | Role matrix create (POST) | Admin, Staff 201; Teacher, Student, Parent 403 | passing |
| TC-FEE-12-A31 | Role matrix update (PUT) | Admin, Staff 200; others 403 | passing |
| TC-FEE-12-A32 | Role matrix list, read, outstanding, history, by number | Admin, Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-12-A33 | No token; cross-tenant header; tenant B list and `GET /{id}` of tenant A data | 401; 403; empty and 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-12-E01 | P1 | Web | Admin | 24 seeded completed payments | 1. Open Fee > Fee Transactions. | Card "Fee Transactions" lists transactions newest first with Transaction #, Student, Total Amount, Payment Method, Status, Date | passing |
| TC-FEE-12-E02 | P3 | Web | Admin | TC-FEE-10-E05 done (pending cheque) | 1. Set Status "Pending" and Payment Method "Cheque". | Only the pending cheque row(s) | planned |
| TC-FEE-12-E03 | P3 | Web | Admin | Seeded payments | 1. Set From Date and To Date to today.<br>2. Click "Apply Date Filter".<br>3. Click "Clear All Filters". | Rows from the range only; all rows return | planned |
| TC-FEE-12-E04 | P2 | Web | Admin | Seeded student Karthik Reddy | 1. Choose Karthik Reddy in "Student".<br>2. Click "View History". | "Outstanding Fees" card with Total Outstanding and "N fee items"; "Transaction History" dialog with "Payment Timeline" | planned |
| TC-FEE-12-E05 | P1 | Web | Admin | TC-FEE-10-E05 done | 1. Click "View" on the pending cheque.<br>2. Click "Mark Completed". | Toast "Transaction status updated successfully"; the View dialog closes; the row shows Completed and "Generate Receipt" appears when the row is opened again | passing |
| TC-FEE-12-E06 | P2 | Web | Admin | TC-FEE-12-E05 done | 1. In "Transaction Details" click "Generate Receipt". | Toast "Receipt generated successfully"; receipt visible in Fee Receipts | planned |
| TC-FEE-12-E07 | P3 | Web | Admin | A second pending cheque made as in TC-FEE-10-E05 | 1. "View" it.<br>2. Click "Cancel Transaction". | Toast "Transaction status updated successfully"; status Cancelled; no further actions | planned |
| TC-FEE-12-E08 | P2 | Web | Admin | Kavya Verma has an unpaid Activity Fee term | 1. Click "New Transaction".<br>2. Choose Kavya Verma, Payment Method "Cash".<br>3. "Add Item": Fee Type Activity Fee, its term, Payment Date today, Amount Due and Amount Paid 100.<br>4. Click "Create Transaction". | Toast "Transaction created successfully"; row appears | blocked: module known gap (POST /fee/transactions/ for cash returns 500 MissingGreenlet after saving) |
| TC-FEE-12-E09 | P3 | Web | Admin | As TC-FEE-12-E08 | 1. "New Transaction" with Payment Method "Cheque" and only "Cheque Number *".<br>2. Add one item and click "Create Transaction". | Error toast from the API (cheque date and bank missing, K13); nothing saved | planned |
| TC-FEE-12-E10 | P3 | Web | Admin | None | 1. Click "New Transaction", choose a student, add no items.<br>2. Click "Create Transaction". | Toast "Please add at least one transaction item" | planned |
| TC-FEE-12-E11 | P3 | Web | Staff | Seeded payments | 1. Sign in as Staff.<br>2. Open Fee > Fee Transactions. | List visible with "New Transaction" and "View" (Staff has create and update) | planned |
| TC-FEE-12-E12 | P3 | Mobile | Admin | As TC-FEE-12-E08 | 1. Open `/fees/transactions`.<br>2. Tap "Add Transaction", complete the steps with Cash and one item.<br>3. Submit. | Toast "Fee transaction created successfully" | blocked: module known gap (cash create returns 500 after saving) |

API tests implemented in: backend/tests/api/fee/test_fee_transactions.py

Implemented in: backend/tests/unit/fee/test_fee_transaction_refund_rules.py (phase 1 unit cases).

---

## F13 Refunds

**Purpose.** Return money for a completed payment through a controlled flow: a request, an approval or rejection, and a processing step that records how the money was returned. Refunds are a record of the decision; they do not change transaction status or the fee summary.

**Roles and permissions.** `fee_refunds:create` (request), `read` (single, pending list, approved list, per-transaction summary), `list` (search, statistics), `approve` (approve or reject), `process`. Default seed: Admin all five; Staff create, read, list. Menu: Fee > Fee Refunds (web `/fee/refunds`); mobile tile "Fee Refunds" (`/fees/refunds`). Web gates "Approve/Reject" on `approve` and shows "Process" to anyone on an approved row (the API still needs `process`).

**Preconditions.** A completed transaction (F10 or F12).

**Steps, web.**
1. Open Fee > Fee Refunds (title "Fee Refunds", subtitle "Manage fee refund requests and track their status"). Cards "Total Refund Amount", "Pending Refunds", "Processed Refunds", "Rejected Refunds" from `GET /statistics`.
2. Click "Create Refund Request" (needs `create`). In "Create New Refund Request" ("Create a new fee refund request for a student") choose "Student *" ("Select a student"), then "Fee Transaction *" ("Please select a student first" until then; completed transactions of the student, shown as number, amount, method, fee types, date), enter "Refund Amount *", choose "Refund Reason *" (Fee Adjustment, Student Withdrawal, Excess Payment, Other), optionally "Detailed Reason" ("Provide detailed reason..."), and click "Create Refund". Toast "Refund created successfully"; a server error toasts `Failed to create refund: <message>`.
3. Filters ("Filters"): "Student", "Status" (All statuses, Pending, Approved, Rejected, Processed), "Refund Reason" (All reasons, Fee Adjustment, Student Withdrawal, Excess Payment, Other), "Requested Date From", "Requested Date To", "Apply Filters", "Clear All Filters", "Refresh". The table shows S.No., Refund Number, Student Admission, Refund Amount, Reason, Status, Requested Date and Actions: View, "Approve/Reject" (pending), "Process" (approved).
4. "Approve/Reject" opens "Approve or Reject Refund" ("Review and decide on the refund request for <number>"): "Action" (Approve, Reject); rejection needs "Rejection Reason *" (toast "Please provide a rejection reason" when empty); "Submit". Approval sends the remark "Approved", rejection sends the typed reason.
5. "Process" opens "Process Refund" ("Process the approved refund for <number>"): "Reference Number (Optional)" ("Enter bank reference number..."), button "Process Refund"; toast "Refund processed successfully". The page sends `refund_method` bank_transfer when a reference is typed, otherwise cash with the reference "Cash refund processed".

**Steps, mobile.** The Fee Refunds screen shows tiles Total, Amount, Pending, Approved, Processed, Rejected, filters "All Statuses", "All Students", "Filter by reason...", From and To (YYYY-MM-DD), and cards per refund (number, student, transaction, amount, reason, date, status). "Request Refund" opens "Create Refund" (Student, Fee Transaction "Select Student First", Refund Amount "Enter refund amount", Refund Reason with Fee Adjustment, Student Withdrawal, Excess Payment, Other; "Detailed Reason *" is required for Other; checks `Refund amount cannot exceed transaction amount`; toast "Fee refund created successfully"). Row actions: approve (check icon, modal "Process Refund Action" with Action and "Remarks *"), process (modal "Process Refund" with "Reference Number (optional)"), cancel (modal "Cancel Refund" with "Cancellation Reason *"). Approve sends action and remarks, process sends `refund_method` (selector in the modal) and the reference, and cancel is sent as a rejection with the reason as remarks (K03 fixed). Toasts "Refund approved successfully", "Refund processed successfully", "Refund cancelled successfully"; an empty remark toasts "Required" / "Please enter remarks before continuing." and an empty cancellation reason "Please enter a cancellation reason.".

**Expected results.** A `fee_refunds` row with a number `RFD` + date + 6 hex characters and status `pending`; then `approved` or `rejected`; then `processed`. Statistics and the per-transaction summary reflect the counts.

**API endpoints.** Prefix `/fee/refunds`.
- `POST /` (201): `fee_transaction_id`, `student_id`, `student_admission_num`, `academic_year_id`, `refund_amount` (> 0), `refund_reason` (`fee_adjustment`, `student_withdrawal`, `excess_payment`, `other`), `detailed_reason`, `requested_by_user_id` (optional, overwritten by the token user). `student_id`, `student_admission_num` and `academic_year_id` are optional: they are taken from the transaction and a differing value is 400.
- `POST /approve`: `refund_id`, `action` (`approve` or `reject`), `approval_remarks` (required), `approved_by_user_id` (required in the body, overwritten by the token user).
- `POST /process`: `refund_id`, `refund_method` (`cash`, `bank_transfer`, `cheque`), `refund_reference`, `processing_remarks`, `processed_by_user_id` (required in the body, overwritten by the token user).
- `GET /` (`student_id`, `academic_year_id`, `status`, `refund_reason`, `date_from`, `date_to`, `limit` 1-500, `offset`); `GET /{id}`; `GET /pending/approval` and `GET /approved/processing` (`limit` default 50, `offset`); `GET /statistics` (`academic_year_id`, `date_from`, `date_to`); `GET /transaction/{transaction_id}/summary`; `GET /health`.

**Rules and validations.**
- Create: the transaction must exist (404 `Transaction with ID <id> not found`) and be `completed` (400 `Can only refund completed transactions`). Available amount = `total_amount` minus refunds in status `approved` or `processed`; a request above it gives 400 `Refund amount <a> exceeds available amount <b>`; a request equal to it passes (W10). Pending refunds are not counted and approval does not re-check the limit, so several pending requests can together exceed the transaction.
- Create derives `student_id`, `student_admission_num` and `academic_year_id` from the transaction and rejects a differing body value with 400 (K18 fixed); the amount limit counts pending, approved and processed refunds and locks the transaction row. `refund_reason` outside the four values is 422. `detailed_reason` is optional on the API (required by the mobile form for Other).
- Approve or reject only works while `pending`: otherwise 400 `Refund is already <status>, cannot change approval status`. Approve sets `approved`; reject sets `rejected`; both store `approved_by_user_id`, `approval_remarks` and `approved_date`.
- Process only works from `approved`: otherwise 400 `Only approved refunds can be processed`. It sets `processed` with `processed_by_user_id`, `refund_method`, `refund_reference`, `processing_remarks`, `processed_date`. `rejected` and `processed` are final. There is no cancel, update or delete endpoint (`PUT`, `DELETE /{id}`, `POST /{id}/cancel` and `GET /by-transaction/{id}` called by the clients do not exist).
- Statistics: `total_refund_amount` is the sum of `processed` refunds only; counts per status; `refunds_by_reason`; `monthly_refunds` (excludes rejected) as `{month "YYYY-MM", count, amount}`; date filters on `requested_date`.
- Summary per transaction: `total_requested` (all statuses), `total_approved` (approved plus processed), `total_processed`, `status_counts`, `refund_count`.
- The `refund_reason` query filter on `GET /` uses `RefundReason`, whose values are the stored ones (`fee_adjustment`, `student_withdrawal`, `excess_payment`, `other`) (K19 fixed).
- Refunds are never subtracted from Paid in the summary, the history or reports (F09).

**Error and edge cases.** The web list sends `offset`, `date_from` and `date_to` (K19 fixed). Unknown refund id: 404 `Refund with ID <id> not found`.

**Unit-testable logic.** Eligibility and available-amount rule (W10), status machine (pending to approved or rejected; approved to processed), statistics aggregation, summary aggregation, refund number format, `FeeRefundBase` validators.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-13-U01 | Available amount: transaction 5000, approved 1000, processed 2000, pending 3000, rejected 500 | available 2000 (pending and rejected ignored) | passing |
| TC-FEE-13-U02 | Request 2500 against available 2000; request exactly 2000 | 400 `Refund amount 2500 exceeds available amount 2000.00`; accepted | passing |
| TC-FEE-13-U03 | Two pending requests of 4000 each on a 5000 transaction | Both accepted (pending not counted) | passing |
| TC-FEE-13-U04 | Non-completed transaction (pending, cancelled, bounced) | 400 `Can only refund completed transactions` for each | passing |
| TC-FEE-13-U05 | Status machine: approve on pending; approve on approved; reject on rejected; process on pending; process on approved | Allowed; 400; 400; 400 `Only approved refunds can be processed`; allowed | passing |
| TC-FEE-13-U06 | `FeeRefundBase` with amount 0 and -10 | ValidationError `Refund amount must be positive` | passing |
| TC-FEE-13-U07 | `FeeRefundBase` with reason `adjustment` | ValidationError (Literal of four) | passing |
| TC-FEE-13-U08 | `FeeRefundApproval` with `action="cancel"` | ValidationError | passing |
| TC-FEE-13-U09 | `FeeRefundProcessing` with `refund_method="card"` | ValidationError | passing |
| TC-FEE-13-U10 | Refund number format | Matches `^RFD\d{8}[0-9A-F]{6}$` | passing |
| TC-FEE-13-U11 | Statistics: refunds 1000 processed, 500 pending, 200 rejected, 300 approved | `total_refund_amount` 1000; counts processed 1, pending 1, rejected 1, approved 1; monthly excludes the rejected one | passing |
| TC-FEE-13-U12 | Transaction summary with the same set | `total_requested` 2000, `total_approved` 1300, `total_processed` 1000 | passing |
| TC-FEE-13-A01 | Admin `POST /` 2000 for a 5000 completed cash transaction, reason `excess_payment` | 201; status `pending`; `refund_number` matches the pattern; `requested_by_user_id` equals the token user even when the body sent another id | passing |
| TC-FEE-13-A02 | POST without `requested_by_user_id` | 422 | passing |
| TC-FEE-13-A03 | POST above the available amount (W10) | 400 `Refund amount 2500 exceeds available amount 2000.00` | passing |
| TC-FEE-13-A04 | POST on a pending cheque transaction | 400 `Can only refund completed transactions` | passing |
| TC-FEE-13-A05 | POST on an unknown transaction | 404 `Transaction with ID ... not found` | passing |
| TC-FEE-13-A06 | POST with `refund_reason="other"` and no `detailed_reason` | 201 (optional on the API) | passing |
| TC-FEE-13-A07 | POST with `refund_reason="withdrawal"`; amount 0; amount -1 | 422 each | passing |
| TC-FEE-13-A08 | POST with a `student_id` different from the transaction's student | 400 (K18 fixed) | passing |
| TC-FEE-13-A09 | `POST /approve` action approve with remarks | 200; `approved`; `approved_by_user_id` equals the token user; `approved_date` set | passing |
| TC-FEE-13-A10 | `POST /approve` action reject | 200; `rejected`; final | passing |
| TC-FEE-13-A11 | Approve a refund already approved or rejected | 400 `Refund is already <status>, cannot change approval status` | passing |
| TC-FEE-13-A12 | `POST /approve` without `approved_by_user_id` or without `approval_remarks` | 422 | passing |
| TC-FEE-13-A13 | `POST /process` on an approved refund with `refund_method=bank_transfer` and a reference | 200; `processed`; method, reference, remarks and dates stored | passing |
| TC-FEE-13-A14 | `POST /process` on pending or rejected or already processed | 400 `Only approved refunds can be processed` | passing |
| TC-FEE-13-A15 | `POST /process` without `refund_method` or `processed_by_user_id` | 422 | passing |
| TC-FEE-13-A16 | After approval, request again for the same transaction up to the new available amount | Accepted up to `total - approved`; one cent more is rejected | passing |
| TC-FEE-13-A17 | After processing, fee summary Paid for the student | Unchanged (refunds never subtracted) | passing |
| TC-FEE-13-A18 | `GET /` filtered by `student_id`, `status=pending`, date range | Matching refunds newest first | passing |
| TC-FEE-13-A19 | `GET /?refund_reason=excess_payment`; `refund_reason=fee_adjustment` | 200 with matches for each of the four values; 422 for others | passing |
| TC-FEE-13-A20 | `GET /?status=completed` | 422 (not a refund status) | passing |
| TC-FEE-13-A21 | `GET /pending/approval` and `GET /approved/processing` | Only refunds in that status, oldest first | passing |
| TC-FEE-13-A22 | `GET /statistics` with and without `academic_year_id` and dates | Aggregates per the statistics rule; `total_refund_amount` counts processed only | passing |
| TC-FEE-13-A23 | `GET /transaction/{id}/summary` | Figures per the summary rule; unknown transaction returns zeros and `refund_count` 0 | passing |
| TC-FEE-13-A24 | `GET /{id}` existing; unknown | 200; 404 `Refund with ID ... not found` | passing |
| TC-FEE-13-A25 | Non-existent endpoints the clients call: `PUT /{id}`, `DELETE /{id}`, `POST /{id}/cancel`, `GET /by-transaction/{id}` | 405 or 404; the clients no longer call them (K03 fixed) | passing |
| TC-FEE-13-A26 | `GET /fee/refunds/health` | 200 `module: "fee_refunds"` | passing |
| TC-FEE-13-A27 | Role matrix create | Admin, Staff 201; Teacher, Student, Parent 403 | passing |
| TC-FEE-13-A28 | Role matrix approve | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-13-A29 | Role matrix process | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-FEE-13-A30 | Role matrix list, statistics (list) and read, pending, approved, summary (read) | Admin, Staff 200; others 403 | passing |
| TC-FEE-13-A31 | No token; cross-tenant header; tenant B sees none of tenant A refunds and cannot approve one | 401; 403; empty and 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-13-E01 | P1 | Web | Admin | Seeded student Aarav Gupta (20260001) fully paid; seeded pending refund 1,000.00 on his transaction | 1. Open Fee > Fee Refunds.<br>2. Click "Create Refund Request".<br>3. Choose Student Aarav Gupta and one of his completed transactions.<br>4. Enter Refund Amount 200, Refund Reason "Excess Payment", Detailed Reason "QA refund".<br>5. Click "Create Refund". | Toast "Refund created successfully"; new row Pending for 200 | passing |
| TC-FEE-13-E02 | P3 | Web | Admin | As TC-FEE-13-E01 | 1. Create a refund for the same transaction with an amount above the transaction total. | Error toast `Failed to create refund: Refund amount ... exceeds available amount ...` | planned |
| TC-FEE-13-E03 | P1 | Web | Admin | TC-FEE-13-E01 done | 1. Click "Approve/Reject" on the QA refund.<br>2. Keep Action "Approve".<br>3. Click "Submit". | Row Approved; "Process" appears | passing |
| TC-FEE-13-E04 | P3 | Web | Admin | A pending QA refund | 1. Click "Approve/Reject".<br>2. Choose Action "Reject", leave "Rejection Reason *" empty.<br>3. Click "Submit". | Toast "Please provide a rejection reason" | planned |
| TC-FEE-13-E05 | P2 | Web | Admin | A pending QA refund | 1. "Approve/Reject", Action "Reject", reason "QA not eligible".<br>2. Click "Submit". | Row Rejected with no further actions | planned |
| TC-FEE-13-E06 | P1 | Web | Admin | TC-FEE-13-E03 done, plus a second approved QA refund | 1. "Process" the first, enter "QA-REF-1" in "Reference Number (Optional)", click "Process Refund".<br>2. "Process" the second with no reference. | Toast "Refund processed successfully" both times; both Processed (method bank_transfer, then cash) | passing |
| TC-FEE-13-E07 | P3 | Web | Admin | Seeded refunds and QA refunds | 1. Set Status "Approved", click "Apply Filters".<br>2. Choose Student Aarav Gupta. | Only matching rows | planned |
| TC-FEE-13-E08 | P2 | Web | Staff | Seeded refunds | 1. Sign in as Staff.<br>2. Open Fee > Fee Refunds. | "Create Refund Request" visible; no "Approve/Reject"; "Process" still shown on approved rows (the API returns 403) | planned |
| TC-FEE-13-E09 | P3 | Web | Admin | After TC-FEE-13-E01 to E06 | 1. Read the cards and click "Refresh". | "Pending Refunds", "Processed Refunds", "Rejected Refunds" counts and "Total Refund Amount" (processed only) match the table | planned |
| TC-FEE-13-E10 | P2 | Mobile | Admin | As TC-FEE-13-E01 | 1. Open "Fee Refunds", tap "Request Refund".<br>2. Choose Aarav Gupta, a transaction, amount 100, reason Fee Adjustment, tap "Create Refund".<br>3. Tap the approve action, enter "Remarks *", confirm. | Toasts "Fee refund created successfully" and "Refund approved successfully" | planned |
| TC-FEE-13-E11 | P3 | Mobile | Admin | A pending QA refund | 1. Tap cancel on it.<br>2. Enter "Cancellation Reason *" and confirm. | Toast "Refund cancelled successfully"; status Rejected with the reason as remarks | planned |

API tests implemented in: backend/tests/api/fee/test_fee_refunds.py

Implemented in: backend/tests/unit/fee/test_fee_transaction_refund_rules.py (phase 1 unit cases).

---

## F14 Fee SMS (due reminder and receipt resend)

**Purpose.** Tell a parent how much a student still owes, and resend receipt confirmations. The per-payment receipt SMS is part of F10 (`send_sms`).

**Roles and permissions.** Due reminder preview and send use `fee_collection:read` (the code checks `read`, not `send_sms`); receipt resend uses `fee_collection:send_sms`. Default seed: Admin has `read` but no `send_sms` (the QA grant list decides). Web: "Send SMS" button on the Fee Summary tab. Mobile: no screen for these endpoints.

**Preconditions.** The student has a linked parent with a phone number (first linked parent is used); the SMS provider is configured (`MSG91_*` variables) or mocked in tests.

**Steps, web.**
1. Open Fee Collection > student > "Fee Summary" and click "Send SMS".
2. The dialog "Confirm SMS" shows the parent phone and name, the message text and, when no phone exists, `No phone number on record - SMS cannot be delivered.`
3. Click "Confirm & Send" (disabled when the parent has no phone); a `sent` result toasts "SMS sent successfully". "Cancel" closes the dialog.
4. After a payment, the "Payment Recorded" dialog also offers "Send Receipt SMS", which uses the communication module quick-send (template "Fee Collection"), not these endpoints.

**Steps, mobile.** Not available in the UI.

**Expected results.** A message is sent through the provider and a `NotificationLog` row is written (status sent or failed). Receipt resend queues `NotificationQueue` rows and a Celery batch.

**API endpoints.** Prefix `/fee/collection`.
- `GET /summary/{student_id}/sms-preview?academic_year_id=`: `{parent_name, parent_phone, student_name, admission_number, academic_year, due_amount, message, can_send}`.
- `POST /summary/{student_id}/send-sms?academic_year_id=`: `{status: "sent" | "skipped" | "failed", detail}`.
- `POST /send-receipt-sms`: JSON array of receipt ids; returns `{status: "queued", queued_count, skipped_count, detail}`.

**Rules and validations.**
- Message: `Dear <parent>, fee due for <student> (Adm: <admission>) is Rs.<due> for <academic year>. Please pay at the earliest.` where `due = grand_total_due + old_fee_pending_amount` formatted with thousands separators and two decimals, and the parent name defaults to "Parent". Without a parent phone the preview message is `No parent phone number found` plus a note and `can_send` is false.
- Send: unknown student 404 `Student not found`; no parent phone returns status `skipped` with detail `No parent phone number found for this student`; provider failure returns `failed` with detail `SMS failed: <error>`; success returns `sent` with detail `SMS sent to <name> (<phone>)`. The send is synchronous. The `NotificationLog` write failure is swallowed.
- Receipt resend: each id is looked up; a missing receipt, transaction, student, or parent phone increments `skipped_count`; valid ones are queued with the message `Received Rs <total> for <student>. Receipt No. <number>.` and a batch task is dispatched after the commit. An empty array queues nothing.
- Payments by cheque or DD never send the receipt SMS (F10).

**Error and edge cases.** Only the first linked parent is used. Preview works even when the SMS provider is down. The reminder uses the full-year due, not the as-of-date terms.

**Unit-testable logic.** Message builder and due total, `can_send` logic, send status mapping (`sent`, `skipped`, `failed`), resend counters.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-14-U01 | Message builder with parent "Asha", student "Ravi K", admission "A101", due 6000 and old fee 900, year "2026-27" | `Dear Asha, fee due for Ravi K (Adm: A101) is Rs.6,900.00 for 2026-27. Please pay at the earliest.` | passing |
| TC-FEE-14-U02 | Due formatting with 1234567.5 | `Rs.1,234,567.50` | passing |
| TC-FEE-14-U03 | No parent row | parent name "Parent", `can_send` false | passing |
| TC-FEE-14-U04 | Parent with an empty phone | `can_send` false; send returns `skipped` | passing |
| TC-FEE-14-U05 | Provider raises an exception | Status `failed`, detail starts `SMS failed:` | passing |
| TC-FEE-14-U06 | Resend counters with 3 receipts: one missing, one without parent phone, one valid | queued 1, skipped 2 | passing |
| TC-FEE-14-A01 | Admin `GET /summary/{id}/sms-preview?academic_year_id=Y1` for a student with due 6000, parent with phone | `can_send` true; `due_amount` "6000.00" (plus old fee when present); message per the template | passing |
| TC-FEE-14-A02 | Preview for a student whose parent has no phone | `can_send` false | skipped: admission requires a parent phone, so a student whose parent has no phone cannot be created through the API |
| TC-FEE-14-A03 | Preview for an unknown student | 404 `Student not found` | passing |
| TC-FEE-14-A04 | Preview without `academic_year_id` | 422 | passing |
| TC-FEE-14-A05 | `POST /summary/{id}/send-sms` with the provider mocked to succeed | 200 `{status: "sent", detail: "SMS sent to <name> (<phone>)"}`; one `NotificationLog` row with status sent | skipped: a successful or failed send would call the SMS provider; |
| TC-FEE-14-A06 | Send with the provider mocked to fail | 200 `{status: "failed"}`; log row status failed | skipped: the provider failure path needs a mocked provider, which is not possible against the running API |
| TC-FEE-14-A07 | Send for a student without a parent phone | 200 `{status: "skipped"}` | skipped: a parent without a phone cannot be created through admission |
| TC-FEE-14-A08 | Send for an unknown student | 404 `Student not found` | passing |
| TC-FEE-14-A09 | `POST /send-receipt-sms` with one valid receipt id and one random id | 200 `{status: "queued", queued_count: 1, skipped_count: 1}` | passing |
| TC-FEE-14-A10 | `POST /send-receipt-sms` with an empty array | 200 queued 0, skipped 0 | passing |
| TC-FEE-14-A11 | `POST /send-receipt-sms` with a non-UUID item | 422 | passing |
| TC-FEE-14-A12 | Role matrix preview and send (read) | Admin 200; Staff, Teacher, Student, Parent 403 with the default seed | passing |
| TC-FEE-14-A13 | Role matrix receipt resend (`send_sms`) | Roles with the grant 200; Admin without the default grant 403 (verify the QA seed) | passing |
| TC-FEE-14-A14 | No token; cross-tenant header; tenant B cannot preview a tenant A student | 401; 403; 404 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-14-E01 | P2 | Web | Admin | Seeded student Kavya Verma with a seeded parent phone; SMS provider mocked or disabled in the QA API | 1. Open Kavya Verma, "Fee Summary".<br>2. Click "Send SMS".<br>3. Click "Confirm & Send". | Dialog "Confirm SMS" shows the parent phone and name and `Dear <parent>, fee due for Kavya Verma (Adm: 006) is Rs.<due> for 2026-2027. Please pay at the earliest.`; on send, toast "SMS sent successfully" (or the failed status) and the dialog closes | planned |
| TC-FEE-14-E02 | P3 | Web | Admin | A student whose parent has no phone | 1. Click "Send SMS". | Text `No phone number on record - SMS cannot be delivered.`; "Confirm & Send" disabled | blocked: admission requires a parent phone, so no such student exists |
| TC-FEE-14-E03 | P3 | Web | Admin | Seeded student Kavya Verma | 1. Click "Send SMS".<br>2. Click "Cancel". | Dialog closes; no `send-sms` request | planned |

API tests implemented in: backend/tests/api/fee/test_fee_sms.py

Implemented in: backend/tests/unit/fee/test_fee_receipt_sms_rules.py (phase 1 unit cases).

---

## F15 Fee reports

**Purpose.** Management reports on money collected, money still pending, and the fee structure, each with a table, summary statistics and an export file.

**Roles and permissions.** `fee_reports:read` (all six report endpoints; a token with `is_superadmin` skips the check), `fee_reports:export` (export). Default seed: Admin and Staff both. Web: sidebar Fee > Fee Reports (from the backend menu) and the Reports hub card "Fee Reports" (`/fee/reports`, page guarded by `fee_reports:read`; no card on the Fee dashboard). Mobile: Reports screen card "Fee Reports" (`/reports/fee-reports`) and the screen `/fees/reports` (no Fee hub tile).

**Preconditions.** Transactions, student mappings and class mappings exist.

**Steps, web.**
1. Open Fee > Fee Reports or Reports > "Fee Reports" (page "Fee Reports & Export", subtitle "Generate reports and export fee data"; the format select and "Export" sit in the header).
2. Use the filter bar: "All Classes" (then a section select), "All Categories", and on the Collection Summary tab only From and To date inputs, "All Methods" (Cash, UPI, Cheque, Bank Transfer) and "All Status" (Completed, Pending, Cancelled, Bounced); "Clear" resets. Class, section and category apply to all tabs. The tables load without a filter; while no filter is set the page also shows "Select at least one filter to generate a report" under the tabs.
3. Choose a tab: "Collection Summary" (table columns S.No., Transaction #, Student, Class/Section, Category, Type, Term, Due, Paid, Method, Status, Date, Collected By), "Pending Fees" (S.No., Admission No, Student, Class/Section, Category, Type, Term, Due, Paid, Balance, Due Date, Days Overdue) or "Fee Structure" (S.No., Category, Type, Term, Class, Section, Amount, Academic Year, Status). Each tab shows a statistics table (Metric, Value): Total Collected, Total Due, Collection %, Payment Methods; Total Pending, Total Overdue, Students Pending, Avg Overdue Days; Fee Types, Categories, Terms, Avg Fee. Pages hold 50 rows with Previous and Next.
4. Pick the file format (CSV, Excel, PDF; default Excel) and click "Export"; the button is disabled until at least one filter is set. Success toasts "Report exported successfully".
5. The page sends no academic year, so figures cover all years (K21).

**Steps, mobile.** Two screens. `/reports/fee-reports` (Reports > "Fee Reports", see RPT F06): tabs "Collection", "Pending", "Structure", chips "All Time", "Today", "Last 7D", "This Month", "Export". `/fees/reports` ("Fee Reports"): tabs "Collection Summary", "Pending Fees", "Fee Structure"; filters "From Date", "To Date" (YYYY-MM-DD), "Payment Method" (All, Cash, Online, Cheque, UPI, Bank, Card), "Status" (All, Completed, Pending, Cancelled, Bounced), Class and Section, "Apply Filters"; stat tiles Collected and Total Due, "By Payment Method", "Recent Transactions"; "Total Pending", "Students", "Overdue", "Overdue Amt"; "Avg Fee", "Fee Types", "Categories". Export is CSV only. The "Online" option matches no stored method.

**Expected results.** Read-only tables and a downloaded file containing every matching row (not only the visible page).

**API endpoints.** Prefix `/reports/fees`.
- `GET /collection-summary`, `GET /collection-summary/stats`: filters `academic_year_id`, `fee_category_id`, `fee_type_id`, `payment_method`, `status`, `date_from`, `date_to`, `class_id`, `section_id`; the table adds `page`, `page_size` (default 100, 1 to 1000), `sort_by` (a `FeeTransaction` column), `sort_order` (`asc` or `desc`, default `desc`).
- `GET /pending-fees`, `GET /pending-fees/stats`: `academic_year_id`, `fee_category_id`, `fee_type_id`, `fee_term_id`, `class_id`, `section_id`, `days_overdue`, `amount_min`, `amount_max`; table adds `page`, `page_size`, `sort_by` (a key of the row), `sort_order` (default `asc`).
- `GET /fee-structure`, `GET /fee-structure/stats`: `academic_year_id`, `fee_category_id`, `fee_type_id`, `class_id`; table adds paging and sorting (`FeeType` column).
- `POST /export`: `{report_type: "fee_collection_summary" | "pending_fees" | "fee_structure", filters: {...}, format: "csv" | "xlsx" | "pdf", filename?}`; returns the file with `Content-Disposition: attachment` and `Content-Length`. Default file name `fee_<report_type>_<tenant id>`.
- Table responses: `{data, total_count, page, page_size, total_pages}`.

**Rules and validations.**
- Collection summary: one row per transaction item. It joins admission and class with inner joins, so a transaction whose student has no current class is not listed. `date_from` and `date_to` filter `created_at`; a `date_to` of the form `YYYY-MM-DD` includes the whole day. Statuses are not filtered unless `status` is given, so pending, cancelled and bounced rows appear. `transaction_date` in the row is `created_at`; `collected_by` is the user id.
- Collection stats: `total_collected` sums `amount_paid` of `completed` rows only; `total_due` sums, per (student, fee type, term date), the largest `amount_due` among completed rows (each paid instalment counted once); `collection_percentage = round(collected / due x 100, 2)` or 0 (W12); `payment_methods`, `fee_categories` (collected per key) and `monthly_collection` (key `YYYY-MM` of `created_at`) are completed amounts only.
- Pending fees: one row per student term amount whose balance `term_amount - completed paid for that term date` is above 0 (concessions ignored, K09); a mapping with no term amounts is one row using `total_fee` minus all completed payments of the fee type (term "Annual", no due date). `days_overdue = (today - due_date).days` when the due date is before today, otherwise null; the `days_overdue` filter excludes rows with null; `amount_min` and `amount_max` of 0 are ignored. Default order: student name then due date. Future instalments appear with null days overdue. Stats: `total_pending_amount`, `total_overdue_amount` (rows with days overdue), `total_students_with_pending` and `total_students_overdue` (distinct admission numbers), `average_overdue_days` (1 decimal), per-category and per-class sums (2 decimals).
- Fee structure: one row per (fee type, class mapping): `fee_amount` is the class mapping `total_fee`, `section_name` is always null, `status` is the fee type status; the academic year filter applies to the fee type. Stats: distinct counts, `average_fee_amount` (2 decimals), `fee_range` min and max, `category_wise_breakdown`.
- Stats endpoints use the same filtered query as their table, so the two agree.
- Export: `format` outside csv, xlsx, pdf is 422 (schema pattern); unknown `report_type` is 400 `Unsupported fee report type`; missing `fee_reports:export` is 403. Export has no superadmin bypass.
- Filter values that fail validation (for example `page_size` 0 or 1001, `sort_order` other than asc or desc, an unparsable `date_from`) return 422 (K20 fixed).

**Error and edge cases.** Empty data returns `data: []`, `total_count: 0`, `total_pages: 0` and zero stats. An unknown `sort_by` is ignored (default ordering).

**Unit-testable logic.** Collection percentage rounding (W12), pending balance and days overdue, instalment due de-duplication in `total_due`, date-only `date_to` expansion to end of day (`_parse_date_to`), pending row classification (overdue versus not due), statistics aggregation, structure statistics.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-15-U01 | Collection percentage with collected 7500 and due 10000 (W12); due 0 | 75.0; 0.0 | passing |
| TC-FEE-15-U02 | Collection percentage with 1 and 3 | 33.33 | passing |
| TC-FEE-15-U03 | `_parse_date_to("2026-09-15")` and `("2026-09-15T10:00:00")` | `2026-09-15 23:59:59.999999`; unchanged | passing |
| TC-FEE-15-U04 | Pending row: term 3000, paid 1000, due 2026-06-10, today 2026-09-15 | balance 2000; `days_overdue` 97 | passing |
| TC-FEE-15-U05 | Pending row with due date today, and with a future due date | `days_overdue` null for both | passing |
| TC-FEE-15-U06 | Pending row for a term fully paid | Row omitted | passing |
| TC-FEE-15-U07 | Pending row for a mapping without term amounts: total 1000, paid 400 | One row, term "Annual", due 1000, balance 600, no due date | passing |
| TC-FEE-15-U08 | Pending filter `amount_min` 0 and `amount_max` 0 | Both ignored | passing |
| TC-FEE-15-U09 | Pending filter `days_overdue=30` with a not-overdue row | Row excluded | passing |
| TC-FEE-15-U10 | Pending stats with rows (2000 overdue 97 days, 1000 not due, two students) | total pending 3000.00, overdue 2000.00, students 2, students overdue 1, average overdue days 97.0 | passing |
| TC-FEE-15-U11 | Collection stats total due: two completed items for the same (student, fee type, term date) with amount_due 3000 | Counted once: 3000 | passing (asserts the grouped MAX query shape; the grouping runs in SQL) |
| TC-FEE-15-U12 | Pending default sort | By student name then due date; null due dates last | passing |
| TC-FEE-15-U13 | Structure stats with fees 1000, 3000 across two categories | average 2000.00, range min 1000 max 3000, breakdown per category | passing |
| TC-FEE-15-A01 | Admin `GET /collection-summary?academic_year_id=Y1` | `ReportResponse`; rows per transaction item with the 14 documented fields | passing |
| TC-FEE-15-A02 | Collection summary with `status=completed`, `payment_method=cash`, class and section | Only matching rows | passing |
| TC-FEE-15-A03 | Collection summary with `date_from` and `date_to` equal to today (date only) | Includes today's rows (date-only end of day) | passing |
| TC-FEE-15-A04 | Collection summary `page=2&page_size=1` | One row; `sl_no` 2; `total_pages` equals `total_count` | passing |
| TC-FEE-15-A05 | Collection summary `sort_by=total_amount&sort_order=asc`; `sort_by=unknown` | Ascending by amount; unknown column ignored | passing |
| TC-FEE-15-A06 | Collection summary with `page_size=0`, `page_size=1001`, `sort_order=up`, `date_from=notadate` | 422 each (K20 fixed) | passing |
| TC-FEE-15-A07 | `GET /collection-summary/stats` for a fixture with completed 7500 and pending 1000 | `total_collected` 7500.0; pending payment not counted; `collection_percentage` per W12; `payment_methods` and `monthly_collection` keys | passing |
| TC-FEE-15-A08 | Stats agree with table: sum of `amount_paid` of completed rows in the table equals `total_collected` | Equal | passing |
| TC-FEE-15-A09 | `GET /pending-fees` for a student with Tuition 12000 and a completed payment of 3000 against term 1 | Three rows (terms 2 to 4) each with `balance_amount` 3000.0; term 1 omitted; a concession would not change the balances | passing |
| TC-FEE-15-A10 | `GET /pending-fees?days_overdue=30&amount_min=1000` | Only overdue rows with balance at least 1000 | passing |
| TC-FEE-15-A11 | `GET /pending-fees?sort_by=balance_amount&sort_order=desc` | Sorted descending; rows missing the key last | passing |
| TC-FEE-15-A12 | `GET /pending-fees/stats` | Totals per the stats rule; `class_wise_pending` keyed by class name | passing |
| TC-FEE-15-A13 | Pending report for a student with a concession of 2000 | Balance not reduced by the concession (documents K09) | passing |
| TC-FEE-15-A14 | `GET /fee-structure?academic_year_id=Y1&class_id=C1` | Rows per fee type of the class mappings; `section_name` null; `fee_amount` equals class mapping total | passing |
| TC-FEE-15-A15 | `GET /fee-structure/stats` | Counts, average, range, breakdown consistent with the table | passing |
| TC-FEE-15-A16 | `POST /export` collection summary as csv with filters | 200 `text/csv`; attachment filename; header row plus all matching rows (more than one page) | passing |
| TC-FEE-15-A17 | `POST /export` as xlsx and as pdf | 200 with the xlsx and pdf media types and non-empty bodies | passing |
| TC-FEE-15-A18 | `POST /export` pending_fees and fee_structure | 200 for both | passing |
| TC-FEE-15-A19 | `POST /export` with `report_type="x"`; with `format="txt"` | 400 `Unsupported fee report type`; 422 | passing |
| TC-FEE-15-A20 | Export file row count equals `total_count` of the matching table call | Equal | passing |
| TC-FEE-15-A21 | Role matrix read endpoints (six) | Admin, Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-15-A22 | Role matrix export | Admin, Staff 200; Teacher, Student, Parent 403 | passing |
| TC-FEE-15-A23 | No token; cross-tenant header; tenant B report excludes tenant A rows | 401; 403; empty | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-15-E01 | P1 | Web | Admin | Seeded payments | 1. Open Fee > Fee Reports (or Reports > "Fee Reports"). | "Fee Reports & Export"; "Collection Summary" tab with Metric/Value rows Total Collected, Total Due, Collection %, Payment Methods and the rows table; the note "Select at least one filter to generate a report" below | passing |
| TC-FEE-15-E02 | P2 | Web | Admin | Seeded payments | 1. Choose "All Status" > "Completed".<br>2. Set From and To to today. | Rows and statistics recompute for completed rows in the range | planned |
| TC-FEE-15-E03 | P2 | Web | Admin | Seeded data | 1. Click "Pending Fees".<br>2. Click "Fee Structure". | Pending: Total Pending, Total Overdue, Students Pending, Avg Overdue Days and Balance and Days Overdue columns; Structure: Fee Types, Categories, Terms, Avg Fee | planned |
| TC-FEE-15-E04 | P3 | Web | Admin | No filter set | 1. Look at "Export". | Disabled | planned |
| TC-FEE-15-E05 | P1 | Web | Admin | Seeded data | 1. Choose a class in "All Classes".<br>2. Keep format "Excel".<br>3. Click "Export". | Toast "Report exported successfully"; an .xlsx with every matching row | passing |
| TC-FEE-15-E06 | P2 | Web | Staff | Seeded data | 1. Sign in as Staff.<br>2. Open Fee > Fee Reports, choose a class, click "Export". | Page loads; the file downloads (Staff has read and export) | planned |
| TC-FEE-15-E07 | P3 | Web | Student | Signed in as seeded student Karthik Reddy (login 001) | 1. Open `/fee/reports` by URL. | "Access Denied" and "You don't have permission to view fee reports." | planned |
| TC-FEE-15-E08 | P2 | Mobile | Admin | Seeded data | 1. Open `/fees/reports` (Fee Reports screen).<br>2. Choose "Pending Fees", tap "Apply Filters". | Pending tiles match the web Pending Fees totals for the same filters | planned |

API tests implemented in: backend/tests/api/fee/test_fee_reports.py

Implemented in: backend/tests/unit/fee/test_fee_report_rules.py (phase 1 unit cases).

---

## F16 Student and parent self-service

**Purpose.** Let students and parents see fees, receipts and payments without staff help, with strict scoping so nobody sees another family's data. Payment is always recorded by staff; there is no online payment.

**Roles and permissions.** Student: `fee_receipts:read_own`, `list_own`; `fee_transactions:read_own`, `list_own` (default seed). Parent: `fee_receipts:read_related`; `fee_transactions:read_related`; `fee_collection:read_related`. Student has no `fee_collection` grant in the default seed, so the `my-summary` and `my-history` endpoints return 403 for it; the web and mobile student pages therefore use `my-outstanding-fees` instead. Web menu for both roles: Fee > My Receipts, My Transactions (injected by `menuUtils.ts`); mobile Fee hub for Student shows "My Fees" and Parent "Child Fees".

**Preconditions.** A student user with an `entity_id` (student id) or a parent user linked to children through student-parent links; payments exist.

**Steps, web.**
1. Student: Fee (`/fee`, page "Fee", subtitle "View your fees and receipts") shows "Fee Sections" cards "My Receipts" and "My Transactions".
2. "My Fee Summary" (`/fee/collection` or `/fee/my-fees`, subtitle "View your current fee status"): "Admission #: <number>" and the table S.No., Fee Type, Fee Term, Due, Paid, Outstanding with "Total Outstanding"; empty text "No outstanding fees - you're all paid up."
3. "My Receipts" (`/fee/my-receipts`): S.No., Receipt #, Academic Year, Class / Section, Generated On, Action "Download" (PDF). Empty state "No receipts yet".
4. "My Transactions" (`/fee/my-transactions`): S.No., Transaction #, Date, Payment Method, Amount, Status, Receipt ("Generated" or a dash). Empty state "No transactions yet".
5. Parent: `/fee/collection` shows "My Child's Fee Summary" (subtitle "View your child's current fee status"); with more than one child a "Select Child" dropdown appears; the header lists Student, Class and AY; the table has S.No., Fee Type, Assigned, After Concession, Paid, Due, Last Paid, Receipt # and Grand Total. "My Receipts" and "My Transactions" list the linked children's records filtered to the child chosen in the header switcher ("No child selected. Use the child switcher in the header above." when none).

**Steps, mobile.** Home "Fee Management" card opens the Fee hub for Student ("My Fees", "View your fee summary and payment history": cards "My Fee Summary", "My Receipts", "My Transactions") or Parent ("Child Fees", "View child fee summary and payment history": cards "Child Fee Summary", "My Fees", "My Receipts", "My Transactions"); the summary card reads "View dues, payments, concessions & old fees". The `/fees/my-fees` screen shows tiles Total Fee, Paid, Due, Paid %, a progress bar, "Fee Breakdown" and "Recent Receipts" (empty text "No outstanding fees - you're all paid up."). Receipts and transactions show "Failed to load receipts" / "Failed to load transactions" with "Retry" when the API call fails. A parent with no child selected sees "No student selected. Use the selector in the header.". The `/fees/collection` screen calls `my-summary` (student) or `child-summary` (parent) without `academic_year_id`, so it fails with 422 (K22).

**Expected results.** Each endpoint returns only the caller's own data (student) or linked children's data (parent). Read-only.

**API endpoints.**
- `GET /fee/collection/my-summary?academic_year_id=&as_of_date=` and `GET /fee/collection/my-history?academic_year_id=` (student, `fee_collection:read` resolved as own).
- `GET /fee/collection/child-summary/{student_id}?academic_year_id=&as_of_date=` and `GET /fee/collection/child-history/{student_id}?academic_year_id=` (parent).
- `GET /fee/transactions/my-fees?skip=&limit=` (student, `fee_transactions:read_own`); returns `{items, student_id, total_count, has_next, access_scope, user_role}`.
- `GET /fee/transactions/my-children-fees?skip=&limit=&academic_year_id=&transaction_status=` (parent, `read_related`); returns `{items, total_count, has_next, filters_applied, access_scope, user_role}`.
- `GET /fee/transactions/my-outstanding-fees` (student) and `GET /fee/transactions/child-outstanding-fees/{student_id}` (parent): `OutstandingFeeSummary` for the year of the student's latest admission.
- `GET /fee/receipts/my-receipts?limit=&offset=` (student, `list_own`) and `GET /fee/receipts/my-children-receipts?limit=&offset=` (parent, `read_related`).
- `GET /fee/collection/receipts/{receipt_id}/pdf` (F11).

**Rules and validations.**
- Scope resolution: an explicit `_own` or `_related` action checks that exact grant; otherwise `<action>_own`, then `<action>_related`, then `<action>`. A denied scope is 403 `permission_denied`.
- `my-summary`, `my-history`: a caller without a student id (for example Admin) gets 400 `Only students can access this endpoint`. `child-summary`, `child-history`: a caller without a parent id gets 400 `Only parents can access this endpoint`; a student id outside the caller's children is rejected by the entity check with 404 (the explicit 403 branch is not reached).
- `my-fees`, `my-outstanding-fees`, `my-receipts`: a caller that holds the grant but has no student id gets 400 `Only students can access this endpoint` (Admin lacks the `_own` grant and gets 403 first); `my-children-fees`, `my-children-receipts`: a parent without children gets 400 `Only parents with children can access this endpoint`.
- Pagination: `limit` 1 to 100 (default 10), `skip` or `offset` at least 0. `my-fees` is ordered by `created_at` descending and includes every status (pending, cancelled, bounced too). `transaction_status` on the parent list is applied as given without validation.
- Calculations follow the shared references: `my-summary` and `child-summary` equal the staff summary (F09); `my-outstanding-fees` is term based and ignores concessions and old fees (so it can differ from the summary for a student with a concession).
- The PDF endpoint checks the receipt's student against the caller and returns 404 `Receipt not found` otherwise (F11).
- A student's `fee_collection` grant is absent in the default seed, so `my-summary` and `my-history` return 403 (K22).

**Error and edge cases.** A parent who selects a child with no payments sees empty states, not errors. A teacher is redirected away from all fee pages. A student hitting an admin URL such as `/fee/categories` directly is not redirected on web (student path allow-list matches `/fee`); the page shows its own "Access Denied" panel ("You don't have permission to view fee categories."). A Student or Parent login without a linked student (such as the QA role logins) sees `Only students can access this endpoint` on My Receipts or `Permission denied: Parent cannot read_own fee_transactions` on `/fee/my-fees` for a parent.

**Unit-testable logic.** Own and related scope resolution, parent-child allowed-id list, outstanding items per term, web child filter by admission number, pagination `has_next` (`skip + limit < total_count`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-16-U01 | Scope resolution for a role holding `read_own` and `read` | `own` wins (more restrictive) | passing |
| TC-FEE-16-U02 | Scope resolution for Parent holding only `read_related` and asking `read` | `related` with the child ids | passing |
| TC-FEE-16-U03 | `has_next` with total 25, skip 10, limit 10; skip 20 | true; false | passing |
| TC-FEE-16-U04 | Outstanding items for a term 3000 with 1000 paid and a concession of 2000 on the fee type | outstanding 2000 (concession ignored) | passing |
| TC-FEE-16-U05 | Web child filter by `student_admission_num` for a parent with two children | Only the selected child's rows | blocked: filter is inline in web/src/pages/fee/MyReceiptsPage.tsx and MyTransactionsPage.tsx; needs the helper exported |
| TC-FEE-16-A01 | Student `GET /fee/transactions/my-fees` | 200; items only the caller's transactions, newest created first; `access_scope` "own" | passing |
| TC-FEE-16-A02 | Student `my-fees?limit=1&skip=1` | One item; `total_count` full; `has_next` computed | passing |
| TC-FEE-16-A03 | Student `my-fees?limit=101` | 422 | passing |
| TC-FEE-16-A04 | Parent `GET /fee/transactions/my-children-fees` | Transactions of all linked children only; `access_scope` "related" | passing |
| TC-FEE-16-A05 | Parent `my-children-fees?transaction_status=completed&academic_year_id=Y1` | Filtered; `filters_applied` echoes both | passing |
| TC-FEE-16-A06 | Student calls `my-children-fees`; parent calls `my-fees` | 403 each | passing |
| TC-FEE-16-A07 | Admin calls `my-fees` and `my-receipts` | 403 (no `_own` grant) | passing |
| TC-FEE-16-A08 | Student `GET /fee/transactions/my-outstanding-fees` | Term items for the latest admission's year; totals as per the rule | passing |
| TC-FEE-16-A09 | Parent `child-outstanding-fees/{child}`; with an unrelated student id | 200; 404 (entity check) | passing |
| TC-FEE-16-A10 | Student `GET /fee/receipts/my-receipts` | Only own receipts, newest first | passing |
| TC-FEE-16-A11 | Parent `GET /fee/receipts/my-children-receipts` | Receipts of all linked children only | passing |
| TC-FEE-16-A12 | Parent calls `my-receipts`; student calls `my-children-receipts` | 403 each | passing |
| TC-FEE-16-A13 | Parent without linked children calls `my-children-receipts` and `my-children-fees` | 400 `Only parents with children can access this endpoint` (or 403 when the grant is absent) | passing |
| TC-FEE-16-A14 | Student `GET /fee/collection/my-summary?academic_year_id=Y1` with the default seed | 403 (no `fee_collection` grant); with the grant added in the QA tenant: 200 equal to the staff summary | skipped: needs a temporary fee_collection:read grant on the shared Student role, which would race with other workers an... |
| TC-FEE-16-A15 | Student `my-summary` without `academic_year_id` | 422 | passing |
| TC-FEE-16-A16 | Admin `my-summary` | 400 `Only students can access this endpoint` | passing |
| TC-FEE-16-A17 | Parent `GET /fee/collection/child-summary/{child}?academic_year_id=Y1` | 200; equals the staff summary for that child | passing |
| TC-FEE-16-A18 | Parent `child-summary` for a student that is not a child | 404 | passing |
| TC-FEE-16-A19 | Student `child-summary` | 403 or 400 (no related scope) | passing |
| TC-FEE-16-A20 | Parent `child-history/{child}` and student `my-history` | 200 with completed transactions only (with the grant) | passing |
| TC-FEE-16-A21 | Student downloads own receipt PDF; another student's receipt id | 200; 404 | passing |
| TC-FEE-16-A22 | Parent downloads a child's receipt PDF; an unrelated child's receipt | 200; 404 | passing |
| TC-FEE-16-A23 | Cross-family check: parent P1 token with parent P2's child id on every `child-*` endpoint | 404 each (never data) | passing |
| TC-FEE-16-A24 | Tenant isolation: a student of tenant A cannot see tenant B data; cross-tenant header | 403 on header mismatch; own data only | passing |
| TC-FEE-16-A25 | No token on every endpoint of this feature | 401 | passing |
| TC-FEE-16-A26 | Teacher token on every endpoint of this feature | 403 | passing |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-16-E01 | P2 | Web | Student | A student created through the API for the test (QA name, own QA class) that has completed first login (login = admission number) | 1. Open Fee. | "Fee" page, "View your fees and receipts", "FEE SECTIONS" cards "My Receipts" and "My Transactions" only | planned |
| TC-FEE-16-E02 | P1 | Web | Student | As TC-FEE-16-E01 with a QA fee mapped; grant Student `fee_transactions:read_own` first (qa_manual has no such grant, so the case is skipped until it is granted) | 1. Open `/fee/my-fees`. | "My Fee Summary" with "Admission #: <the QA student's admission number>" and rows S.No., Fee Type, Fee Term, Due, Paid, Outstanding; Total Outstanding | skipped: blocked: qa_manual Student role has no fee_transactions:read_own grant (page shows "Permission denied: Student... |
| TC-FEE-16-E03 | P2 | Web | Student | As TC-FEE-16-E01; a receipt paid for the QA student | 1. Open My Receipts.<br>2. Click "Download" on a row. | Rows with Receipt #, Academic Year, Class / Section, Generated On; a PDF downloads | planned |
| TC-FEE-16-E04 | P2 | Web | Student | As TC-FEE-16-E01 | 1. Open My Transactions. | Rows with Transaction #, Date, Payment Method, Amount, Status badge, Receipt "Generated" | planned |
| TC-FEE-16-E05 | P3 | Web | Student | Signed in as seeded student Kavya Verma (login 006, no payments) | 1. Open My Receipts.<br>2. Open My Transactions. | "No receipts yet" and "No transactions yet" | planned |
| TC-FEE-16-E06 | P1 | Web | Parent | A parent created through the API for the test (QA name) with two QA children (fees 4,500 and 9,000) that has completed first login; grant Parent `fee_collection:read_related` first (qa_manual has no such grant, so the case is skipped until it is granted) | 1. Open `/fee/collection`.<br>2. Choose the other child in "Select Child". | "My Child's Fee Summary"; header Student, Class, AY; the table changes per child (4,500.00 for the first child, 9,000.00 for the second) | skipped: blocked: qa_manual Parent role has no fee_collection:read_related grant (page shows "Permission denied: Parent... |
| TC-FEE-16-E07 | P2 | Web | Parent | As TC-FEE-16-E06 | 1. Open My Receipts and My Transactions.<br>2. Switch child with the header switcher. | Only the selected child's rows; "No child selected. Use the child switcher in the header above." when none | planned |
| TC-FEE-16-E08 | P3 | Web | Student | As TC-FEE-16-E01 | 1. Open `/fee/categories` by URL. | No redirect; "Access Denied" and "You don't have permission to view fee categories." | planned |
| TC-FEE-16-E09 | P3 | Web | Teacher | None | 1. Sign in as Teacher.<br>2. Open `/fee/categories` by URL. | Redirected to the Dashboard; no Fee card | planned |
| TC-FEE-16-E10 | P2 | Mobile | Student | Signed in to qa_manual as seeded student Karthik Reddy | 1. Open the Fee Management card ("My Fees" hub).<br>2. Open "My Receipts", "My Transactions" and "My Fee Summary". | Each screen loads with the student's data; receipt download works | planned |
| TC-FEE-16-E11 | P3 | Mobile | Parent | Signed in as the seeded parent of Harsha and Tanvi Raju | 1. Open "Child Fees" > "Child Fee Summary". | Child summary loads for the selected child | blocked: K22 (child-summary is called without academic_year_id, 422) |

API tests implemented in: backend/tests/api/fee/test_fee_self_service.py

Implemented in: backend/tests/unit/fee/test_fee_scope_rules.py (phase 1 unit cases).

---

## F17 Fee hub, navigation and route guards

**Purpose.** The landing pages and menus through which each role reaches the fee features, and the guards that hide what a role may not use.

**Roles and permissions.** Web hub: `fee_categories:list`, `fee_types:list` or `fee_terms:list` shows the dashboard; otherwise the self-service page. Mobile tiles are gated per resource (`list`).

**Preconditions.** Logged in with a role and permissions (a re-login is needed after a grant change because the UI caches permissions).

**Steps, web.**
1. Admin-type roles: open Fee (`/fee`) to see "Fee Management Dashboard" ("Comprehensive overview and management of all fee-related components") with "Fee Management Sections": Fee Categories, Fee Types, Fee Terms, Fee Mappings, Fee Term Amounts, Fee Collection, Fee Receipts, Fee Refunds, each with a "Manage" button. The sidebar Fee submenu comes from the backend menu: in the seeded menu it lists Fee Categories, Fee Types, Fee Terms, Fee Mappings, Term Amounts, Fee Collection, Fee Receipts, Fee Transactions, Fee Refunds, Fee Reports, My Fees, My Receipts.
2. Student and parent: Fee shows "View your fees and receipts" and "Fee Sections" with "My Receipts" and "My Transactions" (F16).
3. `/fees` redirects to `/fee`. Teacher is redirected from every `/fee/*` to `/`, which lands on the Dashboard.
4. Fee Transactions (`/fee/transactions`) and Fee Reports (`/fee/reports`) have no dashboard card; they are reached from the sidebar (Reports also from the Reports hub).

**Steps, mobile.** The Home "Fee Management" card opens the Fee hub "Fee Management" ("Manage all fee operations in one place", "FEE SECTIONS") with tiles Fee Categories, Fee Types, Fee Terms, Fee Mappings, Fee Term Amounts (opens the Class Mappings tab), Fee Collection, Fee Receipts, Fee Refunds, each shown only with the resource permission (`list`); Student and Parent see the self-service layout; Teacher has no Fee Management card and `/fees` redirects to the Home dashboard. There are no tiles for Transactions or Reports (Reports tab has Fee Reports).

**Expected results.** Each role sees only the entries it can use; hidden pages still enforce permissions on the API.

**API endpoints.** None specific; menus come from the login response. The legacy-route redirects are frontend only.

**Rules and validations.**
- Web `routes/_app/fee.tsx`: role `teacher` redirects to `/`; for role `student` the allow-list contains `/fee`, which prefix-matches every path, so no student redirect happens.
- The web dashboard card for Fee Term Amounts goes to `/fee/term-amounts`, which redirects to the Class Mappings tab with a highlighted row.
- Mobile Fee Collection tile is gated on `fee_transactions:list`, while the API needs `fee_collection:list` (K23).

**Error and edge cases.** A user with only `fee_receipts:list` (no categories, types or terms list) sees the self-service page on web. The menu for a student comes from `menuUtils.ts` injection when the backend sends no Fee node.

**Unit-testable logic.** `menuUtils.ts` self-service injection for student and parent and the admin Fee submenu injection; `routes/_app/fee.tsx` `beforeLoad` redirect rules; mobile `roleBlocksFees` and `menuChildrenFor`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-FEE-17-U01 | `ensureFeeMenu` with no Fee node for role student | Injects a Fee node with children My Receipts (`/fee/my-receipts`) and My Transactions (`/fee/my-transactions`) | blocked: ensureFeeMenu is not exported from web/src/lib/menuUtils.ts |
| TC-FEE-17-U02 | `injectFeeSubmenu` for an admin with a flat Fee node | Adds the eight submenu entries | blocked: injectFeeSubmenu is not exported from web/src/lib/menuUtils.ts |
| TC-FEE-17-U03 | `beforeLoad` for role teacher on `/fee/categories` | Redirect to `/` | passing |
| TC-FEE-17-U04 | `beforeLoad` for role student on `/fee/categories` | No redirect (allow-list prefix match) | passing |
| TC-FEE-17-U05 | Mobile `roleBlocksFees("teacher")` | true; false for admin, student, parent | passing |
| TC-FEE-17-U06 | `permissionsMap` with only `fee_terms:list` | Dashboard shown (any of three list grants) | blocked: the dashboard decision is inline in FeeIndexPage in web/src/routes/_app/fee/index.tsx; needs the check exported |
| TC-FEE-17-A01 | Login as Admin, Staff, Teacher, Student, Parent and read the menu and permission list | Admin and Staff have fee resources; Teacher none; Student and Parent only the self-service grants | passing |
| TC-FEE-17-A02 | Grant change then login again | New grants appear only after the new login (permissions are cached at login) | skipped: needs a temporary grant change on the shared Student role, which would race with other workers and is not perm... |

**UI test cases.**

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-FEE-17-E01 | P1 | Web | Admin | None | 1. Open Fee. | "Fee Management Dashboard" with eight cards (Fee Categories, Fee Types, Fee Terms, Fee Mappings, Fee Term Amounts, Fee Collection, Fee Receipts, Fee Refunds); each "Manage" opens its page | passing |
| TC-FEE-17-E02 | P3 | Web | Admin | Seeded class mappings | 1. Click "Manage" on "Fee Term Amounts". | Fee Mappings with the Class Mappings tab and the first row highlighted | planned |
| TC-FEE-17-E03 | P3 | Web | Admin | None | 1. Open `/fees` by URL. | Redirected to `/fee` | planned |
| TC-FEE-17-E04 | P3 | Web | Student | Signed in as seeded student Karthik Reddy | 1. Open Fee. | Cards "My Receipts" and "My Transactions" only | planned |
| TC-FEE-17-E05 | P2 | Web | Teacher | None | 1. Sign in as Teacher.<br>2. Open `/fee` by URL. | Redirected to the Dashboard; no Fee card or sidebar entry | planned |
| TC-FEE-17-E06 | P2 | Web | Staff | None | 1. Sign in as Staff.<br>2. Open Fee and each card. | Dashboard with the eight cards; categories, types and terms open without create, edit or delete controls | planned |
| TC-FEE-17-E07 | P3 | Web | Admin | None | 1. Expand Fee in the sidebar. | Entries from the backend menu: Fee Categories, Fee Types, Fee Terms, Fee Mappings, Term Amounts, Fee Collection, Fee Receipts, Fee Transactions, Fee Refunds, Fee Reports, My Fees, My Receipts | planned |
| TC-FEE-17-E08 | P2 | Mobile | Admin | Signed in to qa_manual | 1. Tap the "Fee Management" card.<br>2. Tap "Fee Term Amounts". | "FEE SECTIONS" with eight tiles; "Fee Term Amounts" opens Fee Mappings on the Class Mappings tab | planned |
| TC-FEE-17-E09 | P3 | Mobile | Teacher | None | 1. Open `/fees`. | Redirected to the Home dashboard; no Fee Management card | planned |
| TC-FEE-17-E10 | P3 | Mobile | Parent | Signed in as the seeded parent of Harsha and Tanvi Raju | 1. Tap the "Fee Management" card. | Hub "Child Fees" with "Child Fee Summary", "My Fees", "My Receipts", "My Transactions" | planned |

API tests implemented in: backend/tests/api/fee/test_fee_menu.py

Implemented in: web/src/__tests__/fee/feeRouteGuard.test.ts (U03, U04) and mobile/__tests__/fee/feeRoleGuard.test.ts (U05) (phase 1 unit cases).

---

## Known gaps

Differences between `docs/modules/fee.md` or the intended behaviour and the code, plus defects found while reading it. Each entry is verifiable in the named file. Defects found during testing are added here.

| Ref | Gap | Where |
|---|---|---|
| K01 | The list endpoints for categories, types and terms accept only `limit` and `offset`. Web sends `academic_year_id`, `skip` and `category_status`, which are ignored, so the pages list every year's rows and a second page repeats the first. Only the dropdowns filter by year | `fee_category_service.py` `get_all_fee_categories`, `fee_term_service.py` `get_all_fee_terms`, `web/src/api/fee/categories.ts`, `terms.ts` |
| K02 | Fixed (2026-10-02): the dropdown accepts the UUID the endpoint already parsed. Was: `GET /fee/types/dropdown?fee_category_id=<uuid>` passes a UUID to `UUID()`, which raises and returns 500; the unfiltered call works | `fee_type_service.py` `get_fee_types_dropdown` |
| K03 | Fixed (2026-10-02): `approve` and `process` no longer require user ids in the body (the token user is used); `refund_method` is required for process and the mobile process modal now sends it; web and mobile cancel call `POST /approve` with `action=reject` and the reason as remarks; the web list sends `offset`, `date_from`, `date_to`; the unused update, delete, by-transaction and bulk client functions were removed. There is still no real cancel state. Was: Both clients call refund routes that do not exist (`PUT` and `DELETE /fee/refunds/{id}`, `POST /{id}/cancel`, `GET /by-transaction/{id}`); mobile approve omits `approved_by_user_id` and process sends `reference_number` without `refund_method` (422). Mobile "Cancel Refund" always fails. No cancel state exists in the backend | `mobile/src/api/fees.ts`, `web/src/api/fee/refunds.ts`, `fee_refund_endpoints.py` |
| K04 | `docs/graph/views/fee.md` says payments fill term amounts "oldest outstanding first"; the code iterates `mapping.term_amounts` without an ORDER BY, which gives date order only because rows are inserted in date order | `fee_collection_service.py` `_process_fee_payment_inner` |
| K05 | Fixed (2026-10-02): `FeeClassMappingUpdate` types `class_id` and `academic_year_id` as UUIDs and the uniqueness check and the `fee_type_id` filter accept UUIDs. Was: `FeeClassMappingUpdate` types `class_id` and `academic_year_id` as integers (422 for UUIDs), and a `fee_type_id` makes `check_mapping_unique` call `UUID()` on a UUID (500). `GET /fee/class-mappings/?fee_type_id=` fails the same way. Only `total_fee` and `all_by_default` are safely updatable; mobile edit sends both UUIDs | `fee_class_mapping_schema.py`, `fee_class_mapping_service.py` |
| K06 | Web "Equal Distribution" of class term amounts can produce unrounded values (333.3333 x 3) that pass the 0.01 frontend check but fail the backend's exact-sum check | `TermAmountModal.tsx`, `fee_class_map_term_amount_service.py` |
| K07 | Mobile old-fee calls use `/fee/old/...` (404) and different field names (carry-forward sends `previous_year_id`, `current_year_id`, `student_ids`), so the mobile Old Fees tab does nothing | `mobile/src/api/fees.ts`, `app/fees/collection/[studentId].tsx` |
| K08 | The web Old Fees tab requests `current_year_id`, which filters `current_academic_year_id`; manual entries store null there, so they are counted in the summary and payment limit but are not shown in the tab | `fee_old_service.py`, `web/src/api/fee/collection.ts` |
| K09 | The pending-fees report and carry-forward ignore concessions: a student with a concession still shows the full instalment pending and a carried-forward amount of `total_fee - paid` | `fee_report_service.py`, `fee_old_service.py` |
| K10 | Audit writes insert into `audit_logs`, which exists in no schema, so no fee audit trail is recorded | `_write_audit_log` in the collection, concession and old-fee services |
| K11 | A cheque or DD payment without `fee_items` marks old fees as paid immediately although the transaction is pending and could bounce | `fee_collection_service.py` |
| K12 | Fixed (2026-10-02): the payment path takes a transaction-scoped Postgres advisory lock per tenant and student, receipt numbering takes a tenant-wide advisory lock, and `idempotency_key` (optional, max 64) on `POST /fee/collection/pay` and `POST /fee/transactions/` derives a deterministic transaction number so a repeat returns the original result. A database unique constraint on receipt numbers already exists on the model. Was: No idempotency key or row lock: duplicate or concurrent payment requests can both succeed while dues remain, and the receipt number is "max plus 1" protected only by a unique constraint, so a collision returns 500 | `fee_collection_service.py`, `fee_receipt_service.py` |
| K13 | Web "New Transaction" sends no `cheque_date`, `cheque_bank` or `bank_name`, which the API requires for cheque and bank transfer, so those methods fail with 422 on that form | `FeeTransactions.tsx`, `fee_transaction_schema.py` |
| K14 | Fixed (2026-10-02): overpay returns 400 with a clear message and the outstanding amount, and items for the same term date are checked cumulatively; `create_business_rule_error` now accepts `details` and `status_code`. The total-mismatch check had the same bug and also returns 400. Was: `POST /fee/transactions`: an overpaying item calls `create_business_rule_error(..., details=...)`, an unsupported keyword, so the caller gets 500 `Failed to validate fee item N` instead of a business-rule error; items for the same term date are validated independently so two items can overpay together | `fee_transaction_service.py`, `error_handler.py` |
| K15 | Fixed (2026-10-02): numbering ignores non-numeric suffixes, compares numerically and skips used numbers. Was: Receipt renumbering accepts any string; a non-numeric suffix with the current month prefix makes the next number generation fail (500) because the suffix is parsed as an integer | `fee_receipt_service.py` |
| K16 | Fixed (2026-10-02): the handler re-raises HTTP errors, so an unknown id is 404. Was: `GET /fee/receipts/{id}/verify` returns 500 for an unknown id (the 404 is swallowed by a broad exception handler) | `fee_receipt_service.py` `verify_receipt_integrity` |
| K17 | Fixed (2026-10-02): lookup is by `transaction_number` in the query (404 when absent). Was: `GET /fee/transactions/transaction-number/{n}` inspects only the first row of an unfiltered search (`limit=1`), so it finds only the newest transaction | `fee_transaction_endpoints.py` |
| K18 | Fixed (2026-10-02): student, admission number and academic year are taken from the transaction; a body value that differs gets 400; the amount check now counts pending refunds and locks the transaction row. Was: `POST /fee/refunds` trusts `student_id`, `student_admission_num` and `academic_year_id` from the body without comparing them to the transaction | `fee_refund_service.py` |
| K19 | Fixed (2026-10-02): `RefundReason` now holds the stored values; the web list sends `offset`, `date_from`, `date_to`. Was: `docs/modules/fee.md` says `RefundReason` is unused; `GET /fee/refunds/` uses it for the `refund_reason` filter, whose values (`adjustment`, `withdrawal`, `excess_payment`, `duplicate_payment`, `error_correction`) do not match the stored ones, so only `excess_payment` can be filtered. The web list also sends `skip`, `start_date`, `end_date`, which the API ignores | `fee_refund_endpoints.py`, `enums.py`, `web/src/api/fee/refunds.ts` |
| K20 | Fixed (2026-10-02): `page`, `page_size` and `sort_order` are validated at the router (422) and bad `date_from` or `date_to` raise 422; export filter validation errors are 422. Was: Report endpoints validate filters inside a broad `try`, so an invalid `page_size`, `sort_order` or date string returns 500 instead of 422 | `backend/app/api/v1/reports/fee_reports.py` |
| K21 | The web Fee Reports page sends no `academic_year_id` (all years are mixed) and disables Export until a filter is set | `FeeReports.tsx` |
| K22 | The Student default seed has no `fee_collection` grant, so `my-summary` and `my-history` return 403 (the web and mobile student pages use `my-outstanding-fees`); mobile `collection.tsx` still calls `my-summary` and `child-summary` without the required `academic_year_id` (422) | `permission_catalog.py`, `mobile/app/fees/collection.tsx` |
| K23 | `docs/modules/fee.md` says Admin and staff collect fees, but the default Staff seed has no `fee_collection` grant (only `fee_transactions`), the web Payment tab gates on `fee_transactions:create` while the API needs `fee_collection:create`, the mobile Fee Collection tile gates on `fee_transactions:list`, and the due-reminder endpoints check `fee_collection:read` rather than the documented `send_sms`. Admin also lacks `send_sms` in the default seed | `permission_catalog.py`, `FeePaymentTab.tsx`, `mobile/app/(tabs)/fees.tsx`, `fee_collection_endpoints.py` |
| K24 | Web Transactions has no Fee dashboard card (the seeded menu gives it a sidebar entry), no control to bounce a payment or set `cheque_status`, and "Mark Completed" leaves `cheque_status` as pending; a cleared cheque also needs a separate "Generate Receipt" click because no receipt is created on status change | `FeeTransactions.tsx`, `fee_transaction_service.py` |
| K25 | A student with more than one admission row makes summary, history and terms-due lookups fail with 500 (`scalar_one_or_none`) | `fee_collection_service.py` |
| K26 | A legacy-mode payment that reduces old fees produces a receipt whose total exceeds the sum of its items because old fee amounts are not receipt items | `fee_collection_service.py`, `fee_receipt_service.py` |
| K27 | Refunds are never subtracted from Paid, the history or the reports, and pending refunds are not counted against the refundable amount | `fee_refund_service.py`, `fee_collection_service.py` |
| K28 | No online payment gateway exists; every payment is recorded by staff (carried over from the module doc) | module-wide |
| K29 | UI-FEE-01: the mandatory class mapping toast says "Fee applied to 0 of 1 students" although the fee was applied (the client bulk call duplicates the backend auto-apply) | `web/src/pages/fee` class mapping dialog |
| K30 | UI-FEE-02: the "Approved By" menu of the first concession row opens upward and is clipped | `web/src/pages/fee` concessions tab |
| K31 | UI-FEE-03: the Fee Summary keeps the old Payable Amount after "Save All Concessions" until the page is reloaded | `web/src/pages/fee` concessions and summary |
