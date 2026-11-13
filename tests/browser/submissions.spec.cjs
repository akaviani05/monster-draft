const {test,expect,login,visit,json,PY,CPP}=require('./support/fixtures.cjs');

test('empty history, then Python file upload becomes the final code',async({page})=>{
  await login(page,'empty');await visit(page,'submissions','کدهای من');await expect(page.locator('.empty')).toContainText('هنوز کدی');
  await page.getByLabel('فایل کد',{exact:true}).setInputFiles({name:'first.py',mimeType:'text/plain',buffer:Buffer.from(PY)});
  await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(PY);await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();
  await expect(page.locator('.list-row').first()).toContainText('first.py');await expect(page.locator('.list-row').first()).toContainText('نسخهٔ نهایی');
});
test('C++ file is compiled and automatically selected',async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');await page.getByLabel('فایل کد',{exact:true}).setInputFiles({name:'robot.cpp',mimeType:'text/plain',buffer:Buffer.from(CPP)});
  await expect(page.getByLabel('زبان برنامه')).toHaveValue('cpp');await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();await expect(page.locator('.list-row').first()).toContainText('robot.cpp');
});
for(const [language,source,error] of [['python','if :','نگارشی'],['cpp','not c++','کامپایل']])test(`invalid ${language} preserves the final submission`,async({page})=>{
  await login(page);const before=await json(await page.request.get('/api/dashboard'));await visit(page,'submissions','کدهای من');await page.getByLabel('زبان برنامه').selectOption(language);await page.getByLabel('کد ربات',{exact:true}).fill(source);await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();await expect(page.locator('.inline-error')).toContainText(error);
  expect((await json(await page.request.get('/api/dashboard'))).active_submission_id).toBe(before.active_submission_id);
});
test('old final code can be selected and survives reload',async({page,installation})=>{
  const team=await installation.client();await json(await team.post('/api/submissions',{source:PY,language:'python',filename:'new.py'}),201);
  await login(page);await visit(page,'submissions','کدهای من');const before=await json(await team.get('/api/dashboard'));await page.getByRole('button',{name:'انتخاب نسخهٔ نهایی'}).first().click();await expect(page.locator('#toast')).toContainText('نسخهٔ نهایی');await page.reload();
  const after=await json(await team.get('/api/dashboard'));expect(after.active_submission_id).not.toBe(before.active_submission_id);await expect(page.locator('.badge').filter({hasText:'نسخهٔ نهایی'})).toHaveCount(1);
});
test('paginated history keeps old versions selectable',async({page,installation})=>{
  installation.state({action:'submission_history',count:30});await login(page);await visit(page,'submissions','کدهای من');await expect(page.locator('.list-row')).toHaveCount(25);await page.getByRole('button',{name:'نسخه‌های قدیمی‌تر'}).click();await expect(page.locator('.list-row')).toHaveCount(6);await expect(page.locator('.list-row').last()).toContainText('نسخهٔ نهایی');await page.getByRole('button',{name:'نسخه‌های جدیدتر'}).click();await expect(page.locator('.list-row')).toHaveCount(25);
});
test('download returns the exact stored source',async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');const event=page.waitForEvent('download');await page.locator('[data-action=download-code]').first().click();const download=await event;const fs=require('node:fs');expect(fs.readFileSync(await download.path(),'utf8')).toBe(PY);
});
test('oversized source and wrong filename extension are explained in the UI',async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');const input=page.getByLabel('فایل کد',{exact:true});await input.setInputFiles({name:'big.py',mimeType:'text/plain',buffer:Buffer.alloc(65537,32)});await expect(page.locator('#toast')).toContainText('۶۴');
  await input.setInputFiles({name:'bad.sh',mimeType:'text/plain',buffer:Buffer.from('echo hi')});await expect(page.locator('#toast')).toContainText('.py');
});
for(const body of [{source:''},{source:'x'.repeat(65537)},{source:PY,language:'bash'},{source:null},{source:[]},{source:'\ud800'}])test(`API rejects invalid upload ${JSON.stringify(body).slice(0,55)}`,async({installation})=>{
  const team=await installation.client();expect((await team.post('/api/submissions',body)).status()).toBe(400);
});
test('upload storage quota produces a visible error and keeps history',async({page,installation})=>{
  installation.state({action:'storage_full'});await login(page);await visit(page,'submissions','کدهای من');await page.getByLabel('کد ربات',{exact:true}).fill(PY);await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();await expect(page.locator('.inline-error')).toContainText('فضای');await expect(page.locator('.list-row')).toHaveCount(1);
});
test('minute submission quota returns 429 without new final code',async({installation})=>{
  const team=await installation.client();for(let i=0;i<9;i++)expect((await team.post('/api/submissions',{source:PY})).status()).toBe(201);
  expect((await team.post('/api/submissions',{source:PY})).status()).toBe(429);
});

test('daily submission quota rejects another upload',async({installation})=>{
  const team=await installation.client();installation.state({action:'submission_history',count:100});expect((await team.post('/api/submissions',{source:PY})).status()).toBe(429);
});
