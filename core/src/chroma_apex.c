/* SPDX-License-Identifier: MIT
 * CHROMA APEX C core. Common stable counting/radix technique;
 * no claim of novel asymptotic complexity or universal speed supremacy.
 */
#include "chroma_apex.h"
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

/* key normalization makes the IEEE754 total ordering compatible with unsigned
 * integer comparisons; NaNs compare as one equivalence class, signed zeros tie. */
static uint64_t float_key(double x) {
  uint64_t u;
  if (isnan(x)) return UINT64_MAX;
  if (x == 0.) x = 0.;
  memcpy(&u, &x, sizeof u);
  return (u & UINT64_C(0x8000000000000000)) ? ~u : u ^ UINT64_C(0x8000000000000000);
}
static void init_stats(apx_stats *s,size_t n) {
  if(s){memset(s,0,sizeof *s);s->count=n;s->path=APX_EMPTY;}
}
static int ordered_u64(const uint64_t *keys,size_t n, uint32_t *out,apx_stats *s) {
  for(size_t i=0;i<n;i++)out[i]=(uint32_t)i;
  for(size_t i=1;i<n;i++)if(keys[i-1]>keys[i])return 0;
  if(s)s->path=APX_ORDERED;
  return 1;
}
static int radix_u64(const uint64_t *k,size_t n,uint32_t *out,apx_stats *s){
  uint32_t *scratch=(uint32_t*)malloc(n*sizeof(uint32_t));
  if(!scratch)return APX_NO_MEMORY;
  uint32_t *from=out,*to=scratch;
  uint64_t v0=k[0],diff=0;
  for(size_t i=1;i<n;i++)diff|=v0^k[i];
  uint32_t passes=0;
  for(unsigned pass=0;pass<8;pass++){
    unsigned shift=pass*8;
    if(((diff>>shift)&255u)==0)continue;
    size_t counts[256]={0};
    for(size_t i=0;i<n;i++)counts[(k[from[i]]>>shift)&255u]++;
    size_t pos=0;
    for(size_t b=0;b<256;b++){size_t v=counts[b];counts[b]=pos;pos+=v;}
    for(size_t i=0;i<n;i++){
      uint32_t ix=from[i];to[counts[(k[ix]>>shift)&255u]++]=ix;
    }
    uint32_t *tmp=from;from=to;to=tmp;passes++;
  }
  if(from!=out)memcpy(out,from,n*sizeof(uint32_t));
  if(s){s->passes=passes;s->path=APX_RADIX;s->scratch_bytes_peak=n*sizeof(uint32_t);}
  free(scratch);return APX_OK;
}
static int count_dense(const uint64_t *k,size_t n,uint32_t *out,uint64_t min,uint64_t span,apx_stats *s){
  size_t *counts=(size_t*)calloc((size_t)span,sizeof(size_t));
  if(!counts)return APX_NO_MEMORY;
  for(size_t i=0;i<n;i++)counts[(size_t)(k[i]-min)]++;
  size_t p=0;
  for(size_t i=0;i<(size_t)span;i++){size_t v=counts[i];counts[i]=p;p+=v;}
  for(size_t i=0;i<n;i++)out[counts[(size_t)(k[i]-min)]++]=(uint32_t)i;
  if(s){s->passes=2;s->path=APX_COUNTING;s->scratch_bytes_peak=span*sizeof(size_t);}
  free(counts);return APX_OK;
}
static int core_u64(const uint64_t *k,size_t n,uint32_t *out,apx_stats *s){
  if(ordered_u64(k,n,out,s))return APX_OK;
  /* Reverse monotonic stream: emit equal-key groups in their original order.
   * This is stable and avoids a histogram or radix workspace. */
  int descending=1;
  for(size_t i=1;i<n;i++)if(k[i-1]<k[i]){descending=0;break;}
  if(descending){
    size_t pos=n,dest=0;
    while(pos){size_t end=pos;uint64_t v=k[pos-1];
      do{pos--;}while(pos&&k[pos-1]==v);
      for(size_t j=pos;j<end;j++)out[dest++]=(uint32_t)j;
    }
    if(s)s->path=APX_REVERSED;
    return APX_OK;
  }
  uint64_t min=k[0],max=k[0];
  for(size_t i=1;i<n;i++){
    if(k[i]<min)min=k[i];
    if(k[i]>max)max=k[i];
  }
  /* Overflow-safe span check and capped histogram. */
  if(max-min < UINT64_C(65536) && max-min < n*4u)
    return count_dense(k,n,out,min,max-min+1u,s);
  return radix_u64(k,n,out,s);
}
static int order_common(const void *keys,size_t n,uint32_t *out,apx_stats *s,int type){
  init_stats(s,n);
  if(n>UINT32_MAX)return APX_TOO_LARGE;
  if(n==0)return APX_OK;
  if(!keys||!out)return APX_BAD_ARGUMENT;
  if(n>SIZE_MAX/sizeof(uint64_t))return APX_TOO_LARGE;
  uint64_t *normalized=(uint64_t*)malloc(n*sizeof(uint64_t));
  if(!normalized)return APX_NO_MEMORY;
  if(type==0){const double *a=(const double*)keys;for(size_t i=0;i<n;i++)normalized[i]=float_key(a[i]);}
  if(type==1){memcpy(normalized,keys,n*sizeof(uint64_t));}
  if(type==2){const int64_t *a=(const int64_t*)keys;for(size_t i=0;i<n;i++){
      uint64_t v;memcpy(&v,&a[i],sizeof v);
      normalized[i]=v ^ UINT64_C(0x8000000000000000);
  }}
  int result=core_u64(normalized,n,out,s);
  if(s)s->scratch_bytes_peak+=n*sizeof(uint64_t);
  free(normalized);
  return result;
}
int apx_order_f64(const double*k,size_t n,uint32_t*out,apx_stats*s){return order_common(k,n,out,s,0);}
int apx_order_u64(const uint64_t*k,size_t n,uint32_t*out,apx_stats*s){return order_common(k,n,out,s,1);}
int apx_order_i64(const int64_t*k,size_t n,uint32_t*out,apx_stats*s){return order_common(k,n,out,s,2);}
const char *apx_status_string(int x){
  switch(x){case APX_OK:return "ok";case APX_BAD_ARGUMENT:return "bad argument";
  case APX_TOO_LARGE:return "too many elements";case APX_NO_MEMORY:return "out of memory";
  default:return "unknown error";}
}
uint32_t apx_abi_version(void){return (APX_VERSION_MAJOR<<16)|APX_VERSION_MINOR;}
