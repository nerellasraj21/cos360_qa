# End-to-end journeys

Cross-module journeys that walk a school through a full cycle, the way real users meet the product. Each journey strings together features that are tested one by one in `docs/features/*.md`. Together they are the release smoke test: run them by hand on a fresh manual-test tenant before every release, and automate them in `COS360_QA/ui_tests/tests/journeys/` (titles start with the journey ID).

_Last verified against code: 2026-10-07_

## How to run a journey

- Environment and tenant: `docs/testing/test-environment.md` ("Manual and UI testing"). Use the manual-test tenant, never `qa_school` (the API suite fills it with throwaway rows).
- Run the journeys in order. Later journeys use data created by earlier ones; every journey lists what it needs.
- Each step names the feature it exercises (`STU F03` is feature F03 in `docs/features/students.md`). The detailed clicks, labels and expected messages are in that feature's UI test cases; use the P1 cases first.
- Record every step as Pass, Fail or Blocked in the "Journeys" sheet of the Excel catalog. A step that fails because of a documented known gap is Blocked, with the gap quoted.
- A journey passes when every step passes and its exit checks hold.
- Use names starting with "QA J<NN>" for everything you create, so the data can be found and cleaned up.

## Journey index

| ID | Journey | Roles | Platforms | Needs |
|---|---|---|---|---|
| J01 | Bring a new school online | Super admin, Admin | Web | Nothing |
| J02 | Set up the academic structure | Admin | Web | J01 |
| J03 | Bring the staff on board | Admin, Staff, Teacher | Web, Mobile | J02 |
| J04 | Admit a student and give the family access | Admin, Student, Parent | Web, Mobile | J02 |
| J05 | Set up fees and collect the first payment | Admin, Staff, Parent | Web, Mobile | J04 |
| J06 | Run a school day | Teacher, Admin, Parent, Student | Web, Mobile | J03, J04 |
| J07 | Run an exam from set-up to results | Admin, Teacher, Student, Parent | Web, Mobile | J03, J04 |
| J08 | Issue documents and certificates | Admin, Student, Parent | Web, Mobile | J04 |
| J09 | Transport for a student | Admin, Parent | Web, Mobile | J04, J05 |
| J10 | Spend and approve money | Staff, Admin | Web | J02 |
| J11 | Talk to parents | Admin | Web, Mobile | J04 |
| J12 | Read the school's numbers | Admin | Web, Mobile | J05, J06, J07, J10 |
| J13 | Corrections, refunds and year end | Admin | Web | J05 |
| J14 | Role access and tenant isolation sweep | All roles | Web, Mobile | J03, J04 |

## J01 Bring a new school online

Goal: a super admin provisions a school and its admin can sign in and fill in the school's details.

1. Super admin signs in to the platform API or super admin screens (TEN F02).
2. Super admin checks the plan the school will use and its resources (TEN F04, F05).
3. Super admin provisions tenant `qa_j01_school` on that plan with an admin login (TEN F07). Default roles and permissions are seeded (TEN F08) and a default academic year exists.
4. Admin opens the mobile app, enters organisation `qa_j01_school`, selects the academic year and signs in (AUTH F01, F02, F03). The web app picks the tenant from the host name, so locally it needs a web dev server started with `VITE_DEFAULT_TENANT=qa_j01_school`; in production it is the school's own subdomain.
5. Admin completes the forced first-login password change if prompted (AUTH F04).
6. Admin sees the role-based menu (AUTH F06) and the home dashboard cards (RPT F01).
7. Admin fills in School Registration: name, contacts, address, board, logo and principal signature (MST F14 / TEN F12).

Exit checks: the tenant is listed as active (TEN F09); the admin's menu matches the plan; school settings are saved and shown after a reload.

## J02 Set up the academic structure

Goal: the school is ready to admit students.

1. Create and activate the academic year (MST F01, F02).
2. Create classes with sections (MST F03, F05).
3. Create subject categories and subjects (MST F07, F08).
4. Map subjects to classes, in bulk and singly (MST F09, F10).
5. Add holidays and events to the calendar (TTC F02).
6. Build and save a timetable for one section (TTC F06, F07, F08).

Exit checks: dropdowns in admission and timetable list the new classes and sections (MST F06); the calendar shows the holidays (TTC F01).

## J03 Bring the staff on board

1. Create designations (STF F01).
2. Enroll a teacher and a staff member with qualifications and photo (STF F02, F04, F05).
3. Each new account signs in and changes the temporary password (STF F03, AUTH F04), on web for one and on mobile for the other.
4. Admin marks staff attendance for today (STF F10) and checks history (STF F11).
5. The teacher opens their own profile (STF F12, AUTH F10).

Exit checks: both appear in the staff list and search (STF F06); the teacher's menu shows only teacher items (AUTH F06).

## J04 Admit a student and give the family access

