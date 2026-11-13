const {test,expect,login,visit,json,PASSWORD,PY,CPP,ROOT}=require('./support/fixtures.cjs');
const fs=require('node:fs'),path=require('node:path');

for(const [filename,language,source] of [['ROBOT.CPP','cpp',CPP],['ROBOT.PY','python',PY]]){
  test(`uppercase ${filename} upload selects the correct compiler and final version`,async({page})=>{
    await login(page);await visit(page,'submissions','کدهای من');
    await page.getByLabel('فایل کد',{exact:true}).setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from(source)});
    await expect(page.getByLabel('زبان برنامه')).toHaveValue(language);
    const saved=page.waitForResponse(r=>r.url().endsWith('/api/submissions')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();const version=await json(await saved,201);
    expect(version.language).toBe(language);expect(version.filename).toBe(filename);
    await expect(page.locator('.list-row').first()).toContainText(filename);
    expect((await json(await page.request.get('/api/dashboard'))).active_submission_id).toBe(version.id);
  });
}

test('rapid navigation followed by file selection preserves source and language',async({page})=>{
  await login(page);const nav=page.getByRole('navigation',{name:'منوی اصلی'});
  for(let attempt=0;attempt<4;attempt++){
    const source=attempt%2?PY:CPP,language=attempt%2?'python':'cpp',filename='draft.'+(attempt%2?'py':'cpp');
    const loaded=page.waitForResponse(r=>r.url().endsWith('/api/submissions?page=1'));
    await nav.getByRole('link',{name:'کدهای من',exact:true}).click();await expect(page.locator('h1')).toHaveText('کدهای من');
    await page.getByLabel('فایل کد',{exact:true}).setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from(source)});
    await json(await loaded);await expect(page.getByLabel('زبان برنامه')).toHaveValue(language);await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(source);
    await nav.getByRole('link',{name:'بازی دوستانه',exact:true}).click();await expect(page.locator('h1')).toHaveText('بازی دوستانه');
  }
});

test('a new upload from older history returns to the newest page and shows its final version',async({page,installation})=>{
  installation.state({action:'submission_history',count:30});await login(page);await visit(page,'submissions','کدهای من');
  await page.getByRole('button',{name:'نسخه‌های قدیمی‌تر'}).click();await expect(page.locator('.list-row')).toHaveCount(6);
  await page.getByLabel('کد ربات',{exact:true}).fill(PY);
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/submissions')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();const version=await json(await saved,201);
  await expect(page.getByRole('button',{name:'نسخه‌های جدیدتر'})).toBeDisabled();
  await expect(page.locator('.list-row').first()).toContainText('نسخهٔ نهایی');
  expect((await json(await page.request.get('/api/submissions'))).items[0].id).toBe(version.id);
});

test('logging into another team in the same document resets history pagination',async({page,installation})=>{
  installation.state({action:'submission_history',count:30});await login(page);await visit(page,'submissions','کدهای من');
  await page.getByRole('button',{name:'نسخه‌های قدیمی‌تر'}).click();await expect(page.locator('.list-row')).toHaveCount(6);
  await page.getByRole('button',{name:'خروج از حساب'}).click();await expect(page.locator('#login-form')).toBeVisible();
  await page.getByLabel('نام کاربری تیم').fill('beta');await page.getByLabel('رمز عبور',{exact:true}).fill(PASSWORD);
  await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();
  await expect(page.locator('.list-row')).toHaveCount(1);await expect(page.locator('.list-row')).toContainText('نسخهٔ نهایی');
  await expect(page.getByRole('button',{name:'نسخه‌های جدیدتر'})).toBeDisabled();
});

test('replay controls retain keyboard focus across consecutive steps',async({page})=>{
  await page.goto('/visualizer');await page.getByRole('button',{name:'دیدن بازی نمونه',exact:true}).click();
  const next=page.getByRole('button',{name:'انتخاب بعدی',exact:true});await next.focus();
  for(let turn=1;turn<=3;turn++){
    await page.keyboard.press('Enter');await expect(page.locator('#timeline')).toHaveValue(String(turn));await expect(next).toBeFocused();
  }
});

