const {test,expect,login,visit,json,waitJob,PY,CPP}=require('./support/fixtures.cjs');

for(const [language,source,filename] of [['python',PY,'draft.py'],['cpp',CPP,'draft.cpp']]){
  test(`submission editor tests ${language} privately and steps through real stdin and stdout`,async({page,installation})=>{
    const team=await installation.client(),other=await installation.client('beta');
    const before=(await json(await team.get('/api/dashboard'))).active_submission_id;
    await login(page);await visit(page,'submissions','کدهای من');
    await page.getByLabel('فایل کد آزمایش',{exact:true}).setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from(source)});
    await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(source);
    await expect(page.getByLabel('زبان برنامه',{exact:true})).toHaveValue(language);
    await page.getByLabel('ربات حریف آزمایش',{exact:true}).selectOption('random');
    const response=page.waitForResponse(r=>r.url().endsWith('/api/debug')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();
    const job=await json(await response,201);expect((await waitJob(team,job.id)).status).toBe('completed');
    await expect(page.locator('#debug-panel')).toContainText('اجرای ۳۰ انتخاب کامل شد');
    await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(source);
    const report=await json(await team.get('/api/debug/'+job.id));
    expect(report.result.reason).toBe('completed');expect(report.events.filter(e=>e.stream==='stdout').map(e=>e.text).join('').trim().split('\n')).toHaveLength(15);
    await expect(page.locator('[data-debug-stream=stdin]')).toContainText(report.seat===0?'YOURTURN':'OPPTURN');
    await page.getByRole('button',{name:'گام بعد',exact:true}).click();await expect(page.locator('#debug-panel')).toContainText('نوبت ۲');
    await page.getByRole('button',{name:'گام قبل',exact:true}).click();await page.getByRole('button',{name:'گام قبل',exact:true}).click();
    const replay=await json(await team.get(`/api/matches/${job.id}/replay`));
    await expect(page.locator('[data-debug-stream=stdin]')).toHaveText(String(replay.banner));
    expect((await other.get('/api/debug/'+job.id)).status()).toBe(404);
    expect((await json(await team.get('/api/dashboard'))).active_submission_id).toBe(before);
    expect((await json(await team.get('/api/dashboard'))).stats.played).toBe(0);
    const popup=page.waitForEvent('popup');await page.getByRole('link',{name:'دیدن بازپخش همین آزمایش',exact:true}).click();
    const replayPage=await popup;await expect(replayPage.locator('.monster-card')).toHaveCount(6);await replayPage.close();
    await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(source);
  });
}

for(const [name,source,language,error] of [
  ['Python syntax','def broken(:','python','خطای نگارشی'],
  ['C++ compilation','int main( {','cpp','کامپایل'],
])test(`test area displays ${name} errors and preserves the editor`,async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');
  await page.getByLabel('زبان برنامه',{exact:true}).selectOption(language);
  await page.getByLabel('کد ربات',{exact:true}).fill(source);
  await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();
  await expect(page.locator('#debug-error')).toContainText(error);
  await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(source);
  await expect(page.getByRole('button',{name:'آزمایش کد فعلی',exact:true})).toBeEnabled();
});

test('interactive file picker rejects unsupported and oversized files without replacing the draft',async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');await page.getByLabel('کد ربات',{exact:true}).fill(PY);
  for(const [name,content] of [['invalid.txt','pass'],['large.py','x'.repeat(65537)]]){
    await page.getByLabel('فایل کد آزمایش',{exact:true}).setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from(content)});
    await expect(page.locator('#debug-error')).toContainText('حداکثر ۶۴ کیلوبایت');
    await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(PY);
  }
  await page.getByLabel('فایل کد آزمایش',{exact:true}).setInputFiles({name:'valid.py',mimeType:'text/plain',buffer:Buffer.from(PY)});
  await expect(page.locator('#debug-error')).toHaveCount(0);
  await expect(page.getByLabel('فایل کد آزمایش',{exact:true})).toHaveValue(/valid\.py$/);
});

