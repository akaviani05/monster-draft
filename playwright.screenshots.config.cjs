const base=require('./playwright.config.cjs');
module.exports={...base,testIgnore:[],testMatch:'**/screenshots.spec.cjs',timeout:180000,
  use:{...base.use,baseURL:'http://127.0.0.1:8091'},
  reporter:[['list']],outputDir:'output/screenshot-test-results',
  webServer:{command:'python3 scripts/browser_server.py',url:'http://127.0.0.1:8091/api/health',
    reuseExistingServer:false,timeout:30000,env:{...process.env,ARENA_SCREENSHOT_FIXTURES:'1'}}};
