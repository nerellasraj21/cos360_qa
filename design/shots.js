const { chromium } = require('../ui_tests/node_modules/playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const url = 'file:///' + process.argv[2].split(String.fromCharCode(92)).join('/');
  const out = process.argv[3];
  const go = async (r, s, t, name, w, h) => {
    if (w) await p.setViewportSize({ width: w, height: h });
    await p.goto(url + '?x=' + name + '#' + r + '.' + s); await p.waitForSelector('.roombar');
    if (t) await p.evaluate(id => document.querySelector(`.tabbar button[data-tab="${id}"]`).click(), t);
    await p.waitForTimeout(300);
    await p.screenshot({ path: out + '/' + name + '.png' });
  };
  await go('today', 'today', null, 'today');
  await go('people', 'students', 'create', 'admit');
  await go('people', 'students', 'list', 'students');
  await go('accounts', 'counter', null, 'counter');
  await go('classes', 'attendance', null, 'attendance');
  await go('exams', 'marks', null, 'marks');
  await go('exams', 'exams', 'create', 'examcreate');
  await go('today', 'today', null, 'mobile', 400, 860);
  await go('accounts', 'counter', null, 'mobile_counter', 400, 860);
  await b.close();
})();
