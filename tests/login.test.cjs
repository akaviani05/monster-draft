const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
async function render(pathname,sessionUser=null){
  const elements={app:{innerHTML:''},modal:{open:false}};
  const document={body:{dataset:{}},getElementById:id=>elements[id]||={},addEventListener(){}};
  const box={document,window:{addEventListener(){}},location:{pathname,hash:'',search:''},URLSearchParams,Intl,console,setTimeout,clearTimeout,setInterval:()=>0};
  box.fetch=async url=>({ok:true,json:async()=>url==='/api/session'?{user:sessionUser,csrf:'fixture'}:{items:[]}});
  vm.createContext(box);vm.runInContext(fs.readFileSync('web/assets/common.js','utf8'),box);box.Arena=box.window.Arena;
  box.AdminUI={configure(){},load(){throw Error('Admin data must not load for a student')}};
  vm.runInContext(fs.readFileSync('web/assets/app.js','utf8'),box);
  await new Promise(setImmediate);return elements.app.innerHTML;
}
test('/admin renders only the dedicated administrator password form',async()=>{
  const html=await render('/admin');assert.ok(html.includes('id="admin-login-form"'));assert.ok(html.includes('رمز مدیریت'));assert.ok(!html.includes('name="username"'));assert.ok(!html.includes('نام کاربری تیم'));
});
test('student session on /admin still asks for admin password',async()=>{
  const html=await render('/admin/',{id:1,role:'team',name:'تیم آزمایش'});assert.ok(html.includes('id="admin-login-form"'));assert.ok(!html.includes('این بخش مخصوص مدیر مسابقه است.'));
});
test('ordinary team login stays on the home page',async()=>{
  const html=await render('/');assert.ok(html.includes('id="login-form"'));assert.ok(html.includes('name="username"'));assert.ok(!html.includes('id="admin-login-form"'));
});

async function navigationRuntime(tournaments=[]){
  let html='',renders=0,pending=null;
  const app={get innerHTML(){return html},set innerHTML(value){html=value;renders++}};
  const elements={app,modal:{open:false}},handlers={};
  const payload={worker:{online:true,active:0,slots:2},stats:{played:0,wins:0},queue:{},matches:{items:[],total:0},submissions:[],submission_count:0,invitations:[],teams:[],tournaments};
  const document={getElementById:id=>elements[id]||={},addEventListener(){}};
  const box={document,window:{addEventListener:(name,callback)=>handlers[name]=callback,scrollTo(){}},location:{pathname:'/',hash:'',search:''},URLSearchParams,Intl,console,setTimeout,clearTimeout,setInterval:()=>0};
  vm.createContext(box);vm.runInContext(fs.readFileSync('web/assets/common.js','utf8'),box);box.Arena=box.window.Arena;
  box.Arena.api=async path=>{
    if(path==='/session')return {user:{id:2,name:'تیم آزمایش',role:'team'},csrf:'fixture'};
    if(path==='/bots')return {items:[]};
    if(path==='/dashboard'){const wait=pending;pending=null;return wait?await wait:structuredClone(payload)}
    if(path.startsWith('/submissions'))return {items:[]};
    throw Error('Unexpected request '+path);
  };
  box.AdminUI={configure(){},load(){throw Error('Team must not load administrator data')}};
  vm.runInContext(fs.readFileSync('web/assets/app.js','utf8'),box);await new Promise(setImmediate);
  return {app,box,get renders(){return renders},navigate:hash=>{box.location.hash=hash;handlers.hashchange()},defer:()=>{let resolve;pending=new Promise(done=>resolve=done);return ()=>resolve(structuredClone(payload))}};
}
test('navigation exposes the submission form only after its data has loaded',async()=>{
  const r=await navigationRuntime(),previous=r.app.innerHTML,finish=r.defer();r.navigate('#submissions');await new Promise(setImmediate);
  assert.equal(r.app.innerHTML,previous);finish();await new Promise(setImmediate);assert.match(r.app.innerHTML,/id="submission-form"/);
});
test('tournament list and progress use games per pair even when queued count is smaller',async()=>{
  const r=await navigationRuntime([{id:1,name:'جام آزمایش',status:'running',teams:4,games:6,games_per_pair:4,completed:2,starts_at:1}]);
  r.navigate('#tournaments');await new Promise(setImmediate);
  assert.match(r.app.innerHTML,/<span>۲۴ بازی<\/span>/);
  assert.match(r.app.innerHTML,/<progress value="2" max="24"/);
  assert.match(r.app.innerHTML,/۴ بازی برای هر جفت تیم/);
});
test('a late navigation response cannot redraw the current form',async()=>{
  const r=await navigationRuntime(),finish=r.defer();r.navigate('#submissions');await new Promise(setImmediate);r.navigate('#practice');
  assert.match(r.app.innerHTML,/id="invite-form"/);const count=r.renders;finish();await new Promise(setImmediate);
  assert.equal(r.renders,count,'Late responses must preserve the current page and its input');
});
