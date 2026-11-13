(() => {
  const {icon,esc,fa,api,toast,modal}=Arena;
  let replay=null,step=0,playing=false,mode='auto',playTimer=null,waitTimer=null;
  const viewer=document.getElementById('viewer');
  const cardPattern=/^[A-E][1-5]$/;
  function breakdown(hand,opponent,banner){
    const species=s=>hand.filter(c=>c[0]===s).length,other=s=>opponent.filter(c=>c[0]===s).length,strength=k=>hand.filter(c=>Number(c[1])===k).length;
    const p={base:hand.reduce((sum,c)=>sum+Number(c[1]),0),squads:9*[...'ABCDE'].filter(s=>species(s)>=3).length,spectrum:[1,2,3,4,5].every(strength)?15:0,banner_a:species('A')>other('A')?12:0,banner_b:species('B')>other('B')?12:0,banner_strength:strength(banner)>opponent.filter(c=>Number(c[1])===banner).length?9:0};
    p.total=Object.values(p).reduce((a,b)=>a+b,0);return p;
  }
  function validate(log){
    const fail=()=>{throw new Error('این فایل با قالب بازپخش نسخهٔ ۱ سازگار نیست یا مراحل بازی آن ناسازگار است.')};
    if(!log||log.version!=='monster-draft-duel/1'||!Number.isInteger(log.banner)||log.banner<1||log.banner>5||!Array.isArray(log.players)||log.players.length!==2||log.players.some(p=>typeof p!=='string'||p.length>150)||!Array.isArray(log.initial_market)||log.initial_market.length!==6||!Array.isArray(log.turns)||log.turns.length>30||!log.result)fail();
    let market=log.initial_market.slice(),hands=[[],[]],counts={};
    function observe(c){if(typeof c!=='string'||!cardPattern.test(c))fail();counts[c]=(counts[c]||0)+1;if(counts[c]>2)fail()}
    market.forEach(observe);
    log.turns.forEach((t,i)=>{
      if(!t||typeof t!=='object')fail();
      if(t.turn!==i||t.seat!==[0,1,1,0][i%4]||!Number.isInteger(t.choice)||t.choice<0||t.choice>5||!Array.isArray(t.market)||JSON.stringify(t.market)!==JSON.stringify(market)||t.card!==market[t.choice])fail();
      observe(t.refill);hands[t.seat].push(t.card);market[t.choice]=t.refill;
    });
    if(JSON.stringify(log.hands)!==JSON.stringify(hands)||![null,0,1].includes(log.result.winner)||!Object.hasOwn(Arena.reasons,log.result.reason)||!Array.isArray(log.result.scores)||log.result.scores.length!==2)fail();
    const scores=[breakdown(hands[0],hands[1],log.banner),breakdown(hands[1],hands[0],log.banner)];
    scores.forEach((s,p)=>{for(const k in s)if(log.result.scores[p]?.[k]!==s[k])fail()});
    if(log.result.reason==='completed'){
      if(log.turns.length!==30)fail();
      const keys=scores.map((s,p)=>[s.total,s.base,...[5,4,3,2,1].map(k=>hands[p].filter(c=>+c[1]===k).length)]);
      let winner=null;for(let i=0;i<7;i++)if(keys[0][i]!==keys[1][i]){winner=keys[0][i]>keys[1][i]?0:1;break}
      if(winner!==log.result.winner)fail();
    }else if(![0,1].includes(log.result.loser)||log.result.winner!==1-log.result.loser)fail();
    return log;
  }
  function load(log){const valid=validate(log);pause();clearTimeout(waitTimer);replay=valid;step=0;document.getElementById('download-log').disabled=false;render();toast('بازپخش آماده است. برای پخش، دکمهٔ شروع را بزنید.')}
  function mini(c){return `<span class="mini-card species-${c[0]}" dir="ltr">${c}</span>`}
  function render(){
    if(!replay)return;
    const focused=document.activeElement,focusId=focused&&viewer.contains(focused)?focused.id:null;
    const hands=[[],[]];
    replay.turns.slice(0,step).forEach(t=>{hands[t.seat].push(t.card)});
    const scores=[breakdown(hands[0],hands[1],replay.banner),breakdown(hands[1],hands[0],replay.banner)],last=replay.turns[step-1],next=replay.turns[step],finished=step===replay.turns.length;
    // Highlight the card actually picked in this frame, before its replacement.
    const market=last?last.market:replay.initial_market,actor=last||next;
    function player(seat){return `<section class="player ${actor?.seat===seat?'active':''}"><span class="avatar">${esc(replay.players[seat].slice(0,1))}</span><div><strong>${esc(replay.players[seat])}</strong><br><small>جای ${seat===0?'اول':'دوم'} · ${fa(hands[seat].length)} از ۱۵ کارت</small></div><span class="player-score">${fa(scores[seat].total)}<small>امتیاز فعلی</small></span></section><div class="collection">${hands[seat].map(mini).join('')||'<small>منتظر اولین انتخاب…</small>'}</div>`}
    viewer.innerHTML=`<div class="viewer-layout"><div><section class="viewer-stage"><div class="viewer-banner">پرچم‌های گونه <span class="pill">A +۱۲</span><span class="pill">B +۱۲</span> پرچم قدرت <span class="pill">${fa(replay.banner)} +۹</span></div>${player(1)}<div class="market">${market.map((c,i)=>`<div class="monster-card ${last?.choice===i?'selected':''}" title="جای ${fa(i)}؛ ${c}"><span class="slot">${i}</span><img src="assets/monster-${c[0].toLowerCase()}.svg" alt="گونهٔ ${c[0]}"><b>${c}</b><span class="strength">قدرت ${fa(Number(c[1]))}</span></div>`).join('')}</div>${player(0)}<div class="analysis-controls"><label for="playback-mode">روش نمایش</label><select id="playback-mode"><option value="auto">پخش خودکار</option><option value="manual">تحلیل نوبت‌به‌نوبت</option></select>${mode==='manual'?`<button class="btn primary" id="analyze-next" ${finished?'disabled':''}>نمایش نوبت بعد</button><small>برای بررسی هر انتخاب، یک بار دکمه را بزنید.</small>`:''}</div><div class="playback"><button class="btn" id="first" aria-label="بازگشت به آغاز">${icon('back')}</button><button class="btn" id="prev" aria-label="انتخاب قبلی">‹</button><button class="btn primary" id="play" aria-label="${playing?'توقف':'پخش'}">${icon(playing?'pause':'play')}</button><button class="btn" id="next" aria-label="انتخاب بعدی">›</button><input id="timeline" type="range" min="0" max="${replay.turns.length}" value="${step}" aria-label="نوبت بازپخش"><select id="speed" aria-label="سرعت پخش"><option value="3200">۰٫۵×</option><option value="1600" selected>۱×</option><option value="800">۲×</option><option value="400">۴×</option></select></div><p class="turn-label">${step===0?'شروع بازی؛ بازار اولیه':`انتخاب ${fa(step)} از ${fa(replay.turns.length)} · ${esc(replay.players[last.seat])} کارت ${last.card} از جای ${fa(last.choice)} برداشت؛ این نما بازار هنگام انتخاب است. کارت جایگزین: ${last.refill}.`}</p></section><p class="hint">امتیازهای میان بازی برای آموزش‌اند؛ امتیاز رسمی فقط در پایان محاسبه می‌شود. کلیدهای ← و → برای حرکت و Space برای پخش.</p></div><aside class="viewer-sidebar"><section class="panel breakdown"><h2>دفتر امتیازها</h2><p class="hint">${finished?'امتیاز پایان بازی':'بر اساس کارت‌های انتخاب‌شده تا این لحظه'}</p><div class="players-score">${scores.map((s,p)=>`<div><small>${esc(replay.players[p])}</small><b>${fa(s.total)}</b></div>`).join('')}</div>${finished?`<div class="result-callout">${replay.result.winner===null?'بازی مساوی شد':`${esc(replay.players[replay.result.winner])} برنده شد`}<br><small>${esc(Arena.reasons[replay.result.reason])}</small></div>`:''}<table><thead><tr><th>بخش امتیاز</th><th>جای اول</th><th>جای دوم</th></tr></thead><tbody>${Object.entries({base:'قدرت کارت‌ها',squads:'دسته‌های هم‌گونه',spectrum:'طیف کامل قدرت',banner_a:'پرچم A',banner_b:'پرچم B',banner_strength:`پرچم قدرت ${fa(replay.banner)}`}).map(([k,v])=>`<tr><td>${v}</td><td>${fa(scores[0][k])}</td><td>${fa(scores[1][k])}</td></tr>`).join('')}</tbody></table></section><section class="panel"><div class="panel-head"><h2>رد انتخاب‌ها</h2><small>${fa(step)} انتخاب</small></div><div class="event-list">${replay.turns.slice(0,step).reverse().map(t=>`<div class="event-row"><span class="muted">${fa(t.turn+1)}.</span><span>${esc(replay.players[t.seat])}</span>${mini(t.card)}<span class="muted">جای ${fa(t.choice)}</span></div>`).join('')||'<span class="muted">هنوز کارتی انتخاب نشده.</span>'}</div></section></aside></div>`;
    const modeSelect=document.getElementById('playback-mode');modeSelect.value=mode;modeSelect.onchange=()=>{pause();mode=modeSelect.value;render()};
    if(mode==='manual'){document.getElementById('analyze-next').onclick=()=>go(step+1);document.getElementById('play').disabled=true;}
    const speed=document.getElementById('speed');speed.value=String(currentSpeed);speed.onchange=()=>{currentSpeed=Number(speed.value);if(playing){clearTimeout(playTimer);schedule()}};
    document.getElementById('first').onclick=()=>go(0);document.getElementById('prev').onclick=()=>go(step-1);document.getElementById('next').onclick=()=>go(step+1);document.getElementById('play').onclick=toggle;
    document.getElementById('timeline').oninput=e=>go(Number(e.target.value));
    const control=focusId&&document.getElementById(focusId);if(control&&!control.disabled)control.focus({preventScroll:true});
  }
  let currentSpeed=1600;
  function pause(){playing=false;clearTimeout(playTimer)}
  function go(n){pause();step=Math.max(0,Math.min(replay.turns.length,n));render()}
  function schedule(){playTimer=setTimeout(()=>{if(!playing)return;step++;if(step>=replay.turns.length){step=replay.turns.length;playing=false}render();if(playing)schedule()},currentSpeed)}
  function toggle(){if(!replay)return;if(mode==='manual'){go(step+1);return;}if(playing)pause();else{if(step===replay.turns.length)step=0;playing=true;schedule()}render()}
  async function watch(id){
    clearTimeout(waitTimer);pause();
    try{
      const session=await api('/session');Arena.setCSRF(session.csrf);
      if(!session.user){viewer.innerHTML=`<section class="panel viewer-empty"><h2>برای دیدن این بازی وارد شوید</h2><p>بازپخش بازی‌های دوستانه فقط برای دو تیم و مدیر در دسترس است.</p><a class="btn primary" href="/?next=${encodeURIComponent('/visualizer?match='+id)}">ورود به میدان</a></section>`;return}
      const job=await api('/matches/'+id);
      if(job.status==='completed'){load(await api('/matches/'+id+'/replay'));return}
      if(job.status==='failed')throw new Error(job.error||'خطای زیرساخت؛ با مدیر مسابقه صحبت کنید.');
      viewer.innerHTML=`<section class="panel viewer-empty"><img src="assets/monster-d.svg" alt=""><h2>${job.status==='running'?'ربات‌ها در میدان‌اند…':'بازی در صف است'}</h2><p>بازی شمارهٔ ${fa(id)}؛ به محض پایان، بازپخش همین‌جا باز می‌شود.</p><a class="btn" href="/#matches">دیدن صف مسابقه‌ها</a></section>`;
      waitTimer=setTimeout(()=>watch(id),2000);
    }catch(err){viewer.innerHTML=`<section class="panel replay-error" role="alert">${esc(err.message)}</section>`}
  }
  document.getElementById('load-log').onclick=()=>document.getElementById('log-file').click();
  document.getElementById('log-file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>1048576)throw new Error('فایل بازپخش باید کمتر از یک مگابایت باشد.');load(JSON.parse(await file.text()))}catch(err){toast(err instanceof SyntaxError?'فایل JSON معتبر نیست.':err.message,true)}e.target.value=''};
  document.getElementById('sample-replay').onclick=()=>{try{load(window.ExampleReplay)}catch(err){toast(err.message,true)}};
  document.getElementById('download-log').onclick=()=>{if(!replay)return;const url=URL.createObjectURL(new Blob([JSON.stringify(replay,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=`duel-${replay.match_id||'replay'}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
  document.getElementById('local-codes').onclick=async()=>{
    try{const session=await api('/session');if(!session.user){toast('برای اجرای کدها، ابتدا وارد حساب تیم شوید.',true);return}Arena.setCSRF(session.csrf);modal('آزمایش دو کد محلی',`<p class="hint">فایل‌ها به اجراکنندهٔ ایزولهٔ سایت فرستاده می‌شوند. این آزمایش نسخهٔ فعال تیم را تغییر نمی‌دهد و از سهمیهٔ بازی استفاده می‌کند.</p><form id="local-form" class="section-gap"><div class="field"><label for="code0">کد بازیکن جای اول</label><input id="code0" type="file" accept=".py,.cpp" required></div><div class="field"><label for="code1">کد بازیکن جای دوم</label><input id="code1" type="file" accept=".py,.cpp" required></div><div class="inline-error" role="alert"></div><button class="btn primary" type="submit">بفرست به میدان</button></form>`);document.getElementById('local-form').onsubmit=async e=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;try{const codes=[];for(let p=0;p<2;p++){const f=document.getElementById('code'+p).files[0];if(f.size>65536||!/\.(py|cpp)$/i.test(f.name))throw new Error('فقط فایل .py یا .cpp، حداکثر ۶۴ کیلوبایت.');codes.push({filename:f.name,language:/\.cpp$/i.test(f.name)?'cpp':'python',source:await f.text()})}const job=await api('/local',{codes});document.getElementById('modal').close();history.replaceState(null,'','?match='+job.id);watch(job.id)}catch(err){e.target.querySelector('.inline-error').textContent=err.message}finally{button.disabled=false}}}catch(err){toast('اجرای کدها به سرور سایت و ورود به حساب نیاز دارد. بازپخش فایل‌ها آفلاین کار می‌کند.',true)}
  };
  document.addEventListener('keydown',e=>{if(!replay||document.getElementById('modal').open||['INPUT','SELECT','BUTTON','TEXTAREA'].includes(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();toggle()}else if(e.code==='ArrowRight'){e.preventDefault();go(step+1)}else if(e.code==='ArrowLeft'){e.preventDefault();go(step-1)}});
  const match=new URLSearchParams(location.search).get('match');if(match&&/^\d+$/.test(match))watch(Number(match));
  // Public functions are intentionally tiny to support external conformance tests.
  window.DuelReplay={validate,breakdown};
})();
