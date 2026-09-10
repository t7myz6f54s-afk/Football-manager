const puppeteer = require('puppeteer');
const SCREENS = ['home','inbox','squad','tactics','training','match','comps','transfers','scouting','finances','club','calendar','table','board','media','career'];
(async () => {
  const b = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox','--disable-dev-shm-usage','--hide-scrollbars'] });
  const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const wait = ms => new Promise(r => setTimeout(r, ms));
  await p.setViewport({ width: 393, height: 852, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle0' }); await wait(1200);
  for (const sc of SCREENS) {
    await p.evaluate(s => go(s), sc); await wait(800);
    const bad = await p.evaluate(() => {
      const out = [];
      if (document.documentElement.scrollWidth > innerWidth + 2) out.push('@' + document.documentElement.scrollWidth);
      document.querySelectorAll('#content *').forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.right > innerWidth + 6 && getComputedStyle(e).position !== 'fixed') out.push((e.className||e.tagName).toString().split(' ')[0] + '@' + Math.round(r.right));
      });
      return out.slice(0, 3);
    });
    console.log(sc.padEnd(10), bad.length ? 'OVERFLOW ' + bad.join(', ') : 'ok');
  }
  console.log('errors:', errs.length ? errs.join(' | ') : 'none');
  await b.close();
})();