test('local two-code form accepts uppercase Python and C++ extensions',async({page})=>{
  await login(page);const before=(await json(await page.request.get('/api/dashboard'))).active_submission_id;
  await page.goto('/visualizer');await page.getByRole('button',{name:'بازی با دو کد',exact:true}).click();
  for(const [slot,filename,source] of [[0,'ONE.CPP',CPP],[1,'TWO.PY',PY]])await page.locator('#code'+slot).setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from(source)});
  const queued=page.waitForResponse(r=>r.url().endsWith('/api/local')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'بفرست به میدان',exact:true}).click();const job=await json(await queued,201);
  await expect(page).toHaveURL(new RegExp('/visualizer\\?match='+job.id+'$'));
  await expect(page.locator('.monster-card')).toHaveCount(6,{timeout:15000});
  expect((await json(await page.request.get('/api/dashboard'))).active_submission_id).toBe(before);
});

test('malformed replay cards are rejected without replacing the current game',async({page})=>{
  await page.goto('/visualizer');await page.getByRole('button',{name:'دیدن بازی نمونه',exact:true}).click();
  const sample=JSON.parse(fs.readFileSync(path.join(ROOT,'web/assets/example.json'),'utf8'));
  // The last refill has no later market snapshot; validate its type directly.
  const malformed=structuredClone(sample);malformed.turns.at(-1).refill=[malformed.turns.at(-1).refill];
  await page.locator('#log-file').setInputFiles({name:'nested.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(malformed))});
  await expect(page.locator('#toast')).toContainText('سازگار نیست');await expect(page.locator('.monster-card b')).toHaveText(sample.initial_market);
  await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();await expect(page.locator('#timeline')).toHaveValue('1');
});

for(const [role,route,title] of [['alpha','submissions','کدهای من'],['admin','admin/settings','تنظیمات اجرا']]){
  test(`${role} skip link focuses the current page without changing the route`,async({page})=>{
    await login(page,role);await visit(page,route,title);const url=page.url();
    await page.locator('a.skip').focus();await page.keyboard.press('Enter');
    await expect(page.locator('#main')).toBeFocused();await expect(page.locator('h1')).toHaveText(title);await expect(page).toHaveURL(url);
  });
}

for(const [name,url,data] of [
  ['login password','/api/login',{username:'alpha',password:'bad\ud800password'}],
  ['team name','/api/admin/teams',{username:'unicode-team',name:'bad\ud800name',password:PASSWORD}],
  ['reset password','/api/admin/teams/2',{password:'bad\ud800password'}],
  ['source filename','/api/submissions',{source:PY,filename:'bad\ud800.py'}],
  ['nested local filename','/api/local',{codes:[{source:PY,filename:'bad\ud800.py'},{source:PY}]}],
])test(`invalid Unicode in ${name} returns a validation error without breaking the server`,async({installation})=>{
  const admin=await installation.client('admin');const response=await admin.post(url,data);
  expect(response.status()).toBe(400);expect((await response.json()).error).toEqual(expect.any(String));
  expect((await admin.get('/api/admin/overview')).status()).toBe(200);
});

test('non-ASCII forged CSRF tokens are rejected with 403',async({installation})=>{
  const team=await installation.client();expect((await team.post('/api/practice',{bot:'greedy'},{headers:{'X-CSRF-Token':'forged-é'}})).status()).toBe(403);
  expect((await json(await team.get('/api/matches'))).total).toBe(0);
});

test('resource IDs outside the database integer range are rejected without internal errors',async({installation})=>{
  const admin=await installation.client('admin'),huge='9'.repeat(40);
  for(const url of ['/api/submissions/','/api/matches/','/api/tournaments/'])expect((await admin.get(url+huge)).status()).toBe(404);
  expect((await admin.get('/api/matches?tournament='+huge)).status()).toBe(400);
  expect((await admin.post('/api/admin/teams/'+huge,{active:false})).status()).toBe(404);
  expect((await admin.get('/api/admin/overview')).status()).toBe(200);
});
