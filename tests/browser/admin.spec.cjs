const {test,expect,login,visit,json,PASSWORD}=require('./support/fixtures.cjs');
const fs=require('node:fs');

test('administrator downloads all submissions and selected finals',async({page,installation})=>{
  const team=await installation.client();
  for(const scope of ['all','final'])expect((await team.get('/api/admin/submissions.zip?scope='+scope)).status()).toBe(403);
  await login(page,'admin');await visit(page,'admin/teams','مدیریت تیم‌ها');
  for(const [scope,label] of [['all','دریافت همهٔ ارسال‌ها (ZIP)'],['final','دریافت کدهای نهایی (ZIP)']]){
    const pending=page.waitForEvent('download');
    await page.getByRole('link',{name:label,exact:true}).click();
    const download=await pending;
    expect(download.suggestedFilename()).toBe('submissions-'+scope+'.zip');
    expect(fs.readFileSync(await download.path()).subarray(0,4).toString('hex')).toBe('504b0304');
  }
});

test('team creation, search, rename, status filters and password reset',async({page,installation})=>{
  await login(page,'admin');await visit(page,'admin/teams','مدیریت تیم‌ها');await page.getByRole('button',{name:'ثبت تیم جدید',exact:true}).click();
  await page.getByLabel('نام نمایشی تیم').fill('تیم جدید');await page.getByLabel('نام کاربری انگلیسی').fill('created-team');await page.getByLabel('رمز اولیه').fill('NewFixturePassword!');await page.getByRole('button',{name:'ساخت حساب تیم'}).click();
  await expect(page.locator('dialog')).not.toBeVisible();await page.getByLabel('جست‌وجوی تیم').fill('created-team');await expect(page.locator('tbody tr')).toHaveCount(1);await expect(page.locator('tbody')).toContainText('تیم جدید');
  await page.getByRole('button',{name:'ویرایش نام',exact:true}).click();await page.getByLabel('نام نمایشی تیم').fill('تیم ویرایش‌شده');await page.getByRole('button',{name:'ذخیرهٔ نام تیم',exact:true}).click();await expect(page.locator('tbody')).toContainText('تیم ویرایش‌شده');
  await page.getByRole('button',{name:'غیرفعال کردن',exact:true}).click();await page.getByLabel('وضعیت تیم',{exact:true}).selectOption('inactive');await expect(page.locator('tbody tr')).toHaveCount(1);await page.getByRole('button',{name:'فعال کردن',exact:true}).click();await page.getByLabel('وضعیت تیم',{exact:true}).selectOption('active');
  await page.getByRole('button',{name:'تغییر رمز',exact:true}).click();await page.getByLabel('رمز تازه').fill('UpdatedFixturePassword!');await page.getByRole('button',{name:'ثبت رمز تازه',exact:true}).click();await expect(page.locator('dialog')).not.toBeVisible();
  await installation.client('created-team','UpdatedFixturePassword!');
});
test('duplicate team username returns a visible form error',async({page})=>{
  await login(page,'admin');await visit(page,'admin/teams','مدیریت تیم‌ها');await page.getByRole('button',{name:'ثبت تیم جدید',exact:true}).click();await page.getByLabel('نام نمایشی تیم').fill('تکراری');await page.getByLabel('نام کاربری انگلیسی').fill('alpha');await page.getByLabel('رمز اولیه').fill(PASSWORD);await page.getByRole('button',{name:'ساخت حساب تیم'}).click();await expect(page.locator('dialog .inline-error')).toContainText('قبلاً');
});
test('administrator-created passwords preserve leading and trailing spaces',async({installation})=>{
  const admin=await installation.client('admin');await json(await admin.post('/api/admin/teams',{username:'spaced',name:'تیم فاصله',password:'  Fixture password  '}),201);await installation.client('spaced','  Fixture password  ');
});
for(const username of ['ab','space name','فارسی','a'.repeat(33)])test(`reject invalid username ${username}`,async({installation})=>{
  const admin=await installation.client('admin');expect((await admin.post('/api/admin/teams',{username,name:'Test',password:PASSWORD})).status()).toBe(400);
});
test('team-name HTML is rendered as text and never executed',async({page,installation})=>{
  const admin=await installation.client('admin');await admin.post('/api/admin/teams',{username:'escaped',name:'<img src=x onerror=alert(1)>',password:PASSWORD});let dialogs=0;page.on('dialog',d=>{dialogs++;d.dismiss()});
  await login(page,'admin');await visit(page,'admin/teams','مدیریت تیم‌ها');await page.getByLabel('جست‌وجوی تیم').fill('escaped');await expect(page.locator('tbody')).toContainText('<img src=x onerror=alert(1)>');await expect(page.locator('tbody img')).toHaveCount(0);expect(dialogs).toBe(0);
});
test('no-result search, ready and missing-source filters',async({page})=>{
  await login(page,'admin');await visit(page,'admin/teams','مدیریت تیم‌ها');await page.getByLabel('جست‌وجوی تیم').fill('no-such-team');await expect(page.locator('tbody')).toContainText('پیدا نشد');await page.getByLabel('جست‌وجوی تیم').fill('');await page.getByLabel('وضعیت تیم',{exact:true}).selectOption('ready');await expect(page.locator('tbody tr')).toHaveCount(3);await page.getByLabel('وضعیت تیم',{exact:true}).selectOption('missing');await expect(page.locator('tbody tr')).toHaveCount(1);
});
test('worker capacity and pause persist through server restart',async({page,installation})=>{
  await login(page,'admin');await visit(page,'admin/settings','تنظیمات اجرا');await page.getByLabel('ظرفیت بازی‌های هم‌زمان').fill('1');await page.getByRole('checkbox').check();await page.getByRole('button',{name:'ذخیرهٔ تنظیمات',exact:true}).click();await expect(page.locator('#toast')).toContainText('ذخیره');
  await installation.restart();await page.reload();await expect(page.getByLabel('ظرفیت بازی‌های هم‌زمان')).toHaveValue('1');await expect(page.getByRole('checkbox')).toBeChecked();
});
for(const body of [{slots:0},{slots:129},{slots:true},{slots:'2'},{paused:'true'},{command:'ls'},{}])test(`invalid worker settings ${JSON.stringify(body)}`,async({installation})=>{
  const admin=await installation.client('admin');expect((await admin.post('/api/admin/worker',body)).status()).toBe(400);
});
test('pause holds queued games, resume drains them, and completed rows replay',async({page,installation})=>{
  const admin=await installation.client('admin'),team=await installation.client();await json(await admin.post('/api/admin/worker',{paused:true,slots:1}),201);const job=await json(await team.post('/api/practice',{bot:'greedy'}),201);
  await login(page,'admin');await visit(page,'admin/queue','صف مسابقه‌ها');await page.getByLabel('وضعیت مسابقه').selectOption('queued');await expect(page.locator('tbody tr')).toHaveCount(1);await expect(page.getByRole('button',{name:'ادامهٔ دریافت بازی‌ها',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'ادامهٔ دریافت بازی‌ها',exact:true}).click();await expect(page.getByRole('button',{name:'توقف دریافت بازی‌ها',exact:true})).toBeVisible();
  const filtered=page.waitForResponse(r=>r.url().includes('/api/admin/queue?')&&r.url().includes('status=completed'));
  await page.getByLabel('وضعیت مسابقه').selectOption('completed');await json(await filtered);
  const replay=page.getByRole('link',{name:'بازپخش',exact:true});await expect(replay).toHaveAttribute('href','/visualizer?match='+job.id,{timeout:15000});await expect(page.locator('tbody tr')).toHaveCount(1);
  await replay.click();await expect(page.locator('.monster-card')).toHaveCount(6);
});
test('retry preserves failed game identity and returns it to the paused queue',async({page,installation})=>{
  const admin=await installation.client('admin');await admin.post('/api/admin/worker',{paused:true});const failed=installation.state({action:'failed_job'});
  await login(page,'admin');await visit(page,'admin/queue','صف مسابقه‌ها');await page.getByLabel('وضعیت مسابقه').selectOption('failed');await expect(page.locator('tbody')).toContainText('خطای زیرساخت');await page.getByRole('button',{name:'تکرار خطای زیرساخت',exact:true}).click();await expect(page.locator('.empty')).toContainText('مسابقه‌ای');await page.getByLabel('وضعیت مسابقه').selectOption('queued');await expect(page.locator('tbody tr')).toHaveCount(1);
  expect((await json(await admin.get('/api/admin/queue?status=queued'))).items[0].id).toBe(failed.id);
});
test('queue pagination shows all results without duplication',async({page,installation})=>{
  installation.state({action:'completed_jobs',count:30});await login(page,'admin');await visit(page,'admin/queue','صف مسابقه‌ها');await expect(page.locator('tbody tr')).toHaveCount(25);const first=await page.locator('tbody').innerText();await page.getByRole('button',{name:'صفحهٔ بعد',exact:true}).click();await expect(page.locator('tbody tr')).toHaveCount(5);expect(await page.locator('tbody').innerText()).not.toBe(first);await page.getByRole('button',{name:'صفحهٔ قبل',exact:true}).click();await expect(page.locator('tbody tr')).toHaveCount(25);
});
