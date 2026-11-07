'use strict';
const assert=require('node:assert/strict');
const {createApexXL,stableReference}=require('./apex_massive.js');
const core=createApexXL();
const seeded=(function(){let x=0x1234abcd;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return(x>>>0)/4294967296}})();
const patterns=[
 {type:'number',path:'x',produce:i=>i%33},
 {type:'number',path:'x',produce:i=>i},
 {type:'number',path:'x',produce:i=>-i},
 {type:'number',path:'x',produce:i=>Math.floor(seeded()*10000)-5000+seeded()},
 {type:'string',path:'x',produce:i=>'key-'+(i%101).toString(36)},
 {type:'bigint',path:'x',produce:i=>BigInt(i%23)-11n},
];
let checks=0;
for(const p of patterns)for(const n of [0,1,2,7,37,120,1000,5000]){
 let a=Array.from({length:n},(_,i)=>({id:i,x:p.produce(i),metadata:{group:i%13,payload:'Z'.repeat(i%233)}}));
 const schema=[{type:p.type,path:'x'}];
 const ref=stableReference(a,schema);const ix=core.order(a,schema);
 assert.deepEqual(Array.from(ix),ref);const shuffled=core.sortedCopy(a,schema);
 assert.deepEqual(shuffled.map(r=>r.id),ref);
 checks++;
}
for(const n of [0,1,120,1000,10000]){
 const a=Array.from({length:n},(_,i)=>({id:i,a:{b:Math.floor(seeded()*8)},c:(i%7),nested:['x','z',i%13],t:i%11}));
 const schema=[{path:'a.b',type:'number'},{path:'c',type:'number',order:'desc'},{path:'nested',type:'tuple'}];
 const ix=Array.from(core.order(a,schema));const reference=stableReference(a,schema);
 assert.deepEqual(ix,reference);checks++;
}
console.log(`PASS JS correctness: ${checks} suites`);
