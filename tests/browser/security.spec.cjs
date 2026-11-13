const {test,expect,json,PY,PASSWORD}=require('./support/fixtures.cjs');

for(const path of ['/api/dashboard','/api/submissions','/api/matches','/api/admin/overview','/api/admin/queue','/api/tournaments/1'])test(`anonymous cannot GET ${path}`,async({installation})=>{
  const client=await installation.client(null);expect((await client.get(path)).status()).toBe(401);
});
for(const path of ['/api/admin/overview','/api/admin/queue'])test(`team cannot GET ${path}`,async({installation})=>{
  const team=await installation.client();expect((await team.get(path)).status()).toBe(403);
});
for(const [path,body] of [['/api/admin/teams',{username:'blocked',name:'blocked',password:PASSWORD}],['/api/admin/worker',{slots:1}],['/api/admin/tournaments',{name:'blocked',teams:[1,2],starts_at:1}],['/api/admin/jobs/1',{action:'retry'}],['/api/admin/teams/2',{active:false}],['/api/admin/tournaments/1',{action:'start'}]])test(`team cannot POST ${path}`,async({installation})=>{
  const team=await installation.client();expect((await team.post(path,body)).status()).toBe(403);
});
for(const token of ['', 'forged-token'])test(`mutation rejects ${token?'wrong':'missing'} CSRF token`,async({installation})=>{
  const team=await installation.client();expect((await team.post('/api/practice',{bot:'greedy'},{headers:{'X-CSRF-Token':token}})).status()).toBe(403);
});
test('cross-site origin and Fetch Metadata cannot submit authenticated mutations',async({installation})=>{
  const team=await installation.client();for(const headers of [{Origin:'https://evil.invalid'},{'Sec-Fetch-Site':'cross-site'}])expect((await team.post('/api/practice',{bot:'greedy'},{headers})).status()).toBe(403);
});
test('cross-site password login is rejected before a session is created',async({installation})=>{
  const anon=await installation.client(null);expect((await anon.post('/api/admin/login',{password:PASSWORD},{headers:{Origin:'https://evil.invalid'}})).status()).toBe(403);
  expect((await json(await anon.get('/api/session'))).user).toBeNull();
});
test('source, final selection and friendly replay are owner-scoped',async({installation})=>{
  const owner=await installation.client('alpha'),other=await installation.client('beta'),admin=await installation.client('admin');
  await admin.post('/api/admin/worker',{paused:true});const source=await json(await owner.post('/api/submissions',{source:PY,language:'python'}),201);
  expect((await other.get('/api/submissions/'+source.id)).status()).toBe(404);expect((await other.post('/api/submissions/'+source.id+'/activate',{})).status()).toBe(404);
  const job=await json(await owner.post('/api/practice',{bot:'greedy'}),201);expect((await other.get('/api/matches/'+job.id)).status()).toBe(403);expect((await other.get(`/api/matches/${job.id}/replay`)).status()).toBe(403);
  expect((await admin.get('/api/matches/'+job.id)).status()).toBe(200);expect((await json(await other.get('/api/matches'))).items).toEqual([]);
});
test('private data and file paths are excluded from dashboard payloads',async({installation})=>{
  const team=await installation.client();const text=await (await team.get('/api/dashboard')).text();
  expect(text).not.toContain(installation.directory);for(const key of ['"password"','"source"','"token"','"path"'])expect(text).not.toContain(key);
});
for(const resource of ['/','/admin','/visualizer','/guide','/assets/app.js'])test(`security headers on ${resource}`,async({installation})=>{
  const client=await installation.client(null),response=await client.get(resource);expect(response.status()).toBe(200);const headers=response.headers();
  expect(headers['content-security-policy']).toContain("script-src 'self'");expect(headers['x-content-type-options']).toBe('nosniff');expect(headers['x-frame-options']).toBe('DENY');
});
for(const path of ['/var/arena.sqlite3','/bots/guardian.py','/bots/champion.cpp','/arena/service.py','/../arena/service.py','/%2e%2e/arena/service.py','/.env'])test(`private path is not served: ${path}`,async({installation})=>{
  const client=await installation.client(null);expect((await client.get(path)).status()).toBe(404);
});
