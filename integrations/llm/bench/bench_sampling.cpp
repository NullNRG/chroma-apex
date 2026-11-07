#include "apex_llm.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include <string>
static volatile uint64_t checksum=0;
static double one(const std::vector<float>& v, unsigned k, float p, int method, size_t reps) {
    for(int i=0;i<5;i++){uint32_t token;apx_llm_sample(v.data(),v.size(),0.8f,k,p,0.41,&token,nullptr,method);checksum+=token;}
    std::vector<double> durations;
    durations.reserve(5);
    for(int batch=0;batch<5;batch++) {
        auto s=std::chrono::steady_clock::now();
        for(size_t r=0;r<reps;r++){
            uint32_t token;
            int rc=apx_llm_sample(v.data(),(uint32_t)v.size(),0.8f,k,p,((r%89)+.5)/90.0,&token,nullptr,method);
            if(rc) abort();checksum+=token;
        }
        auto e=std::chrono::steady_clock::now();
        durations.push_back(std::chrono::duration<double,std::micro>(e-s).count()/reps);
    }
    std::sort(durations.begin(),durations.end());return durations[2];
}
int main(int argc,char**argv) {
    std::mt19937 g(127);
    size_t multiplier=argc>1?std::stoul(argv[1]):1;
    std::printf("vocab,distribution,top_k,top_p,fullsort_us,partialsort_us,nthsort_us,apex_us,best_standard_us,speedup_vs_best_standard\n");
    for(int n : {8192,32768,128000}) for(const char* distribution : {"normal","flat","masked"}) {
        std::vector<float> v(n);
        std::normal_distribution<float> norm(0,2.4f);
        for(int j=0;j<n;j++){
            if(!strcmp(distribution,"normal"))v[j]=norm(g);
            else if(!strcmp(distribution,"flat"))v[j]=float(int(g()%128)-64)/16.0f;
            else v[j]=(j%10==0)?-INFINITY:norm(g);
        }
        for(unsigned k : {1u,40u,1024u,8192u,0u}) {
            if(k>(unsigned)n)continue;
            float p=k==0?0.95f:1.0f;
            size_t reps=std::max<size_t>(2, 12*8192/n)*multiplier;
            double ref=one(v,k,p,1,reps),partial=one(v,k,p,2,reps),nth=one(v,k,p,3,reps),apex=one(v,k,p,0,reps);
            double standard=std::min({ref,partial,nth});
            std::printf("%d,%s,%u,%.2f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f\n",n,distribution,k,p,ref,partial,nth,apex,standard,standard/apex);
            std::fflush(stdout);
        }
    }
    std::fprintf(stderr,"checksum=%llu\n",(unsigned long long)checksum);
}
