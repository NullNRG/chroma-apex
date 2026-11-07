#include "apex_llm.h"
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <random>
#include <vector>

static std::mt19937_64 gen(0xC0FFEE);
static uint64_t cases = 0;
static void verify(const std::vector<float>& v, const std::vector<uint32_t>& ks, const std::vector<float>& ps) {
    for (uint32_t k : ks) for(float p : ps) for (float temp : {0.0f, 0.3f, 0.8f, 1.4f}) for(double u : {0.0, 0.00001, 0.31, 0.8, 0.999999999}) {
        uint32_t a=UINT32_MAX, b=UINT32_MAX;
        apx_llm_stats sa={},sb={};
        int ra=apx_llm_sample(v.data(),(uint32_t)v.size(),temp,k,p,u,&a,&sa,0);
        int rb=apx_llm_sample(v.data(),(uint32_t)v.size(),temp,k,p,u,&b,&sb,1);
        if(ra!=rb || (ra==0 && (a!=b || sa.retained_count != sb.retained_count))) {
            std::fprintf(stderr,"FAIL n=%zu k=%u p=%g temp=%g u=%g a=%u b=%u ra=%d rb=%d candidates=%u/%u keep=%u/%u\n",v.size(),k,p,temp,u,a,b,ra,rb,sa.candidate_count,sb.candidate_count,sa.retained_count,sb.retained_count);
            std::abort();
        }
        for (int method : {2,3}) {
            uint32_t other=UINT32_MAX; apx_llm_stats ss={};
            int rc=apx_llm_sample(v.data(),(uint32_t)v.size(),temp,k,p,u,&other,&ss,method);
            if(rc!=rb || (rc==0 && (other!=b || ss.retained_count!=sb.retained_count))) {
                fprintf(stderr,"METHOD FAIL %d n=%zu k=%u p=%g t=%g u=%g expected=%u got=%u\n",method,v.size(),k,p,temp,u,b,other); abort();
            }
        }
        ++cases;
    }
}
int main() {
    const bool quick=std::getenv("APX_QUICK_TEST") != nullptr;
    for (size_t n : {size_t(1),size_t(2),size_t(5),size_t(40),size_t(129),size_t(1024),size_t(8192),size_t(32768)}) {
        if(quick && n>1024) continue;
        std::vector<float> v(n);
        for(int pattern=0;pattern<(quick?4:8);pattern++) {
            std::normal_distribution<float> d(0, 3);
            for(size_t i=0;i<n;i++) {
                switch(pattern) {
                case 0:v[i]=d(gen);break;
                case 1:v[i]=float(i);break;
                case 2:v[i]=float(n-i);break;
                case 3:v[i]=float((int)(i%17)-8);break;
                case 4:v[i]=1.0f;break;
                case 5:v[i]=float(int(gen()%100)-90)/10;break;
                case 6:v[i]=(i%29==0)?-std::numeric_limits<float>::infinity():d(gen);break;
                case 7:v[i]=(i%23==0)?std::numeric_limits<float>::quiet_NaN():d(gen);break;
                }
            }
            auto ks=std::vector<uint32_t>{0,1,2,40,128,129,500,8000,(uint32_t)n};
            verify(v,ks,{0.01f,0.5f,0.9f,1.0f});
        }
        fprintf(stderr,"PASS n=%zu\n",n);
    }
    for (size_t n : {size_t(4),size_t(130),size_t(9000)}) {
        if(quick && n>130)continue;
        std::vector<float> v(n, 0.0f);
        v[0]=std::numeric_limits<float>::infinity();v[1]=std::numeric_limits<float>::infinity();v[2]=-std::numeric_limits<float>::infinity();v[3]=std::numeric_limits<float>::quiet_NaN();
        verify(v,{0,1,2,40,129,8000},{0.2f,0.95f,1.0f});
    }
    float masked[] = {NAN,-INFINITY};uint32_t output=999;
    assert(apx_llm_sample(masked,2,0.8f,40,0.9f,0.5,&output,nullptr,0)==2);
    assert(apx_llm_sample(masked,2,0.8f,40,0.9f,0.5,&output,nullptr,1)==2);
    assert(apx_llm_sample(masked,2,-1.f,40,0.9f,0.5,&output,nullptr,0)==1);
    std::printf("PASS %llu deterministic comparisons to reference\n",(unsigned long long)cases);
}
