const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function runtime(){
  const elements={};const document={getElementById:id=>elements[id]||=( {className:'',innerHTML:'',textContent:'',disabled:false,files:[],querySelector:()=>({onclick:null})}),addEventListener:()=>{}};
  const sandbox={window:{},document,location:{search:''},URLSearchParams,Intl,console,setTimeout,clearTimeout,Blob,URL};vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync('web/assets/common.js','utf8'),sandbox);sandbox.Arena=sandbox.window.Arena;
  vm.runInContext(fs.readFileSync('web/assets/viewer.js','utf8'),sandbox);return sandbox;
}
const context=runtime(),replay=JSON.parse(fs.readFileSync('web/assets/example.json','utf8'));
const validate=context.window.DuelReplay.validate;
test('replay accepts exact canonical sample',()=>assert.equal(validate(replay),replay));
test('Persian score fixture agrees with Python and proposal',()=>{
  const a='A5 A4 A2 A1 B5 B4 B3 C5 C2 C1 D4 D3 D1 E5 E2'.split(' '),b='A5 A3 A2 B5 B4 B1 B2 C5 C3 C2 D5 D4 D2 E4 E3'.split(' ');
  assert.equal(context.window.DuelReplay.breakdown(a,b,2).total,110);assert.equal(context.window.DuelReplay.breakdown(b,a,2).total,122);
});
for(const [name,mutate] of Object.entries({
  version:l=>l.version='other',banner:l=>l.banner=6,turnOrder:l=>l.turns[1].seat=0,slot:l=>l.turns[0].choice=6,
  market:l=>l.turns[1].market[0]='Z9',refill:l=>l.turns[0].refill='Z1',hand:l=>l.hands[0].pop(),
  score:l=>l.result.scores[0].total++,partial:l=>l.turns.pop(),winner:l=>l.result.winner=l.result.winner===0?1:0,
  player:l=>l.players[0]={bad:true},doubleCopies:l=>{l.initial_market=Array(6).fill('A1')},
  refillType:l=>l.turns.at(-1).refill=[l.turns.at(-1).refill],
}))test('rejects corrupted '+name,()=>{const l=structuredClone(replay);mutate(l);assert.throws(()=>validate(l))});
test('UI escapes untrusted team names and filenames',()=>assert.equal(context.Arena.esc('<script>"&\''),'&lt;script&gt;&quot;&amp;&#39;'));
test('one squad bonus, strict majorities, spectrum once',()=>{const f=context.window.DuelReplay.breakdown;assert.equal(f(['C1','C1','C2','C2','C3','C3'],[],4).squads,9);assert.equal(f(['A1'],['A1'],1).banner_a,0);assert.equal(f(['A1','B2','C3','D4','E5'],[],1).spectrum,15)});
test('slower playback and explicit manual stepping preserve the chosen turn',()=>{
  const box=runtime(),delays=[];box.setTimeout=(fn,ms)=>{delays.push(ms);return delays.length};box.clearTimeout=()=>{};
  box.window.ExampleReplay=replay;box.document.getElementById('sample-replay').onclick();
  assert.equal(box.document.getElementById('speed').value,'1600');
  const mode=box.document.getElementById('playback-mode');mode.value='manual';mode.onchange();
  assert.ok(box.document.getElementById('viewer').innerHTML.includes('نمایش نوبت بعد'));
  box.document.getElementById('analyze-next').onclick();
  assert.match(box.document.getElementById('viewer').innerHTML,/id="timeline"[^>]*value="1"/);
  const selected=box.document.getElementById('viewer').innerHTML.match(/class="monster-card selected"[\s\S]*?<b>([A-E][1-5])<\/b>/);
  assert.equal(selected[1],replay.turns[0].card);
  assert.equal(box.document.getElementById('play').disabled,true);
  assert.ok(!delays.includes(1600));
});
test('every replay frame highlights its recorded choice and player rather than its refill',()=>{
  const box=runtime();box.window.ExampleReplay=replay;box.document.getElementById('sample-replay').onclick();
  for(const turn of replay.turns){
    box.document.getElementById('next').onclick();
    const html=box.document.getElementById('viewer').innerHTML;
    const selected=html.match(/class="monster-card selected"[\s\S]*?<b>([A-E][1-5])<\/b>/);
    assert.equal(selected[1],turn.card);
    assert.ok(html.includes(`کارت جایگزین: ${turn.refill}`));
  }
});
