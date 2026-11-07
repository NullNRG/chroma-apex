/* APEX XL external stable JSONL sort.
 * Ordered spill runs, fixed fan-in merge, atomic output; Node.js 18+.
 * Processes records larger than RAM when each individual line fits available memory.
 */
'use strict';
const fs=require('node:fs');
const fsp=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const readline=require('node:readline');
const {once}=require('node:events');
const {createApexXL,compileSchema,projection,compareProjection}=require('./apex_massive');
async function put(stream,line){if(!stream.write(line))await once(stream,'drain');}
async function close(stream){stream.end();await once(stream,'finish');}
function scan(pathname){const stream=fs.createReadStream(pathname,{encoding:'utf8',highWaterMark:256*1024});const rl=readline.createInterface({input:stream,crlfDelay:Infinity});return {stream,rl,it:rl[Symbol.asyncIterator]()};}
class Heap{
 constructor(less){this.x=[];this.less=less;}
 push(v){const a=this.x;let i=a.length;a.push(v);while(i>0){const p=(i-1)>>1;if(!this.less(v,a[p]))break;a[i]=a[p];i=p;}a[i]=v;}
 pop(){const a=this.x,top=a[0],last=a.pop();if(a.length){let i=0;for(;;){const l=2*i+1,r=l+1;if(l>=a.length)break;const j=r<a.length&&this.less(a[r],a[l])?r:l;if(!this.less(a[j],last))break;a[i]=a[j];i=j;}a[i]=last;}return top;}
 get size(){return this.x.length;}
}
function parseRunLine(s,compiled){const p=s.indexOf('\t');if(p<0)throw new Error('Corrupted spill run');const seq=Number(s.slice(0,p)),raw=s.slice(p+1);if(!Number.isSafeInteger(seq))throw new Error('Corrupted spill sequence');const record=JSON.parse(raw);return {seq,raw,key:projection(record,compiled)};}
async function merge(inputs,output,compiled,finalOutput){
 const readers=inputs.map(scan),writer=fs.createWriteStream(output,{encoding:'utf8',highWaterMark:1024*1024});
 const heap=new Heap((a,b)=>{const c=compareProjection(a.item.key,b.item.key,compiled);return c<0||(c===0&&a.item.seq<b.item.seq);});
 try{
   for(let k=0;k<readers.length;k++){const r=await readers[k].it.next();if(!r.done)heap.push({k,item:parseRunLine(r.value,compiled)});}
   while(heap.size){const {k,item}=heap.pop();await put(writer,finalOutput?item.raw+'\n':item.seq+'\t'+item.raw+'\n');const r=await readers[k].it.next();if(!r.done)heap.push({k,item:parseRunLine(r.value,compiled)});}
   await close(writer);
 }catch(err){writer.destroy();throw err;}
 finally{for(const r of readers){r.rl.close();r.stream.destroy();}}
}
async function externalSortJsonl(inputPath,outputPath,schema,{chunkRecords=25000,fanIn=8,tempDir=null,onProgress=null}={}){
 if(!Number.isSafeInteger(chunkRecords)||chunkRecords<2)throw new RangeError('chunkRecords must be >=2');
 if(!Number.isSafeInteger(fanIn)||fanIn<2||fanIn>128)throw new RangeError('fanIn must be in 2..128');
 const compiled=compileSchema(schema),engine=createApexXL(),parent=tempDir||path.dirname(path.resolve(outputPath));
 await fsp.mkdir(parent,{recursive:true});const work=await fsp.mkdtemp(path.join(parent,'.apex-xl-'));
 let count=0,runCount=0,passes=0,files=[],batch=[],reader=null;
 async function flush(){
   if(!batch.length)return;
   const rec=batch.map(v=>v.record),ix=engine.order(rec,schema),file=path.join(work,`run-${runCount++}.jsonl`);
   const writer=fs.createWriteStream(file,{encoding:'utf8'});
   try{for(let i=0;i<ix.length;i++){const a=batch[ix[i]];await put(writer,a.seq+'\t'+a.raw+'\n');}await close(writer);}catch(err){writer.destroy();throw err;}
   files.push(file);batch=[];if(onProgress)onProgress({phase:'spill',records:count,runs:runCount});
 }
 try{
   reader=scan(inputPath);
   for await(const line of reader.rl){if(!line.trim())continue;const record=JSON.parse(line);batch.push({seq:count++,raw:line,record});if(batch.length>=chunkRecords)await flush();}
   reader=null;await flush();
   if(!files.length){await fsp.writeFile(path.join(work,'empty'),'');files=[path.join(work,'empty')];}
   while(files.length>fanIn){const next=[];for(let i=0;i<files.length;i+=fanIn){const group=files.slice(i,i+fanIn),name=path.join(work,`merge-${passes}-${i}.jsonl`);await merge(group,name,compiled,false);next.push(name);for(const g of group)await fsp.unlink(g); }files=next;passes++;if(onProgress)onProgress({phase:'merge',pass:passes,runs:files.length});}
   const tempOut=path.join(work,'result.jsonl');
   await merge(files,tempOut,compiled,true);passes++;
   // Use an atomic rename in the destination filesystem when possible.
   const destination=path.resolve(outputPath);
   try{await fsp.rename(tempOut,destination);}catch(err){if(err.code!=='EXDEV')throw err;const tmpDest=destination+'.apex-partial-'+process.pid;await fsp.copyFile(tempOut,tmpDest);await fsp.rename(tmpDest,destination);}
   return {records:count,initialRuns:runCount,mergePasses:passes,output:destination,chunkRecords,fanIn};
 }finally{if(reader){reader.rl.close();reader.stream.destroy();}await fsp.rm(work,{recursive:true,force:true});}
}
module.exports={externalSortJsonl};
if(require.main===module){
 const [,,input,output,schemaArg,chunkArg]=process.argv;
 if(!input||!output||!schemaArg){console.error('Usage: node external_jsonl.js input.jsonl output.jsonl schema.json [chunkRecords]');process.exitCode=2;}
 else{const s=require(path.resolve(schemaArg));externalSortJsonl(input,output,s,{chunkRecords:chunkArg?Number(chunkArg):25000,onProgress:p=>console.error(JSON.stringify(p))}).then(x=>console.log(JSON.stringify(x))).catch(e=>{console.error(e);process.exitCode=1;});}
}
