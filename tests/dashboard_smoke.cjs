const assert=require('node:assert/strict');
const fs=require('node:fs');
const source=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/\nload\(\);\s*$/,'');
const snapshot=JSON.parse(fs.readFileSync('data/latest.json','utf8'));
const render=new Function('d',source+'\nreturn [decisionOverview(d),evidencePanel(d)];');
const [overview,evidence]=render(snapshot);
assert.match(overview,/SPY/);
assert.match(overview,/QQQ/);
assert.match(overview,/Recovery confirmation/);
if(snapshot.comprehensive_checklist){
 assert.match(evidence,/Manual evidence journal/);
 assert.match(evidence,/data-journal/);
}
const [empty,missing]=render({assets:{}});
assert.match(empty,/Unavailable/);
assert.match(missing,/awaits/);
console.log('Dashboard snapshot and missing-data rendering verified');
