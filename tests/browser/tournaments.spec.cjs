const {test,expect,login,visit,json,PY}=require('./support/fixtures.cjs');
async function setup(installation,paired=false,delay=600){
  const admin=await installation.client('admin');const data=await json(await admin.get('/api/admin/overview'));const teams=data.teams.filter(t=>t.submission_id).map(t=>t.id);
  const response=await json(await admin.post('/api/admin/tournaments',{name:'جام آزمایش',teams,paired,starts_at:Date.now()/1000+delay}),201);return {admin,id:response.id,teams};
}
async function complete(admin,id){
  await expect.poll(async()=>(await json(await admin.get('/api/tournaments/'+id))).tournament.status,{timeout:20000}).toBe('completed');
  return json(await admin.get('/api/tournaments/'+id));
}
test('create tournament from top K of a completed tournament',async({page,installation})=>{
  const {admin,id}=await setup(installation,true);await admin.post('/api/admin/tournaments/'+id,{action:'start'});
  const previous=await complete(admin,id),top=previous.standings.filter(r=>r.rank<=2).map(r=>r.id);
  await login(page,'admin');await visit(page,'admin/tournaments','تورنمنت‌ها');
  await page.getByRole('button',{name:'تورنمنت جدید',exact:true}).click();
  await page.getByLabel('تورنمنت قبلی',{exact:true}).selectOption(String(id));
  await page.getByLabel('تعداد تیم‌های برتر',{exact:true}).fill('2');
  await page.getByRole('button',{name:'انتخاب تیم‌های برتر',exact:true}).click();
  await expect(page.locator('#tournament-form input[name="teams"]:checked')).toHaveCount(2);
  for(const team of top)await expect(page.locator(`#tournament-form input[name="teams"][value="${team}"]`)).toBeChecked();
  await page.getByLabel('نام رقابت',{exact:true}).fill('جام برترین‌ها');
  const created=page.waitForResponse(r=>r.url().endsWith('/api/admin/tournaments')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'ثبت برنامهٔ تورنمنت',exact:true}).click();
  const next=await json(await created,201),event=await json(await admin.get('/api/tournaments/'+next.id));
  expect(event.standings.map(r=>r.id).sort((a,b)=>a-b)).toEqual([...top].sort((a,b)=>a-b));
  await page.getByRole('button',{name:'جدول رتبه‌بندی',exact:true}).first().click();
  await expect(page.getByRole('columnheader',{name:'درصد برد مقابل ۱۰ تیم برتر'})).toBeVisible();
});
for(const count of [1,4,6])test(`UI schedules ${count} games per pair, starts and displays standings`,async({page})=>{
  await login(page,'admin');await visit(page,'admin/tournaments','تورنمنت‌ها');await expect(page.locator('.empty')).toContainText('هنوز');await page.getByRole('button',{name:'تورنمنت جدید',exact:true}).click();await page.getByLabel('نام رقابت').fill('جام مرورگر');await expect(page.locator('#tournament-estimate')).toContainText('۳ بازی');await page.getByLabel('تعداد بازی برای هر جفت تیم',{exact:true}).fill(String(count));await expect(page.locator('#tournament-estimate')).toContainText(count===6?'۱۸ بازی':count===4?'۱۲ بازی':'۳ بازی');
  await page.getByRole('button',{name:'ثبت برنامهٔ تورنمنت',exact:true}).click();await expect(page.locator('.tournament-card')).toContainText('برنامه‌ریزی‌شده');await expect(page.locator('.tournament-card .meta span').nth(1)).toHaveText(count===6?'۱۸ بازی':count===4?'۱۲ بازی':'۳ بازی');await expect(page.locator('.tournament-card progress')).toHaveAttribute('max',String(3*count));await page.getByRole('button',{name:'شروع اکنون',exact:true}).click();await expect(page.locator('.tournament-card')).toContainText('پایان‌یافته',{timeout:20000});
  await page.getByRole('button',{name:'جدول رتبه‌بندی',exact:true}).click();await expect(page.locator('dialog [data-standings=ranked] tbody tr')).toHaveCount(count>1?3:0);await expect(page.locator('dialog [data-standings=provisional] tbody tr')).toHaveCount(count>1?0:3);for(const row of await page.locator('dialog tbody tr').all())await expect(row.locator('td').nth(1)).toHaveText(count===6?'۱۲':count===4?'۸':'۲');
});
for(const paired of [false,true])test(`${paired?'paired':'single'} event has all pairs, balanced seats and immutable input`,async({installation})=>{
  const {admin,id,teams}=await setup(installation,paired);await admin.post('/api/admin/worker',{paused:true});const alpha=await installation.client();const before=(await json(await alpha.get('/api/dashboard'))).active_submission_id;
  const newest=await json(await alpha.post('/api/submissions',{source:PY,filename:'latest.py'}),201);await alpha.post('/api/submissions/'+before+'/activate',{});
  await json(await admin.post('/api/admin/tournaments/'+id,{action:'start'}));await expect.poll(async()=>(await json(await admin.get('/api/tournaments/'+id))).tournament.status).toBe('running');
  const later=await json(await alpha.post('/api/submissions',{source:PY,filename:'after-start.py'}),201);
  await admin.post('/api/admin/worker',{paused:false});const event=await complete(admin,id);expect(event.standings.map(r=>r.played)).toEqual([paired?4:2,paired?4:2,paired?4:2]);
  const games=(await json(await admin.get('/api/matches?tournament='+id))).items;expect(games).toHaveLength(paired?6:3);
  const pairs=new Map();let starts=new Map(teams.map(t=>[t,0]));
  for(const game of games){
    const pair=[game.p0,game.p1].sort().join(':');pairs.set(pair,(pairs.get(pair)||0)+1);starts.set(game.p0,starts.get(game.p0)+1);
    expect([game.s0,game.s1]).not.toContain(newest.id);expect([game.s0,game.s1]).not.toContain(later.id);
  }
  expect(pairs.size).toBe(3);expect([...pairs.values()]).toEqual([paired?2:1,paired?2:1,paired?2:1]);expect(Math.max(...starts.values())-Math.min(...starts.values())).toBeLessThanOrEqual(1);

});
test('paired games reuse seeds and swap starting players',async({installation})=>{
  const {admin,id}=await setup(installation,true);await admin.post('/api/admin/tournaments/'+id,{action:'start'});await complete(admin,id);
  const games=(await json(await admin.get('/api/matches?tournament='+id))).items;const grouped={};
  for(const g of games){const key=[g.p0,g.p1].sort().join(':');(grouped[key]||=[]).push(g)}
  for(const pair of Object.values(grouped)){
    const a=await json(await admin.get(`/api/matches/${pair[0].id}/replay`)),b=await json(await admin.get(`/api/matches/${pair[1].id}/replay`));expect(a.seed).toBe(b.seed);expect(a.initial_market).toEqual(b.initial_market);expect(pair[0].p0).toBe(pair[1].p1);
  }
});
test('scheduled event starts automatically at its stored time',async({installation})=>{
  const {admin,id}=await setup(installation,false,1);await complete(admin,id);
});
test('cancelled scheduled tournament never creates games',async({page,installation})=>{
  const {admin,id}=await setup(installation);await login(page,'admin');await visit(page,'admin/tournaments','تورنمنت‌ها');await page.getByRole('button',{name:'لغو',exact:true}).click();await expect(page.locator('.tournament-card')).toHaveCount(0);await expect(page.locator('.empty')).toContainText('هنوز');expect((await json(await admin.get('/api/matches?tournament='+id))).total).toBe(0);expect((await admin.post('/api/admin/tournaments/'+id,{action:'start'})).status()).toBe(409);
});
for(const action of ['disable','missing-code'])test(`selected team becomes ${action} before start; no silent removal`,async({installation})=>{
  const {admin,id,teams}=await setup(installation);
  if(action==='disable')await admin.post('/api/admin/teams/'+teams[0],{active:false});else installation.state({action:'missing_code'});
  await admin.post('/api/admin/tournaments/'+id,{action:'start'});await expect.poll(async()=>(await json(await admin.get('/api/tournaments/'+id))).tournament.status).toBe('failed');expect((await json(await admin.get('/api/matches?tournament='+id))).total).toBe(0);
});
test('infrastructure retry resumes failed tournament games only',async({installation})=>{
  const {admin,id}=await setup(installation);await admin.post('/api/admin/worker',{paused:true});await admin.post('/api/admin/tournaments/'+id,{action:'start'});await expect.poll(async()=>(await json(await admin.get('/api/matches?tournament='+id))).total).toBe(3);
  installation.state({action:'tournament_failure',id});expect((await json(await admin.get('/api/tournaments/'+id))).standings.every(r=>r.played===0)).toBe(true);
  await json(await admin.post('/api/admin/tournaments/'+id,{action:'retry'}));await admin.post('/api/admin/worker',{paused:false});expect((await complete(admin,id)).standings.every(r=>r.played===2)).toBe(true);
});
for(const variant of ['one-team','duplicate-team','no-code','past-date','bad-paired','empty-name'])test(`reject tournament ${variant}`,async({installation})=>{
  const admin=await installation.client('admin'),data=await json(await admin.get('/api/admin/overview'));const ready=data.teams.filter(t=>t.submission_id).map(t=>t.id),empty=data.teams.find(t=>!t.submission_id).id;
  const body={name:'valid',teams:ready,starts_at:Date.now()/1000+600,paired:false};
  if(variant==='one-team')body.teams=ready.slice(0,1);if(variant==='duplicate-team')body.teams=[ready[0],ready[0]];if(variant==='no-code')body.teams=[ready[0],empty];if(variant==='past-date')body.starts_at=1;if(variant==='bad-paired')body.paired='true';if(variant==='empty-name')body.name='';
  expect((await admin.post('/api/admin/tournaments',body)).status()).toBe(400);
});
test('completed tournament is public to signed-in teams and cannot be started or cancelled again',async({installation})=>{
  const {admin,id}=await setup(installation);await admin.post('/api/admin/tournaments/'+id,{action:'start'});const event=await complete(admin,id);const outsider=await installation.client('empty');const games=(await json(await outsider.get('/api/matches?tournament='+id))).items;expect(games).toHaveLength(3);expect((await outsider.get(`/api/matches/${games[0].id}/replay`)).status()).toBe(200);
  for(const action of ['start','cancel','retry'])expect((await admin.post('/api/admin/tournaments/'+id,{action})).status()).toBe(409);
  const sorted=[...event.standings].sort((a,b)=>Number(b.eligible)-Number(a.eligible)||(b.win_ratio||0)-(a.win_ratio||0)||b.wins-a.wins||b.draws-a.draws||b.difference-a.difference||a.id-b.id);expect(event.standings).toEqual(sorted);
});
