// Exam F11 Mark entry, web (P1). Own QA class, students and exam.
const fs = require('fs');
const path = require('path');
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

const XLSX = require(path.resolve(__dirname, '..', '..', '..', '..', 'COS360_Full_App', 'web', 'node_modules', 'xlsx'));

async function setup(api, cleanup) {
  const klass = await kit.createQaClass(api, cleanup);
  const students = await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
  const exam = await kit.createExam(api, cleanup, klass);
  return { klass, students, exam };
}

async function openGrid(page, exam) {
  await page.goto('/exam/marks');
  await page.getByRole('row').filter({ hasText: exam.name }).getByRole('button', { name: 'Enter Marks' }).click();
  await expect(page).toHaveURL(/\/summary$/);
  await expect(page.getByText('Subject', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Enter Marks' }).click();
  await expect(page.getByText(/Mark Entry - /)).toBeVisible();
}

function studentRow(page, student) {
  return page.getByRole('row').filter({ hasText: student.name });
}

test.describe('Exam F11 mark entry (web)', () => {
  test('TC-EXM-11-E01 teacher enters and saves marks for one student', async ({ page, signIn, api, cleanup }) => {
    const { students, exam } = await setup(api, cleanup);
    await signIn('teacher');
    await openGrid(page, exam);
    const row = studentRow(page, students[0]);
    const inputs = row.getByRole('spinbutton');
    await inputs.nth(0).fill('62');
    await inputs.nth(1).fill('18');
    await inputs.nth(2).fill('70');
    await inputs.nth(3).fill('90');
    await expect(page.getByText('Unsaved changes for 1 student.')).toBeVisible();
    await expect(row).toContainText('80');
    await expect(row).toContainText('240');
    await page.getByRole('button', { name: 'Save Marks' }).click();
    await toast(page, 'Marks saved successfully');
    await page.reload();
    const again = studentRow(page, students[0]);
    await expect(again.getByRole('spinbutton').nth(0)).toHaveValue('62');
    await expect(again.getByRole('spinbutton').nth(1)).toHaveValue('18');
    await expect(again.getByRole('spinbutton').nth(2)).toHaveValue('70');
    await expect(again.getByRole('spinbutton').nth(3)).toHaveValue('90');
    await expect(again).toContainText('240');
  });
  test('TC-EXM-11-E05 import marks from an Excel file', async ({ page, signIn, api, cleanup }, testInfo) => {
    const { students, exam } = await setup(api, cleanup);
    await signIn('teacher');
    await openGrid(page, exam);
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Template' }).click()]);
    const template = testInfo.outputPath('template.xlsx');
    await download.saveAs(template);
    const wb = XLSX.read(fs.readFileSync(template), { type: 'buffer' });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '' });
    const col = rows[0].findIndex((h) => String(h).startsWith('Mathematics Written'));
    expect(col).toBeGreaterThan(0);
    for (const r of rows.slice(1)) {
      if ([students[1].admissionNumber, students[2].admissionNumber].includes(String(r[0]).trim())) r[col] = 70;
    }
    wb.Sheets[wb.SheetNames[0]] = XLSX.utils.aoa_to_sheet(rows);
    const filled = testInfo.outputPath('filled.xlsx');
    XLSX.writeFile(wb, filled);
    await page.getByRole('button', { name: 'Upload Excel' }).click();
    const dialog = page.getByRole('dialog');
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), dialog.getByRole('button', { name: 'Browse File' }).click()]);
    await chooser.setFiles(filled);
    await dialog.getByRole('button', { name: 'Upload', exact: true }).click();
    // doc: the toast counts every template row matched by Adm# (3 here, including the student with no marks), not only the rows that carry marks
    await toast(page, 'Imported 3 student rows');
    await expect(page.getByText(/Unsaved changes for 2 students/)).toBeVisible();
    await expect(studentRow(page, students[1]).getByRole('spinbutton').first()).toHaveValue('70');
    await expect(studentRow(page, students[2]).getByRole('spinbutton').first()).toHaveValue('70');
    await page.getByRole('button', { name: 'Save Marks' }).click();
    await toast(page, 'Marks saved successfully');
    await page.reload();
    await expect(studentRow(page, students[1]).getByRole('spinbutton').first()).toHaveValue('70');
    await expect(studentRow(page, students[2]).getByRole('spinbutton').first()).toHaveValue('70');
    await expect(studentRow(page, students[0]).getByRole('spinbutton').first()).toHaveValue('');
  });
});
