const {defineConfig}=require('@playwright/test');
module.exports=defineConfig({
  testDir:'tests/browser',testMatch:'**/*.spec.cjs',testIgnore:['**/screenshots.spec.cjs'],
  globalSetup:require.resolve('./tests/browser/global-setup.cjs'),
  timeout:45000,expect:{timeout:7000},workers:1,fullyParallel:false,retries:0,forbidOnly:!!process.env.CI,
  // Each test owns its server and database. One worker keeps the 0.3 s judge
  // budget meaningful on small contest hosts; increase only with dedicated CPUs.
  use:{browserName:'chromium',headless:true,viewport:{width:1440,height:1000},
    actionTimeout:10000,navigationTimeout:15000,trace:'retain-on-failure',screenshot:'only-on-failure'},
  reporter:[['list'],['html',{outputFolder:'output/browser-report',open:'never'}],
    ['json',{outputFile:'output/browser-report/results.json'}]],
  outputDir:'output/browser-results',
});