1. Preview or generate an admission number (STU F02).
2. Admit a student with father and mother through the web wizard (STU F03); parents are created or reused (STU F04).
3. Admit a second student on mobile, as a sibling of the first (STU F03, F04).
4. Upload a student photo and a document (STU F05, F14).
5. The student signs in with the admission number and the temporary password and changes it (AUTH F03, F04).
6. The parent signs in, picks a child, and sees the child's admission view and profile (AUTH F09, STU F17, F18, F19).

Exit checks: both students appear in the admission list (STU F06) and details view (STU F07); the parent sees exactly two children.

## J05 Set up fees and collect the first payment

1. Create fee categories, fee types and terms with installment dates (FEE F01, F02, F03).
2. Map fees to the student's class, with term amounts (FEE F04, F05), and confirm the student's fee mapping (FEE F06).
3. Add a sibling concession for the second student (FEE F07).
4. Staff finds the student and reads the fee summary and terms due (FEE F09).
5. Staff collects a partial payment by cash and a second payment by UPI (FEE F10).
6. Staff opens and prints the receipt, then reprints it (FEE F11).
7. The parent sees the paid amounts, the outstanding balance and the receipts (FEE F16).

Exit checks: transactions list both payments (FEE F12); the balance equals the mapped total minus concession minus payments; the receipt PDF opens.

## J06 Run a school day

1. The teacher marks attendance for the class on web, including one absent and one late (STU F11).
2. The teacher corrects one entry (STU F12).
3. The parent sees the child's attendance history and percentage on mobile (STU F13).
4. The student and parent open today's timetable and the school calendar on mobile (TTC F11, F12).

Exit checks: the attendance percentage matches the marks entered; the absent student is listed in the attendance report (RPT F07).

## J07 Run an exam from set-up to results

1. Configure exam settings, a board pattern, a grade scheme and remark grades (EXM F01 to F05).
2. Create an exam for the class with subject configs and dates (EXM F06, F07, F08) and activate it (EXM F09).
3. Grant mark entry permission to the teacher (EXM F10).
4. The teacher enters marks for every student, one subject by Excel upload (EXM F11) and checks the marks summary (EXM F12).
5. Admin checks hall ticket eligibility, publishes and downloads hall tickets (EXM F13, F14).
6. Admin computes and publishes results (EXM F15, F16).
7. The student and parent see marks and results (EXM F17).

Exit checks: ranks and grades match the grade scheme; the audit log shows the mark changes (EXM F18).

## J08 Issue documents and certificates

1. Create a certificate type and a template (CER F01, F02).
2. Select the student, upload a received document and issue a certificate file (CER F03, F04, F05).
3. Generate a certificate from the template (CER F06).
4. The student and the parent see and download the certificate (CER F11, F12, F10).

Exit checks: the admin list shows both files with metadata (CER F07).

## J09 Transport for a student

1. Create a route with stops, a vehicle with a driver, and trips (TRN F04 to F07).
2. Set transport pricing (TRN F08).
3. Assign the student to a route and stop (TRN F09 / STU F21).
4. Check the transport fee effect on the student's fees (TRN F12).
5. The parent sees the child's transport details (TRN F10).

## J10 Spend and approve money

1. Create expense categories, types and departments, and review expense settings (EXP F02 to F05).
2. Staff records an expense with line items and an attachment (EXP F06, F10).
3. The amount triggers approval; admin approves one expense and rejects another (EXP F11, F12).
4. Admin reviews the summary and the expense reports and exports one (EXP F13, F14).

Exit checks: the audit trail lists every change (EXP F15).

## J11 Talk to parents

1. Create a WhatsApp or email template and an SMS template (COM F01).
2. Pick class-section parents and read the preview count (COM F02).
3. Send to a single test parent whose contact is a tester's own (COM F03). In an environment without a delivery worker this step is Blocked: messages stay queued (COM F05).
4. Read the message log and its detail (COM F06).

## J12 Read the school's numbers

1. Admin opens the reports hub (RPT F03).
2. Student, staff, fee, attendance and financial reports load with filters and match the data created in J04 to J10 (RPT F04 to F08).
3. Export one report as CSV, Excel and PDF (RPT F12).
4. On mobile, open the academic and transport reports (RPT F10, F11).

## J13 Corrections, refunds and year end

1. Refund part of a payment and approve it (FEE F13).
2. Carry forward unpaid balances as old fees and settle one (FEE F08).
3. Create the next academic year and switch the working year (MST F01, F02).

Exit checks: fee reports reflect the refund (FEE F15); the old fee shows against the student in the new year.

## J14 Role access and tenant isolation sweep

1. Sign in as each role on web and mobile and compare the menu with `docs/permissions.md` (AUTH F06, F07).
2. As Teacher, Student and Parent, open admin-only URLs directly; the screen must not show data and the API must refuse (AUTH F07).
3. As the parent, try another family's student; access is refused (STU F17, EXM F17).
4. Sign in to `qa_j01_school` and the manual-test tenant side by side; neither shows the other's data (TEN F16).
5. Sign out on both platforms; protected pages redirect to sign-in (AUTH F14).
