// TTC F06-F10 section timetable, web (P1). Baseline: qa_manual seeded timetables for 1-A, 1-B, 2-A, 2-B; 3-A and 3-B empty.
const fs = require('fs');
const { test, expect, toast } = require('../../helpers/fixtures');
const { sectionId, subjectIds, putTimetable, subjectRow, getTimetable, clearTimetable } = require('./ttc-kit');

async function pickClassSection(page, cls, section) {
  await page.getByRole('combobox').nth(1).click();
  await page.getByRole('option', { name: cls, exact: true }).click();
  await page.getByRole('combobox').nth(2).click();
  const loaded = page.waitForResponse((r) => r.url().includes('/timetable/frontend/'));
  await page.getByRole('option', { name: section, exact: true }).click();
  await loaded;
  await page.waitForTimeout(700);
}

async function openSection(page, signIn, cls, section) {
  await signIn('admin');
  await page.goto('/TimeTable');
  await expect(page.getByText('Time Table Management')).toBeVisible();
  await expect(page.getByRole('combobox').nth(1)).toBeVisible();
  await page.waitForTimeout(800);
  await pickClassSection(page, cls, section);
}

async function setTime(page, trigger, hour, minute, meridiem) {
  await trigger.click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: hour, exact: true }).first().click();
  await dialog.getByRole('button', { name: minute, exact: true }).last().click();
  await dialog.getByRole('button', { name: meridiem, exact: true }).click();
  await dialog.getByRole('button', { name: 'Done' }).click();
  await expect(dialog).toBeHidden();
}

async function chooseSubject(page, cell, subject) {
  await cell.click();
  await page.getByRole('option', { name: subject, exact: true }).click();
}

function dataRows(page) {
  return page.getByRole('row').filter({ hasNot: page.getByRole('columnheader') });
}

