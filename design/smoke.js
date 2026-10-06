const { chromium } = require('../ui_tests/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text().slice(0, 200)); });
  await p.goto('file:///' + process.argv[2].split(String.fromCharCode(92)).join('/'));
  await p.waitForSelector('.roombar');
  let n = 0;
  const rooms = await p.$$eval('.rooms .room', e => e.map(x => x.dataset.id));
  rooms.push('setup');
  for (const r of rooms) {
    await p.evaluate(id => document.querySelector(`[data-act=room][data-id=${id}]`).click(), r);
    const secs = await p.$$eval('.rail a.sec', e => e.map(x => x.dataset.id));
    for (const s of secs) {
      await p.evaluate(id => document.querySelector(`.rail a.sec[data-id=${id}]`).click(), s);
      const tabs = await p.$$eval('.tabbar button', e => e.map(x => x.dataset.tab));
      for (const t of (tabs.length ? tabs : [null])) {
        if (t) await p.evaluate(id => document.querySelector(`.tabbar button[data-tab="${id}"]`).click(), t);
        const len = await p.evaluate(() => document.getElementById('body').innerText.length);
        n++;
        if (len < 20) errs.push(`EMPTY ${r}.${s}.${t}`);
        if (/undefined|NaN|\[object/.test(await p.evaluate(() => document.getElementById('body').innerText))) errs.push(`BADTEXT ${r}.${s}.${t}`);
      }
    }
  }
  console.log('views', n, 'errors', errs.length);
  console.log(errs.slice(0, 25).join('\n'));
  await b.close();
})();
