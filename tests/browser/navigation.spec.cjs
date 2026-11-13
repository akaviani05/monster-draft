const {test,expect,login,visit}=require('./support/fixtures.cjs');

async function fits(page){
  await page.evaluate(()=>document.fonts.ready);
  expect(await page.locator('html').getAttribute('dir')).toBe('rtl');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Page must not overflow horizontally').toBe(true);
}
for(const width of [390,768,1440]){
  test(`team pages, guide and viewer fit ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:1000});await page.goto('/');await fits(page);await login(page);
    for(const [route,title] of [['dashboard','تیم آلفا'],['profile','پروفایل تیم'],['scoreboard','جدول امتیازها'],['submissions','کدهای من'],['practice','بازی دوستانه'],['matches','مسابقه‌ها'],['tournaments','تورنمنت‌ها']]){await visit(page,route,title);await fits(page)}
    await page.goto('/guide');await expect(page.locator('h1')).toBeVisible();await fits(page);await page.goto('/visualizer');await page.getByRole('button',{name:'دیدن بازی نمونه',exact:true}).click();await expect(page.locator('.monster-card')).toHaveCount(6);await fits(page);
  });
  test(`admin pages and create-team dialog fit ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:1000});await page.goto('/admin');await fits(page);await login(page,'admin');
    for(const [route,title] of [['admin','مرکز مدیریت'],['admin/teams','مدیریت تیم‌ها'],['admin/tournaments','تورنمنت‌ها'],['admin/queue','صف مسابقه‌ها'],['admin/settings','تنظیمات اجرا']]){await visit(page,route,title);await fits(page)}
    await visit(page,'admin/teams','مدیریت تیم‌ها');await page.getByRole('button',{name:'ثبت تیم جدید',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await fits(page);await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).not.toBeVisible();
  });
}
test('mobile navigation opens and closes after selecting a page',async({page})=>{
  await page.setViewportSize({width:390,height:844});await login(page);const menu=page.getByRole('button',{name:'باز کردن منو',exact:true});await expect(menu).toHaveAttribute('aria-expanded','false');await menu.click();await expect(menu).toHaveAttribute('aria-expanded','true');await page.getByRole('navigation',{name:'منوی اصلی'}).getByRole('link',{name:'کدهای من',exact:true}).click();await expect(page.locator('h1')).toHaveText('کدهای من');await expect(menu).toHaveAttribute('aria-expanded','false');await expect(page.locator('.sidebar')).not.toHaveClass(/open/);
});
test('student cannot navigate into admin pages through a manually edited hash',async({page})=>{
  await login(page);await page.goto('/#admin/teams');await expect(page.locator('.empty')).toContainText('مخصوص مدیر');await expect(page.getByRole('button',{name:'ثبت تیم جدید',exact:true})).toHaveCount(0);
});
test('session bootstrap transport failure shows retry and recovers',async({page})=>{
  await page.route('**/api/session',route=>route.abort('failed'));await page.goto('/');await expect(page.locator('h1')).toHaveText('ارتباط با میدان برقرار نشد');await page.unroute('**/api/session');await page.getByRole('button',{name:'تلاش دوباره',exact:true}).click();await expect(page.locator('#login-form')).toBeVisible();
});
test('failed submit request keeps entered code and offers a retry',async({page})=>{
  await login(page);await visit(page,'submissions','کدهای من');await page.getByLabel('کد ربات',{exact:true}).fill('print(0)');await page.route('**/api/submissions',route=>route.abort('failed'));await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();await expect(page.locator('.inline-error')).not.toBeEmpty();await expect(page.getByLabel('کد ربات',{exact:true})).toHaveValue('print(0)');await expect(page.getByRole('button',{name:'بررسی و ثبت کد'})).toBeEnabled();await page.unroute('**/api/submissions');await page.getByRole('button',{name:'بررسی و ثبت کد'}).click();await expect(page.locator('.list-row')).toHaveCount(2);
});
test('matches pagination, explicit refresh and empty tournament list',async({page,installation})=>{
  installation.state({action:'completed_jobs',count:30});await login(page);await visit(page,'matches','مسابقه‌ها');await expect(page.locator('tbody tr')).toHaveCount(25);const ids=await page.locator('tbody .match-team+small').allTextContents();await page.getByRole('button',{name:'صفحهٔ بعد',exact:true}).click();await expect(page.locator('tbody tr')).toHaveCount(5);expect(await page.locator('tbody .match-team+small').allTextContents()).not.toEqual(ids);await page.getByRole('button',{name:'به‌روزرسانی',exact:true}).click();await expect(page.locator('#toast')).toContainText('به‌روز');await page.getByRole('button',{name:'صفحهٔ قبل',exact:true}).click();await expect(page.locator('tbody tr')).toHaveCount(25);await visit(page,'tournaments','تورنمنت‌ها');await expect(page.locator('.empty')).toContainText('هنوز');
});
