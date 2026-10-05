# Authentication and sessions (AUTH)

Authentication and session handling for every tenant user of COS360: how a user picks the organisation (tenant) and academic year, signs in with a username, email or staff phone number, is forced to replace a temporary password on first login, receives a permission map and a role-based menu, keeps a session across reloads and app restarts, renews expired access tokens, switches between children (parents), views and edits their own profile, changes their password, and signs out. It also covers the API-only access-validation helpers. Platform super admin sign-in and tenant-admin password resets belong to `docs/features/tenants-and-admin.md` (TEN). Module rules and gotchas: `docs/modules/auth.md`; system design: `docs/architecture.md`, `docs/permissions.md`. Conventions and test case IDs: `docs/testing/strategy.md`, `docs/features/README.md`.

_Last verified against code: 2026-10-02_

## Roles

| Role | What it does in this module |
|---|---|
| Admin | Signs in (never forced to change password), views its own account on the Admin Profile page, changes its own password (needs `profile:update_own`), signs out |
| Staff | Signs in (forced password change on first login), own profile (email, phone), change password through the API |
| Teacher | Same as Staff; the profile endpoints record the audit profile type as `unknown` |
| Student | Signs in (forced password change on first login), own profile (email only), own-scope permissions |
| Parent | Signs in (forced password change on first login), own profile (email, phone, occupation), child selection, `*_related` permissions |
| Custom roles | Sign in, receive permissions and menu; never forced to change password; `entity_id` is the staff record id when one exists, else null |
| Anonymous | Organisation detection, academic year list, login, set-password (with change-password token), refresh (with refresh token), logout (with token) |

Test fixtures used below: the QA tenant `qa_school`, one QA login per role (credentials from `backend/.env.test`, never written in documents), a second tenant `qa_school_b` created by the test setup through `POST /super_admin/system/tenants/`, and two academic years in `qa_school` (one active, one not). "Header" means the `cschema` request header.

## Feature index

| ID | Title |
|---|---|
| F01 | Organisation (tenant) selection |
| F02 | Academic year selection |
| F03 | Login |
| F04 | First-login forced password change |
| F05 | Permission loading |
| F06 | Role-based menu |
| F07 | Session persistence and route guards |
| F08 | Token refresh and expiry |
| F09 | Parent child selection |
| F10 | Own profile view and edit |
| F11 | Change password (self-service) |
| F12 | Forgot and reset password |
| F13 | Access validation helpers (API only) |
| F14 | Logout |

## F01 Organisation (tenant) selection

### Purpose
Tell the backend which school the user belongs to before anyone is signed in, and keep every later request bound to that school.

### Roles and permissions
No permission: all roles and anonymous users. Nothing is shown in the menu.

### Preconditions
The tenant exists in `public.tenants` with `is_active = true` (created by TEN F07). Web needs a hostname or `VITE_DEFAULT_TENANT` that equals the tenant `client_name`.

### Steps, web
1. Open the web app on a school host such as `school1.example.com`. There is no organisation field on the web login page: the tenant is the first label of the hostname (`getTenantFromHostname`), after dropping a leading `www.`. A host without a dot (`localhost`) uses `VITE_DEFAULT_TENANT` (`qa_school` in the test environment).
2. The browser sends it as the `cschema` header only on requests that carry no access token: `/auth/login`, `/auth/academic-years`, `/auth/refresh`, `/auth/staff/set-password`. Authenticated requests send no header.

### Steps, mobile
1. Open the app with no stored organisation. The screen "Select Organization" shows the text "Enter your organization name to get started", a field labelled "Organization" (placeholder "Enter organization name") and the button "Continue".
2. Type the organisation code (the app lowercases and trims it) and tap "Continue". The app calls `GET /auth/academic-years` with that code as `cschema`.
3. On success the code is stored (AsyncStorage `@auth/client_schema`) and the sign-in form opens with the read-only field "Organization Name".
4. On a 404 the text "Organisation not found. Check the name and try again." appears; on any other failure "Could not reach the server. Check your connection and try again."
5. From the sign-in form, "Change Organization" returns to step 1.

### Expected results
Web: the login page loads the academic years of the tenant named by the hostname. Mobile: an unknown code is never stored; a known code is stored and the sign-in form opens. After login both clients drop the header on authenticated calls.

### API endpoints
| Method and path | Notes |
|---|---|
| any request, header `cschema: <client_name>` | Read by `TenantMiddleware`; used before login |
| `GET /auth/academic-years` | Public; doubles as the "does this organisation exist" probe (404 when it does not) |

### Rules and validations
- Header sanitising (`TenantMiddleware.sanitize_client_name`): lowercase, trim, remove every character outside `a-z 0-9 _ -`, accept 1 to 100 characters, otherwise `None` which gives 400 "Invalid 'cschema' header". So `QA_School` becomes `qa_school` and `qa school` becomes `qaschool`.
- Priority in `extract_client_name`: header, then an `Authorization: Bearer` token (tenant comes from the token), then, only when `TENANT_STRICT_MODE` is off, the subdomain of the `Host` header (at least three dot-separated parts, first part matching `^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$`), then the default tenant only if `TENANT_ALLOW_DEFAULT_FALLBACK` is on. Defaults: strict on, fallback off, so a request with neither header nor token is rejected ("Tenant must be specified via 'cschema' header").
- Errors raised inside `TenantMiddleware` are not turned into JSON by FastAPI; they surface as a plain 500 (`docs/architecture.md` section 4).
- Unknown or inactive `client_name`: 404 "Tenant '<name>' not found or inactive". The lookup is cached 60 seconds per process.
- With a token: the signed `tenant_id` wins. A header that resolves to a different tenant gives 403 "Tenant does not match your session"; an inactive tenant gives 401 "Invalid connection"; a token without `tenant_id` gives 401 "Your session is out of date. Please log in again."
- `/health`, `/docs`, `/redoc`, `/openapi.json`, `/favicon.ico` bypass tenant detection.

### Error and edge cases
- Header made only of invalid characters (`!!!`): rejected as above.
- Header longer than 100 characters after cleaning: rejected.
- Web on `127.0.0.1`: the regex takes `127` as the tenant, which does not exist (404).
- Mobile: the stored organisation is removed by logout and by a failed token refresh, so the user is asked again.

### Unit-testable logic
`TenantMiddleware.sanitize_client_name`, `is_valid_subdomain`, `extract_from_subdomain`, `extract_client_name` priority; web `getTenantFromHostname`; mobile lowercase and trim of the typed code.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-01-U01 | `sanitize_client_name("QA_School")` | `qa_school` | passing |
| TC-AUTH-01-U02 | `sanitize_client_name("  Abc-1 ")` | `abc-1` | passing |
| TC-AUTH-01-U03 | `sanitize_client_name("little bunny")` | `littlebunny` (spaces removed) | passing |
| TC-AUTH-01-U04 | `sanitize_client_name("!!!")` and `""` and `None` | `None` for each | passing |
| TC-AUTH-01-U05 | `sanitize_client_name` with 100 and 101 letters | 100 letters returned unchanged; 101 letters returns `None` | passing |
| TC-AUTH-01-U06 | `extract_from_subdomain("school1.cos360.com")`, `("localhost:8000")`, `("a.b")` | `school1`; `None`; `None` | passing |
| TC-AUTH-01-U07 | `is_valid_subdomain` with `-bad`, `bad-`, `ok-1`, 63 chars, 64 chars, empty | False, False, True, True, False, False | passing |
| TC-AUTH-01-U08 | `extract_client_name` with header and Bearer token both present | header value returned; detection method `cschema_header` | passing |
| TC-AUTH-01-U09 | `extract_client_name` with only a Bearer token | returns `None`; detection method `token` | passing |
| TC-AUTH-01-U10 | `extract_client_name` with nothing, strict mode on | raises HTTPException 400 "Tenant must be specified via 'cschema' header" | passing |
| TC-AUTH-01-U11 | `extract_client_name` with strict off, Host `school1.cos360.com` | `school1` | passing |
| TC-AUTH-01-U12 | `extract_client_name` with strict off, no usable host, fallback on, default `default` | `default` | passing |
| TC-AUTH-01-U13 | `extract_client_name` with strict off, no usable host, fallback off | raises HTTPException 400 "No valid tenant specified. Please provide 'cschema' header" | passing |
| TC-AUTH-01-U14 | Web `getTenantFromHostname`: `school1.abc.com`, `www.school1.abc.com`, `localhost`, `127.0.0.1` | `school1`; `school1`; default tenant; `127` | passing |
| TC-AUTH-01-U15 | `TenantService.get_tenant_id` caches a hit for 60 s and drops a miss (fake clock, fake session) | second call inside 60 s does not query; call after 61 s queries again; a miss is not cached | passing |
| TC-AUTH-01-A01 | `GET /auth/academic-years` with header `cschema: qa_school`, no token | 200; JSON array of `{id, title, is_active}` | planned |
| TC-AUTH-01-A02 | Same call with header `QA_School` | 200; same list (header sanitised) | planned |
| TC-AUTH-01-A03 | Header `no_such_school` | 404; detail "Tenant 'no_such_school' not found or inactive" | planned |
| TC-AUTH-01-A04 | Header `!!!` | request rejected, no data returned (status 500 today, intended 400 "Invalid 'cschema' header") | planned |
| TC-AUTH-01-A05 | No header and no token | request rejected, no data returned (status 500 today, intended 400 "Tenant must be specified via 'cschema' header") | planned |
| TC-AUTH-01-A06 | Header `qa school` (with a space) | 404 for tenant `qaschool` (documents that spaced names cannot be addressed) | planned |
| TC-AUTH-01-A07 | Deactivate `qa_school_b` (TEN F09), then `GET /auth/academic-years` with header `qa_school_b` | 404 "Tenant 'qa_school_b' not found or inactive" | planned |
| TC-AUTH-01-A08 | Admin token of `qa_school` plus header `qa_school_b` on `GET /admin/users/` | 403 "Tenant does not match your session" | planned |
| TC-AUTH-01-A09 | Admin token of `qa_school` plus header `qa_school` | 200 | planned |
| TC-AUTH-01-A10 | Admin token of `qa_school` with no header | 200; data belongs to `qa_school` | planned |
| TC-AUTH-01-A11 | Token of `qa_school_b`, then deactivate `qa_school_b`, then `GET /admin/users/` in the same process | 401 "Invalid connection" | planned |
| TC-AUTH-01-A12 | Valid signed token with no `tenant_id` claim (legacy token) | 401 "Your session is out of date. Please log in again." | planned |
| TC-AUTH-01-A13 | Users with the same username in `qa_school` and `qa_school_b`; list users with each tenant's token | each list contains only its own tenant's user (tenant isolation) | planned |
| TC-AUTH-01-E01 | Web: open `/login` on host `localhost` (default tenant `qa_school`) | the Academic Year select lists the `qa_school` years, the active one marked "(Current)" | planned |
| TC-AUTH-01-E02 | Mobile: first launch, type `NoSuchSchool`, tap "Continue" | text "Organisation not found. Check the name and try again." shown; nothing stored; still on "Select Organization" | planned |
| TC-AUTH-01-E03 | Mobile: type ` QA_School ` (spaces, capitals), tap "Continue" | sign-in form opens; "Organization Name" shows `qa_school` and is not editable | planned |
| TC-AUTH-01-E04 | Mobile: on the sign-in form tap "Change Organization", enter `qa_school_b`, "Continue" | academic years of `qa_school_b` replace the previous ones | planned |
| TC-AUTH-01-E05 | Mobile: stop the backend, tap "Continue" with a valid code | text "Could not reach the server. Check your connection and try again." | planned |

Implemented in: `backend/tests/unit/auth/test_auth_tenant_detection.py` (U01-U13, U15); `web/src/__tests__/auth/tenantAndGuards.test.ts` (U14).

## F02 Academic year selection

### Purpose
Choose the academic year to work in while signing in. The choice is mandatory and is written into the session.

