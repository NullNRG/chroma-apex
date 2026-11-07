// SPDX-License-Identifier: MIT
// Heavy record case. All methods include full key extraction and ordered output reconstruction.
'use strict';
const fs=require('node:fs');const {performance}=require('node:perf_hooks');
const {createApexXL,balance}=require('../packages/js/apex_massive');
const sorter=createApexXL(),schema=[{type:'balance'}];
let seed=0xC0FFEE;function rand(){seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return seed>>>0;}
function make(n){return Array.from({length:n},(_,id)=>({id,rawWeight:rand()%50000,entropySeed:'x'.repeat(rand()%24),subTokens:Array.from({length:64},()=>rand()%9),payload:'!'.repeat(1024)}));}
function run(m,a){
 if(m==='apex')return sorter.sortedCopy(a,schema);
 if(m==='direct')return a.slice().sort((x,y)=>balance(x)-balance(y));
 const keys=a.map(balance),ix=Array.from(keys,(_,i)=>i);
 ix.sort((x,y)=>keys[x]-keys[y]||x-y);return ix.map(i=>a[i]);
}
function med(a){return a.sort((x,y)=>x-y)[a.length>>1]}
const res=[];
for(const n of [10000,100000]){
 const a=make(n);
 const expected=run('cached',a).map(x=>x.id).join(',');
 for(const m of ['apex','direct','cached']){
   let out=run(m,a);if(out.map(x=>x.id).join(',')!==expected)throw new Error('mismatch');
 }
 const times={apex:[],direct:[],cached:[]};
 for(let r=0;r<7;r++){
  const rotated=['apex','direct','cached'];
  for(const m of [...rotated.slice(r%3),...rotated.slice(0,r%3)]){
    if(global.gc)global.gc();const start=performance.now(),x=run(m,a),stop=performance.now();
    if(x.length!==n)throw new Error('length');times[m].push(stop-start);
  }
 }
 for(const m of ['apex','direct','cached'])res.push({n,method:m,median_ms:med(times[m])});
 console.log(n, Object.fromEntries(['apex','direct','cached'].map(m=>[m,med(times[m]).toFixed(3)])));
}
fs.writeFileSync('bench/local_balance_results.json',JSON.stringify({node:process.version,results:res},null,2));
