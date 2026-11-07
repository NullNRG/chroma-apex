// SPDX-License-Identifier: MIT
// End-to-end cached-key permutation benchmark, not a payload copy benchmark.
// Existing IPS4o (BSD-2-Clause) may be provided by -DAPX_USE_IPS4O -I/path.
#include "chroma_apex.h"
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#if __has_include(<boost/sort/pdqsort/pdqsort.hpp>)
#include <boost/sort/pdqsort/pdqsort.hpp>
#define APX_HAVE_PDQ 1
#endif
#ifdef APX_USE_IPS4O
#include "ips4o.hpp"
#endif
using clk=std::chrono::steady_clock;
static double median(std::vector<double> x){std::sort(x.begin(),x.end());return x[x.size()/2];}
static double key(double x){return std::isnan(x)?INFINITY:x;}
static bool less(double a,double b){if(std::isnan(a))return false;if(std::isnan(b))return true;return a<b;}
static void verify(const std::vector<double>& a,const std::vector<uint32_t>& p){
 if(p.size()!=a.size())std::abort();
 std::vector<char> seen(p.size());
 for(size_t i=0;i<p.size();i++){
   if(p[i]>=p.size()||seen[p[i]])std::abort();seen[p[i]]=1;
   if(i){double x=a[p[i-1]],y=a[p[i]];
     if(less(y,x)||(!less(x,y)&&p[i-1]>p[i]))std::abort();
   }
 }
}
int main(int argc,char **argv){
 int repeat=argc>1?std::atoi(argv[1]):7;
 if(repeat<3)repeat=3;
 std::mt19937_64 rng(0x5eed);
 std::puts("size,pattern,method,median_ms,records_per_second");
 for(size_t n:{size_t(120),size_t(10000),size_t(100000),size_t(500000)}){
  for(std::string pattern:{"random64","compact","ordered","mostly-ordered","reverse"}){
   std::vector<double> v(n);
   for(size_t i=0;i<n;i++){
      if(pattern=="random64")v[i]=(double)(int64_t)rng()/1048576.0;
      if(pattern=="compact")v[i]=(double)(rng()%1024);
      if(pattern=="ordered"||pattern=="mostly-ordered")v[i]=(double)i;
      if(pattern=="reverse")v[i]=(double)(n-i);
   }
   if(pattern=="mostly-ordered")for(size_t j=0;j<n/1000;j++){
      size_t x=rng()%n,y=rng()%n;std::swap(v[x],v[y]);
   }
   // Full output verification happens outside timed measurements.
   auto run=[&](int which, std::vector<uint32_t>& out){
     out.resize(n);
     if(which==0){
       if(apx_order_f64(v.data(),n,out.data(),nullptr)!=APX_OK)std::abort();
     }else{
       std::iota(out.begin(),out.end(),0);
       auto comp=[&](uint32_t x,uint32_t y){
         if(less(v[x],v[y]))return true;
         if(less(v[y],v[x]))return false;
         return x<y;
       };
       if(which==1)std::sort(out.begin(),out.end(),comp);
       if(which==2)std::stable_sort(out.begin(),out.end(),[&](uint32_t x,uint32_t y){return less(v[x],v[y]);});
#ifdef APX_HAVE_PDQ
       if(which==3)boost::sort::pdqsort(out.begin(),out.end(),comp);
#endif
#ifdef APX_USE_IPS4O
       if(which==4)ips4o::sort(out.begin(),out.end(),comp);
#endif
     }
   };
   int num=3;
#ifdef APX_HAVE_PDQ
   num=4;
#endif
#ifdef APX_USE_IPS4O
   num=5;
#endif
   for(int method=0;method<num;method++){
     std::vector<uint32_t> out;
     run(method,out);verify(v,out);
     std::vector<double> timings;
     for(int r=0;r<repeat;r++){
       auto t0=clk::now();run(method,out);auto t1=clk::now();
       timings.push_back(std::chrono::duration<double,std::milli>(t1-t0).count());
     }
     const char *name=method==0?"apex-native":method==1?"std-sort-stable-ties":method==2?"std-stable-sort":method==3?"boost-pdqsort-stable-ties":"ips4o-stable-ties";
     const double ms=median(timings);
     std::printf("%zu,%s,%s,%.6f,%.0f\n",n,pattern.c_str(),name,ms,n*1000./ms);
   }
  }
 }
}
