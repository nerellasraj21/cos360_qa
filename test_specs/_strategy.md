# Testing strategy

How COS360 is tested, in three phases, and how every test traces back to a documented feature.

_Last verified against code: 2026-10-07_

## The three phases

| Phase | Name | What it proves | Needs | Where tests live |
|---|---|---|---|---|
| 1 | Unit | One piece of logic behaves correctly in isolation (calculators, validators, status rules, permission matrices, formatters, query builders) | Nothing external: no database, no network | Backend: `backend/tests/unit/<module>/`. Web: `web/src/**/*.test.ts` (vitest; `src/components/dropdown-system/**` is excluded). Mobile: `mobile/__tests__/**` (jest) |
| 2 | API | Each HTTP endpoint accepts valid input, rejects invalid input, enforces permissions per role, scopes data to the tenant, and returns the documented shape | Local test database and a provisioned QA tenant | `backend/tests/api/<module>/` (pytest + httpx), copied as the standalone suite `COS360_QA/api_tests/` |
| 3 | UI | A user can complete each feature in the web app and in the mobile app, by hand (manual test cases) or by Playwright | Running test API, web and Expo web dev servers, seeded manual-test tenant | Manual: the UI cases in `docs/features/*.md`, exported to the COS360_QA Excel catalog. Automated: `COS360_QA/ui_tests/` (Playwright, JavaScript) |

There is also a cross-module journey suite, `docs/testing/e2e-journeys.md`, that runs a whole school cycle per role. It is the release smoke test, by hand or automated.

Run the cheap phases first. A failure in phase 1 or 2 must be fixed before phase 3 results are trusted.

## The external QA project

`COS360_QA` (a separate repository next to this one) holds everything a tester needs without the app source: the standalone API suite, the Playwright UI suite, the Swagger contract exported from the API, and the test case catalog (`test_cases/COS360_Test_Cases.xlsx` and `.csv`). The catalog is generated, never edited by hand: `tools/sync_specs.py` copies `docs/features/*.md` into `test_specs/`, and `tools/build_test_catalog.py` builds the workbook from those specs plus the latest run results in `reports/results-*.json`. The feature docs in this repo stay the single source of truth.

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

### Phase 3: UI (manual and automated)

UI cases (`-E<NN>`) are written so that a manual tester and a Playwright spec follow the same steps. Their table in the feature doc has eight columns:

| Column | Content |
|---|---|
| ID | `TC-<MOD>-<FF>-E<NN>`, never renumbered |
| Priority | `P1` smoke (core happy path, at least one per feature), `P2` regression, `P3` edge, negative or cosmetic |
| Platform | `Web` or `Mobile` |
| Role | Admin, Staff, Teacher, Student, Parent or Super admin |
| Preconditions | Data and state needed, by baseline name or by the case ID that creates it |
| Steps | Numbered single actions separated by `<br>`, with exact on-screen labels in double quotes and concrete data (names start with "QA ") |
| Expected | Observable result, exact message text where known, and what is stored |
| Status | See "Reporting a result" |

Automation rules (`COS360_QA/ui_tests`):
- Spec files live under `ui_tests/tests/<module>/`, named `<feature>.web.spec.js` or `<feature>.mobile.spec.js` (the suffix picks the project). Test titles start with the case ID: `test('TC-FEE-03-E01 add a term', ...)`.
- Projects: `web` at 1280x800 against `http://127.0.0.1:5174`; `mobile` is the Expo web build at 390x844 (Pixel 5 profile) against `http://127.0.0.1:8082`. The config starts the test API and both dev servers if they are not already running, and refuses a non-local API or a tenant without the `qa_` prefix.
- Web specs sign in by injecting an API token into storage (`helpers/session.js` `signInWeb`). Mobile specs sign in through the form (`signInMobileViaForm`); a token-only session is not enough for the mobile app. Auth specs that test the form always use the form.
- Selectors prefer role and accessible name, then visible text, then `data-testid`. Do not select by CSS class or position. Mobile renders plain elements without roles, so mobile specs use visible text.
- Each spec states the baseline data it relies on at the top.
- Assert visible outcomes (toast text, row appears, status badge) and, where cheap, the API state behind them.

## Environments and data safety

- Phases 2 and 3 run only against the **local `cos360_unischema` database** and the **`qa_school` tenant**. Never against the shared Neon database or any other tenant. Setup: `docs/testing/test-environment.md`.
- The test configuration refuses to start when the database URL does not point at `localhost` or `127.0.0.1`, or when the tenant is not a `qa_` tenant.
- Test credentials come from `backend/.env.test` (gitignored) and environment variables. They are never committed.

## Running

| Phase | Command | From |
|---|---|---|
| Backend unit | `pytest tests/unit` (some unit files carry no `unit` marker, so do not filter with `-m unit`) | `backend/` |
| Backend API | `pytest tests/api -m api -n 4` (needs the test API on port 8100) | `backend/` |
| API, standalone | `python tools/run_api_tests.py` (writes `reports/results-*.json`) | `COS360_QA/` |
| Web unit | `npm test` (vitest run) | `web/` |
| Mobile unit | `npm test` (jest) | `mobile/` |
| UI (web) | `npx playwright test --project=web` | `COS360_QA/ui_tests/` |
| UI (mobile) | `npx playwright test --project=mobile` | `COS360_QA/ui_tests/` |
| Test catalog | `python tools/sync_specs.py` then `python tools/build_test_catalog.py` | `COS360_QA/` |

Run one feature: `pytest -m api -k FEE-03`, or `npx playwright test -g "TC-FEE-03"`.

## Where the tests are kept

`backend/tests/` is gitignored on purpose (see `docs/operations/testing.md`), so the backend unit and API tests live on the developer machine, and the API suite is also kept in the COS360_QA repository. The feature documentation, the strategy, the environment setup and the web and mobile unit tests are committed here. Because the IDs live in the committed docs, a backend suite can be rebuilt from them.

## Reporting a result

The Status column of a feature doc's test table takes one of these values:

| Status | Meaning |
|---|---|
| `planned` | Documented, not yet executed or automated |
| `passing` | Automated and passing in the latest run |
| `failing` | Automated and failing in the latest run (a new defect) |
| `known defect: <id or reason>` | Automated and failing on purpose, held by an expected-failure marker until the defect is fixed |
| `skipped: <reason>` | Automated but not runnable in the test environment (for example it would send a real SMS) |
| `blocked: <reason>` | Cannot be executed because of an open defect or a missing screen |
| `obsolete: <reason>` | No longer applies; kept so the ID is never reused |

Unit and API statuses are refreshed from the latest run by the catalog tooling. Manual results are recorded in the Excel catalog (Actual result, Result, Tester, Date) and reported as described in `docs/testing/manual-testing-guide.md`. Defects found while testing go to the module doc's "Known gaps" list once confirmed.
