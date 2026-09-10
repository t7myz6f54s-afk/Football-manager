const puppeteer = require('puppeteer');
(async () => {
  const b = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox','--disable-dev-shm-usage','--hide-scrollbars'] });
  const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const wait = ms => new Promise(r => setTimeout(r, ms));
  await p.setViewport({ width: 393, height: 852, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle0' }); await wait(1400);
  await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight));  await wait(400);
  const y = await p.evaluate(() => { const el = document.querySelector('.god'); if (el) { el.scrollIntoView(); return true; } return false; });
  await wait(400);
  await p.screenshot({ path: '/home/user/.shots/v32-01-god.png' });
  console.log('god card:', y, 'errors:', errs.join('|') || 'none');
  await b.close();
})();
