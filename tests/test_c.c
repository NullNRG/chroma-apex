/* SPDX-License-Identifier: MIT */
#include "chroma_apex.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
static uint64_t state=UINT64_C(0x1234567abcde0123);
static uint64_t rng(void){state^=state>>12;state^=state<<25;state^=state>>27;return state*UINT64_C(2685821657736338717);}
static int compare_f(double a,double b){
  if(isnan(a))return isnan(b)?0:1;
  if(isnan(b))return -1;
  return (a>b)-(a<b);
}
static void check_f(const double *a,size_t n){
  uint32_t *ix=malloc((n?n:1)*sizeof(uint32_t));apx_stats s;
  assert(apx_order_f64(a,n,ix,&s)==APX_OK);
  assert(s.count==n);
  unsigned char *seen=calloc(n?n:1,1);
  for(size_t i=0;i<n;i++){
    assert(ix[i]<n&&!seen[ix[i]]);seen[ix[i]]=1;
    if(i){int c=compare_f(a[ix[i-1]],a[ix[i]]);assert(c<=0);if(!c)assert(ix[i-1]<ix[i]);}
  }
  free(seen);free(ix);
}
static void check_i(const int64_t *a,size_t n){
  uint32_t *ix=malloc((n?n:1)*sizeof(uint32_t));apx_stats s;
  assert(apx_order_i64(a,n,ix,&s)==APX_OK);
  for(size_t i=1;i<n;i++){assert(a[ix[i-1]]<=a[ix[i]]);if(a[ix[i-1]]==a[ix[i]])assert(ix[i-1]<ix[i]);}
  free(ix);
}
static void check_u(const uint64_t *a,size_t n){
  uint32_t *ix=malloc((n?n:1)*sizeof(uint32_t));apx_stats s;
  assert(apx_order_u64(a,n,ix,&s)==APX_OK);
  for(size_t i=1;i<n;i++){assert(a[ix[i-1]]<=a[ix[i]]);if(a[ix[i-1]]==a[ix[i]])assert(ix[i-1]<ix[i]);}
  free(ix);
}
int main(void){
  assert(apx_abi_version()==(APX_VERSION_MAJOR<<16|APX_VERSION_MINOR));
  assert(apx_order_f64(NULL,0,NULL,NULL)==APX_OK);
  assert(apx_order_f64(NULL,1,NULL,NULL)==APX_BAD_ARGUMENT);
  double edge[]={NAN,-0.,0.,INFINITY,-INFINITY,1.,NAN,-1.,1.,-INFINITY,INFINITY,3.};
  check_f(edge,sizeof(edge)/sizeof(edge[0]));
  int64_t edges[]={INT64_MIN,INT64_MAX,0,-1,1,INT64_MIN,INT64_MAX};
  uint64_t ue[]={UINT64_MAX,0,UINT64_MAX,UINT64_C(1)<<63,0,1};
  check_i(edges,7);check_u(ue,6);
  const size_t cases[]={1,2,3,5,17,32,63,120,255,1000,8192,100000};
  unsigned long checks=0;
  for(size_t z=0;z<sizeof(cases)/sizeof(*cases);z++){
    size_t n=cases[z];double *a=malloc(n*sizeof *a);int64_t *b=malloc(n*sizeof *b);uint64_t *c=malloc(n*sizeof *c);
    for(int pattern=0;pattern<8;pattern++){
      for(size_t i=0;i<n;i++){
        uint64_t v=rng();
        switch(pattern){
          case 0:a[i]=(double)(v%17);break;
          case 1:a[i]=(double)(n-i);break;
          case 2:a[i]=(double)i;break;
          case 3:a[i]=(double)((int64_t)(v>>32))/100.;break;
          case 4:a[i]=(double)((int64_t)(v>>24))*(1./65536.);break;
          case 5:a[i]=i%31==0?NAN:(i%13==0?INFINITY:(double)(v%1000)-500.);break;
          case 6:a[i]=i%11==0?-0.:0.;break;
          default:a[i]=i%37==0?NAN:(double)((i/19)%32);break;
        }
        b[i]=pattern%3?(int64_t)v:(int64_t)(v%49)-25;
        c[i]=pattern%3?v:v%61;
      }
      check_f(a,n);check_i(b,n);check_u(c,n);checks+=3;
    }
    free(a);free(b);free(c);
  }
  printf("PASS C native correctness: %lu suites and edge cases\n",checks);
  return 0;
}
