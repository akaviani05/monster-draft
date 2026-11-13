const {test,expect,login,visit,json,waitJob,PY,CPP}=require('./support/fixtures.cjs');

for(const bot of ['random','greedy','planner','guardian','champion'])test(`play against ${bot} produces a complete viewable replay`,async({page,installation})=>{
  const team=await installation.client();const job=await json(await team.post('/api/practice',{bot}),201);expect((await waitJob(team,job.id)).status).toBe('completed');
  const replay=await json(await team.get(`/api/matches/${job.id}/replay`));expect(replay.turns).toHaveLength(30);expect(replay.result.reason).toBe('completed');
  await login(page);await page.goto('/visualizer?match='+job.id);await expect(page.locator('.monster-card')).toHaveCount(6);await expect(page.locator('#timeline')).toHaveValue('0');
});
for(const width of [390,1440])test(`champion practice card queues its own opponent at ${width}px`,async({page,installation},testInfo)=>{
  await page.setViewportSize({width,height:1000});await login(page);await visit(page,'practice','بازی دوستانه');
  const card=page.locator('.bot-card').filter({has:page.getByRole('button',{name:'بازی با اژدها',exact:true})});
  await expect(card.locator('img')).toHaveAttribute('src','/assets/monster-e.svg');
  await expect.poll(()=>card.locator('img').evaluate(img=>img.naturalWidth)).toBeGreaterThan(0);
  await expect(card.getByText('سخت',{exact:true})).toBeVisible();
  await page.screenshot({path:testInfo.outputPath('champion-practice.png'),fullPage:true});
  await card.getByRole('button',{name:'بازی با اژدها',exact:true}).click();
  await expect(page.locator('#toast')).toContainText('به صف اضافه شد');
  const team=await installation.client();const matches=await json(await team.get('/api/matches'));const job=matches.items[0];expect(job.bot).toBe('champion');
  expect((await waitJob(team,job.id)).status).toBe('completed');
  const replay=await json(await team.get(`/api/matches/${job.id}/replay`));expect(replay.turns).toHaveLength(30);expect(replay.result.reason).toBe('completed');
  await expect(page.locator('body')).toHaveJSProperty('scrollWidth',width);
});
test('practice UI queues the selected opponent and opens that exact game',async({page})=>{
  await login(page);await visit(page,'practice','بازی دوستانه');await page.getByRole('button',{name:'بازی با جوانه',exact:true}).click();await expect(page.locator('#toast')).toContainText('به صف اضافه شد');
  await visit(page,'matches','مسابقه‌ها');const link=page.locator('tbody tr').first().getByRole('link',{name:/تماشای بازی/});await expect(link).toBeVisible({timeout:20000});const href=await link.getAttribute('href');await link.click();await expect(page).toHaveURL(new RegExp(href.replace('?','\\?')+'$'));await expect(page.locator('.monster-card')).toHaveCount(6);
});
test('missing source cannot queue a practice game',async({page,installation})=>{
  await login(page,'empty');await visit(page,'practice','بازی دوستانه');await page.getByRole('button',{name:'بازی با جوانه',exact:true}).click();await expect(page.locator('#toast')).toContainText('ابتدا');
  const client=await installation.client('empty');expect((await json(await client.get('/api/matches'))).total).toBe(0);
});
for(const bot of ['unknown',null,[],{}])test(`unknown practice opponent ${JSON.stringify(bot)} is rejected`,async({installation})=>{
  const team=await installation.client();expect((await team.post('/api/practice',{bot})).status()).toBe(400);
});
test('ten pending games reach the minute limit',async({installation})=>{
  const admin=await installation.client('admin'),team=await installation.client();await json(await admin.post('/api/admin/worker',{paused:true}),201);
  for(let i=0;i<10;i++)expect((await team.post('/api/practice',{bot:'greedy'})).status()).toBe(201);
  expect((await team.post('/api/practice',{bot:'greedy'})).status()).toBe(429);
});
for(const [count,age] of [[10,0]])test(`completed-game quota ${count} / age ${age}`,async({installation})=>{
  const team=await installation.client();installation.state({action:'completed_jobs',count,age_seconds:age});expect((await team.post('/api/practice',{bot:'greedy'})).status()).toBe(429);
});
test('old game history does not impose a daily limit',async({page,installation})=>{
  const team=await installation.client();installation.state({action:'completed_jobs',count:1000,age_seconds:120});
  await login(page);await visit(page,'practice','بازی دوستانه');await expect(page.getByText(/۱۰ درخواست در دقیقه/)).toBeVisible();
  const job=await json(await team.post('/api/practice',{bot:'greedy'}),201);
  expect((await team.post('/api/practice',{bot:'greedy'})).status()).toBe(201);
  expect((await waitJob(team,job.id)).status).toBe('completed');
  expect((await json(await team.get('/api/matches'))).total).toBe(1002);
});
test('invitation accept creates exactly one match with frozen source versions',async({installation})=>{
  const admin=await installation.client('admin'),a=await installation.client(),b=await installation.client('beta');await admin.post('/api/admin/worker',{paused:true});
  const beta=(await json(await a.get('/api/dashboard'))).teams.find(t=>t.name==='تیم بتا');const aBefore=(await json(await a.get('/api/dashboard'))).active_submission_id;
  const invite=await json(await a.post('/api/invitations',{team_id:beta.id}),201);await a.post('/api/submissions',{source:PY,filename:'new.py'});
  const bVersion=await json(await b.post('/api/submissions',{source:PY,filename:'recipient.py'}),201);
  const response=await json(await b.post('/api/invitations/'+invite.id,{action:'accept'}));
  const jobs=(await json(await a.get('/api/matches'))).items;expect(jobs).toHaveLength(1);expect([jobs[0].s0,jobs[0].s1].sort()).toEqual([aBefore,bVersion.id].sort());
  expect((await b.post('/api/invitations/'+invite.id,{action:'accept'})).status()).toBe(409);expect(response.job_id).toBe(jobs[0].id);
});
test('legacy friendlies endpoint cannot bypass recipient approval',async({installation})=>{
  const a=await installation.client(),b=await installation.client('beta'),outsider=await installation.client('gamma');
  const beta=(await json(await a.get('/api/dashboard'))).teams.find(t=>t.name==='تیم بتا');
  const invitation=await json(await a.post('/api/friendlies',{team_id:beta.id,accepted:true,action:'accept'}),201);
  expect(invitation.status).toBe('pending');expect(invitation.job_id).toBeNull();
  expect((await json(await a.get('/api/matches'))).total).toBe(0);
  expect((await a.post('/api/invitations/'+invitation.id,{action:'accept'})).status()).toBe(403);
  expect((await outsider.post('/api/invitations/'+invitation.id,{action:'accept'})).status()).toBe(403);
  expect((await json(await b.get('/api/matches'))).total).toBe(0);
  const accepted=await json(await b.post('/api/invitations/'+invitation.id,{action:'accept'}));
  expect((await waitJob(a,accepted.job_id)).status).toBe('completed');
  expect((await b.post('/api/invitations/'+invitation.id,{action:'accept'})).status()).toBe(409);
  expect((await json(await a.get('/api/matches'))).total).toBe(1);
});
for(const action of ['reject','cancel'])test(`invitation ${action} creates no match`,async({installation})=>{
  const a=await installation.client(),b=await installation.client('beta');const beta=(await json(await a.get('/api/dashboard'))).teams.find(t=>t.name==='تیم بتا');const invite=await json(await a.post('/api/invitations',{team_id:beta.id}),201);
  await json(await (action==='cancel'?a:b).post('/api/invitations/'+invite.id,{action}));expect((await json(await a.get('/api/matches'))).total).toBe(0);
});
test('duplicate invitation, self invitation, expired invitation and outsider response are rejected',async({installation})=>{
  const a=await installation.client(),b=await installation.client('beta'),outsider=await installation.client('gamma');const data=await json(await a.get('/api/dashboard'));const beta=data.teams.find(t=>t.name==='تیم بتا'),alpha=data.teams.find(t=>t.name==='تیم آلفا');
  expect((await a.post('/api/invitations',{team_id:alpha.id})).status()).toBe(400);
  const invite=await json(await a.post('/api/invitations',{team_id:beta.id}),201);expect((await b.post('/api/invitations',{team_id:alpha.id})).status()).toBe(409);expect((await outsider.post('/api/invitations/'+invite.id,{action:'accept'})).status()).toBe(403);
  installation.state({action:'expire_invite',id:invite.id});expect((await b.post('/api/invitations/'+invite.id,{action:'accept'})).status()).toBe(409);
});
test('simultaneous acceptance cannot duplicate a friendly match',async({installation})=>{
  const a=await installation.client(),b=await installation.client('beta');const beta=(await json(await a.get('/api/dashboard'))).teams.find(t=>t.name==='تیم بتا');const invite=await json(await a.post('/api/invitations',{team_id:beta.id}),201);
  const responses=await Promise.all([b.post('/api/invitations/'+invite.id,{action:'accept'}),b.post('/api/invitations/'+invite.id,{action:'accept'})]);expect(responses.map(r=>r.status()).sort()).toEqual([200,409]);expect((await json(await a.get('/api/matches'))).total).toBe(1);
});
test('local two-code Python/C++ game preserves the final submission',async({page,installation})=>{
  const team=await installation.client();const before=(await json(await team.get('/api/dashboard'))).active_submission_id;await login(page);await page.goto('/visualizer');await page.getByRole('button',{name:'بازی با دو کد',exact:true}).click();
  await page.locator('#code0').setInputFiles({name:'local.cpp',mimeType:'text/plain',buffer:Buffer.from(CPP)});await page.locator('#code1').setInputFiles({name:'local.py',mimeType:'text/plain',buffer:Buffer.from(PY)});await page.getByRole('button',{name:'بفرست به میدان'}).click();await expect(page.locator('.monster-card')).toHaveCount(6,{timeout:20000});expect((await json(await team.get('/api/dashboard'))).active_submission_id).toBe(before);
});
for(const codes of [[],[{}],[{},{} ,{}],['bad','bad']])test(`malformed local pair ${JSON.stringify(codes)}`,async({installation})=>{
  const team=await installation.client();expect((await team.post('/api/local',{codes})).status()).toBe(400);
});

