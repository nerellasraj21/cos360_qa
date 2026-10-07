// Exam F19 Notifications, mobile (P1). Nothing is delivered (queue stub).
const { test, expect } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { text, vis, openHub, tile } = kit.mobile;

test.describe('Exam F19 notifications (mobile)', () => {
  test('TC-EXM-19-E05 queue a custom push notification', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(180_000);
    const klass = await kit.createQaClass(api, cleanup);
    await kit.createStudents(api, cleanup, klass, ['Alpha', 'Bravo']);
    const exam = await kit.createExam(api, cleanup, klass);
    await signIn('admin');
    await openHub(page);
    await tile(page, 'Exams');
    await text(page, exam.name).first().click({ timeout: 60_000 });
    await text(page, 'Send Exam Notification').first().click({ timeout: 60_000 });
    await expect(text(page, 'Notification Type *').first()).toBeVisible({ timeout: 60_000 });
    await text(page, 'Custom').first().click();
    await vis(page.getByPlaceholder('Enter the notification message...')).fill('QA exam starts Monday');
    await text(page, 'Both').first().click();
    await text(page, 'Send Notification').first().click({ timeout: 20_000 });
    await expect(text(page, 'Notifications Queued').first()).toBeVisible({ timeout: 30_000 });
    await expect(text(page, /notification\(s\) queued/, { exact: false }).first()).toBeVisible();
  });
});
