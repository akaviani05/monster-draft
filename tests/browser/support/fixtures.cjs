const base=require('@playwright/test');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {spawn,spawnSync}=require('node:child_process');
const {once}=require('node:events');
const ROOT=path.resolve(__dirname,'../../..'),PYTHON=process.env.ARENA_TEST_PYTHON||'python3';
const PASSWORD='PlaywrightFixtureOnly!234';
const PY=fs.readFileSync(path.join(ROOT,'B.py'),'utf8');
const CPP=fs.readFileSync(path.join(ROOT,'A.cpp'),'utf8');
class Installation{
  constructor(){
    this.directory=fs.mkdtempSync(path.join(os.tmpdir(),'arena-pw-'));
    this.token=crypto.randomBytes(24).toString('hex');
    fs.writeFileSync(path.join(this.directory,'.playwright-test-data'),this.token,{mode:0o600});
    this.env={...process.env,ARENA_TEST_TOKEN:this.token,ARENA_DATA:this.directory};
    this.clients=[];this.logs='';
  }
  async start(port=0){
    this.child=spawn(PYTHON,['-u','tests/browser/support/harness.py','serve','--data',this.directory,'--port',String(port)],{cwd:ROOT,env:this.env,stdio:['ignore','pipe','pipe']});
    this.child.stderr.on('data',c=>{this.logs=(this.logs+c).slice(-12000)});
    let buffer='';
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('Disposable server startup timed out: '+this.logs)),20000);
      const failed=()=>{clearTimeout(timer);reject(Error('Disposable server failed: '+this.logs))};
      this.child.once('error',failed);this.child.once('exit',failed);
      this.child.stdout.on('data',chunk=>{
        buffer+=chunk;
        for(const line of buffer.split('\n').slice(0,-1)){
          try{const info=JSON.parse(line);if(info.ready){this.url=info.url;clearTimeout(timer);this.child.removeListener('exit',failed);resolve()}}catch{}
        }
        buffer=buffer.slice(buffer.lastIndexOf('\n')+1);
      });
    });return this;
  }
  state(body){
    const result=spawnSync(PYTHON,['tests/browser/support/harness.py','state','--data',this.directory],{cwd:ROOT,env:this.env,input:JSON.stringify(body),encoding:'utf8',timeout:25000});
    if(result.status!==0)throw Error('Fixture operation failed: '+result.stderr);
    return JSON.parse(result.stdout);
  }
  async client(role='alpha',password=PASSWORD){
    const request=await base.request.newContext({baseURL:this.url});this.clients.push(request);
    let csrf;
    if(role){
      const login=await request.post(role==='admin'?'/api/admin/login':'/api/login',{data:role==='admin'?{password}:{username:role,password}});
      base.expect(login.status(),await login.text()).toBe(200);csrf=(await login.json()).csrf;
    }
    return {request,get:(url)=>request.get(url),post:(url,data={},options={})=>request.post(url,{...options,data,headers:{'X-CSRF-Token':csrf||'',...(options.headers||{})}})};
  }
  async stop(){
    if(this.child&&this.child.exitCode===null){
      const exited=once(this.child,'exit');this.child.kill('SIGTERM');
      const timer=setTimeout(()=>this.child.kill('SIGKILL'),40000);
      await exited;clearTimeout(timer);
    }
  }
  async restart(){const port=Number(new URL(this.url).port);await this.stop();await this.start(port)}
  async dispose(){await this.stop();await Promise.all(this.clients.map(c=>c.dispose()));fs.rmSync(this.directory,{recursive:true,force:true})}
}
const test=base.test.extend({
  installation:[async({},use,testInfo)=>{
    const app=new Installation();
    try{await app.start();await use(app)}finally{
      if(testInfo.status!==testInfo.expectedStatus&&app.logs)await testInfo.attach('server-log',{body:app.logs,contentType:'text/plain'});
      await app.dispose();
    }
  },{timeout:60000}],
  baseURL:async({installation},use)=>use(installation.url),
  diagnostics:[async({page},use,testInfo)=>{
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await use();
    base.expect(errors,'Uncaught browser JavaScript errors').toEqual([]);
    if(testInfo.status!==testInfo.expectedStatus){
      try{await testInfo.attach('page',{body:await page.screenshot({fullPage:true,mask:[page.locator('input[type=password]')]}),contentType:'image/png'})}catch{}
    }
  },{auto:true}],
});
async function login(page,role='alpha',password=PASSWORD){
  const admin=role==='admin';await page.goto(admin?'/admin':'/');
  if(!admin)await page.getByLabel('نام کاربری تیم').fill(role);
  await page.getByLabel(admin?'رمز مدیریت':'رمز عبور',{exact:true}).fill(password);
  await page.getByRole('button',{name:admin?'ورود به پنل مدیریت':'ورود به میدان',exact:true}).click();
  await base.expect(page.locator('.sidebar')).toHaveCount(1);
}
async function visit(page,route,title){await page.goto('/#'+route);await base.expect(page.locator('h1')).toContainText(title)}
async function json(response,status=200){base.expect(response.status(),await response.text()).toBe(status);return response.json()}
async function waitJob(client,id){
  await base.expect.poll(async()=> (await (await client.get('/api/matches/'+id)).json()).status,{timeout:15000}).toMatch(/completed|failed/);
  return json(await client.get('/api/matches/'+id));
}
module.exports={test,expect:base.expect,login,visit,json,waitJob,PASSWORD,PY,CPP,ROOT,Installation};
