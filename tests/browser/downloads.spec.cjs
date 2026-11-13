const {test,expect,ROOT}=require('./support/fixtures.cjs');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {pathToFileURL}=require('node:url'),{spawnSync}=require('node:child_process');
const inventory=['A.cpp','B.py','README.txt','play.py','runner/__init__.py','runner/game.py','runner/local.py',
  'viewer/index.html',...['Vazirmatn.ttf','OFL.txt','logo.svg','monster-a.svg','monster-b.svg','monster-c.svg','monster-d.svg','monster-e.svg','style.css','common.js','viewer.js'].map(n=>'viewer/assets/'+n)].sort();

test('student ZIP contains exactly the public allowlist and its viewer works entirely offline',async({page,browser})=>{
  await page.goto('/guide');const event=page.waitForEvent('download');await page.locator('a[href$="downloads/runner.zip"]').first().click();const zip=await (await event).path();
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'arena-pw-download-'));
  const context=await browser.newContext({offline:true});
  try{
    const extracted=spawnSync(process.env.ARENA_TEST_PYTHON||'python3',['-c',
      'import sys,json,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(json.dumps(sorted(z.namelist()))); z.extractall(sys.argv[2])',zip,directory],{encoding:'utf8'});
    expect(extracted.status,extracted.stderr).toBe(0);expect(JSON.parse(extracted.stdout)).toEqual(inventory);
    for(const file of ['A.cpp','B.py','play.py'])expect(fs.readFileSync(path.join(directory,file),'utf8')).toBe(fs.readFileSync(path.join(ROOT,file),'utf8'));
    const viewer=await context.newPage(),network=[],errors=[];viewer.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url())});viewer.on('pageerror',e=>errors.push(e.message));
    await viewer.goto(pathToFileURL(path.join(directory,'viewer/index.html')).href);await viewer.locator('#log-file').setInputFiles(path.join(ROOT,'web/assets/example.json'));await expect(viewer.locator('.monster-card')).toHaveCount(6);
    await viewer.getByLabel('روش نمایش').selectOption('manual');await viewer.getByRole('button',{name:'نمایش نوبت بعد',exact:true}).click();await expect(viewer.locator('#timeline')).toHaveValue('1');
    const replay=JSON.parse(fs.readFileSync(path.join(ROOT,'web/assets/example.json'),'utf8'));
    await expect(viewer.locator('.monster-card.selected b')).toHaveText(replay.turns[0].card);
    await expect(viewer.locator('#local-codes')).toHaveCount(0);await expect(viewer.locator('#sample-replay')).toHaveCount(0);expect(network).toEqual([]);expect(errors).toEqual([]);
  }finally{await context.close();fs.rmSync(directory,{recursive:true,force:true})}
});
test('Persian guide uses the bundled font and PDF is downloadable without login',async({page})=>{
  const broken=[];page.on('response',r=>{if(r.status()>=400)broken.push(r.url())});await page.goto('/guide');await expect(page.locator('html')).toHaveAttribute('lang','fa');await expect(page.locator('h1')).toBeVisible();
  await page.evaluate(()=>document.fonts.ready);expect(await page.locator('body').evaluate(el=>getComputedStyle(el).fontFamily)).toContain('Vazirmatn');
  const event=page.waitForEvent('download');await page.getByRole('link',{name:'دریافت PDF راهنمای پیاده‌سازی و بازی',exact:true}).click();const pdf=fs.readFileSync(await (await event).path());expect(pdf.subarray(0,5).toString()).toBe('%PDF-');expect(pdf.length).toBeGreaterThan(10000);expect(pdf.equals(fs.readFileSync(path.join(ROOT,'web/downloads/student-guide-fa.pdf')))).toBe(true);expect(broken).toEqual([]);
});
test('every local guide fragment and same-origin asset resolves',async({page})=>{
  await page.goto('/guide');const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(a=>a.getAttribute('href')));
  for(const link of new Set(links.filter(h=>h.startsWith('#'))))expect(await page.locator('[id]').evaluateAll((nodes,id)=>nodes.some(n=>n.id===id),link.slice(1)),link).toBe(true);
  const assets=await page.locator('[src],link[rel=stylesheet]').evaluateAll(nodes=>nodes.map(n=>n.src||n.href));for(const url of new Set(assets))expect((await page.request.get(url)).status(),url).toBe(200);
});
