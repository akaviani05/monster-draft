/* Report a blocked environment honestly, without silently skipping E2E tests. */
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const folder=path.join(root,'output/browser-report');
function status(state,reason=''){
  fs.mkdirSync(folder,{recursive:true});
  fs.writeFileSync(path.join(folder,'run-status.json'),JSON.stringify({state,reason,checked_at:new Date().toISOString()},null,2)+'\n');
}
function run(){
  let cli;
  try{cli=path.join(path.dirname(require.resolve('@playwright/test/package.json')),'cli.js')}
  catch{status('blocked','Playwright is not installed.');console.error('Run npm ci, then npx playwright install chromium.');process.exitCode=1;return}
  const args=process.argv.slice(2);
  if(args.includes('--list')&&!args.some(a=>a.startsWith('--reporter')))args.push('--reporter=list');
  const result=spawnSync(process.execPath,[cli,'test',...args],{cwd:root,stdio:'inherit'});
  if(!process.argv.includes('--list'))status(result.status===0?'completed':'failed',result.status===0?'':'See results.json and the HTML report.');
  process.exitCode=result.status??1;
}
if(process.argv.includes('--list'))run();
else{
  const server=net.createServer();
  server.once('error',error=>{
    const reason=`Loopback HTTP cannot start (${error.code}). Run on a host that permits local servers and Chromium.`;
    status('blocked',reason);console.error(reason+' No browser tests were executed.');process.exitCode=1;
  });
  server.listen(0,'127.0.0.1',()=>server.close(run));
}
