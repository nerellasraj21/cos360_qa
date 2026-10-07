// Exam F19 Notifications, web (P1). The endpoint only counts and queues; nothing is delivered.
const { test, expect, toast } = require('../../helpers/fixtures');
const kit = require('./_kit');

test.describe.configure({ timeout: 120_000 });

async function ensureSelected(button, wanted) {
  const selected = await button.evaluate((el) => el.className.includes('bg-primary'));
  if (selected !== wanted) await button.click();
}

test.describe('Exam F19 notifications (web)', () => {
  test('TC-EXM-19-E01 queue a push notification to students', async ({ page, signIn, api, cleanup }) => {
    const klass = await kit.createQaClass(api, cleanup);
    await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo', 'Charlie']);
    const exam = await kit.createExam(api, cleanup, klass);
    await signIn('admin');
    await page.goto(`/exam/exams/${exam.id}/notify`);
    await expect(page.getByText('Send exam-related notifications')).toBeVisible();
    await page.getByRole('main').getByRole('button', { name: 'Students', exact: true }).click();
    await ensureSelected(page.getByRole('button', { name: 'SMS', exact: true }), false);
    await ensureSelected(page.getByRole('button', { name: 'Email', exact: true }), false);
    await ensureSelected(page.getByRole('button', { name: 'Push Notification', exact: true }), true);
    await page.getByPlaceholder('Enter your notification message...').fill('QA exam starts Monday');
    await page.getByRole('button', { name: 'Send Notification' }).click();
    await toast(page, '3 notification(s) queued');
    await expect(page.getByPlaceholder('Enter your notification message...')).toHaveValue('');
  });
});
