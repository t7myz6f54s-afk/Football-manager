const puppeteer = require('puppeteer');
(async () => {
  const b = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox','--disable-dev-shm-usage','--hide-scrollbars'] });
  const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const wait = ms => new Promise(r => setTimeout(r, ms));
  await p.setViewport({ width: 393, height: 852, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle0' }); await wait(1600);
  await p.screenshot({ path: '/home/user/.shots/v30-01-home.png' });
  await p.evaluate(() => go('table')); await wait(1400);
  await p.screenshot({ path: '/home/user/.shots/v30-02-table.png' });
  const imgs = await p.evaluate(() => {
    const im = [...document.querySelectorAll('img.crest')];
    return { total: im.length, broken: im.filter(i => i.complete && i.naturalWidth === 0).length };
  });
  console.log(JSON.stringify(imgs), 'errors:', errs.join('|') || 'none');
  await b.close();
})();
