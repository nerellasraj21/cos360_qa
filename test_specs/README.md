# Feature documentation

Step-by-step documentation of every COS360 feature. Each page is both the user-facing walkthrough and the specification the tests implement. Conventions and test case IDs: `docs/testing/strategy.md`.

_Last verified against code: 2026-10-02_

| Module | Doc |
|---|---|
| Authentication and sessions | `auth.md` |
| Tenants, platform and admin | `tenants-and-admin.md` |
| Masters | `masters.md` |
| Timetable and calendar | `timetable-calendar.md` |
| Students | `students.md` |
| Certificates | `certificates.md` |
| Staff | `staff.md` |
| Communication | `communication.md` |
| Fee | `fee.md` |
| Exam | `exam.md` |
| Expense | `expense.md` |
| Transport | `transport.md` |
| Reports and dashboards | `reports-dashboards.md` |

## How a feature page is laid out

Each feature is a section `## F<NN> <Title>` with these parts, in this order:

1. **Purpose**: one or two sentences on what the user achieves.
2. **Roles and permissions**: who can do it, as `resource:action` pairs, and which roles see it in the menu.
3. **Preconditions**: data and settings that must exist first (and which feature creates them).
4. **Steps, web**: numbered steps using the real menu path, button and field labels.
5. **Steps, mobile**: numbered steps with the real screen and control names, or "same as web" plus the differences.
6. **Expected results**: what the user sees and what is stored.
7. **API endpoints**: method and path, with the request fields that matter.
8. **Rules and validations**: business rules, limits, formats, calculations.
9. **Error and edge cases**: what happens on bad input, missing permission, duplicates, empty data.
10. **Unit-testable logic**: the functions and rules that phase 1 covers.
11. **Test cases**: a table of `ID | Scenario | Expected | Status`, using the IDs from the strategy.

Features within a module are ordered the way a user meets them: setup first, daily operations next, reporting and clean-up last.
