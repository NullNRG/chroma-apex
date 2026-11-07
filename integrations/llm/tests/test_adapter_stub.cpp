#include "llama.h"
#include "llama_cpp_sampler.h"
#include <cassert>
#include <cstdio>
extern "C" llama_sampler* llama_sampler_init(llama_sampler_i * iface,void*ctx){return new llama_sampler{iface,ctx};}
int main(){
    auto*sample=llama_sampler_init_chroma_apex(1,1,0,123);
    llama_token_data data[]={{23,.5f,0},{99,6.f,0},{4,1.f,0}};
    llama_token_data_array arr{data,3,-1,false};
    sample->iface->apply(sample,&arr);
    assert(arr.selected==1);
    auto*clone=sample->iface->clone(sample);
    clone->iface->apply(clone,&arr);
    assert(arr.selected==1);
    sample->iface->free(sample); delete sample;
    clone->iface->free(clone); delete clone;
    puts("PASS isolated llama sampler ABI-shaped shim");
}
