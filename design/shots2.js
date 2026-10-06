const { chromium } = require('../ui_tests/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const url = 'file:///' + process.argv[2].split(String.fromCharCode(92)).join('/'), out = process.argv[3];
  await p.goto(url);
  await p.waitForSelector('.roombar');
  const leaf = k => p.evaluate(key => { for (const x of document.querySelectorAll('[data-act=leaf]')) if (x.dataset.key === key) x.click(); }, k);
  await p.evaluate(() => { for (const x of document.querySelectorAll('[data-act=fold]')) if (x.dataset.key === 'Fee') x.click(); });
  await leaf('Fee/Collection/Fee Collection');
  await p.waitForTimeout(200);
  await p.screenshot({ path: out + '/menu_desktop.png' });
  await p.setViewportSize({ width: 400, height: 860 });
  await p.evaluate(() => document.querySelector('.hamb').click());
  await p.waitForTimeout(400);
  await p.screenshot({ path: out + '/menu_mobile.png' });
  await b.close();
})();