### Roles and permissions
No permission for `GET /auth/academic-years` (public). All roles pick a year at login. The web side effect on Admin login needs `academic_years:update` (it is made with the Admin's own token).

### Preconditions
At least one `academic_years` row in the tenant (TEN F07 creates a default active year; more come from the Masters module).

### Steps, web
1. On `/login` the select "Academic Year" shows "Loading years..." while the list loads, then options such as `2026-2027 (Current)`; the active year (or else the first one) is preselected. Placeholder "Select academic year".
2. Change the selection if needed. The "Login" button is disabled while years load.
3. After signing in, the navbar shows a "Year" dropdown (placeholder "Select Academic Year") that changes the year used by pages; it is client state kept in `localStorage['academic-year-storage']`.
4. Admin only: on a successful login the app calls `PUT /masters/academic_years/{id}` with `{is_active: true}`, and the backend deactivates every other year.

### Steps, mobile
1. On the sign-in form tap the "Academic Year" field. A picker "Select Academic Year" lists the years with a "Current" badge on the active one; "No academic years available" with a retry button appears when none load.
2. Pick a year. The active year is preselected when the form opens.
3. Tapping "Sign In" with no year selected shows "Please select an academic year", or "Could not load academic years. Tap to retry." when the list is empty.

### Expected results
The year id and title are stored as `academic_year_id` and `academic_year_title` in both tokens and in the login response. The backend does not use the claim to scope any query.

### API endpoints
| Method and path | Request fields | Notes |
|---|---|---|
| `GET /auth/academic-years` | none (header `cschema`) | Returns `[{id, title, is_active}]` ordered by `start_date` descending |
| `POST /auth/login` | `academic_year_id` (UUID, required) | See F03 |

### Rules and validations
- `academic_year_id` is a required UUID in `LoginRequest`: missing, empty string or a non-UUID gives 422. A well-formed id that does not exist gives 400 "Invalid academic year" (checked after the password, so a wrong password still gives 401).
- The 400 "Academic year is required" in `MultiTenantAuthService.login_user` is not reachable through the endpoint because the schema rejects the missing field first.
- Refresh keeps the same year claims.
- Admin login on web activates the chosen year for the whole tenant (`docs/modules/auth.md` rule 10).

### Error and edge cases
- Tenant with no academic years: list is `[]`; web login sends no year and gets 422 ("Field required"); mobile blocks submit.
- Past year chosen by an Admin on web: that year becomes the tenant's only active year.
- The web navbar "Year" selection is independent of the year inside the token.

### Unit-testable logic
`LoginRequest` validation; web `AcademicYearDropdown` fallback rule (empty, `371` or id shorter than 10 characters is replaced by the current or first year); `useAcademicYearStore` persisted-state sanitising; mobile `applyAcademicYears` (array, `items`, `results` shapes; preselect active else first).

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-02-U01 | `LoginRequest` without `academic_year_id` | validation error "Field required" | passing |
| TC-AUTH-02-U02 | `LoginRequest` with `academic_year_id=""` and `"abc"` | validation error for each (invalid UUID) | passing |
| TC-AUTH-02-U03 | `LoginRequest` with a valid UUID string | model valid; value is a `UUID` | passing |
| TC-AUTH-02-U04 | `AcademicYearOption` serialisation of `{id, title, is_active}` | JSON has exactly those three keys | passing |
| TC-AUTH-02-U05 | Web store initial value when `localStorage` holds id `371` or `abc` | entry removed; selected id is `""` | passing |
| TC-AUTH-02-U06 | Mobile `applyAcademicYears` with `[]`, plain array, `{items:[...]}`, `{results:[...]}` | selected id `""`; active year id; same; same | blocked: applyAcademicYears is inline in mobile/app/login.tsx and not exported |
| TC-AUTH-02-A01 | `GET /auth/academic-years` with two years (2025-2026 inactive, 2026-2027 active) | 200; order 2026-2027 first (start_date desc); `is_active` true only for 2026-2027 | planned |
| TC-AUTH-02-A02 | Same call without any token | 200 (public endpoint) | planned |
| TC-AUTH-02-A03 | Login with the id of the inactive year | 200; response `academic_year_title` is `2025-2026`; decoded access token has the same `academic_year_id` | planned |
| TC-AUTH-02-A04 | Login without `academic_year_id` | 422; detail lists field `academic_year_id` | planned |
| TC-AUTH-02-A05 | Login with `academic_year_id` "" | 422 | planned |
| TC-AUTH-02-A06 | Login with a random UUID that is not a year of the tenant | 400 "Invalid academic year" | planned |
| TC-AUTH-02-A07 | Login with year id of tenant `qa_school_b` against `qa_school` | 400 "Invalid academic year" (tenant isolation) | planned |
| TC-AUTH-02-A08 | Wrong password plus random year UUID | 401 "Invalid Credentials" (password is checked first) | planned |
| TC-AUTH-02-A09 | Login, then `POST /auth/refresh` | refresh response carries the same `academic_year_id` and `academic_year_title` | planned |
| TC-AUTH-02-A10 | Years of `qa_school_b` listed with header `qa_school` | none of the `qa_school_b` titles appear | planned |
| TC-AUTH-02-A11 | Admin login with the inactive year id, then list academic years (Masters) | the chosen year is the only one with `is_active` true (side effect made by the web client; reproduce with `PUT /masters/academic_years/{id}` `{is_active: true}`) | planned |
| TC-AUTH-02-E01 | Web: open `/login` | select shows the active year preselected and labelled "(Current)"; button "Login" enabled after the list loads | planned |
| TC-AUTH-02-E02 | Web: choose the older year, log in as Admin, open Masters > Academic Years | the older year is now active | planned |
| TC-AUTH-02-E03 | Web: log in as Teacher with the older year | session works; the Masters academic year list still shows the same active year (only Admin activates) | planned |
| TC-AUTH-02-E04 | Web: after login change the navbar "Year" dropdown and reload | the choice is kept (`academic-year-storage`) | planned |
| TC-AUTH-02-E05 | Mobile: tap the "Academic Year" field | modal "Select Academic Year" lists years; active one has a "Current" badge; picking one closes it and shows its title | planned |
| TC-AUTH-02-E06 | Mobile: tenant with no academic years, tap "Sign In" | text "Could not load academic years. Tap to retry." under the field | planned |

Implemented in: `backend/tests/unit/auth/test_auth_login_schemas.py` (U01-U04); `web/src/__tests__/auth/academicYearStore.test.ts` (U05).

## F03 Login

### Purpose
Sign in with a username, email or staff phone number and receive tokens, the user's role, permissions and menu.

### Roles and permissions
No permission: every active tenant user (Admin, Staff, Teacher, Student, Parent, custom roles). Super admins use TEN F02.

### Preconditions
Active tenant (F01), an academic year (F02), a user created by staff enrolment, student admission, parent creation or provisioning (TEN F07). Usernames: staff and teacher use email, or phone when there is no email; students use the admission number; parents use email, or `<admission_no>.father` / `<admission_no>.mother`; the first Admin is whatever the super admin supplied.

### Steps, web
1. Open `/login`. The card "Welcome!" shows "Academic Year", "Username / Admission Number" (placeholder "Username or Admission Number"), "Password" (placeholder "Enter Password", eye button with label "Show password"/"Hide password"), the button "Login" and the link "Forgot your password?".
2. Enter the credentials and press "Login" (the button reads "Logging in..." while waiting).
3. On success the app goes to `/dashboard`. If the response asks for a password change, see F04.
4. On failure a red banner shows the backend text, for example "Invalid Credentials".

### Steps, mobile
1. Complete F01 and F02 steps, then fill "Username" (placeholder "Enter your username") and "Password" (placeholder "Enter your password", eye toggle).
2. Tap "Sign In". Local checks: "Username is required", "Password is required", "Password must be at least 6 characters", "Organization name is required".
3. On success the app opens the tabs (`/(tabs)`); a red banner shows backend errors.

### Expected results
Response 200 body (`LoginResponse`): `user{id, username, email, is_active}`, `role{id, name, description}`, `menu`, `permissions`, `entity_id`, `academic_year_id`, `academic_year_title`, `access_token`, `refresh_token`, `token_type: "bearer"`, `expires_in: 86400`, `tenant_id`, `client_name`. Tokens are stored by the client (F07).

### API endpoints
| Method and path | Request fields that matter |
|---|---|
| `POST /auth/login` | `username`, `password`, `academic_year_id`, optional `client_name`; header `cschema` |

### Rules and validations
- Identifier lookup in order: `users.username`, then `users.email`, then `staff.phone` joined to `users`. Matching is exact and case sensitive; the value is not trimmed.
- Unknown user, inactive user and wrong password all return 401 "Invalid Credentials".
- Order of checks: tenant, credentials, menu and permissions load, academic year (400 "Invalid academic year"), first-login challenge (F04), then token issue.
- Tokens: HS256, access 24 h (`expires_in` 86400), refresh 7 d, claims `sub`, `username`, `role` (role name), `tenant_id`, `client_name`, `academic_year_id`, `academic_year_title`, `exp`, `token_type`. No permissions or `user_type` inside.
- Body `client_name`: must resolve to the same tenant as the header or login returns 400 "Tenant does not match the request"; an unknown body value gives 401 "Invalid connection". Neither client sends it.
- `entity_id`: student record id for `Student`, parent record id for `Parent`, staff record id for any other role that has a staff record, else `null`.
- No lockout and no rate limit on tenant login; the password policy applies only when a password is set (minimum 8 characters).
- Passwords are bcrypt hashes (`passlib`).

### Error and edge cases
- Two staff rows with the same phone number: the lookup raises and the response is 500 "Authentication error".
- Missing header and token: rejected before the endpoint (F01).
- Deactivated user holding an old access token keeps API access until the token expires (the token is not re-checked against `users.is_active`), but cannot refresh (F08).
- A login without header but with a body `client_name` is still rejected by the middleware in strict mode.

### Unit-testable logic
`MultiTenantAuthService.authenticate_user` lookup order and the identical 401 for the three failure cases (fake session); `_resolve_entity_id` model choice per role; `create_access_token` / `create_refresh_token` claims and lifetimes; `verify_password`; `LoginRequest`, `LoginResponse` schemas; web `useAuthStore.login` mapping; mobile `validateForm` messages.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-03-U01 | `authenticate_user` with a user matching by username and a different user whose email equals the same text | the username match wins | passing |
| TC-AUTH-03-U02 | `authenticate_user` identifier equals a staff phone only | the user joined through `staff.phone` is returned | passing |
| TC-AUTH-03-U03 | `authenticate_user` for unknown identifier, inactive user, wrong password | HTTPException 401 "Invalid Credentials" each time | passing |
| TC-AUTH-03-U04 | `create_access_token({"sub":"u1"})` | decodes with `token_type=access` and `exp` about 86400 s ahead (tolerance 5 s) | passing |
| TC-AUTH-03-U05 | `create_refresh_token` | `token_type=refresh`, `exp` about 7 days ahead | passing |
| TC-AUTH-03-U06 | `verify_access_token` with a refresh token and with a change-password token | HTTPException 401 "Invalid token type" for each | passing |
| TC-AUTH-03-U07 | `verify_access_token` with a token signed with another secret, and with an expired token | HTTPException 401 "Invalid token" for each | passing |
| TC-AUTH-03-U08 | `_resolve_entity_id` for role names Student, Parent, Staff, Admin, custom | model used is Student, Parent, Staff, Staff, Staff; returns `None` when no row | passing |
| TC-AUTH-03-U09 | `LoginResponse` default `expires_in` and `token_type` | 86400 and `bearer` | passing |
| TC-AUTH-03-U10 | Web `useAuthStore.login` with role `Student` and `entity_id` set | `studentId` equals `entity_id`; `isAuthenticated` true; `permissions` flattened to `{resource, action, is_granted:true}` rows | passing |
| TC-AUTH-03-U11 | Web `useAuthStore.login` with role `Parent` and `user.parent_profile.students` of 2 | `selectedStudent` is the first; `studentId` is its id | passing |
| TC-AUTH-03-U12 | Mobile login `validateForm`: empty username; 5-character password; empty organisation | messages "Username is required"; "Password must be at least 6 characters"; "Organization name is required" | blocked: validateForm is inline in mobile/app/login.tsx and not exported |
| TC-AUTH-03-A01 | Login as Admin with username and active year | 200; `role.name` "Admin"; `token_type` "bearer"; `expires_in` 86400; `tenant_id` equals the tenant id; `client_name` `qa_school`; `user` has no password field | planned |
| TC-AUTH-03-A02 | Login as each of Staff, Teacher, Student, Parent | 200 each; `role.name` matches; `entity_id` is the staff id for Staff and Teacher, student id for Student, parent id for Parent | planned |
| TC-AUTH-03-A03 | Admin without a staff row | `entity_id` is null | planned |
| TC-AUTH-03-A04 | Login with the user's email instead of username | 200 | planned |
| TC-AUTH-03-A05 | Login with a staff member's phone number | 200 | planned |
| TC-AUTH-03-A06 | Login with a student's admission number as username | 200; role Student | planned |
| TC-AUTH-03-A07 | Wrong password | 401 "Invalid Credentials" | planned |
| TC-AUTH-03-A08 | Unknown username | 401 "Invalid Credentials" (same body as A07) | planned |
| TC-AUTH-03-A09 | Deactivated user with the correct password (set `is_active` false via TEN F13) | 401 "Invalid Credentials" | planned |
| TC-AUTH-03-A10 | Username in different case (`ADMIN` when stored as `admin`) and with trailing space | 401 each (exact match) | planned |
| TC-AUTH-03-A11 | Same username in `qa_school` and `qa_school_b` with different passwords; each password against each tenant | success only with the matching tenant's password; the other pairing gives 401 | planned |
| TC-AUTH-03-A12 | Decode the access token | claims `sub`, `username`, `role`, `tenant_id`, `client_name`, `academic_year_id`, `academic_year_title`, `exp`, `token_type=access`; no `permissions`, no `user_type` | planned |
| TC-AUTH-03-A13 | Body `client_name` equal to the header tenant | 200 | planned |
| TC-AUTH-03-A14 | Body `client_name` of `qa_school_b` with header `qa_school` | 400 "Tenant does not match the request" | planned |
| TC-AUTH-03-A15 | Body `client_name` of a name that does not exist | 401 "Invalid connection" | planned |
| TC-AUTH-03-A16 | Empty username and empty password | 401 "Invalid Credentials" | planned |
| TC-AUTH-03-A17 | Body missing `password` | 422 naming field `password` | planned |
| TC-AUTH-03-A18 | Ten wrong passwords in a row, then the correct one | all ten return 401; the correct login returns 200 (no lockout, no 429) | planned |
| TC-AUTH-03-A19 | Login without any header and token | request rejected before the endpoint (F01 rule) | planned |
| TC-AUTH-03-A20 | Deactivate the user after login, call `GET /auth/available-resources` with the old access token | still 200 until expiry (documents that the token is not re-checked); `POST /auth/refresh` with the old refresh token gives 401 (F08) | planned |
| TC-AUTH-03-E01 | Web: Admin logs in with valid credentials | lands on `/dashboard`; navbar shows the username | planned |
| TC-AUTH-03-E02 | Web: wrong password | banner "Invalid Credentials"; stays on `/login` | planned |
| TC-AUTH-03-E03 | Web: click the eye button | password field switches between hidden and visible; button label alternates "Show password" and "Hide password" | planned |
| TC-AUTH-03-E04 | Web: log in as Staff, Teacher, Student, Parent in turn | each lands on `/dashboard` with the sidebar of its role (F06) | planned |
| TC-AUTH-03-E05 | Web: while the request runs | button shows "Logging in..." and is disabled | planned |
| TC-AUTH-03-E06 | Web: already logged in, open `/login` | redirected to `/dashboard` | planned |
| TC-AUTH-03-E07 | Mobile: sign in as Admin with valid credentials | opens the tabs home | planned |
| TC-AUTH-03-E08 | Mobile: tap "Sign In" with empty fields | messages "Username is required" and "Password is required" | planned |
| TC-AUTH-03-E09 | Mobile: password of 5 characters | message "Password must be at least 6 characters"; no request is sent | planned |
| TC-AUTH-03-E10 | Mobile: wrong password | red banner "Invalid Credentials" | planned |
| TC-AUTH-03-E11 | Mobile: sign in as Student and as Parent | each lands on its tabs; the Parent has a selected child (F09) | planned |

Implemented in: `backend/tests/unit/auth/test_auth_login_service.py` (U01-U09); `web/src/__tests__/auth/authStore.test.ts` (U10, U11).

## F04 First-login forced password change

### Purpose
Make a user replace the temporary password that the school gave them before they can use the system.

### Roles and permissions
Applies to roles `Staff`, `Teacher`, `Student`, `Parent` whose `users.is_first_login` is TRUE. Admin and custom roles are never forced. No permission needed.

### Preconditions
A user created by staff enrolment or student admission (which set the flag), or a fixture user with `is_first_login = TRUE`. The temporary password is the hardcoded default of those services (not repeated here).

### Steps, web
1. Log in on `/login` with the temporary password (F03). The app stores the token in `sessionStorage['change_password_token']` and opens `/set-password`.
2. The page "Set Your Password" ("Create a new password to access your account.") shows "New Password" (placeholder "Minimum 8 characters", eye button) and "Confirm Password" (placeholder "Re-enter your password").
3. Fill both and press "Set Password" ("Setting password..." while waiting).
4. On success the user is signed in and the app opens `/`. When the token is missing or the server says it is expired or invalid, the page shows "Session expired or invalid", "Please log in again with your temporary password." and the button "Back to Login".

### Steps, mobile
1. Sign in with the temporary password (F03). The app stores the 15-minute token in SecureStore and opens "Set New Password" ("Please set a new password for your account").
2. Fill "New Password" (placeholder "Enter new password (min 8 characters)") and "Confirm New Password" (placeholder "Re-enter your new password"), then tap "Set Password".
3. Local checks: "New password is required", "New password must be at least 8 characters", "Please confirm your new password", "New passwords do not match". With no stored token: "Session expired. Please log in again." and a redirect to `/login`.
4. On success the app opens the tabs, already signed in.

### Expected results
`users.password_hash` holds the new hash, `users.is_first_login` is FALSE, the response is a full login payload (same shape as F03 plus `message: "Password updated successfully"`), the temporary password no longer works.

### API endpoints
| Method and path | Request fields | Notes |
|---|---|---|
| `POST /auth/login` | as F03 | Returns the challenge instead of tokens |
| `POST /auth/staff/set-password` | `change_password_token`, `new_password` (min 8), `confirm_password` | Used for all four roles; no bearer header needed; `cschema` header still required by the middleware |

### Rules and validations
- Challenge body: `requires_password_change: true`, `change_password_token` (JWT, 15 minutes, `token_type` `change_password`), `message` "Please set a new password to continue", `academic_year_id`, `academic_year_title`. No access or refresh token is issued.
- The academic year is validated before the challenge, so a bad year still gives 400.
- Set-password order: `new_password == confirm_password` (400 "Passwords do not match"), token validity (401 "Invalid or expired change-password token. Please login again."; wrong token type 401 "Invalid token type"), tenant still active (401 "Invalid connection"), user exists (404 "User not found"), user active (401 "Invalid Credentials"), flag still TRUE (400 "Password has already been set. Please log in with your password.").
- The tenant comes from the token; the `cschema` header is not compared to it on this endpoint.
- `is_first_login` is read and written with raw SQL; Admin password resets do not set it (TEN F13).

### Error and edge cases
- Reusing the same token after success: 400 "Password has already been set. Please log in with your password."
- Token older than 15 minutes: 401 expired message.
- Using an access token in `change_password_token`: 401 "Invalid token type".
- User deactivated between login and set-password: 401 "Invalid Credentials".
- Web `new_password` shorter than 8: blocked by the HTML `minLength`; the server answers 422.
- Closing the tab loses the web token (sessionStorage) and the user must log in again.

### Unit-testable logic
`create_change_password_token` / `verify_change_password_token` (lifetime 15 min, type check); `SetPasswordRequest` validation; the order of checks in `set_password_first_login` (fake session); web `SetPasswordPage` token-missing branch; mobile `validate()` messages.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-04-U01 | `create_change_password_token` decoded | `token_type=change_password`; `exp` about 15 minutes ahead | passing |
| TC-AUTH-04-U02 | `verify_change_password_token` with an access token | HTTPException 401 "Invalid token type" | passing |
| TC-AUTH-04-U03 | `verify_change_password_token` with an expired token (clock 16 minutes later) | HTTPException 401 "Invalid or expired change-password token. Please login again." | passing |
| TC-AUTH-04-U04 | `SetPasswordRequest` with `new_password` of 7 and of 8 characters | 7 rejected; 8 accepted | passing |
| TC-AUTH-04-U05 | `set_password_first_login` with flag already FALSE (fake session) | HTTPException 400 "Password has already been set. Please log in with your password."; hash not changed | passing |
| TC-AUTH-04-U06 | `set_password_first_login` with a deactivated user | HTTPException 401 "Invalid Credentials" | passing |
| TC-AUTH-04-U07 | Role gate in `login_user`: names Staff, Teacher, Student, Parent vs Admin and a custom role | first-login check runs only for the four names | passing |
| TC-AUTH-04-U08 | Mobile `validate()` with `""`, `"1234567"`, `"12345678"` and mismatching confirm | "New password is required"; "New password must be at least 8 characters"; "Please confirm your new password"; "New passwords do not match" | blocked: validate is inline in mobile/app/set-password.tsx and not exported |
| TC-AUTH-04-A01 | Login as a Staff fixture with `is_first_login` TRUE | 200 body has `requires_password_change` true, `change_password_token`, `message`, `academic_year_id`, `academic_year_title`; no `access_token` | planned |
| TC-AUTH-04-A02 | Same for Teacher, Student and Parent fixtures | same challenge for each role | planned |
| TC-AUTH-04-A03 | Admin fixture with flag forced TRUE in the database | normal login (tokens issued, no challenge) | planned |
| TC-AUTH-04-A04 | Challenge token decoded | `token_type=change_password`, claims `sub`, `username`, `role`, `tenant_id`, `client_name`, academic year; `exp` about 15 min | planned |
| TC-AUTH-04-A05 | Use the challenge token as bearer on `GET /profile/staff/me` | 401 "Invalid token type" | planned |
| TC-AUTH-04-A06 | `POST /auth/staff/set-password` with matching 10-character passwords | 200; `message` "Password updated successfully"; `access_token`, `refresh_token`, `menu`, `permissions`, `entity_id` present | planned |
| TC-AUTH-04-A07 | After A06 log in with the old temporary password | 401 "Invalid Credentials" | planned |
| TC-AUTH-04-A08 | After A06 log in with the new password | 200 with tokens and no challenge | planned |
| TC-AUTH-04-A09 | Replay the same change-password token | 400 "Password has already been set. Please log in with your password." | planned |
| TC-AUTH-04-A10 | `new_password` and `confirm_password` differ | 400 "Passwords do not match" (checked before the token) | planned |
| TC-AUTH-04-A11 | `new_password` "short7!" (7 characters) | 422 on `new_password` | planned |
| TC-AUTH-04-A12 | `new_password` of exactly 8 characters | 200 | planned |
| TC-AUTH-04-A13 | Garbage string as `change_password_token` | 401 "Invalid or expired change-password token. Please login again." | planned |
| TC-AUTH-04-A14 | Token that is 16 minutes old (token minted with a past `exp` in the test) | 401 "Invalid or expired change-password token. Please login again." | planned |
| TC-AUTH-04-A15 | Deactivate the user after the challenge, then set the password | 401 "Invalid Credentials" | planned |
| TC-AUTH-04-A16 | Deactivate the tenant after the challenge, then set the password | 401 "Invalid connection" | planned |
| TC-AUTH-04-A17 | Set-password with header `cschema: qa_school_b` and a `qa_school` token | 200 for the `qa_school` user (token tenant wins; documents the missing header cross-check) | planned |
| TC-AUTH-04-A18 | Challenge login with a wrong academic year id | 400 "Invalid academic year" (no challenge issued) | planned |
| TC-AUTH-04-A19 | Role denial matrix: set-password for a token minted for each of the five roles | works for Staff, Teacher, Student, Parent; the Admin case cannot occur through login | planned |
| TC-AUTH-04-E01 | Web: log in as the first-login Staff fixture | redirected to `/set-password`; page title "Set Your Password" | planned |
| TC-AUTH-04-E02 | Web: enter a 10-character password twice, press "Set Password" | signed in and taken to `/`; sidebar visible | planned |
| TC-AUTH-04-E03 | Web: enter different passwords | banner "Passwords do not match" | planned |
| TC-AUTH-04-E04 | Web: open `/set-password` directly in a new tab with no token | panel "Session expired or invalid" with button "Back to Login" | planned |
| TC-AUTH-04-E05 | Web: after success log out and log in with the new password | normal login, no password page | planned |
| TC-AUTH-04-E06 | Mobile: sign in as the first-login Student fixture | screen "Set New Password" | planned |
| TC-AUTH-04-E07 | Mobile: password "1234567" | message "New password must be at least 8 characters" | planned |
| TC-AUTH-04-E08 | Mobile: mismatching confirmation | message "New passwords do not match" | planned |
| TC-AUTH-04-E09 | Mobile: valid new password, tap "Set Password" | opens the tabs signed in | planned |
| TC-AUTH-04-E10 | Mobile: first-login Parent completes the flow | tabs open and the first child is selected (F09) | planned |

Implemented in: `backend/tests/unit/auth/test_auth_login_service.py` (U01-U07).

## F05 Permission loading

### Purpose
Give the client the signed-in user's permissions once, at login, so the UI can hide what the user cannot do. The backend remains the source of truth and checks the database on every request.

### Roles and permissions
No permission is needed to receive the map. Everything the map contains is a `resource:action` pair granted to the user's role (`resource_permissions.is_granted = true`).

### Preconditions
A role with rows in `resource_permissions` (seeded by TEN F07 and F08, edited by TEN F15).

### Steps, web
1. Log in (F03). The login response `permissions` (an object `{resource: [actions]}`) is stored in `useAuthStore` as `permissionsMap` and as a flat `permissions` list, and persisted in `localStorage['auth-storage']`.
2. Pages and buttons call `hasPermission(resource, action)` (hooks `usePermission`, component `PermissionGuard`). Example: opening Administration > Users without `user_management:list` shows "Access Denied" and "You don't have permission to view users."
3. After an administrator changes a role's permissions, the user must log out and log in again to see the UI change.

### Steps, mobile
1. Log in (F03). `normalisePermissions` converts the map into a list stored in AsyncStorage `@auth/permissions_data`.
2. Tabs, dashboard tiles and screens use `useAuth().hasPermission`. Screens guarded by `ScreenAccessGate` show an Access Denied panel when the check fails.
3. As on web, new grants are visible only after the next login.

### Expected results
`permissions` lists only granted actions, grouped by resource, with the actions of each resource sorted alphabetically; a role with no grants gets `{}`. Clients cache the map until the next login or logout.

### API endpoints
| Method and path | Notes |
|---|---|
| `POST /auth/login` | Response field `permissions` |
| `POST /auth/staff/set-password` | Same field in its response |
| `POST /auth/refresh` | Does not return permissions |

### Rules and validations
- Source: `MultiTenantAuthService.get_user_permissions`: rows for the role with `is_granted` true, ordered by resource then action, grouped; a database error returns `{}`.
- Runtime enforcement does not read the token: `check_role_plan_permission_with_error` looks up the role (by the `role` name in the token) and the `resource_permissions` row on each request, so grants and revocations apply to the API at once. The plan layer is not consulted at runtime.
- Web `hasPermission`: exact match in `permissionsMap`; for roles named `teacher` and `staff` (compared in lower case) the frontend matrices in `teacherPermissionMatrix.ts` and `staffPermissionMatrix.ts` replace the backend grant for the resources they list (they can only hide). Resources not listed fall through to the backend grant.
- Mobile `hasPermission`: the same matrices, then `hasPermissionWithFallbacks`: aliases (`classes`, `sections`, `classes_sections`, `academic_years`, `subjects`, `staff`, `students`, `fee_*`), `list` and `read` satisfy each other, and `read_own`, `read_related`, `list_own`, `list_related` satisfy `read` or `list`. This widens the UI gate only.
- Default seed: only the Student role receives `profile:read_own` and `profile:update_own` (`permission_catalog.py`); a tenant on a plan built from the Admin catalog (such as the `Full` plan of `CatalogService.ensure_full_plan`) has no `profile` resource and no `_own` or `_related` actions at all, so those grants are not seeded for any role there (see Known gaps).

### Error and edge cases
- Role with no grants: `permissions` is `{}` and the UI hides everything guarded.
- Grant removed after login: the UI still shows the control; the API answers 403 "Permission not found in database: <role> cannot <action> <resource>. Contact administrator to configure permissions."
- Role renamed outside the system roles is not possible for the five system names (TEN F14).

### Unit-testable logic
`get_user_permissions` grouping, ordering and empty result; web `useAuthStore.hasPermission` including the matrices; mobile `normalisePermissions`, `generateFallbackPatterns`, `checkPermissionWithFallbacks`, `hasPermission` role caps.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-05-U01 | `get_user_permissions` with rows (fee_types,list), (fee_types,create), (students,list) | `{"fee_types":["create","list"],"students":["list"]}` | passing |
| TC-AUTH-05-U02 | `get_user_permissions` with no rows | `{}` | passing |
| TC-AUTH-05-U03 | `get_user_permissions` when the query raises | `{}` (error swallowed and logged) | passing |
| TC-AUTH-05-U04 | Web `hasPermission` for an Admin map containing `students: ['list']` | `('students','list')` true; `('students','create')` false; unknown resource false | passing |
| TC-AUTH-05-U05 | Web `hasPermission`, role `Teacher`, backend map `exam_marks: ['create','read','list','delete']` | `delete` false (matrix lists only create, read, list) | passing |
| TC-AUTH-05-U06 | Web `hasPermission`, role `Teacher`, backend map `fee_categories: ['create']` (resource not in the teacher matrix) | true (falls through to the backend grant) | passing |
| TC-AUTH-05-U07 | Web `hasPermission`, role `Staff`, map `fee_refunds: ['create','approve']` | `create` true; `approve` false | passing |
| TC-AUTH-05-U08 | Web `hasPermission` with role name `TEACHER` and `staff` in other case | caps still apply (case-insensitive) | passing |
| TC-AUTH-05-U09 | Web `useAuthStore.logout` | `permissions`, `permissionsMap`, `menuItems`, tokens cleared; `isAuthenticated` false | passing |
| TC-AUTH-05-U10 | Mobile `normalisePermissions({"students":["list","read"]})` | two items with ids `students:list`, `students:read`, `is_granted` true | passing |
| TC-AUTH-05-U11 | Mobile `normalisePermissions` with `null`, `undefined`, an array | `[]`, `[]`, the same array | passing |
| TC-AUTH-05-U12 | Mobile `generateFallbackPatterns("fee_types","list")` | contains `fees_types:list`, `feetypes:list`, `fee_types:read`, `fee_types:read_own`, `fee_types:read_related` | passing |
| TC-AUTH-05-U13 | Mobile `checkPermissionWithFallbacks` with only `student_attendance:read_related` for `student_attendance:list` | granted through the scoped fallback | passing |
| TC-AUTH-05-U14 | Mobile `hasPermission` for role Teacher on `exam_marks:delete` | false (same matrix as web) | blocked: hasPermission is a closure inside AuthProvider (mobile/contexts/AuthContext.tsx); the teacher matrix it applies is covered by permissions.test.ts |
| TC-AUTH-05-A01 | Login as Admin; compare `permissions` with `resource_permissions` rows where `is_granted` | equal sets; includes `role_management` with create, read, update, delete, list | planned |
| TC-AUTH-05-A02 | Login as Staff, Teacher, Student, Parent | each map equals its role's granted rows; Teacher has no `fee_*`; Student has no plain `read` on `students` | planned |
| TC-AUTH-05-A03 | Every action list in the response | sorted alphabetically | planned |
| TC-AUTH-05-A04 | Set one of the role's permissions to `is_granted` false (TEN F15), log in again | that action is absent from `permissions` | planned |
| TC-AUTH-05-A05 | Grant a new permission (TEN F15), call an endpoint needing it with the old token | 200 immediately (no re-login needed on the API); the old login response still lacks it | planned |
| TC-AUTH-05-A06 | Revoke a permission, call the endpoint with the old token | 403 "Permission not found in database: <role> cannot <action> <resource>. Contact administrator to configure permissions." | planned |
| TC-AUTH-05-A07 | Custom role with no grants, user logs in | 200; `permissions` is `{}`; `menu` is `[]` | planned |
| TC-AUTH-05-A08 | Role matrix on `GET /admin/users/` (needs `user_management:list`) | Admin 200; Staff, Teacher, Student, Parent 403 | planned |
| TC-AUTH-05-A09 | Permission map in the set-password response (F04) | equals the map a normal login returns afterwards | planned |
| TC-AUTH-05-A10 | Tenant isolation: add a permission to the Staff role of `qa_school_b`, log in as Staff of `qa_school` | `qa_school` map unchanged | planned |
| TC-AUTH-05-A11 | Student and Parent maps on a tenant whose plan lacks `_own`/`_related` and `profile` | maps contain none of those actions (documents the seed behaviour in Known gaps) | planned |
| TC-AUTH-05-E01 | Web: Admin opens Administration > Users | table with columns Username, Email, Role, Entity, Status, Actions is shown | planned |
| TC-AUTH-05-E02 | Web: Staff opens `/admin/users` by URL | "Access Denied" with "You don't have permission to view users." | planned |
| TC-AUTH-05-E03 | Web: as Admin revoke `user_management:update` from a custom role user; that user's UI | edit and reset buttons stay visible until re-login; after re-login they are gone | planned |
| TC-AUTH-05-E04 | Web: log in as Teacher | no Fee entries in the sidebar; Teacher cannot create fee categories even if the backend grants it | planned |
| TC-AUTH-05-E05 | Mobile: Staff opens the Administration users screen | "Access Denied" panel from `ScreenAccessGate` | planned |
| TC-AUTH-05-E06 | Mobile: Parent opens Student Attendance | screen opens (guard satisfied by `student_attendance:read_related`) | planned |

Implemented in: `backend/tests/unit/auth/test_auth_permissions_menu.py` (U01-U03); `web/src/__tests__/auth/authStore.test.ts` (U04-U09); `mobile/__tests__/auth/authUtils.test.ts` and `mobile/__tests__/auth/permissions.test.ts` (U10-U13).

## F06 Role-based menu

### Purpose
Show each user only the navigation entries their role may open.

### Roles and permissions
Menu visibility comes from `role_menu_permissions.can_view` for the user's role, not from `resource_permissions`; a menu does not imply API access. Admin, Staff and Teacher receive every menu of the tenant's plan; Student and Parent receive only the menus whose URL is in `STUDENT_PARENT_MENU_URLS`: `/dashboard`, `/students`, `/students/admission`, `/students/attendance`, `/students/studenttransport`, `/students/studentdocuments`, `/students/studentcertificates`, `/fee`, `/fee/my-fees`, `/fee/my-receipts`, `/exam`, `/exam/exams`, `/exam/marks`, `/exam/hall-tickets`, `/exam/results`.

### Preconditions
A shared menu catalog with plan access (TEN F06) and a provisioned tenant (TEN F07). The QA tenant uses the demo catalog (`scripts/seed_demo_catalog.py`): Dashboard, Masters, Students, Staff, Fee, Transport, Exam, Expense, Communication, Timetable, Calendar, Reports, Administration (Users, School Settings).

### Steps, web
1. Log in. `useMenuData` turns the login `menu` into the sidebar.
2. The sidebar is built by `menuUtils.ts`: hides the items "Route Stops", "Transport Trips" and "Student Transport" for everyone; removes Fee items for `teacher`; removes "My Fees" for `student`; for `student` and `parent` adds a Fee node ("My Receipts" `/fee/my-receipts`, "My Transactions" `/fee/my-transactions`) when the backend sent none; gives a flat "Fee" entry the eight admin children (Fee Categories, Fee Types, Fee Terms, Fee Mappings, Fee Term Amounts, Fee Collection, Fee Receipts, Fee Refunds) for roles other than student, parent and teacher; adds "School Registration" (`/settings/school`) under Masters for roles other than teacher and student when absent; orders top-level items by the agreed list (dashboard, students, staff, exam management or exams, fee, expense, communication, reports, masters, administration, transport; names not in the list, such as "Exam", "Timetable", "Calendar", go last in catalog order).
3. The Administration dashboard (`/admin`) shows cards for the children of the "Administration" menu.

### Steps, mobile
1. Log in. The drawer and hubs use the stored menu mapped to mobile paths (`menuMap.ts`) and filtered by `src/lib/menuUtils.ts`: same hidden items, Fee removed for Teacher, "My Fees" removed for Student, School Settings hidden for Teacher and Student, and Communication, Reports, Masters, Transport removed for Student and Parent (also guardian, father, mother).

### Expected results
`menu` is a tree of `{id, name, path, display_order, children?}` sorted by `display_order` at each level; leaf items have no `children` key; items whose parent the role cannot view are dropped.

### API endpoints
| Method and path | Notes |
|---|---|
| `POST /auth/login`, `POST /auth/staff/set-password` | Field `menu` |
| `GET /auth/menus/`, `POST /auth/menus/` | Shared catalog (TEN F06); not used for the sidebar |

### Rules and validations
- Query: menus joined to `role_menu_permissions` where `can_view`; ordered by `display_order`, then id; depth up to L3.
- A child whose parent is not granted is silently dropped; a database failure returns `[]`.
- The default role-menu links are created by role seeding (TEN F08); `can_edit` is true only for Admin and is not used at runtime.
- Client menus are a login-time snapshot (changes appear after re-login).

### Error and edge cases
- Role with no menu links: empty sidebar; web logs "No menu data found in authStore".
- Menu catalog row removed from the plan: its link disappears at the next plan sync (TEN F09).
- Student URL not in the allowlist (for example `/staff`): never delivered to Student or Parent.

### Unit-testable logic
`build_hierarchical_menu` tree building and sorting (fake rows); web `filterMenuForRole`, `ensureFeeMenu`, `injectFeeSubmenu`, `injectSchoolSettings`, `reorderMenu`; mobile `filterMenuForRole`, `roleBlocksFees`, `roleBlocksSchoolSettings`.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-06-U01 | `build_hierarchical_menu` with an L0 "Masters" (order 2) and L1 children (orders 2 and 1) | one root; children sorted by order 1 then 2; no `parent_id` or `level` keys | passing |
| TC-AUTH-06-U02 | Leaf menu node | has no `children` key | passing |
| TC-AUTH-06-U03 | Child row whose parent id is not among the viewable rows | child omitted from the result | passing |
| TC-AUTH-06-U04 | `build_hierarchical_menu` when the query raises | returns `[]` | passing |
| TC-AUTH-06-U05 | Role with no viewable rows | returns `[]` | passing |
| TC-AUTH-06-U06 | Web `filterMenuForRole` with items named "Route Stops", "Transport Trips", "Student Transport" for any role | all three removed (case-insensitive) | passing |
| TC-AUTH-06-U07 | Web `filterMenuForRole`, role `teacher`, items "Fee" (`/fee`), "Fee Management", "Students" | Fee items removed recursively; Students kept | passing |
| TC-AUTH-06-U08 | Web `filterMenuForRole`, role `student`, child "My Fees" | removed; "My Receipts" kept | passing |
| TC-AUTH-06-U09 | Web menu for `student` without a Fee node | node id 99001 "Fee" `/fee` with children "My Receipts" and "My Transactions" appended | passing |
| TC-AUTH-06-U10 | Web menu for `parent` whose Fee node lacks "My Transactions" | only the missing child is added; existing children untouched | passing |
| TC-AUTH-06-U11 | Web `injectFeeSubmenu` for role `admin` with a flat L0 "Fee Management" | gets 8 children; for roles student, parent, teacher the item is unchanged | passing |
| TC-AUTH-06-U12 | Web `injectSchoolSettings` for `admin` with a "Masters" item | child "School Registration" `/settings/school` added; not added for `teacher`, `student`; not duplicated when the URL already exists | passing |
| TC-AUTH-06-U13 | Web `reorderMenu` with Reports, Dashboard, Zeta, Students | Dashboard, Students, Reports, Zeta | passing |
| TC-AUTH-06-U14 | Mobile `applyRoleMenuRules` for `parent` | Communication, Reports, Masters, Transport removed | passing |
| TC-AUTH-06-U15 | Mobile `roleBlocksFees('Teacher')` and `roleBlocksSchoolSettings('student')` | true; true | passing |
| TC-AUTH-06-A01 | Admin login on the QA tenant | `menu` contains Administration with children Users (`/admin/users`) and School Settings (`/settings/school`), and Masters | planned |
| TC-AUTH-06-A02 | Student login | every `path` (all levels) is in the allowlist; no Masters, Administration, Transport, Communication, Reports | planned |
| TC-AUTH-06-A03 | Parent login | same allowlist rule as A02 | planned |
| TC-AUTH-06-A04 | Staff and Teacher login | menu equals Admin's menu minus entries the role has no link for (compare with `role_menu_permissions`) | planned |
| TC-AUTH-06-A05 | Delete the link of an L0 menu for Staff, keep its child's link, log in | the child does not appear (dropped with its parent) | planned |
| TC-AUTH-06-A06 | Each level of the response | siblings sorted by `display_order` ascending | planned |
| TC-AUTH-06-A07 | Custom role with no links | `menu` is `[]` | planned |
| TC-AUTH-06-A08 | Same tenant after a plan sync that removes a menu from the plan (TEN F09), log in as Admin | that menu is gone | planned |
| TC-AUTH-06-A09 | Menus of `qa_school_b` roles | do not appear in `qa_school` responses (role links are tenant rows) | planned |
| TC-AUTH-06-A10 | Role matrix on `GET /auth/menus/` (needs `menu_management:list`) | Admin 200; Staff, Teacher, Student, Parent 403 | planned |
| TC-AUTH-06-E01 | Web: Admin sidebar on the demo catalog | order Dashboard, Students, Staff, Fee, Expense, Communication, Reports, Masters, Administration, Transport, then Exam, Timetable, Calendar (names missing from the agreed list keep catalog order at the end) | planned |
| TC-AUTH-06-E02 | Web: Teacher sidebar | no Fee entry; no "Route Stops" or "Student Transport" | planned |
| TC-AUTH-06-E03 | Web: Student sidebar | Dashboard, Students, Fee (My Receipts, My Transactions), Exam only; no Masters | planned |
| TC-AUTH-06-E04 | Web: Parent sidebar | same as Student | planned |
| TC-AUTH-06-E05 | Web: Admin opens `/admin` | cards "Users" and "School Settings" appear; clicking a card with a path navigates to it | planned |
| TC-AUTH-06-E06 | Web: Staff sidebar on the demo catalog (School Settings already exists under Administration) | the settings page is listed once and "School Registration" is not added under Masters | planned |
| TC-AUTH-06-E07 | Mobile: Parent drawer | no Communication, Reports, Masters or Transport | planned |
| TC-AUTH-06-E08 | Mobile: Teacher drawer | no Fee and no School Settings | planned |

Implemented in: `backend/tests/unit/auth/test_auth_permissions_menu.py` (U01-U05); `web/src/__tests__/auth/menuUtils.test.ts` (U06-U13, through the exported useMenuData with react-query mocked); `mobile/__tests__/auth/permissions.test.ts` (U14, U15).

## F07 Session persistence and route guards

### Purpose
Keep the user signed in across reloads and app restarts, and keep signed-out users away from private pages.

### Roles and permissions
No permission; all signed-in roles.

### Preconditions
A successful login or set-password (F03, F04).

### Steps, web
1. After login the Zustand store writes `localStorage['auth-storage']` (user, role, selectedStudent, availableStudents, studentId, entityId, academic year id and title, permissions, permissionsMap, menuItems, accessToken, refreshToken, isAuthenticated).
2. Reload or reopen the browser: the store is restored, the sidebar and permissions are intact, no login is needed.
3. Open a private page (for example `/dashboard`) while signed out: the route `_app` redirects to `/login`. Open `/login`, `/forgot-password` or `/set-password` while signed in: the route `_auth` redirects to `/dashboard`.
4. Clearing site data or logging out ends the session.

### Steps, mobile
1. After login tokens go to the secure store (`expo-secure-store`: keys `auth_access_token`, `auth_refresh_token`, `auth_token_expiry`, `auth_change_password_token`; on Expo web they fall back to AsyncStorage keys prefixed `@secure/`); user, role, permissions, menu, organisation and student context go to AsyncStorage.
2. Close and reopen the app: `initializeAuth` checks for tokens and a stored user first, refreshes an expired access token with the refresh token, and opens the tabs.
3. If the refresh fails, all stored session data is cleared and the login screen opens (the organisation prompt returns).

### Expected results
A valid session survives reloads and restarts until logout, refresh failure, or storage clearing.

### API endpoints
| Method and path | Notes |
|---|---|
| `POST /auth/refresh` | Used on cold start (mobile) and after a 401 (both) |
| any authenticated endpoint | Stateless: the server keeps no session besides the logout blacklist |

### Rules and validations
- Mobile expiry check treats the token as expired five minutes before `exp` (`TOKEN_EXPIRY_BUFFER`); the expiry time is `now + expires_in` seconds, or 3600 s when the response has none.
- Mobile never writes tokens to AsyncStorage on native platforms.
- Web guards only test `isAuthenticated`; permissions are not checked per route (a typed URL opens the page and its API calls return 403).
- Persisted state is not validated against the server; a revoked token is detected on the next request.

### Error and edge cases
- Corrupted `auth-storage`: the store falls back to defaults and the user must log in.
- Two web tabs: both share the same localStorage; a refresh in one tab updates the tokens for both.
- Mobile with stored user but missing tokens: treated as signed out.

### Unit-testable logic
Mobile `isTokenExpired` (buffer), `storeAuthData` expiry fallback, `getStoredTokens`, `clearAuthData`, `isAuthenticated`, `initializeAuth`; web store `partialize` list and route `beforeLoad` guards.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-07-U01 | Mobile `isTokenExpired` with expiry in 4 minutes, 5 minutes, 6 minutes (fake clock) | true, true, false (boundary: now + 5 min >= expiry) | passing |
| TC-AUTH-07-U02 | Mobile `isTokenExpired` with no stored expiry | true | passing |
| TC-AUTH-07-U03 | Mobile `storeAuthData` with `expires_in` 86400 and with none | stored expiry about `now + 86400 s`; `now + 3600 s` | passing |
| TC-AUTH-07-U04 | Mobile `getStoredTokens` with only an access token stored | `null` | passing |
| TC-AUTH-07-U05 | Mobile `clearAuthData` | tokens, change-password token, user, role, permissions, menu, selected student, available students, student id and organisation keys removed | passing |
| TC-AUTH-07-U06 | Mobile `isAuthenticated` with tokens but no stored user | false | passing |
| TC-AUTH-07-U07 | Mobile `isAuthenticated` with an expired access token and a refresh that fails | false and session cleared | passing |
| TC-AUTH-07-U08 | Mobile `initializeAuth` when not authenticated | `{isAuthenticated:false, user:null, role:null, permissions:[], menu:[]}` | passing |
| TC-AUTH-07-U09 | Web `_app` `beforeLoad` with `isAuthenticated` false | throws a redirect to `/login` | passing |
| TC-AUTH-07-U10 | Web `_auth` `beforeLoad` with `isAuthenticated` true | throws a redirect to `/dashboard` | passing |
| TC-AUTH-07-U11 | Web store `partialize` | persisted keys are exactly the 14 listed; no functions | passing |
| TC-AUTH-07-A01 | Use one access token for three consecutive authenticated calls | all 200 (stateless) | planned |
| TC-AUTH-07-A02 | Refresh token used as bearer on an authenticated endpoint | 401 "Invalid token type" | planned |
| TC-AUTH-07-A03 | Access token used as `refresh_token` | 401 "Invalid token type" | planned |
| TC-AUTH-07-A04 | Access token with a tampered payload (signature unchanged) | 401 "Invalid token" | planned |
| TC-AUTH-07-A05 | Authenticated call with header `Authorization: Token abc` or without it (header `cschema` present) | 401 "Authorization header missing or invalid" | planned |
| TC-AUTH-07-E01 | Web: log in, reload the page | still on `/dashboard`; sidebar intact | planned |
| TC-AUTH-07-E02 | Web: log in, close the tab, open a new tab on `/dashboard` | session restored | planned |
| TC-AUTH-07-E03 | Web: signed out, open `/dashboard` | redirected to `/login` | planned |
| TC-AUTH-07-E04 | Web: signed in, open `/login` and `/forgot-password` | both redirect to `/dashboard` | planned |
| TC-AUTH-07-E05 | Web: clear `localStorage['auth-storage']`, reload | redirected to `/login` | planned |
| TC-AUTH-07-E06 | Mobile (Expo web): log in, reload | tabs reopen without login | planned |
| TC-AUTH-07-E07 | Mobile: set `@secure/auth_token_expiry` to the past, reload | app refreshes the token and stays signed in | planned |
| TC-AUTH-07-E08 | Mobile: corrupt the stored refresh token and set expiry to the past, reload | login screen opens at "Select Organization" | planned |

Implemented in: `mobile/__tests__/auth/authUtils.test.ts` (U01-U08); `web/src/__tests__/auth/tenantAndGuards.test.ts` (U09, U10); `web/src/__tests__/auth/authStore.test.ts` (U11).

## F08 Token refresh and expiry

### Purpose
Renew an expired access token without asking the user to sign in again, and end the session when renewal is impossible.

### Roles and permissions
No permission; any holder of a valid refresh token.

### Preconditions
A session created by F03 or F04. Access tokens last 24 hours, refresh tokens 7 days.

### Steps, web
1. Use the app normally. When any request answers 401 (except `/auth/login*`), the interceptor in `web/src/api/index.ts` runs one shared `POST /auth/refresh` with the stored refresh token and the tenant header, stores the new pair, and retries each failed request once. A request that failed after another one already refreshed is retried with the newer token instead of refreshing again.
2. If the refresh fails, the store is logged out and the browser goes to `/login`.

### Steps, mobile
1. `getValidAccessToken` refreshes before a request when the stored expiry is within five minutes; a 401 triggers one shared refresh through `refreshPromise` and a retry.
2. On cold start an expired access token is refreshed (F07). A failed refresh clears the stored session including the organisation, and `onSessionExpired` signs the user out.

### Expected results
New `access_token` and `refresh_token` with fresh lifetimes; the user's role name and `is_active` are re-read from the database.

### API endpoints
| Method and path | Request fields | Notes |
|---|---|---|
| `POST /auth/refresh` | `refresh_token`; header `cschema` | Response: `access_token`, `refresh_token`, `token_type`, `expires_in` (86400), `academic_year_id`, `academic_year_title` (no `tenant_id` or `client_name`) |

### Rules and validations
- Checks in order: refresh token signature and type (401 "Invalid refresh token", or 401 "Invalid token type"); not blacklisted (401 "Refresh token has been invalidated. Please login again."); `tenant_id` claim present (401 "Your session is out of date. Please log in again."); equals the request tenant (403 "Tenant does not match your session"); user exists and is active (401 "Account is inactive. Please contact the administrator.").
- The new token carries the current role name, so a role change takes effect at the next refresh.
- The old refresh token is not revoked or rotated and stays valid until it expires or is blacklisted by logout.
- Expired or invalid access tokens answer 401 "Invalid token"; a blacklisted access token answers 401 "Token has been invalidated. Please login again."
- Super admin refresh tokens cannot be used here (no `tenant_id`).

### Error and edge cases
- Refresh token past 7 days: 401 "Invalid refresh token".
- Several tabs or requests failing together: exactly one refresh call (web `refreshPromise`, mobile lock).
- User deactivated: refresh 401; their current access token keeps working until `exp`.
- Mobile assumes 1 hour when `expires_in` is absent.

### Unit-testable logic
`verify_refresh_token`, `create_*_token` lifetimes; refresh ordering of checks (fake db and request); web interceptor decisions (tokenless path list, retry-once flag, shared promise, newer-token reuse); mobile `getValidAccessToken` and `refreshAccessToken`.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-08-U01 | `verify_refresh_token` with an access token | HTTPException 401 "Invalid token type" | passing |
| TC-AUTH-08-U02 | `verify_refresh_token` with garbage | HTTPException 401 "Invalid refresh token" | passing |
| TC-AUTH-08-U03 | Refresh handler with a payload lacking `tenant_id` (fake request, fake db) | HTTPException 401 "Your session is out of date. Please log in again." | passing |
| TC-AUTH-08-U04 | Refresh handler with `tenant_id` different from `request.state.tenant_id` | HTTPException 403 "Tenant does not match your session" | passing |
| TC-AUTH-08-U05 | Refresh handler with a user row `is_active` false, and with no row | HTTPException 401 "Account is inactive. Please contact the administrator." for both | passing |
| TC-AUTH-08-U06 | Refresh handler: user role now `Teacher`, payload role `Staff` | new token data has `role` `Teacher` | passing |
| TC-AUTH-08-U07 | `RefreshTokenResponse` defaults | `token_type` `bearer`, `expires_in` 86400 | passing |
| TC-AUTH-08-U08 | Web interceptor with three concurrent 401 responses (mock axios) | exactly one POST to `/auth/refresh`; each request retried once with the new token | passing |
| TC-AUTH-08-U09 | Web interceptor 401 on `/auth/login` | no refresh attempt; error propagated | passing |
| TC-AUTH-08-U10 | Web interceptor, refresh rejects | store `logout()` called and `window.location.href` set to `/login` | passing |
| TC-AUTH-08-U11 | Web interceptor, request already retried (`_retry` true) | no second refresh | passing |
| TC-AUTH-08-U12 | Web request interceptor for `/auth/refresh`, `/auth/login`, `/auth/academic-years`, `/auth/staff/set-password` | no `Authorization` header; `cschema` header set | passing |
| TC-AUTH-08-U13 | Web request interceptor for `/admin/users/` with a token | `Authorization: Bearer <token>`; no `cschema` header | passing |
| TC-AUTH-08-U14 | Mobile `getValidAccessToken(false)` with an expired token | returns `null` (no refresh) | passing |
| TC-AUTH-08-U15 | Mobile `refreshAccessToken` failure | session cleared and `null` returned (no throw) | passing |
| TC-AUTH-08-A01 | `POST /auth/refresh` with the login refresh token and header `cschema: qa_school` | 200; new tokens differ from the old ones; `expires_in` 86400; academic year fields equal the login values | planned |
| TC-AUTH-08-A02 | New access token used on an authenticated endpoint | 200 | planned |
| TC-AUTH-08-A03 | Decode the new access token | same `sub`, `tenant_id`, `client_name`, academic year; `exp` later than the old one | planned |
| TC-AUTH-08-A04 | Use the old refresh token again after A01 | 200 (no rotation) | planned |
| TC-AUTH-08-A05 | Change the user's role (TEN F13), then refresh | new access token carries the new role name | planned |
| TC-AUTH-08-A06 | Deactivate the user (TEN F13), then refresh | 401 "Account is inactive. Please contact the administrator." | planned |
| TC-AUTH-08-A07 | Logout (F14), then refresh with the same refresh token | 401 "Refresh token has been invalidated. Please login again." | planned |
| TC-AUTH-08-A08 | Refresh with an access token | 401 "Invalid token type" | planned |
| TC-AUTH-08-A09 | Refresh with a random string | 401 "Invalid refresh token" | planned |
| TC-AUTH-08-A10 | Refresh with a refresh token whose `exp` is in the past | 401 "Invalid refresh token" | planned |
| TC-AUTH-08-A11 | Refresh token of `qa_school` with header `qa_school_b` | 403 "Tenant does not match your session" | planned |
| TC-AUTH-08-A12 | Refresh token minted without `tenant_id` | 401 "Your session is out of date. Please log in again." | planned |
| TC-AUTH-08-A13 | Refresh with no header | request rejected by the tenant middleware (F01 rule) | planned |
| TC-AUTH-08-A14 | Body without `refresh_token` | 422 naming `refresh_token` | planned |
| TC-AUTH-08-A15 | Super admin refresh token (TEN F02) sent to `/auth/refresh` | 401 "Your session is out of date. Please log in again." | planned |
| TC-AUTH-08-A16 | Access token whose `exp` is in the past on `GET /auth/available-resources` | 401 "Invalid token" | planned |
| TC-AUTH-08-A17 | Deactivate the tenant, then refresh with its header | 404 "Tenant 'qa_school_b' not found or inactive" | planned |
| TC-AUTH-08-E01 | Web: log in, replace `accessToken` in `auth-storage` with `bad`, click a sidebar item | page loads; network log shows one `/auth/refresh` call; user stays signed in | planned |
| TC-AUTH-08-E02 | Web: also replace `refreshToken` with `bad`, click a sidebar item | store cleared; redirected to `/login` | planned |
| TC-AUTH-08-E03 | Web: dashboard that fires several requests with a bad access token | network log shows a single `/auth/refresh` | planned |
| TC-AUTH-08-E04 | Mobile: expiry in the past with a valid refresh token, open the app | home opens; stored expiry moved about 24 h ahead | planned |
| TC-AUTH-08-E05 | Mobile: refresh token invalid and expiry in the past | login screen shows "Select Organization" | planned |

Implemented in: `backend/tests/unit/auth/test_auth_login_service.py` (U01-U07); `web/src/__tests__/auth/apiInterceptors.test.ts` (U08-U13); `mobile/__tests__/auth/authUtils.test.ts` (U14, U15).

## F09 Parent child selection

### Purpose
Let a parent with several children choose which child's information the app shows.

### Roles and permissions
Role `Parent` only. `GET /student-parent-links/my-children` answers 403 to every other role. Data visibility for the chosen child comes from `*_related` permissions.

### Preconditions
A Parent user linked to one or more students in `student_parent_links` (Students and Masters modules).

### Steps, web
1. Log in as Parent. The client loads the children (`GET /student-parent-links/parent/{entity_id}/students` at login, `GET /student-parent-links/my-children` through `AuthProvider`) and selects the first.
2. In the navbar (screens of 768 px and wider) the combobox shows the selected child's name and "class - section"; its placeholder is "Select student...".
3. Click it, type in "Search students..." (matches name, first name, last name, admission number), pick a child. The list shows a "Selected" badge on the current one; "No students found." when the filter matches none.
4. The choice is stored (`selectedStudent`, `studentId`) and persisted; later requests carry the headers `X-Student-ID`, `X-Academic-Year-ID`, `X-Class-ID`, which the backend ignores.

### Steps, mobile
1. Log in as Parent. Children are loaded before the tabs open and the first child is selected, with the interceptor headers set in the same step.
2. Open "Select Child" (`/parents/select-child`, also reachable from the header selector). It shows "Select which child you want to view information for." and one card per child; "No children linked to your account." when none.
3. Tap a child: `selectStudent` stores it and the screen goes back.

### Expected results
The selected child drives which child's records the child-scoped screens request (path or query `student_id`).

### API endpoints
| Method and path | Notes |
|---|---|
| `GET /student-parent-links/my-children` | Parent only; one row per linked child with `id, first_name, last_name, name, is_active, date_of_birth, gender, admission_number, academic_year_id, academic_year, class_id, class_name, section_id, section_name` (latest admission); ordered by first name, last name |
| `GET /student-parent-links/parent/{parent_id}/students` | A Parent may pass only their own parent id; other roles need `parent_management:read` |

### Rules and validations
- `my-children` for a role other than `Parent`: 403 "Only parents can access this endpoint"; Parent user without a `parents` row: 404 "Parent profile not found".
- `parent/{parent_id}/students` with another parent's id: 403 "You can only view your own children".
- The backend ignores `X-Student-ID`, `X-Academic-Year-ID`, `X-Class-ID`.
- Web shows the selector only when the user is a parent with at least one child.
- Mobile selects the first child automatically and commits auth and student context in one `LOGIN_SUCCESS`.

### Error and edge cases
- Parent with no children: selector hidden (web); "No children linked to your account." (mobile).
- Child link removed while logged in: stale list until the next fetch (web refetches every 5 minutes).
- Child with no admission yet: class and section are `null`.
- Two parents linked to the same child both see that child.

### Unit-testable logic
Web `StudentSelector` filter, `useAuthStore.selectStudent`, `setAvailableStudents` (keeps a valid selection, else picks first); `fetchMyChildren` name splitting; mobile `completeLogin` ordering and `selectStudent`.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-09-U01 | Web `setAvailableStudents` with two students and none selected | `selectedStudent` is the first | passing |
| TC-AUTH-09-U02 | Web `selectStudent(second)` | `selectedStudent` and `studentId` equal the second | passing |
| TC-AUTH-09-U03 | Web `StudentSelector` filter text `adm0002` | only the child with that admission number remains (case-insensitive) | blocked: the filter is inline in StudentSelector.tsx component state (web/src/components/common/StudentSelector.tsx) |
| TC-AUTH-09-U04 | Web `fetchMyChildren` for an item with only `name: "Asha Rao"` | `first_name` "Asha", `last_name` "Rao" | passing |
| TC-AUTH-09-U05 | Web request interceptor with a selected student | headers `X-Student-ID`, `X-Academic-Year-ID`, `X-Class-ID` set from it | passing |
| TC-AUTH-09-U06 | Mobile `completeLogin` for a Parent (mock API) | `setSelectedStudentForInterceptor` is called before the single `LOGIN_SUCCESS` dispatch, which carries `selectedStudent` and `availableStudents` | blocked: completeLogin is inside AuthProvider and not exported (mobile/contexts/AuthContext.tsx) |
| TC-AUTH-09-U07 | Mobile `completeLogin` when the children call fails | `LOGIN_SUCCESS` still dispatched; error "Could not load student information. Please refresh." | blocked: completeLogin is inside AuthProvider and not exported (mobile/contexts/AuthContext.tsx) |
| TC-AUTH-09-A01 | `GET /student-parent-links/my-children` as Parent with two linked children | 200; two rows ordered by first name; each has the 14 documented fields | planned |
| TC-AUTH-09-A02 | Same call as Admin, Staff, Teacher, Student | 403 "Only parents can access this endpoint" for each | planned |
| TC-AUTH-09-A03 | Parent user with no `parents` row | 404 "Parent profile not found" | planned |
| TC-AUTH-09-A04 | Parent with a child that has two admissions | one row; class, section and year from the latest admission | planned |
| TC-AUTH-09-A05 | Parent with a child without admissions | row with `admission_number`, `class_name`, `section_name` null | planned |
| TC-AUTH-09-A06 | `GET /student-parent-links/parent/{own_parent_id}/students` as Parent | 200; the linked students | planned |
| TC-AUTH-09-A07 | Same with another parent's id | 403 "You can only view your own children" | planned |
| TC-AUTH-09-A08 | Same path as Admin (needs `parent_management:read`) | 200; as Teacher, Student 403 | planned |
| TC-AUTH-09-A09 | Children of a parent in `qa_school_b` requested with a `qa_school` Parent token | empty or not found; no `qa_school_b` child is ever returned | planned |
| TC-AUTH-09-A10 | No token (header only) | 401 "Authorization header missing or invalid" | planned |
| TC-AUTH-09-A11 | Send `X-Student-ID` of an unrelated student on `my-children` | response unchanged (header ignored) | planned |
| TC-AUTH-09-E01 | Web: Parent with two children logs in | navbar combobox shows the first child's name and class | planned |
| TC-AUTH-09-E02 | Web: open the combobox, type the second child's admission number, select | combobox shows the second child; the "Selected" badge moves | planned |
| TC-AUTH-09-E03 | Web: reload after selecting | the second child stays selected | planned |
| TC-AUTH-09-E04 | Web: Parent with no children | no combobox in the navbar | planned |
| TC-AUTH-09-E05 | Web: type a name that matches nobody | "No students found." | planned |
| TC-AUTH-09-E06 | Mobile: Parent with two children opens "Select Child" | two cards; the current child marked | planned |
| TC-AUTH-09-E07 | Mobile: tap the second child | screen closes; header shows the second child; child-scoped screens reload | planned |
| TC-AUTH-09-E08 | Mobile: Parent with no linked children | "No children linked to your account." | planned |

Implemented in: `web/src/__tests__/auth/authStore.test.ts` (U01, U02); `web/src/__tests__/auth/apiAuthHooks.test.ts` (U04); `web/src/__tests__/auth/apiInterceptors.test.ts` (U05).

## F10 Own profile view and edit

### Purpose
Let a Student, Staff member or Parent see their own record and change the few fields they own.

### Roles and permissions
`profile:read_own` to view and `profile:update_own` to edit, checked by `check_user_resource_access`. Editable fields: Student `email` (written to `users.email`); Staff `email` and `phone` (written to the `staff` row); Parent `email`, `phone`, `occupation` (written to the `parents` row). Everything else is admin-managed. There is no profile endpoint for Admin, Teacher or custom roles: the web shows an account summary instead, and the Admin edits its own `users` row through TEN F13. Default seed: only Student holds both permissions (see Known gaps), so the other roles need grants (TEN F15) before these endpoints answer 200.

### Preconditions
A signed-in user with the grant and a matching record (`students`, `staff` or `parents` row linked by `user_id`).

### Steps, web
1. Open the user menu in the navbar (avatar and username) and click "Profile" (`/profile`). The page depends on the role: Student sees "Student Profile", Parent sees "My Profile", every other role sees "Staff Profile".
2. Student: cards "Personal Information" and "Academic Information"; click "Edit Email", change the Email field in the dialog "Edit Email" and submit.
3. Staff: click "Edit Email & Phone", change Email and Phone, submit.
4. Parent: the button "Edit Profile" opens the editor (email, phone, occupation); it is shown only with `parent_profile:update_own`, a resource no role holds, and saves with `PUT /profile/parent` (see Known gaps).
5. Admin, Teacher and users without a staff record or without `profile:read_own`: when the staff profile call answers 403 or 404 the page shows "My Profile" with "Account Information" (Username, Email, Role, Academic Year).
6. Admin only: the page `/admin/profile` ("Admin Profile": Username, Email, Status, Role) has "Edit Email" and "Change Password" (F11). It is reached by URL or by a menu entry whose path is `/admin/profile`.

### Steps, mobile
1. Open the Profile tab. Student, Staff, Teacher, Admin and Parent roles each load their profile view; with no `profile:read_own` the fallback view shows the account details and a "Logout" button.
2. Tap "Edit Profile". Staff form fields "Email *" (placeholder "Enter email address") and "Phone *" (placeholder "Enter 10-digit phone number"); Student edits the email; Parent edits email, phone and occupation. Save or cancel.
3. Admin: "My Profile" (`/admin/profile`) lists Username, Email, Full Name, Role, Status and has the "Change Password" row (F11).

### Expected results
The edited values are stored on the row named above and returned in the response; the profile page shows them. Student `users.email` is also a login identifier, and Staff `phone` is a login identifier through `staff.phone`.

### API endpoints
| Method and path | Request fields | Response |
|---|---|---|
| `GET /profile/student/me` | none | `student_id, user_id, first_name, last_name, date_of_birth, gender, email, admission_number, class_name, section_name, is_active, profile_photo_url (always null), attendance_percentage, total_certificates, total_documents` |
| `PUT /profile/student/me` | `email` | same as GET |
| `GET /profile/staff/me` | none | `staff_id, user_id, first_name, last_name, email, phone, designation, employee_id, date_of_joining, is_active, profile_photo_url` |
| `PUT /profile/staff/me` | `email`, `phone` | same as GET |
| `GET /profile/parent/me` | none | `parent_id, user_id, name, email, phone, occupation, relation_to_student, profile_photo_url, children[]` |
| `PUT /profile/parent/me` | `email`, `phone`, `occupation` | same as GET |

### Rules and validations
- Permission: `profile:read_own` for GET and `profile:update_own` for PUT. Missing grant: 403 with detail `{"error":"permission_denied","message":"Permission denied: <role> cannot <action> profile", ...}`.
- A user whose role does not match the endpoint (for example an Admin calling `/profile/student/me` with the grant) gets 404 "Student profile not found", "Staff profile not found" or "Parent profile not found".
- Update bodies are partial: omitted or null fields are untouched; unknown fields (the clients also send `phone` and `address` for students) are dropped silently. An empty string is stored as is.
- Emails and phones are not format-validated by the backend (the schemas use plain strings); web and mobile validate in the form.
- Staff and Parent email changes do not change `users.email`, so the login identifier does not change; a Student email change does.
- Student `attendance_percentage` = present records / total records x 100 rounded to 2 decimals (status "Present"); null when there are no attendance records. `class_name` and `section_name` come from the student's admission record.
- Every GET and PUT writes a `profile_audit_logs` row (view, update, or bulk update with old and new values); audit failures are logged and ignored. No endpoint reads the audit log.

### Error and edge cases
- Student with no admission: `admission_number`, `class_name`, `section_name` are null.
- Email longer than the `users.email` column (100 characters): the update fails with a database error (not 200).
- Admin or Teacher without a staff row: 404 on `/profile/staff/me`.
- Token of one tenant never reads another tenant's rows (row-level security).

### Unit-testable logic
Attendance percentage rounding; `StudentProfileUpdate`, `StaffProfileUpdate`, `ParentProfileUpdate` field sets and dropping of unknown keys; partial-update change tracking; web `ProfileRouter` role switch and the 403 or 404 fallback; mobile role-to-component choice.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-10-U01 | Attendance percentage with 3 Present of 4 records | 75.0 | passing |
| TC-AUTH-10-U02 | Attendance percentage with 1 Present of 3 | 33.33 | passing |
| TC-AUTH-10-U03 | Attendance percentage with no records | `None` | passing |
| TC-AUTH-10-U04 | `StudentProfileUpdate(email="a@b.c", phone="1", address="x")` | only `email` kept | passing |
| TC-AUTH-10-U05 | `StaffProfileUpdate(phone="9876543210")` | `email` is `None`; update changes only phone | passing |
| TC-AUTH-10-U06 | Staff update service with `email=None, phone=None` | no change recorded; no audit row written | passing |
| TC-AUTH-10-U07 | Web `ProfileRouter` with roles student, parent, admin, teacher, null | StudentProfile, ParentProfile, StaffProfile, StaffProfile, "Please log in to view your profile" | passing |
| TC-AUTH-10-U08 | Web `StaffProfile` when the query fails with status 403, and with 404 | "My Profile" fallback with Username, Email, Role, Academic Year | blocked: StaffProfile uses component hooks (useState, useForm) so it cannot be called without rendering (web/src/pages/staff/StaffProfile.tsx) |
| TC-AUTH-10-A01 | `GET /profile/student/me` as Student (grant present) | 200; all 14 documented fields; `profile_photo_url` null | planned |
| TC-AUTH-10-A02 | `GET /profile/staff/me` as Staff | 200; fields match the staff row | planned |
| TC-AUTH-10-A03 | `GET /profile/parent/me` as Parent with two children | 200; `children` has two items with `student_id, first_name, last_name, admission_number, class_name, section_name, is_active` | planned |
| TC-AUTH-10-A04 | Role matrix for each GET endpoint with the grant held by all five roles | only the matching role returns 200; the other four roles return 404 "<Student/Staff/Parent> profile not found" (Admin and Teacher have no student, parent record; Teacher may have a staff row) | planned |
| TC-AUTH-10-A05 | Same GET calls when the role lacks `profile:read_own` | 403 with `error` "permission_denied" | planned |
| TC-AUTH-10-A06 | `PUT /profile/student/me` `{"email":"new.student@example.com"}` | 200; response email updated; `users.email` updated; login with the new email succeeds | planned |
| TC-AUTH-10-A07 | `PUT /profile/student/me` with `{"email":"a@example.com","phone":"9999999999","address":"x"}` | 200; email updated; no other column changes | planned |
| TC-AUTH-10-A08 | `PUT /profile/staff/me` `{"email":"s2@example.com","phone":"9123456780"}` | 200; `staff.email` and `staff.phone` changed; `users.email` and username unchanged | planned |
| TC-AUTH-10-A09 | After A08 log in with the new phone number | 200 (phone lookup uses `staff.phone`) | planned |
| TC-AUTH-10-A10 | `PUT /profile/parent/me` `{"occupation":"Engineer"}` | 200; occupation "Engineer"; email and phone unchanged | planned |
| TC-AUTH-10-A11 | `PUT` with `{}` on each endpoint | 200; values unchanged | planned |
| TC-AUTH-10-A12 | `PUT /profile/student/me` `{"email":"not-an-email"}` | 200 and stored (documents that the backend does not validate) | planned |
| TC-AUTH-10-A13 | `PUT` without `profile:update_own` | 403 `permission_denied` | planned |
| TC-AUTH-10-A14 | No token (header only) | 401 "Authorization header missing or invalid" | planned |
| TC-AUTH-10-A15 | After one GET and one PUT, count `profile_audit_logs` rows for the user | two view rows (the GET and the re-read made by the PUT) and one update row | planned |
| TC-AUTH-10-A16 | `PUT /profile/student/me` with an email of 101 characters | non-2xx; stored email unchanged | planned |
| TC-AUTH-10-A17 | Student of `qa_school_b` and Student of `qa_school` each GET their profile | each sees only its own record; ids differ | planned |
| TC-AUTH-10-A18 | Student with no admission | `admission_number`, `class_name`, `section_name` null; `attendance_percentage` null | planned |
| TC-AUTH-10-E01 | Web: Student opens avatar menu > Profile | page "Student Profile" with "Personal Information" and "Academic Information" | planned |
| TC-AUTH-10-E02 | Web: Student clicks "Edit Email", enters `e2e.student@example.com`, submits | dialog closes; email shown updated | planned |
| TC-AUTH-10-E03 | Web: Student enters `abc` in the dialog | form message "Invalid email address"; no request | planned |
| TC-AUTH-10-E04 | Web: Staff opens Profile, "Edit Email & Phone", changes both | values shown updated | planned |
| TC-AUTH-10-E05 | Web: Admin opens Profile | "My Profile" with "Account Information" (Username, Email, Role, Academic Year) | planned |
| TC-AUTH-10-E06 | Web: Parent opens Profile | "My Profile" lists the children; the "Edit Profile" button is absent (documented gap) | planned |
| TC-AUTH-10-E07 | Web: Admin opens `/admin/profile`, "Edit Email", saves | toast "Admin profile updated successfully!" | planned |
| TC-AUTH-10-E08 | Mobile: Staff opens the Profile tab, "Edit Profile", changes Phone, saves | profile shows the new phone | planned |
| TC-AUTH-10-E09 | Mobile: Student edits email | profile shows the new email | planned |
| TC-AUTH-10-E10 | Mobile: Parent edits occupation | profile shows the new occupation | planned |
| TC-AUTH-10-E11 | Mobile: user without `profile:read_own` | fallback account view and a "Logout" button | planned |

Implemented in: `backend/tests/unit/auth/test_auth_profile_blacklist.py` (U01-U06); `web/src/__tests__/auth/profileAndForgot.test.ts` (U07).

## F11 Change password (self-service)

### Purpose
Let a signed-in user replace their own password after confirming the current one.

### Roles and permissions
`profile:update_own` (checked by `check_user_resource_access`) for every role. Admin has no profile permission unless the plan includes the `profile` resource or an administrator grants it (see Known gaps). UI entry exists for Admin only on web and mobile.

### Preconditions
A signed-in user who knows the current password, holding the permission.

### Steps, web
1. As Admin open `/admin/profile` ("Admin Profile") and click "Change Password".
2. In the dialog "Change Password" fill "Current Password", "New Password" and "Confirm New Password". Local messages: "Current password is required", "New password is required", "Password must be at least 8 characters", "Confirm password is required", "Passwords do not match". A second check shows the toast "New password and confirm password do not match."
3. Press "Change Password" ("Changing..." while waiting). The toast "Password changed successfully!" appears and the dialog closes; a server error shows "Failed to change password: <detail>".

### Steps, mobile
1. As Admin open "My Profile" (`/admin/profile`) and tap the row "Change Password".
2. On the screen "Change Password" fill "Current Password *" (placeholder "Enter current password"), "New Password *" (placeholder "Min 8 characters") and "Confirm New Password *" (placeholder "Re-enter new password"; the two new-password fields share one visibility toggle).
3. Tap "Change Password". Messages: "Current password is required", "New password must be at least 8 characters", "Passwords do not match"; success toast "Password changed successfully".

### Expected results
`users.password_hash` holds the new bcrypt hash; the old password stops working; a sensitive `profile_audit_logs` row is written; the response is `{"message": "Password changed successfully", "success": true}`. Existing tokens are not revoked.

### API endpoints
| Method and path | Request fields |
|---|---|
| `POST /profile/change-password` | `current_password` (min 1), `new_password` (min 8), `confirm_password` (min 8) |

### Rules and validations
- Order: body validation (422), permission (403), `new_password == confirm_password` (400 "New password and confirmation do not match"), user exists (404 "User not found"), current password correct (400 "Current password is incorrect"), save.
- No rule forbids reusing the current password; no complexity rule beyond length 8.
- Audit `profile_type` by role: Student `student`, Staff `staff`, Parent `parent`, Admin `admin`, SuperAdmin `superadmin`; Teacher and custom roles are recorded as `unknown`; the audit `org_id` holds the user id as a placeholder.
- The temporary-password flag is not touched (use F04 for first logins).

### Error and edge cases
- Wrong current password and mismatching confirmation together: the mismatch message wins.
- Mobile screen is reachable only from the Admin profile screen.
- Other sessions of the same user stay valid until their tokens expire.

### Unit-testable logic
`BaseProfileService.change_password` ordering and messages (fake session and audit); `PasswordChangeRequest` validation; role to `profile_type` map; web `AdminProfile` form rules; mobile `handleSubmit` checks.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-11-U01 | `PasswordChangeRequest` with empty `current_password` | validation error on `current_password` | passing |
| TC-AUTH-11-U02 | `PasswordChangeRequest` with 7-character `new_password`; with 7-character `confirm_password` | validation error on each field respectively | passing |
| TC-AUTH-11-U03 | `change_password` with different new and confirm values | HTTPException 400 "New password and confirmation do not match" before any lookup | passing |
| TC-AUTH-11-U04 | `change_password` with unknown user id | HTTPException 404 "User not found" | passing |
| TC-AUTH-11-U05 | `change_password` with wrong current password | HTTPException 400 "Current password is incorrect"; hash unchanged | passing |
| TC-AUTH-11-U06 | `change_password` success | stored value verifies against the new password and not the old; audit called once with `org_id` equal to the user id | passing |
| TC-AUTH-11-U07 | `role_to_profile_type` for Student, Staff, Parent, Admin, SuperAdmin, Teacher, "Librarian" | student, staff, parent, admin, superadmin, unknown, unknown | passing |
| TC-AUTH-11-U08 | Mobile `handleSubmit` with empty current; 7-character new; mismatching confirm | the three messages listed in the steps, in that order of precedence | blocked: handleSubmit is inline in mobile/app/profile/change-password.tsx and not exported |
| TC-AUTH-11-A01 | Admin (grant held) posts a valid change `{current, new "NewPass#2026", confirm same}` | 200 `{"message":"Password changed successfully","success":true}` | planned |
| TC-AUTH-11-A02 | After A01 log in with the old and with the new password | old 401 "Invalid Credentials"; new 200 | planned |
| TC-AUTH-11-A03 | Same change as Staff, Teacher, Student, Parent (each with the grant) | 200 each | planned |
| TC-AUTH-11-A04 | Wrong `current_password` | 400 "Current password is incorrect" | planned |
| TC-AUTH-11-A05 | `new_password` and `confirm_password` differ | 400 "New password and confirmation do not match" | planned |
| TC-AUTH-11-A06 | Wrong current and mismatch at once | 400 "New password and confirmation do not match" | planned |
| TC-AUTH-11-A07 | `new_password` and `confirm_password` of 7 characters | 422 on both fields | planned |
| TC-AUTH-11-A08 | `new_password` of exactly 8 characters | 200 | planned |
| TC-AUTH-11-A09 | `current_password` empty | 422 | planned |
| TC-AUTH-11-A10 | New password equal to the current one | 200 (no rule against reuse) | planned |
| TC-AUTH-11-A11 | Role without `profile:update_own` (parametrised over Staff, Teacher, Student, Parent, Admin) | 403 `permission_denied` for each | planned |
| TC-AUTH-11-A12 | No token (header only) | 401 "Authorization header missing or invalid" | planned |
| TC-AUTH-11-A13 | Use the access token issued before the change on `GET /auth/available-resources`, then refresh | 200 and 200 (tokens survive a password change) | planned |
| TC-AUTH-11-A14 | Audit: row in `profile_audit_logs` for the change | exists, flagged sensitive, `profile_type` per role (Teacher `unknown`) | planned |
| TC-AUTH-11-A15 | Tenant isolation: two users with the same username in `qa_school` and `qa_school_b`; change one password | the other tenant's user still logs in with the old password | planned |
| TC-AUTH-11-E01 | Web: Admin opens `/admin/profile`, "Change Password", correct values | toast "Password changed successfully!"; dialog closed | planned |
| TC-AUTH-11-E02 | Web: confirm field differs | field message "Passwords do not match"; no request | planned |
| TC-AUTH-11-E03 | Web: 7-character new password | message "Password must be at least 8 characters" | planned |
| TC-AUTH-11-E04 | Web: wrong current password | toast starting "Failed to change password:" with "Current password is incorrect" | planned |
| TC-AUTH-11-E05 | Web: after a change log out and log in with the new password | login succeeds | planned |
| TC-AUTH-11-E06 | Mobile: Admin "My Profile" > "Change Password" with valid values | toast "Password changed successfully" | planned |
| TC-AUTH-11-E07 | Mobile: confirmation differs | inline text "Passwords do not match"; submit shows the same message | planned |
| TC-AUTH-11-E08 | Mobile: wrong current password | error toast with "Current password is incorrect" | planned |

Implemented in: `backend/tests/unit/auth/test_auth_profile_blacklist.py` (U01-U07).

## F12 Forgot and reset password

### Purpose
Help a user who cannot sign in. COS360 has no self-service reset: the school administrator resets the password for them.

### Roles and permissions
Forgot-password pages need no login. The administrator's reset (`user_management:update`, Admin by default) is documented in TEN F13.

### Preconditions
None for the pages; an Admin account for the reset.

### Steps, web
1. On `/login` click "Forgot your password?". The page `/forgot-password` shows "Forgot your password?", "Password reset by email is not available yet." and "Please contact your school administrator. They can reset your password and give you a temporary one to sign in with.", with a link "Back to login".
2. The administrator opens Administration > Users, uses the Reset Password action (TEN F13) and gives the user the new password.
3. The user signs in with it. The user is not forced to change it (the reset does not set `is_first_login`).

### Steps, mobile
1. On the sign-in form tap "Forgot Password?". The screen shows the same text under "Forgot Password?" with "Back to Login" at the top and as a button.
2. The administrator resets the password as on web; the user signs in with it.

### Expected results
No email or code is sent; no token is created. After the administrator's reset the old password stops working and the new one works.

### API endpoints
There is no forgot-password or reset-password endpoint. The administrator's reset is `POST /admin/users/{id}/reset-password` (TEN F13).

### Rules and validations
- No self-service reset; no email integration.
- The web and mobile pages are static text; they send no request.
- Admin reset sets the password hash only (min 8 characters); it writes no audit row and does not revoke existing tokens.

### Error and edge cases
- A user reached by a stale link or typed URL while logged in is redirected to `/dashboard` on web.
- The page wording says "temporary" although the reset password is permanent.

### Unit-testable logic
None in the backend. Web `ForgotPasswordForm` and mobile `ForgotPasswordScreen` render the fixed text and the back link.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-12-U01 | Render web `ForgotPasswordForm` | shows the three texts above and a link to `/login` | passing |
| TC-AUTH-12-U02 | Render mobile `ForgotPasswordScreen` | shows "Forgot Password?" and "Back to Login"; pressing it replaces the route with `/login` | blocked: mobile ForgotPasswordScreen needs rendering (mobile/app/forgot-password.tsx) |
| TC-AUTH-12-A01 | `POST /auth/forgot-password` and `POST /auth/reset-password` with header `cschema` | 404 for both (no such routes) | planned |
| TC-AUTH-12-A02 | Admin resets a Staff password through `POST /admin/users/{id}/reset-password`, then Staff logs in with the new password | 200 with tokens and no first-login challenge | planned |
| TC-AUTH-12-A03 | After A02 the old password | 401 "Invalid Credentials" | planned |
| TC-AUTH-12-A04 | Reset by a non-Admin (Staff, Teacher, Student, Parent) | 403 "Permission not found in database: <role> cannot update user_management. Contact administrator to configure permissions." | planned |
| TC-AUTH-12-E01 | Web: on `/login` click "Forgot your password?" | page `/forgot-password` with the explanation text; "Back to login" returns to `/login` | planned |
| TC-AUTH-12-E02 | Web: Admin resets a user's password in Administration > Users, then that user signs in | sign-in succeeds on the first try with the new password | planned |
| TC-AUTH-12-E03 | Mobile: tap "Forgot Password?" | screen with "Password reset by email is not available yet." and the administrator note | planned |
| TC-AUTH-12-E04 | Mobile: tap "Back to Login" (top) and "Back to Login" (button) | both return to the sign-in form | planned |

Implemented in: `web/src/__tests__/auth/profileAndForgot.test.ts` (U01, component function called without rendering).

## F13 Access validation helpers (API only)

### Purpose
Let a client or tool ask whether a given user may reach an endpoint or a menu item. No screen uses these endpoints.

### Roles and permissions
Any authenticated tenant user (valid access token); no resource permission is checked. The result reflects the target user's role grants only, not the plan.

### Preconditions
A signed-in caller and the id of a user in the same tenant.

### Steps, web
Not available in the web app.

### Steps, mobile
Not available in the mobile app (the mobile `mobilePermissions` calls target other paths that do not exist).

### Expected results
A JSON verdict with `has_access`, the resolved resource and action and a denial reason.

### API endpoints
| Method and path | Request | Response |
|---|---|---|
| `POST /auth/validate-access` | body `user_id` (UUID), optional `endpoint`, `menu_item`, `action` (default `read`; one of create, read, update, delete, list, export, approve, import, bulk_delete) | `has_access, reason, user_role, resource, action` |
| `POST /auth/validate-endpoint-access` | query `user_id`, `endpoint`, `action` (default `read`), `http_method` (default `GET`) | `has_access, user_id, endpoint, action, http_method` |
| `POST /auth/validate-menu-access` | query `user_id`, `menu_item`, `action` (default `read`) | `has_access, user_id, menu_item, action` |
| `GET /auth/available-resources` | none | `resources, actions, total_resources, total_actions` |

### Rules and validations
- The target user must exist in the tenant and be active, else `has_access` false with reason "User not found or inactive".
- Resource and action come from `ENDPOINT_RESOURCE_MAPPING` (endpoint, normalised) or `MENU_RESOURCE_MAPPING` (menu key, lower case); an explicit `action` other than `read` overrides the mapped one. Example: endpoint `/api/v1/fee/categories` resolves to `fee_categories:list`; menu `fee_categories` resolves to `fee_categories:read`.
- Unresolvable endpoint or menu: `has_access` false, reason "Could not resolve resource from endpoint or menu item".
- Denied: reason "Access denied: <role> cannot <action> <resource> or plan limitation".
- `action` outside the list: 422. The endpoints are rate limited by `rate_limit_api()`.
- Any authenticated user can query any user id of the tenant (no admin restriction).
- The simplified endpoints return 500 with an error object when the service raises.

### Error and edge cases
- Both `endpoint` and `menu_item` omitted: 200 with `has_access` false and the "Could not resolve" reason (the schema does not reject it).
- `user_id` that is not a UUID on the query-parameter variants: `has_access` false (service error is caught) or 500.
- A user of another tenant is not found (row-level security).

### Unit-testable logic
`get_resource_from_endpoint`, `get_resource_from_menu`, `normalize_endpoint`, `AccessValidationService.resolve_resource_action` override rule, `AccessValidationRequest` validators, `get_all_resources`, `get_all_actions` (32 resources, 9 actions).

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-13-U01 | `get_resource_from_endpoint("/api/v1/fee/categories","GET")` and `"POST"` | `("fee_categories","list")` for both | passing |
| TC-AUTH-13-U02 | `get_resource_from_endpoint("/api/v1/fee/categories/dropdown","GET")` | `("fee_categories","read")` | passing |
| TC-AUTH-13-U03 | `get_resource_from_endpoint("/api/v1/nothing/here","GET")` | `None` | passing |
| TC-AUTH-13-U04 | `get_resource_from_menu("fee_categories")` and `("zzz")` | `("fee_categories","read")`; `None` | passing |
| TC-AUTH-13-U05 | `resolve_resource_action` with endpoint `/api/v1/fee/categories`, action `delete` | `("fee_categories","delete")` (override) | passing |
| TC-AUTH-13-U06 | `resolve_resource_action` with action `read` | keeps the mapped action `list` | passing |
| TC-AUTH-13-U07 | `AccessValidationRequest(action="DELETE")`, `action="bogus"` | `delete`; validation error listing the nine valid actions | passing |
| TC-AUTH-13-U08 | `AccessValidationRequest` with neither `endpoint` nor `menu_item` | model accepted (action `read`) | passing |
| TC-AUTH-13-U09 | `get_all_actions()` | `approve, bulk_delete, create, delete, export, import, list, read, update` | passing |
| TC-AUTH-13-A01 | `POST /auth/validate-access` for the Admin user, endpoint `/api/v1/fee/categories` | 200; `has_access` true; `resource` `fee_categories`; `action` `list`; `user_role` "Admin" | planned |
| TC-AUTH-13-A02 | Same for the Teacher user | 200; `has_access` false; `reason` starts "Access denied: Teacher cannot list fee_categories" | planned |
| TC-AUTH-13-A03 | `menu_item` `fee_categories` for Admin | `has_access` true; action `read` | planned |
| TC-AUTH-13-A04 | Endpoint `/api/v1/nothing/here` | `has_access` false; reason "Could not resolve resource from endpoint or menu item" | planned |
| TC-AUTH-13-A05 | Random `user_id` | `has_access` false; reason "User not found or inactive" | planned |
| TC-AUTH-13-A06 | Deactivated user | `has_access` false; reason "User not found or inactive" | planned |
| TC-AUTH-13-A07 | `action` "bogus" | 422 | planned |
| TC-AUTH-13-A08 | Staff token validating the Admin user's access | 200 (any authenticated user may ask) | planned |
| TC-AUTH-13-A09 | `POST /auth/validate-endpoint-access?user_id=<admin>&endpoint=/api/v1/fee/types` | 200 `{has_access:true, user_id, endpoint, action:"read", http_method:"GET"}` | planned |
| TC-AUTH-13-A10 | `POST /auth/validate-menu-access?user_id=<student>&menu_item=fee_categories` | 200; `has_access` false | planned |
| TC-AUTH-13-A11 | `GET /auth/available-resources` | 200; `total_resources` equals `len(resources)`; `total_actions` 9 | planned |
| TC-AUTH-13-A12 | Any of the four calls without a token (header only) | 401 "Authorization header missing or invalid" | planned |
| TC-AUTH-13-A13 | `user_id` of a `qa_school_b` user with a `qa_school` token | `has_access` false; reason "User not found or inactive" (tenant isolation) | planned |
| TC-AUTH-13-A14 | Neither `endpoint` nor `menu_item` | 200; `has_access` false; "Could not resolve resource from endpoint or menu item" | planned |

Implemented in: `backend/tests/unit/auth/test_auth_permissions_menu.py` (U01-U09).

## F14 Logout

### Purpose
End the session: remove it from the device and make the tokens unusable on the server.

### Roles and permissions
No permission; any holder of a valid token.

### Preconditions
A signed-in session.

### Steps, web
1. Open the user menu (avatar and username) in the navbar and click "Logout".
2. The app calls `POST /auth/logout` with the access token (header) and the refresh token (body), clears the store and the query cache, and goes to `/login`. If the call fails, the local session is still cleared.

### Steps, mobile
1. Open the Profile tab and tap "Logout"; confirm in the dialog titled "Logout" (button "Logout").
2. The app reads its tokens, clears all stored session data (including the saved organisation), sends `POST /auth/logout` in the background with both tokens, resets the parent student headers, and opens `/login`, which asks for the organisation again.

### Expected results
Both tokens are blacklisted (SHA-256 hash in `public.token_blacklist` with the token's expiry); the client holds no tokens, user, permissions or menu.

### API endpoints
| Method and path | Request |
|---|---|
| `POST /auth/logout` | header `Authorization: Bearer <access>`; optional body `{"refresh_token": "<refresh>"}` |

### Rules and validations
- Response 200: `{"message":"Logout successful","instructions":{"clear_tokens":true,"clear_menu":true,"redirect_to":"/login"}}`.
- A valid access token is blacklisted; an expired or invalid access token is skipped when a refresh token is given, so the refresh token is still revoked. With neither token: 401 "Authorization header missing or invalid". With only an invalid access token: 401 "Invalid token". When nothing could be revoked: 401 "Invalid or expired token".
- Blacklist checks run on every authenticated request through `get_current_user_token` (401 "Token has been invalidated. Please login again.") and on refresh. A database error in the check is treated as not blacklisted (fail open).
- The table `public.token_blacklist` stores hashes, user id, username, client name and `expires_at`; repeated logout is idempotent (`ON CONFLICT DO NOTHING`). `cleanup_expired()` exists but is not scheduled.
- Only the tokens sent are revoked: other sessions of the same user stay valid.

### Error and edge cases
- Logout twice with the same tokens: both 200.
- Logout with the access token only: the refresh token still works.
- Backend unreachable: web and mobile clear local state anyway.
- Expired access token and valid refresh token in the body: 200, refresh token revoked.

### Unit-testable logic
`_hash_token` (SHA-256 hex), `blacklist_token` expiry (from `exp`, else 24 h), `is_blacklisted` including fail-open, logout endpoint branching (fake blacklist service), web `useLogoutMutation` (clears on success and on error), mobile `logoutUser` ordering.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-AUTH-14-U01 | `_hash_token("abc")` | 64-character lowercase hex of SHA-256 | passing |
| TC-AUTH-14-U02 | `blacklist_token` with payload `exp` | stored `expires_at` equals the `exp` instant as naive UTC | passing |
| TC-AUTH-14-U03 | `blacklist_token` with payload without `exp` | `expires_at` about 24 hours from now | passing |
| TC-AUTH-14-U04 | `is_blacklisted` when the session raises | returns `False` | passing |
| TC-AUTH-14-U05 | Logout handler with neither header nor body (fake service) | HTTPException 401 "Authorization header missing or invalid" | passing |
| TC-AUTH-14-U06 | Logout handler with an invalid access token and no refresh token | HTTPException 401 "Invalid token" | passing |
| TC-AUTH-14-U07 | Logout handler with invalid access and invalid refresh tokens | HTTPException 401 "Invalid or expired token" | passing |
| TC-AUTH-14-U08 | Web `useLogoutMutation` when the request rejects | `logout()` and `queryClient.clear()` still called | passing |
| TC-AUTH-14-U09 | Mobile `logoutUser` | reads the tokens, then clears storage, then posts logout with `_retry` set; a failing post does not throw | passing |
| TC-AUTH-14-A01 | Logout with access token in the header and refresh token in the body | 200 with the documented body | planned |
| TC-AUTH-14-A02 | Use the access token after A01 on `GET /auth/available-resources` | 401 "Token has been invalidated. Please login again." | planned |
| TC-AUTH-14-A03 | Refresh with the refresh token after A01 | 401 "Refresh token has been invalidated. Please login again." | planned |
| TC-AUTH-14-A04 | Logout with the access token only, then refresh | logout 200; refresh 200 (documents that only sent tokens are revoked) | planned |
| TC-AUTH-14-A05 | Logout with an expired access token and a valid refresh token in the body | 200; refresh token no longer works | planned |
| TC-AUTH-14-A06 | Logout with no Authorization header and no body | 401 "Authorization header missing or invalid" | planned |
| TC-AUTH-14-A07 | Logout with a garbage bearer token and no body | 401 "Invalid token" | planned |
| TC-AUTH-14-A08 | Logout with a garbage bearer token and a garbage refresh token | 401 "Invalid or expired token" | planned |
| TC-AUTH-14-A09 | Repeat A01 with the same tokens | 200 again; one row per token in `public.token_blacklist` | planned |
| TC-AUTH-14-A10 | Inspect the blacklist row | `token_hash` is the SHA-256 of the token; the raw token is not stored; `expires_at` equals the token expiry | planned |
| TC-AUTH-14-A11 | Same user logs in twice (two sessions), logs out session 1 | session 2 tokens still work | planned |
| TC-AUTH-14-A12 | Staff logs out | Admin's tokens unaffected | planned |
| TC-AUTH-14-A13 | Role parametrisation of A01 for Admin, Staff, Teacher, Student, Parent | 200 for each (no permission needed) | planned |
| TC-AUTH-14-A14 | Logout, then log in again with the same credentials | 200 with new tokens (login is not blocked) | planned |
| TC-AUTH-14-E01 | Web: avatar menu > "Logout" | redirected to `/login`; `auth-storage` holds no tokens | planned |
| TC-AUTH-14-E02 | Web: after logout press the browser back button | `/login` (private page not shown) | planned |
| TC-AUTH-14-E03 | Web: capture the access token, log out, call the API with it | 401 "Token has been invalidated. Please login again." | planned |
| TC-AUTH-14-E04 | Web: network logged offline during logout | UI still returns to `/login` with an empty store | planned |
| TC-AUTH-14-E05 | Mobile: Profile tab > "Logout" > confirm | login screen opens at "Select Organization" | planned |
| TC-AUTH-14-E06 | Mobile: Profile tab > "Logout" > cancel | dialog closes; session stays | planned |
| TC-AUTH-14-E07 | Mobile: Parent logs out and another Parent logs in | no child from the first parent is shown | planned |

Implemented in: `backend/tests/unit/auth/test_auth_profile_blacklist.py` (U01-U07); `web/src/__tests__/auth/apiAuthHooks.test.ts` (U08); `mobile/__tests__/auth/authUtils.test.ts` (U09).

## Known gaps

Code behaviour differs from `docs/modules/auth.md` or the architecture documents in these places (this file follows the code):

1. A missing `academic_year_id` returns 422, not 400. The 400 "Academic year is required" exists only in the service and is unreachable through `POST /auth/login`.
2. The mobile screen "Change Password" is opened only from the Admin screen "My Profile"; no other role has an entry to it (the module doc says all roles).
3. The web Staff Profile page no longer 404s for an Admin without a staff record: it shows "My Profile" with "Account Information" on 403 or 404.
4. The token blacklist is a migrated table (`public.token_blacklist`), not created lazily as module rule 18 says.
5. Mobile logout removes the stored organisation (`clearAuthData` deletes `@auth/client_schema`), so the user is asked for it again; module rule 9 describes the organisation as kept after login only.
6. `TenantMiddleware.sanitize_client_name` lowercases and strips spaces, so a tenant name containing a space (module doc example "little bunny") cannot be addressed; new tenants cannot have spaces (TEN F07).
7. Fixed (2026-10-05): `TenantMiddleware` now returns the 400 as a JSON response; a missing or invalid `cschema` header with no token used to surface as 500.
   Fixed (2026-10-05): `POST /profile/change-password` returned 500 on every success because `BaseProfileService` passed `profile_type` to `ProfileAuditService.log_password_change`, which did not accept it; the audit row now stores the real profile type.
8. Default seed: `permission_catalog.py` gives `profile:read_own` and `profile:update_own` only to Student. The `Full` plan built by `CatalogService.ensure_full_plan` copies `ALL_ADMIN`, which has no `profile` resource and no `_own` or `_related` actions, and role seeding keeps a non-Admin pair only if the plan lists it. On such a tenant (the QA tenant) no role, Admin included, can call the profile endpoints or `POST /profile/change-password`, and Student and Parent lose their self-service grants. The phase 2 tests grant `profile:read_own` and `profile:update_own` explicitly.
9. The web parent profile editor sends `PUT /profile/parent` (the backend route is `PUT /profile/parent/me`) and shows its button only for `parent_profile:update_own`, a resource that does not exist; parents cannot edit their profile on web.
10. `POST /auth/refresh` does not rotate or revoke the previous refresh token; a deactivated user's current access token stays valid until it expires; admin password reset does not revoke sessions or force a change.
11. `/auth/validate-access` and its siblings let any authenticated user query any user of the tenant.
12. Mobile login requires 6 characters locally while the backend has no minimum on login (minimum 8 applies when setting a password).
13. `/auth/seed/*` and super admin setup endpoints are covered in TEN F17; the web `/superorg` page is covered in TEN F09.
