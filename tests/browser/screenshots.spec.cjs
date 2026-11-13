const {test,expect}=require('@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'output/screenshots');
const password='DemoArena1405!',images=[];
fs.mkdirSync(out,{recursive:true});
async function login(page,username){
  const admin=username==='admin';await page.goto(admin?'/admin':'/');
  if(!admin)await page.getByLabel('نام کاربری تیم').fill(username);
  await page.getByLabel(admin?'رمز مدیریت':'رمز عبور',{exact:true}).fill(password);
  await page.getByRole('button',{name:admin?'ورود به پنل مدیریت':'ورود به میدان'}).click();await expect(page.locator('.sidebar')).toHaveCount(1);
}
async function mutation(page,url,body){
  const session=await (await page.request.get('/api/session')).json();
  const response=await page.request.post('/api'+url,{data:body,headers:{'X-CSRF-Token':session.csrf}});
  expect(response.ok(),await response.text()).toBeTruthy();return response.json();
}
async function shot(page,name){
  await page.evaluate(()=>document.fonts.ready);
  await expect(page.locator('.loading')).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:true,animations:'disabled',mask:[page.locator('input[type=password]')]});
  images.push({name,file:name+'.png',url:page.url(),viewport:page.viewportSize()});
}
async function visit(page,hash,title){
  await page.goto('/#'+hash);await expect(page.locator('h1')).toContainText(title);await expect(page.locator('.loading')).toHaveCount(0);
}
test.afterAll(()=>{
  fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify({captured_at:new Date().toISOString(),synthetic_data:true,images},null,2));
  const cards=images.map(i=>`<figure><a href="${i.file}"><img loading="lazy" src="${i.file}" alt="${i.name}"></a><figcaption>${i.name} · ${i.viewport.width} × ${i.viewport.height}</figcaption></figure>`).join('');
  fs.writeFileSync(path.join(out,'index.html'),`<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>گالری بررسی رابط مسابقه</title><style>body{font:14px Tahoma;background:#f7f5fb;color:#30263f;margin:30px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}figure{margin:0;padding:12px;background:white;border-radius:12px}img{width:100%;height:300px;object-fit:contain;object-position:top}figcaption{padding-top:12px}a{color:inherit}</style><h1>گالری بررسی رابط مسابقه</h1><p>${images.length} تصویر ثبت‌شده از نصب موقت با داده‌های ساختگی. برای اندازهٔ کامل روی تصویر بزنید.</p><main>${cards}</main></html>`);
});
test('capture every page and important empty, error, active and completed states',async({page,browser})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.locator('#login-form')).toBeVisible();await shot(page,'01-login');
  await page.getByLabel('نام کاربری تیم').fill('simorgh');await page.getByLabel('رمز عبور',{exact:true}).fill('incorrect');await page.getByRole('button',{name:'ورود به میدان'}).click();await expect(page.locator('.inline-error')).toContainText('نادرست');await shot(page,'02-login-error');
  await page.goto('/admin');await expect(page.locator('h2')).toContainText('ورود مدیریت');await shot(page,'03-admin-login');
  await page.goto('/guide');await shot(page,'04-student-guide');
  await page.goto('/visualizer');await shot(page,'05-viewer-empty');await page.getByRole('button',{name:'دیدن بازی نمونه'}).click();await expect(page.locator('.monster-card')).toHaveCount(6);await shot(page,'06-replay-initial');
  for(let i=0;i<15;i++)await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();await shot(page,'07-replay-middle');await page.getByLabel('روش نمایش').selectOption('manual');await shot(page,'07b-replay-analysis-mode');await page.getByLabel('روش نمایش').selectOption('auto');
  for(let i=0;i<15;i++)await page.getByRole('button',{name:'انتخاب بعدی',exact:true}).click();await expect(page.locator('.result-callout')).toBeVisible();await shot(page,'08-replay-final');
  await page.locator('#log-file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('{}')});await expect(page.locator('#toast')).toContainText('سازگار');await shot(page,'09-replay-invalid-file');
  await login(page,'admin');await expect(page.locator('h1')).toContainText('مرکز مدیریت');await shot(page,'10-admin-overview');
  const empty=await mutation(page,'/admin/teams',{username:'screenshot-empty',name:'تیم تازه‌وارد',password});
  await visit(page,'admin/teams','مدیریت تیم‌ها');await shot(page,'11-admin-teams');
  await page.getByLabel('جست‌وجوی تیم').fill('هیچ تیمی با این نام');await shot(page,'12-admin-teams-no-results');await page.getByLabel('جست‌وجوی تیم').fill('');
  await page.getByRole('button',{name:'ثبت تیم جدید'}).click();await shot(page,'13-admin-create-team-dialog');
  await page.getByLabel('نام نمایشی تیم').fill('تیم تکراری');await page.getByLabel('نام کاربری انگلیسی').fill('simorgh');await page.getByLabel('رمز اولیه').fill(password);await page.getByRole('button',{name:'ساخت حساب تیم'}).click();await expect(page.locator('dialog .inline-error')).toContainText('قبلاً');await shot(page,'14-admin-create-team-error');await page.getByRole('button',{name:'بستن',exact:true}).click();
  await page.getByRole('button',{name:'ویرایش نام'}).first().click();await shot(page,'15-admin-edit-team-dialog');await page.getByRole('button',{name:'بستن',exact:true}).click();
  await page.getByRole('button',{name:'تغییر رمز'}).first().click();await shot(page,'16-admin-reset-password-dialog');await page.getByRole('button',{name:'بستن',exact:true}).click();
  const emptyRow=page.locator('tbody tr').filter({hasText:'تیم تازه‌وارد'});await emptyRow.getByRole('button',{name:'غیرفعال کردن',exact:true}).click();await expect(emptyRow).toContainText('غیرفعال');await shot(page,'17-admin-team-disabled');await emptyRow.getByRole('button',{name:'فعال کردن',exact:true}).click();
  await visit(page,'admin/settings','تنظیمات اجرا');await shot(page,'18-admin-worker-settings');
  await page.getByLabel('ظرفیت بازی‌های هم‌زمان').fill('2');await page.getByRole('checkbox').check();await page.getByRole('button',{name:'ذخیرهٔ تنظیمات'}).click();await expect(page.locator('#toast')).toContainText('ذخیره');await shot(page,'19-admin-worker-settings-paused');
  await visit(page,'admin/queue','صف مسابقه‌ها');await shot(page,'20-admin-queue-paused');
  await page.getByLabel('وضعیت مسابقه').selectOption('failed');await expect(page.locator('tbody tr')).toHaveCount(1);await shot(page,'21-admin-queue-infrastructure-error');
  await page.getByRole('button',{name:'تکرار خطای زیرساخت',exact:true}).click();await expect(page.locator('.empty')).toContainText('مسابقه‌ای');await shot(page,'22-admin-queue-filter-empty');
  await page.getByLabel('وضعیت مسابقه').selectOption('queued');await expect(page.locator('tbody tr')).toHaveCount(1);await shot(page,'23-admin-queue-queued');
  await page.getByRole('button',{name:'ادامهٔ دریافت بازی‌ها'}).click();await expect(page.getByRole('button',{name:'توقف دریافت بازی‌ها'})).toBeVisible();await page.getByLabel('وضعیت مسابقه').selectOption('completed');await expect(page.locator('tbody tr')).toHaveCount(2,{timeout:20000});await shot(page,'24-admin-queue-completed');
  await visit(page,'admin/tournaments','تورنمنت‌ها');await shot(page,'25-admin-tournaments-empty');await page.getByRole('button',{name:'تورنمنت جدید',exact:true}).click();await shot(page,'26-admin-create-tournament-dialog');
  await page.getByLabel('نام رقابت').fill('جام تصویربرداری');await page.getByRole('button',{name:'ثبت برنامهٔ تورنمنت'}).click();await expect(page.locator('.tournament-card')).toContainText('برنامه‌ریزی‌شده');await shot(page,'27-admin-tournament-scheduled');
  await mutation(page,'/admin/worker',{paused:true});await page.getByRole('button',{name:'شروع اکنون'}).click();
  await expect(async()=>{await page.getByRole('button',{name:'به‌روزرسانی',exact:true}).count();const r=await page.request.get('/api/dashboard');expect((await r.json()).tournaments[0].status).toBe('running')}).toPass({timeout:10000});
  await page.reload();await expect(page.locator('.tournament-card')).toContainText('در حال اجرا');await shot(page,'28-admin-tournament-running');
  await mutation(page,'/admin/worker',{paused:false});await expect(page.locator('.tournament-card')).toContainText('پایان‌یافته',{timeout:20000});await shot(page,'29-admin-tournament-completed');
  await page.getByRole('button',{name:'جدول رتبه‌بندی'}).click();await expect(page.locator('dialog tbody tr')).toHaveCount(3);await shot(page,'30-admin-tournament-standings');await page.getByRole('button',{name:'بستن',exact:true}).click();
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),student=await context.newPage();student.on('pageerror',e=>errors.push(e.message));
  await login(student,'screenshot-empty');await shot(student,'31-team-dashboard-empty');
  await visit(student,'submissions','کدهای من');await shot(student,'32-team-submissions-empty');
  await visit(student,'practice','بازی دوستانه');await shot(student,'33-team-practice-no-code');
  // Tournament games are visible to all teams; the new team has no private games.
  await visit(student,'matches','مسابقه‌ها');await shot(student,'34-team-matches');
  await student.goto('/admin');await expect(student.locator('#admin-login-form')).toBeVisible();await shot(student,'35-admin-password-required');await student.goto('/');await expect(student.locator('.sidebar')).toHaveCount(1);
  await student.getByRole('button',{name:'خروج از حساب'}).click();await expect(student.locator('#login-form')).toBeVisible();await login(student,'simorgh');await shot(student,'36-team-dashboard-populated');
  await visit(student,'submissions','کدهای من');await shot(student,'37-team-submissions-history');await student.getByLabel('کد ربات',{exact:true}).fill('if :');await student.getByRole('button',{name:'بررسی و ثبت کد'}).click();await expect(student.locator('.inline-error')).toContainText('نگارشی');await shot(student,'38-team-submission-error');const original=(await (await student.request.get('/api/dashboard')).json()).active_submission_id;await mutation(student,'/submissions',{source:fs.readFileSync(path.join(root,'B.py'),'utf8'),language:'python',filename:'B.py'});await student.reload();await expect(student.getByRole('button',{name:'انتخاب نسخهٔ نهایی'}).first()).toBeVisible();await shot(student,'38b-team-select-final-code');await mutation(student,'/submissions/'+original+'/activate',{});
  await visit(student,'practice','بازی دوستانه');await shot(student,'39-team-practice-invitation-pending');await student.getByRole('button',{name:'پذیرش',exact:true}).click();await expect(student.locator('.list-row').first()).toContainText('پذیرفته‌شده');await shot(student,'40-team-invitation-accepted');
  await visit(student,'tournaments','تورنمنت‌ها');await shot(student,'41-team-tournaments');
  await student.goto('/visualizer');await student.getByRole('button',{name:'بازی با دو کد'}).click();await expect(student.locator('dialog')).toBeVisible();await shot(student,'42-local-codes-dialog');await student.getByRole('button',{name:'بستن',exact:true}).click();
  await student.setViewportSize({width:390,height:844});await student.goto('/#dashboard');await expect(student.locator('h1')).toContainText('سیمرغ');await shot(student,'43-mobile-team-dashboard');await student.getByRole('button',{name:'باز کردن منو'}).click();await shot(student,'44-mobile-navigation');
  await student.goto('/guide');await shot(student,'45-mobile-student-guide');await student.goto('/visualizer');await student.getByRole('button',{name:'دیدن بازی نمونه'}).click();await expect(student.locator('.monster-card')).toHaveCount(6);await shot(student,'46-mobile-replay');
  await page.setViewportSize({width:390,height:844});await visit(page,'admin','مرکز مدیریت');await shot(page,'47-mobile-admin-overview');await visit(page,'admin/settings','تنظیمات اجرا');await shot(page,'48-mobile-admin-settings');
  await context.close();expect(errors).toEqual([]);
});
