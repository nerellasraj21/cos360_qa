# Testing strategy

How COS360 is tested, in three phases, and how every test traces back to a documented feature.

_Last verified against code: 2026-10-02_

## The three phases

| Phase | Name | What it proves | Needs | Where tests live |
|---|---|---|---|---|
| 1 | Unit | One piece of logic behaves correctly in isolation (calculators, validators, status rules, permission matrices, formatters, query builders) | Nothing external: no database, no network | Backend: `backend/tests/unit/<module>/`. Web: `web/src/**/__tests__/*.test.ts(x)` (vitest). Mobile: `mobile/**/__tests__/*.test.ts(x)` (jest) |
| 2 | API | Each HTTP endpoint accepts valid input, rejects invalid input, enforces permissions per role, scopes data to the tenant, and returns the documented shape | Local test database and a provisioned QA tenant | `backend/tests/api/<module>/` (pytest + httpx) |
| 3 | UI automation | A user can complete each feature end to end in the web app and in the mobile app | Running backend, web dev server, Expo web, seeded QA tenant | `e2e/` (Playwright, projects `web` and `mobile`) |

Run the cheap phases first. A failure in phase 1 or 2 must be fixed before phase 3 results are trusted.

## Feature documentation is the specification

Every feature is documented step by step in `docs/features/<module>.md` (index: `docs/features/README.md`). Each feature section carries a table of test cases with stable IDs. Tests implement those IDs; the IDs are the traceability link.

### Test case IDs

`TC-<MOD>-<FF>-<P><NN>`

- `<MOD>`: module code (table below)
- `<FF>`: two-digit feature number within the module (`F01` in the doc is `01` here)
- `<P>`: phase letter. `U` unit, `A` API, `E` end to end (UI)
- `<NN>`: two-digit sequence within that feature and phase

Example: `TC-FEE-03-A02` is the second API test of the third fee feature.

| Code | Module | Feature doc |
|---|---|---|
| AUTH | Authentication and sessions | `docs/features/auth.md` |
| TEN | Tenants, platform and admin | `docs/features/tenants-and-admin.md` |
| MST | Masters | `docs/features/masters.md` |
| TTC | Timetable and calendar | `docs/features/timetable-calendar.md` |
| STU | Students | `docs/features/students.md` |
| CER | Certificates | `docs/features/certificates.md` |
| STF | Staff | `docs/features/staff.md` |
| COM | Communication | `docs/features/communication.md` |
| FEE | Fee | `docs/features/fee.md` |
| EXM | Exam | `docs/features/exam.md` |
| EXP | Expense | `docs/features/expense.md` |
| TRN | Transport | `docs/features/transport.md` |
| RPT | Reports and dashboards | `docs/features/reports-dashboards.md` |

### Marking tests with their ID

- Backend (pytest): `@pytest.mark.tc("TC-FEE-03-A02")` on the test function, plus the phase marker (`unit` or `api`).
- Web unit (vitest) and mobile unit (jest): put the ID at the start of the test name: `it('TC-FEE-03-U01 rounds a term amount to 2 decimals', ...)`.
- Playwright: `test('TC-FEE-03-E01 collect a full payment', ...)`.

A test with no ID is allowed for ad hoc regression cases. A documented ID with no test is a gap and is listed as `planned` in the doc.

## What each phase must cover

### Phase 1: unit

- Pure logic in `backend/app/service/**` and `backend/app/schemas/**` validators: totals, due-date and status rules, grade and percentage calculation, ID and number generators, pagination, filters, permission resolution.
- Web `src/lib/**` and `src/utils/**` (permission matrices, `menuUtils`, `roleUtils`, validation, formatters, stores' reducers) and mobile `src/lib`, `src/utils`, `services`, `src/types` helpers.
- Use mocks or fakes for the database and clients. A unit test never opens a socket or a database connection.
- Cover the boundary values the rules in `docs/modules/<module>.md` name.

### Phase 2: API

- Every endpoint listed in a feature's "API endpoints" section gets: a happy path, each documented validation failure (422/400), the not-found case (404), the duplicate or conflict case (409/400), and unauthenticated (401).
- Permission matrix: for each endpoint, a parametrised check per role (Admin, Staff, Teacher, Student, Parent) against `docs/permissions.md`. Allowed roles get 2xx, denied roles get 403.
- Tenant isolation: data created in tenant A is invisible in tenant B, and a token for tenant A with a `cschema` header for B gets 403.
- Response shape: assert the documented fields and types, with decimals as strings.
- Data rules: tests create their own rows, use unique names, and delete or roll them back. They never depend on another test's data.

### Phase 3: UI automation

- One spec file per feature under `e2e/tests/<module>/`, tagged with the feature ID.
- The web project runs at 1280x800. The mobile project runs the Expo web build at 390x844 with a mobile user agent and touch enabled.
- Login uses an API-obtained token injected into storage (one fixture per role), not the login form, except in the auth specs that test the form itself.
- Selectors prefer role and accessible name, then `data-testid`. Do not select by CSS class or position.
- Each spec states its precondition data (seeded QA tenant rows it relies on) at the top.
- Assert visible outcomes (toast text, row appears, status badge) and, where cheap, the API state behind them.

## Environments and data safety

- Phases 2 and 3 run only against the **local `cos360_unischema` database** and the **`qa_school` tenant**. Never against the shared Neon database or any other tenant. Setup: `docs/testing/test-environment.md`.
- The test configuration refuses to start when the database URL does not point at `localhost` or `127.0.0.1`, or when the tenant is not a `qa_` tenant.
- Test credentials come from `backend/.env.test` (gitignored) and environment variables. They are never committed.

## Running

| Phase | Command | From |
|---|---|---|
| Backend unit | `pytest tests/unit -m unit` | `backend/` |
| Backend API | `pytest tests/api -m api` | `backend/` |
| Web unit | `npx vitest run` | `web/` |
| Mobile unit | `npm test` | `mobile/` |
| UI (web) | `npx playwright test --project=web` | `e2e/` |
| UI (mobile) | `npx playwright test --project=mobile` | `e2e/` |

Run one feature: `pytest -m "api and tc" -k FEE-03`, or `npx playwright test -g "TC-FEE-03"`.

## Where the backend tests are kept

`backend/tests/` is gitignored on purpose (see `docs/operations/testing.md`), so backend unit and API tests live on the developer machine only. The feature documentation, the strategy, the environment setup, the web and mobile unit tests, and `e2e/` are committed. Because the IDs live in the committed docs, a backend suite can be rebuilt from them.

## Reporting a result

Update the Status column of the feature doc's test table when a test passes: `planned`, `written`, `passing`, `blocked: <reason>`. Defects found while testing go to the module doc's "Known gaps" list.