for(const action of ['accept','reject','cancel'])test(`two-account invitation UI: ${action}`,async({page,browser,installation})=>{
  const otherContext=await browser.newContext({baseURL:installation.url});const other=await otherContext.newPage();
  try{
    await login(page);await visit(page,'practice','بازی دوستانه');await expect(page.locator('.list-row')).toHaveCount(0);await page.getByLabel('تیم مقابل',{exact:true}).selectOption({label:'تیم بتا'});await page.getByRole('button',{name:'فرستادن دعوت'}).click();await expect(page.locator('.list-row')).toHaveCount(1);
    if(action==='cancel'){await page.getByRole('button',{name:'لغو',exact:true}).click();await expect(page.locator('.list-row .badge')).toContainText('لغوشده')}
    else{
      await login(other,'beta');await visit(other,'practice','بازی دوستانه');await expect(other.locator('.list-row')).toContainText('تیم آلفا');await other.getByRole('button',{name:action==='accept'?'پذیرش':'رد',exact:true}).click();
      await expect(other.locator('.list-row .badge')).toContainText(action==='accept'?'پذیرفته‌شده':'ردشده');
      if(action==='accept'){await other.getByRole('link',{name:'دیدن بازی',exact:true}).click();await expect(other.locator('.monster-card')).toHaveCount(6,{timeout:15000})}
    }
    const client=await installation.client();expect((await json(await client.get('/api/matches'))).total).toBe(action==='accept'?1:0);
  }finally{await otherContext.close()}
});
test('minute invitation quota counts closed invitations too',async({installation})=>{
  const a=await installation.client(),b=await installation.client('beta');const beta=(await json(await a.get('/api/dashboard'))).teams.find(t=>t.name==='تیم بتا');
  for(let i=0;i<10;i++){const invite=await json(await a.post('/api/invitations',{team_id:beta.id}),201);await json(await b.post('/api/invitations/'+invite.id,{action:'reject'}))}
  expect((await a.post('/api/invitations',{team_id:beta.id})).status()).toBe(429);
});
