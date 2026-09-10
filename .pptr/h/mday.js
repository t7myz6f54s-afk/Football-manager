const puppeteer = require('puppeteer');
(async () => {
  const b = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox','--disable-dev-shm-usage','--hide-scrollbars'] });
  const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const clickText = (txt) => p.evaluate((txt) => {
    const els = [...document.querySelectorAll('button')].filter(e => e.textContent.trim().toLowerCase().includes(txt));
    if (els.length) { els[els.length-1].click(); return true; } return false;
  }, txt);
  await p.setViewport({ width: 393, height: 852, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle0' }); await wait(1200);
  for (let i = 0; i < 25; i++) {
    if (await p.evaluate(() => G.screen) === 'match') break;
    await p.evaluate(() => { const x = document.querySelector('#btn-continue'); if (x && !x.disabled) x.click(); });
    await wait(450);
    await clickText('match centre'); await wait(350);
    await clickText('close'); await wait(200);
  }
  await clickText('close'); await wait(300);
  await clickText('watch full match'); await wait(1500);
  // capture frames hoping to catch a goal flash
  for (let f = 0; f < 10; f++) {
    await wait(1400);
    const has = await p.evaluate(() => !!document.querySelector('.gflash'));
    if (has) { await p.screenshot({ path: '/home/user/.shots/v33-01-goalflash.png' }); console.log('flash caught at frame', f); break; }
  }
  await clickText('skip to half-time'); await wait(1200); await clickText('close'); await wait(300);
  await clickText('send them back out'); await wait(1500);
  await clickText('skip to full-time'); await wait(1600); await clickText('close'); await wait(300);
  await p.screenshot({ path: '/home/user/.shots/v33-02-ft.png' });
  console.log('errors:', errs.join('|') || 'none');
  await b.close();
})();
