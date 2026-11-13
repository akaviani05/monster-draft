const {test,expect,login,visit,json,waitJob}=require('./support/fixtures.cjs');

test('team profile persists, escapes student names and appears in admin search and opponent choices',async({page,installation})=>{
  await login(page);await visit(page,'profile','پروفایل تیم');
  await page.getByLabel('نام دانش‌آموز اول',{exact:true}).fill('دانش‌آموز نمونه');
  await page.getByLabel('نام دانش‌آموز دوم',{exact:true}).fill('<img src=x onerror=alert(1)>');
  await page.getByRole('button',{name:'ذخیرهٔ پروفایل',exact:true}).click();
  await expect(page.locator('#toast')).toContainText('ذخیره شد');await page.reload();
  await expect(page.getByLabel('نام دانش‌آموز اول',{exact:true})).toHaveValue('دانش‌آموز نمونه');
  const beta=await installation.client('beta');
  const team=(await json(await beta.get('/api/dashboard'))).teams.find(t=>t.name==='تیم آلفا');
  expect(team.display_name).toContain('(دانش‌آموز نمونه، <img');
  await page.getByRole('button',{name:'خروج از حساب'}).click();await login(page,'beta');
  await visit(page,'practice','بازی دوستانه');
  await expect(page.locator('#opponent option').filter({hasText:'دانش‌آموز نمونه'})).toHaveText(team.display_name);
  await expect(page.locator('#opponent img')).toHaveCount(0);
  await page.getByRole('button',{name:'خروج از حساب'}).click();await login(page,'admin');
  await page.goto('/admin#admin/teams');await page.getByLabel('جست‌وجوی تیم',{exact:true}).fill('دانش‌آموز نمونه');
  await expect(page.locator('#admin-team-body tr')).toHaveCount(1);
  await expect(page.locator('#admin-team-body')).toContainText('<img src=x onerror=alert(1)>');
  await expect(page.locator('#admin-team-body img')).toHaveCount(0);
});

test('selecting a team waits for approval before a real friendly updates the scoreboard',async({page,installation})=>{
  const a=await installation.client(),b=await installation.client('beta');
  const beforeA=(await json(await a.get('/api/dashboard'))).active_submission_id;
  const beforeB=(await json(await b.get('/api/dashboard'))).active_submission_id;
  await login(page);await visit(page,'practice','بازی دوستانه');
  await page.getByLabel('تیم مقابل',{exact:true}).selectOption({label:'تیم بتا'});
  const response=page.waitForResponse(r=>r.url().endsWith('/api/invitations')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'فرستادن دعوت',exact:true}).click();
  const invitation=await json(await response,201);expect(invitation.status).toBe('pending');expect(invitation.job_id).toBeNull();
  await expect(page.locator('.list-row .badge')).toHaveText('در انتظار تأیید تیم مقابل');
  expect((await json(await a.get('/api/matches'))).total).toBe(0);
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    if(width===390)await expect(page.locator('.sidebar')).not.toBeInViewport();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    await page.locator('.list-row').screenshot({path:test.info().outputPath(`waiting-approval-${width}.png`)});
  }
  const accepted=await json(await b.post('/api/invitations/'+invitation.id,{action:'accept'}));
  const job={id:accepted.job_id};const done=await waitJob(a,job.id);expect(done.status).toBe('completed');
  const row=(await json(await a.get('/api/matches'))).items.find(j=>j.id===job.id);
  expect([row.s0,row.s1].sort()).toEqual([beforeA,beforeB].sort());
  const replay=await json(await b.get(`/api/matches/${job.id}/replay`));expect(replay.turns).toHaveLength(30);
  expect(replay.result.reason).toBe('completed');
  await visit(page,'scoreboard','جدول امتیازها');
  await expect(page.locator('tbody tr')).toHaveCount(4);
  const rows=(await json(await a.get('/api/scoreboard'))).items;
  expect(rows.reduce((n,r)=>n+r.played,0)).toBe(2);
  await expect(page.locator('tbody tr').first()).toContainText(rows[0].display_name);
});

test('profile and friendly mutations require CSRF and scoreboard requires authentication',async({installation})=>{
  const a=await installation.client(),admin=await installation.client('admin');
  const before=await json(await a.get('/api/profile'));
  expect((await a.post('/api/profile',{student1:'a',student2:'b'},{headers:{'X-CSRF-Token':''}})).status()).toBe(403);
  expect(await json(await a.get('/api/profile'))).toEqual(before);
  expect((await a.post('/api/profile',{student1:'a',student2:'b',id:999})).status()).toBe(400);
  expect((await admin.post('/api/profile',{student1:'a',student2:'b'})).status()).toBe(403);
  const beta=(await json(await a.get('/api/dashboard'))).teams.find(t=>t.name==='تیم بتا');
  expect((await a.post('/api/friendlies',{team_id:beta.id},{headers:{'X-CSRF-Token':''}})).status()).toBe(403);
  expect((await a.get('/api/scoreboard?tournament=99999')).status()).toBe(404);
  expect((await a.get('/api/scoreboard?tournament=bad')).status()).toBe(400);
  const anonymous=await installation.client(null);expect((await anonymous.get('/api/scoreboard')).status()).toBe(401);
});

