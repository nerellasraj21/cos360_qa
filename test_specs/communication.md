# Communication: feature documentation and test specification

Code: `COM`. Test case IDs: `TC-COM-<FF>-<P><NN>` (U unit, A API, E end-to-end UI). Conventions: `docs/testing/strategy.md`, layout: `docs/features/README.md`. Module rules: `docs/modules/communication.md`. Graph view: `docs/graph/views/communication.md`.

_Last verified against code: 2026-10-02_

## Module overview

Communication lets school staff send outbound messages to parents and staff over three channels: SMS (MSG91 Flow API), WhatsApp (Meta Cloud API) and Email (SendGrid). A message is always built from a saved template with `{{variable}}` placeholders (WhatsApp alone may send free text), addressed to a target audience (individual, a chosen list, a class and section, everybody, or a role), rendered per recipient, written to a queue and delivered later by a Celery worker, which records every outcome in a log. The module also contains the holiday announcement and the "send SMS" triggers that other modules (staff, students, exams, fee) expose; they share the same queue. Only outbound messaging exists: there is no push, no in-app inbox, no inbound handling, no delivery webhooks.

What is real and what is not: the three providers are real HTTP integrations configured only by environment variables (`MSG91_AUTH_KEY`, `WA_PHONE_NUMBER_ID`, `WA_ACCESS_TOKEN`, `SENDGRID_API_KEY` and the per-template MSG91 ids). The QA environment has none of them, and tests must never send real messages: unit tests mock `httpx`, API tests patch `send_notification_batch.delay`, and nothing in phases 2 and 3 reaches a provider. No current SMS producer works end to end even with keys (the DLT ids are never supplied, see F05 and F08), and the holiday announcement queues a single row addressed to nobody (F07). The Celery worker is not part of docker-compose.

## Roles

Backend grants are live `resource_permissions` rows (`docs/permissions.md`); the table shows the **default seed** in `backend/app/service/tenant/permission_catalog.py`. The QA tenant (`qa_school`) must additionally grant `announcements:send_sms`, `staff_attendance:send_sms` and `staff_enrollment:send_sms` to Admin (nothing in the repo seeds any `send_sms` action).

| Role | `communications` | `announcements` | `*:send_sms` |
|---|---|---|---|
| Admin | create, read, update, list (no delete) | none | none |
| Teacher | none | none | none |
| Staff | none | none | none |
| Student | none | none | none |
| Parent | none | none | none |

Notes. Menus: the seed gives Admin, Staff and Teacher every menu, so the Communication menu is visible to Staff and Teacher, but their requests are denied (403) and the web Logs page shows "Access Denied". Student and Parent have no Communication menu on web; the mobile tab is hidden for the role names student, parent, guardian, father and mother and the screen itself shows "Access Restricted - Communication tools are only available to staff and admin." There is no frontend permission cap for `communications` (the Teacher and Staff matrices do not list it). The mobile Communication tab performs no per-action permission check: buttons are shown to every non-student, non-parent role and the server decides.

Per-action independence: `create` (send, create template), `list` (list or get template, preview count, log list), `read` (log detail) and `update` (edit, deactivate) are separate grants.

## Feature index

| ID | Title |
|---|---|
| F01 | Message templates (create, edit, deactivate, activate, defaults) |
| F02 | Recipient targeting and preview count |
| F03 | Compose and send a message |
| F04 | Quick send from module pages |
| F05 | Delivery worker and providers |
| F06 | Message logs |
| F07 | Holiday announcement |
| F08 | Module-triggered SMS and send_sms gating |

Common test data (QA tenant `qa_school`, seeded by the test setup): templates `QA Notice SMS` (sms, body `Dear {{name}}, this is a QA notice.`), `QA Student SMS` (sms, `Dear {{name}}, notice about {{student_name}} of {{class_name}}-{{section_name}}.`), `QA Custom SMS` (sms, `Hello {{name}}, amount {{amount}} due on {{due_date}}.`), `QA Notice Email` (email, subject `Notice for {{name}}`, body `Dear {{name}}, this is a QA notice.`), `QA Notice WhatsApp` (whatsapp, `Dear {{name}}, this is a QA notice.`) and one inactive template `QA Old SMS`; parents `Parent One` (phone `9876511111`, email `parent1@qa.example`, child `Kid One` in class 5 section A), `Parent Two` (no phone, email only), `Parent Three` (phone only, two children in class 5 section A); staff from the staff doc (`Asha Verma`, `Ravi Kumar`, inactive `Meena Rao`); logs seeded directly in the database (sent, failed and queued examples) because no worker runs in QA; a second tenant `qa_school_b`.

---

## F01 Message templates (create, edit, deactivate, activate, defaults)

**Purpose.** Maintain the reusable message bodies, one per channel, that every send is built from.

**Roles and permissions.**
- Create: `communications:create`. List and get: `communications:list`. Edit, deactivate and activate: `communications:update`.
- Web hub card "Templates" and mobile "Templates" tab are visible to every non-student, non-parent role; the create button is shown only with `communications:create` on web (and always on mobile), edit and deactivate need `communications:update` on web.

**Preconditions.** None for creating. The user holds the grant for the action.

**Steps, web.**
1. Communication (`/communication`, "Communication") -> card "Templates" (`/communication/templates`).
2. Filters: "All Channels" (SMS, WhatsApp, Email), "All Status" (Active, Inactive), search "Search templates...". The table has Name, Channel, Variables, Status, Last Modified and Actions.
3. "+ New Template": dialog "New Template" with "Template Name *" (placeholder `e.g. fee_reminder`), Channel radios sms, whatsapp, email (only when creating), "Message Body *" (counter `N / 160 (k credit(s))` for SMS), "Insert Variable" menu (name, parent_name, student_name, staff_name, class_name, section_name, amount, due_date, exam_name, month, date, reason), "Detected variables" badges, a "Live Preview" and, for email, "Subject *". "Save Template". Toast "Template created successfully".
4. Edit icon ("Edit Template", aria label `Edit <name>`): dialog "Edit Template", name and body (and subject for email) can change, the channel cannot; "Save Changes". Toast "Template updated successfully".
5. Trash icon ("Deactivate Template") appears for active templates: dialog "Deactivate Template" ("Are you sure you want to deactivate <name>? It will no longer be available for sending messages.") -> "Deactivate". Toast "Template deactivated". Inactive rows have only the edit icon.
6. "Load Default Templates" creates any of the nine built-in SMS templates (Welcome, Student Absentees, Staff Recruiting, Staff Attendance, Fee Collection, Exam Schedule, Mark Entry, Holiday, Homework Diary) whose name is missing (matched by trimmed lower-case name). Toasts "<n> default template(s) created.", "All default templates already exist.", "Failed to create: <names>", "Could not check existing templates. Please try again."
7. There is **no Activate button** on web or mobile. An inactive template can be reactivated only through `PUT /communication/templates/{id}` with `{"is_active": true}`.

**Steps, mobile.**
1. Communication tab (bottom tabs) -> in-page tab "Templates". Chips for channel and status, "Search templates...", "New Template".
2. "New Template" opens the modal "New Template": "Name *", "Subject *" (email only), "Message Body *", Channel chips (disabled when editing: "Channel cannot be changed on existing templates."), "Save". Toasts "Template Created - New template has been saved.", "Template Updated - Changes have been saved." On failure the generic "Create Failed - Could not create template." or "Update Failed - Could not update template." (the server reason is not shown).
3. Edit and the ban icon ("Deactivate template") with the confirm "Deactivate Template" (`Deactivate "<name>"? It will no longer be available for sending.`), toast "Deactivated - Template has been deactivated."
4. The constant `HIDE_TEMPLATES = true` in `app/(tabs)/communication.tsx` forces both the Templates list and the Compose template dropdown to be empty ("No templates found"), so on mobile templates can be created but not seen, edited, deactivated or used to send (defect D-COM-01).
5. No "Load Default Templates" on mobile.

**Expected results.** A row in `message_templates` with `is_active = true`, `variables` re-derived from the body, unique per `(name, channel)`. Edits change only the sent fields. Deactivation sets `is_active = false`; the row is kept because queue and log rows reference it.

**API endpoints** (clients call the collection with a trailing slash, `/communication/templates/`, which FastAPI redirects).
- `POST /communication/templates` body `{name, channel, body, subject?}` -> 201 `TemplateRead {id,name,channel,body,subject,variables,is_active,updated_at}`.
- `GET /communication/templates?channel=&is_active=` -> plain array ordered by name (no pagination; `page` and `page_size` sent by clients are ignored).
- `GET /communication/templates/{template_id}` -> `TemplateRead`.
- `PUT /communication/templates/{template_id}` body `{name?, body?, subject?, is_active?}` -> `TemplateRead`.
- `DELETE /communication/templates/{template_id}` -> `TemplateRead` with `is_active=false`.

**Rules and validations.**
1. `name`, `channel`, `body` are required on create. `channel` is `sms`, `whatsapp` or `email` (422 otherwise). The backend accepts an empty `name` or `body`; both clients block empty values.
2. `variables` is always re-derived from `body` with the pattern `{{ name }}` (spaces allowed, word characters only), in order of first appearance, de-duplicated. Anything the client sends in `variables` is ignored. Expressions such as `{{ a.b }}` or `{% if %}` do not produce variables. The web and mobile clients detect variables with a stricter pattern (no spaces inside the braces).
3. SMS bodies longer than 480 characters are rejected on create (a Pydantic validation error, HTTP 422, not 400); exactly 480 is accepted. The check is not applied on PUT, and not to WhatsApp or email.
4. `(name, channel)` must be unique (exact, case-sensitive): create returns 400 "Template with name '<n>' already exists for channel '<c>'." The same name may exist on another channel.
5. PUT re-derives `variables` when `body` is sent (an empty variable list when the new body has none). PUT does not re-check name uniqueness or the 480 limit: a name clash ends in a database integrity error (clients see an error response; HTTP 400 through the middleware mapping, the module doc says 500).
6. `channel` cannot be changed (not in the update schema).
7. DELETE is a soft deactivate and is idempotent (a second call returns 200 again).
8. `subject` is stored for email templates but is never used when sending (the email subject is fixed, F05).
9. Template bodies are rendered with an unsandboxed Jinja2 `Template` (server-side template injection for anyone with `communications:create`, see Known gaps).
10. Data is per tenant; the same name may exist in another tenant.

**Error and edge cases.** Unknown or foreign-tenant id: 404 "Template not found."; non-UUID id: 422. Duplicate name on create: 400. Missing token 401; missing grant 403. Inactive templates are listed (filter `is_active=false`) but cannot be sent (F03). Template update uses `commit()` then `refresh()` (known MissingGreenlet workaround; see Known gaps).

