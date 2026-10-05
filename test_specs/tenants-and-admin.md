# Tenants, platform and admin (TEN)

How the COS360 platform is set up and administered: the platform super admin who bootstraps the system, signs in, manages plans and creates schools (tenants); the default roles, permissions and menus each new school receives; the tenant administrator who manages school settings, user accounts, roles and permissions; and the cross-tenant rules that keep one school's data away from another. Tenants share one database and one schema, separated by `tenant_id` and row-level security. Tenant-user sign-in, profiles and sessions are in `docs/features/auth.md` (AUTH). Module rules and gotchas: `docs/modules/tenants-and-admin.md`; system design: `docs/architecture.md`, `docs/permissions.md`. Conventions and test case IDs: `docs/testing/strategy.md`, `docs/features/README.md`.

_Last verified against code: 2026-10-02_

## Roles

| Role | What it does in this module |
|---|---|
| Super admin (platform) | Account in `public.super_admin_users`, token with `user_type: "super_admin"`. Bootstraps the platform, manages super admin accounts, plans, plan resources, tenants (create, activate or deactivate, change plan), reads any tenant's users, students, stats, roles, reports and adds role permissions there, checks system health. No web or mobile screen works for it |
| Admin | Tenant administrator. Seeded with every action of the tenant's plan plus `role_management:*`. Manages school settings, user accounts, custom roles and role permissions, menus and the seeding endpoint |
| Staff | No access to any feature of this module (all admin endpoints answer 403), except that `GET /admin/role-mgmt/roles/` answers any authenticated user |
| Teacher | Same as Staff |
| Student | Same as Staff |
| Parent | Same as Staff |
| Custom roles | Can be given any `resource:action` through role permission management; no seed |

Test fixtures used below: the QA tenant `qa_school` provisioned from the `Full` plan with the demo menu catalog (70 menus), one QA login per role and one QA super admin (credentials from `backend/.env.test`, never written in documents), a second tenant `qa_school_b` created by the test setup through `POST /super_admin/system/tenants/`, and a plan `Lite` created by the tests (resources `academic_years:[read,list]` and `students:[list]`, one plan menu `/dashboard`). "Header" means the `cschema` request header. Counts that depend on the permission catalog (`permission_catalog.py`) are stated for the catalog at the verification date. Menu catalog and plan-menu rows have no delete endpoint; tests that create them remove them directly in `cos360_test`.

## Feature index

| ID | Title |
|---|---|
| F01 | Platform bootstrap (super admin setup) |
| F02 | Super admin login and lockout |
| F03 | Super admin account management |
| F04 | Plans |
| F05 | Plan resources |
| F06 | Menu catalog and role-menu links |
| F07 | Tenant provisioning |
| F08 | Default role and permission seeding |
| F09 | Tenant list, activation and plan change |
| F10 | Super admin tenant data views |
| F11 | Platform monitoring |
| F12 | School settings |
| F13 | User management |
| F14 | Role management |
| F15 | Role permissions and resource-permission management |
| F16 | Tenant resolution and isolation |
| F17 | Seed, legacy and unguarded endpoints |

## F01 Platform bootstrap (super admin setup)

### Purpose
Create the first platform super admin on a fresh system and check whether the super admin tables are ready.

### Roles and permissions
No authentication. Both endpoints are reachable by anyone who can reach the server (see Known gaps).

### Preconditions
The server environment variable `SUPER_ADMIN_INITIAL_PASSWORD` is set for initialisation; the migrations have created `public.super_admin_users` and `public.super_admin_audit`.

### Steps, web
Not available: no screen.

### Steps, mobile
Not available: no screen.

### Expected results
`POST /super_admin/setup/initialize` creates the user `superadmin` (email `superadmin@cos360.com`, name "System Administrator", `requires_password_change` true) and an audit row `SYSTEM_SETUP`, and returns the credentials, including the password taken from the environment. `GET /super_admin/setup/status` reports table presence and the number of super admins.

### API endpoints
| Method and path | Notes |
|---|---|
| `POST /super_admin/setup/initialize` | No body; status 201 |
| `GET /super_admin/setup/status` | Returns `system_status`, `tables_exist`, `missing_tables`, `super_admin_count`, `ready_for_login` |

### Rules and validations
- Without `SUPER_ADMIN_INITIAL_PASSWORD`: 400 "Set SUPER_ADMIN_INITIAL_PASSWORD in the server environment before running setup" (checked first).
- When any super admin already exists: 409 "Super Admin system is already initialized".
- The user insert uses `ON CONFLICT (username) DO NOTHING`, so a second run cannot duplicate `superadmin`.
- The response echoes the plain password with the warning "CHANGE PASSWORD IMMEDIATELY AFTER FIRST LOGIN".
- The code runs `CREATE TABLE IF NOT EXISTS` and index statements inside the request; `docs/architecture.md` states that the application database role cannot run DDL, so a successful first run is not guaranteed (Known gaps).
- `status`: `system_status` is `initialized` when both tables exist, else `not_initialized`; `ready_for_login` needs both tables and at least one super admin.

### Error and edge cases
- Any database error: 500 "Failed to initialize Super Admin system: <error text>" (the error text leaks).
- The setup routes stay mounted in every environment.

