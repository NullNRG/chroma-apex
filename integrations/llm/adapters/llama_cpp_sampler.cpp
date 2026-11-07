/* SPDX-License-Identifier: MIT
 * Optional llama.cpp custom sampler adapter. Compiles as a separate translation
 * unit when an upstream llama.cpp checkout and its public header are available.
 * Replaces a top-k/top-p/temp/dist sampling chain, not penalties or grammar.
 * NOTE: not compiled against upstream in this environment: no llama.cpp source.
 */
#include "apex_llm.h"
#include "llama.h"
#include <cstdint>
#include <limits>
#include <random>
#include <vector>
#include <algorithm>

namespace {
struct State {
    int32_t top_k;
    float top_p;
    float temperature;
    std::mt19937 rng;
    std::vector<float> scores;
};
static const char * sampler_name(const llama_sampler*) {return "chroma-apex-llm";}
static void sampler_apply(llama_sampler * sampler, llama_token_data_array * candidates) {
    State * s=static_cast<State*>(sampler->ctx);
    if(!candidates || !candidates->size) return;
    s->scores.resize(candidates->size);
    for(size_t i=0;i<candidates->size;i++)s->scores[i]=candidates->data[i].logit;
    // Uniform entropy source local to this sampler (different RNG sequence than upstream).
    double u=std::generate_canonical<double, 53>(s->rng);
    uint32_t chosen=0;
    const auto len=(uint32_t)std::min(candidates->size,size_t(UINT32_MAX));
    int rc=apx_llm_sample(s->scores.data(),len,s->temperature,
        s->top_k<=0?0u:(uint32_t)s->top_k,s->top_p,u,&chosen,nullptr,0);
    if(rc==0) candidates->selected=chosen;
    // If all candidates are masked, leave `selected` unchanged so the caller's
    // existing failure policy remains authoritative.
}
static llama_sampler * sampler_clone(const llama_sampler * src);
static void sampler_free(llama_sampler * sampler){delete static_cast<State*>(sampler->ctx);}
static llama_sampler_i iface={
    sampler_name, nullptr, sampler_apply, nullptr, sampler_clone, sampler_free,
    nullptr, nullptr, nullptr, nullptr, nullptr, nullptr
};
static llama_sampler * sampler_clone(const llama_sampler *src) {
    return llama_sampler_init(&iface,new State(*static_cast<const State*>(src->ctx)));
}
}
extern "C" llama_sampler * llama_sampler_init_chroma_apex(
    int32_t top_k,float top_p,float temperature,uint32_t seed) {
    auto * s=new State{top_k,top_p,temperature,std::mt19937(seed),{}};
    return llama_sampler_init(&iface,s);
}
