// Exam F14 Hall ticket download, web (P1). Seeded exam, read only.
const fs = require('fs');
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe('Exam F14 hall ticket download (web)', () => {
  test('TC-EXM-14-E03 download one seeded hall ticket as PDF', async ({ page, signIn, api }, testInfo) => {
    test.fail(true, 'UI-EXM-04: the hall ticket Download page is unreachable on web; the Download button changes the URL to /exam/hall-tickets/<id>/download but the eligibility page stays (route $examId.tsx renders no Outlet)');
    const list = kit.rows(await api('GET', '/exams'));
    const id = list.find((e) => e.exam_name === 'Half Yearly Examination 2026').id;
    await signIn('admin');
    await page.goto('/exam/hall-tickets');
    await page.getByRole('row').filter({ hasText: 'Half Yearly Examination 2026' }).getByRole('button', { name: 'Manage' }).click();
    await expect(page.getByText('Hall Tickets - Half Yearly Examination 2026')).toBeVisible();
    await page.getByRole('button', { name: 'Download', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/exam/hall-tickets/${id}/download`));
    await expect(page.getByText('Download Hall Tickets - Half Yearly Examination 2026')).toBeVisible();
    const row = page.getByRole('row').filter({ hasText: 'Karthik Reddy' });
    await expect(row).toBeVisible();
    const [download] = await Promise.all([page.waitForEvent('download'), row.getByRole('button', { name: 'PDF' }).click()]);
    expect(download.suggestedFilename()).toBe('hall-ticket-001.pdf');
    await toast(page, 'Downloaded');
    const file = testInfo.outputPath('hall-ticket.pdf');
    await download.saveAs(file);
    const bytes = fs.readFileSync(file);
    expect(bytes.subarray(0, 5).toString()).toBe('%PDF-');
    expect(bytes.length).toBeGreaterThan(1000);
  });
});
