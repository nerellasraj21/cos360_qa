// Transport F06-F08 vehicles, trips and pricing, web. Vehicles and pricing are soft-deleted, trips hard-deleted in cleanup.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { list, routeByName, vehicleByName, driverUserId, createVehicle } = require('./kit');

async function pickOption(page, trigger, text) {
  await trigger.click();
  await page.getByText(text, { exact: true }).last().click();
}

test.describe('Transport F06-F08 vehicles, trips, pricing (web)', () => {
  test('TC-TRN-06-E01 add a vehicle', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Bus 3');
    const reg = `QA${Date.now().toString(36).slice(-6).toUpperCase()}`;
    await signIn('admin');
    await page.goto('/transport/vehicles');
    await page.getByRole('button', { name: 'Add Vehicle' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByPlaceholder('Bus 01').fill(name);
    await dialog.getByPlaceholder('KA01AB1234').fill(reg);
    await dialog.getByText('Driving Licence No. *').locator('xpath=following-sibling::input').fill(`QADL${reg}`);
    const writes = [];
    page.on('request', (r) => {
      if (r.url().includes('/masters/vehicles') && ['POST', 'PUT', 'PATCH'].includes(r.method())) writes.push(r.method());
    });
    await dialog.getByRole('button', { name: 'Add Vehicle' }).click();
    await toast(page, 'Vehicle created successfully');
    await toast(page, 'Vehicle updated successfully');
    const created = await vehicleByName(api, name);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/vehicles/${created.id}`));
    expect(writes).toEqual(['POST', 'PUT']);
    await page.getByPlaceholder('Search...').fill(name);
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toContainText('Active');
    await expect(row).toContainText(/0\s*Active/);
  });

  test('TC-TRN-07-E01 add a trip', async ({ page, signIn, api, cleanup }) => {
    const vehicle = await createVehicle(api, cleanup, unique('QA Bus 3'));
    await signIn('admin');
    await page.goto('/transport/trips');
    await page.getByRole('button', { name: 'Add Trip' }).click();
    const dialog = page.getByRole('dialog');
    await pickOption(page, dialog.getByRole('combobox', { name: 'Select Vehicle' }), `${vehicle.name} - ${vehicle.registration_number}`);
    await pickOption(page, dialog.getByRole('combobox', { name: 'Select Route' }), 'Route 2 - Uppal');
    await pickOption(page, dialog.getByRole('combobox', { name: 'Select Driver' }), 'Mohan Singh');
    await expect(dialog.getByRole('spinbutton', { name: 'Trip Number' })).toHaveValue('1');
    await dialog.getByRole('button', { name: 'Add Trip' }).click();
    await toast(page, 'Trip created!');
    const trips = list(await api('GET', '/masters/trips/?limit=1000'));
    const created = trips.find((t) => t.vehicle_id === vehicle.id);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/trips/${created.id}`));
    const row = page.getByRole('row').filter({ hasText: vehicle.name });
    await expect(row).toContainText('Route 2 - Uppal');
    await expect(row).toContainText('Mohan Singh');
    await expect(row).toContainText('1');
  });

  test('TC-TRN-08-E01 add an annual pricing plan', async ({ page, signIn, api, cleanup }) => {
    const vehicle = await createVehicle(api, cleanup, unique('QA Bus 3'));
    const cycle = unique('QA Annual 2026-27');
    await signIn('admin');
    await page.goto('/transport/pricing');
    await page.getByRole('button', { name: 'Add Pricing' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox').nth(0).click();
    await page.getByRole('option', { name: new RegExp(vehicle.name) }).click();
    await dialog.getByRole('combobox').nth(1).click();
    await page.getByRole('option', { name: 'Route 2 - Uppal' }).click();
    await expect(dialog.getByText('Annual', { exact: true })).toBeVisible();
    await dialog.getByRole('textbox', { name: 'Cycle Name' }).fill(cycle);
    await dialog.getByRole('spinbutton', { name: 'Amount (₹)' }).fill('13000');
    await dialog.getByRole('textbox', { name: 'Start Date' }).fill('2026-06-01');
    await dialog.getByRole('textbox', { name: 'End Date' }).fill('2027-03-31');
    await dialog.getByRole('button', { name: 'Add Pricing' }).click();
    await toast(page, `Pricing "${cycle}" created successfully!`);
    const plans = list(await api('GET', '/masters/transport-pricing/?limit=1000'));
    const created = plans.find((p) => p.cycle_name === cycle);
    expect(created).toBeTruthy();
    cleanup(() => api('DELETE', `/masters/transport-pricing/${created.id}`));
    const route = await routeByName(api, 'Route 2 - Uppal');
    expect(created.route_id).toBe(route.id);
    const row = page.getByRole('row').filter({ hasText: cycle });
    await expect(row).toContainText(vehicle.name);
    await expect(row).toContainText('Route 2 - Uppal');
    await expect(row).toContainText('Annual');
    await expect(row).toContainText('₹13,000');
    await expect(row).toContainText('Active');
  });
});
