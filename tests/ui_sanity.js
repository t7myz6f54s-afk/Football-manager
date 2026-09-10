/* Static sanity: every screen dispatched in go() must have a definition.
   Run: node tests/ui_sanity.js */
const fs = require('fs');
const src = fs.readFileSync(__dirname + '/../fm/static/app.js', 'utf8');
const goBody = src.slice(src.indexOf('async function go('), src.indexOf('async function refreshState'));
const called = [...goBody.matchAll(/await (render[A-Za-z]+)\(/g)].map(m => m[1]);
const defined = new Set([...src.matchAll(/(?:async )?function (render[A-Za-z]+)\(/g)].map(m => m[1]));
const missing = [...new Set(called)].filter(f => !defined.has(f));
// helpers used in onclick attributes must exist too
const onclickFns = [...new Set([...src.matchAll(/onclick="([a-zA-Z_]+)\(/g)].map(m => m[1]))];
const allFns = new Set([...src.matchAll(/(?:async )?function ([a-zA-Z_]+)\(/g)].map(m => m[1]));
const missingHandlers = onclickFns.filter(f => !allFns.has(f) && !['go', 'closeModal'].includes(f));
// CSS classes referenced by JS must exist in stylesheet (spot list)
const css = fs.readFileSync(__dirname + '/../fm/static/style.css', 'utf8');
const needCss = ['.dock', '.mhero', '.ev-goal', '.crest', '.cellclub', '.pitch', '.escore', '.tcard', '.tbadge', '.slogo', '.dead-box'];
const missingCss = needCss.filter(c => !css.includes(c));
if (missing.length || missingHandlers.length || missingCss.length) {
  console.error('MISSING render fns:', missing, '| handlers:', missingHandlers, '| css:', missingCss);
  process.exit(1);
}
console.log('ui sanity ok:', new Set(called).size, 'screens,', onclickFns.length, 'onclick handlers,', needCss.length, 'css hooks');
