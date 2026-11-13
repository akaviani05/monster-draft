/* Check local serving capability before starting the disposable screenshot suite. */
const net=require('node:net');
const path=require('node:path');
const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
const folder=path.resolve(__dirname,'../output/screenshots');
function status(state,reason=''){
  fs.mkdirSync(folder,{recursive:true});
  const file=path.join(folder,'manifest.json');
  const captured=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')).images.length:0;
  fs.writeFileSync(path.join(folder,'capture-status.json'),JSON.stringify({state,reason,checked_at:new Date().toISOString(),captured_screenshots:captured},null,2));
}
const server=net.createServer();
server.once('error',error=>{
  status('blocked',`Loopback HTTP is denied (${error.code}); Chromium startup is also restricted in this task environment.`);
  console.error(`Screenshot capture blocked: cannot create a loopback server (${error.code}). Run npm run test:screenshots in a terminal that permits local HTTP and Chromium. No screenshots were fabricated.`);
  process.exitCode=1;
});
server.listen(0,'127.0.0.1',()=>server.close(()=>{
  let cli;try{cli=path.join(path.dirname(require.resolve('@playwright/test/package.json')),'cli.js')}catch{
    status('blocked','Install development dependencies and Chromium first.');
    console.error('Install development tools first: npm install && npx playwright install chromium');process.exitCode=1;return;
  }
  const result=spawnSync(process.execPath,[cli,'test','--config','playwright.screenshots.config.cjs'],{stdio:'inherit'});
  status(result.status===0?'completed':'failed',result.status===0?'':'See the Playwright test output.');
  process.exitCode=result.status??1;
}));
