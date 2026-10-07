// Communication F02 targeting, F03 compose and send, F04 quick send, F05/F06 logs, F08 no triggers (web).
// Every real send goes to ONE QA staff member whose phone is a non-routable number; class-level sends are never pressed.
const { test, expect, unique, toast } = require('../../helpers/fixtures');
const { createStaff } = require('../../helpers/staffkit');
const { createTemplate, ensureStaffRecruiting } = require('../../helpers/comkit');

function qaPhone() {
  return `0000${Math.floor(Math.random() * 900000 + 100000)}`;
}

async function qaStaff(api, cleanup, label = 'QA Com') {
  const name = unique(label);
  const staff = await createStaff(api, cleanup, { first_name: name, last_name: 'Zed', phone: qaPhone() });
  return { staff, name: `${name} Zed`, first: name };
}

function main(page) {
  return page.getByRole('main');
}

async function pickStaff(page, first) {
  await main(page).getByRole('button', { name: 'Staff', exact: true }).click();
  await main(page).locator('input[id^="react-select"]').fill(first);
  await page.getByRole('option', { name: new RegExp(first) }).click();
  await page.keyboard.press('Escape');
  await expect(main(page).getByText('1 staff selected')).toBeVisible();
}

test.describe('Communication compose, logs and quick send (web)', () => {
  test('TC-COM-02-E01 class and section select the students', async ({ page, signIn }) => {
    await signIn('admin');
    await page.goto('/communication/compose');
    await main(page).getByRole('button', { name: 'Parents', exact: true }).click();
    await main(page).getByRole('combobox', { name: 'Class' }).click();
    await page.getByRole('option', { name: 'Class 1', exact: true }).click();
    await main(page).getByRole('combobox', { name: 'Section' }).click();
    await page.getByRole('option', { name: '1-A', exact: true }).click();
    await expect(main(page).locator('span', { hasText: /^Students$/ })).toBeVisible();
    await expect(main(page).getByText(/^(\d+)\/\1$/)).toBeVisible();
    await expect(main(page).getByText('Kavya Verma')).toBeVisible();
    await expect(main(page).getByText('Saanvi Iyer')).toBeVisible();
    await expect(main(page)).toContainText(/\d+\s*recipients/);
    const boxes = main(page).getByRole('checkbox');
    const total = await boxes.count();
    for (let i = 0; i < total; i += 1) {
      await expect(boxes.nth(i)).toBeChecked();
    }
  });

  test('TC-COM-03-E01 class send preview (Send Now is not pressed)', async ({ page, signIn, api, cleanup }) => {
    const name = unique('QA Notice SMS');
    await createTemplate(api, cleanup, { name, body: 'Dear {{name}}, this is a QA notice.' });
    await signIn('admin');
    await page.goto('/communication/compose');
    await main(page).getByRole('button', { name: 'Parents', exact: true }).click();
    await main(page).getByRole('combobox', { name: 'Class' }).click();
    await page.getByRole('option', { name: 'Class 1', exact: true }).click();
    await main(page).getByRole('combobox', { name: 'Section' }).click();
    await page.getByRole('option', { name: '1-A', exact: true }).click();
    await main(page).getByRole('button', { name: 'SMS', exact: true }).click();
    await main(page).locator('select').last().selectOption({ label: name });
    await expect(main(page)).toContainText('Dear [name], this is a QA notice.');
    await expect(main(page)).toContainText(/\d+ chars\s*.\s*1 SMS credit\s*.\s*Sender: COS360/);
    await expect(main(page).getByRole('button', { name: 'Send Now' })).toBeEnabled();
  });

  test('TC-COM-03-E07 send to one staff member', async ({ page, signIn, api, cleanup }) => {
    test.skip(true, 'environment: a real send dispatches to a Celery broker host that does not resolve (your-production-redis-server) and the shared API stops answering for minutes; not run to protect other test runs');
    const { first } = await qaStaff(api, cleanup);
    const name = unique('QA Notice SMS');
    await createTemplate(api, cleanup, { name, body: 'Dear {{name}}, this is a QA notice.' });
    await signIn('admin');
    await page.goto('/communication/compose');
    await pickStaff(page, first);
    await main(page).getByRole('button', { name: 'SMS', exact: true }).click();
    await main(page).locator('select').last().selectOption({ label: name });
    await expect(main(page)).toContainText(/1\s*recipients/);
    await main(page).getByRole('button', { name: 'Send Now' }).click();
    await toast(page, '1 messages queued successfully');
    await expect(page).toHaveURL(/\/communication\/logs/);
  });

  test('TC-COM-04-E01 staff row opens the Send Message dialog', async ({ page, signIn, api, cleanup }) => {
    const { first } = await qaStaff(api, cleanup);
    await ensureStaffRecruiting(api);
    await signIn('admin');
    await page.goto('/staff/enrollment');
    await page.getByPlaceholder('Search staff...').fill(first);
    await page.getByRole('row').filter({ hasText: first }).getByRole('button', { name: 'Send Welcome/Recruiting Message' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('Send Message');
    await expect(dialog).toContainText(`To: ${first}`);
    for (const channel of ['SMS', 'WhatsApp', 'Email']) {
      await expect(dialog.getByRole('button', { name: channel, exact: true })).toBeVisible();
    }
    await expect(dialog.locator('select')).toHaveValue(/.+/);
    await expect(dialog.locator('select option:checked')).toHaveText('Staff Recruiting');
    await expect(dialog.getByText('Preview')).toBeVisible();
    await expect(dialog).toContainText('[name]');
    await expect(dialog.getByRole('button', { name: 'Send Now' })).toBeVisible();
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).toBeHidden();
  });

  test('TC-COM-04-E03 send the recruiting message to one staff member', async ({ page, signIn, api, cleanup }) => {
    test.skip(true, 'environment: a real send dispatches to a Celery broker host that does not resolve (your-production-redis-server) and the shared API stops answering for minutes; not run to protect other test runs');
    const { first } = await qaStaff(api, cleanup);
    await ensureStaffRecruiting(api);
    await signIn('admin');
    await page.goto('/staff/enrollment');
    await page.getByPlaceholder('Search staff...').fill(first);
    await page.getByRole('row').filter({ hasText: first }).getByRole('button', { name: 'Send Welcome/Recruiting Message' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Send Now' }).click();
    await toast(page, '1 messages queued successfully');
    await expect(dialog).toBeHidden();
  });

  test('TC-COM-05-E01 a queued send leaves no log row', async ({ page, signIn, api, cleanup }) => {
    test.skip(true, 'environment: a real send dispatches to a Celery broker host that does not resolve (your-production-redis-server) and the shared API stops answering for minutes; not run to protect other test runs');
    const { staff, first } = await qaStaff(api, cleanup);
    const tpl = await createTemplate(api, cleanup, { name: unique('QA Notice SMS'), body: 'Dear {{name}}, this is a QA notice.' });
    const sent = await api('POST', '/communication/send', { body: { template_id: tpl.id, target_type: 'multiple_staff', target_ref: { staff_ids: [staff.id] }, variables: {} } });
    expect(sent.status).toBe(200);
    expect(sent.data.queued_count).toBe(1);
    await signIn('admin');
    await page.goto('/communication/logs');
    await expect(page.getByText(/No logs found\.|Showing 1/).first()).toBeVisible();
    await expect(page.getByText(first)).toHaveCount(0);
  });

  test('TC-COM-06-E01 failed log list and TC-COM-06-E04 detail', async ({ page, signIn, api, cleanup }) => {
    const { staff, name } = await qaStaff(api, cleanup);
    const tpl = await createTemplate(api, cleanup, { name: unique('QA Broken SMS'), body: 'Hi {% if %}' });
    const sent = await api('POST', '/communication/send', { body: { template_id: tpl.id, target_type: 'multiple_staff', target_ref: { staff_ids: [staff.id] }, variables: {} } });
    expect(sent.status).toBe(200);
    await signIn('admin');
    await page.goto('/communication/logs');
    for (const header of ['Recipient', 'Channel', 'Status', 'Target Group', 'Triggered By', 'Date/Time', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header, exact: true })).toBeVisible();
    }
    const row = page.getByRole('row').filter({ hasText: name });
    await expect(row).toBeVisible();
    await expect(row).toContainText('SMS');
    await expect(row).toContainText('Failed');
    await expect(row).toContainText('multiple staff');
    await expect(page.getByText(/Showing 1.\d+ of \d+/)).toBeVisible();
    await row.getByRole('button', { name: `View log for ${name}` }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toContainText('Notification Detail');
    for (const label of ['Recipient', 'Channel', 'Phone', 'Email', 'Status', 'Provider ID', 'Triggered By', 'Target Group', 'Sent At', 'Error']) {
      await expect(dialog.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(dialog).toContainText('Failed');
    await expect(dialog).toContainText(name);
    await expect(dialog).toContainText(/Expected an expression/);
    await expect(dialog.getByRole('button', { name: 'Close' }).last()).toBeVisible();
  });

  test('TC-COM-08-E01 no attendance summary or interview call control on staff pages', async ({ page, signIn }) => {
    await signIn('admin');
    for (const route of ['/staff/enrollment', '/staff/attendance']) {
      await page.goto(route);
      await expect(page.getByRole('main')).toBeVisible();
      await expect(page.getByRole('button', { name: /interview/i })).toHaveCount(0);
      await expect(page.getByRole('button', { name: /attendance summary|send summary/i })).toHaveCount(0);
    }
  });
});
