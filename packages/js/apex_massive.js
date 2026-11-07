/* CHROMA APEX XL — stable schema-oriented reference sorter.
 * All variants implement known algorithm families; claims are about engineering,
 * not unprecedented mathematical sorting complexity. License: MIT.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ChromaApexXL=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const TYPES=new Set(['number','date','boolean','string','bigint','balance','array-length','token-sum','string-length','bytes','tuple','json','custom','auto']);
function pathParts(path){
  if(Array.isArray(path))return path.slice();
  if(typeof path!=='string'||!path.trim())throw new TypeError('Schema requires a property path');
  return path.split('.');
}
function compileSchema(schema){
  if(!Array.isArray(schema)||!schema.length)throw new TypeError('Schema must contain key descriptors');
  return schema.map(d=>{
    if(typeof d==='string')d={path:d,type:'auto'};
    if(!d||!TYPES.has(d.type||'auto'))throw new TypeError('Unsupported key type');
    const parts=d.type==='balance'||d.type==='custom'?null:pathParts(d.path);
    if(d.type==='custom'&&(typeof d.project!=='function'||typeof d.compare!=='function'))throw new TypeError('Custom key requires project and compare functions');
    const type=d.type||'auto';
    const get=parts?function(o){for(let j=0;j<parts.length;j++){if(o==null)return undefined;o=o[parts[j]];}return o;}:null;
    return {path:d.path,type,get,project:d.project,compare:d.compare,desc:d.order==='desc',nullsLast:d.nulls!=='first'};
  });
}
function balance(r){
  if(!r || typeof r!=='object'||!Number.isFinite(r.rawWeight)||typeof r.entropySeed!=='string'||!Array.isArray(r.subTokens))throw new TypeError('Invalid balance record');
  let s=0;for(const t of r.subTokens){if(typeof t!=='number'||!Number.isFinite(t))throw new TypeError('Invalid token');s+=t;}
  let w=r.rawWeight+r.entropySeed.length*1.5+s%7;
  if(!Number.isFinite(w))throw new TypeError('Nonfinite balance metric');
  return w===0?0:w;
}
function canonicalJson(value,seen=new WeakSet()){
  if(value===null)return null;
  if(value instanceof Date)return ['date',value.toISOString()];
  if(typeof value==='bigint')return ['bigint',String(value)];
  if(typeof value==='number')return ['number',String(value)];
  if(typeof value==='string')return ['string',value];
  if(typeof value==='boolean')return ['boolean',value];
  if(typeof value==='undefined')return ['undefined'];
  if(typeof value!=='object')throw new TypeError('Non-serializable JSON key');
  if(seen.has(value))throw new TypeError('Circular JSON sort key');
  seen.add(value);
  let result;
  if(Array.isArray(value))result=['array',value.map(v=>canonicalJson(v,seen))];
  else if(value instanceof Uint8Array)result=['bytes',Array.from(value)];
  else result=['object',Object.keys(value).sort().map(k=>[k,canonicalJson(value[k],seen)])];
  seen.delete(value);return result;
}
function convert(row,d){
  let v=d.type==='balance'?balance(row):d.type==='custom'?d.project(row):d.get(row);
  if(v==null)return null;
  switch(d.type){
    case 'balance': case 'number': if(typeof v!=='number')throw new TypeError('Numeric key expected');return Number.isNaN(v)?null:(v===0?0:v);
    case 'date': {const t=v instanceof Date?v.getTime():(typeof v==='number'?v:Date.parse(v));return Number.isNaN(t)?null:t;}
    case 'boolean': return Boolean(v)?1:0;
    case 'string': if(typeof v!=='string')throw new TypeError('String key expected');return v;
    case 'bigint': if(typeof v!=='bigint')throw new TypeError('BigInt key expected');return v;
    case 'array-length': if(!Array.isArray(v))throw new TypeError('Array key expected');return v.length;
    case 'token-sum': if(!Array.isArray(v))throw new TypeError('Array key expected');{let x=0;for(const item of v){if(typeof item!=='number'||!Number.isFinite(item))throw new TypeError('Invalid numeric token');x+=item;}return x;}
    case 'string-length': return String(v).length;
    case 'bytes': if(!(v instanceof Uint8Array))throw new TypeError('Uint8Array/Buffer key expected');return v;
    case 'tuple': if(!Array.isArray(v))throw new TypeError('Tuple array key expected');return v;
    case 'json': return JSON.stringify(canonicalJson(v));
    case 'custom': return v;
    case 'auto': if(v instanceof Date){const t=v.getTime();return Number.isNaN(t)?null:t;}
      if(typeof v==='number'){return Number.isNaN(v)?null:(v===0?0:v);}
      if(typeof v==='string'||typeof v==='bigint')return v;
      if(typeof v==='boolean')return v?1:0;
      throw new TypeError('Auto keys must be scalar primitives, Date, or null');
  }
}
function cmpValue(a,b,d){
  const an=a===null,bn=b===null;
  if(an||bn)return an?(bn?0:(d.nullsLast?1:-1)):(d.nullsLast?-1:1);
  if(d.type==='custom'){
    const raw=d.compare(a,b);
    if(typeof raw!=='number'||!Number.isFinite(raw))throw new TypeError('Custom compare must return finite number');
    const c=Math.sign(raw);return d.desc?-c:c;
  }
  if(d.type==='bytes'){
    const n=Math.min(a.length,b.length);for(let i=0;i<n;i++)if(a[i]!==b[i]){const c=a[i]<b[i]?-1:1;return d.desc?-c:c;}
    const c=Math.sign(a.length-b.length);return d.desc?-c:c;
  }
  if(d.type==='tuple'){
    const n=Math.min(a.length,b.length);
    for(let i=0;i<n;i++){const c=cmpValue(a[i],b[i],{type:'auto',desc:false,nullsLast:d.nullsLast});if(c)return d.desc?-c:c;}
    const c=Math.sign(a.length-b.length);return d.desc?-c:c;
  }
  const ta=typeof a,tb=typeof b;
  if(ta!==tb){const rank={number:0,bigint:1,string:2};const c=(rank[ta]??3)-(rank[tb]??3);return d.desc?-Math.sign(c):Math.sign(c);}
  const c=a<b?-1:a>b?1:0;
  return d.desc?-c:c;
}
function projection(row,compiled){const o=new Array(compiled.length);for(let i=0;i<compiled.length;i++)o[i]=convert(row,compiled[i]);return o;}
function compareProjection(a,b,compiled){for(let i=0;i<compiled.length;i++){const c=cmpValue(a[i],b[i],compiled[i]);if(c)return c;}return 0;}
function stableReference(rows,schema){
  const ds=compileSchema(schema),proj=rows.map(x=>projection(x,ds));
  return Array.from({length:rows.length},(_,i)=>i).sort((a,b)=>compareProjection(proj[a],proj[b],ds)||a-b);
}
function createApexXL(){
 let cap=0,keys=new Float64Array(0),ranks=new Uint32Array(0),scratch=new Uint32Array(0),hi=new Uint32Array(0),lo=new Uint32Array(0),bins=new Uint32Array(65536),out=[],dv=new DataView(new ArrayBuffer(8));
 function reserve(n){if(n<=cap)return;cap=n;keys=new Float64Array(n);ranks=new Uint32Array(n);scratch=new Uint32Array(n);hi=new Uint32Array(n);lo=new Uint32Array(n);out=new Array(n);}
 function radixFloat(n){
   let dh=0,dl=0,fh=0,fl=0;
   for(let i=0;i<n;i++){
     dv.setFloat64(0,keys[i],false);let h=dv.getUint32(0,false),l=dv.getUint32(4,false);
     if(h&0x80000000){h=(~h)>>>0;l=(~l)>>>0;}else h=(h^0x80000000)>>>0;
     hi[i]=h;lo[i]=l;ranks[i]=i;
     if(i){dh|=h^fh;dl|=l^fl;}else{fh=h;fl=l;}
   }
   let inp=ranks,dst=scratch,passes=0;
   for(let pass=0;pass<8;pass++){
     const bits=(pass<4?dl:dh),shift=(pass&3)*8;
     if(!((bits>>>shift)&255))continue;
     const word=pass<4?lo:hi;
     bins.fill(0,0,256);
     for(let i=0;i<n;i++)bins[(word[inp[i]]>>>shift)&255]++;
     let p=0;for(let b=0;b<256;b++){const v=bins[b];bins[b]=p;p+=v;}
     for(let i=0;i<n;i++){const x=inp[i];dst[bins[(word[x]>>>shift)&255]++]=x;}
     [dst,inp]=[inp,dst];passes++;
   }
   return {indices:inp,passes,path:'f64-radix'};
 }
 function tryRayCut(n,desc){
   // Exact cut witnesses: each active boundary is crossed by an inversion.
   // Keep this an optional sparse-data optimization, never an approximate sorter.
   const extreme=new Float64Array(n);let v=keys[n-1];
   for(let i=n-1;i>=0;i--){if(desc?keys[i]>v:keys[i]<v)v=keys[i];extreme[i]=v;}
   let max=keys[0],begin=-1,regions=[],area=0;
   for(let i=0;i<n-1;i++){
     if(desc?keys[i]<max:keys[i]>max)max=keys[i];
     const bad=desc?max<extreme[i+1]:max>extreme[i+1];
     if(bad){if(begin<0)begin=i;}
     else if(begin>=0){const end=i+1;regions.push([begin,end]);area+=end-begin;begin=-1;}
   }
   if(begin>=0){regions.push([begin,n]);area+=n-begin;}
   if(!regions.length||area>Math.min(n/4,regions.length*48)||regions.some(([a,b])=>b-a>96))return null;
   for(let i=0;i<n;i++)ranks[i]=i;
   for(const [start,end] of regions){
     const xs=[];for(let i=start;i<end;i++)xs.push(i);
     xs.sort((a,b)=>(desc?(keys[b]-keys[a]):(keys[a]-keys[b]))||a-b);
     for(let j=0;j<xs.length;j++)ranks[start+j]=xs[j];
   }
   return {indices:ranks,passes:1,path:'certified-ray-repair'};
 }
 function countInt(n,min,span,desc){
   bins.fill(0,0,span);
   for(let i=0;i<n;i++)bins[keys[i]-min]++;
   let p=0;
   if(!desc)for(let b=0;b<span;b++){const x=bins[b];bins[b]=p;p+=x;}
   else for(let b=span-1;b>=0;b--){const x=bins[b];bins[b]=p;p+=x;}
   for(let i=0;i<n;i++)ranks[bins[keys[i]-min]++]=i;
   return {indices:ranks,passes:2,path:'dense-index-count'};
 }
 function order(rows,schema,stats={}){
   if(!Array.isArray(rows))throw new TypeError('Expected record array');
   const ds=compileSchema(schema),n=rows.length;
   if(n>4294967295)throw new RangeError('Indices must fit in 32 bits');
   const start=typeof performance!=='undefined'?performance.now():Date.now();
   reserve(n);stats.n=n;stats.columns=ds.length;stats.keyReads=n*ds.length;stats.passes=0;
   if(n===0){stats.path='empty';return new Uint32Array(0);}
   let result;
   if(ds.length===1&&['number','balance','date','boolean','string-length','token-sum','array-length'].includes(ds[0].type)){
     const desc=ds[0].desc,nullable=[];let num=0,min=Infinity,max=-Infinity,globalOrdered=true,prevKey=null,integers=true,falls=0;
     for(let i=0;i<n;i++){
       const v=convert(rows[i],ds[0]);
       if(i&&cmpValue(prevKey,v,ds[0])>0){globalOrdered=false;falls++;}
       prevKey=v;
       if(v===null){nullable.push(i);continue;}
       if(!Number.isFinite(v))throw new TypeError('Nonfinite numeric key not supported by fast path');
       keys[num]=v;
       num++;if(!Number.isSafeInteger(v))integers=false;
       if(v<min)min=v;if(v>max)max=v;
     }
     if(globalOrdered){const identity=new Uint32Array(n);for(let i=0;i<n;i++)identity[i]=i;stats.path='ordered-zero-write';stats.passes=0;return identity;}
     // The full finite-key vector is dense only if there are no nulls.
     if(nullable.length===0){
       const span=max-min+1;
       if(n>=512&&falls<=Math.min(32,Math.max(2,(n/256)|0)))result=tryRayCut(n,desc);
       if(result){} else if(integers&&Number.isSafeInteger(span)&&span>0&&span<=Math.min(65536,Math.max(2048,n*3))){result=countInt(n,min,span,desc);}
       else if(n>64&&!desc)result=radixFloat(n);
       else if(n>64&&desc){result=radixFloat(n); // reverse equal-value groups, not individual ties
         const src=result.indices,dest=src===scratch?ranks:scratch;let p=0;
         for(let end=n;end>0;){let begin=end-1;while(begin>0&&keys[src[begin-1]]===keys[src[end-1]])begin--;
           for(let j=end-1;j>=begin;j--)dest[p++]=src[j];end=begin;}
         result={indices:dest,passes:result.passes+1,path:'f64-radix-desc'};
       }else{
         const ix=Array.from({length:n},(_,i)=>i);ix.sort((a,b)=>cmpValue(keys[a],keys[b],ds[0])||a-b);
         result={indices:ix,passes:1,path:'cached-numeric-native'};
       }
     }else{
       const ix=Array.from({length:n},(_,i)=>i),col=new Array(n);
       for(let i=0;i<n;i++)col[i]=convert(rows[i],ds[0]);
       ix.sort((a,b)=>cmpValue(col[a],col[b],ds[0])||a-b);
       result={indices:ix,passes:1,path:'nullable-cached'};
     }
   }else{
     const cols=ds.map(()=>new Array(n));
     for(let i=0;i<n;i++)for(let j=0;j<ds.length;j++)cols[j][i]=convert(rows[i],ds[j]);
     let sorted=true;
     scan:for(let i=1;i<n;i++)for(let j=0;j<ds.length;j++){
       const c=cmpValue(cols[j][i-1],cols[j][i],ds[j]);
       if(c>0){sorted=false;break scan;}if(c<0)break;
     }
     if(sorted){const identity=new Uint32Array(n);for(let i=0;i<n;i++)identity[i]=i;stats.path='ordered-zero-write';stats.passes=0;return identity;}
     let clustered=false;
     if(n>=512 && ds.length>1){
       const groups=new Map();
       for(let i=0;i<n;i++){
         const k=cols[0][i];let g=groups.get(k);
         if(!g){if(groups.size>=64){groups.clear();break;}g={key:k,items:[]};groups.set(k,g);}
         g.items.push(i);
       }
       if(groups.size>=2 && groups.size<=64){
         const orderedGroups=Array.from(groups.values()).sort((a,b)=>cmpValue(a.key,b.key,ds[0]));
         let cursor=0;
         for(const group of orderedGroups){
           const a=group.items;
           if(a.length>1)a.sort((u,v)=>{for(let j=1;j<ds.length;j++){const c=cmpValue(cols[j][u],cols[j][v],ds[j]);if(c)return c;}return u-v;});
           for(let i=0;i<a.length;i++)ranks[cursor++]=a[i];
         }
         result={indices:ranks,passes:2,path:'categorical-lead-clusters'};clustered=true;
       }
     }
     if(!clustered){
       const ix=Array.from({length:n},(_,i)=>i);
       ix.sort((a,b)=>{for(let j=0;j<ds.length;j++){const c=cmpValue(cols[j][a],cols[j][b],ds[j]);if(c)return c;}return a-b;});
       result={indices:ix,passes:1,path:'cached-composite-index'};
     }
   }
   stats.path=result.path;stats.passes=result.passes;
   // Copy the indices: reusable work buffers must never leak out to callers.
   return Uint32Array.from(result.indices.subarray?result.indices.subarray(0,n):result.indices);
 }
 function sort(rows,schema,stats={}){
   const ix=order(rows,schema,stats),n=ix.length;
   let writes=0;
   // Destination references are compact even when payload objects are huge.
   reserve(n);for(let i=0;i<n;i++)out[i]=rows[ix[i]];
   for(let i=0;i<n;i++)if(rows[i]!==out[i]){rows[i]=out[i];writes++;}
   stats.writes=writes;stats.referenceBytesApprox=8*n;
   return rows;
 }
 function sortedCopy(rows,schema,stats={}){const ix=order(rows,schema,stats);return Array.from(ix,i=>rows[i]);}
 return {order,sort,sortedCopy,compileSchema,project:(row,schema)=>projection(row,compileSchema(schema))};
}
return {createApexXL,compileSchema,projection,compareProjection,cmpValue,stableReference,balance};
});
