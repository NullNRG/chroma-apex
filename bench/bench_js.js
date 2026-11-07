// SPDX-License-Identifier: MIT
// This benchmark includes schema projection and result construction for both sides.
'use strict';
const fs=require('node:fs');const {performance}=require('node:perf_hooks');
const {createApexXL}=require('../packages/js/apex_massive');
let seed=0xC0FFEE;function rand(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296;}
const schema=[{path:'user.tier',type:'number'},{path:'stats.score',type:'number'},{path:'user.region',type:'string'}];
const region=['eu','us','sa','au','jp'];
function build(n,pattern){
 let a=Array.from({length:n},(_,id)=>({id,user:{tier:Math.floor(rand()*7),region:region[Math.floor(rand()*5)]},stats:{score:Math.floor(rand()*20000)},payload:'q'.repeat(256)}));
 if(pattern==='ordered')a.sort((x,y)=>x.user.tier-y.user.tier||x.stats.score-y.stats.score|| (x.user.region<y.user.region?-1:x.user.region>y.user.region?1:0)||x.id-y.id);
 if(pattern==='noise'){
   a.sort((x,y)=>x.user.tier-y.user.tier||x.stats.score-y.stats.score|| (x.user.region<y.user.region?-1:x.user.region>y.user.region?1:0)||x.id-y.id);
   for(let j=0;j<n/1000;j++){let x=(rand()*n)|0,y=(rand()*n)|0;[a[x],a[y]]=[a[y],a[x]];}
 }
 return a;
}
const sorter=createApexXL();
function compareRecords(a,b){let c=a.user.tier-b.user.tier||a.stats.score-b.stats.score;
 if(c)return c;return a.user.region<b.user.region?-1:a.user.region>b.user.region?1:0;}
function run(method,records){
 if(method==='apex')return sorter.sortedCopy(records,schema);
 if(method==='direct')return records.slice().sort(compareRecords);
 const n=records.length;let cols=new Array(n);
 for(let i=0;i<n;i++){let r=records[i];cols[i]=[r.user.tier,r.stats.score,r.user.region];}
 let ix=Array.from({length:n},(_,i)=>i);
 ix.sort((i,j)=>cols[i][0]-cols[j][0]||cols[i][1]-cols[j][1]||(cols[i][2]<cols[j][2]?-1:cols[i][2]>cols[j][2]?1:0)||i-j);
 return ix.map(i=>records[i]);
}
const median=a=>a.sort((x,y)=>x-y)[a.length>>1];
const result=[];
for(const n of [10000,100000,300000])for(const pattern of ['random','ordered','noise']){
 const a=build(n,pattern);
 const outputs={};for(const m of ['apex','direct','cached'])outputs[m]=run(m,a).map(x=>x.id);
 const expected=outputs.apex.join(',');for(const m of ['direct','cached'])if(outputs[m].join(',')!==expected)throw new Error('mismatch '+n+'/'+pattern+'/'+m);
 const times={apex:[],direct:[],cached:[]};
 for(let round=0;round<7;round++){
   for(const m of [...['apex','direct','cached'].slice(round%3),...['apex','direct','cached'].slice(0,round%3)]){
     if(global.gc)global.gc();
     const t0=performance.now();let x=run(m,a);const t1=performance.now();
     if(x.length!==n)throw new Error('count');times[m].push(t1-t0);
   }
 }
 for(const m of ['apex','direct','cached'])result.push({n,pattern,method:m,median_ms:median(times[m])});
 console.log(`${n} ${pattern} APEX=${median(times.apex).toFixed(3)}ms direct=${median(times.direct).toFixed(3)}ms cached=${median(times.cached).toFixed(3)}ms`);
}
fs.writeFileSync('bench/local_js_results.json',JSON.stringify({node:process.version,results:result},null,2));
