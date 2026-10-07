# Manual testing guide

Everything a manual tester needs to test COS360 web and mobile: where to test, which logins to use, what to run in which order, how to record results, and how to report a defect.

_Last verified against code: 2026-10-07_

## What you test with

| Item | Where |
|---|---|
| Test cases | `COS360_QA/test_cases/COS360_Test_Cases.xlsx`, sheet "Test Cases" (filter Type = UI). Each row has priority, platform, role, preconditions, numbered steps and the expected result. |
| Smoke set | Sheet "Smoke": every P1 UI case. |
| Journeys | Sheet "Journeys", described in `docs/testing/e2e-journeys.md`. |
| Feature walkthroughs | `docs/features/<module>.md`: what each screen is for, the menu path, the rules and the error cases. Read the feature section before testing it. |
| Known gaps | `docs/modules/<module>.md`, "Known gaps": behaviour that is already known to be wrong. A case that hits one is Blocked, not a new defect. |
| API contract | `COS360_QA/swagger` (`python tools/serve_swagger.py`), for checking what a screen should send or receive. |

## Environment

The test environment runs on a developer machine or a shared test server; never on production data. Setup steps are in `docs/testing/test-environment.md`, section "Manual and UI testing".

| App | Address |
|---|---|
| Web | `http://localhost:5174` |
| Mobile (Expo web, in a phone-sized browser window) | `http://localhost:8082` |
| Mobile on a phone | Expo Go or a test build pointed at the test API (`docs/operations/mobile-release.md`) |

Browsers: latest Chrome for every case; repeat the P1 web cases in Edge and Firefox. Phone checks: one Android phone and one iPhone for the P1 mobile cases.

## Tenant and logins

- Test in the manual-test tenant `qa_manual`, which is seeded with a realistic school (classes, staff, students, fees, exams, transport, expenses). Do not test by hand in `qa_school`: the automated API suite creates and deletes throwaway rows there all the time.
- Admin, Staff, Teacher, Student and Parent logins for the role tests are the QA logins kept in `COS360_QA/.env` (`QA_ADMIN_USER`, `QA_STAFF_USER`, and so on). The test lead gives you the passwords; never paste them into a defect, a screenshot or a document.
- The seeded students and parents also have logins: a student signs in with the admission number, a parent with their email or `<admission number>.father` / `.mother`. New accounts start with the school's temporary password and must change it at first login (AUTH F04). Ask the test lead for the temporary password.
- The mobile app asks for the organisation first: enter `qa_manual`. The web app on localhost uses the tenant it was started with.

## Order of testing

1. Smoke: every P1 case, on web and mobile. Stop and report if more than a few fail; the build is not testable.
2. Journeys J01 to J14, in order.
3. Regression: P2 cases, module by module, in the order of `docs/features/README.md`.
4. Edge cases: P3 cases, as time allows.
5. Retest: every defect marked fixed, then the P1 cases of the affected module.

## Recording a result

Fill these columns of the catalog for each case you run:

| Column | Value |
|---|---|
| Result | `Pass`, `Fail`, `Blocked` or `Not run` |
| Actual Result | What you saw, in one or two sentences. Required for Fail and Blocked. |
| Defect ID | The defect you raised, or the known gap that blocks the case |
| Tester | Your name |
| Test Date | The date of the run |
| Build | The app version or git commit under test (ask the test lead) |

Do not edit the generated columns (ID, steps, expected, automated status). If a step or an expected result is wrong, raise it as a documentation defect.

## Reporting a defect

Before raising a defect, check the module doc's "Known gaps". If it is listed there, mark the case Blocked and quote the gap.

Every defect needs:

- Title: `<Module>: <what is wrong>, <where>`. Example: `Fee: receipt shows placeholder school name, receipt PDF`.
- Case ID (or journey step) and the feature ID.
- Environment: web or mobile, browser or phone model, tenant, role, build.
- Steps to reproduce, numbered, with the exact data used.
- Expected result (quote the case) and actual result.
- Evidence: screenshot or screen recording; for web, the browser console and network errors if any. Blur any password or personal data.
- Severity and priority, from the tables below.

| Severity | Meaning |
|---|---|
| S1 Critical | Data loss, wrong money or marks, a user sees another school's or another family's data, security hole, app unusable |
| S2 Major | A feature does not work and there is no workaround |
| S3 Minor | A feature works with a workaround, or a validation or message is wrong |
| S4 Trivial | Cosmetic: layout, spelling, alignment |

| Priority | Meaning |
|---|---|
| P1 | Fix before the next release |
| P2 | Fix in the next release |
| P3 | Fix when convenient |

Until the team picks a defect tracker, record defects in the "Defects" sheet of the catalog with the fields above.

## Data rules

- Name everything you create with a "QA " prefix and your initials, for example "QA RN Science Club". Journey data uses "QA J<NN>".
- Use only fake people and contacts. The one exception is a phone number or email address that belongs to you, when a case checks a message actually arrives.
- Never press Send in Communication with a whole class or "All parents" selected unless the case says so; the test environment may deliver real messages.
- Delete what you created at the end of a session when the case allows it.

## Exit criteria for a release

- Every P1 case and every journey passes, on web and mobile.
- No open S1 or S2 defect.
- Every P2 case has been run; failures have a defect and a decision (fix now or accept).
- Known gaps that block P1 or P2 cases are listed in the release notes with the decision taken.