**Unit-testable logic.** `_extract_variables` (order, de-duplication, spaces, non-matching forms); `TemplateCreate` validator (480 limit, channel enum, ignores client `variables`); `TemplateUpdate.re_extract_variables`; `create_template` duplicate check; `list_templates` filters and ordering; `deactivate_template`; web `detectVariables`, SMS counter `Math.ceil(len / 160)`, `DEFAULT_COMMUNICATION_TEMPLATES` (nine SMS entries) and the missing-name computation in `handleLoadDefaults`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-01-U01 | `_extract_variables("Hi {{name}}, {{ amount }} {{name}} {{a.b}}")` | `["name", "amount"]` (order kept, duplicate and `a.b` dropped) | passing |
| TC-COM-01-U02 | `TemplateCreate` for an SMS body of 480 and of 481 characters | valid; ValidationError "SMS body exceeds 480 characters (3 SMS credits). Reduce the message length." | passing |
| TC-COM-01-U03 | `TemplateCreate` for a 481-character body on whatsapp and email | valid (limit is SMS only) | passing |
| TC-COM-01-U04 | `TemplateCreate(..., variables=["x"], body="Hi {{name}}")` | `variables == ["name"]` (client value ignored) | passing |
| TC-COM-01-U05 | `TemplateCreate(channel="push")` | ValidationError | passing |
| TC-COM-01-U06 | `TemplateUpdate(body="No vars")` and `TemplateUpdate(name="x")` | `variables == []`; `variables is None` | passing |
| TC-COM-01-U07 | `create_template` with a mocked existing `(name, channel)` | HTTPException 400 "Template with name 'X' already exists for channel 'sms'." | passing |
| TC-COM-01-U08 | `list_templates` with `channel="sms"`, `is_active=False` | statement filters both and orders by name | passing |
| TC-COM-01-U09 | `deactivate_template` twice on a mocked row | `is_active` stays false; no error | passing |
| TC-COM-01-U10 | Web `detectVariables("A {{x}} {{ y }} {{x}}")` | `["x"]` (the spaced form is not detected on the client) | blocked: detectVariables is local to web/src/pages/Communication/TemplatesTab.tsx |
| TC-COM-01-U11 | Web SMS counter for 0, 1, 160, 161, 320, 321 characters | 0, 1, 1, 2, 2, 3 credits (`Math.ceil(n / 160)`; 0 chars shows no credit text) | blocked: the SMS counter is inline in web/src/pages/Communication/TemplatesTab.tsx |
| TC-COM-01-U12 | `DEFAULT_COMMUNICATION_TEMPLATES` | nine entries, all `sms`, unique names | passing |
| TC-COM-01-U13 | `handleLoadDefaults` missing-name logic with existing names " welcome ", "HOLIDAY" | those two (case and whitespace insensitive) are skipped; seven are created | blocked: handleLoadDefaults is inline in web/src/pages/Communication/TemplatesTab.tsx |
| TC-COM-01-A01 | Admin `POST /communication/templates` `{name:"QA Fee SMS", channel:"sms", body:"Dear {{name}}, fee {{amount}} due."}` | 201; `variables ["name","amount"]`, `is_active` true, `subject` null | planned |
| TC-COM-01-A02 | Create an email template with `subject:"Notice for {{name}}"` | 201; `subject` echoed | planned |
| TC-COM-01-A03 | Same `(name, channel)` again; same name on `whatsapp` | 400 "Template with name 'QA Fee SMS' already exists for channel 'sms'."; the second is 201 | planned |
| TC-COM-01-A04 | Boundary: SMS body of 480 and 481 characters | 201; 422 | planned |
| TC-COM-01-A05 | `channel:"push"`; missing `name`; missing `body`; missing `channel` | 422 each | planned |
| TC-COM-01-A06 | Body `{{name}}` with client `variables:["zzz"]` | stored `variables ["name"]` | planned |
| TC-COM-01-A07 | `GET /communication/templates` | 200 plain array ordered by name, includes active and inactive | planned |
| TC-COM-01-A08 | `?channel=email`; `?is_active=false`; `?channel=sms&is_active=true`; `?channel=push` | filtered arrays; `?channel=push` returns `[]` (no validation) | planned |
| TC-COM-01-A09 | `GET /communication/templates/` (trailing slash) | 200 (redirect followed) with the same array | planned |
| TC-COM-01-A10 | `?page=2&page_size=1` | ignored: the full array is returned | planned |
| TC-COM-01-A11 | `GET /communication/templates/{id}`; random uuid; `abc` | 200; 404 "Template not found."; 422 | planned |
| TC-COM-01-A12 | `PUT {body:"Hi {{name}} {{x}}"}` | 200; `variables ["name","x"]`; `updated_at` newer | planned |
| TC-COM-01-A13 | `PUT {name:"Renamed", subject:"S"}` | 200 with the new values | planned |
| TC-COM-01-A14 | `PUT {is_active:false}` then `PUT {is_active:true}` | inactive then active again (the only way to reactivate) | planned |
| TC-COM-01-A15 | `PUT {channel:"email"}` | 200 and the channel is unchanged (field ignored) | planned |
| TC-COM-01-A16 | `PUT` with a name that clashes with another template of the same channel | error response (400 via the integrity-error mapping); record the observed status; the row is unchanged | planned |
| TC-COM-01-A17 | `PUT` an SMS body of 481 characters | 200 (no length check on update, documents the gap) | planned |
| TC-COM-01-A18 | `DELETE /communication/templates/{id}` twice | 200 `TemplateRead` with `is_active` false both times; the row still exists | planned |
| TC-COM-01-A19 | `PUT` and `DELETE` on a random uuid | 404 "Template not found." | planned |
| TC-COM-01-A20 | Admin on all five endpoints | 2xx | planned |
| TC-COM-01-A21 | Staff, Teacher, Student, Parent on all five endpoints | 403 | planned |
| TC-COM-01-A22 | A custom role with only `communications:list`: GET list and get 200, POST 403, PUT 403, DELETE 403 | actions are independent | planned |
| TC-COM-01-A23 | A custom role with only `communications:update`: PUT and DELETE 2xx, GET 403, POST 403 | as stated | planned |
| TC-COM-01-A24 | No token on all five endpoints | 401 | planned |
| TC-COM-01-A25 | Tenant isolation: template created in `qa_school` | absent from `qa_school_b`'s list; GET by id in B 404; the same `(name, channel)` can be created in B | planned |
| TC-COM-01-A26 | Token of tenant A with `cschema: qa_school_b` | 403 | planned |
| TC-COM-01-A27 | Body `{{ 7*7 }}` stored, then a send to one parent | the queued message contains `49` (documents template injection) | planned |
| TC-COM-01-E01 | Web, Admin: New Template `QA Web SMS` (sms) with body `Dear {{name}}, fee {{amount}} due.` | toast "Template created successfully"; row shows Variables "name, amount" and Status Active | planned |
| TC-COM-01-E02 | Web: create the same name and channel again | error toast with the backend text "Template with name 'QA Web SMS' already exists for channel 'sms'." | planned |
| TC-COM-01-E03 | Web: dialog counter for an SMS body of 161 characters | shows "161 / 160 (2 credits)" | planned |
| TC-COM-01-E04 | Web: Insert Variable -> `{{student_name}}` | inserted at the cursor; "Detected variables" shows `student_name` | planned |
| TC-COM-01-E05 | Web: email channel | "Subject *" field appears; saved subject is shown when editing | planned |
| TC-COM-01-E06 | Web: edit name and body, Save Changes | toast "Template updated successfully"; the channel radios are not shown | planned |
| TC-COM-01-E07 | Web: deactivate an active template and confirm | toast "Template deactivated"; Status Inactive; the trash icon disappears; filter "Inactive" lists it | planned |
| TC-COM-01-E08 | Web: Load Default Templates on an empty tenant, then again | "9 default template(s) created." then "All default templates already exist." | planned |
| TC-COM-01-E09 | Web: filters channel "Email" + search "notice" | only matching rows; a status filter "Inactive" shows `QA Old SMS` | planned |
| TC-COM-01-E10 | Web, Staff and Teacher | the Templates page loads but is empty or shows an error (list returns 403); no New Template button | planned |
| TC-COM-01-E11 | Mobile, Admin: Templates tab | shows "No templates found" even though templates exist (D-COM-01) | planned |
| TC-COM-01-E12 | Mobile, Admin: New Template, Save with name `QA Mobile SMS` and a body | toast "Template Created - New template has been saved."; verify through the API that the row exists | planned |
| TC-COM-01-E13 | Mobile: Save with an empty name | toast "Error - Template name is required" | planned |
| TC-COM-01-E14 | Mobile: email channel without a subject | toast "Error - Subject is required for email templates" | planned |
| TC-COM-01-E15 | Mobile, Student and Parent | the tab is hidden; the direct route shows "Access Restricted" | planned |

Implemented in: backend/tests/unit/communication/test_templates.py (U01-U09), web/src/__tests__/communication/defaultTemplates.test.ts (U12).

---

## F02 Recipient targeting and preview count

**Purpose.** Choose who receives a message and see how many recipients the choice resolves to before sending.

**Roles and permissions.** `communications:list` for the preview count (the same grant as listing templates). The resolver itself runs inside the send call (F03, `communications:create`).

**Preconditions.** Parents, students, staff and classes exist (students and staff docs). Parents are linked to students through `student_parent_links`.

**Steps, web.**
1. Communication -> "Compose" (`/communication/compose`). The left column "Target Type" has four buttons: "Parents", "Students", "Staff", "Entire School".
2. Parents or Students: choose "Class" and "Section"; a "Students" checklist appears (badge `selected/total`, "Search name or admission #", "Select all"); all students start selected. For Parents the warning "<n> selected student(s) have no linked parent contact and will be skipped." appears when some students have no parent.
3. Staff: the "Staff" multi-select ("Search and select staff...") lists everyone returned by `GET /staff/` (active and inactive) as `Name (phone)`; below it "<n> staff selected".
4. Entire School: the note "This will send to every parent, student, and staff member in the school."
5. The counter under "Preview & send" shows the resolved number with the label "recipients" ("..." while loading, a dash when no target is complete).

**Steps, mobile.**
1. Communication tab -> Compose -> "2. SELECT RECIPIENTS": "Target Type *" with the same four options, "Class *", "Section *", the Students list with "Search name or admission #", "Staff *" ("Search and select staff..."), and the line "Estimated recipients: ~<n>", "Fetching recipients..." or "Complete fields to see recipient count".

**Expected results.** The clients map the choice to a backend target: Parents -> `multiple_parents` with the parent ids of the checked students (father, mother, guardian and linked parents); Students -> `multiple_students` with the checked student ids; Staff -> `multiple_staff`; Entire School -> `all_users`. The count equals the number of rows the resolver produces for the target, before the channel's missing-contact filter.

**API endpoints.**
- `GET /communication/send/preview-count?target_type=<t>` plus any of `class_id`, `section_id`, `role`, `parent_id`, `student_id`, `staff_id`, `parent_ids` (repeatable), `student_ids` (repeatable), `staff_ids` (repeatable) -> `{estimated_count: n}`.

**Rules and validations.** Targets (`target_type` with `target_ref`):