test.describe('TTC F06-F10 timetable (web)', () => {
  test.describe.configure({ mode: 'serial' });

  test('TC-TTC-06-E03 view the seeded timetable of 1-A', async ({ page, signIn }) => {
    await openSection(page, signIn, 'Class 1', '1-A');
    await expect(page.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    for (const d of ['Time', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']) {
      await expect(page.getByRole('columnheader', { name: d, exact: true })).toBeVisible();
    }
    await expect(page.getByRole('columnheader', { name: 'Saturday' })).toHaveCount(0);
    await expect(dataRows(page)).toHaveCount(8);
    await expect(page.getByText('9:00 AM - 10:00 AM')).toBeVisible();
    const snacks = page.getByRole('row').filter({ hasText: '10:45 AM - 11:00 AM' });
    await expect(snacks).toContainText('Snacks');
    expect(await snacks.getByRole('cell').count()).toBe(2);
    const lunch = page.getByRole('row').filter({ hasText: '12:30 PM - 1:15 PM' });
    await expect(lunch).toContainText('Lunch');
    const first = page.getByRole('row').filter({ hasText: '9:00 AM - 10:00 AM' });
    await expect(first).toContainText('English');
  });

  test('TC-TTC-06-E05 section without a timetable opens in edit mode', async ({ page, signIn, api }) => {
    await clearTimetable(api, await sectionId(api, 'Class 3 - 3-B'));
    await openSection(page, signIn, 'Class 3', '3-B');
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
    await expect(page.getByText('Include Saturday')).toBeVisible();
    for (const d of ['Time', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: d, exact: true })).toBeVisible();
    }
    await expect(page.getByRole('button', { name: '+ Add Subject Row' })).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add Special Row' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Repeat All for Week' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Repeat One Subject' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Export' })).toHaveCount(0);
  });

  test('TC-TTC-07-E01 build and save a new timetable', async ({ page, signIn, api, cleanup }) => {
    const sid = await sectionId(api, 'Class 3 - 3-A');
    await clearTimetable(api, sid);
    cleanup(() => clearTimetable(api, sid));
    const ids = await subjectIds(api);
    await openSection(page, signIn, 'Class 3', '3-A');
    await page.getByRole('button', { name: '+ Add Subject Row' }).click();
    await setTime(page, page.getByRole('button', { name: 'Select time' }).first(), '09', '00', 'AM');
    await setTime(page, page.getByRole('button', { name: 'Select time' }).first(), '09', '45', 'AM');
    const row = page.getByRole('row').nth(1);
    for (let d = 0; d < 5; d++) await chooseSubject(page, row.getByRole('combobox').nth(d), 'Mathematics');
    await page.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Timetable saved successfully');
    await expect(page.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Export' })).toBeVisible();
    await expect(page.getByText('9:00 AM - 9:45 AM')).toBeVisible();
    await expect(page.getByRole('cell', { name: 'Mathematics' })).toHaveCount(5);
    const saved = await getTimetable(api, sid);
    expect(saved.timetable_data).toHaveLength(1);
    expect(saved.timetable_data[0].time).toEqual({ from: '09:00', to: '09:45' });
    expect(Object.values(saved.timetable_data[0].subjects)).toEqual(Array(5).fill(ids.Mathematics));
  });

  test('TC-TTC-07-E03 replace one cell and save', async ({ page, signIn, api, cleanup }) => {
    const sid = await sectionId(api, 'Class 3 - 3-A');
    const ids = await subjectIds(api);
    await putTimetable(api, cleanup, sid, [subjectRow('09:00', '09:45', ids.Mathematics)]);
    await openSection(page, signIn, 'Class 3', '3-A');
    await page.getByRole('button', { name: 'Edit' }).click();
    const row = page.getByRole('row').nth(1);
    await chooseSubject(page, row.getByRole('combobox').nth(2), 'English');
    await page.getByRole('button', { name: 'Save' }).click();
    await toast(page, 'Timetable saved successfully');
    await page.reload();
    await pickClassSection(page, 'Class 3', '3-A');
    await expect(page.getByRole('button', { name: 'Edit' })).toBeVisible();
    const view = page.getByRole('row').filter({ hasText: '9:00 AM - 9:45 AM' });
    await expect(view).toContainText('English');
    const saved = await getTimetable(api, sid);
    expect(saved.timetable_data[0].subjects.Wednesday).toBe(ids.English);
    expect(saved.timetable_data[0].subjects.Monday).toBe(ids.Mathematics);
  });

  test('TC-TTC-08-E09 repeat Monday for the week', async ({ page, signIn, api, cleanup }) => {
    const sid = await sectionId(api, 'Class 3 - 3-A');
    const ids = await subjectIds(api);
    await putTimetable(api, cleanup, sid, [subjectRow('09:00', '09:45', ids.Mathematics)]);
    await openSection(page, signIn, 'Class 3', '3-A');
    await page.getByRole('button', { name: 'Edit' }).click();
    await page.getByRole('button', { name: '+ Add Subject Row' }).click();
    await setTime(page, page.getByRole('button', { name: 'Select time' }).first(), '10', '00', 'AM');
    await setTime(page, page.getByRole('button', { name: 'Select time' }).first(), '10', '45', 'AM');
    await chooseSubject(page, page.getByRole('row').nth(2).getByRole('combobox').nth(0), 'English');
    await page.getByRole('button', { name: '+ Add Subject Row' }).click();
    await setTime(page, page.getByRole('button', { name: 'Select time' }).first(), '11', '00', 'AM');
    await setTime(page, page.getByRole('button', { name: 'Select time' }).first(), '11', '45', 'AM');
    await chooseSubject(page, page.getByRole('row').nth(3).getByRole('combobox').nth(0), 'Hindi');
    await page.getByRole('button', { name: 'Repeat All for Week' }).click();
    const dialog = page.getByRole('dialog');
    // doc: "Copy from day" is already set to Monday when the dialog opens, and its list is clipped by the dialog footer; the case should say "Leave Monday in Copy from day"
    await expect(dialog.getByRole('button', { name: 'Monday' })).toBeVisible();
    await dialog.getByRole('button', { name: 'Apply to All Days' }).click();
    await toast(page, "Monday's schedule applied to all days");
    const expected = ['Mathematics', 'English', 'Hindi'];
    for (let r = 0; r < 3; r++) {
      const row = page.getByRole('row').nth(r + 1);
      await expect(row.getByText(expected[r], { exact: true })).toHaveCount(5);
    }
  });

  test('TC-TTC-10-E01 export seeded timetable as CSV', async ({ page, signIn }) => {
    await openSection(page, signIn, 'Class 1', '1-A');
    await page.getByRole('button', { name: 'Export' }).click();
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByText('Save as CSV').click(),
    ]);
    expect(download.suggestedFilename()).toBe('Timetable - Class 1 - 1-A.csv');
    const text = fs.readFileSync(await download.path(), 'utf8').replace(/^﻿/, '');
    const lines = text.trim().split(/\r?\n/);
    expect(lines[0]).toBe('"Time","Monday","Tuesday","Wednesday","Thursday","Friday"');
    expect(lines).toHaveLength(9);
    const snacks = lines.find((l) => l.includes('10:45 AM - 11:00 AM'));
    expect(snacks).toBe('"10:45 AM - 11:00 AM","Snacks","Snacks","Snacks","Snacks","Snacks"');
    const lunch = lines.find((l) => l.includes('12:30 PM - 1:15 PM'));
    expect(lunch).toContain('"Lunch","Lunch","Lunch","Lunch","Lunch"');
    for (const l of lines) expect(l.startsWith('"') && l.endsWith('"')).toBe(true);
  });
});
