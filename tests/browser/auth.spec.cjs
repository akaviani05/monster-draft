const {test,expect,login,json,PASSWORD}=require('./support/fixtures.cjs');

test('team login, persisted session, logout and invalidated cookie',async({page,installation})=>{
  await login(page);await expect(page.locator('h1')).toContainText('تیم آلفا');await page.reload();await expect(page.locator('.sidebar')).toHaveCount(1);
  const cookies=await page.context().cookies();const cookie=cookies.find(c=>c.name==='arena_session');expect(cookie.httpOnly).toBe(true);expect(cookie.sameSite).toBe('Strict');
  await page.getByRole('button',{name:'خروج از حساب'}).click();await expect(page.locator('#login-form')).toBeVisible();
  const anonymous=await installation.client(null);expect((await anonymous.get('/api/dashboard')).status()).toBe(401);
  expect((await anonymous.request.get('/api/dashboard',{headers:{Cookie:`arena_session=${cookie.value}`}})).status()).toBe(401);
});
test('admin entry is password-only and opens the administration panel',async({page})=>{
  await page.goto('/admin');await expect(page.locator('#admin-login-form')).toBeVisible();await expect(page.locator('input[name=username]')).toHaveCount(0);
  await page.getByLabel('رمز مدیریت').fill(PASSWORD);await page.getByRole('button',{name:'ورود به پنل مدیریت',exact:true}).click();await expect(page.locator('h1')).toHaveText('مرکز مدیریت مسابقه');
  await page.reload();await expect(page.locator('.nav a[href="#admin/settings"]')).toBeVisible();
});
test('student session cannot open admin data and is asked for admin password',async({page})=>{
  await login(page);await page.goto('/admin');await expect(page.locator('#admin-login-form')).toBeVisible();expect((await page.request.get('/api/admin/overview')).status()).toBe(403);
});
for(const [name,password] of [['alpha','wrong'],['unknown',PASSWORD],["' OR 1=1 --",PASSWORD]])test(`reject team credentials: ${name}`,async({page})=>{
  await page.goto('/');await page.getByLabel('نام کاربری تیم').fill(name);await page.getByLabel('رمز عبور',{exact:true}).fill(password);await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();await expect(page.locator('.inline-error')).toContainText('نادرست');await expect(page.locator('.sidebar')).toHaveCount(0);
});
test('bad admin password shows error without creating a session',async({page})=>{
  await page.goto('/admin');await page.getByLabel('رمز مدیریت').fill('wrong');await page.getByRole('button',{name:'ورود به پنل مدیریت',exact:true}).click();await expect(page.locator('.inline-error')).toContainText('نادرست');expect((await (await page.request.get('/api/session')).json()).user).toBeNull();
});
test('admin login supports an account whose username is not admin',async({page,installation})=>{
  installation.state({action:'rename_admin'});await login(page,'admin');await expect(page.locator('h1')).toContainText('مرکز مدیریت');
});
test('disabled admin cannot sign in',async({page,installation})=>{
  installation.state({action:'disable_admin'});await page.goto('/admin');await page.getByLabel('رمز مدیریت').fill(PASSWORD);await page.getByRole('button',{name:'ورود به پنل مدیریت',exact:true}).click();await expect(page.locator('.inline-error')).toContainText('نادرست');
});
test('expired team session returns to login on reload',async({page,installation})=>{
  await login(page);installation.state({action:'expire_sessions'});await page.reload();await expect(page.locator('#login-form')).toBeVisible();expect((await page.request.get('/api/dashboard')).status()).toBe(401);
});
test('expired admin session returns to administrator password form',async({page,installation})=>{
  await login(page,'admin');installation.state({action:'expire_sessions',username:'admin'});await page.reload();await expect(page.locator('#admin-login-form')).toBeVisible();
});
test('login throttling does not allow a correct password to bypass the limit',async({installation})=>{
  const anonymous=await installation.client(null);for(let i=0;i<15;i++)expect((await anonymous.post('/api/admin/login',{password:'wrong'})).status()).toBe(401);
  expect((await anonymous.post('/api/admin/login',{password:PASSWORD})).status()).toBe(429);
});
test('disabled team cannot sign in and its existing session is revoked',async({page,installation})=>{
  await login(page);const admin=await installation.client('admin');const teams=(await json(await admin.get('/api/admin/overview'))).teams;const alpha=teams.find(t=>t.username==='alpha');
  await json(await admin.post('/api/admin/teams/'+alpha.id,{active:false}));expect((await page.request.get('/api/dashboard')).status()).toBe(401);await page.reload();await expect(page.locator('#login-form')).toBeVisible();
  await page.getByLabel('نام کاربری تیم').fill('alpha');await page.getByLabel('رمز عبور',{exact:true}).fill(PASSWORD);await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();await expect(page.locator('.inline-error')).toContainText('نادرست');
});
test('password reset revokes old sessions and only the new password succeeds',async({page,installation})=>{
  await login(page);const admin=await installation.client('admin');const teams=(await json(await admin.get('/api/admin/overview'))).teams;const alpha=teams.find(t=>t.username==='alpha');
  await json(await admin.post('/api/admin/teams/'+alpha.id,{password:'ChangedFixtureOnly!'}));await page.reload();await expect(page.locator('#login-form')).toBeVisible();
  await page.getByLabel('نام کاربری تیم').fill('alpha');await page.getByLabel('رمز عبور',{exact:true}).fill(PASSWORD);await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();await expect(page.locator('.inline-error')).toContainText('نادرست');
  await page.getByLabel('رمز عبور',{exact:true}).fill('ChangedFixtureOnly!');await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();await expect(page.locator('.sidebar')).toHaveCount(1);
});
test('missing required login input is rejected by native validation',async({page})=>{
  await page.goto('/admin');await page.getByRole('button',{name:'ورود به پنل مدیریت',exact:true}).click();expect(await page.getByLabel('رمز مدیریت').evaluate(el=>el.validity.valueMissing)).toBe(true);
});
