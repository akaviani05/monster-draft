const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const team={id:1,name:'<script>bad()</script>',username:'test',active:1,submission_id:2,filename:'<image>.py',language:'python',submitted_at:0};
const overview={teams:[team],counts:{teams:1,active:1,ready:1},settings:{slots:6,paused:false},worker:{online:true,slots:6,active:0,at:0},tournaments:[],queue:{}};
async function runtime(){
  const box={window:{},location:{hash:'#admin'},document:{addEventListener(){}},console,Intl,setTimeout,clearTimeout};
  vm.createContext(box);vm.runInContext(fs.readFileSync('web/assets/common.js','utf8'),box);
  box.Arena=box.window.Arena;box.respond=async p=>p.startsWith('/admin/queue')?{items:[],total:0}:overview;box.Arena.api=p=>box.respond(p);
  vm.runInContext(fs.readFileSync('web/assets/admin.js','utf8'),box);await box.window.AdminUI.load();return box;
}
const helpers={head:(a,b,c='')=>`<h1>${a}</h1><p>${b}</p>${c}`,tournaments:()=>'<h1>تورنمنت‌ها</h1>'};
for(const [sub,title] of [['','مرکز مدیریت مسابقه'],['/teams','مدیریت تیم‌ها'],['/settings','تنظیمات اجرا'],['/queue','صف مسابقه‌ها'],['/tournaments','تورنمنت‌ها']])test('admin renders '+(sub||'overview'),async()=>{const box=await runtime();box.location.hash='#admin'+sub;await box.window.AdminUI.load();assert.ok(box.window.AdminUI.render(helpers).includes(title))});
test('team names and filenames are escaped in admin HTML',async()=>{const box=await runtime();box.location.hash='#admin/teams';const html=box.window.AdminUI.render(helpers);assert.ok(!html.includes('<script>bad()'));assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('&lt;image&gt;.py'))});
test('administrator data cannot reappear after logout from a late response',async()=>{
  const box=await runtime();let finish;box.respond=()=>new Promise(resolve=>finish=resolve);
  const load=box.window.AdminUI.load();box.window.AdminUI.reset();finish(overview);await load;
  assert.ok(!box.window.AdminUI.render(helpers).includes('مرکز مدیریت مسابقه'));
});
test('a late administrator response cannot restore an older team name',async()=>{
  const box=await runtime();box.location.hash='#admin/teams';let finish;
  box.respond=()=>new Promise(resolve=>finish=resolve);const earlier=box.window.AdminUI.load();
  box.respond=async()=>({...overview,teams:[{...team,name:'Current team name'}]});await box.window.AdminUI.load();finish(overview);await earlier;
  const html=box.window.AdminUI.render(helpers);assert.ok(html.includes('Current team name'));assert.ok(!html.includes('&lt;script&gt;bad()'));
});
