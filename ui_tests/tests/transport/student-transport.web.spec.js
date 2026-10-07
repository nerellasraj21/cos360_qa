// Transport F09-F12 student transport, web. Uses the seeded student Ananya Reddy (no assignment) and removes
// any assignment it creates; the student-facing view uses a throwaway family with its own assignment.
const { test, expect, toast } = require('../../helpers/fixtures');
const { createFamily, injectWeb } = require('../../helpers/throwaway');
const { list, routeByName, stopsOf, studentByName, assignStudent, assignmentsOf, clearAssignments } = require('./kit');

test.describe.configure({ mode: 'serial' });

async function tripOfRoute(api, routeName) {
  const route = await routeByName(api, routeName);
  const trips = list(await api('GET', '/masters/trips/?limit=1000'));
  return { route, trip: trips.find((t) => t.route_id === route.id) };
}

test.describe('Transport F09-F12 student transport (web)', () => {
  test('TC-TRN-09-E01 admin assigns Ananya Reddy to a Route 1 stop', async ({ page, signIn, api, cleanup }) => {
    test.fail(true, 'UI-TRN-01: choosing a trip in the Assign Transport dialog crashes the page (Something went wrong: Select.Item must have a value prop that is not an empty string) whenever the trip vehicle has a pricing plan, because the "None" pricing option is built with an empty value');
    const student = await studentByName(api, 'Ananya Reddy');
    await clearAssignments(api, student.id);
    cleanup(() => clearAssignments(api, student.id));
    await signIn('admin');
    await page.goto('/students/studenttransport');
    await expect(page.getByRole('heading', { name: 'Student Transport' })).toBeVisible();
    await page.getByRole('button', { name: 'Assign Transport' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox').nth(0).click();
    await page.getByRole('option', { name: 'Ananya Reddy' }).click();
    for (const index of [0, 1]) {
      await dialog.getByRole('combobox').nth(1).click();
      await page.getByRole('option', { name: 'Trip #1' }).nth(index).click();
      await expect(dialog).toBeVisible();
      await expect(page.getByText('Something went wrong')).toHaveCount(0);
      await dialog.getByRole('combobox').nth(2).click();
      const stop = page.getByRole('option', { name: /KPHB Phase 1/ });
      if (await stop.isVisible().catch(() => false)) break;
      if (await stop.waitFor({ timeout: 1500 }).then(() => true).catch(() => false)) break;
      await page.keyboard.press('Escape');
    }
    await page.getByRole('option', { name: /KPHB Phase 1/ }).click();
    await expect(dialog.getByRole('spinbutton')).toHaveValue('1200');
    await dialog.getByRole('button', { name: 'Assign', exact: true }).click();
    await toast(page, 'Student transport created!');
    const row = page.getByRole('row').filter({ hasText: 'Ananya Reddy' });
    await expect(row).toContainText('Trip #1');
    await expect(row).toContainText('Route 1 - Kukatpally');
    await expect(row).toContainText('KPHB Phase 1');
    await expect(row).toContainText('1,200');
    const stored = await assignmentsOf(api, student.id);
    expect(stored).toHaveLength(1);
    expect(Number(stored[0].fee_per_term)).toBe(1200);
  });

  test('TC-TRN-10-E01 student sees My Transport', async ({ page, api, cleanup }) => {
    test.setTimeout(240_000);
    const family = await createFamily(cleanup);
    const { route, trip } = await tripOfRoute(api, 'Route 1 - Kukatpally');
    const stop = (await stopsOf(api, route.id)).find((s) => s.name === 'Kukatpally Bus Stand');
    await assignStudent(api, cleanup, { studentId: family.studentId, tripId: trip.id, stopId: stop.id, fee: 4000 });
    await injectWeb(page, family.admissionNumber, family.studentPassword);
    await page.goto('/students/studenttransport');
    await expect(page.getByRole('heading', { name: 'My Transport' })).toBeVisible();
    const card = page.getByRole('main');
    await expect(card.getByText('Transport Assignment')).toBeVisible();
    await expect(card).toContainText('Route 1 - Kukatpally');
    // doc: the Vehicle line shows the registration number and type (TS09UA1234, Bus), not the vehicle name
    await expect(card).toContainText('TS09UA1234');
    await expect(card).toContainText('Kukatpally Bus Stand');
    await expect(card).toContainText('07:00');
    await expect(card).toContainText('17:15');
    await expect(card).toContainText('4,000');
  });

  test('TC-TRN-11-E01 admin adds a student trip assignment', async ({ page, signIn, api, cleanup }) => {
    const student = await studentByName(api, 'Ananya Reddy');
    await clearAssignments(api, student.id);
    cleanup(() => clearAssignments(api, student.id));
    await signIn('admin');
    await page.goto('/transport/studentTrips');
    await expect(page.getByRole('heading', { name: 'Student Transport Assignments' })).toBeVisible();
    await page.getByRole('button', { name: 'Add Assignment' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox').nth(0).click();
    await page.getByRole('option', { name: /Route 2/ }).first().click();
    await dialog.getByRole('combobox').nth(1).click();
    await page.getByRole('option', { name: 'Ananya Reddy' }).click();
    await dialog.getByRole('combobox').nth(2).click();
    await page.getByRole('option', { name: /Habsiguda/ }).first().click();
    await dialog.getByRole('spinbutton', { name: 'Fee Per Term' }).fill('1300');
    await dialog.getByRole('button', { name: 'Add Assignment' }).click();
    await toast(page, 'Student trip created!');
    const stored = await assignmentsOf(api, student.id);
    expect(stored).toHaveLength(1);
    expect(Number(stored[0].fee_per_term)).toBe(1300);
    const row = page.getByRole('row').filter({ hasText: 'Ananya Reddy' });
    await expect(row).toBeVisible();
    await expect(row).toContainText(/inactive/i);
  });

  test('TC-TRN-12-E01 fee per term is prefilled from the student transport fee mapping', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(240_000);
    const family = await createFamily(cleanup);
    const years = await api('GET', '/masters/academic_years/?active_only=true');
    const year = list(years).find((y) => y.is_active);
    const terms = list(await api('GET', '/fee/terms/?limit=5'));
    const classes = list(await api('GET', '/masters/class_sections/dropdown'));
    const klass = classes.find((c) => c.name === family.className);
    const sections = await api('GET', `/masters/class_sections/by_class_id/${klass.id}/sections`);
    const category = await api('POST', '/fee/categories/', { body: { category_name: `QA Transport ${family.admissionNumber}`.slice(0, 60), academic_year_id: year.id } });
    expect(category.status).toBe(201);
    cleanup(() => api('DELETE', `/fee/categories/${category.data.id}`));
    const feeType = await api('POST', '/fee/types/', {
      body: { type_name: `QA Bus Fee ${family.admissionNumber}`.slice(0, 60), fee_category_id: category.data.id, fee_term_id: terms[0].id, academic_year_id: year.id },
    });
    expect(feeType.status).toBe(201);
    cleanup(() => api('DELETE', `/fee/types/${feeType.data.id}`));
    const mapping = await api('POST', '/fee/student-mappings/', {
      body: {
        student_id: family.studentId,
        student_admission_num: family.admissionNumber,
        class_id: klass.id,
        section_id: sections.data[0].id,
        fee_type_id: feeType.data.id,
        total_fee: '5400.00',
        academic_year_id: year.id,
      },
    });
    expect(mapping.status).toBe(201);
    cleanup(() => api('DELETE', `/fee/student-mappings/${mapping.data.id}`));
    await signIn('admin');
    await page.goto('/students/studenttransport');
    await page.getByRole('button', { name: 'Assign Transport' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox').nth(0).click();
    await page.getByRole('option', { name: family.studentName }).click();
    await expect(dialog.getByRole('spinbutton')).toHaveValue('5400');
    await expect(dialog.getByText(/Auto-loaded from the student's assigned transport fee/)).toBeVisible();
  });
});