| target_type | target_ref | resolves to |
|---|---|---|
| `individual_parent` | `parent_id` | that parent |
| `multiple_parents` | `parent_ids[]` | those parents (one row per parent) |
| `individual_student` | `student_id` | the student's linked parents (one row per parent) |
| `multiple_students` | `student_ids[]` | linked parents of each student (one row per parent and student) |
| `individual_staff` | `staff_id` | that staff member (active or not) |
| `multiple_staff` | `staff_ids[]` | those staff members (active or not) |
| `class_section_parents` and `class_section_students` | `class_id`, optional `section_id` | parents of students admitted to that class (and section), one row per parent and student |
| `all_parents` | none | every parent |
| `all_students` | none | linked parents of all students (one row per parent and student) |
| `all_staff` | none | active staff only |
| `all_users` | none | all parents plus active staff, de-duplicated by phone and by email |
| `fee_defaulters` | none | parents of students with a `fee_student_mappings.total_fee > 0` (every student with a fee mapping, paid or not) |
| `role_based` | `role` (role name) | active staff whose user role has that exact name |

1. Students are never contacted directly; student targets resolve to parents. A parent with two selected children appears twice (once per child) so each message can name the child. Only `all_users` de-duplicates.
2. A missing or empty reference (no `parent_id`, no `class_id`, empty id list, unknown role) resolves to zero recipients, not an error.
3. `target_type` must be one of the values above: an unknown value gives 422 on the preview endpoint (`Unknown target_type: '<x>'`) but 500 on the send endpoint (F03).
4. The preview counts every resolved row, including rows without a phone or email, so it can exceed the number actually queued.
5. A student without an admission renders `class_name` and `section_name` as `None` (left joins).
6. Row-level security scopes every query to the tenant.

**Error and edge cases.** Missing `target_type`: 422. Malformed ids in a reference (not UUIDs): database error (500). Missing token 401; missing `communications:list` 403. `role` is case-sensitive: `teacher` finds nobody when the role is `Teacher`.

**Unit-testable logic.** `_resolve_raw` routing table and the unknown-type `ValueError`; each resolver's mapping of rows to recipient dicts (name composition `first + " " + last`, `student_name`, class and section) with a mocked session; `_resolve_all_users` de-duplication by phone and by email (case and whitespace insensitive); `resolve_recipients` filtering (sms and whatsapp need a phone, email needs an email); web and mobile `resolveTarget` and `buildPreviewParams`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-02-U01 | `_resolve_raw(db, "bogus", {})` | raises ValueError "Unknown target_type: 'bogus'" | passing |
| TC-COM-02-U02 | Each resolver called with an empty reference (`{}`) for individual and multiple targets and `class_section_parents`, `role_based` | returns `[]` without touching the database | passing |
| TC-COM-02-U03 | `_resolve_all_users` with parents (A: phone 1, email a@x), staff (phone 1, other email) and staff (phone 2, email A@X) | the first staff row is dropped (same phone), the second is dropped (same email, case-insensitive); one recipient remains plus unrelated ones | passing |
| TC-COM-02-U04 | `_resolve_all_users` with rows with empty phone and email | none is treated as a duplicate of another empty value | passing |
| TC-COM-02-U05 | `resolve_recipients` for channel sms with recipients [phone, no phone, empty string phone] | valid 1, skipped 2 (each skipped gets `skip_reason` "missing_contact") | passing |
| TC-COM-02-U06 | `resolve_recipients` for channel email and whatsapp | email needs `email`; whatsapp needs `phone` | passing |
| TC-COM-02-U07 | Staff name composition for `last_name=None` | `"Asha"` without a trailing space (individual and multiple resolvers); for `all_users` the name is stripped | passing |
| TC-COM-02-U08 | Web `resolveTarget` for ('parents', no parent ids), ('students', ids), ('staff', ids), ('entire_school') | `null`, `multiple_students`, `multiple_staff`, `all_users` with `{}` | blocked: resolveTarget is local to web/src/pages/Communication/SendMessagePanel.tsx |
| TC-COM-02-U09 | Web `buildPreviewParams` for each resolved target | `parent_ids`, `student_ids`, `staff_ids` or only `target_type` for `all_users`; `null` for no target | blocked: buildPreviewParams is local to web/src/pages/Communication/SendMessagePanel.tsx |
| TC-COM-02-U10 | Mobile `resolveTarget` and `buildPreviewParams` | identical results to the web functions | blocked: resolveTarget and buildPreviewParams are local to mobile/app/(tabs)/communication.tsx |
| TC-COM-02-A01 | `all_parents` with `Parent One`, `Parent Two`, `Parent Three` | `{estimated_count: 3}` (parents without a phone are counted) | planned |
| TC-COM-02-A02 | `multiple_parents&parent_ids=<P1>&parent_ids=<P3>` | 2 | planned |
| TC-COM-02-A03 | `individual_parent&parent_id=<P1>`; unknown parent id | 1; 0 | planned |
| TC-COM-02-A04 | `individual_student&student_id=<Kid One>` (one linked parent) | 1 | planned |
| TC-COM-02-A05 | `multiple_students` with the two children of Parent Three | 2 (one row per parent and child) | planned |
| TC-COM-02-A06 | `class_section_parents&class_id=<5>&section_id=<A>` | equals the number of (parent, student) pairs in the section | planned |
| TC-COM-02-A07 | `class_section_students` for the same class and section | same number as `class_section_parents` | planned |
| TC-COM-02-A08 | `class_section_parents&class_id=<5>` without a section | includes every section of class 5 | planned |
| TC-COM-02-A09 | `class_section_parents` without `class_id` | 0 | planned |
| TC-COM-02-A10 | `all_students` | number of distinct (parent, student) rows | planned |
| TC-COM-02-A11 | `all_staff` with 3 staff of whom 1 inactive | 2 | planned |
| TC-COM-02-A12 | `multiple_staff` with the inactive staff id | 1 (inactive staff are included for explicit selection) | planned |
| TC-COM-02-A13 | `all_users` | parents plus active staff with phone or email duplicates removed | planned |
| TC-COM-02-A14 | `fee_defaulters` with one fully paid and one unpaid student, both with `total_fee > 0` | both students' parents counted (proxy rule) | planned |
| TC-COM-02-A15 | `role_based&role=Teacher`; `role=teacher`; `role=Nobody` | number of active staff with role Teacher; 0; 0 | planned |
| TC-COM-02-A16 | Missing `target_type`; `target_type=bogus` | 422 (validation); 422 "Unknown target_type: 'bogus'" | planned |
| TC-COM-02-A17 | `multiple_parents&parent_ids=abc` | non-2xx (database error, 500) | planned |
| TC-COM-02-A18 | Admin on the endpoint | 200 | planned |
| TC-COM-02-A19 | Staff, Teacher, Student, Parent | 403 | planned |
| TC-COM-02-A20 | A custom role with only `communications:create`: preview-count 403 (needs `list`) | as stated | planned |
| TC-COM-02-A21 | No token | 401 | planned |
| TC-COM-02-A22 | Tenant isolation: tenant B calls `all_parents`, `all_staff`, `all_users` | counts of tenant B only (0 for an empty tenant) | planned |
| TC-COM-02-A23 | Token tenant A with `cschema: qa_school_b` | 403 | planned |
| TC-COM-02-E01 | Web, Admin: Compose -> Parents -> class 5, section A | student checklist with all students selected; the counter shows the resolved parent count | planned |
| TC-COM-02-E02 | Web: untick one student | badge `n-1/n`; the counter updates after the request | planned |
| TC-COM-02-E03 | Web: "Select all" off | counter shows a dash (no target) | planned |
| TC-COM-02-E04 | Web: select a student with no linked parent while on Parents | warning "1 selected student has no linked parent contact and will be skipped." | planned |
| TC-COM-02-E05 | Web: Staff -> pick Asha Verma and Ravi Kumar | "2 staff selected"; counter 2 | planned |
| TC-COM-02-E06 | Web: Entire School | the note text is shown and the counter equals the `all_users` count | planned |
| TC-COM-02-E07 | Web: switching Target Type clears class, section, students and staff | selections reset | planned |
| TC-COM-02-E08 | Mobile, Admin: Recipients -> Parents -> class and section | the Students list and "Estimated recipients: ~<n>" | planned |
| TC-COM-02-E09 | Mobile: Staff -> pick two staff | "Estimated recipients: ~2" | planned |
| TC-COM-02-E10 | Mobile: no target chosen | "Complete fields to see recipient count" | planned |

Implemented in: backend/tests/unit/communication/test_recipient_resolver.py (U01-U07).

---

## F03 Compose and send a message

**Purpose.** Send a templated message over SMS, WhatsApp or email to the chosen audience. The API queues the messages and returns at once; delivery is asynchronous (F05).

**Roles and permissions.** `communications:create`. Rate limit: the shared `rate_limit_api()`, 200 requests per minute per IP (the docstring and spec say 10 per minute per user; not implemented). The web "Send Now" button is rendered only with `communications:create`; mobile shows it to every non-student, non-parent role.

**Preconditions.** An active template for the chosen channel (F01) and a resolvable audience (F02). Placeholders other than the four system variables must be supplied by the sender.

**Steps, web.**
1. Communication -> "Compose" (`/communication/compose`).
2. Left column: choose the "Target Type" and the recipients (F02).
3. Top right: choose the channel with the buttons "SMS", "WhatsApp", "Email".
4. Section "1 Context & template": "Context (what this SMS is for)" (General, Exam schedule, Attendance, Fee reminder, Admission, Holiday, Homework; it filters the template list by words in the template name) and "Template" ("Select template..."). Only active templates of the chosen channel are listed. Changing the channel or context clears the template.
5. For each template variable that the page does not treat as a system variable (everything except `name`, `parent_name`, `student_name`, `staff_name`, `class_name`, `section_name`) an input appears; all must be filled.
6. Section "2 Preview & send": the message preview shows system variables as `[name]` and filled values; for SMS the line "<n> chars - <k> SMS credit(s) - Sender: COS360".
7. Click "Send Now" (enabled when a template, a complete target and all inputs are present). There is no confirmation dialog. Toast "<n> messages queued successfully" and the app opens `/communication/logs`. Errors: 429 "Rate limit exceeded. Please wait a moment before sending again.", 403 "Permission denied", otherwise the backend detail or "Failed to send notification".

**Steps, mobile.**
1. Communication tab -> in-page tab "Compose": "1. SELECT CHANNEL" (SMS, WhatsApp, Email), "2. SELECT RECIPIENTS" (F02), "3. SELECT TEMPLATE" ("Template *"), "4. FILL IN VARIABLES" when needed, then "Send Now".
2. "Send Now" opens the modal "Confirm Send" with Channel, Target, Recipients and Template rows, the message preview and the warning "This will queue <n> message(s) and cannot be undone."; "Cancel" or "Confirm & Send" ("Queuing...").
3. Success: toast "Messages Queued - <n> messages queued successfully." and the app switches to the Logs tab. Errors: "Rate Limited - Too many requests. Please wait and try again.", "Permission Denied - You do not have permission to send messages.", "Send Failed - <detail>".
4. Because of `HIDE_TEMPLATES = true` (D-COM-01) the template dropdown is always empty ("No active SMS templates"), so a mobile send cannot be completed.

**Expected results.** The response `{queued_count: n}` is returned immediately. One `notification_queue` row per deliverable recipient is committed with the text already rendered (status `queued`, `triggered_by` = the user id, `target_type`, `target_ref`); a single Celery task `send_notification_batch(queue_ids, channel, tenant_id)` is dispatched. Recipients without a phone (sms, whatsapp) or without an email (email) are dropped silently and not counted, so `queued_count` can be lower than the preview. Recipients whose body fails to render get a `failed` log row immediately (empty message) and are not queued. No message is delivered until a worker runs.

