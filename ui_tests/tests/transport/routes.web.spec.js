// Transport F01-F05 hub, route types, routes and route stops, web. Routes, stops and vehicles are soft-deleted in cleanup.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { routeByName, stopsOf } = require('./kit');

test.describe('Transport F01-F05 hub, routes, stops (web)', () => {
  test('TC-TRN-01-E01 transport hub lists four sections', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/');
    await page.getByRole('button', { name: 'Transport', exact: true }).first().click();
    await expect(page).toHaveURL(/\/transport\/?$/);
    const main = page.getByRole('main');
    await expect(main.getByRole('heading', { name: 'Transport Dashboard' })).toBeVisible();
    await expect(main.getByText('Manage school transport, routes, vehicles, and student allocations')).toBeVisible();
    await expect(main.getByRole('heading', { name: 'Transport Sections' })).toBeVisible();
    for (const name of ['Routes', 'Vehicles', 'Trips', 'Pricing']) {
      await expect(main.getByRole('heading', { name, exact: true })).toBeVisible();
    }
    await expect(main.getByRole('heading', { name: 'Route Stops' })).toHaveCount(0);
    await expect(main.getByRole('heading', { name: 'Student Transport' })).toHaveCount(0);
  });

  test('TC-TRN-02-E01 route form has no route type or trip type control', async ({ page, signIn, api }) => {
    await signIn('admin');
    await page.goto('/transport/routes');
    await page.getByRole('button', { name: 'Add Route' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Add New Route')).toBeVisible();
    await expect(dialog.getByText(/Route Type/i)).toHaveCount(0);
    await expect(dialog.getByText(/Trip Type/i)).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    const seeded = await routeByName(api, 'Route 1 - Kukatpally');
    expect(seeded.route_type).toBe('Pickup');
  });

  test('TC-TRN-04-E01 create a route with two stops', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Route 3 - Ameerpet');
    await signIn('admin');
    await page.goto('/transport/routes');
    await page.getByRole('button', { name: 'Add Route' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: 'Route Name *' }).fill(name);
    await dialog.getByRole('textbox', { name: 'Starting Point *' }).fill('QA Ameerpet');
    await dialog.getByRole('textbox', { name: 'Ending Point *' }).fill('Demo School Campus');
    await dialog.getByRole('spinbutton', { name: 'Number of Stops' }).fill('2');
    await expect(dialog.getByText('2 stops')).toBeVisible();
    const stopNames = dialog.getByPlaceholder(/stop name/i);
    await stopNames.nth(0).fill('QA Stop A');
    await stopNames.nth(1).fill('QA Stop B');
    await dialog.getByRole('button', { name: 'Add Route' }).click();
    await toast(page, `Route "${name}" created successfully!`);
    const created = await routeByName(api, name);
    expect(created).toBeTruthy();
    cleanup(async () => {
      for (const s of await stopsOf(api, created.id)) await api('DELETE', `/masters/route-stops/${s.id}`);
      await api('DELETE', `/masters/routes/${created.id}`);
    });
    await page.getByPlaceholder('Search...').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText('07:00');
    await expect(row).toContainText('08:30');
    await row.getByRole('button', { name: 'View' }).click();
    await expect(page.getByRole('row').filter({ hasText: 'QA Stop A' })).toContainText('1');
    await expect(page.getByRole('row').filter({ hasText: 'QA Stop B' })).toContainText('2');
  });

  test('TC-TRN-05-E01 add a stop to Route 2', async ({ page, signIn, api, cleanup }) => {
    const stop = unique('QA Stop Nagole');
    await signIn('admin');
    await page.goto('/transport/routes');
    await page.getByRole('combobox', { name: 'Select a route to view stops...' }).click();
    await page.getByText('Route 2 - Uppal', { exact: true }).last().click();
    await page.getByRole('button', { name: 'Add Stop' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('textbox', { name: /Stop Name/ }).fill(stop);
    const number = 40 + Math.floor(Math.random() * 900);
    // doc: the default Stop Number is 5, but a soft-deleted stop keeps its number (unique per route including inactive stops), so repeating the case fails; use an unused number
    await dialog.getByRole('spinbutton', { name: /Stop Number/ }).fill(String(number));
    await dialog.getByRole('spinbutton', { name: /Amount/ }).fill('1400');
    await dialog.getByRole('button', { name: 'Select time' }).first().click();
    await page.getByRole('button', { name: '07', exact: true }).first().click();
    await page.getByRole('button', { name: '50', exact: true }).click();
    await page.getByRole('button', { name: 'AM', exact: true }).click();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await dialog.getByRole('button', { name: 'Add Stop' }).click();
    await toast(page, `Route stop "${stop}" created successfully!`);
    const route = await routeByName(api, 'Route 2 - Uppal');
    const created = (await stopsOf(api, route.id)).find((s) => s.name === stop);
    expect(created).toBeTruthy();
    cleanup(async () => {
      await api('PATCH', `/masters/route-stops/${created.id}`, { body: { number: 100000 + number } });
      await api('DELETE', `/masters/route-stops/${created.id}`);
    });
    const row = page.getByRole('row').filter({ hasText: stop });
    expect(created.number).toBe(number);
    await expect(row.getByRole('cell').first()).toHaveText('5');
    await expect(row).toContainText('₹1,400');
    await expect(row).toContainText('07:50');
  });
});
