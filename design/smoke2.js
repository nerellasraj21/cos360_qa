const { chromium } = require('../ui_tests/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text().slice(0, 200)); });
  await p.goto('file:///' + process.argv[2].split(String.fromCharCode(92)).join('/'));
  await p.waitForSelector('.roombar');
  const keys = await p.evaluate(() => { document.querySelectorAll('[data-act=fold]').forEach(x => x.click()); return null; });
  let n = 0, leaves = 0;
  const all = [];
  for (let pass = 0; pass < 3; pass++) {
    await p.evaluate(() => { document.querySelectorAll('.grp:not(.open)>[data-act=fold]').forEach(x => x.click()); });
  }
  const list = await p.$$eval('[data-act=leaf]', e => e.map(x => x.dataset.key));
  for (const k of list) {
    await p.evaluate(key => { const els = document.querySelectorAll('[data-act=leaf]'); for (const x of els) if (x.dataset.key === key) { x.click(); return; } }, k);
    const t = await p.evaluate(() => document.querySelector('.title') ? document.querySelector('.title').innerText : '(bare)');
    const len = await p.evaluate(() => document.getElementById('body').innerText.length);
    leaves++;
    if (len < 20) errs.push('EMPTY ' + k);
    await p.evaluate(() => { document.querySelectorAll('.grp:not(.open)>[data-act=fold]').forEach(x => x.click()); });
  }
  console.log('leaves', leaves, 'errors', errs.length); console.log(errs.slice(0, 15).join('\n'));
  await b.close();
})();
