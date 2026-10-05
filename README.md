# COS360 QA framework

One project for testing COS360 end to end:

| Part | Folder | State |
|---|---|---|
| API tests (pytest, httpx) | `api_tests/` | about 4,300 tests, 13 modules, runnable |
| UI tests (Playwright, JavaScript, web and Expo-web mobile) | `ui_tests/` | scaffold and first auth specs, not yet run |
| AI tests | `ai_tests/` | reserved, nothing yet |
| API contract (Swagger UI) | `swagger/` | exported from the running API |
| Test case catalog (Excel and CSV) | `test_cases/` | generated from the specs and the last run |
| Test case specs (source of the catalog) | `test_specs/` | copied from `COS360_Full_App/docs/features` |

The suite only talks to a running COS360 backend over HTTP. It refuses to run unless the API URL is local and the tenant name starts with `qa_`.

## One-time setup

1. Python 3.11+ and Node 20+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in the QA logins (same values as `COS360_Full_App/backend/.env.test`). `.env` is gitignored.
4. The QA tenant (`qa_school`, plus `qa_school_b` for isolation tests) must exist. Create it once from the app repo:
   `python scripts/qa/setup_qa_tenant.py` (run inside `COS360_Full_App/backend`; see `docs/testing/test-environment.md` there).
5. UI tests only: `cd ui_tests`, `npm install`, `npx playwright install chromium`.

## Start the QA API

From `COS360_Full_App/backend`:

```
python scripts/qa/run_test_api.py
```

It listens on `http://127.0.0.1:8100` with rate limiting off and the local QA database.

## Run the API tests

```
python tools/run_api_tests.py                  # everything, 4 workers (about 35 to 40 minutes)
python tools/run_api_tests.py api_tests/fee    # one module
QA_WORKERS=2 python tools/run_api_tests.py     # fewer workers
```

Equivalent plain pytest: `python -m pytest api_tests -m api -q -n 4`. Always use `-n 4` or similar; a serial run takes hours. After each run the Excel catalog is rebuilt with the results.

Notes:
- Tests create their own data with unique names and clean up. A run killed halfway can leave rows or role grants behind; `python scripts/qa/setup_qa_tenant.py --reset` in the app repo returns the tenant to a clean baseline.
- A few tests read uploaded files from the backend's disk, so `COS360_APP` in `.env` must point at the `COS360_Full_App` folder.
- Skipped tests are deliberate: rate limiting is off, SMS, email and WhatsApp sends are never triggered, and some checks need direct database access.
- Tests marked as expected failures (xfail) document known application defects. When a defect is fixed the test starts to pass and fails the run, which is the signal to remove the marker.

## Run the UI tests

```
cd ui_tests
npx playwright test --project=web
npx playwright test --project=mobile
npx playwright show-report
```

The config starts the QA API, the web dev server (port 5174) and Expo web (port 8082) if they are not already running, all pointed at `qa_school`.

## View the API contract (Swagger)

```
python tools/export_openapi.py     # refresh from the running API
python tools/serve_swagger.py      # opens http://127.0.0.1:8200
```

`swagger/openapi.json` can also be imported into Postman or Insomnia. The page loads the Swagger UI scripts from a CDN, so it needs internet access.

## View the test cases

Open `test_cases/COS360_Test_Cases.xlsx`: a Summary sheet per module and a Test Cases sheet (ID, module, feature, type, scenario, expected result, status in the docs, automated or not, last run, test file) with filters. `COS360_Test_Cases.csv` has the same rows for importing into free test management tools such as TestLink, Kiwi TCMS or TestRail.

Refresh after the docs change:

```
python tools/sync_specs.py            # copy the feature docs from the app repo
python tools/build_test_catalog.py
```

## Test case IDs

`TC-<MODULE>-<FEATURE>-<TYPE><NN>`, for example `TC-FEE-03-A02`. Type is `U` unit, `A` API, `E` UI. API tests carry the ID with `@pytest.mark.tc("...")`.