**API endpoints.**
- `POST /communication/send` body `{template_id?, channel?, message?, target_type, target_ref, variables}` -> `{queued_count}` (HTTP 200).

**Rules and validations.**
1. A saved template is required (`template_id`), except for WhatsApp: with `channel: "whatsapp"`, no `template_id` and a non-blank `message`, the free text is rendered as a template. In that mode `target_type` must be one of the plain individual, multiple, class-section and `all_parents`, `all_students`, `all_staff` types (not `all_users`, `fee_defaulters`, `role_based`). Violations are 422 with the messages "template_id is required unless channel is 'whatsapp' with a free-text message.", "message is required for a template-less WhatsApp send.", "target_type '<t>' is not allowed for a template-less WhatsApp send. Allowed: [...]". Neither client exposes free text.
2. With `template_id`, the channel is taken from the template; the request's `channel` is ignored.
3. A missing template is 404 "Template not found."; an inactive template is 400 "Template is inactive and cannot be used for sending."
4. Every placeholder of the template that is not a system variable (`name`, `student_name`, `class_name`, `section_name`) must be a key of `variables`, otherwise 400 "Missing user-provided template variables: ['a', 'b']" (sorted) and nothing is queued. Extra keys are accepted. For free-text WhatsApp no variable check is made.
5. Each message is rendered per recipient with Jinja2: system variables first (`name` is the recipient's name, `student_name`, `class_name`, `section_name` come from the student row or are empty), then `variables`, which may override them. Rendering happens at queue time; later template edits do not change queued messages. A syntax or undefined-attribute error writes a `failed` log (empty `message`, the error text in `error_message`) for that recipient only.
6. Client contract bug: both clients send `extra_variables`, but the backend field is `variables`, so values typed by the user are dropped and any template with a non-system placeholder fails with 400. The clients also treat `parent_name` and `staff_name` as system variables and never ask for them, but the backend does not resolve them.
7. An unknown `target_type` is not validated by the schema (plain string); the resolver's ValueError is not converted, so the endpoint answers 500.
8. If dispatching the Celery task fails the error is logged and swallowed: rows stay `queued` and the call still returns `queued_count`.
9. `fee_defaulters` is a proxy (F02), student and class targets fan out per (parent, student), only `all_users` de-duplicates.
10. Tenant data only; the worker receives the tenant id, never the `cschema` header.

**Error and edge cases.** 422 for schema errors; 400 for an inactive template or missing variables; 404 for an unknown template; 401, 403; 429 after the rate limit; an audience that resolves to nobody returns `queued_count: 0` and no task is dispatched; a student target whose children have no parents queues nothing. `class_name` and `section_name` render `None` for students without an admission. Jinja is unsandboxed (Known gaps).

**Unit-testable logic.** `SendRequest` validators (template-or-WhatsApp rules, allowed targets); `queue_and_dispatch` with mocked resolver and session (inactive template, missing variables, per-recipient rendering, user variable override, failed-log path, dispatch failure swallowed, empty audience, `queued_count`); `_insert_failed_log_sync`; web and mobile `buildPreviewText` and the `isAllFilled` rule; client SMS credit math.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-03-U01 | `SendRequest(target_type="all_parents")` without `template_id` and `channel` | ValidationError "template_id is required unless channel is 'whatsapp' with a free-text message." | passing |
| TC-COM-03-U02 | `SendRequest(channel="whatsapp", message="  ", target_type="all_parents")` | ValidationError "message is required for a template-less WhatsApp send." | passing |
| TC-COM-03-U03 | `SendRequest(channel="whatsapp", message="Hi", target_type="all_users")` and with `fee_defaulters`, `role_based` | ValidationError "target_type '<t>' is not allowed ..." for each | passing |
| TC-COM-03-U04 | The same with `all_staff`, `class_section_parents`, `individual_student` | valid | passing |
| TC-COM-03-U05 | `SendRequest(channel="sms", message="Hi", target_type="all_parents")` (no template) | ValidationError (free text is WhatsApp only) | passing |
| TC-COM-03-U06 | `queue_and_dispatch` with an inactive template (mocked) | HTTPException 400 "Template is inactive and cannot be used for sending." | passing |
| TC-COM-03-U07 | Template variables `["name","amount"]`, `user_vars={}` | HTTPException 400 "Missing user-provided template variables: ['amount']"; nothing added to the session | passing |
| TC-COM-03-U08 | Template variables `["b","a"]` with neither supplied | message lists `['a', 'b']` (sorted) | passing |
| TC-COM-03-U09 | Two recipients, body `Hi {{name}} {{student_name}}`, `user_vars={"student_name":"Override"}` | rendered `Hi P1 Override` and `Hi P2 Override` (user variable wins) | passing |
| TC-COM-03-U10 | Recipient with `class_name=None` and body `{{class_name}}` | renders `None` | passing |
| TC-COM-03-U11 | A body that fails to render for one recipient only, and a body with a syntax error (fails for every recipient) | one `NotificationLog` (status failed, message "", error text) added per failed render; no queue row for it | passing |
| TC-COM-03-U12 | Three recipients, one without phone on channel sms | `queued_count == 2`; the third is dropped silently | passing |
| TC-COM-03-U13 | `send_notification_batch.delay` raising an exception | `queue_and_dispatch` still returns the count; the error is logged | passing |
| TC-COM-03-U14 | Empty audience | returns 0 and never calls `.delay` | passing |
| TC-COM-03-U15 | Free-text WhatsApp send with `message="Hi {{name}}"` | rendered per recipient; no template lookup; channel `whatsapp` | passing |
| TC-COM-03-U16 | Web `buildPreviewText("Hi {{name}} {{amount}}", {amount:"500"})` and with an empty value | `Hi [name] 500`; `Hi [name] [amount]` | blocked: buildPreviewText is local to web/src/pages/Communication/SendMessagePanel.tsx |
| TC-COM-03-U17 | Web `isAllFilled` for a template with variables `amount` (empty, filled), no template, no target | false, true, false, false | blocked: isAllFilled is an inline expression in web/src/pages/Communication/SendMessagePanel.tsx |
| TC-COM-03-A01 | Patch `.delay`. Admin `POST /communication/send` `{template_id:<QA Notice SMS>, target_type:"multiple_parents", target_ref:{parent_ids:[P1]}, variables:{}}` | 200 `{queued_count: 1}`; one queue row: status queued, `rendered_message` "Dear Parent One, this is a QA notice.", `recipient_phone` 9876511111; `.delay` called once with the queue id, "sms", the tenant id | planned |
| TC-COM-03-A02 | `multiple_parents` with `[P1, P2]` where Parent Two has no phone, template sms | `queued_count` 1 (Parent Two skipped, not logged) | planned |
| TC-COM-03-A03 | The same targets with the email template | `queued_count` 2 if both have emails; recipients without email dropped | planned |
| TC-COM-03-A04 | Template `QA Student SMS` to `multiple_students` with the two children of Parent Three | `queued_count` 2 (two rows for one parent); messages name each child and `5-A` | planned |
| TC-COM-03-A05 | Template `QA Custom SMS` without `variables` | 400 "Missing user-provided template variables: ['amount', 'due_date']" | planned |
| TC-COM-03-A06 | Same with `variables:{amount:"500", due_date:"2026-10-31"}` | 200; message "Hello <name>, amount 500 due on 2026-10-31." | planned |
| TC-COM-03-A07 | Same with `extra_variables:{...}` instead of `variables` (the clients' field name) | 400 (the field is ignored; documents D-COM-02) | planned |
| TC-COM-03-A08 | `variables` with a key overriding a system variable, `{"name":"Override"}` | the message uses "Override" | planned |
| TC-COM-03-A09 | Inactive template `QA Old SMS` | 400 "Template is inactive and cannot be used for sending." | planned |
| TC-COM-03-A10 | Random `template_id`; non-UUID `template_id` | 404 "Template not found."; 422 | planned |
| TC-COM-03-A11 | `channel:"email"` sent together with an sms `template_id` | the template's channel (sms) is used; the queue rows have channel sms | planned |
| TC-COM-03-A12 | Missing `target_type`; no `template_id` and no `channel` | 422 each | planned |
| TC-COM-03-A13 | `target_type:"bogus"` with a valid template | 500 (unhandled ValueError); no queue rows | planned |
| TC-COM-03-A14 | Free-text WhatsApp: `{channel:"whatsapp", message:"Hello {{name}}", target_type:"multiple_staff", target_ref:{staff_ids:[Asha]}}` | 200 `queued_count` 1 (phone present); queue row `template_id` null | planned |
| TC-COM-03-A15 | Free-text WhatsApp to `all_users` | 422 "target_type 'all_users' is not allowed for a template-less WhatsApp send. ..." | planned |
| TC-COM-03-A16 | Free text on sms | 422 | planned |
| TC-COM-03-A17 | Template body with a Jinja syntax error `Hi {% if %}` | 200 `queued_count 0`; the log list contains a `failed` entry per recipient with `message` "" and an `error_message` | planned |
| TC-COM-03-A18 | Audience resolving to nobody (`role_based` role "Nobody") | 200 `{queued_count: 0}`; `.delay` not called | planned |
| TC-COM-03-A19 | `.delay` patched to raise | 200 `{queued_count: n}` and the queue rows exist | planned |
| TC-COM-03-A20 | Edit the template after sending | the already queued `rendered_message` is unchanged | planned |
| TC-COM-03-A21 | `all_users` | one queue row per de-duplicated recipient with the needed contact | planned |
| TC-COM-03-A22 | 201 requests from one client IP inside one minute | the 201st returns 429 | planned |
| TC-COM-03-A23 | Admin | 200 | planned |
| TC-COM-03-A24 | Staff, Teacher, Student, Parent | 403 | planned |
| TC-COM-03-A25 | A custom role with only `communications:list`: 403; with only `create`: 200 | as stated | planned |
| TC-COM-03-A26 | No token | 401 | planned |
| TC-COM-03-A27 | Tenant isolation: send in tenant A using a template id of tenant B | 404 "Template not found."; queue rows only in the tenant that sent; tenant B sees none | planned |
| TC-COM-03-A28 | Token tenant A with `cschema: qa_school_b` | 403 | planned |
| TC-COM-03-E01 | Web, Admin: Compose -> Parents -> class 5 / A -> channel SMS -> template `QA Notice SMS` -> Send Now (worker not running) | toast "<n> messages queued successfully"; the app opens `/communication/logs` | planned |
| TC-COM-03-E02 | Web: before choosing a template | "Send Now" is disabled; the preview shows "Select a template to preview the message." | planned |
| TC-COM-03-E03 | Web: choose `QA Custom SMS` and fill "amount" and "due date" | the preview shows the filled values; Send Now becomes enabled; after sending the toast shows the backend error "Missing user-provided template variables: ['amount', 'due_date']" (D-COM-02) | planned |
| TC-COM-03-E04 | Web: channel "WhatsApp" then "Email" | the Template list changes to that channel's active templates; the previous selection is cleared | planned |
| TC-COM-03-E05 | Web: Context "Holiday" | the template list is limited to templates whose name contains "holiday" | planned |
| TC-COM-03-E06 | Web: SMS body of 161 characters | the line "161 chars - 2 SMS credits - Sender: COS360" | planned |
| TC-COM-03-E07 | Web: Staff -> Asha Verma -> `QA Notice SMS` -> Send Now | toast "1 messages queued successfully" | planned |
| TC-COM-03-E08 | Web: Entire School -> `QA Notice Email` | toast with the queued count (recipients without email are excluded) | planned |
| TC-COM-03-E09 | Web: rate limited (backend patched to return 429) | toast "Rate limit exceeded. Please wait a moment before sending again." | planned |
| TC-COM-03-E10 | Web, Staff and Teacher | Compose loads without a Send Now button and with no templates (list 403) | planned |
| TC-COM-03-E11 | Mobile, Admin: SMS, Parents, class, section | the template dropdown shows "No active SMS templates" (D-COM-01); Send Now stays disabled | planned |
| TC-COM-03-E12 | Mobile, Admin: tap Send Now without a target | toast "Error - Please select a target type" | planned |
| TC-COM-03-E13 | Mobile, Student and Parent | no Communication tab; direct route shows "Access Restricted" | planned |

Implemented in: backend/tests/unit/communication/test_send_pipeline.py (U01-U15).

---

## F04 Quick send from module pages

**Purpose.** Send a single templated message from the row of another module (for example "message this staff member") without leaving the page.

**Roles and permissions.** The button renders only with `communications:create` (web `QuickSendButton`). The call is the normal `POST /communication/send`, so the backend applies `communications:create`. Template choices come from `GET /communication/templates` (`communications:list`).

**Preconditions.** An active template of the chosen channel whose name matches the preselected name. For the staff module: `Staff Recruiting` (staff enrollment row) and `Staff Attendance` (staff attendance row), both created by "Load Default Templates".

**Steps, web.**
1. Staff -> Staff Enrollment: click the Send icon of a row ("Send Welcome/Recruiting Message"); or Staff -> Attendance: the Send icon of a non-present row ("Send Attendance Message"; disabled for present staff).
2. Dialog "Send Message" with "To: <name>", "Channel" (SMS, WhatsApp, Email), "Template" (preselected by name: exact match first, then name contains), inputs for placeholders that are not system variables and not prefilled, "Preview" and, for SMS, the character and credit counter. "Cancel" or "Send Now".
3. Other web call sites (documented in the owning modules): admission (Welcome), calendar holiday (Holiday), exam detail and mark entry (Exam Schedule, Mark Entry), fee payment (Fee Collection), student attendance (Student Absentees).

**Steps, mobile.** The button exists on the exam detail screen and the holidays screen only; there is none on the staff screens.

**Expected results.** One message to one recipient through the F03 pipeline; toast "<n> messages queued successfully" and the dialog closes. The staff call sites use `targetType = individual_staff` with `targetRef = {staff_id}`.

**API endpoints.** `GET /communication/templates?channel=sms&page_size=100` and `POST /communication/send` (see F01 and F03).

**Rules and validations.**
1. The client sends `extra_variables`, which the backend ignores (D-COM-02). The default `Staff Recruiting` body uses `{{staff_name}}` and `{{school_name}}`; the backend needs both in `variables`, so the send fails with 400 "Missing user-provided template variables: ['school_name', 'staff_name']". `Staff Attendance` fails the same way (`staff_name`, `date`, `school_name`, `location`). Quick send therefore works only for templates whose placeholders are all system variables.
2. The dialog treats `name`, `parent_name`, `student_name`, `staff_name`, `class_name` and `section_name` as system variables and never asks for them.
3. The `Send` icon is hidden without `communications:create` and disabled for staff rows marked present.

**Error and edge cases.** No active template for the channel: the dialog shows "No active <CHANNEL> templates. Create one in Communication -> Templates." Template not found by name: the picker stays empty and "Send Now" is disabled. Server errors appear as toasts.

**Unit-testable logic.** Template preselection (exact then contains, case-insensitive), `missingVars` computation (non-system, not prefilled), payload construction (system variables filtered out), `canSubmit`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-04-U01 | Preselection with templates ["Staff Recruiting", "Recruiting Notice"] and name "Staff Recruiting"; and with only ["Staff Recruiting 2"] | exact match first; falls back to the contains match | blocked: logic is inline in web/src/components/communication/QuickSendButton.tsx |
| TC-COM-04-U02 | `missingVars` for body variables [staff_name, school_name, date] with prefill {date} | `["school_name"]` | blocked: logic is inline in web/src/components/communication/QuickSendButton.tsx |
| TC-COM-04-U03 | Payload building with merged variables {staff_name, school_name:"QA School"} | system variables are removed, `{school_name:"QA School"}` remains (sent under `extra_variables`) | blocked: logic is inline in web/src/components/communication/QuickSendButton.tsx |
| TC-COM-04-U04 | `canSubmit` for no template, a template with an empty missing variable, a complete state, a pending mutation | false, false, true, false | blocked: logic is inline in web/src/components/communication/QuickSendButton.tsx |
| TC-COM-04-A01 | `POST /communication/send` with the exact payload the dialog builds for `Staff Recruiting` (`extra_variables` only) | 400 "Missing user-provided template variables: ['school_name', 'staff_name']" (D-COM-02) | planned |
| TC-COM-04-A02 | Same send with `variables:{staff_name:"Asha Verma", school_name:"QA School"}` | 200 `queued_count` 1 for an `individual_staff` target with a phone | planned |
| TC-COM-04-A03 | `individual_staff` for a staff member without a phone on sms | 200 `queued_count` 0 | planned |
| TC-COM-04-A04 | `individual_staff` with an unknown staff id | 200 `queued_count` 0 | planned |
| TC-COM-04-A05 | Template list used by the dialog: `GET /communication/templates?channel=sms&page_size=100` | 200 array including inactive rows (the client filters `is_active`) | planned |
| TC-COM-04-A06 | Staff, Teacher, Student, Parent on the send call | 403 | planned |
| TC-COM-04-A07 | No token | 401 | planned |
| TC-COM-04-E01 | Web, Admin: Staff Enrollment, click the Send icon of Asha Verma | dialog "Send Message", "To: Asha Verma", template "Staff Recruiting" preselected, preview with `[...]` placeholders | planned |
| TC-COM-04-E02 | Web: fill "school name" and press Send Now | a toast shows the backend error "Missing user-provided template variables: ['school_name', 'staff_name']" (D-COM-02); the dialog stays open | planned |
| TC-COM-04-E03 | Web: first edit the `Staff Recruiting` template body to `Dear {{name}}, welcome to the team.` (system variables only), then use the Send icon of Asha Verma | toast "1 messages queued successfully"; the dialog closes | planned |
| TC-COM-04-E04 | Web: channel switched to Email with no active email template | text "No active EMAIL templates. Create one in Communication -> Templates." | planned |
| TC-COM-04-E05 | Web, Staff Attendance: present staff row | the Send icon is disabled with the tooltip "Staff is present - no notification needed" | planned |
| TC-COM-04-E06 | Web, Staff Attendance: absent staff row | the icon opens the dialog preselecting "Staff Attendance" | planned |
| TC-COM-04-E07 | Web, Staff role (no `communications:create`) | no Send icon on staff rows | planned |
| TC-COM-04-E08 | Mobile, Admin: the staff screens | no QuickSend button exists | planned |

Implemented in: no unit case of this feature is implemented; all U cases are blocked (see Status).

---

## F05 Delivery worker and providers

**Purpose.** Deliver the queued messages through the real providers and record the outcome of each attempt.

**Roles and permissions.** No user-facing access: the task runs in a Celery worker with its own tenant session. Tests call it directly.

**Preconditions.** A running worker (`celery -A app.celery_app worker`) with Redis, and provider settings in the environment. Neither exists in the QA environment or in docker-compose; without them queue rows stay `queued` and nothing is logged.

**Steps, web.** None (background process). The visible effects are the log rows in F06 once a worker has run.

**Steps, mobile.** None.

**Expected results.** `send_notification_batch(queue_ids, channel, tenant_id)` opens a tenant session, and for each queue id marks the row `processing`, calls the provider, then marks it `done` and writes a `notification_log` row `sent` with `provider_message_id`. On a provider error it writes a `failed` log and re-raises so Celery retries the whole batch (maximum 3 retries, 60 seconds apart, `acks_late`).

**API endpoints.** None. Internal: Celery task `send_notification_batch`, `_process_batch`, `_process_single`, `_call_provider`, `_send_sms`, `_send_whatsapp`, `_send_email`; `msg91_service.normalize_phone`, `build_msg91_payload`, `send_sms_via_msg91`; `sms_templates` registry.

**Rules and validations.**
1. **SMS (MSG91 Flow API).** `POST https://control.msg91.com/api/v5/flow/` with header `authkey`. Requires `MSG91_AUTH_KEY` (else ValueError "MSG91_AUTH_KEY not configured in environment"), a flow template id (`row_data.template_id`, taken from `target_ref.msg91_template_id`, else the queue row's `template_id`), a DLT TE id (`target_ref.dlt_te_id`) and a recipient phone. Positional variables `var1..varN` come from `target_ref.variables`. `MSG91_SENDER_ID` is optional. HTTP status 400 or above, a JSON `type == "error"` and non-JSON replies raise ValueError with the provider text; success returns `request_id` (else `message`, else `sms_sent`). The SMS body stored in the database is only the human-readable copy: MSG91 renders the DLT-registered text, so editing an SMS template body changes the log text but not what recipients receive.
2. **Phone normalisation (SMS).** `normalize_phone` accepts `9876543210`, `+91 98765 43210`, `98765-43210`, `09876543210`, `919876543210`, `0091 9876543210` and returns `919876543210`; a 10-digit number starting 6 to 9 is national even when it begins `91`. Anything else raises ValueError (empty, no digits, wrong length, first digit 0 to 5).
3. **Wiring gap (net effect: no SMS path currently succeeds).** `/communication/send` places the `MessageTemplate` UUID in the queue row's `template_id`, but no row carries `dlt_te_id`; the module triggers and the holiday endpoint omit `dlt_te_id` and use variable orders that differ from `sms_templates.py`. `sms_templates.build_target_ref(key, **values)` produces the right payload but nothing calls it. The registry entry `hall_ticket` has no body yet.
4. **WhatsApp (Meta Cloud API v17.0).** Requires `WA_PHONE_NUMBER_ID` and `WA_ACCESS_TOKEN` (else ValueError "WA_PHONE_NUMBER_ID or WA_ACCESS_TOKEN not configured"). Sends a free-form `text` message, which Meta delivers only inside the 24-hour customer-service window (approved Meta templates are not implemented). Phone handling: a leading `+` is removed; a number that does not start with `91` gets the `91` prefix, so a 10-digit number that starts with `91` is not prefixed (defect). Returns the first message id or `wa_sent`.
5. **Email (SendGrid).** Requires `SENDGRID_API_KEY` (else ValueError "SENDGRID_API_KEY not configured"). `EMAIL_FROM` defaults to `noreply@example.com` and `EMAIL_FROM_NAME` to `COS360`. The subject is fixed as "Notification from COS360" (the template subject is rendered and discarded), the body is sent as `text/html` without escaping. Returns the `X-Message-Id` header or `email_sent`.
6. An unknown channel raises ValueError "Unknown channel: '<c>'". An invalid queue id string or a queue id not visible to the tenant is skipped with a log entry.
7. A provider error rolls back the whole batch transaction: the `failed` log row and the status change are lost, rows already sent earlier in the batch are reset to `queued` and are re-sent on retry, and after 3 retries nothing is persisted. Nothing checks that a row is already `done` before sending.
8. No delivery receipts or webhooks exist: `delivered` is never set. No queue pruning job exists.
9. Providers are called with `httpx` (30 second timeout), one request per recipient, inside a thread executor.

**Error and edge cases.** Broker unreachable: `/communication/send` swallows the error (rows stay queued), the module triggers and the holiday endpoint return 500 after committing their rows. Provider outage, invalid credentials, unapproved DLT template, exhausted credits: surfaced only as the error text of a `failed` log that is then rolled back.

**Unit-testable logic.** `normalize_phone`, `build_msg91_payload`, `send_sms_via_msg91` (mock `httpx.Client`), `SmsTemplate.build_variables`, `render`, `is_registered`, `build_target_ref`, `get_template`; `_send_whatsapp` payload and phone rule; `_send_email` payload; `_call_provider` routing; `_process_single` and `_process_batch` with a mocked session; the retry wrapper `send_notification_batch` (mock `self.retry`).

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-05-U01 | `normalize_phone` for "9876543210", "+91 98765 43210", "98765-43210", "09876543210", "919876543210", "0091 9876543210" | "919876543210" for all six | passing |
| TC-COM-05-U02 | `normalize_phone("9199887766")` (10 digits starting 91) | "919199887766" (treated as national) | passing |
| TC-COM-05-U03 | `normalize_phone` for "", "abc", "12345", "5876543210", "98765432101" | ValueError each ("Phone number is empty", "contains no digits", "Invalid Indian phone number", "Not a valid Indian mobile", "Invalid Indian phone number") | passing |
| TC-COM-05-U04 | `build_msg91_payload("T1", "919876543210", {"var1":"A"}, "1007...", sender="COS360")` | `{template_id:"T1", DLT_TE_ID, short_url:"0", realTimeResponse:"1", recipients:[{mobiles, var1:"A"}], sender:"COS360"}` | passing |
| TC-COM-05-U05 | `build_msg91_payload` with an empty template id, empty phone, empty DLT id, and variables containing `mobiles` | ValueError each ("template_id is required", "phone is required", "dlt_te_id is required - DLT template is mandatory", "'mobiles' is reserved ...") | passing |
| TC-COM-05-U06 | `send_sms_via_msg91` with `MSG91_AUTH_KEY` unset | ValueError "MSG91_AUTH_KEY not configured in environment" | passing |
| TC-COM-05-U07 | `send_sms_via_msg91` rows missing `template_id`, `dlt_te_id`, `recipient_phone` | ValueError for each ("template_id not found in row_data", "dlt_te_id not found in row_data - DLT template is mandatory", "recipient_phone not found in row_data") | passing |
| TC-COM-05-U08 | Mocked MSG91 replies: HTTP 400 text, JSON `{"type":"error","message":"Bad"}`, non-JSON 200, `{"type":"success","request_id":"R1"}`, `{"message":"M1"}`, `{}` | ValueError "MSG91 HTTP 400: ...", ValueError "MSG91 error: Bad", ValueError "MSG91 returned non-JSON response: ...", "R1", "M1", "sms_sent" | passing |
| TC-COM-05-U09 | `httpx.RequestError` raised by the client | ValueError "MSG91 request failed: ..." | passing |
| TC-COM-05-U10 | `SmsTemplate.build_variables` for `staff_attendance` with all four values, with one missing, with an extra name | `{var1..var4}`; ValueError "is missing variable(s)"; ValueError "does not declare variable(s)" | passing |
| TC-COM-05-U11 | `build_variables` for `hall_ticket` (no body) | ValueError "has no body defined yet" | passing |
| TC-COM-05-U12 | `render` for `holiday` with `holiday_date="2026-10-02"` | body with the single placeholder replaced | passing |
| TC-COM-05-U13 | `is_registered` with env ids unset, only the flow id set, both set (monkeypatched env) | false, false, true | passing |
| TC-COM-05-U14 | `build_target_ref("staff_attendance", staff_name="A", attendance_date="d", school_name="S", location="L")` | `{msg91_template_id, dlt_te_id, variables:{var1..var4}}` | passing |
| TC-COM-05-U15 | `get_template("nope")` | KeyError listing the available keys | passing |
| TC-COM-05-U16 | `_send_whatsapp` without env | ValueError "WA_PHONE_NUMBER_ID or WA_ACCESS_TOKEN not configured" | passing |
| TC-COM-05-U17 | `_send_whatsapp` phone handling for "+919876543210", "9876543210", "919876543210", "9112345678" (env set, mocked httpx) | `to` is "919876543210", "919876543210", "919876543210", "9112345678" (the last is not prefixed: documents the defect); payload `type` is "text" | passing (the 9112345678 case asserts current behaviour, defect D-COM-07) |
| TC-COM-05-U18 | `_send_whatsapp` reply with and without `messages` | the first message id; `wa_sent` | passing |
| TC-COM-05-U19 | `_send_email` without `SENDGRID_API_KEY` | ValueError "SENDGRID_API_KEY not configured" | passing |
| TC-COM-05-U20 | `_send_email` payload (mocked httpx, env set) | subject "Notification from COS360", content type `text/html`, from `EMAIL_FROM` or `noreply@example.com`; returns `X-Message-Id` or `email_sent` | passing |
| TC-COM-05-U21 | `_call_provider("push", {})` | ValueError "Unknown channel: 'push'" | passing |
| TC-COM-05-U22 | `send_notification_batch` where `_process_batch` raises | `self.retry` is called with `countdown=60` | passing |
| TC-COM-05-A01 | Insert a queue row (sms, recipient phone, `target_ref` with template id and DLT id) and run `_process_batch` with `_call_provider` patched to return "REQ1" | queue row `done`; one `notification_log` row `sent` with `provider_message_id` "REQ1" and the rendered message | planned |
| TC-COM-05-A02 | Same with `_call_provider` raising ValueError("boom") | the task raises; after the rolled-back transaction no log row exists and the queue row is `queued` again (documents rule 7) | planned |
| TC-COM-05-A03 | Batch of two rows where the second fails | the first row's `done` state and its log are rolled back too; both are `queued` | planned |
| TC-COM-05-A04 | Run the task for a queue id of tenant A with tenant B's id | the row is not visible; skipped with a warning; no log written | planned |
| TC-COM-05-A05 | Queue id "not-a-uuid" | skipped; no exception | planned |
| TC-COM-05-A06 | Real `_send_sms` with no provider settings in the QA environment | ValueError "MSG91_AUTH_KEY not configured in environment" and the same rollback result as A02 | planned |
| TC-COM-05-A07 | Rows produced by `/communication/send` for sms (template UUID, no DLT id) processed with a patched `msg91` HTTP client | fails with "template_id not found" or "dlt_te_id not found in row_data" (documents rule 3) | planned |
| TC-COM-05-E01 | Web, Admin, no worker running: send from Compose, then open Logs | the send toast appears; the Logs list shows no new rows (rows remain queued) | planned |
| TC-COM-05-E02 | Web: with the QA seeded logs (sent, failed) | Logs shows "Sent" and "Failed" badges (see F06); no UI can start the worker | planned |

Implemented in: backend/tests/unit/communication/test_providers.py.

---

## F06 Message logs

**Purpose.** Audit what the system tried to send: one row per recipient and attempt, with its status, recipient, rendered text and provider reference.

**Roles and permissions.** List: `communications:list`. Detail: `communications:read`. Web: the Logs page is guarded by `communications:list` ("Access Denied" otherwise). Mobile: the Logs tab is shown to every non-student, non-parent role; the API decides.

**Preconditions.** Log rows exist. They are written by the worker (F05), by the render-failure path of F03 and by the fee summary SMS. In QA, where no worker runs, rows are seeded directly into `notification_log`.

**Steps, web.**
1. Communication -> "Logs" (`/communication/logs`).
2. Filters: "All Channels", "All Status" (Queued, Sent, Delivered, Failed), "From" and "To" dates. There is no target-type filter on the page (the API supports it).
3. Columns: Recipient (name and phone or email), Channel, Status badge, Target Group (the target type with spaces), Triggered By (user id), Date/Time, Actions. 20 rows per page, "Showing a-b of N" and page buttons.
4. The View icon ("View log for <name>") opens "Notification Detail": Recipient, Channel, Phone, Email, Status, Provider ID, Triggered By, Target Group, Sent At, an "Error" box when present and the "Message" text.

**Steps, mobile.**
1. Communication tab -> "Logs": channel and status dropdowns ("All Channels", "All Status"), "From" and "To" fields in `YYYY-MM-DD`, cards with recipient, channel chip, status chip, target group, phone or email and date; the eye icon ("View log detail") opens "Log Detail" with Recipient, Channel, Phone, Email, Status, Target Group, Triggered By, Provider ID, Sent At, Error and Message; pagination arrows with "a-b of N".

**Expected results.** Newest first. `status` is one of `queued`, `sent`, `delivered`, `failed`; in practice only `sent` and `failed` are written (`delivered` needs webhooks, which do not exist). Phone numbers and emails are shown in full (the masking in the spec is not implemented).

**API endpoints.**
- `GET /communication/logs?channel=&status=&target_type=&date_from=&date_to=&page=1&page_size=20` -> `{items:[LogRead], total, page, page_size}`.
- `GET /communication/logs/{log_id}` -> `LogRead {id, template_id, recipient_name, recipient_phone, recipient_email, channel, message, status, provider_message_id, error_message, triggered_by, target_type, target_ref, created_at}`.

**Rules and validations.**
1. `page >= 1`, `1 <= page_size <= 100` (422 otherwise).
2. Sort is `created_at` descending.
3. `date_from` and `date_to` are compared as raw strings against the timestamp column; `date_to=2026-10-02` means up to midnight at the start of that day, so rows created later on 2 October are excluded (no end-of-day handling). A value that is not a date or timestamp, or an invalid `status` or `channel`, fails in the database (500).
4. `target_ref` is a JSON object; the mobile type declares it as a string and `updated_at` that the API does not return (typing drift only).
5. A failed render row has an empty `message` and the render error in `error_message`.
6. Logs are tenant scoped by row-level security.

**Error and edge cases.** Unknown id: 404 "Log entry not found."; non-UUID id: 422. Empty result: `{items: [], total: 0, ...}` and the clients show "No logs found." Missing token 401; missing grant 403.

**Unit-testable logic.** Filter building in `list_logs_endpoint`; `LogListResponse` and `LogRead` schemas (enum values, nullable fields); web `STATUS_CONFIG` badge mapping and pagination arithmetic (`Math.ceil(total / 20)`, range text); mobile `STATUS_COLORS`, `formatDate`, filter object construction.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-06-U01 | `LogRead` validation with `status="delivered"` and `status="processing"` | valid; ValidationError | passing |
| TC-COM-06-U02 | `LogRead` with all nullable fields missing | valid (only id, channel, message, status, triggered_by, target_type, created_at are required) | passing |
| TC-COM-06-U03 | Web pagination for total 41 and page 3 | `totalPages` 3; text "Showing 41-41 of 41" | blocked: pagination arithmetic is inline in web/src/pages/Communication/LogsTab.tsx |
| TC-COM-06-U04 | Web `StatusBadge` mapping for sent, delivered, failed, queued, and an unknown status | labels Sent, Delivered, Failed, Queued; unknown shows the raw text | blocked: STATUS_CONFIG and StatusBadge are not exported from web/src/pages/Communication/LogsTab.tsx |
| TC-COM-06-U05 | Mobile `getLogs` parameter cleaning for `{channel:"", status:undefined, page:1}` | only `page` is sent | passing |
| TC-COM-06-A01 | Seed 25 logs. Admin `GET /communication/logs` | 200; 20 items; `total` 25; `page` 1; `page_size` 20; ordered by `created_at` descending | planned |
| TC-COM-06-A02 | `?page=2` | 5 items | planned |
| TC-COM-06-A03 | `?page_size=100`; `?page_size=101`; `?page_size=0`; `?page=0` | 200; 422; 422; 422 | planned |
| TC-COM-06-A04 | `?channel=sms`; `?status=failed`; `?target_type=multiple_parents` | only matching rows; `total` reflects the filter | planned |
| TC-COM-06-A05 | `?date_from=2026-10-01&date_to=2026-10-03` | rows created in the range; a row at 2026-10-03 10:00 is excluded (midnight boundary) | planned |
| TC-COM-06-A06 | `?date_from=abc`; `?status=bogus`; `?channel=bogus` | 500 (database error), no data | planned |
| TC-COM-06-A07 | A render-failure log created through F03 (`Hi {% if %}`) | listed with `status` failed, `message` "", non-empty `error_message`, `provider_message_id` null | planned |
| TC-COM-06-A08 | `GET /communication/logs/{id}` | 200 `LogRead` including `target_ref` as an object | planned |
| TC-COM-06-A09 | Random id; `abc` | 404 "Log entry not found."; 422 | planned |
| TC-COM-06-A10 | Phone and email in the response | complete values, not masked (documents the gap) | planned |
| TC-COM-06-A11 | Admin | list and detail 200 | planned |
| TC-COM-06-A12 | Staff, Teacher, Student, Parent | 403 on both | planned |
| TC-COM-06-A13 | A custom role with only `communications:list`: list 200, detail 403; with only `read`: detail 200, list 403 | as stated | planned |
| TC-COM-06-A14 | No token | 401 on both | planned |
| TC-COM-06-A15 | Tenant isolation: tenant A logs absent from tenant B's list; detail by id in B returns 404 | as stated | planned |
| TC-COM-06-A16 | Token tenant A with `cschema: qa_school_b` | 403 | planned |
| TC-COM-06-E01 | Web, Admin: Logs with seeded rows | table shows Recipient, Channel, Status, Target Group, Triggered By, Date/Time; newest first | planned |
| TC-COM-06-E02 | Web: filter "Failed" | only failed rows; page resets to 1 | planned |
| TC-COM-06-E03 | Web: filter by channel "Email" and a date range | matching rows only | planned |
| TC-COM-06-E04 | Web: View a failed row | dialog "Notification Detail" with the "Error" box text and the Message | planned |
| TC-COM-06-E05 | Web: pagination Next and Previous with 25 rows | page 2 shows "Showing 21-25 of 25" | planned |
| TC-COM-06-E06 | Web: tenant without logs | "No logs found." | planned |
| TC-COM-06-E07 | Web, Staff and Teacher | "Access Denied - You don't have permission to view communication logs." | planned |
| TC-COM-06-E08 | Mobile, Admin: Logs tab, filter status "Failed", open the eye icon | "Log Detail" shows the error text | planned |
| TC-COM-06-E09 | Mobile: enter `From` as `2026-10-01` | list filtered; the API receives `date_from` | planned |
| TC-COM-06-E10 | Mobile: after a send the app switches to Logs | the tab is active and the list refetches | planned |

Implemented in: backend/tests/unit/communication/test_logs_and_triggers.py (U01-U02), mobile/__tests__/communication/communicationApi.test.ts (U05).

---

## F07 Holiday announcement

**Purpose.** An administrator announces a school holiday by SMS to all parents.

**Roles and permissions.** `announcements:send_sms` (a resource that no seed grants; the QA tenant adds it for Admin). Mobile admin hub card "Announcements" requires `announcements:send_sms`; the screen itself accepts `read` or `list` on `announcements`. Web has no UI.

**Preconditions.** The user holds `announcements:send_sms`.

**Steps, web.** Not available (no web screen).

**Steps, mobile.**
1. Admin tab (`app/(tabs)/admin.tsx`) -> card "Announcements" ("Send holiday notices via SMS to all parents") -> screen "Announcements" with the banner "Holiday Announcement".
2. Fill "Holiday Name *" (placeholder "e.g. Independence Day"), "Holiday Date *" (placeholder `YYYY-MM-DD`) and "Reason *" (placeholder "e.g. National holiday"). When all three are filled a "Message Preview" shows `School will remain closed on <date> for <name>.` with the "COS360" sign-off.
3. Tap "Send to All Parents" ("Sending..."). Toast "Announcement Queued - Holiday announcement queued: <name> on <date>." and the form clears. Client checks: "Holiday name is required", "Holiday date must be in YYYY-MM-DD format", "Reason is required"; server errors show "Send Failed - <detail>" or "Could not send holiday announcement."

**Expected results.** One `notification_queue` row is committed: `recipient_name` "All Parents", **no phone**, channel `sms`, `target_type` `holiday_announcement`, `rendered_message` the sentence above, `target_ref {msg91_template_id: <env MSG91_TEMPLATE_ID_HOLIDAY or null>, variables: {var1: holiday_name, var2: holiday_date, var3: reason}}`. A Celery task is dispatched for that single row. The row has no recipient number and no DLT id, so even with provider credentials the worker cannot deliver it ("recipient_phone not found in row_data"): no parent receives anything. The announcement is therefore a queued record only.

**API endpoints.**
- `POST /announcements/send-holiday-notice?holiday_name=&holiday_date=&reason=` (query parameters, no body) -> `{"status": "queued", "detail": "Holiday announcement queued: <name> on <date>."}`.

**Rules and validations.**
1. `holiday_name`, `holiday_date` and `reason` are required query parameters (422 when missing). No date format or length validation on the server.
2. The message text does not include `reason`; it is only sent as `var3`.
3. The `.delay()` call is not guarded: a missing broker returns 500 after the row is committed.
4. The tenant id (not the `cschema` header) is passed to the worker.
5. One row is created per call regardless of the number of parents (no fan-out).

**Error and edge cases.** Missing parameters 422; no token 401; no grant 403. Repeated calls queue repeated rows.

**Unit-testable logic.** Message construction; `target_ref` shape (`var1..var3` order); mobile `DATE_RE` and `isFormValid`; `announcementsApi.sendHolidayNotice` passes parameters as query string.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-07-U01 | Endpoint message text for ("Independence Day", "2026-08-15", "National holiday") | contains "School will remain closed on 2026-08-15 for Independence Day." and does not contain the reason | passing |
| TC-COM-07-U02 | Mobile `DATE_RE` for "2026-08-15", "15-08-2026", "2026-8-5", "" | match, no match, no match, no match | blocked: DATE_RE is local to mobile/app/admin/announcements.tsx |
| TC-COM-07-U03 | Mobile `isFormValid` for each missing field | false when any of the three is empty or the date is malformed | blocked: isFormValid is local to mobile/app/admin/announcements.tsx |
| TC-COM-07-U04 | `announcementsApi.sendHolidayNotice` request shape (mocked axios) | `POST` with `null` body and `params {holiday_name, holiday_date, reason}` | passing |
| TC-COM-07-A01 | Patch `.delay`. Admin (with `announcements:send_sms`) `POST /announcements/send-holiday-notice?holiday_name=Independence%20Day&holiday_date=2026-08-15&reason=National%20holiday` | 200 `{"status":"queued","detail":"Holiday announcement queued: Independence Day on 2026-08-15."}`; one queue row with recipient "All Parents", `recipient_phone` null, `target_type` "holiday_announcement", `target_ref.variables {var1:"Independence Day", var2:"2026-08-15", var3:"National holiday"}`; `.delay` called once with ([id], "sms", tenant id) | planned |
| TC-COM-07-A02 | Missing each parameter in turn | 422 each | planned |
| TC-COM-07-A03 | `holiday_date=not-a-date` | 200 (no server validation) | planned |
| TC-COM-07-A04 | Env `MSG91_TEMPLATE_ID_HOLIDAY` unset | `target_ref.msg91_template_id` is null | planned |
| TC-COM-07-A05 | `.delay` patched to raise | 500; the queue row is already committed | planned |
| TC-COM-07-A06 | Process the produced row with the real `_send_sms` (credentials mocked) | fails: "template_id not found in row_data" or "dlt_te_id not found in row_data" (the message can never be delivered) | planned |
| TC-COM-07-A07 | A JSON body instead of query parameters | 422 (parameters missing) | planned |
| TC-COM-07-A08 | Admin without `announcements:send_sms` (default seed) | 403 | planned |
| TC-COM-07-A09 | Staff, Teacher, Student, Parent | 403 | planned |
| TC-COM-07-A10 | No token | 401 | planned |
| TC-COM-07-A11 | Tenant isolation: the queue row exists only in the calling tenant; the worker call uses that tenant id | tenant B sees no row | planned |
| TC-COM-07-E01 | Mobile, Admin with the grant: fill the form and tap "Send to All Parents" | toast "Announcement Queued - Holiday announcement queued: <name> on <date>."; the form clears | planned |
| TC-COM-07-E02 | Mobile: empty "Holiday Name" | the send button is disabled; tapping shows "Error - Holiday name is required" when forced | planned |
| TC-COM-07-E03 | Mobile: date "15-08-2026" | "Error - Holiday date must be in YYYY-MM-DD format" | planned |
| TC-COM-07-E04 | Mobile: message preview appears only when all three fields are filled | preview shows `School will remain closed on <date> for <name>.` | planned |
| TC-COM-07-E05 | Mobile, Admin without `announcements:send_sms` | the Announcements card is hidden on the Admin hub | planned |
| TC-COM-07-E06 | Mobile, Staff, Teacher, Student, Parent | no card; opening `/admin/announcements` directly shows the access-denied panel | planned |
| TC-COM-07-E07 | Web | no menu entry or route for announcements exists | planned |

Implemented in: backend/tests/unit/communication/test_logs_and_triggers.py (U01), mobile/__tests__/communication/communicationApi.test.ts (U04).

---

## F08 Module-triggered SMS and send_sms gating

**Purpose.** Let other modules send a purpose-built SMS (staff attendance summary, interview call, absence alerts and so on) through the shared queue, protected by a dedicated `send_sms` permission on the module's resource.

**Roles and permissions.** Each endpoint checks `<resource>:send_sms` and nothing else. No seed grants any `send_sms` action, so every endpoint answers 403 until a tenant admin grants it. This feature covers the two triggers that live in the staff router; the others are owned by their modules.

| Endpoint | Resource:action | Owner doc |
|---|---|---|
| `POST /staff/send-attendance-summary` | `staff_attendance:send_sms` | this doc |
| `POST /staff/send-interview-calls` | `staff_enrollment:send_sms` | this doc |
| `POST /student/attendance/send-absence-alerts` | `student_attendance:send_sms` | `docs/features/students.md` |
| `POST /students/admission/send-confirmation` | `student_admissions:send_sms` | `docs/features/students.md` |
| `POST /students/homework/send-reminders` | `student_homework:send_sms` | `docs/features/students.md` |
| `POST /exams/{exam_id}/send-results-notification`, `/send-hall-ticket-notification`, `/dates/send-schedule` | `exams:send_sms` | `docs/features/exam.md` |
| `POST /fee/collection/send-receipt-sms` | `fee_collection:send_sms` | `docs/features/fee.md` |
| Fee receipt SMS after payment (`send_sms` flag of `POST /fee/collection/pay`) and `POST /fee/collection/summary/{student_id}/send-sms`: synchronous provider calls, not queued | see the fee doc | `docs/features/fee.md` |

**Preconditions.** The user holds the `send_sms` grant for the endpoint. Staff ids refer to rows in `staff` (the "candidates" of the interview endpoint are staff ids too).

**Steps, web.** No client calls these endpoints. The web staff screens use QuickSend (F04) instead.

**Steps, mobile.** No client calls these endpoints.

**Expected results.** For each staff id with a phone number one queue row is added (status `queued`, channel `sms`) and a single task is dispatched; the response lists how many were queued and skipped. Staff without a phone, unknown ids and any per-row exception are counted as skipped.

**API endpoints.**
- `POST /staff/send-attendance-summary?period=<text>` body `[<staff uuid>, ...]` (a JSON array) -> `{status:"queued", queued_count, skipped_count, detail}`.
- `POST /staff/send-interview-calls?interview_date=<text>&interview_time=<text>&position=<text>` body `[<staff uuid>, ...]` -> same response shape.

**Rules and validations.**
1. `period` (attendance summary) and `interview_date`, `interview_time`, `position` (interview) are required query parameters (422 when missing); they are free text, not parsed.
2. The body is a bare JSON array of UUIDs (not an object).
3. The queue row stores `recipient_name` as `"<first> <last>"`; for a staff member without a last name this yields `"<first> None"` (defect). `target_type` is `staff_attendance_summary` or `interview_call`; the text is hard-coded: "Dear <name>, your <period> attendance summary is ready on the portal. View on the app." or "Dear <name>, your interview for <position> is on <date> at <time>." with the "COS360" sign-off.
4. `target_ref` holds `msg91_template_id` from `MSG91_TEMPLATE_ID_STAFF_ATTENDANCE` or `MSG91_TEMPLATE_ID_STAFF_INTERVIEW` (the SMS registry names the latter `MSG91_TEMPLATE_ID_STAFF_RECRUITING`) and `variables` `var1..var2` (name, period) or `var1..var4` (name, date, time, position). No `dlt_te_id` is set, and the variable lists do not match the `sms_templates` registry (`staff_attendance` expects name, attendance date, school name, location), so the provider rejects these rows.
5. A missing broker makes `.delay` raise and the endpoint returns 500 after committing the rows (unlike `/communication/send`, which swallows it).
6. Nothing is logged for skipped staff.

**Error and edge cases.** An empty array returns `queued_count 0`, `skipped_count 0` and dispatches nothing. A non-array body is 422. Missing token 401; missing `send_sms` grant 403 (also for Admin in the default seed). `triggered_by` is the caller's user id.

**Unit-testable logic.** Queue row construction (`target_type`, `target_ref`, message text); skip accounting (no phone, unknown id); the name composition with a null last name; the registry mismatch between endpoint variables and `sms_templates.SmsTemplate.variables`.

**Test cases.**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-COM-08-U01 | Name composition for staff with `last_name=None` | `"Ravi None"` (documents the defect; expected `"Ravi"`) | passing (asserts current behaviour, defect D-COM-05) |
| TC-COM-08-U02 | Registry check: `staff_attendance` variables versus the endpoint's `var1..var2` | the registry has 4 variables, the endpoint sends 2 (mismatch documented) | passing |
| TC-COM-08-U03 | Message text for `period="July"` and for the interview inputs | the sentences from rule 3 with the values inserted | passing |
| TC-COM-08-A01 | Patch `.delay`. Admin with the grant: `POST /staff/send-attendance-summary?period=July` body `[<Asha>, <Ravi>]` | 200 `{status:"queued", queued_count:2, skipped_count:0, detail:"SMS queued for 2 staff. 0 skipped."}`; two rows with `target_type` "staff_attendance_summary", `target_ref.variables {var1:<name>, var2:"July"}`; `.delay` called once with the two ids, "sms", the tenant id | planned |
| TC-COM-08-A02 | A staff id without a phone, an unknown uuid and a valid one | `queued_count` 1, `skipped_count` 2 | planned |
| TC-COM-08-A03 | `[]` | 200 `queued_count` 0, `skipped_count` 0; `.delay` not called | planned |
| TC-COM-08-A04 | Missing `period`; body `{}` instead of an array; body with a non-UUID | 422 each | planned |
| TC-COM-08-A05 | `.delay` patched to raise | 500; the rows remain committed | planned |
| TC-COM-08-A06 | Interview: `POST /staff/send-interview-calls?interview_date=2026-10-10&interview_time=10:30 AM&position=Teacher` body `[<Asha>]` | 200 `queued_count` 1, detail "SMS queued for 1 candidate(s). 0 skipped."; row `target_type` "interview_call", variables `var1..var4` | planned |
| TC-COM-08-A07 | Interview without `position`; without `interview_time`; without `interview_date` | 422 each | planned |
| TC-COM-08-A08 | Env `MSG91_TEMPLATE_ID_STAFF_ATTENDANCE` unset | `target_ref.msg91_template_id` null | planned |
| TC-COM-08-A09 | Process a produced row with the real `_send_sms` (credentials mocked) | fails: "dlt_te_id not found in row_data" | planned |
| TC-COM-08-A10 | Admin without the grant (default seed) on both endpoints | 403 | planned |
| TC-COM-08-A11 | `staff_attendance:send_sms` granted but not `staff_enrollment:send_sms`: attendance summary 200, interview 403 | the resources are independent | planned |
| TC-COM-08-A12 | Staff, Teacher, Student, Parent on both endpoints | 403 | planned |
| TC-COM-08-A13 | No token | 401 on both | planned |
| TC-COM-08-A14 | Tenant isolation: staff ids from tenant A sent with a tenant B token | `queued_count` 0, `skipped_count` equal to the ids count; no rows in either tenant | planned |
| TC-COM-08-A15 | The other trigger endpoints listed in the table (student, exam, fee) without their `send_sms` grant | 403 each (parametrised gating check; their own behaviour is tested in their feature docs) | planned |
| TC-COM-08-E01 | Web and mobile: search for any control that calls the two staff endpoints | none exists; the staff pages offer only QuickSend (F04) | planned |
| TC-COM-08-E02 | Web, Admin: Staff Attendance row Send icon for an absent staff member | opens QuickSend, not the attendance-summary endpoint (confirm through the network log that `/staff/send-attendance-summary` is not called) | planned |

Implemented in: backend/tests/unit/communication/test_logs_and_triggers.py.

---

## Known gaps

Findings from reading the code. The module doc `docs/modules/communication.md` agrees with the code unless stated.

**Defects**
- D-COM-01: mobile `app/(tabs)/communication.tsx` hard-codes `HIDE_TEMPLATES = true`, so the Templates list and the Compose template dropdown are always empty and a mobile send cannot be completed.
- D-COM-02: both clients send `extra_variables`; the backend field is `variables`. Every template with a placeholder other than `name`, `student_name`, `class_name`, `section_name` fails with 400 "Missing user-provided template variables: [...]", including all nine default templates (Compose and QuickSend). The clients also treat `parent_name` and `staff_name` as system variables, which the backend never resolves.
- D-COM-03: `POST /communication/send` with an unknown `target_type` returns 500 (the resolver's ValueError is not converted); the preview endpoint returns 422 for the same input.
- D-COM-04: the holiday announcement queues a single row with no recipient phone and no DLT id and the message cannot be delivered; the endpoint reports "queued".
- D-COM-05: `/staff/send-attendance-summary` and `/staff/send-interview-calls` build names as `"<first> <last>"`, which yields "<first> None" for staff without a last name, and their MSG91 payloads do not match the `sms_templates` registry.
- D-COM-06: no SMS path currently succeeds (flow id from environment, no DLT id anywhere, `/communication/send` passes the template UUID as the flow id).
- D-COM-07: WhatsApp phone normalisation does not prefix a 10-digit number that starts with `91`.

**Doc versus code differences (code behaviour is documented above)**
- The module doc says SMS bodies over 480 characters are "rejected" on create; the validator raises a Pydantic error, so the API answers 422 (the code comment says 400).
- `docs/permissions.md` section 9 lists `communications`, `staff_attendance` and `school_settings` as missing from the Admin default; the current `ROLE_PERMISSIONS` does contain `communications` (create, read, update, list) and `staff_attendance`, but still no `*:send_sms`, no `announcements` and no `profile` for Admin.
- Module doc rule 13 says PUT may end in a 500 on a name clash; the middleware documentation in `docs/architecture.md` maps integrity errors to 400. Record the observed status in TC-COM-01-A16.

**Known behaviours kept from the module doc**
- Skipped recipients are not logged and not counted; the preview counts them.
- Worker failures roll back the batch (failed log lost, earlier rows re-sent on retry, rows stay `queued` after 3 retries); no check of `status == done` before sending.
- Jinja2 renders template bodies with the unsandboxed `Template` (server-side template injection for any user with `communications:create`).
- Email subject is fixed ("Notification from COS360"); the template subject is rendered and discarded; the body is sent as unescaped HTML.
- WhatsApp sends free-form text, which Meta delivers only inside the 24-hour window.
- Rate limit is 200 per minute per IP, not 10 per minute per user.
- `fee_defaulters` targets every student with a fee mapping, paid or not; student and class targets fan out per (parent, student).
- No delivery status, read receipts, opt-out, scheduled sends, manual resend, attachments, phone masking or push notifications; `delivered` is never written.
- Template list ignores `page` and `page_size`; the clients call the collection with a trailing slash.
- There is no Activate action in either client; reactivation is API-only.
- The Celery worker and Redis are not in docker-compose; without them queue rows stay `queued`.
- `GET /communication/logs` compares `date_to` as a string against a timestamp (end of day excluded) and fails with 500 on malformed filter values.
- Mobile Communication tab has no per-action permission checks (only the role-name check).
