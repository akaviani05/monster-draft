const {spawnSync}=require('node:child_process');
module.exports=()=>{
  const result=spawnSync(process.env.ARENA_TEST_PYTHON||'python3',['-m','arena','doctor'],{encoding:'utf8',timeout:30000});
  if(result.status!==0)throw Error('Sandbox prerequisites failed; no unsafe fallback is allowed.\n'+result.stderr+'\n'+result.stdout);
};
