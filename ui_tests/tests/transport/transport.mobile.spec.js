// Transport P1 cases, mobile (Expo web). Own data only; Ananya Reddy's assignment is removed in cleanup.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createFamily, injectMobile } = require('../../helpers/throwaway');
const { list, routeByName, stopsOf, studentByName, assignStudent, assignmentsOf, clearAssignments } = require('./kit');

function vis(page, text, options = { exact: true }) {
  return page.getByText(text, options).locator('visible=true').first();
}

async function openDashboard(page) {
  await page.goto('/', { timeout: 180_000 });
  await expect(vis(page, 'Modules')).toBeVisible({ timeout: 60_000 });
}

test.describe('Transport P1 (mobile)', () => {
  test('TC-TRN-01-E03 transport module shows two section tiles', async ({ page, signIn }) => {
    await signIn('admin');
    await openDashboard(page);
    await page.getByRole('button', { name: 'Open Transport' }).locator('visible=true').click();
    await expect(vis(page, 'Transport Management')).toBeVisible({ timeout: 60_000 });
    await expect(vis(page, 'Routes · Stops · Vehicles · Trips', { exact: false })).toBeVisible();
    await expect(vis(page, 'TRANSPORT SECTIONS')).toBeVisible();
    await expect(vis(page, 'Routes')).toBeVisible();
    await expect(vis(page, 'Vehicles')).toBeVisible();
    await expect(page.getByText('Route Stops', { exact: true }).locator('visible=true')).toHaveCount(0);
    await expect(page.getByText('Pricing', { exact: true }).locator('visible=true')).toHaveCount(0);
    await expect(page.getByText('Student Transport', { exact: true }).locator('visible=true')).toHaveCount(0);
  });

  test('TC-TRN-02-E01 mobile route form has no route type or trip type control', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/transport/routes', { timeout: 180_000 });
    await expect(vis(page, 'Route 1 - Kukatpally')).toBeVisible({ timeout: 60_000 });
    await vis(page, 'Add Route').click();
    await expect(vis(page, 'Add New Route')).toBeVisible();
    await expect(page.getByText(/Route Type/i).locator('visible=true')).toHaveCount(0);
    await expect(page.getByText(/Trip Type/i).locator('visible=true')).toHaveCount(0);
  });

  test('TC-TRN-04-E07 create a route on mobile', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Route 4 - Miyapur');
    await signIn('admin');
    await openDashboard(page);
    await page.getByRole('button', { name: 'Open Transport' }).locator('visible=true').click();
    await expect(vis(page, 'Transport Management')).toBeVisible({ timeout: 60_000 });
    await vis(page, 'Routes').click();
    await expect(vis(page, 'Route 1 - Kukatpally')).toBeVisible({ timeout: 60_000 });
    await vis(page, 'Add Route').click();
    await page.getByPlaceholder('Enter route name').locator('visible=true').fill(name);
    await page.getByPlaceholder('Starting point').locator('visible=true').fill('QA Miyapur');
    await page.getByPlaceholder('Ending point').locator('visible=true').fill('Demo School Campus');
    await page.getByText('Add Route', { exact: true }).locator('visible=true').last().click();
    await toast(page, 'Route created successfully');
    const created = await routeByName(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/routes/${created.id}`));
    await expect(vis(page, name)).toBeVisible();
  });

  test('TC-TRN-09-E08 assign transport to Ananya Reddy on mobile', async ({ page, signIn, api, cleanup }) => {
    const student = await studentByName(api, 'Ananya Reddy');
    await clearAssignments(api, student.id);
    cleanup(() => clearAssignments(api, student.id));
    await signIn('admin');
    await page.goto('/students/transport', { timeout: 180_000 });
    await expect(vis(page, 'Student Transport Assignments')).toBeVisible({ timeout: 60_000 });
    await vis(page, 'Assign Transport').click();
    await vis(page, 'Select student').click();
    await page.getByText(/^Ananya Reddy \(/).locator('visible=true').first().click();
    await vis(page, 'Select trip').click();
    const trips = page.getByText('Trip #1', { exact: true }).locator('visible=true');
    await trips.nth((await trips.count()) - 1).click();
    await vis(page, 'Select stop').click();
    await page.getByText(/#3\s*\W\s*Tarnaka/).locator('visible=true').first().click();
    await vis(page, 'Select pricing plan').click();
    await page.getByText(/^Annual 2026-27/).locator('visible=true').first().click();
    await page.getByPlaceholder('0.00').locator('visible=true').fill('1100');
    await page.getByText('Assign', { exact: true }).locator('visible=true').last().click();
    await toast(page, 'Transport assignment created successfully');
    const stored = await assignmentsOf(api, student.id);
    expect(stored).toHaveLength(1);
    expect(Number(stored[0].fee_per_term)).toBe(1100);
    await expect(page.getByText(/Tarnaka/).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText('Fee: ₹1,100').locator('visible=true').first()).toBeVisible();
  });

  test('TC-TRN-10-E05 student sees My Transport on mobile', async ({ page, api, cleanup }) => {
    test.fail(true, 'UI-TRN-02: the mobile My Transport screen (/transport/student-transport) shows "Route: - Trip #-, Stop: -, NaN/term" for a student who has an assignment, because it reads the API array response as a single object');
    test.setTimeout(240_000);
    const family = await createFamily(cleanup);
    const route = await routeByName(api, 'Route 1 - Kukatpally');
    const trip = list(await api('GET', '/masters/trips/?limit=1000')).find((t) => t.route_id === route.id);
    const stop = (await stopsOf(api, route.id)).find((s) => s.name === 'Kukatpally Bus Stand');
    await assignStudent(api, cleanup, { studentId: family.studentId, tripId: trip.id, stopId: stop.id, fee: 4000 });
    const session = await injectMobile(page, family.admissionNumber, family.studentPassword);
    await page.addInitScript((id) => window.localStorage.setItem('@auth/student_id', id), session.entity_id || family.studentId);
    await page.goto('/transport/student-transport', { timeout: 180_000 });
    await expect(vis(page, 'My Transport')).toBeVisible({ timeout: 60_000 });
    await expect(vis(page, 'Route 1 - Kukatpally', { exact: false })).toBeVisible();
    await expect(vis(page, 'Kukatpally Bus Stand', { exact: false })).toBeVisible();
    await expect(page.getByText(/7:00|07:00/).locator('visible=true').first()).toBeVisible();
    await expect(page.getByText(/4,?000/).locator('visible=true').first()).toBeVisible();
  });
});
