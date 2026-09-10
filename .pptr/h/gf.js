const puppeteer = require('puppeteer');
(async () => {
  const b = await puppeteer.launch({ headless: 'shell', args: ['--no-sandbox','--disable-dev-shm-usage','--hide-scrollbars'] });
  const p = await b.newPage();
  const wait = ms => new Promise(r => setTimeout(r, ms));
  await p.setViewport({ width: 393, height: 852, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await p.goto('http://localhost:8000/', { waitUntil: 'networkidle0' }); await wait(1200);
  await p.evaluate(() => { G.codes = { home: 'ARS', away: 'MCI', comp: 'ENG1', compName: 'Premier League' };
    goalFlash({ type: 'goal', minute: 67, side: 'H', player: 'Bukayo Saka', _sc: '2 – 1' }); });
  await wait(500);
  await p.screenshot({ path: '/home/user/.shots/v33-03-flash.png' });
  await b.close();
})();
