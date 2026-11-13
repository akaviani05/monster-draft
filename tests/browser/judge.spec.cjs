const {test,expect,json,waitJob,login}=require('./support/fixtures.cjs');
const prefix='import sys\ninput()\nTURNS = 30\nfor i in range(TURNS):\n    event = input()\n    A = [input() for _ in range(6)]\n    if event == "OPPTURN":\n        input()\n    else:\n';

for(const [name,body,reason] of [
  ['out-of-range choice','        print(9, flush=True)\n','invalid_output'],
  ['non-numeric output','        print("hello", flush=True)\n','invalid_output'],
  ['infinite loop','        while True: pass\n','turn_timeout'],
  ['shell command','        import os\n        assert os.system("true") == 0\n        print(0, flush=True)\n',null],
])test(`judge contains ${name}, commits a loss and stays available`,async({page,installation})=>{
  const team=await installation.client();await json(await team.post('/api/submissions',{source:prefix+body,filename:'fixture.py'}),201);
  const job=await json(await team.post('/api/practice',{bot:'greedy'}),201);const finished=await waitJob(team,job.id);expect(finished.status).toBe('completed');const log=await json(await team.get(`/api/matches/${job.id}/replay`));
  if(reason)expect(log.result.reason).toBe(reason);else expect(log.result.reason).not.toBe('completed');
  const seat=finished.p0===finished.owner_id?0:1;expect(log.result.loser).toBe(seat);expect(log.result.winner).toBe(1-seat);expect((await team.get('/api/dashboard')).status()).toBe(200);
  const admin=await installation.client('admin');expect((await admin.post('/api/admin/jobs/'+job.id,{action:'retry'})).status()).toBe(409);
  await login(page);await page.goto('/visualizer?match='+job.id);await expect(page.locator('.monster-card')).toHaveCount(6);await page.getByLabel('نوبت بازپخش').focus();await page.keyboard.press('End');await expect(page.locator('.result-callout')).toBeVisible();
});
