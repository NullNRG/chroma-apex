// SPDX-License-Identifier: MIT
'use strict';
const fs=require('node:fs');const fsp=require('node:fs/promises');const os=require('node:os');const path=require('node:path');
const assert=require('node:assert/strict');const {externalSortJsonl}=require('./external_jsonl');
(async()=>{
 const dir=await fsp.mkdtemp(path.join(os.tmpdir(),'chroma-test-'));
 try {
  const input=path.join(dir,'in.jsonl'),output=path.join(dir,'out.jsonl');
  let seed=1234567;const rng=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return seed>>>0};
  let a=Array.from({length:12000},(_,id)=>({id,meta:{tier:rng()%41},person:{name:'person-'+(rng()%51)},payload:'x'.repeat(id%137)}));
  await fsp.writeFile(input,a.map(x=>JSON.stringify(x)).join('\n')+'\n');
  const schema=[{path:'meta.tier',type:'number'},{path:'person.name',type:'string'}];
  const result=await externalSortJsonl(input,output,schema,{chunkRecords:101,fanIn:5});
  assert.equal(result.records,a.length);assert.ok(result.initialRuns>10);assert.ok(result.mergePasses>1);
  const actual=(await fsp.readFile(output,'utf8')).trim().split('\n').map(JSON.parse);
  const expected=a.slice().sort((x,y)=>x.meta.tier-y.meta.tier||(x.person.name<y.person.name?-1:x.person.name>y.person.name?1:0));
  assert.deepEqual(actual.map(x=>x.id),expected.map(x=>x.id));
  console.log('PASS Node JSONL external stable multi-run merge 12000 records');
 }finally{await fsp.rm(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
