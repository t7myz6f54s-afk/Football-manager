const puppeteer = require('puppeteer');
(async () => {
  const b = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox','--disable-dev-shm-usage','--hide-scrollbars'] });
  const p = await b.newPage();
  const wait = ms => new Promise(r => setTimeout(r, ms));
  await p.setViewport({ width: 393, height: 852, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle0' }); await wait(1200);
  await p.evaluate(() => go('table')); await wait(1000);
  const m = await p.evaluate(() => {
    const t = document.querySelector('table.mc');
    const tw = t.closest('.tw');
    return { tableW: t.scrollWidth, wrapW: tw.clientWidth, docW: document.documentElement.scrollWidth, inner: innerWidth };
  });
  console.log(JSON.stringify(m));
  await p.screenshot({ path: '/home/user/.shots/v31-01-table.png' });
  await b.close();
})();