test('scoreboard selector keeps friendlies separate from each tournament including empty events',async({page,installation})=>{
  const a=await installation.client(),admin=await installation.client('admin');
  const teams=(await json(await a.get('/api/dashboard'))).teams.filter(t=>t.submission_id).map(t=>t.id);
  const first=await json(await admin.post('/api/admin/tournaments',{name:'جام اول',teams,starts_at:Date.now()/1000+3600,paired:false}),201);
  const second=await json(await admin.post('/api/admin/tournaments',{name:'جام دوم',teams:teams.slice(0,2),starts_at:Date.now()/1000+3600,paired:false}),201);
  await login(page);await visit(page,'scoreboard','جدول امتیازها');
  await expect(page.locator('tbody tr')).toHaveCount(4);
  await page.getByLabel('رقابت',{exact:true}).selectOption(String(first.id));
  await expect(page.locator('tbody tr')).toHaveCount(3);
  await expect(page.locator('[data-standings=ranked] tbody tr')).toHaveCount(0);
  await expect(page.locator('[data-standings=provisional] tbody tr').first().locator('td').nth(1)).toHaveText('۰');
  await page.getByLabel('رقابت',{exact:true}).selectOption(String(second.id));
  await expect(page.locator('tbody tr')).toHaveCount(2);
  await page.getByLabel('رقابت',{exact:true}).selectOption('');
  await expect(page.locator('tbody tr')).toHaveCount(4);
});

test('profile transport failure keeps entered names for retry',async({page})=>{
  await login(page);await visit(page,'profile','پروفایل تیم');
  await page.getByLabel('نام دانش‌آموز اول',{exact:true}).fill('نام نمونه');
  await page.route('**/api/profile',route=>route.abort('failed'));
  await page.getByRole('button',{name:'ذخیرهٔ پروفایل',exact:true}).click();
  await expect(page.locator('.inline-error')).not.toBeEmpty();
  await expect(page.getByLabel('نام دانش‌آموز اول',{exact:true})).toHaveValue('نام نمونه');
  await page.unroute('**/api/profile');
  await page.getByRole('button',{name:'ذخیرهٔ پروفایل',exact:true}).click();
  await expect(page.locator('#toast')).toContainText('ذخیره شد');
});

test('a third real friendly promotes teams into the win-ratio table',async({page,installation})=>{
  const a=await installation.client(),b=await installation.client('beta');const before=await json(await a.get('/api/dashboard'));
  const beta=before.teams.find(t=>t.name==='تیم بتا');
  for(let i=0;i<2;i++){
    const invitation=await json(await a.post('/api/friendlies',{team_id:beta.id}),201);
    const accepted=await json(await b.post('/api/invitations/'+invitation.id,{action:'accept'}));
    expect((await waitJob(a,accepted.job_id)).status).toBe('completed');
  }
  await login(page);await visit(page,'scoreboard','جدول امتیازها');
  await expect(page.locator('[data-standings=ranked] tbody tr')).toHaveCount(0);
  await expect(page.locator('[data-standings=provisional] tbody tr')).toHaveCount(4);
  const third=await json(await a.post('/api/friendlies',{team_id:beta.id}),201);
  const thirdAccepted=await json(await b.post('/api/invitations/'+third.id,{action:'accept'}));
  expect((await waitJob(a,thirdAccepted.job_id)).status).toBe('completed');
  await page.getByRole('button',{name:'به‌روزرسانی',exact:true}).click();
  await expect(page.locator('[data-standings=ranked] tbody tr')).toHaveCount(2);
  await expect(page.locator('[data-standings=provisional] tbody tr')).toHaveCount(2);
  const rows=(await json(await a.get('/api/scoreboard'))).items.filter(r=>r.eligible);
  expect(rows.every(r=>r.played===3&&r.win_ratio===r.wins/r.played)).toBe(true);
  expect(rows[0].win_ratio).toBeGreaterThanOrEqual(rows[1].win_ratio);
  for(let i=0;i<2;i++){
    const row=page.locator('[data-standings=ranked] tbody tr').nth(i);
    await expect(row.locator('td').nth(1)).toHaveText(rows[i].display_name);
    await expect(row.locator('td').nth(3)).toHaveText(new Intl.NumberFormat('fa-IR',{style:'percent',maximumFractionDigits:1}).format(rows[i].wins/3));
  }
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    if(width===390)await expect(page.locator('.sidebar')).not.toBeInViewport();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    const percent=await page.locator('[data-standings=ranked] tbody tr').first().locator('td').nth(3).boundingBox();
    expect(percent.x).toBeGreaterThanOrEqual(0);expect(percent.x+percent.width).toBeLessThanOrEqual(width);
    await page.screenshot({path:test.info().outputPath(`win-ratio-${width}.png`),fullPage:true});
  }
});

test('profile and scoreboard desktop and mobile review',async({page})=>{
  await login(page);await visit(page,'profile','پروفایل تیم');
  await page.getByLabel('نام دانش‌آموز اول',{exact:true}).fill('دانش‌آموز اول');
  await page.getByLabel('نام دانش‌آموز دوم',{exact:true}).fill('دانش‌آموز دوم');
  await page.getByRole('button',{name:'ذخیرهٔ پروفایل',exact:true}).click();
  await expect(page.locator('#toast')).toContainText('ذخیره شد');
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    for(const [route,title] of [['profile','پروفایل تیم'],['scoreboard','جدول امتیازها']]){
      await visit(page,route,title);await page.evaluate(()=>document.fonts.ready);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
      await page.screenshot({path:test.info().outputPath(`${route}-${width}.png`),fullPage:true});
    }
  }
});