### Unit-testable logic
The decision order in `initialize_super_admin_system` (password setting, existing super admin, insert) with a fake session; status computation from the table list.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-01-U01 | `initialize` with `settings.SUPER_ADMIN_INITIAL_PASSWORD = None` | HTTPException 400 with the "Set SUPER_ADMIN_INITIAL_PASSWORD ..." detail; no session opened | passing |
| TC-TEN-01-U02 | `initialize` with the password set and a fake session reporting an existing super admin row | HTTPException 409 "Super Admin system is already initialized" | passing |
| TC-TEN-01-U03 | `check_super_admin_status` with both tables and 1 user; with only `super_admin_users`; with none | `initialized`, ready true; `not_initialized`, missing `["super_admin_audit"]`, ready false; `not_initialized`, both missing, count 0 | passing |
| TC-TEN-01-A01 | `GET /super_admin/setup/status` on the QA database, no token and no header | 200; `system_status` "initialized"; `tables_exist` `["super_admin_audit","super_admin_users"]`; `missing_tables` `[]`; `super_admin_count` at least 1; `ready_for_login` true | passing |
| TC-TEN-01-A02 | `POST /super_admin/setup/initialize` with the environment password unset (test app configured without it) | 400 "Set SUPER_ADMIN_INITIAL_PASSWORD in the server environment before running setup" | passing |
| TC-TEN-01-A03 | `POST /super_admin/setup/initialize` with the password set while the QA super admin exists | 409 "Super Admin system is already initialized" | blocked: the test API runs without SUPER_ADMIN_INITIAL_PASSWORD, so the 409 branch is unreachable and the server cannot be restarted |
| TC-TEN-01-A04 | `POST /super_admin/setup/initialize` against an empty throwaway database (no super admin rows, app role as in production) | per code 201 with `initial_credentials.username` "superadmin", `email` "superadmin@cos360.com", `password` equal to the environment value, `login_endpoint` "POST /api/v1/super_admin/auth/login"; if the app role lacks DDL rights the result is 500 "Failed to initialize Super Admin system: ..." and is recorded as a known gap | blocked: needs an empty throwaway database and the creation of a super admin, which the task forbids |
| TC-TEN-01-A05 | After A04, log in as `superadmin` | 200; the database row has `requires_password_change` true | blocked: depends on TC-TEN-01-A04 (needs the creation of a super admin) |
| TC-TEN-01-A06 | `GET /super_admin/setup/status` with a tenant Admin token | 200 (no authentication check; documents the gap) | passing |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_super_admin.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f01_f03_super_admin.py`.

## F02 Super admin login and lockout

### Purpose
Let a platform super admin sign in and receive a token for the `/super_admin/*` routes, with protection against password guessing.

### Roles and permissions
Public endpoint; only rows of `public.super_admin_users`. Tenant users cannot sign in here.

### Preconditions
A super admin account (F01 or F03). No tenant header is needed for super admin routes.

### Steps, web
Not available: there is no super admin login screen. The page `/superorg` is inside the tenant-authenticated area and does not sign in as a super admin (see F09).

### Steps, mobile
Not available.

### Expected results
`POST /super_admin/auth/login` returns `access_token` (24 h), `refresh_token` (7 days, carries only `sub`), `token_type` "bearer", `expires_in` 86400, `user_type` "super_admin". On success `failed_login_attempts` resets to 0, `account_locked_until` clears, `last_login_at` is set and an audit row `LOGIN` is written.

### API endpoints
| Method and path | Request fields |
|---|---|
| `POST /super_admin/auth/login` | `username`, `password` |

### Rules and validations
- Order: unknown username (401 "Invalid credentials"), locked account (423 "Account is temporarily locked due to multiple failed login attempts"), password check (wrong: counter plus 1, 401 "Invalid credentials"), active check (403 "Account is deactivated").
- The 5th consecutive failure sets `account_locked_until` to now plus 30 minutes and still answers 401; later attempts, even with the correct password, answer 423 until the time passes.
- Access token claims: `sub`, `username`, `user_type: "super_admin"`, `is_superadmin`, `bypass_permissions`, `ultimate_access`, `permissions` `["system_admin","tenant_management","plan_management"]`, `exp`, `token_type: "access"`. No `role` or `tenant_id`.
- The refresh token cannot be used: `POST /auth/refresh` needs a tenant claim (AUTH F08). There is no super admin refresh or logout, and super admin tokens are not checked against the blacklist.
- The client IP is recorded in the audit row.

### Error and edge cases
- Tenant `/auth/login` credentials do not work here and the reverse.
- A deactivated account with a wrong password still increments the counter (401).
- A super admin token on a tenant endpoint gets 403 because the token has no role; with no header and no tenant claim the tenant cannot be resolved (404).

### Unit-testable logic
`SuperAdminService.authenticate_super_admin`: counter, lock time, order of checks, token claims (fake session and clock); `SuperAdminLogin` and `SuperAdminToken` schemas.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-02-U01 | `authenticate_super_admin` with four wrong passwords | counter 4; `account_locked_until` still `None`; each raises 401 "Invalid credentials" | passing |
| TC-TEN-02-U02 | Fifth wrong password | counter 5; `account_locked_until` about 30 minutes ahead; raises 401 | passing |
| TC-TEN-02-U03 | Correct password while locked | HTTPException 423 "Account is temporarily locked due to multiple failed login attempts" | passing |
| TC-TEN-02-U04 | Correct password after the lock time passed | success; counter 0; `account_locked_until` `None`; `last_login_at` set | passing |
| TC-TEN-02-U05 | Inactive account with the correct password | HTTPException 403 "Account is deactivated" | passing |
| TC-TEN-02-U06 | Inactive account with a wrong password | HTTPException 401; counter plus 1 | passing |
| TC-TEN-02-U07 | Unknown username | HTTPException 401 "Invalid credentials"; no counter change | passing |
| TC-TEN-02-U08 | Access token decoded after success | claims as listed (including three permission strings); refresh token has `sub` and `token_type` `refresh` only | passing |
| TC-TEN-02-U09 | `SuperAdminToken` defaults | `token_type` "bearer", `user_type` "super_admin" | passing |
| TC-TEN-02-A01 | Login as the QA super admin | 200; `access_token`, `refresh_token`, `token_type` "bearer", `expires_in` 86400, `user_type` "super_admin" | passing |
| TC-TEN-02-A02 | Wrong password | 401 "Invalid credentials" | passing |
| TC-TEN-02-A03 | Unknown username | 401 "Invalid credentials" (same body as A02) | passing |
| TC-TEN-02-A04 | Register a throwaway super admin (F03), fail five logins, then log in correctly | attempts 1 to 5: 401; attempt 6 with the right password: 423 | blocked: needs a throwaway super admin and the task forbids creating super admins; failing five logins on the shared QA account would lock it |
| TC-TEN-02-A05 | After A04 set `account_locked_until` to the past in the database, log in | 200; `failed_login_attempts` 0 | blocked: needs a throwaway super admin and the task forbids creating super admins; failing five logins on the shared QA account would lock it |
| TC-TEN-02-A06 | Deactivate the throwaway account (F03), log in with the right password | 403 "Account is deactivated" | blocked: needs a throwaway super admin and the task forbids creating super admins; failing five logins on the shared QA account would lock it |
| TC-TEN-02-A07 | Use the super admin access token on `GET /super_admin/auth/profile` | 200 | passing |
| TC-TEN-02-A08 | Use the super admin refresh token as bearer on `GET /super_admin/auth/profile` | 401 "Invalid token type" | passing |
| TC-TEN-02-A09 | Send the super admin refresh token to `POST /auth/refresh` with header `qa_school` | 401 "Your session is out of date. Please log in again." | passing |
| TC-TEN-02-A10 | Super admin token on `GET /admin/users/` with header `qa_school` | 403 "Permission not found in database: None cannot list user_management. Contact administrator to configure permissions." | passing |
| TC-TEN-02-A11 | Same call with no header | 404 "Tenant '' not found or inactive" | passing |
| TC-TEN-02-A12 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens on `GET /super_admin/auth/profile` | 403 "Super Admin access required" for each | passing |
| TC-TEN-02-A13 | `GET /super_admin/auth/profile` with no token | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-02-A14 | Tenant `qa_school` Admin credentials posted to `/super_admin/auth/login` | 401 "Invalid credentials" | passing |
| TC-TEN-02-A15 | After a successful login query `super_admin_audit` | a row with action `LOGIN`, resource `authentication` and the client IP | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |
| TC-TEN-02-A16 | Login body without `password` | 422 naming `password` | passing |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_super_admin.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f01_f03_super_admin.py`.

## F03 Super admin account management

### Purpose
Let a super admin register further super admins, view and edit its own profile and change its own password.

### Roles and permissions
Super admin token only (`get_current_super_admin`). Tenant tokens: 403 "Super Admin access required". No token: 401.

### Preconditions
A signed-in super admin (F02).

### Steps, web
Not available.

### Steps, mobile
Not available.

### Expected results
New accounts appear in `public.super_admin_users` with a bcrypt hash; profile edits and password changes are stored; audit rows are written (`CREATE`, `UPDATE`, `PASSWORD_CHANGE`).

### API endpoints
| Method and path | Request fields |
|---|---|
| `POST /super_admin/auth/register` | `username` (3 to 100), `email`, `full_name` (2 to 255), `password` (8 to 255), `is_active` (default true) |
| `GET /super_admin/auth/profile` | none |
| `PUT /super_admin/auth/profile` | `email`, `full_name`, `is_active` (all optional) |
| `POST /super_admin/auth/change-password` | `current_password`, `new_password` (8 to 255) |

### Rules and validations
- Register: duplicate username 400 "Username already exists"; duplicate email 400 "Email already exists"; status 201; response has `id, username, email, full_name, is_active, last_login_at, password_changed_at, created_at, updated_at, failed_login_attempts, account_locked_until, requires_password_change` and no hash.
- Profile update: email must be unique among other accounts (400 "Email already exists"); a super admin can set its own `is_active` to false.
- Change password: wrong current 400 "Current password is incorrect"; success `{"message":"Password changed successfully"}`; sets `requires_password_change` false and `password_changed_at`.
- Existing tokens stay valid after a password change or deactivation until they expire.

### Error and edge cases
- `email` that is not an address: 422.
- Updating with an empty body: 200, unchanged apart from `updated_at`.
- Audit write failures are logged and ignored.

### Unit-testable logic
`SuperAdminCreate`, `SuperAdminUpdate`, `SuperAdminPasswordChange` validation boundaries; `create_super_admin` duplicate checks, `update_super_admin` email uniqueness, `change_password` (fake session).

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-03-U01 | `SuperAdminCreate` username of 2, 3, 100, 101 characters | rejected, accepted, accepted, rejected | passing |
| TC-TEN-03-U02 | `SuperAdminCreate` password of 7, 8, 255, 256 characters | rejected, accepted, accepted, rejected | passing |
| TC-TEN-03-U03 | `SuperAdminCreate` `full_name` of 1, 2 characters; email `abc` | rejected, accepted; rejected | passing |
| TC-TEN-03-U04 | `SuperAdminUpdate()` with no fields | valid; all fields `None` | passing |
| TC-TEN-03-U05 | `create_super_admin` with an existing username, then an existing email (fake session) | HTTPException 400 "Username already exists"; 400 "Email already exists" | passing |
| TC-TEN-03-U06 | `change_password` with the wrong current password | HTTPException 400 "Current password is incorrect"; hash unchanged | passing |
| TC-TEN-03-U07 | `change_password` success | new hash verifies; `requires_password_change` false | passing |
| TC-TEN-03-A01 | Register `qa_sa_2` (valid body) as the QA super admin | 201; body lacks any password field; `failed_login_attempts` 0; `requires_password_change` false | blocked: creating a super admin is forbidden by the task rules (no delete endpoint exists) |
| TC-TEN-03-A02 | Register the same username again | 400 "Username already exists" | passing |
| TC-TEN-03-A03 | Register a new username with the first account's email | 400 "Email already exists" | passing |
| TC-TEN-03-A04 | Register with username `ab`, password `short7!`, email `x` (three calls) | 422 each, naming the field | passing |
| TC-TEN-03-A05 | Log in as `qa_sa_2` | 200 | blocked: depends on TC-TEN-03-A01 (creating a super admin is forbidden) |
| TC-TEN-03-A06 | Register with a tenant Admin token, then with no token | 403 "Super Admin access required"; 401 "Authorization header missing or invalid" | passing |
| TC-TEN-03-A07 | `GET /super_admin/auth/profile` as `qa_sa_2` | 200; `username` "qa_sa_2" | passing |
| TC-TEN-03-A08 | `PUT /super_admin/auth/profile` `{"full_name":"QA Second"}` | 200; name updated; `updated_at` later | passing |
| TC-TEN-03-A09 | `PUT` with the first account's email | 400 "Email already exists" | blocked: needs a second super admin whose email can be taken, and creating super admins is forbidden |
| TC-TEN-03-A10 | `PUT {"is_active": false}` on itself, then log in again | update 200; login 403 "Account is deactivated" | blocked: deactivating the shared QA super admin would lock the suite out and a throwaway one cannot be created |
| TC-TEN-03-A11 | `POST /super_admin/auth/change-password` with the right current password and `Brand#New9` | 200 `{"message":"Password changed successfully"}` | blocked: a successful password change would alter the shared QA super admin and a throwaway one cannot be created |
| TC-TEN-03-A12 | After A11 log in with the old and the new password | 401; 200 | blocked: a successful password change would alter the shared QA super admin and a throwaway one cannot be created |
| TC-TEN-03-A13 | Change password with a wrong current password | 400 "Current password is incorrect" | passing |
| TC-TEN-03-A14 | New password of 7 characters; of 8 characters | 422; 200 | passing |
| TC-TEN-03-A15 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens on all four endpoints | 403 "Super Admin access required" for each | passing |
| TC-TEN-03-A16 | Audit rows after A01, A08, A11 | actions `CREATE`, `UPDATE`, `PASSWORD_CHANGE` exist | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_super_admin.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f01_f03_super_admin.py`.

## F04 Plans

### Purpose
Define the subscription plans that decide which resources a school gets when it is created or its plan is changed.

### Roles and permissions
Super admin token only. Tenant roles: 403 "Super Admin access required".

### Preconditions
A signed-in super admin (F02).

### Steps, web
Not available. The web file `web/src/api/superadmin.ts` calls `/super-admin/plans` paths that do not exist on the backend, and the page `/superorg` has no super admin token (see F09).

### Steps, mobile
Not available.

### Expected results
Plans are rows in `public.plans`; there is no delete endpoint. Each list, create, view and update action writes a super admin audit row (`LIST_PLANS`, `CREATE_PLAN`, `VIEW_PLAN`, `UPDATE_PLAN`).

### API endpoints
| Method and path | Request fields |
|---|---|
| `GET /super_admin/plans/` | query `include_resources` (default false) |
| `POST /super_admin/plans/` | query `name`, `description` (both required), `is_active` (default true) |
| `GET /super_admin/plans/{plan_id}` | query `include_resources` |
| `PUT /super_admin/plans/{plan_id}` | query `name`, `description`, `is_active` (all optional) |

### Rules and validations
- All inputs are query parameters, not a JSON body.
- List: `{"plans":[{id,name,description,is_active,tenant_count, resources[], total_permissions}],"total_plans":n}`; `resources` and `total_permissions` only with `include_resources`; in the list `total_permissions` counts resources, in the single view it sums actions.
- Create: duplicate name 400 "Plan with name '<name>' already exists"; returns 201 `{"message":"Plan created successfully","plan":{...},"next_steps":[3 items]}`. `name` is limited to 50 characters and `description` to 150 by the columns; longer values fail in the database (500 "Failed to create plan: ...").
- Update: no parameters 400 "No update parameters provided"; unknown id 404 "Plan with ID <id> not found"; renaming is not checked for duplicates.
- Plans are never deleted; deactivating a plan (`is_active` false) stops it being used for new tenants and plan changes (F07, F09).

### Error and edge cases
- Non-UUID `plan_id`: 422.
- Any unexpected error returns 500 with the error text in `detail` (leaks internals).
- Plan ids are UUIDs; the list is ordered by id.

### Unit-testable logic
Update-statement building from the optional parameters (fake session); `tenant_count` and `total_permissions` aggregation differences.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-04-U01 | `update_plan` with no optional parameters (fake session with an existing plan) | HTTPException 400 "No update parameters provided" | passing |
| TC-TEN-04-U02 | `update_plan` with only `is_active=false` | the SQL `SET` clause contains only `is_active` | passing |
| TC-TEN-04-U03 | `create_plan` with an existing name (fake session) | HTTPException 400 "Plan with name 'X' already exists"; no insert | passing |
| TC-TEN-04-U04 | `get_single_plan` with resources `[("a",["r","l"]),("b",["r"])]` | `total_permissions` 3 | passing |
| TC-TEN-04-U05 | `get_all_plans` with the same resources and `include_resources` | `total_permissions` 2 (counts resources) | passing |
| TC-TEN-04-A01 | `POST /super_admin/plans/?name=Lite-<suffix>&description=QA lite plan` | 201; `plan.is_active` true; `next_steps` has 3 items | passing |
| TC-TEN-04-A02 | Same name again | 400 "Plan with name 'Lite-<suffix>' already exists" | passing |
| TC-TEN-04-A03 | Create with `is_active=false` | 201; `plan.is_active` false | passing |
| TC-TEN-04-A04 | Create without `description` | 422 naming `description` | passing |
| TC-TEN-04-A05 | Create with a 50-character name; with a 51-character name | 201; non-2xx (500 "Failed to create plan: ...", plan not created) | passing |
| TC-TEN-04-A06 | `GET /super_admin/plans/` | 200; `total_plans` equals `len(plans)`; each plan has `tenant_count`; `Full` has the QA tenant counted | passing |
| TC-TEN-04-A07 | `GET /super_admin/plans/?include_resources=true` | each plan has `resources` and `total_permissions`; `Full` has 66 resources | passing |
| TC-TEN-04-A08 | `GET /super_admin/plans/{full_id}?include_resources=true` | 200; `total_permissions` 276 (sum of actions) | passing |
| TC-TEN-04-A09 | `GET /super_admin/plans/{random uuid}` | 404 "Plan with ID <id> not found" | passing |
| TC-TEN-04-A10 | `GET /super_admin/plans/abc` | 422 | passing |
| TC-TEN-04-A11 | `PUT /super_admin/plans/{id}?description=Updated` | 200; `plan.description` "Updated"; name unchanged | passing |
| TC-TEN-04-A12 | `PUT` with no parameters | 400 "No update parameters provided" | passing |
| TC-TEN-04-A13 | `PUT` on a random uuid | 404 "Plan with ID <id> not found" | passing |
| TC-TEN-04-A14 | `PUT ...?is_active=false`, then `POST /super_admin/system/tenants/` with that plan | update 200; provisioning 404 "Plan not found or inactive" (F07) | passing |
| TC-TEN-04-A15 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens on the four endpoints | 403 "Super Admin access required" for each | passing |
| TC-TEN-04-A16 | No token on `GET /super_admin/plans/` | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-04-A17 | Audit rows after A01, A06, A08, A11 | actions `CREATE_PLAN`, `LIST_PLANS`, `VIEW_PLAN`, `UPDATE_PLAN` present (with `old_values` and `new_values` for the update) | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_super_admin.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f04_f05_plans.py`.

## F05 Plan resources

### Purpose
Say which `resource:action` pairs a plan includes. The plan's resources decide what a new school's roles receive when it is created or when the plan is re-applied.

### Roles and permissions
Super admin token only.

### Preconditions
An existing plan (F04).

### Steps, web
Not available.

### Steps, mobile
Not available.

### Expected results
Rows of `public.plan_resource_access` (one row per plan and resource, with an `actions` array) change. Existing tenants are not changed until the plan is re-applied (F09).

### API endpoints
| Method and path | Request fields |
|---|---|
| `GET /super_admin/plans/{plan_id}/resources` | none |
| `POST /super_admin/plans/{plan_id}/resources` | query `resource_name`, `action_name` (both required) |
| `DELETE /super_admin/plans/{plan_id}/resources` | query `resource_name`, `action_name` |

### Rules and validations
- GET: `{"plan":{id,name},"resources":[{resource,actions}],"total_resources":n,"total_permissions":m}`, ordered by resource name; unknown plan 404 "Plan with ID <id> not found".
- POST: adds the action to the resource row (creating the row, active, when absent) and returns 201 with `added_permission`, `plan` and `impact` (`affected_tenants` = tenants on the plan, and a text "All tenants on this plan now have this permission", which is not true until the plan is re-applied). A duplicate gives 400 "Resource '<resource>:<action>' already exists for this plan".
- DELETE: unknown resource 404 "Resource '<resource>' not found for this plan"; unknown action 404 "Resource '<resource>:<action>' not found for this plan"; removing the last action deletes the resource row.
- Resource and action names are free text (no catalogue or format check).
- Audit rows `VIEW_PLAN_RESOURCES`, `ADD_PLAN_RESOURCE`, `REMOVE_PLAN_RESOURCE` carry the affected tenant count.

### Error and edge cases
- Missing query parameter: 422.
- Unexpected errors: 500 with the error text in `detail`.
- Plan resources are never validated against what endpoints check.

### Unit-testable logic
Add and remove branching: duplicate detection, last-action row deletion, remaining-actions update (fake session).

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-05-U01 | Add an action already in the `actions` array (fake session) | HTTPException 400 "Resource 'r:a' already exists for this plan" | passing |
| TC-TEN-05-U02 | Add to a resource with no row | an INSERT with `ARRAY[action]` and `is_active` true is executed | passing |
| TC-TEN-05-U03 | Remove one of two actions | an UPDATE sets the remaining list; no DELETE | passing |
| TC-TEN-05-U04 | Remove the only action | the resource row is deleted | passing |
| TC-TEN-05-U05 | Remove an action not in the array | HTTPException 404 "Resource 'r:a' not found for this plan" | passing |
| TC-TEN-05-A01 | `GET /super_admin/plans/{full_id}/resources` | 200; `total_resources` 66; `total_permissions` 276; sorted by resource | passing |
| TC-TEN-05-A02 | `POST ...?resource_name=qa_widgets&action_name=read` on `Lite-<suffix>` | 201; `added_permission` `{resource:"qa_widgets", action:"read"}`; `impact.affected_tenants` 0 | passing |
| TC-TEN-05-A03 | Add `list` to the same resource | 201; GET shows `qa_widgets` with actions `["read","list"]` | passing |
| TC-TEN-05-A04 | Add `read` again | 400 "Resource 'qa_widgets:read' already exists for this plan" | passing |
| TC-TEN-05-A05 | `DELETE ...?resource_name=qa_widgets&action_name=read` | 200 `removed_permission`; resource now has `["list"]` | passing |
| TC-TEN-05-A06 | Delete the last action `list` | 200; GET no longer lists `qa_widgets` | passing |
| TC-TEN-05-A07 | Delete a resource that does not exist | 404 "Resource 'nope' not found for this plan" | passing |
| TC-TEN-05-A08 | Delete an action that does not exist on an existing resource | 404 "Resource 'students:update' not found for this plan" (plan `Lite` has `students:[list]`) | passing |
| TC-TEN-05-A09 | All three endpoints with a random plan uuid | 404 "Plan with ID <id> not found" each | passing |
| TC-TEN-05-A10 | POST without `action_name` | 422 naming `action_name` | passing |
| TC-TEN-05-A11 | Add `qa_widgets:read` to `Full`, then log in as the `qa_school` Admin | the login `permissions` do not contain `qa_widgets` (plan edits do not propagate until re-applied); remove the resource again afterwards | blocked: adding a resource to the Full plan is forbidden by the task rules and no other plan can be created (TEN-PLAN-CREATE) |
| TC-TEN-05-A12 | `impact.affected_tenants` for a plan used by exactly one tenant | 1 | passing |
| TC-TEN-05-A13 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens on the three endpoints | 403 "Super Admin access required" for each | passing |
| TC-TEN-05-A14 | No token | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-05-A15 | Audit rows after A02, A05, A01 | `ADD_PLAN_RESOURCE`, `REMOVE_PLAN_RESOURCE`, `VIEW_PLAN_RESOURCES` with `affected_tenants` in the details | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_super_admin.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f04_f05_plans.py`.

## F06 Menu catalog and role-menu links

### Purpose
Keep the shared catalog of sidebar menus, say which menus a plan includes, and link menus to each school's roles. The links are what users receive as their menu (AUTH F06).

### Roles and permissions
Catalog import and plan-menu links have no HTTP endpoint (service `CatalogService`, script `scripts/seed_demo_catalog.py`). The tenant endpoints need `menu_management:create` and `menu_management:list` (catalog) and `permission_management:create` and `permission_management:list` (role-menu links); Admin holds all four, other roles none.

### Preconditions
A tenant and its roles (F07). Rows created through the endpoints are shared (catalog) or tenant-scoped (links).

### Steps, web
No screen. The Administration dashboard (`/admin`) shows cards for the children of the "Administration" menu from the login menu.

### Steps, mobile
1. Open the Administration tab and the card "Menu Management" (`/admin/menu`, needs `menu_management`).
2. The screen "Menu Management" ("Configure sidebar navigation items") lists the menus ("No menu items configured" with "Add Menu Item" when empty).
3. The add form has Name (placeholder "e.g. Reports", required), Path ("e.g. /reports"), Icon ("e.g. bar-chart"), Order ("e.g. 1") and Active. Edit, delete (confirm "Delete Menu Item") and the active toggle call routes that do not exist (see Known gaps).

### Expected results
`GET /auth/menus/` returns every row of the shared `public.menus` catalog (all schools see the same list). Created menus are visible to every tenant. A role-menu link makes the menu appear in that role's login menu at the next login.

### API endpoints
| Method and path | Request fields |
|---|---|
| `GET /auth/menus/` | none |
| `POST /auth/menus/` | `name`, `level` (both required), `url`, `parent_id` |
| `GET /auth/permissions/` | none (role-menu links of the tenant) |
| `POST /auth/permissions/` | `role_id`, `menu_id`, `can_view` (default true), `can_edit` (default false) |

### Rules and validations
- Menu columns: `name` up to 50 characters, `url` up to 100, `level` up to 2 characters (L0 to L3, not validated by the API), `parent_id` a menu id, `display_order` (not accepted by the API, default 0).
- The tenant `Menu` model is the public catalog table: a menu created by one school's Admin is visible to all schools (Known gaps).
- A unique link per role and menu (`uq_role_menu_permission`, per tenant); a duplicate or an unknown role or menu id violates the database constraints (400, via the global error handler).
- Service `CatalogService.import_menus`: upserts by `url` (or `group:<name>` when there is no url), sorted by level, sets name, level, `display_order`, and the parent (by `parent_url`); returns the number of new menus. `ensure_full_plan` creates or refreshes the plan `Full` from `ALL_ADMIN` (union with existing actions) and links every catalog menu to it.
- `can_edit` is stored but not used at runtime.

### Error and edge cases
- Mobile create sends `path`, `icon`, `order`, `is_active` and no `level`: the backend answers 422 (Known gaps).
- Role-menu link rows pointing at a deleted menu cannot exist (foreign keys).
- A role that still has links cannot be deleted (F14).

### Unit-testable logic
`MenuCreate`, `MenuRead`, `RoleMenuPermissionCreate` schemas; `CatalogService.import_menus` (parents, order, idempotence) and `ensure_full_plan` with a fake session.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-06-U01 | `MenuCreate(name="Reports")` | validation error: `level` required | passing |
| TC-TEN-06-U02 | `MenuCreate(name="Reports", level="L0")` | valid; `url` and `parent_id` `None` | passing |
| TC-TEN-06-U03 | `RoleMenuPermissionCreate(role_id, menu_id)` | `can_view` True, `can_edit` False | passing |
| TC-TEN-06-U04 | `import_menus` with the 70-item demo list on an empty fake catalog, then again | returns 70, then 0 | passing |
| TC-TEN-06-U05 | `import_menus` item with `parent_url` of an L0 menu | child `parent_id` equals the L0 menu id; `display_order` copied | passing |
| TC-TEN-06-U06 | `ensure_full_plan` on an empty plan table | plan `Full` created; one resource row per resource of `ALL_ADMIN` (66) with the union of its actions | passing |
| TC-TEN-06-U07 | `ensure_full_plan` called twice | no duplicate resource rows or plan-menu links | passing |
| TC-TEN-06-A01 | `POST /auth/menus/` as Admin `{"name":"QA Menu","url":"/qa-menu","level":"L0"}` | 201; `{id, name, url, level, parent_id: null}` | blocked: POST /auth/menus/ writes to the shared menu catalog, which the task forbids modifying, and menu rows have no delete endpoint |
| TC-TEN-06-A02 | Create a child with `parent_id` of the menu from A01 and `level` "L1" | 201; `parent_id` equals the parent id | blocked: POST /auth/menus/ writes to the shared menu catalog, which the task forbids modifying, and menu rows have no delete endpoint |
| TC-TEN-06-A03 | Create without `level` (the mobile payload shape) | 422 naming `level` | passing |
| TC-TEN-06-A04 | Create with `parent_id` of a random uuid | 400 (foreign key violation mapped by the error handler); no row created | passing |
| TC-TEN-06-A05 | Create with `level` "L10" (3 characters) | non-2xx (database length error); no row created | passing |
| TC-TEN-06-A06 | Create with a 50-character name; with 51 | 201; non-2xx | passing |
| TC-TEN-06-A07 | `GET /auth/menus/` as Admin | 200; list contains at least the 70 demo menus and "QA Menu"; items have `id, name, url, level, parent_id` | passing |
| TC-TEN-06-A08 | Admin of `qa_school_b` lists menus after A01 | also contains "QA Menu" (shared catalog; documents the gap) | passing |
| TC-TEN-06-A09 | Role matrix on `GET /auth/menus/` and `POST /auth/menus/` | Admin 200 and 201; Staff, Teacher, Student, Parent 403 "Permission not found in database: <role> cannot list menu_management ..." | passing |
| TC-TEN-06-A10 | `POST /auth/permissions/` as Admin linking the Staff role to "QA Menu" | 201; `can_view` true; `can_edit` false | passing |
| TC-TEN-06-A11 | Repeat the same link | 400 (unique constraint violation mapped by the error handler) | passing |
| TC-TEN-06-A12 | Link with a random `role_id` | 400 (foreign key violation) | passing |
| TC-TEN-06-A13 | `GET /auth/permissions/` as Admin | 200; includes the A10 link; only `qa_school` links (none with `qa_school_b` role ids) | passing |
| TC-TEN-06-A14 | After A10 log in as Staff | the login `menu` contains "QA Menu" | passing |
| TC-TEN-06-A15 | Link created with `can_view` false, Staff logs in | "QA Menu" absent | passing |
| TC-TEN-06-A16 | Role matrix on `GET /auth/permissions/` and `POST /auth/permissions/` | Admin 200 and 201; other roles 403 (`permission_management`) | passing |
| TC-TEN-06-A17 | No token on the four endpoints | 401 "Authorization header missing or invalid" each | passing |
| TC-TEN-06-E01 | Mobile: Admin opens Administration > "Menu Management" | the menu list loads; header "Menu Management" | planned |
| TC-TEN-06-E02 | Mobile: tap add, enter Name "QA Mobile Menu", save | error toast "Failed to create menu item" (the request lacks `level`; documents the gap) | planned |
| TC-TEN-06-E03 | Mobile: submit the add form with an empty Name | toast "Menu name is required" | planned |
| TC-TEN-06-E04 | Mobile: Staff opens `/admin/menu` | Access Denied from `ScreenAccessGate` (needs `menu_management`) | planned |
| TC-TEN-06-E05 | Web: Admin opens `/admin` | cards for the Administration children ("Users", "School Settings" on the demo catalog); no menu editing screen exists | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_provisioning.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f06_menus.py`.

## F07 Tenant provisioning

### Purpose
Create a new school in one step: the tenant, its five system roles, their permissions, their menu links, a default academic year and, optionally, the first Admin user.

### Roles and permissions
Super admin token only.

### Preconditions
An active plan that has resources (F04, F05) and, for menus, plan-menu links to the shared catalog (F06). The plan `Full` of the QA environment has both.

### Steps, web
Not available.

### Steps, mobile
Not available.

### Expected results
In one transaction: a `tenants` row (active), the roles Admin, Teacher, Student, Parent, Staff (system roles), their `resource_permissions` limited to the plan, their `role_menu_permissions`, an active academic year, and optionally the first Admin. Any failure rolls everything back. An audit row `CREATE_TENANT` is written. On the `Full` plan and the 71-menu demo catalog the response counts are `roles` 5, `permissions` 455 (Admin 276, Staff 108, Teacher 53, Student 10, Parent 8) and `role_menu_links` 243 (71 each for Admin, Staff, Teacher; 15 each for Student and Parent).

### API endpoints
| Method and path | Request fields |
|---|---|
| `POST /super_admin/system/tenants/` | query `client_name`, `plan_id`; optional query `schema_name` (deprecated, ignored); optional JSON body `{username, email, password}` for the first Admin |

### Rules and validations
- `client_name` is stripped and lowercased, then must match `^[a-z0-9][a-z0-9_-]{1,62}$` (2 to 63 characters; letters, digits, hyphen, underscore; first character a letter or digit), else 400 "client_name must be 2-63 characters of lowercase letters, digits, hyphen or underscore".
- Admin credentials: `bool(username) != bool(password)` gives 400 "admin_username and admin_password go together"; both empty strings create no Admin; the body model requires both `username` and `password` keys. There is no length rule on the password and the email is not validated.
- Plan: unknown or inactive 404 "Plan not found or inactive"; plan without active resources 409 "The tenant's plan has no resources configured"; existing `client_name` 409 "Tenant already exists"; an integrity error 409 "Tenant could not be created".
- Admin role gets every plan pair plus `role_management` (create, read, update, delete, list). Other roles get the catalog pairs of `ROLE_PERMISSIONS` that the plan lists. Student and Parent menu links are limited to `STUDENT_PARENT_MENU_URLS`; `can_edit` is true only for Admin links.
- Default academic year: created if the tenant has none; title `<start>-<start+1>`, start 1 June, end 31 March of the next year, active; `start` is the current year from June to December and the previous year from January to May.
- The first Admin is created with `is_active` true and is never forced to change the password.
- Not created: certificate templates; the shared catalog and plan access must exist beforehand.
- Response: `{"message":"Tenant created successfully","tenant":{tenant_id, client_name, plan_id, admin_user_id, roles, permissions, role_menu_links}}`.

### Error and edge cases
- Unique names are global: `client_name` is unique across the platform.
- Rolled-back creation leaves no tenant, role, user or year rows.
- Unexpected failure: 500 "Tenant provisioning failed".
- The tenant lookup cache (60 s) is not primed by provisioning; the first request resolves it.

### Unit-testable logic
`CLIENT_NAME_PATTERN` and normalisation; admin credential pairing; default academic year dates; permission pair computation per role against a plan; menu link filtering; transaction rollback on error (fake session).

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-07-U01 | Pattern check for `ab`, `a`, `-ab`, `ab c`, `Ab` (after lowercasing), 63 and 64 characters | match; no; no; no; match (as `ab`); match; no | passing |
| TC-TEN-07-U02 | Normalisation of `"  QA_School_C "` | `qa_school_c` | passing |
| TC-TEN-07-U03 | `provision` with `admin_username="x"` and `admin_password=None`; and the reverse | HTTPException 400 "admin_username and admin_password go together" for both | passing |
| TC-TEN-07-U04 | `provision` with `admin_username=""` and `admin_password=""` | no user is added | passing |
| TC-TEN-07-U05 | Default year for today 2026-05-31 | title `2025-2026`; 2025-06-01 to 2026-03-31 | passing |
| TC-TEN-07-U06 | Default year for today 2026-06-01 and 2026-12-31 | title `2026-2027`; 2026-06-01 to 2027-03-31 | passing |
| TC-TEN-07-U07 | Default year for today 2027-01-01 | title `2026-2027` | passing |
| TC-TEN-07-U08 | Permission pairs for the `Full` plan (66 resources, 276 pairs) | counts Admin 276, Teacher 53, Student 10, Parent 8, Staff 108 | passing |
| TC-TEN-07-U09 | Permission pairs for the `Lite` plan | Admin 8 (3 plan pairs plus 5 `role_management`), Teacher 3, Student 2, Parent 2, Staff 3 | passing |
| TC-TEN-07-U10 | Menu links for 70 menus, 15 in `STUDENT_PARENT_MENU_URLS` | 240 links; `can_edit` true only for the 70 Admin links | passing |
| TC-TEN-07-U11 | `provision` where role seeding raises `PlanNotConfiguredError` (fake session) | HTTPException 409 with the error text; `rollback` called; no `commit` | passing |
| TC-TEN-07-A01 | `POST /super_admin/system/tenants/?client_name=qa_school_b&plan_id=<Full>` with body `{"username":"b_admin","email":"b_admin@example.com","password":"Adm1n#Pass"}` | 201; `message` "Tenant created successfully"; `tenant.roles` 5; `permissions` 455; `role_menu_links` 243; `admin_user_id` not null | passing |
| TC-TEN-07-A02 | `GET /auth/academic-years` with header `qa_school_b` | one year, title per the date rule, `is_active` true | passing |
| TC-TEN-07-A03 | Log in as `b_admin` with that year | 200; role "Admin"; `permissions` has 276 actions in total and `role_management` with all five actions | passing |
| TC-TEN-07-A04 | List roles of the new tenant (Admin of `qa_school_b`) | five roles named Admin, Parent, Staff, Student, Teacher with `is_system_role` true and `is_custom_role` false | passing |
| TC-TEN-07-A05 | Create without a body | 201; `admin_user_id` null; no user rows | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-07-A06 | `client_name=QA_School_C%20` (capitals, trailing space) | 201; `tenant.client_name` `qa_school_c` | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-07-A07 | `client_name=a` | 400 "client_name must be 2-63 characters of lowercase letters, digits, hyphen or underscore" | passing |
| TC-TEN-07-A08 | `client_name=-abc` and `client_name=ab c` | 400 each | passing |
| TC-TEN-07-A09 | `client_name` of 63 characters; of 64 characters; of 2 characters | 201; 400; 201 (delete the created tenants afterwards) | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-07-A10 | Create `qa_school_b` again; then `QA_SCHOOL_B` | 409 "Tenant already exists" for both | passing |
| TC-TEN-07-A11 | Unknown plan uuid; deactivated plan | 404 "Plan not found or inactive" for both | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so a deactivated plan cannot be built) |
| TC-TEN-07-A12 | Plan with no resources | 409 "The tenant's plan has no resources configured"; no tenant row for that name | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so a plan without resources cannot be built) |
| TC-TEN-07-A13 | Body with `username` and empty `password` | 400 "admin_username and admin_password go together" | passing |
| TC-TEN-07-A14 | Body with `username` and no `password` key | 422 naming `password` | passing |
| TC-TEN-07-A15 | Body with empty `username` and empty `password` | 201; no Admin created | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-07-A16 | Missing `client_name`; `plan_id=abc` | 422 each | passing |
| TC-TEN-07-A17 | Admin password `abc` (3 characters) | 201 (no length rule; documents behaviour) | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-07-A18 | Query `users.password_hash` of `b_admin` | starts with `$2` (bcrypt); not equal to the plain password | blocked: users.password_hash cannot be read through the API and the database must not be touched |
| TC-TEN-07-A19 | `b_admin` and `qa_school` Admin share a username in the two tenants | both allowed (unique per tenant) | passing |
| TC-TEN-07-A20 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens | 403 "Super Admin access required" for each | passing |
| TC-TEN-07-A21 | No token | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-07-A22 | Audit row after A01 | action `CREATE_TENANT`; details have `roles` 5, `permissions` 455, `role_menu_links` 243, `admin_created` true | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |
| TC-TEN-07-A23 | Users of `qa_school` listed with its Admin token after A01 | no user of `qa_school_b` appears (isolation) | passing |
| TC-TEN-07-A24 | Student and Parent menus in the new tenant (log in as a created student) | menu paths limited to the 15 allowlist URLs | passing |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_provisioning.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f07_provisioning.py`.

## F08 Default role and permission seeding

### Purpose
Create or top up the default roles, role permissions and role menu links of a school from its plan, without undoing what the school's administrator changed.

### Roles and permissions
`POST /auth/seed/all-role-permissions` needs the role name `Admin` (a name check, not a permission). The same logic runs inside provisioning (F07) and plan sync (F09).

### Preconditions
A tenant with a plan that has resources; for menu links, plan-menu links.

### Steps, web
Not available as a screen.

### Steps, mobile
Not available as a screen.

### Expected results
Missing roles, permission rows and menu links are inserted; existing rows are left alone, so a permission the administrator revoked (`is_granted` false) stays revoked and an existing role keeps its description.

### API endpoints
| Method and path | Notes |
|---|---|
| `POST /auth/seed/all-role-permissions` | No body; status 200; response `{"message":"Role permissions seeded successfully","roles":5,"permissions":n,"role_menu_links":m}` |

### Rules and validations
- Only a token whose `role` is exactly `Admin`: otherwise 403 "Admin access required".
- Role names and descriptions come from `DEFAULT_ROLES`; roles are matched per tenant by name (`ON CONFLICT (tenant_id, name) DO NOTHING`).
- Admin permissions: every plan pair plus `role_management:*`. Teacher, Staff, Student, Parent: the catalog pairs that the plan lists (so `_own` and `_related` pairs need the plan to list them).
- Menu links: all plan menus for Admin, Teacher, Staff; only the allowlist URLs for Student and Parent; `can_view` true; `can_edit` true for Admin.
- Counts in the response are the rows attempted, so a repeated call returns the same numbers.
- Tenant without a plan: 409 "Tenant has no plan assigned"; plan without resources: 409 "The tenant's plan has no resources configured"; other errors 500 "Failed to seed permissions".

### Error and edge cases
- A custom role holding every permission still gets 403 (name check).
- A deleted permission row comes back on the next call; a revoked one does not.
- The seed catalog does not include every resource of the application (Known gaps).

### Unit-testable logic
`RoleSeedService._seed_resource_permissions`, `_seed_role_menus`, `_plan_resources`, `seed_defaults` error cases, `sync_to_plan` stale selection (fake session); the Admin name check in the endpoint.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-08-U01 | `seed_defaults` with a tenant row having `plan_id` None | raises `PlanNotConfiguredError("Tenant has no plan assigned")` | passing |
| TC-TEN-08-U02 | `seed_defaults` with a plan that has no active resources | raises `PlanNotConfiguredError("The tenant's plan has no resources configured")` | passing |
| TC-TEN-08-U03 | `_seed_resource_permissions` for Admin with plan `{students:{list}}` | pairs `students:list` plus the five `role_management` actions | passing |
| TC-TEN-08-U04 | Same for Teacher with a plan lacking `exam_marks` | no `exam_marks` pair; Teacher pairs only where the plan lists the action | passing |
| TC-TEN-08-U05 | Same for Student with a plan that lists `student_attendance:[read_own]` | `student_attendance:read_own` included; `student_attendance:list_own` excluded | passing |
| TC-TEN-08-U06 | `_seed_role_menus` for Student with menus `/dashboard`, `/staff`, `/fee/my-receipts` | links for `/dashboard` and `/fee/my-receipts` only | passing |
| TC-TEN-08-U07 | `sync_to_plan` stale selection with rows `role_management:create`, `students:delete`, `students:list` and plan `{students:{list}}` | only `students:delete` is deleted | passing |
| TC-TEN-08-U08 | Endpoint with a token of role `Staff` and with role `Admin` (fake service) | HTTPException 403 "Admin access required"; service called once for Admin | passing |
| TC-TEN-08-A01 | `POST /auth/seed/all-role-permissions` as the `qa_school` Admin | 200; `message` "Role permissions seeded successfully"; `roles` 5; `permissions` 455; `role_menu_links` 243 | passing |
| TC-TEN-08-A02 | Call it twice and count `resource_permissions` and `role_menu_permissions` rows before and after | row counts unchanged; response numbers identical | passing |
| TC-TEN-08-A03 | Set `is_granted` false for Staff `students:list` (F15), then reseed | the row stays false | passing |
| TC-TEN-08-A04 | Delete Staff's `students:list` row (F15 delete), then reseed | the row exists again with `is_granted` true | passing |
| TC-TEN-08-A05 | Add `student_attendance:read_own` to `Full` (F05), reseed, Student logs in | Student's permissions include `student_attendance:read_own`; Staff's do not | blocked: adding student_attendance:read_own to the Full plan is forbidden by the task rules and no other plan can be created (TEN-PLAN-CREATE) |
| TC-TEN-08-A06 | Reseed as Staff, Teacher, Student, Parent | 403 "Admin access required" for each | passing |
| TC-TEN-08-A07 | Custom role `Registrar` holding `role_management:*` calls the endpoint | 403 "Admin access required" | passing |
| TC-TEN-08-A08 | Tenant whose `plan_id` is NULL (fixture) | 409 "Tenant has no plan assigned" | blocked: a tenant with a NULL plan_id cannot be produced through the API |
| TC-TEN-08-A09 | Tenant on a plan with no resources | 409 "The tenant's plan has no resources configured" | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so a plan without resources cannot be built) |
| TC-TEN-08-A10 | No token (header only) | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-08-A11 | Reseed in `qa_school`, then count rows of `qa_school_b` | `qa_school_b` counts unchanged | passing |
| TC-TEN-08-A12 | System role descriptions after reseed | Admin "System administrator with full access", Student "Student with limited read access" etc. unchanged by a second run | passing |
| TC-TEN-08-A13 | Role names created | exactly Admin, Teacher, Student, Parent, Staff (capitalised) | passing |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_provisioning.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f08_seeding.py`.

## F09 Tenant list, activation and plan change

### Purpose
Let the super admin see all schools, switch a school off or on, and move a school to another plan.

### Roles and permissions
Super admin token only.

### Preconditions
Tenants (F07) and plans (F04, F05).

### Steps, web
1. The page `/superorg` (route `/_app/superorg`, page "Super Admin Dashboard", tabs "Tenants", "System Health", "System Logs", "Plans") can be opened by a signed-in tenant user. Its data calls go to `/super-admin/...` and `/organizations/...`, paths that do not exist on the backend, and it carries a tenant token, so no tenant or plan data loads and creating or editing fails. There is no super admin sign-in on web.

### Steps, mobile
Not available.

### Expected results
The list shows tenants with status; deactivating a tenant blocks its login and all its tokens; changing the plan adds what the new plan grants and removes what it no longer allows, in one transaction, leaving users, custom roles and other data in place.

### API endpoints
| Method and path | Request fields |
|---|---|
| `GET /super_admin/system/tenants/` | query `is_active`, `limit` (default 100), `offset` (default 0) |
| `PUT /super_admin/system/tenants/{tenant_id}/activate` | none (toggles) |
| `PUT /super_admin/system/tenants/{tenant_id}/plan` | query `plan_id` |

### Rules and validations
- List: `{"tenants":[{id, client_name, is_active, created_at, updated_at}],"pagination":{total, limit, offset, has_more}}`, newest first; no `plan_id` in the rows. A negative `limit` reaches the database and gives 500 "Failed to retrieve tenants: ..." with the database error text.
- Activate: flips `is_active`; response `{"message":"Tenant activated successfully"|"Tenant deactivated successfully","tenant":{id, client_name, is_active, updated_at}}`; unknown id 404 "Tenant with ID <id> not found"; the tenant cache is cleared in the handling process, other workers pick it up within 60 seconds.
- Deactivated tenant: login and `/auth/academic-years` with its header 404 "Tenant '<name>' not found or inactive"; existing tokens 401 "Invalid connection".
- Change plan: unknown tenant 404 "Tenant not found"; unknown or inactive plan 404 "Plan not found or inactive"; plan without resources 409 (and the tenant keeps its plan); otherwise it sets `plan_id`, seeds what the plan adds (F08) and deletes `resource_permissions` rows whose action the plan does not list (any resource except `role_management`, every role, custom roles included, revoked rows included) and deletes `role_menu_permissions` rows whose menu is not a plan menu. Response `{"message":"Plan assigned and permissions synchronized","tenant_id","old_plan_id","plan_id","plan_name","roles","permissions","role_menu_links","permissions_removed","role_menu_links_removed"}`.
- Re-applying the same plan id propagates plan resource edits (F05) to the tenant.
- Audit rows `LIST_TENANTS`, `TOGGLE_TENANT_STATUS`, `ASSIGN_TENANT_PLAN`.

### Error and edge cases
- Moving `qa_school_b` from `Full` to `Lite` (resources `academic_years:[read,list]`, `students:[list]`, menu `/dashboard`): `permissions` 18, `role_menu_links` 5, `permissions_removed` 437, `role_menu_links_removed` 238 (before the move: 455 permissions and 243 links).
- A plan with no menus removes every role-menu link of the tenant.
- Permissions granted to custom roles outside the plan are removed on a plan change.

### Unit-testable logic
Stale permission and menu-link selection in `sync_to_plan`; `change_plan` error branches and rollback (fake session); response shaping; pagination `has_more` formula `(offset + limit) < total`.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-09-U01 | `has_more` for total 5 with (limit 2, offset 2), (limit 2, offset 4), (limit 100, offset 0) | true, false, false | passing |
| TC-TEN-09-U02 | `change_plan` with an unknown tenant, then an inactive plan (fake session) | HTTPException 404 "Tenant not found"; 404 "Plan not found or inactive" | passing |
| TC-TEN-09-U03 | `change_plan` where `sync_to_plan` raises `PlanNotConfiguredError` | HTTPException 409; `rollback` called; tenant `plan_id` not committed | passing |
| TC-TEN-09-U04 | `sync_to_plan` with `Lite` against the 455 seeded rows | 437 rows selected for deletion; every `role_management` row kept | passing |
| TC-TEN-09-U05 | `sync_to_plan` with a plan that has no menus | the menu-link DELETE removes all links (`NOT (menu_id = ANY([]))`) | passing |
| TC-TEN-09-A01 | `GET /super_admin/system/tenants/` | 200; `pagination.total` at least 2; rows have `id, client_name, is_active, created_at, updated_at` and no `plan_id`; newest first | passing |
| TC-TEN-09-A02 | `?is_active=false` after deactivating `qa_school_b` | only inactive tenants; `pagination.total` 1 | passing |
| TC-TEN-09-A03 | `?limit=1&offset=0` with two tenants | one row; `has_more` true; `?limit=1&offset=1` gives `has_more` false | passing |
| TC-TEN-09-A04 | `?limit=0` | 200; empty `tenants` | passing |
| TC-TEN-09-A05 | `?limit=-1` | 500 "Failed to retrieve tenants: ..." (documents behaviour) | xfail: TEN-NEG-LIMIT (a negative limit on GET /super_admin/system/tenants/ reaches the database and answers 500 instead of a 4xx validation error) |
| TC-TEN-09-A06 | `PUT /super_admin/system/tenants/{qa_school_b}/activate` | 200 "Tenant deactivated successfully"; `is_active` false | passing |
| TC-TEN-09-A07 | After A06 `POST /auth/login` with header `qa_school_b` | 404 "Tenant 'qa_school_b' not found or inactive" | passing |
| TC-TEN-09-A08 | After A06 a `qa_school_b` access token on `GET /admin/users/` | 401 "Invalid connection" | passing |
| TC-TEN-09-A09 | Toggle again | 200 "Tenant activated successfully"; login works again | passing |
| TC-TEN-09-A10 | Activate with a random uuid; with `abc` | 404 "Tenant with ID <id> not found"; 422 | passing |
| TC-TEN-09-A11 | `PUT .../tenants/{qa_school_b}/plan?plan_id=<Lite>` | 200 "Plan assigned and permissions synchronized"; `old_plan_id` Full; `plan_name` the Lite name; `permissions` 18; `role_menu_links` 5; `permissions_removed` 437; `role_menu_links_removed` 235 | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so no second plan (Lite) can be created to move a tenant to) |
| TC-TEN-09-A12 | After A11 log in as the `qa_school_b` Admin | `permissions` contain `academic_years:[list,read]`, `students:[list]` and `role_management` (five actions) only | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so no second plan (Lite) can be created to move a tenant to) |
| TC-TEN-09-A13 | After A11 count users and custom roles of `qa_school_b` | unchanged (only permissions and menu links were pruned) | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so no second plan (Lite) can be created to move a tenant to) |
| TC-TEN-09-A14 | Custom role in `qa_school_b` with `fee_types:read` before A11 | the row is gone after A11 | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so no second plan (Lite) can be created to move a tenant to) |
| TC-TEN-09-A15 | After A11 move back to `Full` | Admin permissions return to 276; the previously revoked or custom rows do not return | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so no second plan (Lite) can be created to move a tenant to) |
| TC-TEN-09-A16 | Add `qa_widgets:read` to `Lite`, then `PUT .../plan?plan_id=<Lite>` for the tenant already on `Lite` | Admin gains `qa_widgets:read` (re-application propagates plan edits) | passing |
| TC-TEN-09-A17 | Change plan with a random plan uuid; with an inactive plan | 404 "Plan not found or inactive" | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so an inactive plan cannot be built) |
| TC-TEN-09-A18 | Change plan for a random tenant uuid | 404 "Tenant not found" | passing |
| TC-TEN-09-A19 | Move the tenant to a plan with no resources | 409 "The tenant's plan has no resources configured"; `plan_id` unchanged | xfail: TEN-PLAN-CREATE (POST /super_admin/plans/ answers 500, so a plan without resources cannot be built) |
| TC-TEN-09-A20 | Missing `plan_id` | 422 naming `plan_id` | passing |
| TC-TEN-09-A21 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens on the three endpoints | 403 "Super Admin access required" for each | passing |
| TC-TEN-09-A22 | No token | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-09-A23 | Audit rows after A01, A06, A11 | `LIST_TENANTS` (with `filter_active` and `count`), `TOGGLE_TENANT_STATUS` (`old_status`, `new_status`, `client_name`), `ASSIGN_TENANT_PLAN` (the full result) | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |
| TC-TEN-09-E01 | Web: Admin of `qa_school` opens `/superorg` | page "Super Admin Dashboard" with tabs "Tenants", "System Health", "System Logs", "Plans"; no tenant rows load (documents the gap) | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_tenants_system.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f09_tenants.py`.

## F10 Super admin tenant data views

### Purpose
Let the super admin look into one school's data (users, students, statistics, roles, report exports) and add role permissions there, without a tenant login.

### Roles and permissions
Super admin token only. The tenant is named by the UUID in the path, validated against `public.tenants` (active or not), and a tenant database session is opened for it, so row-level security limits every query to that school.

### Preconditions
A signed-in super admin (F02) and the tenant id (F09 list or `GET /super_admin/tenant-data/schemas/`).

### Steps, web
Not available.

### Steps, mobile
Not available.

### Expected results
Read endpoints return only the named tenant's rows. The one write endpoint adds `resource_permissions` rows to a role of that tenant; users with the role gain them at once on the API.

### API endpoints
| Method and path | Request fields |
|---|---|
| `GET /super_admin/tenant-data/schemas/` | none |
| `GET /super_admin/tenant-data/{tenant_id}/users/` | query `limit` (100), `offset` (0), `is_active` |
| `GET /super_admin/tenant-data/{tenant_id}/students/` | query `limit`, `offset`, `class_id` (echoed only) |
| `GET /super_admin/tenant-data/{tenant_id}/stats/` | none |
| `GET /super_admin/tenant-data/{tenant_id}/roles/` | none |
| `GET /super_admin/tenant-data/{tenant_id}/roles/{role_id}/permissions/` | none |
| `POST /super_admin/tenant-data/{tenant_id}/roles/{role_id}/permissions/` | query `resource_name`, `actions` (comma separated) |
| `GET /super_admin/tenant-data/{tenant_id}/reports/` | query `limit`, `offset` |

### Rules and validations
- Unknown tenant: 404 "Tenant '<id>' not found"; non-UUID ids: 422.
- `schemas/`: `{"available_tenants":[{id, client_name, is_active, created_at}],"total_tenants":n}` ordered by `client_name`.
- `users/`: `{tenant_id, users:[{id, username, email, is_active, role_name}], total_count, limit, offset, filters:{is_active}}`, ordered by username.
- `students/`: `students:[{id, first_name, last_name, date_of_birth, gender}]`, ordered by first name; `filters.class_id` repeats the query value but does not filter.
- `stats/`: `statistics` with `users{total, active, inactive}`, `students{total, male, female}` (gender "Male", "Female"), `classes{total}`, and `generated_at`.
- `roles/`: `roles:[{id, name, description, permission_count}]`, `total_roles`; `permission_count` counts every `resource_permissions` row of the role, granted or not.
- `.../permissions/` (GET): `role{id,name,description}`, `permissions:[{resource, actions[]}]` for granted rows, `total_permissions`; unknown role 404 "Role <id> not found in tenant <tenant_id>".
- `.../permissions/` (POST, 201): actions are split on commas and trimmed; an action that already has a row (granted or not) is skipped; response `{"message":"Permissions added to role successfully","tenant_id","role":{id,name},"added_permissions":{resource, actions},"skipped":n,"impact":...}`; nothing new: 400 "All permissions for resource '<resource>' already exist for this role". Resource and action names are not validated; no audit row is written.
- `reports/`: rows of `report_audit` for the tenant (`title` is the report type, `description` the status), newest first.
- Any other failure: 500 with a generic message ("Failed to access tenant users" and similar).

### Error and edge cases
- A role id that belongs to another tenant returns 404 (row-level security).
- Inactive tenants can still be read.
- `limit` and `offset` are not range checked (a negative limit gives 500).

### Unit-testable logic
Action list parsing and the skip counting in the POST handler; the `is_active` filter clause building; response shaping (fake session).

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-10-U01 | Action parsing of `" read, list ,update "` | `["read","list","update"]` | passing |
| TC-TEN-10-U02 | POST handler where `read` already exists and `list` does not (fake session) | added `["list"]`; `skipped` 1 | passing |
| TC-TEN-10-U03 | POST handler where every action exists | HTTPException 400 "All permissions for resource 'x' already exist for this role" | passing |
| TC-TEN-10-U04 | Users query builder with `is_active=False` and with `None` | `WHERE u.is_active = :is_active` present; absent | passing |
| TC-TEN-10-A01 | `GET /super_admin/tenant-data/schemas/` | 200; `available_tenants` sorted by `client_name` including `qa_school` and `qa_school_b`; `total_tenants` equals the list length | passing |
| TC-TEN-10-A02 | `GET .../{qa_school}/users/` | 200; one row per QA user with the right `role_name`; `total_count` equals the database count; sorted by username | passing |
| TC-TEN-10-A03 | `GET .../{qa_school_b}/users/` | only `b_admin` (no `qa_school` user appears) | passing |
| TC-TEN-10-A04 | `?is_active=false` after deactivating one QA user | only that user; `filters.is_active` false | passing |
| TC-TEN-10-A05 | `?limit=2&offset=1` | two rows starting at the second username; `total_count` unchanged | passing |
| TC-TEN-10-A06 | `GET .../{random uuid}/users/` | 404 "Tenant '<id>' not found" | passing |
| TC-TEN-10-A07 | `GET .../abc/users/` | 422 | passing |
| TC-TEN-10-A08 | `GET .../{qa_school}/students/` | 200; rows with the five documented fields; `total_count` equals the student count | passing |
| TC-TEN-10-A09 | `students/?class_id=<uuid>` | list identical to the unfiltered one; `filters.class_id` echoes the value | passing |
| TC-TEN-10-A10 | `GET .../{qa_school}/stats/` | 200; `users.total` equals `active + inactive`; `students.total` at least `male + female`; `classes.total` equals the class count; `generated_at` ends with `Z` | passing |
| TC-TEN-10-A11 | `GET .../{qa_school}/roles/` | five system roles at least; `permission_count` per role equals all rows (Admin 276 on a fresh Full tenant) | passing |
| TC-TEN-10-A12 | `GET .../{qa_school}/roles/{staff_role}/permissions/` | 200; `total_permissions` equals the granted rows; resources with their actions | passing |
| TC-TEN-10-A13 | Same with the Staff role id of `qa_school_b` in the `qa_school` path | 404 "Role <id> not found in tenant <tenant_id>" | passing |
| TC-TEN-10-A14 | `POST .../roles/{staff_role}/permissions/?resource_name=qa_widgets&actions=read,list` | 201; `added_permissions.actions` `["read","list"]`; `skipped` 0 | passing |
| TC-TEN-10-A15 | Same call again | 400 "All permissions for resource 'qa_widgets' already exist for this role" | passing |
| TC-TEN-10-A16 | `actions=read,update` when `read` exists | 201; added `["update"]`; `skipped` 1 | passing |
| TC-TEN-10-A17 | After A14 Staff logs in again | `permissions` contains `qa_widgets:[list,read]` | passing |
| TC-TEN-10-A18 | After A14 call an endpoint guarded by the new pair with the old Staff token | granted at once (database check) | passing |
| TC-TEN-10-A19 | POST for a role whose permission was revoked (`is_granted` false, F15) with the same action | 400 or skipped (the revoked row counts as existing; not re-granted) | passing |
| TC-TEN-10-A20 | POST with an unknown role uuid | 404 "Role <id> not found in tenant <tenant_id>" | passing |
| TC-TEN-10-A21 | POST without `actions` | 422 naming `actions` | passing |
| TC-TEN-10-A22 | `GET .../{qa_school}/reports/` | 200; `reports` (possibly empty), `total_count`, `limit` 100, `offset` 0 | passing |
| TC-TEN-10-A23 | Role matrix: Admin, Staff, Teacher, Student, Parent tokens on all eight endpoints | 403 "Super Admin access required" for each | passing |
| TC-TEN-10-A24 | No token on the eight endpoints | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-10-A25 | Read `qa_school_b` data with a super admin token after `qa_school_b` is deactivated | 200 (inactive tenants remain readable) | passing |
| TC-TEN-10-A26 | After A14 query `super_admin_audit` | no row for this action (documents that tenant-data calls are not audited) | blocked: super_admin_audit rows cannot be read through the API and the database must not be touched |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_tenant_data.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f10_tenant_data.py`.

## F11 Platform monitoring

### Purpose
Tell operators whether the platform is up and how many schools and super admin actions it has.

### Roles and permissions
`GET /health` is public. The three super admin endpoints need a super admin token. The permission `monitoring:read` and `monitoring:admin` exists in the Admin catalog but guards only a router that is not mounted (Known gaps).

### Preconditions
A running server; a super admin token for the three protected endpoints.

### Steps, web
The page `/superorg` has a "System Health" tab, but it calls `/super-admin/system/health` (wrong path) and fails (F09).

### Steps, mobile
Not available.

### Expected results
`GET /health` answers `{"status":"healthy"}`. The health endpoints report the number of total and active tenants. Usage statistics are intended to report tenant counts and super admin activity.

### API endpoints
| Method and path | Notes |
|---|---|
| `GET /health` | Public, tenant-free (outside `/api/v1`) |
| `GET /api/v1/super_admin/system/health` | Super admin; `SystemHealthCheck` |
| `GET /api/v1/super_admin/auth/health` | Super admin; the same payload |
| `GET /api/v1/super_admin/system/usage-stats` | Super admin |
| `GET /api/v1/health/status`, `GET /api/v1/health/metrics`, `GET /api/v1/health/metrics/summary`, `GET /api/v1/health/metrics/health`, `POST /api/v1/health/metrics/alerts/configure` | Defined in `health_endpoints.py` but the router is not included in `main_router.py`, so these paths do not exist |

### Rules and validations
- `SystemHealthCheck`: `status` "healthy", `database_status` "connected", `redis_status` null, `total_tenants`, `active_tenants`, `system_version` "1.0.0", `uptime` "Unknown", `timestamp`. A database failure gives 500 "An error occurred while checking system health".
- `usage-stats`: intended `{"system_overview":{total_tenants, active_tenants, inactive_tenants},"super_admin_activity":{total_super_admins, actions_last_24h, actions_last_7d},"generated_at","generated_by"}`. The handler puts a SQL `func.now()` object into the JSON, which cannot be encoded, so the response is 500 today (verified with `jsonable_encoder`). The audit row `VIEW_USAGE_STATS` is written before the failure.
- `/health` bypasses tenant detection (also `/docs`, `/redoc`, `/openapi.json`, `/favicon.ico`).

### Error and edge cases
- Counting inactive tenants changes `active_tenants` but not `total_tenants`.
- Health payload values for Redis and uptime are placeholders.

### Unit-testable logic
`SuperAdminService.get_system_health` with a fake session (counts, shape, error branch); encoding of the usage-stats payload.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-11-U01 | `get_system_health` with counts 3 and 2 (fake session) | `total_tenants` 3; `active_tenants` 2; `status` "healthy"; `uptime` "Unknown" | passing |
| TC-TEN-11-U02 | `get_system_health` when the session raises | HTTPException 500 "An error occurred while checking system health" | passing |
| TC-TEN-11-U03 | `jsonable_encoder` of a dict containing `sqlalchemy.func.now()` | raises `ValueError` (documents the usage-stats defect) | passing (asserts current behaviour [defect KG-3]; target behaviour is xfail strict) |
| TC-TEN-11-A01 | `GET /health` with no header and no token | 200 `{"status":"healthy"}` | passing |
| TC-TEN-11-A02 | `GET /api/v1/super_admin/system/health` as the QA super admin | 200; `total_tenants` at least 2; `active_tenants` at most `total_tenants`; `database_status` "connected"; `timestamp` present | passing |
| TC-TEN-11-A03 | Deactivate `qa_school_b`, repeat A02 | `active_tenants` drops by 1; `total_tenants` unchanged | passing |
| TC-TEN-11-A04 | `GET /api/v1/super_admin/auth/health` | 200; same shape as A02 | passing |
| TC-TEN-11-A05 | `GET /api/v1/super_admin/system/usage-stats` | 500 today (response serialisation); intended 200 with `system_overview` counts equal to the tenant counts; an audit row `VIEW_USAGE_STATS` exists | xfail: TEN-USAGE-STATS (GET /super_admin/system/usage-stats answers 500 because the payload holds a SQL func.now() object that cannot be JSON-encoded) |
| TC-TEN-11-A06 | `GET /api/v1/health/status`, `/health/metrics`, `/health/metrics/summary`, `/health/metrics/health` with header `qa_school` | 404 each (router not mounted) | passing |
| TC-TEN-11-A07 | `POST /api/v1/health/metrics/alerts/configure` with a JSON body | 404 (router not mounted) | passing |
| TC-TEN-11-A08 | Role matrix on the three super admin endpoints: Admin, Staff, Teacher, Student, Parent | 403 "Super Admin access required" for each | passing |
| TC-TEN-11-A09 | No token on the three super admin endpoints | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-11-A10 | Tenant Admin (holds `monitoring:read`) calls the unmounted paths | 404, not 200 (permission has no effect) | passing |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_tenants_system.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f11_monitoring.py`.

## F12 School settings

### Purpose
Keep the school's identity details (name, contacts, address, board, academic year text) and its logo and principal signature images.

### Roles and permissions
`school_settings:read` to view and `school_settings:update` to save and upload. Admin holds both (when the plan lists the resource); Staff, Teacher, Student, Parent hold none by default, so every endpoint answers 403 for them. The sidebar entry is hidden for Teacher and Student by the client and is not in the Student and Parent menus (allowlist); Staff sees the entry but its calls are denied.

### Preconditions
A tenant whose plan includes `school_settings` (it is in the Admin catalog). The record is created on the first save or upload.

### Steps, web
1. Open the sidebar entry Administration > School Settings (demo catalog; elsewhere Masters > "School Registration" injected by the client), route `/settings/school`, page "School Settings" ("Manage school registration and identity information"). The badge "Not configured yet" shows when no record exists.
2. Basic Information: "School Name", "Contact No." and "Alt. Contact No." (placeholders 9900099000 and 9999900000, 10 characters), "School Email", "School Board" (list "-- Select Board --", CBSE, ICSE, State Board, IGCSE, IB, Custom; "Custom Board Name" appears for Custom), "Academic Year" (placeholder 2026-27), "Installation Date".
3. Address: "Street Address", "City", "District", "State", "PIN Code" (6 characters), "Country" (default India).
4. Press "Save Settings" ("Saving..." while waiting). Toasts "School settings saved successfully" or "Failed to save school settings".
5. Images: boxes "School Logo" and "Principal Signature", each with an "Upload" button and the hint "JPG, PNG, WebP" and "Max 2 MB". Toasts "School logo uploaded successfully", "Principal signature uploaded successfully", "Failed to upload school logo", "Failed to upload signature".

### Steps, mobile
1. Open the Administration tab and the card "School Settings" (`/admin/school-settings`, needs `school_settings:read`).
2. Branding: "School Logo" and "Principal Signature" pickers (JPEG or PNG only); toasts "Uploaded: School logo has been updated." and "Uploaded: Principal signature has been updated.", failures "Upload Failed".
3. "Basic Information": "School Name *", "Contact Number", "Alternate Contact Number", "School Email", "School Board" (placeholder "e.g. CBSE, State Board"), "Academic Year" ("e.g. 2025-2026"), "Installation Date" ("YYYY-MM-DD"). "Address": "Address", "City", "District", "State", "Pin Code", "Country".
4. Tap "Save Settings" ("Saving..."). An empty name shows "School name is required"; success "Saved: School settings have been updated."

### Expected results
One record per school with the saved values; uploaded images are stored under `media/<tenant_id>/school/images/` and `.../signatures/` and served at `/media/...` without authentication.

### API endpoints
| Method and path | Request fields |
|---|---|
| `GET /school-settings` | none |
| `PUT /school-settings` | `school_name, contact_no, alt_contact_no, school_email, address, city, state, district, pin_code, country, academic_year, installation_date (YYYY-MM-DD), school_board` (all optional) |
| `POST /school-settings/upload-image` | multipart file field `photo` |
| `POST /school-settings/upload-signature` | multipart file field `photo` |

### Rules and validations
- `GET` before any save: 404 "School settings not configured yet."
- `PUT` is an upsert that replaces all 13 fields: omitted fields become null; `image_url` and `principal_signature_url` are not touched. The response has the 13 fields, both image URLs and `id`.
- The backend does not validate formats (any text for phone, email or pin). Web enforces 10 digits for contact numbers ("Must be exactly 10 digits"), 6 digits for PIN ("Must be exactly 6 digits") and an email pattern ("Invalid email address"); mobile enforces only the school name.
- Upload: extension (case-insensitive) must be `.jpg`, `.jpeg`, `.png` or `.webp`, else 400 "Only jpg, png, webp files are allowed"; size over 2 MB (2,097,152 bytes) gives 400 "File size must not exceed 2 MB"; the content type is not inspected. Files are saved as `school_image_url<ext>` or `school_principal_signature_url<ext>`, so a new upload with the same extension overwrites the old file and a different extension leaves the old file on disk. Returned URL: `/media/<tenant_id>/school/images/school_image_url.png` (or `.../signatures/school_principal_signature_url.png`).
- An upload on a tenant with no record creates the record with only that image field.
- Row-level security keeps one record per school; two schools cannot see each other's record.

### Error and edge cases
- Upload without the `photo` field: 422.
- Media files are public: anyone with the URL can fetch them.
- A save that fails on the unique or database constraints: 409 "A conflict occurred while saving school settings."

### Unit-testable logic
Upload validation (extension, size boundary, file naming, URL building) with an in-memory file; `upsert_settings` full replace semantics (fake session); web zod schema (10 digits, 6 digits, email pattern); `SchoolSettingsUpdate` optional fields.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-12-U01 | Upload helper with `.PNG`, `.jpg`, `.jpeg`, `.webp` names | accepted (extension lowercased) | passing |
| TC-TEN-12-U02 | Upload helper with `.gif`, `.pdf`, no extension | HTTPException 400 "Only jpg, png, webp files are allowed" | passing |
| TC-TEN-12-U03 | Upload helper with 2,097,152 bytes and 2,097,153 bytes | accepted; HTTPException 400 "File size must not exceed 2 MB" | passing |
| TC-TEN-12-U04 | Saved name and URL for the logo with `.png` and tenant id `T` | file `media/T/school/images/school_image_url.png`; URL `/media/T/school/images/school_image_url.png` | passing |
| TC-TEN-12-U05 | Saved name and URL for the signature with `.jpg` | `media/T/school/signatures/school_principal_signature_url.jpg` | passing |
| TC-TEN-12-U06 | `upsert_settings` on an existing record with a payload that omits `city` | `city` set to `None`; image URLs unchanged | passing |
| TC-TEN-12-U07 | Web zod schema: contact `12345`, `1234567890`, `""`; pin `12345`, `123456`; email `a@b`, `a@b.co` | invalid, valid, valid; invalid, valid; invalid, valid | blocked: the zod schema is not exported from web/src/pages/settings/SchoolSettings.tsx |
| TC-TEN-12-U08 | `SchoolSettingsUpdate()` | valid; all fields `None` | passing |
| TC-TEN-12-A01 | `GET /school-settings` as Admin on a tenant with no record (use `qa_school_b`) | 404 "School settings not configured yet." | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-12-A02 | `PUT /school-settings` as Admin with all 13 fields | 200; body echoes them with `id`; `image_url` null | passing |
| TC-TEN-12-A03 | `GET /school-settings` | 200; same values | passing |
| TC-TEN-12-A04 | `PUT` with only `school_name` | 200; every other of the 13 fields null; `image_url` unchanged | passing |
| TC-TEN-12-A05 | `PUT {}` | 200; all 13 fields null | passing |
| TC-TEN-12-A06 | `PUT` with `contact_no` "abc", `pin_code` "12", `school_email` "x" | 200 and stored (no server-side format validation) | passing |
| TC-TEN-12-A07 | `PUT` with `installation_date` "2026-13-45" | 422 | passing |
| TC-TEN-12-A08 | `POST /school-settings/upload-image` with a 100 KB PNG | 200; `image_url` `/media/<tenant_id>/school/images/school_image_url.png`; file exists on disk | passing |
| TC-TEN-12-A09 | `GET` the media URL from A08 with no token | 200 image bytes (public) | xfail: TEN-MEDIA-CSCHEMA (GET /media/<tenant>/... without a cschema header returns 400 instead of serving the file publicly) |
| TC-TEN-12-A10 | `upload-signature` with a JPG | 200; `principal_signature_url` ends `school_principal_signature_url.jpg` | passing |
| TC-TEN-12-A11 | Upload `logo.gif` | 400 "Only jpg, png, webp files are allowed" | passing |
| TC-TEN-12-A12 | Upload a 2,097,153-byte PNG; a 2,097,152-byte PNG | 400 "File size must not exceed 2 MB"; 200 | passing |
| TC-TEN-12-A13 | Upload a file named `x.PNG` | 200; stored URL ends with lowercase `.png` | passing |
| TC-TEN-12-A14 | Upload PNG then JPG | URL changes to `.jpg`; the `.png` file remains on disk | passing |
| TC-TEN-12-A15 | Upload with the field named `file` instead of `photo` | 422 | passing |
| TC-TEN-12-A16 | Upload on a tenant with no record | 200; record created with only the image field set | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-12-A17 | Role matrix on `GET /school-settings` (`school_settings:read`) | Admin 200; Staff, Teacher, Student, Parent 403 "Permission not found in database: <role> cannot read school_settings. Contact administrator to configure permissions." | passing |
| TC-TEN-12-A18 | Role matrix on `PUT` and both uploads (`school_settings:update`) | Admin 200; the other four roles 403 | passing |
| TC-TEN-12-A19 | No token (header only) | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-12-A20 | `qa_school` saved, `qa_school_b` reads | `qa_school_b` gets 404 (or its own values); never `qa_school`'s | passing |
| TC-TEN-12-A21 | Media paths of the two tenants | contain different tenant ids | passing |
| TC-TEN-12-E01 | Web: Admin opens Administration > School Settings on a tenant with no record | page "School Settings" with badge "Not configured yet"; Country shows India | planned |
| TC-TEN-12-E02 | Web: fill School Name "QA Public School", Contact No. 9900099000, PIN Code 503001, choose board CBSE, press "Save Settings" | toast "School settings saved successfully"; badge gone after reload; values persist | planned |
| TC-TEN-12-E03 | Web: Contact No. `12345`; PIN Code `12` | field messages "Must be exactly 10 digits" and "Must be exactly 6 digits"; no request | planned |
| TC-TEN-12-E04 | Web: School Email `abc` | message "Invalid email address" | planned |
| TC-TEN-12-E05 | Web: choose School Board "Custom" | field "Custom Board Name" appears; saved value is the typed name | planned |
| TC-TEN-12-E06 | Web: upload a PNG as "School Logo" | toast "School logo uploaded successfully"; image preview shown | planned |
| TC-TEN-12-E07 | Web: upload a 3 MB PNG | toast "Failed to upload school logo" | planned |
| TC-TEN-12-E08 | Web: upload "Principal Signature" JPG | toast "Principal signature uploaded successfully" | planned |
| TC-TEN-12-E09 | Web: Teacher and Student sidebars | no School Settings entry | planned |
| TC-TEN-12-E10 | Web: Staff opens `/settings/school` by URL | the page opens (no route guard); the settings call is denied with 403 so the badge "Not configured yet" shows; pressing "Save Settings" gives the toast "Failed to save school settings" | planned |
| TC-TEN-12-E11 | Mobile: Admin opens Administration > "School Settings" | screen "School Settings" with Branding, Basic Information, Address sections | planned |
| TC-TEN-12-E12 | Mobile: clear "School Name *" and tap "Save Settings" | error toast "School name is required" | planned |
| TC-TEN-12-E13 | Mobile: fill the name and tap "Save Settings" | toast "Saved" with "School settings have been updated." | planned |
| TC-TEN-12-E14 | Mobile: Staff opens `/admin/school-settings` | Access Denied from `ScreenAccessGate` | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_tenancy_settings.py` (U01-U06, U08).

API tests implemented in: `backend/tests/api/tenants_admin/test_f12_school_settings.py`.

## F13 User management

### Purpose
Let the tenant administrator find every login account of the school, see which student, staff member or parent it belongs to, fix usernames and emails, switch accounts on or off, change a user's role, and set a new password for someone who is locked out.

### Roles and permissions
`user_management:list` (list and filter options), `user_management:read` (single user), `user_management:update` (edit, role change, password reset). The seed gives Admin read, update and list; Staff, Teacher, Student and Parent have none, so they get 403. There is no create or delete: accounts are created by staff enrolment, student admission and parent creation (other modules), and by provisioning for the first Admin.

### Preconditions
Users exist (QA tenant: one per role plus fixtures). For destructive tests the test creates its own temporary users and removes them.

### Steps, web
1. Open Administration > Users (route `/admin/users`). Without `user_management:list` the page shows "Access Denied" and "You don't have permission to view users."
2. The page "User Management" ("View and manage all user accounts across the organization") shows a badge with the count ("N users"), a search box (placeholder "Search username or email...", debounced 400 ms), the filters "All Roles" and "All Status" (Active, Inactive), and a table with Username, Email, Role, Entity, Status and Actions, 20 rows per page with "Page X of Y" and previous and next buttons.
3. Actions per row: View (button title "View", dialog "User Details": Username, Email, Role, Status, Entity Type, Entity Name, Created), Edit (title "Edit", dialog "Edit User": Username, Email with placeholder "Optional", Active switch, buttons "Cancel" and "Save Changes"), Reset Password (title "Reset Password", dialog "Reset Password": "Set a new password for <username>.", "New Password" with placeholder "Min 8 characters", "Confirm Password", button "Reset Password"). Edit and Reset appear only with `user_management:update`.
4. Edit sends only changed fields; saving with no change just closes the dialog. Toasts: "User updated successfully", "Failed to update user", "Password reset successfully", "Failed to reset password". The reset button stays disabled until the password has 8 or more characters and both fields match ("Passwords do not match").
5. Changing a user's role has no screen (API only).

### Steps, mobile
1. Open the Administration tab, card "User Management" (`/admin/users`, needs `user_management`). Without it an Access Denied panel appears.
2. The screen "User Management" shows "USER CATEGORIES" cards (Staff Members, Students, Parents, Roles & Permissions) and "SYSTEM LOGIN ACCOUNTS": a search box (placeholder "Search by username, name..."), role chips ("All Roles" and one per role from the filter options) and one card per account (name or username, "@username", role, entity type, status dot, edit button); page arrows and "page / total pages" at 20 per page. There is no status filter.
3. Tap the edit button: a sheet with the tabs "Details" (Username *, Email, Active switch, "Cancel", "Save Changes") and "Reset Password" ("New Password *" placeholder "Min 8 characters", button "Reset Password"; there is no confirmation field). Toasts: "User updated successfully", "Failed to update user", "Password reset successfully", "Failed to reset password"; local messages "Username is required" and "New password must be at least 8 characters".

### Expected results
The list reflects the database; edits change `users.username`, `users.email`, `users.is_active`, `users.role_id` or `users.password_hash`. A deactivated user cannot log in or refresh. A role change shows in the user's tokens at the next refresh or login.

### API endpoints
| Method and path | Request fields | Permission |
|---|---|---|
| `GET /admin/users/` | query `page` (default 1, minimum 1), `limit` (default 50, 1 to 100), `role`, `search`, `is_active` | `user_management:list` |
| `GET /admin/users/{user_id}` | none | `user_management:read` |
| `PATCH /admin/users/{user_id}` | `username` (3 to 50), `email`, `is_active` | `user_management:update` |
| `PUT /admin/users/{user_id}/role` | `role_id` | `user_management:update` |
| `POST /admin/users/{user_id}/reset-password` | `new_password` (minimum 8) | `user_management:update` |
| `GET /admin/users/filters/options` | none | `user_management:list` |

### Rules and validations
- List response: `{users:[...], total, page, limit, total_pages}`; each user: `id, username, email, is_active, role_id, role_name, entity_type, entity_id, entity_name, entity_details, created_at, updated_at`. `created_at` and `updated_at` are always null. Order: username ascending. `total_pages` = ceil(total / limit), 0 when there are no users. A page beyond the last returns an empty list with the correct total.
- Filters: `role` is an exact role name (an unknown name gives an empty list); `search` is a case-insensitive match on username or email only (not on names; `%` is not escaped); `is_active` true or false.
- Entity: the first of student, staff, parent that is linked decides `entity_type`. The student details are date of birth, gender, `aadhar_number`, nationality (the single-user view adds caste, community, mother tongue); staff details are `designation` (the department), joining date, phone, qualification, experience years (single view adds address and gender); parent details are phone, occupation, relation, `aadhar_number` (single view adds gender). `entity_name` is first name plus last name, or the parent name.
- `PATCH`: username already used by another user in the tenant 400 "Username '<name>' already exists"; email likewise 400 "Email '<email>' already exists" (uniqueness is per tenant, so another school may use the same value); a body with no change returns 200 with the current user; `email` must be a valid address (422); it does not reject an empty body; an Admin may deactivate its own account.
- Role change: unknown user 404 "User with ID <id> not found"; unknown role 404 "Role with ID <id> not found"; response `{"message":"User role updated successfully","user_id","username","old_role":{id,name},"new_role":{id,name}}`. Moving a user to or from a system role changes first-login handling, entity resolution and frontend caps because they match on the role name.
- Reset: response `{"message":"Password reset successfully for user <username>","user_id","username"}`. It does not set `is_first_login`, writes no audit row, does not revoke existing tokens and does not stop an Admin resetting another Admin.
- Filter options: `{"available_roles":[names sorted],"active_status_options":[true,false],"default_limit":50,"max_limit":100}`.
- Missing grant: 403 "Permission not found in database: <role> cannot <action> user_management. Contact administrator to configure permissions."

### Error and edge cases
- Unknown user on any single-user call: 404 "User with ID <id> not found"; non-UUID id: 422.
- `page` 0, `limit` 0 or 101: 422.
- Deactivating the last active Admin is allowed (no safeguard).
- Username changes alter the login identifier (staff and teachers use email or phone as username, students the admission number).
- Server errors return 500 with the error text in `detail`.

### Unit-testable logic
`total_pages` computation; entity precedence and detail mapping (fake ORM objects); `UserUpdateRequest`, `UserPasswordResetRequest`, `UserRoleUpdateRequest` validation; duplicate checks in `update_user`; web `UsersPage` payload building (only changed fields) and reset button enabling; mobile validation messages.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-13-U01 | `total_pages` for (total, limit) = (0,50), (1,50), (50,50), (51,50), (101,100) | 0, 1, 1, 2, 2 | passing |
| TC-TEN-13-U02 | Entity mapping for a user with both a student and a staff record | `entity_type` "student" | passing |
| TC-TEN-13-U03 | Entity mapping for a staff user | `entity_details.designation` equals `staff.department`; `entity_name` joins first and last name, trimmed when last name is empty | passing |
| TC-TEN-13-U04 | User with no role object | `role_name` "No Role" | passing |
| TC-TEN-13-U05 | `UserUpdateRequest` username of 2, 3, 50, 51 characters | rejected, accepted, accepted, rejected | passing |
| TC-TEN-13-U06 | `UserUpdateRequest(email="bad")` | validation error | passing |
| TC-TEN-13-U07 | `UserPasswordResetRequest` with 7 and 8 characters | rejected; accepted | passing |
| TC-TEN-13-U08 | `UserRoleUpdateRequest(role_id="abc")` | validation error | passing |
| TC-TEN-13-U09 | `update_user` with the user's own current username and email | no change recorded; no commit | passing |
| TC-TEN-13-U10 | `update_user` with a username used by another user (fake session) | HTTPException 400 "Username 'x' already exists" | passing |
| TC-TEN-13-U11 | Web edit dialog with only the Email changed | payload `{email}` only; no change closes without a request | blocked: edit dialog logic is inline in web/src/pages/admin/UsersPage.tsx and not exported |
| TC-TEN-13-U12 | Web reset dialog with password `1234567`, `12345678` and mismatching confirm | button disabled; enabled; disabled with "Passwords do not match" | blocked: reset dialog logic is inline in web/src/pages/admin/UsersPage.tsx and not exported |
| TC-TEN-13-A01 | `GET /admin/users/` as Admin | 200; `page` 1, `limit` 50; `total` equals the database count; users sorted by username; `created_at` null | passing |
| TC-TEN-13-A02 | `?role=Student` | only users with `role_name` "Student" | passing |
| TC-TEN-13-A03 | `?role=NoSuchRole` | 200; `users` `[]`; `total` 0; `total_pages` 0 | passing |
| TC-TEN-13-A04 | `?is_active=false` after deactivating one user | only inactive users | passing |
| TC-TEN-13-A05 | `?search=qa_` (part of a username) and the same in capitals | same results both times (case-insensitive) | passing |
| TC-TEN-13-A06 | `?search=` the first name of a student user | no user returned (names are not searched) | passing |
| TC-TEN-13-A07 | `?search=%` | all users (wildcard not escaped; documents behaviour) | passing |
| TC-TEN-13-A08 | `?limit=2&page=2` with five users | two users (3rd and 4th by username); `total_pages` 3 | passing |
| TC-TEN-13-A09 | `?page=99` | 200; `users` `[]`; `total` unchanged | passing |
| TC-TEN-13-A10 | `?page=0`, `?limit=0`, `?limit=101` | 422 each; `?limit=100` gives 200 | passing |
| TC-TEN-13-A11 | List entries for the Student, Staff and Parent QA users | `entity_type` "student", "staff", "parent"; `entity_id` and `entity_name` set; documented `entity_details` keys | passing |
| TC-TEN-13-A12 | `GET /admin/users/{student_user_id}` | 200; details include caste, community, mother tongue | passing |
| TC-TEN-13-A13 | `GET /admin/users/{random uuid}` | 404 "User with ID <id> not found" | passing |
| TC-TEN-13-A14 | `GET /admin/users/abc` | 422 | passing |
| TC-TEN-13-A15 | `PATCH` a temp user `{"username":"qa_tmp_renamed","email":"qa_tmp@example.com"}` | 200; new values returned | passing |
| TC-TEN-13-A16 | `PATCH` with a username taken by another user | 400 "Username 'x' already exists" | passing |
| TC-TEN-13-A17 | `PATCH` with an email taken by another user | 400 "Email 'x' already exists" | passing |
| TC-TEN-13-A18 | `PATCH` with `{}` and with the user's current values | 200 each; user unchanged | passing |
| TC-TEN-13-A19 | `PATCH` with username `ab`, 51 characters, email `bad` | 422 each | passing |
| TC-TEN-13-A20 | `PATCH {"is_active": false}`, then the user logs in | login 401 "Invalid Credentials"; refresh with its old refresh token 401 "Account is inactive. Please contact the administrator." | passing |
| TC-TEN-13-A21 | `PATCH {"is_active": true}` afterwards | login works again | passing |
| TC-TEN-13-A22 | Same username in `qa_school_b`: `PATCH` a `qa_school` user to a username that only exists in `qa_school_b` | 200 (uniqueness is per tenant) | passing |
| TC-TEN-13-A23 | Admin deactivates its own account | 200 (no safeguard); restore it through the database | passing |
| TC-TEN-13-A24 | `PUT /admin/users/{tmp}/role` with the Teacher role id | 200 with `old_role` and `new_role` objects; `GET` shows `role_name` "Teacher" | passing |
| TC-TEN-13-A25 | After A24 decode the access token issued before the change, then refresh and decode the new access token | the old token still carries the old role name; the refreshed token has `role` "Teacher" | passing |
| TC-TEN-13-A26 | Role change with a random role uuid; with a random user uuid | 404 "Role with ID <id> not found"; 404 "User with ID <id> not found" | passing |
| TC-TEN-13-A27 | Role change with `role_id` "abc" | 422 | passing |
| TC-TEN-13-A28 | `POST /admin/users/{tmp}/reset-password` `{"new_password":"Reset#2026"}` | 200 with `message` "Password reset successfully for user <username>"; `user_id`; `username` | passing |
| TC-TEN-13-A29 | After A28 the user logs in with the new password and with the old one | 200 with no first-login challenge; 401 | passing |
| TC-TEN-13-A30 | Reset with a 7-character password; with 8 characters | 422; 200 | passing |
| TC-TEN-13-A31 | Reset for a random user uuid | 404 "User with ID <id> not found" | passing |
| TC-TEN-13-A32 | After A28 use the user's pre-reset access token | still accepted (tokens not revoked; documents behaviour) | passing |
| TC-TEN-13-A33 | `GET /admin/users/filters/options` | 200; `available_roles` sorted and including the five system roles and custom roles; `default_limit` 50; `max_limit` 100; `active_status_options` `[true,false]` | passing |
| TC-TEN-13-A34 | Role matrix on `GET /admin/users/` and `filters/options` (`list`) | Admin 200; Staff, Teacher, Student, Parent 403 with the "Permission not found in database" text | passing |
| TC-TEN-13-A35 | Role matrix on `GET /admin/users/{id}` (`read`) | Admin 200; the other four 403 | passing |
| TC-TEN-13-A36 | Role matrix on `PATCH`, role change and reset (`update`) | Admin 200; the other four 403 | passing |
| TC-TEN-13-A37 | `POST /admin/users/` and `DELETE /admin/users/{id}` | 405 (no create or delete endpoint) | passing |
| TC-TEN-13-A38 | No token (header only) on every endpoint | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-13-A39 | Tenant isolation: `GET /admin/users/{id}` with a `qa_school_b` user id and a `qa_school` token | 404 "User with ID <id> not found"; the list never contains `qa_school_b` users | passing |
| TC-TEN-13-A40 | Custom role holding `user_management:list` and `read` only | list and detail 200; `PATCH` 403 | passing |
| TC-TEN-13-E01 | Web: Admin opens Administration > Users | table with the QA users; badge "N users" equals the total | planned |
| TC-TEN-13-E02 | Web: type `qa_` in the search box | after about 400 ms only matching rows remain; page reset to 1 | planned |
| TC-TEN-13-E03 | Web: choose "Student" in the role filter and "Inactive" in the status filter | rows narrow accordingly; empty result shows "No users found" | planned |
| TC-TEN-13-E04 | Web: click View on a student user | dialog "User Details" with Entity Type "Student" and the student's name | planned |
| TC-TEN-13-E05 | Web: Edit a temp user, change the Email, "Save Changes" | toast "User updated successfully"; row shows the new email | planned |
| TC-TEN-13-E06 | Web: Edit with a username already in use | toast "Failed to update user" | planned |
| TC-TEN-13-E07 | Web: Edit, switch Active off, save | row status becomes Inactive; that user can no longer log in | planned |
| TC-TEN-13-E08 | Web: Reset Password with `Reset#2026` twice | toast "Password reset successfully"; the user can log in with it | planned |
| TC-TEN-13-E09 | Web: Reset Password with mismatching confirmation | text "Passwords do not match"; the button stays disabled | planned |
| TC-TEN-13-E10 | Web: more than 20 users, next page button | "Page 2 of N" and the next rows | planned |
| TC-TEN-13-E11 | Web: Staff opens `/admin/users` | "Access Denied" with the permission message | planned |
| TC-TEN-13-E12 | Web: custom role with only `user_management:list` | list visible; no Edit or Reset Password buttons | planned |
| TC-TEN-13-E13 | Mobile: Admin opens Administration > "User Management" | category cards and the "SYSTEM LOGIN ACCOUNTS" list | planned |
| TC-TEN-13-E14 | Mobile: tap the "Teacher" role chip | only Teacher accounts listed | planned |
| TC-TEN-13-E15 | Mobile: edit a temp user, change Email, "Save Changes" | toast "User updated successfully" | planned |
| TC-TEN-13-E16 | Mobile: "Reset Password" tab with 7 characters | toast "New password must be at least 8 characters" | planned |
| TC-TEN-13-E17 | Mobile: "Reset Password" tab with a valid password | toast "Password reset successfully" | planned |
| TC-TEN-13-E18 | Mobile: Staff opens `/admin/users` | Access Denied from `ScreenAccessGate` | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_admin_roles_users.py` (U01-U10).

API tests implemented in: `backend/tests/api/tenants_admin/test_f13_users.py`.

## F14 Role management

### Purpose
Let the tenant administrator list roles, create custom roles (for example "Librarian"), rename or re-describe them and delete unused ones, while the five system roles stay protected.

### Roles and permissions
`role_management:create`, `read`, `update`, `delete`, `list`. Admin gets all five from the seed (also when its plan does not list the resource). Other roles have none by default. Exception: `GET /admin/role-mgmt/roles/` has its permission check disabled, so any authenticated user can list roles. The legacy `/auth/roles/roles/` endpoints need `role_management:create` and `list`.

### Preconditions
The tenant's system roles exist (F07, F08). Custom roles are created here.

### Steps, web
1. Open Masters > Roles and Permissions (route `/masters/rolespermissions`, page "Roles & Permissions": "Manage user roles and their access permissions across the system"; the demo catalog entry is named "Roles and Permissions"). The page decides rights with a hard-coded role (`admin`), so every user who opens it sees the buttons "Add Role", "Bulk Create" and "Add Permission"; the backend still enforces permissions.
2. Tab "Roles" (card "User Roles Management": "Create, edit, and delete user roles in the system"): table Role Name, Description ("No description" when empty), Status, Created, Actions (edit and delete icons; delete is disabled for the role named "Admin").
3. "Add Role" opens the dialog "Create Role" ("Add a new role to the system"): "Role Name" (placeholder "e.g., Librarian"), "Description" (placeholder "Role description (optional)"), "Active". Submit: toast "Role created successfully" or "Failed to create role: <detail>".
4. The edit icon opens "Edit Role" ("Update the role information") and the delete icon opens the confirmation "Delete Role" ("Are you sure you want to delete this role? This action cannot be undone.", button "Delete"). Both call routes that do not exist on the backend (`/admin/role-mgmt/roles/{id}`), so they fail with "Failed to update role: ..." and "Failed to delete role: ..." (Known gaps).
5. The tabs "Permissions" and "Permission Matrix" are F15.

### Steps, mobile
1. Administration tab > "Role Management" or "Permission Management" (both open `/masters/rolespermissions`, "Roles & Permissions": "Manage user roles and access permissions"; tabs "Roles", "Permissions", "Matrix").
2. "Add Role": fields "Role Name *" (placeholder "Enter role name"), "Description" (placeholder "Enter role description"), "Active". Local message "Role name is required". Toasts "Role Created: Role created successfully.", "Create Failed".
3. Edit and delete fail as on web ("Update Failed", "Delete Failed").
4. Without read or list permission on the screen resource: "Access Denied" and "You don't have permission to view roles and permissions".

### Expected results
Custom roles are rows in `roles` with `is_custom_role` true and `is_system_role` false, per tenant. Roles can be given permissions (F15) and assigned to users (F13).

### API endpoints
| Method and path | Request fields | Permission |
|---|---|---|
| `GET /admin/role-mgmt/roles/` | none | none (any authenticated user) |
| `POST /admin/role-mgmt/` | `name` (2 to 50), `description` (up to 200) | `role_management:create` |
| `PUT /admin/role-mgmt/{role_id}` | `name`, `description`, `is_active` (ignored) | `role_management:update` |
| `DELETE /admin/role-mgmt/{role_id}` | query `force` (default false) | `role_management:delete` |
| `GET /admin/role-mgmt/{role_id}/delete-validation` | none | `role_management:read` |
| `POST /auth/roles/roles/`, `GET /auth/roles/roles/` | `name`, `description` | `role_management:create`, `list` |

### Rules and validations
- List: `{"roles":[{id, name, description, is_active (always true), is_system_role, is_custom_role, created_at (current time), updated_at (current time), permission_count (granted rows)}],"total_roles":n,"tenant_id":...}` ordered by name.
- Create (201): name validators: not one of Admin, Teacher, Staff, Student, Parent (exact case; 422 "Value error, Cannot create system role '<name>'. Use a different name."), only letters, digits, spaces, hyphen, underscore (422), trimmed; a case-insensitive duplicate in the tenant (including `admin`) gives 400 "Role with name '<name>' already exists in this tenant". Response `{"message":"Role created successfully","role":{...,"permission_count":0,"user_count":0,"is_system_role":false},"next_steps":[3 items]}`. The description column holds 100 characters although the schema accepts 200, so 101 to 200 characters fail in the database (500 "Failed to create role: ...").
- Update: system role (by name) 403 "Cannot modify system role '<name>'. System roles are protected."; unknown 404 "Role with ID <id> not found"; a new name that another role uses (case-insensitive) 400 "Role with name '<name>' already exists"; renaming to a system name 422; no change returns "No changes were made to the role" with `changes_made` `{}`; a change returns `changes_made` with old and new values. `is_active` is accepted and ignored (the table has no such column).
- Delete: system role 403 "Cannot delete system role '<name>'. System roles are protected."; unknown 404; assigned users without `force` 400 "Cannot delete role '<name>'. <n> users are assigned to this role. Reassign users to different roles first, or use force=true to override."; success `{"message":"Role '<name>' deleted successfully","deleted_role":{id,name,deleted_at},"impact_summary":{permissions_removed, users_affected 0, force_deletion false, role_deactivated true}}`; the role's permission rows are deleted with it. With `force=true` and assigned users the handler tries to set `users.role_id` to NULL, which the column forbids, so the result is 500 "Failed to delete role: ..." and nothing is deleted. A role that still has role-menu links cannot be deleted either (foreign key, 500).
- Delete validation: for every existing role the handler builds its response from a five-column row and reads a sixth column, so it fails with 500 "Failed to validate role deletion: ..." (intended: `can_delete`, `blocking_factors`, `impact_summary`).
- Legacy `/auth/roles/roles/`: no duplicate or system-name check; a duplicate name violates the per-tenant unique constraint (400 through the global handler).
- Role names are case-sensitive join keys across the system; system roles cannot be renamed or deleted for that reason.

### Error and edge cases
- Role names that differ only in case can be created through scripts or the legacy endpoint but are rejected by `POST /admin/role-mgmt/`.
- A role cannot be deleted while users have it (400) and cannot be forced (500).
- Tenant isolation: roles are tenant rows; the same custom name may exist in two schools.

### Unit-testable logic
`RoleCreateRequest` and `RoleUpdateRequest` validators; name uniqueness and protection branches in the endpoint handlers (fake session); delete decision tree; delete-validation row handling.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-14-U01 | `RoleCreateRequest(name=...)` with `Admin`, `Teacher`, `Staff`, `Student`, `Parent` | validation error "Cannot create system role '<name>'. Use a different name." for each | passing |
| TC-TEN-14-U02 | `RoleCreateRequest(name="admin")` | accepted by the schema (the database check rejects it later) | passing |
| TC-TEN-14-U03 | `RoleCreateRequest` names `a`, 50 characters, 51 characters | rejected, accepted, rejected | passing |
| TC-TEN-14-U04 | `RoleCreateRequest` names `Lab-Tech_1`, `Bad!`, `  Ok  ` | accepted; rejected; accepted and stored as `Ok` | passing |
| TC-TEN-14-U05 | `RoleCreateRequest` description of 200 and 201 characters | accepted; rejected | passing |
| TC-TEN-14-U06 | `RoleUpdateRequest(name="Parent")`; `RoleUpdateRequest()` | rejected "Cannot rename to system role 'Parent'. Use a different name."; valid | passing |
| TC-TEN-14-U07 | `update_role` handler for a system role row (fake session) | HTTPException 403 "Cannot modify system role 'Teacher'. System roles are protected." | passing |
| TC-TEN-14-U08 | `delete_role` handler with 2 assigned users and `force` False | HTTPException 400 with the "Cannot delete role ... 2 users are assigned ..." text | passing |
| TC-TEN-14-U09 | `validate_role_deletion` with a five-column role row | returns `can_delete: true` with a role summary (timestamps and `is_active` are synthesised, as in the roles list) | passing (KG-1 fixed 2026-10-02) |
| TC-TEN-14-A01 | `GET /admin/role-mgmt/roles/` as Admin | 200; five system roles plus custom ones sorted by name (case-insensitive); `total_roles` equals the length; `tenant_id` present; every role `is_active` true | passing |
| TC-TEN-14-A02 | Same call as Staff, Teacher, Student, Parent | 200 for each (no permission check; documents the gap) | passing |
| TC-TEN-14-A03 | `permission_count` for Admin on a fresh `Full` tenant | 276 | passing |
| TC-TEN-14-A04 | `POST /admin/role-mgmt/` `{"name":"QA Librarian","description":"QA custom role"}` | 201; `message` "Role created successfully"; `role.is_system_role` false; `permission_count` 0; `user_count` 0; `next_steps` has 3 items | passing |
| TC-TEN-14-A05 | Create `Admin`, `Staff` | 422 with "Cannot create system role" in the detail | passing |
| TC-TEN-14-A06 | Create `admin` | 400 "Role with name 'admin' already exists in this tenant" | passing |
| TC-TEN-14-A07 | Create `qa librarian` after A04 | 400 "Role with name 'qa librarian' already exists in this tenant" | passing |
| TC-TEN-14-A08 | Create names `x`, `Bad!`, 51 characters | 422 each | passing |
| TC-TEN-14-A09 | Create with a 100-character description; with 101 | 201; 500 "Failed to create role: ..." and no row created | xfail: TEN-ROLE-DESC-LEN (a 101-200 character description passes the schema but fails in the database with 500) |
| TC-TEN-14-A10 | Create the same name in `qa_school_b` | 201 (per-tenant uniqueness) | passing |
| TC-TEN-14-A11 | Role matrix on `POST /admin/role-mgmt/` | Admin 201; Staff, Teacher, Student, Parent 403 "Permission not found in database: <role> cannot create role_management. Contact administrator to configure permissions." | passing |
| TC-TEN-14-A12 | `PUT /admin/role-mgmt/{custom}` `{"name":"QA Librarian Senior","description":"Updated"}` | 200; `changes_made` has `name` and `description` with old and new | passing |
| TC-TEN-14-A13 | `PUT` with the same values | 200; message "No changes were made to the role"; `changes_made` `{}` | passing |
| TC-TEN-14-A14 | `PUT` renaming to the name of another custom role (any case) | 400 "Role with name '<name>' already exists" | passing |
| TC-TEN-14-A15 | `PUT` on the Teacher role | 403 "Cannot modify system role 'Teacher'. System roles are protected." | passing |
| TC-TEN-14-A16 | `PUT` renaming a custom role to `Admin` | 422 | passing |
| TC-TEN-14-A17 | `PUT {"is_active": false}` on a custom role | 200; no change recorded (field ignored) | passing |
| TC-TEN-14-A18 | `PUT` on a random uuid | 404 "Role with ID <id> not found" | passing |
| TC-TEN-14-A19 | Role matrix on `PUT` | Admin 200; other roles 403 (`role_management:update`) | passing |
| TC-TEN-14-A20 | `DELETE /admin/role-mgmt/{custom}` for an unused role | 200; `message` "Role 'QA Librarian Senior' deleted successfully"; `impact_summary.permissions_removed` equals the role's rows; role gone from the list | passing |
| TC-TEN-14-A21 | `DELETE` on Admin, Staff, Teacher, Student, Parent roles | 403 "Cannot delete system role '<name>'. System roles are protected." each | passing |
| TC-TEN-14-A22 | `DELETE` a custom role assigned to one user, no `force` | 400 "Cannot delete role '<name>'. 1 users are assigned to this role. Reassign users to different roles first, or use force=true to override."; role remains | passing |
| TC-TEN-14-A23 | `DELETE ...?force=true` on the same role | 500 "Failed to delete role: ..." (users.role_id cannot be NULL); the role and the user keep their state | xfail: TEN-ROLE-FORCE-DELETE (DELETE with force=true on a role with users answers 500 because users.role_id cannot be NULL) |
| TC-TEN-14-A24 | `DELETE` a custom role that has a role-menu link (F06) | 500 "Failed to delete role: ..." (foreign key); role remains | xfail: TEN-ROLE-FORCE-DELETE (deleting a role that still has a role-menu link answers 500 (foreign key) instead of a client error) |
| TC-TEN-14-A25 | `DELETE` on a random uuid | 404 "Role with ID <id> not found" | passing |
| TC-TEN-14-A26 | Role matrix on `DELETE` of an unused custom role (a fresh role per caller) | Admin 200; Staff, Teacher, Student, Parent 403 (`role_management:delete`) and the role remains | passing |
| TC-TEN-14-A27 | `GET /admin/role-mgmt/{custom}/delete-validation` | 200 with `can_delete` true and a role summary | passing |
| TC-TEN-14-A28 | Same call on a system role and on a random uuid | 500; 404 "Role with ID <id> not found" | passing |
| TC-TEN-14-A29 | Role matrix on the validation call | Admin 500 (defect); other roles 403 (`role_management:read`) | passing |
| TC-TEN-14-A30 | `POST /auth/roles/roles/` as Admin `{"name":"QA Legacy Role"}` | 201; `is_system_role` false; `is_custom_role` false | passing |
| TC-TEN-14-A31 | Repeat A30 | 400 (unique constraint violation through the global handler) | passing |
| TC-TEN-14-A32 | `POST /auth/roles/roles/` `{"name":"Admin"}` | 400 (duplicate of the system role) | passing |
| TC-TEN-14-A33 | `GET /auth/roles/roles/` as Admin; as Staff | 200 with the roles list; 403 | passing |
| TC-TEN-14-A34 | No token on every endpoint of this feature | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-14-A35 | Tenant isolation: roles of `qa_school_b` listed with a `qa_school` token | none of them appear; `DELETE` of a `qa_school_b` role id with a `qa_school` token gives 404 | passing |
| TC-TEN-14-E01 | Web: Admin opens Masters > Roles and Permissions | page "Roles & Permissions"; tab "Roles" lists the five system roles; delete icon of Admin disabled | planned |
| TC-TEN-14-E02 | Web: "Add Role", name "E2E Librarian", description "E2E", submit | toast "Role created successfully"; new row with an Active badge | planned |
| TC-TEN-14-E03 | Web: "Add Role" with name "Admin" | toast "Failed to create role:" containing "Cannot create system role 'Admin'" | planned |
| TC-TEN-14-E04 | Web: edit the new role, change the description, save | toast "Failed to update role:" (client calls a missing route; documents the gap) | planned |
| TC-TEN-14-E05 | Web: delete the new role, confirm "Delete" | toast "Failed to delete role:"; role still listed (documents the gap) | planned |
| TC-TEN-14-E06 | Web: Staff opens `/masters/rolespermissions` | the page and buttons render, the list loads (roles list is unguarded), "Add Role" then fails with 403 | planned |
| TC-TEN-14-E07 | Mobile: Admin opens Administration > "Role Management" | screen "Roles & Permissions" with tabs "Roles", "Permissions", "Matrix" | planned |
| TC-TEN-14-E08 | Mobile: "Add Role" with an empty name | message "Role name is required" | planned |
| TC-TEN-14-E09 | Mobile: "Add Role" with name "E2E Mobile Role" | toast "Role Created" | planned |
| TC-TEN-14-E10 | Mobile: Staff opens `/masters/rolespermissions` | "Access Denied" with "You don't have permission to view roles and permissions" | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_admin_roles_users.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f14_roles.py`.

## F15 Role permissions and resource-permission management

### Purpose
Decide, per role, which `resource:action` pairs are allowed, one at a time, in bulk, from a template, or through the resource-permission table. These rows are what every API permission check reads.

### Roles and permissions
Role-management endpoints (`/admin/role-mgmt/...`): `role_management:read` (view, templates) and `role_management:update` (change, bulk, apply template). Resource-permission endpoints (`/auth/resource-permissions/...`): `resource_permission_management:create`, `read`, `update`, `delete`, `list`. Admin holds them all by default; no other role does. The plan is not consulted: an Admin can grant any pair to any role, its own included.

### Preconditions
A role to edit (a custom role from F14 for destructive tests; system roles only when the test restores them). QA tests use the resource name `qa_widgets` for new pairs.

### Steps, web
1. Open Masters > Roles and Permissions (F14). Tab "Permissions" (card "Resource Permissions": "Manage individual permissions for roles and resources") has "Filter by Role:" (default "All Roles"), a table Resource, Action, Status, Actions (edit and delete icons), "Rows per page" and page buttons.
2. "Add Permission" opens "Create Permission": "Role", "Resource", "Action" (lists from the dropdown endpoints) and the switch "Permission Granted"; toasts "Permission created successfully" and "Failed to create permission: <detail>". The edit icon opens "Edit Permission" ("Update the permission settings"; toast "Permission updated successfully"); only the granted switch has an effect because the backend update reads only `is_granted`. The delete icon opens "Delete Permission" showing Role, Resource, Action, Status (toast "Permission deleted successfully").
3. "Bulk Create" opens "Bulk Create Permissions": choose "Role", add rows with Resource, Action and "Granted"; toast "Permissions created successfully".
4. Tab "Permission Matrix" ("View permissions across all roles and resources in a matrix format"): one row per role, one column per resource, disabled checkboxes per action; "No Permission Matrix Data" when empty.
5. Changes reach the API at once; the affected users' UI changes after their next login.

### Steps, mobile
1. Open `/masters/rolespermissions` (Administration > "Permission Management") and use the tabs "Permissions" (buttons "Add Permission", "Bulk Create"; dialogs with "Role *", "Resource *", "Action *", "Permission Granted") and "Matrix" (totals "Total Permissions", "Resources", "Roles").
2. Messages: "All fields are required", "Please select a role and add at least one permission"; toasts "Permission Created", "Permission Updated", "Permission Deleted", "Permissions Created" and the matching "... Failed" texts.

### Expected results
`resource_permissions` rows (unique per role, resource, action) change. Users of the role get or lose API access immediately; their login responses show the change after re-login.

### API endpoints
| Method and path | Request fields | Permission |
|---|---|---|
| `GET /admin/role-mgmt/roles/{role_id}/permissions` | none | `role_management:read` |
| `PUT /admin/role-mgmt/roles/{role_id}/permissions` | query `resource`, `action`, `is_granted` (all required) | `role_management:update` |
| `POST /admin/role-mgmt/roles/{role_id}/permissions/bulk` | body `{"permissions":[{resource, action, is_granted}]}` | `role_management:update` |
| `GET /admin/role-mgmt/templates/` | none | `role_management:read` |
| `POST /admin/role-mgmt/roles/{role_id}/apply-template` | query `template_name` | `role_management:update` |
| `POST /auth/resource-permissions/` | `role_id`, `resource` (max 50), `action` (max 30), `is_granted` | `resource_permission_management:create` |
| `GET /auth/resource-permissions/` | query `skip` (0), `limit` (100, 1 to 1000) | `...:list` |
| `GET /auth/resource-permissions/{permission_id}` | none | `...:read` |
| `PUT /auth/resource-permissions/{permission_id}` | `is_granted` | `...:update` |
| `DELETE /auth/resource-permissions/{permission_id}` | none (204) | `...:delete` |
| `GET /auth/resource-permissions/role/{role_id}` | none | `...:read` |
| `GET /auth/resource-permissions/resource/{resource}` | none | `...:read` |
| `POST /auth/resource-permissions/bulk` | `role_id`, `permissions[]` of `{resource, action, is_granted}` | `...:create` |
| `GET /auth/resource-permissions/role/{role_id}/summary` | none | `...:read` |
| `GET /auth/resource-permissions/matrix/all` | none | `...:read` |
| `DELETE /auth/resource-permissions/role/{role_id}/all` | none | `...:delete` |
| `DELETE /auth/resource-permissions/resource/{resource}/all` | none | `...:delete` |
| `GET /auth/resource-permissions/dropdown/resources` | none | `...:read` |
| `GET /auth/resource-permissions/dropdown/actions` | none | `...:read` |
| `GET /auth/resource-permissions/check/{role_id}/{resource}/{action}` | none | `...:read` |

### Rules and validations
- `GET .../roles/{id}/permissions`: `{"role":{id,name,description},"permissions":{resource:[{action,is_granted}]},"summary":{total_permissions, granted_permissions, denied_permissions, resources_count}}`; unknown role 404 "Role with ID <id> not found".
- `PUT .../permissions`: creates the row when absent (`action_taken` "created", `old_value` null) or sets `is_granted` ("updated"); response has `message` "Permission created successfully" or "Permission updated successfully", `permission:{resource, action, old_value, new_value}`, `impact:{affected_users, immediate_effect}`. Names are not validated (a resource over 50 or an action over 30 characters fails in the database, 500 "Failed to update role permission: ...").
- Bulk (`/admin/role-mgmt`): empty or missing `permissions` 400 "No permissions provided in request body"; entries missing `resource` or `action` are skipped; `is_granted` defaults to false; response `summary:{total_processed, updated_permissions, created_permissions, total_changes}`.
- Templates: five (Admin 30 actions, Teacher 15, Staff 13, Student 8, Parent 8) with coarse names such as `fee_management`, `student_management`, `staff_management`, `transport_management` that no endpoint checks. `GET` returns `{"templates":{...},"usage":...,"total_templates":5}`. Apply: unknown name 400 "Template '<name>' not found. Available: ['Admin', 'Teacher', 'Staff', 'Student', 'Parent']"; unknown role 404; every pair is upserted with `is_granted` true (revoked rows become granted); response `permissions_applied` = number of actions in the template.
- Resource-permission create: `resource` is lowercased and must be letters, digits, hyphen or underscore (422 otherwise); `action` is trimmed, lowercased and must match `^[a-z][a-z0-9_]*$` (scoped actions such as `read_own` are valid); duplicate role, resource, action 400 "Permission '<resource>:<action>' already exists for role"; unknown role 404 "Role with ID <id> not found". The response has `id, role_id, resource, action, is_granted`.
- List: `{items, total_count, has_next}` ordered by resource then action, `has_next` = `(skip + limit) < total_count`. Unknown id on get, update or delete: 404 "Permission with ID <id> not found". Update changes only `is_granted`; other body fields are ignored. Delete answers 204.
- `GET .../role/{id}` returns every row of the role (an unknown role gives `[]`); `.../resource/{resource}` returns rows with `role_name` and `role_description`; `/bulk` creates only missing rows and returns just the created ones (unknown role 404); `.../summary` gives `{role_id, role_name, total_permissions, granted_permissions, denied_permissions, permissions[]}` (unknown role 404); `/matrix/all` gives `[{role_id, role_name, permissions_by_resource:{resource:{action:is_granted}}}]` sorted by role name; `DELETE /role/{id}/all` and `/resource/{resource}/all` return `{"message":"Deleted <n> permissions for role <id>"}` or `"... for resource '<resource>'"`, deleting across every role for the resource form.
- Dropdowns: distinct resources and actions of the tenant with display names (for example `academic_years` "Academic Years", `fee_categories` "Fee Categories", `read_own` "Read Own", `bulk_delete` "Bulk Delete", other names title-cased with underscores replaced by spaces).
- `check` returns `{"role_id","resource","action","permission_granted":bool}`; false for a missing or revoked row.
- Missing grant: 403 "Permission not found in database: <role> cannot <action> <resource>. Contact administrator to configure permissions."

### Error and edge cases
- Revoking `role_management` rights from Admin locks the Admin out of this feature; tests must restore.
- `DELETE /role/{id}/all` on a system role removes every permission of that role.
- `DELETE /resource/{resource}/all` affects all roles of the tenant.
- A revoked row (`is_granted` false) stays revoked through reseeding (F08) and cannot be re-added by the super admin POST (F10).
- Applying a template grants coarse names that checks never read, so it changes almost nothing for real endpoints.

### Unit-testable logic
`ResourcePermissionBase` validators; template action counts; `PUT` created versus updated branches; bulk counters; matrix assembly; dropdown display-name mapping; has_next formula; web and mobile form requirements.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-15-U01 | `ResourcePermissionBase(resource="Fee_Types", action="Read_Own")` | `fee_types`, `read_own` | passing |
| TC-TEN-15-U02 | `resource="fee types"` and `resource` of 51 characters | validation error each | passing |
| TC-TEN-15-U03 | `action="1bad"`, `action=""`, `action` of 31 characters | validation error each | passing |
| TC-TEN-15-U04 | `ResourcePermissionUpdate()` | valid; `is_granted` `None` | passing |
| TC-TEN-15-U05 | Template action totals in the `templates` dictionary | Admin 30, Teacher 15, Staff 13, Student 8, Parent 8 | passing |
| TC-TEN-15-U06 | `update_role_permission` with an existing row set to true, new value false (fake session) | `action_taken` "updated"; `old_value` true; `new_value` false | passing |
| TC-TEN-15-U07 | Same with no row | `action_taken` "created"; `old_value` `None` | passing |
| TC-TEN-15-U08 | Bulk handler with `[{resource:"a",action:"x"},{resource:"a"},{action:"y"}]` | the first is created with `is_granted` False; the other two skipped; `total_processed` 3; `total_changes` 1 | passing |
| TC-TEN-15-U09 | `get_permission_matrix` for one role with rows (a,read,true), (a,list,false) | `permissions_by_resource` `{"a":{"read":true,"list":false}}` | passing |
| TC-TEN-15-U10 | Dropdown display names for `academic_years`, `exam_hall_tickets`, `read_own`, `bulk_delete` | "Academic Years", "Exam Hall Tickets", "Read Own", "Bulk Delete" | passing |
| TC-TEN-15-U11 | `get_all_permissions` `has_next` for total 5 with (skip 0, limit 5), (0, 4), (4, 1) | false, true, false | passing |
| TC-TEN-15-U12 | `bulk_create_permissions` with one existing and one new pair | returns only the new row | passing |
| TC-TEN-15-A01 | `GET /admin/role-mgmt/roles/{staff}/permissions` as Admin | 200; `summary.total_permissions` equals `granted + denied`; `resources_count` equals the number of keys in `permissions` | passing |
| TC-TEN-15-A02 | Same call for a random role uuid | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A03 | `PUT .../roles/{custom}/permissions?resource=qa_widgets&action=read&is_granted=true` | 200 "Permission created successfully"; `action_taken` "created"; `old_value` null; `new_value` true; `impact.affected_users` equals the users on the role | passing |
| TC-TEN-15-A04 | Same call with `is_granted=false` | 200 "Permission updated successfully"; `old_value` true; `new_value` false | passing |
| TC-TEN-15-A05 | A user of the custom role calls `GET /admin/users/`; grant `user_management:list` through A03-style PUT; call again; revoke; call again | 403, then 200, then 403 with the same access token (no re-login needed on the API) | passing |
| TC-TEN-15-A06 | PUT without `is_granted`; with `is_granted=maybe` | 422 each | passing |
| TC-TEN-15-A07 | PUT with a resource of 50 characters; with 51 | 200; 500 "Failed to update role permission: ..." | xfail: TEN-NAME-LENGTH (an over-long resource name fails in the database and answers 500 instead of a validation error) |
| TC-TEN-15-A08 | PUT with an action of 30 characters; with 31 | 200; 500 | xfail: TEN-NAME-LENGTH (an over-long action name fails in the database and answers 500 instead of a validation error) |
| TC-TEN-15-A09 | PUT for a random role uuid | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A10 | Admin grants its own role `qa_widgets:read` (not in the plan) | 200 (plan not enforced); revoke afterwards | passing |
| TC-TEN-15-A11 | `POST .../permissions/bulk` with three permissions, one existing | 200 "Bulk permission update completed successfully"; `created_permissions` 2; `updated_permissions` 1; `total_changes` 3 | passing |
| TC-TEN-15-A12 | Bulk with `{"permissions":[]}` and with `{}` | 400 "No permissions provided in request body" each | passing |
| TC-TEN-15-A13 | Bulk with an item lacking `resource` | the item is skipped; `total_processed` counts it | passing |
| TC-TEN-15-A14 | Bulk on a random role uuid | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A15 | `GET /admin/role-mgmt/templates/` | 200; `total_templates` 5; keys Admin, Teacher, Staff, Student, Parent | passing |
| TC-TEN-15-A16 | `POST .../roles/{custom}/apply-template?template_name=Teacher` | 200; `permissions_applied` 15; the role now has 15 more rows, all granted | passing |
| TC-TEN-15-A17 | Apply Admin, Staff, Student, Parent templates to fresh custom roles | `permissions_applied` 30, 13, 8, 8 | passing |
| TC-TEN-15-A18 | Revoke `academic_years:read` on the custom role, then apply the Teacher template | that row becomes granted again | passing |
| TC-TEN-15-A19 | Apply `template_name=Librarian` | 400 "Template 'Librarian' not found. Available: ['Admin', 'Teacher', 'Staff', 'Student', 'Parent']" | passing |
| TC-TEN-15-A20 | Apply to a random role uuid | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A21 | User of a role that has the Admin template applied calls `GET /admin/users/` | 403 (template names are not the names endpoints check) | passing |
| TC-TEN-15-A22 | Role matrix on the five `/admin/role-mgmt` permission and template endpoints | Admin 200; Staff, Teacher, Student, Parent 403 | passing |
| TC-TEN-15-A23 | `POST /auth/resource-permissions/` `{"role_id":<custom>,"resource":"QA_Widgets","action":"READ","is_granted":true}` | 201; body `resource` "qa_widgets", `action` "read" | passing |
| TC-TEN-15-A24 | Same pair again | 400 "Permission 'qa_widgets:read' already exists for role" | passing |
| TC-TEN-15-A25 | Create with a random `role_id` | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A26 | Create with resource `qa widgets`; action `1bad`; resource of 51 characters; action of 31 characters | 422 each | passing |
| TC-TEN-15-A27 | Create with `is_granted` false | 201; `is_granted` false | passing |
| TC-TEN-15-A28 | `GET /auth/resource-permissions/` | 200; `items` sorted by resource then action; `total_count` equals the table count; `has_next` correct for `skip=0&limit=10` | passing |
| TC-TEN-15-A29 | List with `limit=0`, `limit=1001`, `skip=-1` | 422 each; `limit=1000` gives 200 | passing |
| TC-TEN-15-A30 | `GET /auth/resource-permissions/{id}` | 200 with the five fields | passing |
| TC-TEN-15-A31 | Get, update and delete a random uuid | 404 "Permission with ID <id> not found" each | passing |
| TC-TEN-15-A32 | `PUT /auth/resource-permissions/{id}` `{"is_granted": false}` | 200; row revoked | passing |
| TC-TEN-15-A33 | `PUT` with `{"role_id":..., "resource":"other","action":"list","is_granted":true}` | 200; only `is_granted` changed; resource and action unchanged | passing |
| TC-TEN-15-A34 | `DELETE /auth/resource-permissions/{id}` then repeat | 204; 404 | passing |
| TC-TEN-15-A35 | `GET /auth/resource-permissions/role/{custom}` | 200; every row of the role including revoked ones | passing |
| TC-TEN-15-A36 | Same with a random role uuid | 200 `[]` | passing |
| TC-TEN-15-A37 | `GET /auth/resource-permissions/resource/qa_widgets` | rows with `role_name` and `role_description` | passing |
| TC-TEN-15-A38 | `POST /auth/resource-permissions/bulk` with two pairs, one existing | 200; list holds only the new row | passing |
| TC-TEN-15-A39 | Bulk with a random `role_id` | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A40 | `GET .../role/{custom}/summary` | `total_permissions` equals `granted + denied`; `permissions` list length equals total | passing |
| TC-TEN-15-A41 | Summary for a random role | 404 "Role with ID <id> not found" | passing |
| TC-TEN-15-A42 | `GET .../matrix/all` | array sorted by `role_name`; each item has `role_id`, `role_name`, `permissions_by_resource` (booleans) | passing |
| TC-TEN-15-A43 | `DELETE .../role/{custom}/all` | 200 "Deleted <n> permissions for role <id>"; role has no rows afterwards | passing |
| TC-TEN-15-A44 | `DELETE .../resource/qa_widgets/all` after creating the resource on two roles | 200 "Deleted 2 permissions for resource 'qa_widgets'" | passing |
| TC-TEN-15-A45 | `GET .../dropdown/resources` | list of `{resource, display_name}` sorted; `academic_years` has "Academic Years"; `qa_widgets` has "Qa Widgets" | passing |
| TC-TEN-15-A46 | `GET .../dropdown/actions` | includes `read_own` with "Read Own" when any role holds it | passing |
| TC-TEN-15-A47 | `GET .../check/{custom}/qa_widgets/read` granted; revoked; never created | `permission_granted` true; false; false | passing |
| TC-TEN-15-A48 | Role matrix on every `/auth/resource-permissions` endpoint | Admin 2xx; Staff, Teacher, Student, Parent 403 (`resource_permission_management`) | passing |
| TC-TEN-15-A49 | No token on all fifteen resource-permission endpoints | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-15-A50 | Tenant isolation: permission ids, role ids and resources of `qa_school_b` used with a `qa_school` token | 404 or empty results; the matrix lists only `qa_school` roles | passing |
| TC-TEN-15-A51 | After a grant, the user's next login | `permissions` includes the pair; the old login response did not | passing |
| TC-TEN-15-E01 | Web: Admin opens the "Permissions" tab | table lists permission rows; "Filter by Role:" defaults to "All Roles" | planned |
| TC-TEN-15-E02 | Web: filter by the custom role | only its rows | planned |
| TC-TEN-15-E03 | Web: "Add Permission", pick role, resource, action, granted on, submit | toast "Permission created successfully"; the row appears | planned |
| TC-TEN-15-E04 | Web: edit the permission, switch off "Permission Granted", save | toast "Permission updated successfully"; Status shows revoked | planned |
| TC-TEN-15-E05 | Web: delete the permission, confirm | toast "Permission deleted successfully"; row gone | planned |
| TC-TEN-15-E06 | Web: "Bulk Create" with two rows | toast "Permissions created successfully"; both rows listed | planned |
| TC-TEN-15-E07 | Web: tab "Permission Matrix" | a table with a row per role and a column per resource; Admin row has the most checked boxes | planned |
| TC-TEN-15-E08 | Web: grant a permission to the Staff role, then log in as Staff | the new control or page appears only after the new login | planned |
| TC-TEN-15-E09 | Web: duplicate permission | toast "Failed to create permission:" with "already exists for role" | planned |
| TC-TEN-15-E10 | Mobile: Admin opens `/masters/rolespermissions`, tab "Permissions" | list loads | planned |
| TC-TEN-15-E11 | Mobile: "Add Permission" with nothing selected | message "All fields are required" | planned |
| TC-TEN-15-E12 | Mobile: "Add Permission" with role, resource, action | toast "Permission Created" | planned |
| TC-TEN-15-E13 | Mobile: tab "Matrix" | totals "Total Permissions", "Resources" and "Roles" shown | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_admin_roles_users.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f15_permissions.py`.

## F16 Tenant resolution and isolation

### Purpose
Guarantee that every request is bound to exactly one school, that a school's data is invisible to every other school, and that a deactivated school is locked out.

### Roles and permissions
No permission; applies to every request. Super admin routes are the only ones that address a tenant by id in the path (F10).

### Preconditions
Two active tenants with the same kind of data (`qa_school`, `qa_school_b`) and users that share usernames.

### Steps, web
Automatic. The web client sends `cschema` only before login and relies on the token afterwards (AUTH F01).

### Steps, mobile
Automatic. The stored organisation code is sent only before login and on refresh.

### Expected results
Row-level security (policy `tenant_isolation` on `tenant_id`, enabled and forced) filters every tenant table to the transaction's tenant, which is set per transaction from the signed `tenant_id`. An unset tenant matches no rows and cannot insert.

### API endpoints
All tenant endpoints. The behaviour is observed through the endpoints of F13, F14, F15, F12 and AUTH.

### Rules and validations
- Tenant for a request: token claim `tenant_id` when present (header must agree, else 403 "Tenant does not match your session"; tenant must be active, else 401 "Invalid connection"); super admin tokens use the header; no token uses the header and an unknown or inactive name gives 404.
- Uniqueness (usernames, role names, menu links, unique indexes) is per tenant; `client_name` is global.
- The API database role is neither owner nor superuser and has no `BYPASSRLS`; every tenant table has forced row-level security (`test_every_tenant_table_has_forced_rls`).
- Tenant lookups are cached 60 seconds per process; deactivation clears the cache in the handling process.
- Platform tables (`tenants`, `plans`, `plan_resource_access`, `plan_menu_access`, `menus`, `super_admin_*`, `token_blacklist`, `report_audit`) have no `tenant_id` and no row-level security.

### Error and edge cases
- A cross-tenant id (user, role, permission) answers 404, never 403 or the foreign row.
- A token replayed against another tenant's header: 403.
- A request that sets no tenant in a session sees zero rows.

### Unit-testable logic
`resolve_request_tenant_id` branches; `open_tenant_session` and the `after_begin` listener; `TenantService.get_tenant_id`, `is_active`, `clear_cache`; `scope_uniques_to_tenant`.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-16-U01 | `resolve_request_tenant_id` with no token and no header | HTTPException 400 "Tenant must be specified" | passing |
| TC-TEN-16-U02 | With only a header naming an unknown tenant | HTTPException 404 "Tenant '<name>' not found or inactive" | passing |
| TC-TEN-16-U03 | With a token carrying `tenant_id` T and a header that resolves to U | HTTPException 403 "Tenant does not match your session" | passing |
| TC-TEN-16-U04 | With a token for an inactive tenant | HTTPException 401 "Invalid connection" | passing |
| TC-TEN-16-U05 | With a token without `tenant_id` and not a super admin | HTTPException 401 "Your session is out of date. Please log in again." | passing |
| TC-TEN-16-U06 | With a super admin token and header `qa_school` | returns the `qa_school` tenant id; `request.state.tenant_id` set | passing |
| TC-TEN-16-U07 | `open_tenant_session("T")` | `session.info["tenant_id"]` is "T" | passing |
| TC-TEN-16-U08 | `after_begin` listener with a fake connection | executes `set_config('app.tenant_id', 'T', true)` once per transaction; nothing when the session has no tenant | passing |
| TC-TEN-16-U09 | `scope_uniques_to_tenant` on a table with `UNIQUE(name)` | the constraint becomes `(tenant_id, name)` | passing |
| TC-TEN-16-U10 | `TenantService.is_active` cache: hit within 60 s, miss after, `clear_cache` | queries only on a miss; `clear_cache` forces a query | passing |
| TC-TEN-16-A01 | Same username in both tenants; `GET /admin/users/` with each Admin token | each list contains only its tenant's users | passing |
| TC-TEN-16-A02 | `GET /admin/users/{id}` with a user id of the other tenant | 404 "User with ID <id> not found" | passing |
| TC-TEN-16-A03 | Create a custom role `Shared Name` in both tenants | 201 in both (unique per tenant) | passing |
| TC-TEN-16-A04 | `GET /admin/role-mgmt/roles/` in each tenant | only own roles | passing |
| TC-TEN-16-A05 | `PUT /school-settings` in `qa_school`, `GET` in `qa_school_b` | `qa_school_b` never sees `qa_school` values | passing |
| TC-TEN-16-A06 | `GET /auth/resource-permissions/` in each tenant | `total_count` equals each tenant's own row count | passing |
| TC-TEN-16-A07 | `GET /auth/permissions/` (role-menu links) in each tenant | only own links | passing |
| TC-TEN-16-A08 | Token of `qa_school` with header `qa_school_b` on any tenant endpoint | 403 "Tenant does not match your session" | passing |
| TC-TEN-16-A09 | Deactivate `qa_school_b`: login, `/auth/academic-years`, and an existing token | 404; 404; 401 "Invalid connection" | passing |
| TC-TEN-16-A10 | Reactivate `qa_school_b` | all three work again | passing |
| TC-TEN-16-A11 | Database check as the API role: `SELECT count(*) FROM users` in a session with no tenant | 0 | blocked: these cases run SQL as the API database role and the task forbids touching the database directly (row-level security is covered by tests/integration/test_tenant_*.py) |
| TC-TEN-16-A12 | Database check: `INSERT INTO users (...)` in a session with no tenant | fails with a NOT NULL violation on `tenant_id` | blocked: these cases run SQL as the API database role and the task forbids touching the database directly (row-level security is covered by tests/integration/test_tenant_*.py) |
| TC-TEN-16-A13 | Database check: `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` | `false`, `false` | blocked: these cases run SQL as the API database role and the task forbids touching the database directly (row-level security is covered by tests/integration/test_tenant_*.py) |
| TC-TEN-16-A14 | Every tenant table has `relrowsecurity` and `relforcerowsecurity` true (existing integration test) | all true | blocked: these cases run SQL as the API database role and the task forbids touching the database directly (row-level security is covered by tests/integration/test_tenant_*.py) |
| TC-TEN-16-A15 | Super admin `GET /super_admin/tenant-data/{qa_school}/users/` | only `qa_school` users, although the super admin has no tenant | passing |
| TC-TEN-16-A16 | Super admin tenant-data call for `qa_school_b` while the session of the previous call was for `qa_school` | each response contains only the path tenant's rows | passing |
| TC-TEN-16-A17 | A new tenant (F07) and a data read before any row exists | empty lists, not another tenant's rows | skipped: tenant cap of 3 qa_tmp tenants reached by earlier runs, no tenant of this shape |
| TC-TEN-16-E01 | Web: log in on host `localhost` (default tenant `qa_school`) with the `qa_school_b` Admin credentials | banner "Invalid Credentials" | planned |
| TC-TEN-16-E02 | Mobile: organisation `qa_school_b`, `b_admin` credentials, active year | sign-in succeeds; Administration > User Management lists only `b_admin` | planned |
| TC-TEN-16-E03 | Mobile: organisation `qa_school_b`, a `qa_school` user's credentials | banner "Invalid Credentials" | planned |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_tenancy_settings.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f16_f17_isolation_seed.py`.

## F17 Seed, legacy and unguarded endpoints

### Purpose
Document the endpoints that exist only for setup, debugging or an earlier design, so their current behaviour is pinned until they are removed or guarded. They are not part of normal operation. Run these cases only against `cos360_test`.

### Roles and permissions
Mixed: `POST /auth/seed/caste-data` needs the role name `Admin`; the other seed endpoints, the role-management test endpoints and the setup endpoints (F01) need no authentication; `/superadmin/organizations` runs a tenant permission check that no caller can pass.

### Preconditions
The QA database. Seeders write public master data (role templates, menu actions, permission templates, plan menu links, states, districts, mandals) or the tenant's caste master data.

### Steps, web
Not available.

### Steps, mobile
Not available.

### Expected results
Seeders are idempotent and add missing rows only. The debug endpoints return diagnostic text. The legacy organisation endpoints deny everyone.

### API endpoints
| Method and path | Notes |
|---|---|
| `POST /auth/seed/permission-data` | No authentication; writes public role templates, menu actions, permission templates and plan menu links |
| `GET /auth/seed/verify-permission-data` | No authentication; reads the same data |
| `POST /auth/seed/location-data` | No authentication; writes public states, districts and mandals |
| `POST /auth/seed/caste-data` | Admin only; writes the tenant's castes and sub-castes |
| `GET /admin/role-mgmt/test/` | Removed 2026-10-02 |
| `GET /admin/role-mgmt/debug-roles/` | Removed 2026-10-02 |
| `POST`, `GET`, `PUT`, `DELETE /superadmin/organizations/...` | Legacy; every call is denied |

### Rules and validations
- Seeders answer 201 each time; second runs create nothing (`..._created` lists are empty). The permission-data seeder expects exactly one menu whose name contains "academic" (the demo catalog has one); with none it fails because it assigns an integer id to a UUID column (500 "Failed to seed permission data: ...").
- `caste-data`: role `Admin` else 403 "Only administrators can seed data"; creates General, OBC, SC, ST, EWS with their sub-castes for the tenant, skipping existing.
- `test/`: `{"message":"Admin endpoint works!","path":...,"client_name":...,"current_schema":"public","roles_table_columns":[...]}`.
- `debug-roles/`: with a valid token returns `{"success":true,"message":"Retrieved N roles for tenant","roles":[...],"debug_info":{...}}`; with an invalid or missing token it still answers 200 with `{"error": ..., "error_type": ...}`.
- `/superadmin/organizations`: the permission check queries the public session where no tenant rows are visible, so every call, for any role and for a super admin token, answers 403; integer path ids are required (`org_id: int`), so UUID ids give 422.
- None of these endpoints should stay mounted in production (Known gaps).

### Error and edge cases
- Seeding writes shared (public) rows that other schools see.
- The debug endpoint exposes the bearer token in server logs.

### Unit-testable logic
The Admin role check in `seed_caste_data`; idempotence of each seeder with a fake session; the denial path of the organisation routes.

### Test cases
| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TEN-17-U01 | `seed_caste_data` handler with role `Staff` (fake session) | HTTPException 403 "Only administrators can seed data" | passing |
| TC-TEN-17-U02 | `seed_caste_data` twice with a fake session that already holds the rows | second call creates 0 castes and 0 sub-castes | passing |
| TC-TEN-17-U03 | `check_role_plan_permission_with_error` called with role `None` | HTTPException 403 "Permission not found in database: None cannot ..." | passing |
| TC-TEN-17-A01 | `POST /auth/seed/permission-data` with header only | 201; `message` "Permission data seeded successfully" | blocked: the seeders write platform-wide public master data (role templates, plan menu links, locations) which the task forbids |
| TC-TEN-17-A02 | Repeat A01 | 201; `details.role_templates_created` `[]` | blocked: the seeders write platform-wide public master data (role templates, plan menu links, locations) which the task forbids |
| TC-TEN-17-A03 | `GET /auth/seed/verify-permission-data` with header only | 200; keys `role_templates`, `academic_menu`, `menu_actions`, `permission_templates`, `plan_access`; five role templates | passing |
| TC-TEN-17-A04 | `POST /auth/seed/location-data` with header only | 201; `message` "Location data seeded successfully"; second call creates 0 states | blocked: the seeders write platform-wide public master data (role templates, plan menu links, locations) which the task forbids |
| TC-TEN-17-A05 | `POST /auth/seed/caste-data` as Admin | 201; `message` "Caste data seeded successfully"; castes General, OBC, SC, ST, EWS exist in the tenant | passing |
| TC-TEN-17-A06 | Same call again | 201; `details.total_castes` 0 and `details.total_sub_castes` 0 | passing |
| TC-TEN-17-A07 | Same call as Staff, Teacher, Student, Parent | 403 "Only administrators can seed data" each | passing |
| TC-TEN-17-A08 | Same call with no token (header only) | 401 "Authorization header missing or invalid" | passing |
| TC-TEN-17-A09 | `GET /admin/role-mgmt/test/` with header `qa_school` and no token | 404 (route removed 2026-10-02) | passing |
| TC-TEN-17-A10 | `GET /admin/role-mgmt/debug-roles/` as Staff | 404 (route removed 2026-10-02) | passing |
| TC-TEN-17-A11 | Same call with a garbage bearer token | 200 with an `error` field | passing |
| TC-TEN-17-A12 | `GET /superadmin/organizations/` as Admin and as the QA super admin | 403 for both | passing |
| TC-TEN-17-A13 | `GET /superadmin/organizations/1`, `PUT`, `DELETE` and `POST /superadmin/organizations/` as Admin | 403 (or 422 for an invalid body) | passing |
| TC-TEN-17-A14 | `GET /superadmin/organizations/<uuid>` | 422 (integer id required) | passing |

Implemented in: `backend/tests/unit/tenants_admin/test_ten_provisioning.py`.

API tests implemented in: `backend/tests/api/tenants_admin/test_f16_f17_isolation_seed.py`.

## Known gaps

Code behaviour that differs from `docs/modules/tenants-and-admin.md`, `docs/permissions.md` or `docs/architecture.md`, or that is a defect found while writing this specification. This file follows the code.

1. Fixed (2026-10-02): `GET /admin/role-mgmt/{id}/delete-validation` answered 500 because the handler read a sixth column from a five-column row; it now returns the role summary with synthesised `is_active` and timestamps.
2. `DELETE /admin/role-mgmt/{id}?force=true` on a role with users answers 500 (`users.role_id` is NOT NULL); a role with role-menu links cannot be deleted either (foreign key, 500). Module doc: only "cannot delete while users are assigned".
3. `GET /super_admin/system/usage-stats` answers 500: the payload contains a SQL `func.now()` that cannot be JSON-encoded.
4. `health_endpoints.py` (`/health/status`, `/health/metrics*`, `/health/metrics/alerts/configure`) is not included in `main_router.py`; those paths do not exist and the Admin permission `monitoring:read` and `monitoring:admin` guards nothing. Only `GET /health` and the super admin health and usage-stats endpoints exist.
5. `docs/permissions.md` section 9 says plan assignment deletes all tenant menus and loses `parent_id`; the code (`change_plan` calling `sync_to_plan`) keeps menus, prunes permissions and role-menu links that the plan no longer allows (including custom roles' rows and revoked rows), and leaves users and roles. `docs/architecture.md` and the module doc are correct.
6. `POST /auth/seed/caste-data` requires the role `Admin`; the architecture and module docs list it as unauthenticated. `permission-data`, `verify-permission-data` and `location-data` are unauthenticated.
7. `GET` and `POST /auth/menus/` act on the shared `public.menus` catalog (the tenant `Menu` model re-exports it), not on tenant-owned menus; a school Admin with `menu_management` can add rows that every school sees.
8. The mobile Menu Management create sends `path`, `icon`, `order`, `is_active` and no `level`, so the API answers 422; the list reads `path` and `order` while the API returns `url` and no order. Module doc says list and create work.
9. Role edit and delete on web and mobile call `/admin/role-mgmt/roles/{id}` (404); the backend routes are `PUT` and `DELETE /admin/role-mgmt/{id}`. The roles list returns a constant `is_active` true and the current time for `created_at` and `updated_at`; `is_active` in a role update is ignored; the role description column holds 100 characters while the schema allows 200.
10. Web `RolesPermissionsPage` decides rights from a hard-coded role (`admin`), and its permission edit dialog sends role, resource and action while the backend updates only `is_granted`.
11. Super admin tenant-data endpoints write no audit rows (module doc: every super admin action is audited); `students/` ignores `class_id`; `POST .../permissions/` only adds and counts a revoked row as existing.
12. `GET /super_admin/system/tenants/` omits `plan_id`; plan list `total_permissions` counts resources while the single-plan view counts actions; the `impact.immediate_effect` texts of plan resource edits are untrue until the plan is re-applied.
13. Plan, role, tenant and permission names are mostly free text: over-long values fail in the database with 500 and error text in `detail`; a negative `limit` on the tenant list also gives 500.
14. No super admin UI: the web `/superorg` page is inside the tenant-authenticated area and calls `/super-admin/...` and `/organizations/...` paths that do not exist; super admin refresh tokens cannot be used and there is no super admin logout; `POST /super_admin/setup/initialize` and `GET /super_admin/setup/status` are unauthenticated, echo the initial password and run DDL that the application database role cannot run.
15. The default role seed covers only part of the application's resources (module doc 9 and `docs/permissions.md`); with the `Full` plan built from the Admin catalog, Student and Parent get 10 and 8 permissions and no `_own` or `_related` or `profile` grants (AUTH Known gaps 8). Admin holds `user_management` read, update and list only (no create or delete exist as endpoints).
16. `/superadmin/organizations` (legacy) denies every caller; the live registry is `tenants`.
17. `GET /admin/role-mgmt/roles/` has no permission check; `/admin/role-mgmt/test/` and `/debug-roles/` are mounted and `debug-roles` prints the `Authorization` header to the console. Fixed (2026-10-02): the debug routes are removed and `GET /admin/role-mgmt/roles/` now requires `role_management:list`.
18. Admin actions on users, roles and permissions leave no tenant-side audit trail; the admin password reset neither sets `is_first_login` nor revokes sessions.