test('runtime traceback is shown literally and remains private to the submitting team',async({page,installation})=>{
  const team=await installation.client(),admin=await installation.client('admin');
  await login(page);await visit(page,'submissions','کدهای من');
  await page.getByLabel('کد ربات',{exact:true}).fill('input()\nraise RuntimeError("<img src=x onerror=alert(1)>")\n');
  const response=page.waitForResponse(r=>r.url().endsWith('/api/debug')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();const job=await json(await response,201);
  await waitJob(team,job.id);await expect(page.locator('[data-debug-stream=stderr]')).toContainText('RuntimeError: <img');
  await expect(page.locator('#debug-panel img')).toHaveCount(0);
  expect((await admin.get('/api/debug/'+job.id)).status()).toBe(404);
  const replay=await json(await team.get(`/api/matches/${job.id}/replay`));expect(replay.stderr).toBeUndefined();expect(replay._diagnostics).toBeUndefined();
  await page.locator('#debug-panel').screenshot({path:test.info().outputPath('runtime-error.png')});
});

test('queue waiting, CSRF, role, opponent and upload validation use real HTTP checks',async({page,installation})=>{
  const team=await installation.client(),admin=await installation.client('admin'),anon=await installation.client(null);
  const payload={source:PY,bot:'random',language:'python'};
  expect((await anon.post('/api/debug',payload)).status()).toBe(401);
  expect((await admin.post('/api/debug',payload)).status()).toBe(403);
  expect((await team.post('/api/debug',payload,{headers:{'X-CSRF-Token':''}})).status()).toBe(403);
  expect((await team.post('/api/debug',{...payload,bot:'missing'})).status()).toBe(400);
  expect((await team.post('/api/debug',{...payload,source:'x'.repeat(65537)})).status()).toBe(400);
  await json(await admin.post('/api/admin/worker',{paused:true}),201);
  await login(page);await visit(page,'submissions','کدهای من');await page.getByLabel('کد ربات',{exact:true}).fill(PY);
  const response=page.waitForResponse(r=>r.url().endsWith('/api/debug')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();const job=await json(await response,201);
  await expect(page.locator('#debug-panel')).toContainText('در صف');
  await expect(page.getByRole('button',{name:'آزمایش کد فعلی',exact:true})).toBeDisabled();
  expect((await team.get('/api/debug/'+job.id)).status()).toBe(409);
  await json(await admin.post('/api/admin/worker',{paused:false}),201);await waitJob(team,job.id);
  await expect(page.locator('#debug-panel')).toContainText('اجرای ۳۰ انتخاب کامل شد');
});

test('transport failure preserves the draft and allows a real retry',async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');await page.getByLabel('کد ربات',{exact:true}).fill(PY);
  await page.route('**/api/debug',route=>route.abort('failed'));
  await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();await expect(page.locator('#debug-error')).not.toBeEmpty();
  await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue(PY);await page.unroute('**/api/debug');
  await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();await expect(page.locator('#debug-panel')).toContainText('اجرای ۳۰ انتخاب کامل شد');
});

for(const [name,action,reason] of [['invalid output','print(9, flush=True)','invalid_output'],['waiting for extra YOURTURN input','input()','turn_timeout']]){
  test(`diagnostics explain ${name} using the actual process streams`,async({page,installation})=>{
    const source=`TURNS = 30\ninput()\nfor i in range(TURNS):\n    header = input()\n    cards = [input() for j in range(6)]\n    if header == "YOURTURN":\n        ${action}\n    else:\n        input()\n`;
    const client=await installation.client();await login(page);await visit(page,'submissions','کدهای من');
    await page.getByLabel('کد ربات',{exact:true}).fill(source);
    const response=page.waitForResponse(r=>r.url().endsWith('/api/debug')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();const job=await json(await response,201);
    await waitJob(client,job.id);const report=await json(await client.get('/api/debug/'+job.id));expect(report.result.reason).toBe(reason);
    await expect(page.locator('[data-debug-stream=stdin]')).toContainText('YOURTURN');
    if(reason==='invalid_output')await expect(page.locator('[data-debug-stream=stdout]')).toContainText('9');
    else await expect(page.locator('#debug-panel')).toContainText('input اضافه');
  });
}

for(const width of [390,1440])test(`interactive test area fits ${width}px and captures the result`,async({page})=>{
  await page.setViewportSize({width,height:1000});await login(page);await visit(page,'submissions','کدهای من');
  await page.getByLabel('کد ربات',{exact:true}).fill(PY);await page.getByRole('button',{name:'آزمایش کد فعلی',exact:true}).click();
  await expect(page.locator('#debug-panel')).toContainText('اجرای ۳۰ انتخاب کامل شد');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.locator('#debug-panel').screenshot({path:test.info().outputPath(`debug-${width}.png`)});
});
