/* Boot-flow test: load the game, assert splash hides, app appears, no page errors.
   Also: start a career via the real API flow, open every screen, run CONTINUE. */
const puppeteer = require('puppeteer');

(async () => {
  const base = process.env.TL_URL || 'http://127.0.0.1:8123';
  const browser = await puppeteer.launch({
    headless: 'shell',
    executablePath: process.env.CHROME_BIN || undefined,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 393, height: 851, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('response', r => { if (r.status() >= 400) errors.push('http ' + r.status() + ': ' + r.url()); });

  await page.goto(base, { waitUntil: 'networkidle2', timeout: 60000 });

  // 1. splash must hide within 20s
  try {
    await page.waitForSelector('#splash.hidden', { timeout: 20000 });
    console.log('PASS: splash hidden');
  } catch {
    const msg = await page.$eval('#splash-msg', el => el.textContent).catch(() => '?');
    console.log('FAIL: splash still visible after 20s (msg: ' + msg + ')');
    await browser.close(); process.exit(1);
  }

  // 2. start screen content visible
  const startTxt = await page.$eval('#content', el => el.innerText.slice(0, 300)).catch(() => '');
  if (/new career|search|club/i.test(startTxt)) console.log('PASS: start screen rendered');
  else { console.log('FAIL: start screen missing. content="' + startTxt.slice(0, 120) + '"'); await browser.close(); process.exit(1); }

  // 3. tabbar dock rendered (the exact function that had the syntax error)
  const dock = await page.$('#tabbar .dock');
  console.log(dock ? 'PASS: floating dock rendered' : 'FAIL: floating dock missing');

  // 4. create a career through the same endpoints the UI uses
  const club = await page.evaluate(async () => {
    const r = await fetch('/api/clubs/search?q=Arsenal').then(x => x.json());
    const list = r.results || r.clubs || r;
    return Array.isArray(list) ? list[0] : null;
  }).catch(() => null);
  if (!club || !club.code) { console.log('WARN: club search failed; skipping walkthrough'); }
  else {
    const made = await page.evaluate(async (code) => {
      const body = { club_code: code, difficulty: 'normal',
        manager: { name: 'Test Gaffer', nat: 'England', age: 42, reputation: 60, style: 'balanced', attrs: {} } };
      return fetch('/api/career/new', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(x => x.json());
    }, club.code).catch(e => ({ error: String(e) }));
    if (made && made.ok !== false) {
      console.log('PASS: career created (' + (club.name || club.code) + ')');
      await page.evaluate(async () => { G.boot = await api.get('/api/boot'); await enterGame(); });
      await new Promise(r => setTimeout(r, 2000));
      for (const s of ['squad', 'tactics', 'table', 'transfers', 'inbox', 'home']) {
        await page.evaluate(sc => go(sc), s).catch(e => errors.push('go(' + s + '): ' + e.message));
        await new Promise(r => setTimeout(r, 800));
        const ok = await page.evaluate(() => {
          const c = document.querySelector('#content');
          return c && c.innerText.length > 40 && !/LOADING/i.test(c.innerText);
        });
        console.log((ok ? 'PASS: ' : 'FAIL: ') + 'screen ' + s);
      }
      // CONTINUE once (engine day tick through the UI path)
      const cont = await page.evaluate(async () => { await doContinue(); return true; }).catch(e => String(e));
      console.log(cont === true ? 'PASS: doContinue executed' : 'FAIL: doContinue ' + cont);
      // ---- Match Day Live+: play a full match through the real UI loop ----
      await page.evaluate(() => playMatch('full'));
      await new Promise(r => setTimeout(r, 2500));
      const liveHud = await page.evaluate(() => !!document.querySelector('#lv-feed') && !!document.querySelector('#lv-clock'));
      console.log(liveHud ? 'PASS: live HUD rendered (feed + clock)' : 'FAIL: live HUD missing');
      await page.evaluate(() => { if (LIVE) LIVE.fast = true; });  // fast-forward the sim
      // wait for half-time (talk screen) or full-time, up to 150s
      let reachedHT = false, reachedFT = false;
      for (let i = 0; i < 150; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const st = await page.evaluate(() => ({
          ht: !!document.querySelector('#ht-talk'),
          ft: (document.querySelector('#content') || {innerText: ''}).innerText.includes('FULL-TIME'),
          min: LIVE ? LIVE.clockMin : -1,
        }));
        if (st.ht) { reachedHT = true; break; }
        if (st.ft) { reachedFT = true; break; }
      }
      console.log(reachedHT ? 'PASS: reached half-time' : (reachedFT ? 'PASS: straight to full-time' : 'FAIL: stuck before half-time'));
      if (reachedHT) {
        await page.evaluate(() => submitHalftime(true));   // send them back out
        await new Promise(r => setTimeout(r, 7000));       // normal pace: reach ~minute 60
        const midState = await page.evaluate(() => ({ live: !!LIVE && !LIVE.stopped, min: LIVE ? LIVE.clockMin : -1 }));
        let sentOrder = false;
        if (midState.live && midState.min > 45) {
          await page.evaluate(() => sendOrder('press_hard'));
          sentOrder = true;
        }
        await page.evaluate(() => { if (LIVE) LIVE.fast = true; });
        for (let i = 0; i < 150; i++) {
          await new Promise(r => setTimeout(r, 1000));
          const st = await page.evaluate(() => ({
            live: !!LIVE && !LIVE.stopped,
            ft: (document.querySelector('#content') || {innerText: ''}).innerText.includes('FULL-TIME'),
          }));
          if (st.ft) { reachedFT = true; break; }
          if (!st.live) break;
        }
        console.log((sentOrder ? 'PASS: ' : 'WARN: ') + 'touchline order sent mid-half');
      }
      console.log(reachedFT ? 'PASS: reached full-time through live UI' : 'FAIL: never reached full-time');
      const liveErrs = errors.filter(e => !/favicon/i.test(e));
      if (liveErrs.length) { console.log('LIVE PAGE ERRORS:'); liveErrs.forEach(e => console.log('  ' + e)); }
      // ---- Stats Center: advance a few days so league games are played, then check ----
      for (let k = 0; k < 6; k++) { await page.evaluate(async () => { await doContinue(); }); await new Promise(r => setTimeout(r, 600)); }
      await page.evaluate(() => go('stats'));
      await new Promise(r => setTimeout(r, 1200));
      const statsOk = await page.evaluate(() => {
        const t = ((document.querySelector('#content') || {innerText: ''}).innerText || '').toLowerCase();
        return t.includes('statistics') && t.includes('golden boot') && t.includes('expected goals') && t.includes('form guide');
      });
      console.log((statsOk ? 'PASS: ' : 'FAIL: ') + 'stats screen renders (golden boot + xG sections)');
      // grouped More menu
      await page.evaluate(() => openSheet());
      await new Promise(r => setTimeout(r, 500));
      const menuOk = await page.evaluate(() => {
        const t = ((document.querySelector('#sheet-grid') || {innerText: ''}).innerText || '').toLowerCase();
        return ['club','market','world','office'].every(x => t.includes(x));
      });
      console.log((menuOk ? 'PASS: ' : 'FAIL: ') + 'grouped More menu (Club/Market/World/Office, no emoji)');
      await page.evaluate(() => closeSheet());
      // transfer flow end-to-end (exercises the fixed would_sell / player_willing)
      const bid = await page.evaluate(async () => {
        const sr = await fetch('/api/transfer/search?max_fee=60&age_max=24').then(x => x.json());
        const list = sr.players || [];
        if (!list.length) return 'no targets found';
        const t = list[0];
        const r = await fetch('/api/transfer/offer', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pid: t.id, fee: 15, wage: 50 }) }).then(x => x.json());
        return { target: t.name, result: r };
      }).catch(e => 'err ' + e.message);
      console.log('transfer probe: ' + JSON.stringify(bid).slice(0, 160));
    } else {
      console.log('WARN: career create failed: ' + JSON.stringify(made).slice(0, 200));
    }
  }

  const fatal = errors.filter(e => !/favicon/i.test(e));
  if (fatal.length) { console.log('PAGE ERRORS:'); fatal.forEach(e => console.log('  ' + e)); }
  else console.log('PASS: zero page/console errors');
  await browser.close();
  process.exit(fatal.length ? 1 : 0);
})();
