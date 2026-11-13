const {test,expect,json,PASSWORD}=require('./support/fixtures.cjs');
const {createHash}=require('node:crypto');

test('normal reload uses content-versioned scripts and styles with revalidation',async({page,installation})=>{
  const anon=await installation.client(null);
  for(const path of ['/','/admin','/visualizer']){
    await page.goto(path);await page.reload();
    const urls=await page.locator('script[src],link[rel=stylesheet]').evaluateAll(nodes=>nodes.map(n=>n.src||n.href));
    expect(urls.length).toBeGreaterThan(0);
    for(const url of urls){
      const asset=await anon.get(url);expect(asset.status()).toBe(200);
      expect(asset.headers()['cache-control']).toBe('no-cache');
      const version=createHash('sha256').update(await asset.body()).digest('hex').slice(0,16);
      expect(new URL(url).searchParams.get('v')).toBe(version);
    }
  }
});

for(const [name,body,contentType,status] of [
  ['malformed JSON','{','application/json',400],['JSON list','[]','application/json',400],
  ['JSON null','null','application/json',400],['text/plain','{}','text/plain',415],
  ['empty body','','application/json',413],['oversized body','x'.repeat(180001),'application/json',413],
])test(`HTTP rejects ${name} with a JSON error`,async({installation})=>{
  // Buffers preserve the exact wire bytes, including a genuinely empty body.
  const anon=await installation.client(null);const response=await anon.request.post('/api/login',{data:Buffer.from(body),headers:{'Content-Type':contentType}});
  expect(response.status()).toBe(status);expect((await response.json()).error).toEqual(expect.any(String));
});
for(const path of ['/api/submissions?page=bad','/api/matches?page=bad','/api/matches?tournament=bad','/api/admin/queue?page=bad','/api/admin/queue?status=bad'])test(`reject malformed pagination/filter: ${path}`,async({installation})=>{
  const admin=await installation.client('admin');expect((await admin.get(path)).status()).toBe(400);
});
for(const path of ['/api/submissions/999999','/api/matches/999999','/api/matches/999999/replay','/api/tournaments/999999','/api/unknown'])test(`missing API resource: ${path}`,async({installation})=>{
  const team=await installation.client();expect((await team.get(path)).status()).toBe(404);
});
test('HEAD has the GET headers and no response body',async({installation})=>{
  const anon=await installation.client(null);
  for(const path of ['/','/admin','/guide','/assets/style.css','/api/health']){
    const get=await anon.get(path),head=await anon.request.head(path);expect(head.status()).toBe(200);expect(head.headers()['content-length']).toBe(get.headers()['content-length']);expect(await head.body()).toHaveLength(0);
  }
});
test('forged cookies never create a session',async({installation})=>{
  const anon=await installation.client(null);for(const Cookie of ['arena_session=fake','arena_session="bad','other=1']){
    expect((await anon.request.get('/api/dashboard',{headers:{Cookie}})).status()).toBe(401);
  }
});
test('external next URL is ignored after login',async({page})=>{
  await page.goto('/?next=https%3A%2F%2Fevil.invalid');await page.getByLabel('نام کاربری تیم').fill('alpha');await page.getByLabel('رمز عبور',{exact:true}).fill(PASSWORD);await page.getByRole('button',{name:'ورود به میدان',exact:true}).click();await expect(page.locator('.sidebar')).toBeVisible();expect(new URL(page.url()).hostname).toBe('127.0.0.1');
});
test('pagination clamps zero and negative pages and returns an empty distant page',async({installation})=>{
  const team=await installation.client();for(const page of [0,-1])expect((await json(await team.get('/api/submissions?page='+page))).page).toBe(1);
  const data=await json(await team.get('/api/submissions?page=99999'));expect(data.items).toEqual([]);expect(data.total).toBe(1);
});
