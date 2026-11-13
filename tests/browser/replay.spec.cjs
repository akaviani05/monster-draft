const {test,expect,login,json,waitJob,PY,ROOT}=require('./support/fixtures.cjs');
const fs=require('node:fs'),path=require('node:path');
const sample=JSON.parse(fs.readFileSync(path.join(ROOT,'web/assets/example.json'),'utf8'));
const upload=async(page,value)=>page.locator('#log-file').setInputFiles({name:'replay.json',mimeType:'application/json',buffer:Buffer.from(typeof value==='string'?value:JSON.stringify(value))});
async function example(page){await page.goto('/visualizer');await page.getByRole('button',{name:'دیدن بازی نمونه',exact:true}).click();await expect(page.locator('.monster-card')).toHaveCount(6)}

test('empty viewer is usable without login and code execution requires an account',async({page})=>{
  await page.goto('/visualizer');await expect(page.locator('.viewer-empty')).toBeVisible();await expect(page.getByRole('button',{name:'دریافت بازپخش',exact:true})).toBeDisabled();await page.getByRole('button',{name:'بازی با دو کد',exact:true}).click();await expect(page.locator('#toast')).toContainText('وارد');
});
test('file replay uses its exact six-slot market, hands and scores',async({page})=>{
  await page.goto('/visualizer');await upload(page,sample);await expect(page.locator('.monster-card b')).toHaveText(sample.initial_market);
  await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();await expect(page.locator('.monster-card b')).toHaveText(sample.turns[0].market);await expect(page.locator('.monster-card.selected b')).toHaveText(sample.turns[0].card);await expect(page.locator('.collection .mini-card')).toHaveCount(1);
  for(let i=1;i<30;i++)await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();await expect(page.locator('.result-callout')).toBeVisible();await expect(page.locator('.collection .mini-card')).toHaveCount(30);await expect(page.locator('.players-score b')).toHaveText(sample.result.scores.map(s=>new Intl.NumberFormat('fa-IR').format(s.total)));
});
test('manual analysis advances exactly one turn and clamps at both ends',async({page})=>{
  await example(page);await page.getByLabel('روش نمایش').selectOption('manual');await expect(page.getByRole('button',{name:'پخش',exact:true})).toBeDisabled();await page.getByRole('button',{name:'انتخاب قبلی',exact:true}).click();await expect(page.locator('#timeline')).toHaveValue('0');
  await page.getByRole('button',{name:'نمایش نوبت بعد',exact:true}).click();await expect(page.locator('#timeline')).toHaveValue('1');for(let i=1;i<30;i++)await page.getByRole('button',{name:'نمایش نوبت بعد',exact:true}).click();await expect(page.getByRole('button',{name:'نمایش نوبت بعد',exact:true})).toBeDisabled();await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();await expect(page.locator('#timeline')).toHaveValue('30');await page.getByRole('button',{name:'بازگشت به آغاز',exact:true}).click();await expect(page.locator('#timeline')).toHaveValue('0');
});
test('chosen card, market and acting player stay aligned through playback and seeking',async({page})=>{
  await page.clock.install();await example(page);await page.clock.pauseAt(new Date(Date.now()+1000));
  await page.getByRole('button',{name:'پخش',exact:true}).click();await page.clock.runFor(1600);
  await expect(page.locator('.monster-card.selected b')).toHaveText(sample.turns[0].card);
  await page.getByRole('button',{name:'توقف',exact:true}).click();
  for(const index of [1,2,3,14,29,0]){
    await page.locator('#timeline').focus();await page.keyboard.press('Home');
    for(let i=0;i<=index;i++)await page.keyboard.press('ArrowRight');
    const turn=sample.turns[index];
    await expect(page.locator('.monster-card b')).toHaveText(turn.market);
    await expect(page.locator('.monster-card.selected b')).toHaveText(turn.card);
    await expect(page.locator('.player.active strong')).toHaveText(sample.players[turn.seat]);
    await expect(page.locator('.turn-label')).toContainText('کارت جایگزین: '+turn.refill);
    await expect(page.locator('.collection .mini-card')).toHaveCount(index+1);
  }
  await page.getByRole('button',{name:'بازگشت به آغاز',exact:true}).click();
  await expect(page.locator('.monster-card.selected')).toHaveCount(0);
  await expect(page.locator('.monster-card b')).toHaveText(sample.initial_market);
  await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    await page.screenshot({path:test.info().outputPath(`chosen-card-${width}.png`),fullPage:true});
  }
});
test('automatic playback, pause, changed speed and replay from the end',async({page})=>{
  await page.clock.install();await example(page);await page.clock.pauseAt(new Date(Date.now()+1000));await expect(page.getByLabel('سرعت پخش')).toHaveValue('1600');
  await page.getByRole('button',{name:'پخش',exact:true}).click();await page.clock.runFor(1600);await expect(page.locator('#timeline')).toHaveValue('1');
  await page.getByRole('button',{name:'توقف',exact:true}).click();await page.clock.runFor(5000);await expect(page.locator('#timeline')).toHaveValue('1');
  await page.getByLabel('سرعت پخش').selectOption('400');await page.getByRole('button',{name:'پخش',exact:true}).click();await page.clock.runFor(29*400);await expect(page.locator('#timeline')).toHaveValue('30');await expect(page.getByRole('button',{name:'پخش',exact:true})).toBeEnabled();await page.getByRole('button',{name:'پخش',exact:true}).click();await expect(page.locator('#timeline')).toHaveValue('0');
});
test('keyboard arrows and space work outside controls',async({page})=>{
  await example(page);await page.getByLabel('روش نمایش').selectOption('manual');await page.locator('h1').click();await page.keyboard.press('ArrowRight');await expect(page.locator('#timeline')).toHaveValue('1');await page.keyboard.press('ArrowLeft');await expect(page.locator('#timeline')).toHaveValue('0');await page.keyboard.press('Space');await expect(page.locator('#timeline')).toHaveValue('1');
});
test('timeline supports keyboard seeking',async({page})=>{
  await example(page);await page.getByLabel('نوبت بازپخش').focus();await page.keyboard.press('End');await expect(page.locator('#timeline')).toHaveValue('30');await page.keyboard.press('Home');await expect(page.locator('#timeline')).toHaveValue('0');
});
test('downloaded replay preserves all data including decimal seed strings',async({page})=>{
  const log=structuredClone(sample);log.seed='9223372036854775807';await page.goto('/visualizer');await upload(page,log);const event=page.waitForEvent('download');await page.getByRole('button',{name:'دریافت بازپخش',exact:true}).click();expect(JSON.parse(fs.readFileSync(await (await event).path(),'utf8'))).toEqual(log);
});
for(const [name,mutate] of Object.entries({
  version:l=>l.version='wrong',banner:l=>l.banner=6,seat:l=>l.turns[0].seat=1,slot:l=>l.turns[0].choice=6,
  market:l=>l.turns[1].market[0]='Z9',refill:l=>l.turns[0].refill='A9',inventory:l=>l.initial_market=Array(6).fill('A1'),
  hand:l=>l.hands[0].pop(),score:l=>l.result.scores[0].total++,winner:l=>l.result.winner=l.result.winner===0?1:0,
  truncated:l=>l.turns.pop(),nullTurn:l=>l.turns[0]=null,player:l=>l.players[0]={name:'bad'},
}))test(`reject corrupted replay: ${name}`,async({page})=>{
  await page.goto('/visualizer');const log=structuredClone(sample);mutate(log);await upload(page,log);await expect(page.locator('#toast')).toContainText('سازگار نیست');await expect(page.locator('.monster-card')).toHaveCount(0);
});
test('invalid JSON and oversized files are rejected without destroying a loaded game',async({page})=>{
  await example(page);await upload(page,'not JSON');await expect(page.locator('#toast')).toContainText('JSON');await expect(page.locator('.monster-card')).toHaveCount(6);await page.locator('#log-file').setInputFiles({name:'huge.json',mimeType:'application/json',buffer:Buffer.alloc(1048577,32)});await expect(page.locator('#toast')).toContainText('مگابایت');await expect(page.locator('.monster-card')).toHaveCount(6);
});
test('untrusted replay names are displayed literally',async({page})=>{
  await page.goto('/visualizer');const log=structuredClone(sample);log.players=['<img src=x onerror=alert(1)>','<script>alert(1)</script>'];let dialogs=0;page.on('dialog',d=>{dialogs++;d.dismiss()});await upload(page,log);await expect(page.locator('.player strong')).toHaveText([log.players[1],log.players[0]]);await expect(page.locator('.player script')).toHaveCount(0);expect(dialogs).toBe(0);
});
test('friendly deep link requires login and returns to the requested match',async({page,installation})=>{
  const team=await installation.client();const job=await json(await team.post('/api/practice',{bot:'greedy'}),201);await waitJob(team,job.id);await page.goto('/visualizer?match='+job.id);await expect(page.getByRole('link',{name:'ورود به میدان',exact:true})).toBeVisible();await page.getByRole('link',{name:'ورود به میدان',exact:true}).click();await page.getByLabel('نام کاربری تیم').fill('alpha');await page.getByLabel('رمز عبور',{exact:true}).fill(require('./support/fixtures.cjs').PASSWORD);await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();await expect(page).toHaveURL(new RegExp('/visualizer\\?match='+job.id+'$'));await expect(page.locator('.monster-card')).toHaveCount(6);
});
test('pending match view turns into replay after dispatch resumes',async({page,installation})=>{
  const admin=await installation.client('admin'),team=await installation.client();await admin.post('/api/admin/worker',{paused:true});const job=await json(await team.post('/api/practice',{bot:'greedy'}),201);await login(page);await page.goto('/visualizer?match='+job.id);await expect(page.locator('.viewer-empty h2')).toContainText('در صف');await admin.post('/api/admin/worker',{paused:false});await expect(page.locator('.monster-card')).toHaveCount(6,{timeout:15000});
});
test('infrastructure failure and forbidden match produce clear error states',async({page,installation})=>{
  const admin=await installation.client('admin');await admin.post('/api/admin/worker',{paused:true});const failed=installation.state({action:'failed_job'});await login(page);await page.goto('/visualizer?match='+failed.id);await expect(page.locator('.replay-error')).toContainText('خطای زیرساخت');
  await page.getByRole('link',{name:'بازگشت به میدان',exact:true}).click();await page.getByRole('button',{name:'خروج از حساب'}).click();await expect(page.locator('#login-form')).toBeVisible();await login(page,'beta');await page.goto('/visualizer?match='+failed.id);await expect(page.locator('.replay-error')).toContainText('متعلق');
});
test('anonymous local-code dialog stays closed; authenticated invalid extension is explained',async({page})=>{
  await page.goto('/visualizer');await page.getByRole('button',{name:'بازی با دو کد',exact:true}).click();await expect(page.locator('dialog')).not.toBeVisible();await login(page);await page.goto('/visualizer');await page.getByRole('button',{name:'بازی با دو کد',exact:true}).click();
  await page.locator('#code0').setInputFiles({name:'bad.sh',mimeType:'text/plain',buffer:Buffer.from('echo no')});await page.locator('#code1').setInputFiles({name:'ok.py',mimeType:'text/plain',buffer:Buffer.from(PY)});await page.getByRole('button',{name:'بفرست به میدان',exact:true}).click();await expect(page.locator('dialog .inline-error')).toContainText('.py');
});
