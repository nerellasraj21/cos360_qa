// Exam F06 Create exam, mobile (P1). Own QA class.
const { test, expect, unique } = require('../../helpers/fixtures');
const kit = require('./_kit');

const { vis, text, openHub, tile } = kit.mobile;

async function choose(page, placeholder, option) {
  await text(page, placeholder).first().click();
  await text(page, option).last().click();
}

test.describe('Exam F06 create exam (mobile)', () => {
  test('TC-EXM-06-E19 create an exam on mobile', async ({ page, signIn, api, cleanup }) => {
    test.setTimeout(90_000);
    const klass = await kit.createQaClass(api, cleanup);
    const name = unique('QA Mobile FA1');
    cleanup(async () => {
      const list = kit.rows(await api('GET', '/exams'));
      for (const e of list.filter((x) => x.exam_name === name)) await api('DELETE', `/exams/${e.id}`);
    });
    await signIn('admin');
    await openHub(page);
    await text(page, 'Create Exam').first().click();
    await vis(page.getByPlaceholder('FA1 2024-25')).fill(name);
    await choose(page, 'CBSE', 'State');
    await vis(page.getByPlaceholder('FA1', { exact: true })).fill('FA1');
    await choose(page, '— None —', 'Standard Percentage Grading');
    await text(page, 'Class & Sections', { exact: false }).first().click();
    await page.waitForTimeout(1000);
    await text(page, 'Type to search and select class-sections...').first().click();
    await page.keyboard.type(klass.name);
    await page.waitForTimeout(1000);
    await text(page, klass.dash).first().click();
    await page.mouse.click(195, 650);
    await text(page, 'Next: Subject Config', { exact: false }).first().click();
    await page.waitForTimeout(1500);
    for (const [subject, comps] of [['Mathematics', [['Written', 80], ['Oral', 20]]], ['English', [['Written', 100]]], ['Environmental Studies', [['Written', 100]]]]) {
      await text(page, subject).first().click();
      for (let i = 0; i < comps.length; i += 1) {
        await text(page, 'Add Component').first().click();
        await vis(page.getByPlaceholder('e.g. Written')).nth(i).fill(comps[i][0]);
        await vis(page.getByPlaceholder('—', { exact: true })).nth(1 + 2 * i).fill(String(comps[i][1]));
      }
      await text(page, subject).first().click();
    }
    await text(page, 'Create Exam').last().click();
    await expect(text(page, 'Exam Created').first()).toBeVisible({ timeout: 30_000 });
    const found = kit.rows(await api('GET', '/exams')).find((x) => x.exam_name === name);
    expect(found).toBeTruthy();
    const cfgs = kit.rows(await api('GET', `/exams/${found.id}/subject-configs`));
    expect(cfgs).toHaveLength(3);
    const math = cfgs.find((c) => c.subject_id === klass.subjectIds.Mathematics);
    expect(math.components.map((c) => Number(c.max_marks)).sort((x, y) => x - y)).toEqual([20, 80]);
  });
});
